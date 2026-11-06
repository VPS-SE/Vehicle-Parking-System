"""Task 7: JSON feeds behind the live lot map (state per bay, parked vehicles for search)."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from vps.accounts.models import User
from vps.factories import make_driver, make_lot, make_reservation, make_staff
from vps.reservations.models import Reservation

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client(client):
    client.force_login(make_staff(role=User.Role.ADMIN))
    return client


@pytest.fixture
def parked():
    lot = make_lot(name="PES RR Campus Back Gate", slots={"TwoWheeler": 2})
    driver = make_driver()
    now = timezone.now()
    reservation = make_reservation(
        driver,
        lot.slots.get(code="TW-001"),
        now - timedelta(minutes=30),
        status=Reservation.Status.ACTIVE,
        entry_time=now - timedelta(minutes=25),
        vehicle_reg_no="KA05DM0001",
    )
    return lot, reservation


def test_state_json_shape(admin_client, parked):
    lot, reservation = parked
    data = admin_client.get(reverse("lots:map_state", args=[lot.pk])).json()

    assert set(data) == {"updated_at", "slots"}
    taken = data["slots"][str(reservation.slot_id)]
    assert taken["state"] == "occupied"
    assert taken["code"] == "TW-001"
    assert taken["type"] == "TwoWheeler"
    assert taken["reg"] == "KA05DM0001"
    assert taken["ref"] == reservation.booking_ref
    assert taken["driver"] == reservation.driver.full_name
    assert taken["since"] == reservation.entry_time.isoformat()

    free = data["slots"][str(lot.slots.get(code="TW-002").pk)]
    assert free == {"state": "free", "code": "TW-002", "type": "TwoWheeler"}


def test_state_json_archived_lot_is_404(admin_client, parked):
    lot, _ = parked
    lot.is_archived = True
    lot.save()
    assert admin_client.get(reverse("lots:map_state", args=[lot.pk])).status_code == 404


def test_parked_json_lists_active_vehicles(admin_client, parked):
    lot, reservation = parked
    data = admin_client.get(reverse("lots:map_parked")).json()
    assert data == [
        {
            "reg": "KA05DM0001",
            "lot_id": lot.pk,
            "lot": "PES RR Campus Back Gate",
            "slot_id": reservation.slot_id,
            "code": "TW-001",
        }
    ]


@pytest.mark.parametrize("role", [User.Role.DRIVER, User.Role.ATTENDANT])
def test_json_is_admin_only(client, parked, role):
    lot, _ = parked
    client.force_login(make_staff(role=role))
    assert client.get(reverse("lots:map_state", args=[lot.pk])).status_code == 403
    assert client.get(reverse("lots:map_parked")).status_code == 403


def test_admin_page_wires_live_feeds(admin_client, parked):
    lot, _ = parked
    content = admin_client.get(reverse("lots:map"), {"lot": lot.pk}).content.decode()
    assert f'data-state-url="{reverse("lots:map_state", args=[lot.pk])}"' in content
    assert f'data-parked-url="{reverse("lots:map_parked")}"' in content
    assert "js/lotmap.js" in content
    assert 'data-counter="occupied"' in content
    assert "data-lotmap-search" in content


def test_driver_page_loads_script_without_live_feeds(client, parked):
    _, reservation = parked
    client.force_login(reservation.driver)
    content = client.get(
        reverse("reservations:slot_map", args=[reservation.booking_ref])
    ).content.decode()
    assert "js/lotmap.js" in content
    assert "data-state-url" not in content
