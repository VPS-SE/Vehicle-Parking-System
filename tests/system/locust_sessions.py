"""Locust load test for TC-18 (NFR-PERF-03).

200 concurrent signed-in driver sessions loading search, occupancy, and booking history.
"""

import json
import os
import queue
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from locust import HttpUser, between, task

SESSIONS_FILE = os.environ.get(
    "VPS_LOAD_SESSIONS",
    "/tmp/claude-1000/-home-viviansobers-Documents-SEM-5-SE-Vehicle-Parking-System/9f662486-9041-4504-88bb-a3ed18ff8e55/scratchpad/sys2/load-sessions.json",
)

with open(SESSIONS_FILE) as f:
    _data = json.load(f)
    DRIVERS = _data.get("drivers", [])

# Thread-safe queue of driver sessions so each user gets a unique signed-in session
driver_queue = queue.Queue()
for d in DRIVERS:
    driver_queue.put(d)


class SessionDriverUser(HttpUser):
    wait_time = between(0.5, 1.5)

    def on_start(self):
        try:
            self.driver = driver_queue.get_nowait()
        except queue.Empty:
            # If spawned users exceed queue length, recycle from start
            self.driver = DRIVERS[0]

        self.client.cookies.set("sessionid", self.driver["sessionid"], domain="127.0.0.1", path="/")

        # Vehicle ID calculation from email load.driverXXX -> 120 + XXX
        match = re.search(r"load\.driver(\d+)", self.driver.get("email", ""))
        if match:
            driver_num = int(match.group(1))
            self.vehicle_id = str(120 + driver_num)
        else:
            self.vehicle_id = "121"

    @task(3)
    def search_availability(self):
        """TC-18: Driver searches slot availability."""
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        params = f"lot=1&vehicle={self.vehicle_id}&start={tomorrow}T10:00&end={tomorrow}T12:00"
        self.client.get(
            f"/reservations/search/?{params}",
            name="/reservations/search/",
        )

    @task(1)
    def load_occupancy(self):
        """TC-18: Driver views live occupancy page."""
        self.client.get(
            "/lots/occupancy/",
            name="/lots/occupancy/",
        )

    @task(1)
    def booking_history(self):
        """TC-18: Driver views booking history."""
        self.client.get(
            "/reservations/history/",
            name="/reservations/history/",
        )
