"""#19: test data factories and the 500-slot, 30-day demo data set (STP Section 5)."""

from datetime import timedelta
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.db.models import Count, Max, Min
from django.utils import timezone

from vps import factories
from vps.billing.models import Charge, Payment
from vps.billing.services import unpaid_total
from vps.lots.models import Lot, Slot, Tariff
from vps.reservations.models import Reservation

pytestmark = pytest.mark.django_db


def test_factories_build_valid_linked_records():
    driver = factories.make_driver()
    vehicle = factories.make_vehicle(driver, vehicle_type="EV")
    lot = factories.make_lot(slots={"Standard": 2, "EV": 1})
    tariff = factories.make_tariff(lot, "EV", "45.00")
    start = timezone.now() + timedelta(days=1)
    booking = factories.make_reservation(driver, lot.slots.get(slot_type="EV"), start, hours=2)
    charge = factories.make_charge(booking, "120.00")
    payment = factories.make_payment(charge)

    for record in (driver, vehicle, lot, tariff, booking, charge, payment):
        record.full_clean()
    assert booking.vehicle_reg_no == vehicle.registration_no
    assert booking.period.upper - booking.period.lower == timedelta(hours=2)
    assert sorted(lot.slots.values_list("code", flat=True)) == ["EV-001", "ST-001", "ST-002"]
    assert factories.make_driver().email != driver.email
    assert unpaid_total(driver) == Decimal("0.00")


def run_seed(*args):
    out = StringIO()
    call_command("seed_demo_data", *args, stdout=out)
    return out.getvalue()


def test_seed_builds_one_500_slot_lot_with_30_days_of_bookings():
    output = run_seed("--seed", "7")

    lot = Lot.objects.get(name=factories.DEMO_LOT_NAME)
    assert lot.slots.count() == 500
    assert set(lot.slots.values_list("slot_type", flat=True)) == set(Slot.SlotType.values)
    assert Tariff.objects.filter(lot=lot).count() == len(Slot.SlotType.values)
    bookings = Reservation.objects.filter(slot__lot=lot)
    days = {timezone.localtime(r.period.lower).date() for r in bookings}
    assert len(days) == 30
    span = bookings.aggregate(first=Min("period__startswith"), last=Max("period__startswith"))
    today = timezone.localdate()
    assert timezone.localtime(span["first"]).date() <= today - timedelta(days=19)
    assert timezone.localtime(span["last"]).date() >= today + timedelta(days=9)
    statuses = dict(bookings.values_list("status").annotate(n=Count("id")))
    assert set(statuses) >= {"Completed", "Expired", "Reserved", "Active"}
    for done in bookings.filter(status="Completed")[:50]:
        assert done.entry_time and done.exit_time and done.charges.filter(kind="Parking").exists()
    assert Payment.objects.filter(charge__reservation__slot__lot=lot).exists()
    assert Charge.objects.filter(reservation__slot__lot=lot, payment__isnull=True).exists()
    assert "seed=7" in output
    assert f"{bookings.count()} reservations" in output


def test_the_plan_is_repeatable_for_a_seed():
    today = timezone.localdate()
    assert factories.demo_plan(7, today) == factories.demo_plan(7, today)
    assert factories.demo_plan(7, today) != factories.demo_plan(8, today)


def test_seed_runs_once():
    run_seed("--seed", "7")
    count = Reservation.objects.count()

    output = run_seed("--seed", "7")

    assert "already exists" in output
    assert Reservation.objects.count() == count
