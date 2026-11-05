"""Reproduction tests for Code Review 2 findings (G1 - G3).

Each test is marked @pytest.mark.xfail(strict=True) to demonstrate the failure
on the current codebase.
"""

from datetime import time, timedelta

import pytest
from django.db.backends.postgresql.psycopg_any import DateTimeTZRange
from django.utils import timezone

from vps.accounts.models import User
from vps.gate import services as gate_services
from vps.lots.models import Lot, Slot, Tariff

pytestmark = pytest.mark.django_db


@pytest.fixture
def lot():
    lot = Lot.objects.create(
        name="Lot Review 2",
        address="100 Review Road",
        opens_at=time(6),
        closes_at=time(23),
    )
    for code, rank in (("R1", 1), ("R2", 2)):
        Slot.objects.create(lot=lot, code=code, distance_rank=rank)
    return lot


@pytest.fixture
def slot(lot):
    slot = lot.slots.first()
    Tariff.objects.create(
        lot=lot,
        slot_type="Standard",
        hourly_rate_inr="40.00",
        effective_from=timezone.localdate() - timedelta(days=5),
    )
    return slot


def test_g01_staff_can_search_parking_slots(client, lot):
    """G1: Attendants and Admins have Function.SEARCH but cannot search slots without owning vehicles."""
    attendant = User.objects.create_user(
        email="attendant_search@example.com",
        password="ValidPassword2026!",
        role=User.Role.ATTENDANT,
    )
    client.force_login(attendant)
    now = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
        days=1
    )
    start_str = (now + timedelta(hours=10)).strftime("%Y-%m-%dT%H:%M")
    end_str = (now + timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M")

    # Attendant accesses slot search (their default landing page)
    response = client.get(
        "/reservations/search/",
        {"lot": lot.pk, "start": start_str, "end": end_str},
    )
    assert response.status_code == 200
    assert response.context["search_error"] == ""
    assert response.context["slot_count"] is not None


def test_g02_admin_permitted_to_record_outage_exit_time(client, slot):
    """G2: Table 5 permits Admin to correct exit times, but checkout_vehicle requires GATE_OPERATIONS."""
    from vps.reservations.models import Reservation

    admin = User.objects.create_user(
        email="admin_exit@example.com",
        password="ValidPassword2026!",
        role=User.Role.ADMIN,
    )
    driver = User.objects.create_user(email="driver_exit@example.com")
    now = timezone.now()
    reservation = Reservation.objects.create(
        booking_ref="VPS-261105-0099",
        driver=driver,
        vehicle_reg_no="KA01CD5678",
        slot=slot,
        period=DateTimeTZRange(now - timedelta(hours=4), now + timedelta(hours=2)),
        status=Reservation.Status.ACTIVE,
        entry_time=now - timedelta(hours=4),
    )
    paper_exit = now - timedelta(hours=1)

    # 1. Admin must be permitted to record outage exit time via checkout_vehicle service
    updated = gate_services.checkout_vehicle(
        query=reservation.booking_ref,
        attendant=admin,
        now=now,
        exit_time=paper_exit,
        reason="Power outage during exit",
    )
    assert updated.exit_time == paper_exit
    assert updated.status == Reservation.Status.COMPLETED

    # 2. Admin must be permitted to access checkout page to submit outage exit times
    client.force_login(admin)
    view_resp = client.get("/gate/checkout/")
    assert view_resp.status_code == 200


def test_g03_staff_creation_renders_success_message(client):
    """G3: create_staff template fails to display success flash messages or site navigation."""
    admin = User.objects.create_user(
        email="admin_staff@example.com",
        password="ValidPassword2026!",
        role=User.Role.ADMIN,
    )
    client.force_login(admin)
    response = client.post(
        "/accounts/staff/create/",
        {
            "full_name": "New Attendant User",
            "email": "new_attendant@example.com",
            "mobile": "9876543299",
            "password": "ValidPassword2026!",
            "role": User.Role.ATTENDANT,
        },
        follow=True,
    )
    assert response.status_code == 200
    assert "Staff account created for new_attendant@example.com." in response.content.decode()
    assert '<nav class="site-nav"' in response.content.decode()
