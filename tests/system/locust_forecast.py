"""Load test for the forecast service (TC-36, NFR-PERF-05): GET /v1/forecast."""

from datetime import datetime, timedelta
from random import choice, randint
from zoneinfo import ZoneInfo

from locust import HttpUser, between, task

IST = ZoneInfo("Asia/Kolkata")


class ForecastClient(HttpUser):
    wait_time = between(0.05, 0.2)

    @task
    def forecast(self):
        arrival = datetime.now(IST) + timedelta(minutes=randint(10, 23 * 60))
        self.client.get(
            "/v1/forecast",
            params={
                "lot_id": 1,
                "vehicle_type": choice(["Car", "TwoWheeler", "EV"]),
                "arrival": arrival.isoformat(timespec="minutes"),
            },
            name="/v1/forecast",
        )
