"""TC-17: SQL injection input is handled safely.

Requirements: SEC-06
Preconditions: Signed in as Driver.
Steps:
  1. Search with lot parameter "1 OR 1=1" and add a vehicle named "x'); DROP TABLE vehicle;--".
  2. (System level) Run an OWASP ZAP active scan on the search and vehicle endpoints.
Expected result:
  Search returns invalid input error for the invalid lot; the nickname is stored
  as plain text; no SQL error appears; vehicle table remains intact.
"""

from datetime import time

import pytest
from django.db import connection

from vps.accounts.models import User
from vps.lots.models import Lot
from vps.vehicles.models import Vehicle

pytestmark = pytest.mark.django_db


@pytest.fixture
def driver():
    return User.objects.create_user(
        email="driver@example.com",
        password="ValidPassword2026!",
        role=User.Role.DRIVER,
    )


@pytest.fixture
def lot():
    return Lot.objects.create(
        name="Main Lot",
        address="100 Brigade Road",
        opens_at=time(6),
        closes_at=time(23),
    )


def test_tc17_sql_injection_payloads_handled_safely(client, driver, lot):
    """TC-17 step 1: verifies parameterised ORM queries prevent SQL injection."""
    client.force_login(driver)

    # 1. Search with SQL injection payload in lot parameter
    injection_lot = "1 OR 1=1"
    response = client.get(
        "/reservations/search/",
        {
            "lot": injection_lot,
            "vehicle": "1",
            "start": "2026-11-05T10:00",
            "end": "2026-11-05T12:00",
        },
    )
    # The view handles the invalid lot safely without a 500 or SQL syntax error
    assert response.status_code == 200
    assert "search_error" in response.context
    assert response.context["search_error"] != ""
    assert response.context["slot_count"] is None

    # 2. Add vehicle with SQL injection payload in nickname
    injection_nickname = "x'); DROP TABLE vehicle;--"
    post_resp = client.post(
        "/vehicles/",
        {
            "registration_no": "KA01CD5678",
            "vehicle_type": "Car",
            "nickname": injection_nickname,
        },
        follow=True,
    )
    assert post_resp.status_code == 200

    # Verify nickname is stored verbatim as plain text
    vehicle = Vehicle.objects.get(registration_no="KA01CD5678")
    assert vehicle.nickname == injection_nickname

    # Verify the vehicle table was NOT dropped and remains completely healthy
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM vehicles_vehicle")
        count = cursor.fetchone()[0]
        assert count >= 1
