"""Locust load test for TC-36 (NFR-PERF-02).

50 concurrent users creating reservations, checking in and checking out at the gate.
Measures reserve, check-in, and check-out response times separately.
"""

import itertools
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
    ATTENDANTS = _data.get("attendants", [])

driver_queue = queue.Queue()
for d in DRIVERS:
    driver_queue.put(d)

attendant_cycle = itertools.cycle(ATTENDANTS)


class BookingUser(HttpUser):
    wait_time = between(1.0, 2.5)

    def on_start(self):
        try:
            self.driver = driver_queue.get_nowait()
        except queue.Empty:
            self.driver = DRIVERS[0]

        self.attendant = next(attendant_cycle)

        # Calculate vehicle_id
        match = re.search(r"load\.driver(\d+)", self.driver.get("email", ""))
        if match:
            driver_num = int(match.group(1))
            self.vehicle_id = str(120 + driver_num)
        else:
            self.vehicle_id = "121"

        # Prime cookies and CSRF token
        self.client.cookies.set("sessionid", self.driver["sessionid"], domain="127.0.0.1", path="/")
        resp = self.client.get("/reservations/search/", name="/reservations/search/")
        self.csrf = resp.cookies.get("csrftoken") or self.client.cookies.get("csrftoken", "")

    @task
    def lifecycle_booking(self):
        """TC-36: Reserve -> Check-in -> Check-out -> Record Payment."""
        now = datetime.now(ZoneInfo("Asia/Kolkata"))

        # Schedule booking to start in 2 minutes so check-in is valid immediately
        start = now + timedelta(minutes=2)
        end = start + timedelta(minutes=30)

        # Lot Demo Central hours: 06:00 to 23:00
        if start.hour < 6:
            start = now.replace(hour=7, minute=0, second=0, microsecond=0)
            end = start + timedelta(minutes=30)
        elif start.hour >= 22 and start.minute > 25:
            start = (now + timedelta(days=1)).replace(hour=7, minute=0, second=0, microsecond=0)
            end = start + timedelta(minutes=30)

        start_str = start.strftime("%Y-%m-%dT%H:%M")
        end_str = end.strftime("%Y-%m-%dT%H:%M")

        csrf = self.client.cookies.get("csrftoken", self.csrf)

        # 1. Driver reserves a slot
        self.client.cookies.set("sessionid", self.driver["sessionid"], domain="127.0.0.1", path="/")
        booking_ref = None
        with self.client.post(
            "/reservations/confirm/",
            data={
                "csrfmiddlewaretoken": csrf,
                "lot": "1",
                "vehicle": self.vehicle_id,
                "start": start_str,
                "end": end_str,
            },
            headers={"Referer": f"{self.host}/reservations/search/"},
            name="reserve",
            allow_redirects=False,
            catch_response=True,
        ) as reserve_resp:
            match = re.search(
                r"confirmation/(VPS-[^/]+)/", reserve_resp.headers.get("Location", "")
            )
            if reserve_resp.status_code == 302 and match:
                booking_ref = match.group(1)
                reserve_resp.success()
            else:
                reserve_resp.failure(f"no booking: HTTP {reserve_resp.status_code}")

        if not booking_ref:
            return

        # 2. Attendant checks in the vehicle
        self.client.cookies.set(
            "sessionid", self.attendant["sessionid"], domain="127.0.0.1", path="/"
        )
        csrf = self.client.cookies.get("csrftoken", self.csrf)
        with self.client.post(
            "/gate/check-in/",
            data={"csrfmiddlewaretoken": csrf, "reference": booking_ref},
            headers={"Referer": f"{self.host}/gate/"},
            name="check-in",
            allow_redirects=False,
            catch_response=True,
        ) as checkin_resp:
            if checkin_resp.status_code == 200 and "Checked in" in checkin_resp.text:
                checkin_resp.success()
            else:
                checkin_resp.failure(f"not checked in: HTTP {checkin_resp.status_code}")
                return

        # 3. Attendant checks out the vehicle
        with self.client.post(
            "/gate/dashboard-checkout/",
            data={"csrfmiddlewaretoken": csrf, "reference": booking_ref},
            headers={"Referer": f"{self.host}/gate/"},
            name="check-out",
            allow_redirects=False,
            catch_response=True,
        ) as checkout_resp:
            if checkout_resp.status_code == 302 and "/gate/receipt/" in checkout_resp.headers.get(
                "Location", ""
            ):
                checkout_resp.success()
            else:
                checkout_resp.failure(f"not checked out: HTTP {checkout_resp.status_code}")
                return

        # 4. Attendant records payment so driver balance is cleared (BR-04)
        pay_search = self.client.get(
            f"/gate/payments/?q={booking_ref}",
            name="/gate/payments/",
        )
        match = re.search(r"/gate/payments/(\d+)/", pay_search.text)
        if match:
            charge_id = match.group(1)
            self.client.post(
                f"/gate/payments/{charge_id}/",
                data={
                    "csrfmiddlewaretoken": csrf,
                    "method": "Cash",
                    "q": booking_ref,
                },
                headers={"Referer": f"{self.host}/gate/payments/"},
                name="payment",
                allow_redirects=False,
            )
