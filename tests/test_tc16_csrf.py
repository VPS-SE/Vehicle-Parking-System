"""TC-16: State change without CSRF token is rejected.

Requirements: SEC-05
Preconditions: Signed in as Driver with a Reserved reservation.
Steps:
  1. Send POST /reservations/{id}/cancel/ without a CSRF token.
Expected result:
  HTTP 403; reservation still Reserved.
"""

from datetime import time, timedelta

import pytest
from django.db.backends.postgresql.psycopg_any import DateTimeTZRange
from django.test import Client
from django.utils import timezone

from vps.accounts.models import User
from vps.lots.models import Lot, Slot
from vps.reservations.models import Reservation
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
def reservation(driver):
    lot = Lot.objects.create(
        name="Lot A",
        address="1 Ring Road",
        opens_at=time(6),
        closes_at=time(23),
    )
    slot = Slot.objects.create(lot=lot, code="A-01", distance_rank=1)
    car = Vehicle.objects.create(owner=driver, registration_no="KA01AB1234", vehicle_type="Car")
    start = timezone.now() + timedelta(hours=2)
    end = start + timedelta(hours=2)
    return Reservation.objects.create(
        booking_ref="VPS-261104-0001",
        driver=driver,
        vehicle_reg_no=car.registration_no,
        slot=slot,
        period=DateTimeTZRange(start, end),
        status=Reservation.Status.RESERVED,
    )


def test_tc16_state_change_without_csrf_is_rejected(driver, reservation):
    """TC-16: cancelling a reservation without a CSRF token returns 403 and status stays Reserved."""
    # Use client with CSRF checks strictly enforced
    client = Client(enforce_csrf_checks=True)
    client.force_login(driver)

    # Send POST without CSRF token
    response = client.post(f"/reservations/{reservation.pk}/cancel/")

    # HTTP 403 Forbidden
    assert response.status_code == 403

    # Reservation remains Reserved
    reservation.refresh_from_db()
    assert reservation.status == Reservation.Status.RESERVED
