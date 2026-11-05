"""Tests for Finding F6: unpaid_total safety for None, AnonymousUser and edge cases."""

from datetime import time, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import AnonymousUser
from django.db.backends.postgresql.psycopg_any import DateTimeTZRange
from django.utils import timezone

from vps.accounts.models import User
from vps.billing.models import Charge, Payment
from vps.billing.services import unpaid_total
from vps.lots.models import Lot, Slot
from vps.reservations.models import Reservation

pytestmark = pytest.mark.django_db


@pytest.fixture
def slot():
    lot = Lot.objects.create(
        name="Lot F6", address="Main Street", opens_at=time(6), closes_at=time(23)
    )
    return Slot.objects.create(lot=lot, code="F6-01", slot_type="Standard", distance_rank=1)


@pytest.fixture
def walk_in_with_debt(slot):
    now = timezone.now()
    walk_in = Reservation.objects.create(
        booking_ref="VPS-261105-0001",
        driver=None,
        vehicle_reg_no="KA01WI1111",
        slot=slot,
        period=DateTimeTZRange(now - timedelta(hours=3), now - timedelta(hours=1)),
        status=Reservation.Status.COMPLETED,
        is_walk_in=True,
        entry_time=now - timedelta(hours=3),
        exit_time=now - timedelta(hours=1),
    )
    charge = Charge.objects.create(
        reservation=walk_in,
        kind=Charge.Kind.PARKING,
        amount_inr=Decimal("120.00"),
    )
    return walk_in, charge


def test_unpaid_total_none_returns_zero_with_walk_in_debt(walk_in_with_debt):
    """None driver must return Decimal('0.00') even when walk-in debts exist."""
    assert unpaid_total(None) == Decimal("0.00")


def test_unpaid_total_anonymous_user_returns_zero_with_walk_in_debt(walk_in_with_debt):
    """AnonymousUser must return Decimal('0.00') even when walk-in debts exist."""
    anon = AnonymousUser()
    assert unpaid_total(anon) == Decimal("0.00")


def test_unpaid_total_unsaved_user_returns_zero_with_walk_in_debt(walk_in_with_debt):
    """Unsaved User instance without a pk must return Decimal('0.00')."""
    unsaved = User(email="unsaved@example.com")
    assert unpaid_total(unsaved) == Decimal("0.00")


def test_real_driver_gets_only_their_own_unpaid_total(slot, walk_in_with_debt):
    """A real driver gets only their own unpaid charges, excluding walk-ins, others, and paid."""
    now = timezone.now()
    driver_a = User.objects.create_user(email="driver_a@example.com")
    driver_b = User.objects.create_user(email="driver_b@example.com")

    # Driver A reservation 1: unpaid parking charge
    res_a1 = Reservation.objects.create(
        booking_ref="VPS-261105-0002",
        driver=driver_a,
        vehicle_reg_no="KA01AA1111",
        slot=slot,
        period=DateTimeTZRange(now - timedelta(hours=2), now),
        status=Reservation.Status.COMPLETED,
    )
    Charge.objects.create(
        reservation=res_a1,
        kind=Charge.Kind.PARKING,
        amount_inr=Decimal("75.00"),
    )

    # Driver A reservation 2: unpaid no-show charge
    res_a2 = Reservation.objects.create(
        booking_ref="VPS-261105-0003",
        driver=driver_a,
        vehicle_reg_no="KA01AA1111",
        slot=slot,
        period=DateTimeTZRange(now + timedelta(hours=1), now + timedelta(hours=2)),
        status=Reservation.Status.CANCELLED,
    )
    Charge.objects.create(
        reservation=res_a2,
        kind=Charge.Kind.NO_SHOW,
        amount_inr=Decimal("50.00"),
    )

    # Driver A reservation 3: paid charge (should not be included in unpaid_total)
    res_a3 = Reservation.objects.create(
        booking_ref="VPS-261105-0004",
        driver=driver_a,
        vehicle_reg_no="KA01AA1111",
        slot=slot,
        period=DateTimeTZRange(now - timedelta(days=1, hours=2), now - timedelta(days=1)),
        status=Reservation.Status.COMPLETED,
    )
    paid_charge = Charge.objects.create(
        reservation=res_a3,
        kind=Charge.Kind.PARKING,
        amount_inr=Decimal("60.00"),
    )
    Payment.objects.create(
        charge=paid_charge,
        method=Payment.Method.CARD,
        recorded_by=driver_a,
    )

    # Driver B reservation: unpaid charge (should not be included in driver A's total)
    res_b = Reservation.objects.create(
        booking_ref="VPS-261105-0005",
        driver=driver_b,
        vehicle_reg_no="KA02BB2222",
        slot=slot,
        period=DateTimeTZRange(now - timedelta(hours=1), now),
        status=Reservation.Status.COMPLETED,
    )
    Charge.objects.create(
        reservation=res_b,
        kind=Charge.Kind.PARKING,
        amount_inr=Decimal("200.00"),
    )

    # Driver A should have 75.00 + 50.00 = 125.00
    assert unpaid_total(driver_a) == Decimal("125.00")
    # Driver B should have 200.00
    assert unpaid_total(driver_b) == Decimal("200.00")


def test_driver_with_no_unpaid_charges_returns_zero(slot, walk_in_with_debt):
    """A real driver with no charges gets 0.00 even when walk-ins have debts."""
    clean_driver = User.objects.create_user(email="clean@example.com")
    assert unpaid_total(clean_driver) == Decimal("0.00")


def test_driver_home_page_shows_correct_total_with_walk_in_debt(client, slot, walk_in_with_debt):
    """The driver's home page displays their own unpaid charges and does not leak walk-in debts."""
    now = timezone.now()
    driver = User.objects.create_user(email="driver_home@example.com")

    # Driver has an unpaid charge of 45.50
    res = Reservation.objects.create(
        booking_ref="VPS-261105-0006",
        driver=driver,
        vehicle_reg_no="KA01DH6666",
        slot=slot,
        period=DateTimeTZRange(now - timedelta(hours=1), now),
        status=Reservation.Status.COMPLETED,
    )
    Charge.objects.create(
        reservation=res,
        kind=Charge.Kind.PARKING,
        amount_inr=Decimal("45.50"),
    )

    client.force_login(driver)
    response = client.get("/vehicles/")

    assert response.status_code == 200
    assert response.context["unpaid_total"] == Decimal("45.50")
    assert "₹45.50" in response.content.decode()


def test_driver_home_page_shows_zero_when_driver_has_no_debt_despite_walk_in(
    client, slot, walk_in_with_debt
):
    """A driver with zero balance sees ₹0.00 and no outstanding charges message."""
    driver = User.objects.create_user(email="nodebt@example.com")
    client.force_login(driver)
    response = client.get("/vehicles/")

    assert response.status_code == 200
    assert response.context["unpaid_total"] == Decimal("0.00")
    html = response.content.decode()
    assert "₹0.00" in html
    assert "No outstanding charges" in html
