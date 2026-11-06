"""Tests for TC-45 through TC-49 covering business rules BR-02, BR-03, BR-05, BR-06, BR-07.

Test case mapping:
- TC-45: BR-02 (Gate Attendant role enforcement for gate operations and payments)
- TC-46: BR-03 (Max 2 open reservations per driver, reservation limits and cancellation release)
- TC-47: BR-05 (Cancellation fees at 60min / 59min boundaries and no-show fee)
- TC-48: BR-06 (No-show 15-minute grace period boundary and expiry)
- TC-49: BR-07 (Billing in 30-min blocks, 1-hr minimum, 10-min overstay grace, 1.5x rate)
"""

from datetime import datetime, time, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db.backends.postgresql.psycopg_any import DateTimeTZRange
from django.urls import reverse
from django.utils import timezone

from vps.accounts.models import User
from vps.billing.models import Charge, Payment
from vps.factories import (
    make_driver,
    make_lot,
    make_reservation,
    make_staff,
    make_tariff,
    make_vehicle,
)
from vps.gate import services as gate_services
from vps.reservations import services as res_services
from vps.reservations.models import Reservation

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# TC-45: BR-02 Gate Operations Role Enforcement
# ---------------------------------------------------------------------------


def test_tc45_br02_only_gate_attendants_perform_gate_operations(client):
    """TC-45 (BR-02): Only Gate Attendants check vehicles in/out, register walk-ins, and record payments.

    Admins and Drivers get HTTP 403 on each page and POST; Attendants succeed.
    """
    now = timezone.now()
    today_start = now.replace(hour=10, minute=0, second=0, microsecond=0)
    if today_start < now:
        today_start = now + timedelta(minutes=5)

    lot = make_lot(name="TC45 Lot", opens_at=time(0), closes_at=time(23, 59))
    slot = lot.slots.first()
    make_tariff(lot=lot, rate="50.00")

    driver = make_driver(email="tc45_driver@example.com")
    admin = make_staff(role=User.Role.ADMIN, email="tc45_admin@example.com")
    attendant = make_staff(role=User.Role.ATTENDANT, email="tc45_attendant@example.com")

    make_vehicle(owner=driver, registration_no="KA01TC4501")

    # 1. Verification of HTTP 403 for Driver and Admin on gate pages & actions
    forbidden_users = [driver, admin]

    # Dummy charge for payment testing
    res_dummy = make_reservation(
        driver=driver,
        slot=slot,
        start=today_start + timedelta(days=2),
        hours=2,
    )
    charge_dummy = Charge.objects.create(
        reservation=res_dummy,
        kind=Charge.Kind.PARKING,
        amount_inr=Decimal("100.00"),
    )

    for user in forbidden_users:
        client.force_login(user)

        # Gate dashboard
        assert client.get(reverse("gate:dashboard")).status_code == 403

        # Check-in POST
        assert client.post(reverse("gate:checkin"), {"reference": "ANYREF"}).status_code == 403

        # Checkout POST
        assert (
            client.post(reverse("gate:dashboard_checkout"), {"reference": "ANYREF"}).status_code
            == 403
        )

        # Walk-in GET and POST
        assert client.get(reverse("gate:walk_in")).status_code == 403
        assert (
            client.post(
                reverse("gate:dashboard_walk_in"), {"registration_no": "KA01TC4599"}
            ).status_code
            == 403
        )
        assert (
            client.post(reverse("gate:walk_in"), {"registration_no": "KA01TC4599"}).status_code
            == 403
        )

        # Payments GET and POST
        assert client.get(reverse("gate:payments")).status_code == 403
        assert (
            client.post(
                reverse("gate:pay_charge", args=[charge_dummy.pk]),
                {"method": Payment.Method.CASH},
            ).status_code
            == 403
        )

        # Service-level checks
        with pytest.raises(ValidationError):
            gate_services.check_in_vehicle("ANYREF", attendant=user)
        with pytest.raises(ValidationError):
            gate_services.checkout_vehicle("ANYREF", attendant=user, exit_time=None)
        with pytest.raises(ValidationError):
            gate_services.register_walk_in(
                attendant=user, lot=lot, registration_no="KA01TC4599", vehicle_type="Car"
            )
        with pytest.raises(ValidationError):
            from vps.billing.services import record_payment

            record_payment(attendant=user, charge=charge_dummy, method=Payment.Method.CASH)

    # 2. Attendant succeeds on all of these
    client.force_login(attendant)

    # Gate dashboard GET succeeds
    resp_dash = client.get(reverse("gate:dashboard"))
    assert resp_dash.status_code == 200

    # Walk-in GET and POST succeed
    resp_walk_get = client.get(reverse("gate:walk_in"))
    assert resp_walk_get.status_code == 200

    resp_walk_post = client.post(
        reverse("gate:dashboard_walk_in"),
        {"lot": lot.pk, "registration_no": "KA01TC4502", "vehicle_type": "Car"},
    )
    assert resp_walk_post.status_code == 200
    walkin_res = Reservation.objects.get(vehicle_reg_no="KA01TC4502")
    assert walkin_res.status == Reservation.Status.ACTIVE

    # Check-in of a reserved booking succeeds
    res_to_checkin = make_reservation(
        driver=driver,
        slot=lot.slots.create(code="ST-099", slot_type="Standard", distance_rank=99),
        start=now,
        hours=2,
    )
    resp_checkin = client.post(
        reverse("gate:checkin"),
        {"reference": res_to_checkin.booking_ref},
    )
    assert resp_checkin.status_code == 200
    res_to_checkin.refresh_from_db()
    assert res_to_checkin.status == Reservation.Status.ACTIVE

    # Check-out of the checked-in booking succeeds
    resp_checkout = client.post(
        reverse("gate:dashboard_checkout"),
        {"reference": res_to_checkin.booking_ref},
    )
    assert resp_checkout.status_code == 302
    assert f"/gate/receipt/{res_to_checkin.booking_ref}/" in resp_checkout.url
    res_to_checkin.refresh_from_db()
    assert res_to_checkin.status == Reservation.Status.COMPLETED

    # Payments GET and POST succeed
    resp_payments = client.get(reverse("gate:payments") + f"?q={res_to_checkin.booking_ref}")
    assert resp_payments.status_code == 200

    unpaid_charge = res_to_checkin.charges.first()
    assert unpaid_charge is not None
    resp_pay = client.post(
        reverse("gate:pay_charge", args=[unpaid_charge.pk]),
        {"method": Payment.Method.CASH, "q": res_to_checkin.booking_ref},
    )
    assert resp_pay.status_code == 302
    assert Payment.objects.filter(charge=unpaid_charge).exists()


# ---------------------------------------------------------------------------
# TC-46: BR-03 Reservation Limit (Max 2 Open Reservations)
# ---------------------------------------------------------------------------


def test_tc46_br03_driver_reservation_limit_and_cancellation_release():
    """TC-46 (BR-03): A Driver with 2 Reserved bookings is refused a third; after cancelling one, booking works again."""
    driver = make_driver(email="tc46_driver@example.com")
    car = make_vehicle(owner=driver, registration_no="KA01TC4601")
    lot = make_lot(slots={"Standard": 5}, opens_at=time(6), closes_at=time(23))
    make_tariff(lot=lot)

    base_time = timezone.localtime().replace(
        hour=10, minute=0, second=0, microsecond=0
    ) + timedelta(days=2)

    # 1. Driver creates first reservation -> succeeds
    r1 = res_services.reserve(driver, car, lot, base_time, base_time + timedelta(hours=2))
    assert r1.status == Reservation.Status.RESERVED

    # 2. Driver creates second reservation -> succeeds
    r2 = res_services.reserve(
        driver, car, lot, base_time + timedelta(hours=3), base_time + timedelta(hours=5)
    )
    assert r2.status == Reservation.Status.RESERVED

    # 3. Driver attempts third reservation -> refused due to 2 open reservations limit
    with pytest.raises(ValidationError) as exc:
        res_services.reserve(
            driver, car, lot, base_time + timedelta(hours=6), base_time + timedelta(hours=8)
        )
    assert exc.value.message_dict == {"__all__": [res_services.LIMIT_REACHED]}

    # 4. Driver cancels one of the reservations
    res_services.cancel_reservation(driver=driver, reservation_id=r1.pk)
    r1.refresh_from_db()
    assert r1.status == Reservation.Status.CANCELLED

    # 5. Driver creates reservation again -> succeeds now that open count is 1
    r3 = res_services.reserve(
        driver, car, lot, base_time + timedelta(hours=6), base_time + timedelta(hours=8)
    )
    assert r3.status == Reservation.Status.RESERVED
    assert (
        Reservation.objects.filter(driver=driver, status=Reservation.Status.RESERVED).count() == 2
    )


# ---------------------------------------------------------------------------
# TC-47: BR-05 Cancellation Fees and No-Show Charge
# ---------------------------------------------------------------------------


def test_tc47_br05_cancellation_fees_and_no_show_charge():
    """TC-47 (BR-05): Cancelling 60 minutes or more before the start is free;

    59 minutes before costs Rs 30; a no-show costs Rs 50.
    """
    driver = make_driver(email="tc47_driver@example.com")
    lot = make_lot(slots={"Standard": 4}, opens_at=time(6), closes_at=time(23))
    make_tariff(lot=lot)

    ref_start = timezone.make_aware(datetime(2026, 11, 10, 12, 0))

    # Case 1: Cancel 90 minutes before start -> Free
    r_90m = make_reservation(driver, lot.slots.all()[0], start=ref_start, hours=2)
    res_services.cancel_reservation(
        driver=driver,
        reservation_id=r_90m.pk,
        now=ref_start - timedelta(minutes=90),
    )
    r_90m.refresh_from_db()
    assert r_90m.status == Reservation.Status.CANCELLED
    assert not Charge.objects.filter(reservation=r_90m).exists()

    # Case 2: Cancel exactly 60 minutes before start (boundary) -> Free
    r_60m = make_reservation(driver, lot.slots.all()[1], start=ref_start, hours=2)
    res_services.cancel_reservation(
        driver=driver,
        reservation_id=r_60m.pk,
        now=ref_start - timedelta(minutes=60),
    )
    r_60m.refresh_from_db()
    assert r_60m.status == Reservation.Status.CANCELLED
    assert not Charge.objects.filter(reservation=r_60m).exists()

    # Case 3: Cancel 59 minutes before start (boundary) -> Rs 30 fee
    r_59m = make_reservation(driver, lot.slots.all()[2], start=ref_start, hours=2)
    res_services.cancel_reservation(
        driver=driver,
        reservation_id=r_59m.pk,
        now=ref_start - timedelta(minutes=59),
    )
    r_59m.refresh_from_db()
    assert r_59m.status == Reservation.Status.CANCELLED
    charge_59m = Charge.objects.get(reservation=r_59m)
    assert charge_59m.kind == Charge.Kind.LATE_CANCEL
    assert charge_59m.amount_inr == Decimal("30.00")

    # Case 4: No-show expiry -> Rs 50 fee
    r_noshow = make_reservation(driver, lot.slots.all()[3], start=ref_start, hours=2)
    expired_count = res_services.expire_no_shows(now=ref_start + timedelta(minutes=16))
    assert expired_count >= 1
    r_noshow.refresh_from_db()
    assert r_noshow.status == Reservation.Status.EXPIRED
    charge_noshow = Charge.objects.get(reservation=r_noshow)
    assert charge_noshow.kind == Charge.Kind.NO_SHOW
    assert charge_noshow.amount_inr == Decimal("50.00")


# ---------------------------------------------------------------------------
# TC-48: BR-06 Reservation Expiry Window Boundary
# ---------------------------------------------------------------------------


def test_tc48_br06_booking_held_15_minutes_and_expires_after():
    """TC-48 (BR-06): A booking is still Reserved 15 minutes after its start and expires after that."""
    driver = make_driver(email="tc48_driver@example.com")
    lot = make_lot(slots={"Standard": 1}, opens_at=time(6), closes_at=time(23))
    make_tariff(lot=lot)
    slot = lot.slots.first()

    start_time = timezone.make_aware(datetime(2026, 11, 10, 14, 0))
    reservation = make_reservation(driver, slot, start=start_time, hours=2)

    # 1. 14 minutes after start -> Still Reserved
    assert res_services.expire_no_shows(now=start_time + timedelta(minutes=14)) == 0
    reservation.refresh_from_db()
    assert reservation.status == Reservation.Status.RESERVED
    assert not Charge.objects.filter(reservation=reservation).exists()

    # 2. Exactly 15 minutes after start (boundary) -> Still Reserved
    assert res_services.expire_no_shows(now=start_time + timedelta(minutes=15)) == 0
    reservation.refresh_from_db()
    assert reservation.status == Reservation.Status.RESERVED
    assert not Charge.objects.filter(reservation=reservation).exists()

    # 3. 15 minutes and 1 second / 16 minutes after start -> Expires
    assert res_services.expire_no_shows(now=start_time + timedelta(minutes=15, seconds=1)) == 1
    reservation.refresh_from_db()
    assert reservation.status == Reservation.Status.EXPIRED
    assert Charge.objects.filter(reservation=reservation, kind=Charge.Kind.NO_SHOW).exists()


# ---------------------------------------------------------------------------
# TC-49: BR-07 Billing Blocks, 1-Hour Minimum, 10-Minute Grace & Overstay
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "stay_minutes,expected_parking_charge",
    [
        (0, "40.00"),  # 0 min -> 1 hour min
        (20, "40.00"),  # 20 min -> 1 hour min
        (30, "40.00"),  # 30 min -> 1 hour min
        (60, "40.00"),  # 60 min -> exactly 1 hour
        (61, "60.00"),  # 61 min -> 1.5 hours
        (90, "60.00"),  # 90 min -> 1.5 hours
        (91, "80.00"),  # 91 min -> 2.0 hours
        (120, "80.00"),  # 120 min -> 2.0 hours
    ],
)
def test_tc49_br07_parking_duration_rounding_and_minimum(stay_minutes, expected_parking_charge):
    """TC-49 (BR-07): Billing in 30-minute blocks with a 1-hour minimum."""
    attendant = make_staff(role=User.Role.ATTENDANT, email="tc49_gate@example.com")
    lot = make_lot(slots={"Standard": 1}, opens_at=time(6), closes_at=time(23))
    make_tariff(lot=lot, rate="40.00")
    slot = lot.slots.first()

    entry = timezone.make_aware(datetime(2026, 11, 10, 10, 0))
    # 4-hour reservation window so normal parking covers up to 2 hours without overstay
    booking = Reservation.objects.create(
        booking_ref=f"VPS-TC49-{stay_minutes:04d}",
        vehicle_reg_no="KA01TC4901",
        slot=slot,
        period=DateTimeTZRange(entry, entry + timedelta(hours=4)),
        status=Reservation.Status.ACTIVE,
        entry_time=entry,
    )

    exit_time = entry + timedelta(minutes=stay_minutes)
    gate_services.checkout_vehicle(booking.booking_ref, attendant=attendant, now=exit_time)
    booking.refresh_from_db()

    assert booking.status == Reservation.Status.COMPLETED
    charge = booking.charges.get(kind=Charge.Kind.PARKING)
    assert charge.amount_inr == Decimal(expected_parking_charge)
    assert not booking.charges.filter(kind=Charge.Kind.OVERSTAY).exists()


@pytest.mark.parametrize(
    "exit_minutes_after_entry,expected_overstay",
    [
        (120, None),  # At reserved end (120 min) -> No overstay
        (129, None),  # 9 min past reserved end (within 10 min grace) -> No overstay
        (130, None),  # Exactly 10 min past reserved end (grace boundary) -> No overstay
        (131, "30.00"),  # 11 min past reserved end (1 min past grace -> 0.5h * 1.5 * 40 = 30.00)
        (140, "30.00"),  # 20 min past reserved end (10 min past grace -> 0.5h)
        (160, "30.00"),  # 40 min past reserved end (30 min past grace -> 0.5h)
        (161, "60.00"),  # 41 min past reserved end (31 min past grace -> 1.0h * 1.5 * 40 = 60.00)
        (190, "60.00"),  # 70 min past reserved end (60 min past grace -> 1.0h)
        (191, "90.00"),  # 71 min past reserved end (61 min past grace -> 1.5h * 1.5 * 40 = 90.00)
    ],
)
def test_tc49_br07_overstay_grace_period_and_multiplier_boundaries(
    exit_minutes_after_entry, expected_overstay
):
    """TC-49 (BR-07): No overstay charge up to 10 minutes after reserved end;

    after that, overstay is billed at 1.5 times the hourly rate in 30-minute blocks.
    """
    attendant = make_staff(role=User.Role.ATTENDANT, email="tc49_gate2@example.com")
    lot = make_lot(slots={"Standard": 1}, opens_at=time(6), closes_at=time(23))
    make_tariff(lot=lot, rate="40.00")
    slot = lot.slots.first()

    entry = timezone.make_aware(datetime(2026, 11, 10, 10, 0))
    # 2-hour reservation window: reserved end is entry + 120 minutes
    booking = Reservation.objects.create(
        booking_ref=f"VPS-OVR-{exit_minutes_after_entry:04d}",
        vehicle_reg_no="KA01TC4902",
        slot=slot,
        period=DateTimeTZRange(entry, entry + timedelta(hours=2)),
        status=Reservation.Status.ACTIVE,
        entry_time=entry,
    )

    exit_time = entry + timedelta(minutes=exit_minutes_after_entry)
    gate_services.checkout_vehicle(booking.booking_ref, attendant=attendant, now=exit_time)
    booking.refresh_from_db()

    assert booking.status == Reservation.Status.COMPLETED
    # 2-hour reserved parking fee is 2h * 40 = 80.00
    parking_charge = booking.charges.get(kind=Charge.Kind.PARKING)
    assert parking_charge.amount_inr == Decimal("80.00")

    overstay_charges = booking.charges.filter(kind=Charge.Kind.OVERSTAY)
    if expected_overstay is None:
        assert not overstay_charges.exists()
    else:
        assert overstay_charges.count() == 1
        assert overstay_charges.first().amount_inr == Decimal(expected_overstay)
