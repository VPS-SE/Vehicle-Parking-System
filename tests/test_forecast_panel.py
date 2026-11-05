"""FR-FCST-01 and FR-FCST-03 on the search page: the forecast panel and its fallback (TC-20)."""

import json
import threading
import time as clock
from datetime import datetime, time, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar
from unittest import mock
from urllib.parse import parse_qs, urlparse

import pytest
from django.utils import timezone

from vps.accounts.models import User
from vps.lots.models import Lot, Slot
from vps.vehicles.models import Vehicle

pytestmark = pytest.mark.django_db
NOW = timezone.make_aware(datetime(2026, 11, 5, 8, 0))


class Stub(BaseHTTPRequestHandler):
    reply: ClassVar[dict] = {}
    delay = 0.0
    requests: ClassVar[list] = []

    def do_GET(self):
        Stub.requests.append(parse_qs(urlparse(self.path).query))
        clock.sleep(Stub.delay)
        body = json.dumps(Stub.reply).encode()
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *args):
        pass


@pytest.fixture
def service(settings):
    server = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    Stub.delay, Stub.requests = 0.0, []
    Stub.reply = {"probability": 0.6, "band": "Medium", "estimate": True, "model_version": "1"}
    settings.FORECAST_URL = f"http://127.0.0.1:{server.server_port}"
    yield Stub
    server.shutdown()
    server.server_close()


@pytest.fixture(autouse=True)
def fixed_now():
    with mock.patch("django.utils.timezone.now", return_value=NOW):
        yield


@pytest.fixture
def lot():
    lot = Lot.objects.create(name="F", address="1 Road", opens_at=time(6), closes_at=time(23))
    Slot.objects.create(lot=lot, code="S1", distance_rank=1)
    return lot


@pytest.fixture
def driver(client):
    driver = User.objects.create_user(email="d@example.com", mobile="9876543210")
    Vehicle.objects.create(owner=driver, registration_no="KA01AB1234", vehicle_type="Car")
    client.force_login(driver)
    return driver


def search(client, lot, driver, start=NOW + timedelta(hours=1)):
    local = timezone.localtime(start)
    return client.get(
        "/reservations/search/",
        {
            "lot": lot.pk,
            "vehicle": driver.vehicles.get().pk,
            "start": local.strftime("%Y-%m-%dT%H:%M"),
            "end": (local + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M"),
        },
    )


def test_panel_shows_percent_band_and_estimate(client, service, lot, driver):
    response = search(client, lot, driver)
    assert response.context["forecast"] == {"percent": 60, "band": "Medium", "estimate": True}
    assert "60%</strong> (Medium) · Estimate" in response.content.decode()
    sent = service.requests[0]
    assert sent["lot_id"] == [str(lot.pk)] and sent["vehicle_type"] == ["Car"]
    assert datetime.fromisoformat(sent["arrival"][0]) == NOW + timedelta(hours=1)


def test_tc20_slow_service_does_not_hold_up_search(client, service, lot, driver):
    service.delay = 5
    started = clock.monotonic()
    response = search(client, lot, driver)
    elapsed = clock.monotonic() - started
    assert response.status_code == 200
    assert response.context["slot_count"] == 1
    assert "Forecast not available" in response.content.decode()
    assert elapsed < 3, f"search took {elapsed:.1f} s"


@pytest.mark.parametrize(
    "reply",
    [{"probability": 1.7, "band": "High"}, {"band": "High"}, {"probability": 0.5, "band": "Huge"}],
)
def test_bad_answers_count_as_not_available(client, service, lot, driver, reply):
    service.reply = reply
    assert search(client, lot, driver).context["forecast"] == {"message": "Forecast not available"}


def test_service_down_or_not_configured(client, settings, lot, driver):
    settings.FORECAST_URL = "http://127.0.0.1:9"  # nothing listens on the discard port
    assert search(client, lot, driver).context["forecast"]["message"] == "Forecast not available"
    settings.FORECAST_URL = ""
    response = search(client, lot, driver)
    assert response.context["slot_count"] == 1
    assert response.context["forecast"]["message"] == "Forecast not available"


def test_no_forecast_beyond_24_hours(client, service, lot, driver):
    response = search(client, lot, driver, start=NOW + timedelta(days=2))
    assert "next 24 hours" in response.context["forecast"]["message"]
    assert not service.requests


def test_staff_need_a_vehicle_type_for_a_forecast(client, service, lot):
    client.force_login(User.objects.create_user(email="g@example.com", role=User.Role.ATTENDANT))
    local = timezone.localtime(NOW + timedelta(hours=1))
    params = {
        "lot": lot.pk,
        "start": local.strftime("%Y-%m-%dT%H:%M"),
        "end": (local + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
    }
    assert (
        "vehicle type" in client.get("/reservations/search/", params).context["forecast"]["message"]
    )
    params["vehicle_type"] = "EV"
    assert client.get("/reservations/search/", params).context["forecast"]["band"] == "Medium"
    assert service.requests[-1]["vehicle_type"] == ["EV"]
