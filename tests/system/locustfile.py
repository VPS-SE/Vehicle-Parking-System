"""Locust load test for Vehicle Parking System (TC-18, TC-36).

Signed-in drivers search availability and load the occupancy page.
"""

import re
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from locust import HttpUser, between, events, task

SHARED_DATA = {
    "sessionid": None,
    "csrftoken": None,
    "vehicle_id": "1",
}


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Set up a signed-in driver account and registered vehicle once for all workers."""
    host = environment.host or "http://127.0.0.1:8100"
    session = requests.Session()
    ts = int(time.time() * 1000)
    email = f"locust_driver_{ts}@example.com"
    mobile = f"9{ts % 1000000000:09d}"
    plate = f"KA05LC{ts % 9000 + 1000}"

    # 1. Register driver
    session.get(f"{host}/accounts/register/")
    csrf = session.cookies.get("csrftoken")
    session.post(
        f"{host}/accounts/register/",
        data={
            "csrfmiddlewaretoken": csrf,
            "full_name": "Locust Driver",
            "email": email,
            "mobile": mobile,
            "password": "SysTest!2026pass",
        },
        headers={"Referer": f"{host}/accounts/register/"},
    )

    # 2. Add vehicle
    csrf = session.cookies.get("csrftoken")
    session.post(
        f"{host}/vehicles/",
        data={
            "csrfmiddlewaretoken": csrf,
            "registration_no": plate,
            "vehicle_type": "Car",
            "nickname": "Locust Car",
        },
        headers={"Referer": f"{host}/vehicles/"},
    )

    # 3. Find vehicle ID
    r = session.get(f"{host}/reservations/search/")
    match = re.search(r'<option\s+value="(\d+)"[^>]*>' + plate, r.text)
    vehicle_id = match.group(1) if match else "1"

    SHARED_DATA["sessionid"] = session.cookies.get("sessionid")
    SHARED_DATA["csrftoken"] = session.cookies.get("csrftoken")
    SHARED_DATA["vehicle_id"] = vehicle_id


class DriverUser(HttpUser):
    wait_time = between(0.5, 1.5)

    def on_start(self):
        if SHARED_DATA["sessionid"]:
            self.client.cookies.set("sessionid", SHARED_DATA["sessionid"])
        if SHARED_DATA["csrftoken"]:
            self.client.cookies.set("csrftoken", SHARED_DATA["csrftoken"])

    @task(3)
    def search_availability(self):
        """TC-18: Driver searches slot availability."""
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        vehicle_id = SHARED_DATA.get("vehicle_id", "1")
        params = f"lot=1&vehicle={vehicle_id}&start={tomorrow}T10:00&end={tomorrow}T12:00"
        self.client.get(
            f"/reservations/search/?{params}",
            name="/reservations/search/",
        )

    @task(1)
    def load_occupancy(self):
        """TC-28: Driver views live occupancy page."""
        self.client.get(
            "/lots/occupancy/",
            name="/lots/occupancy/",
        )
