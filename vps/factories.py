"""Test data factories and the demo data set (STP Section 5, issue #19).

The make_* functions build one valid record each with sensible defaults, so a test only
states what matters to it. demo_plan() and seed_demo() build the 500-slot lot with 30
days of bookings used for demos and manual system testing (`manage.py seed_demo_data`).
"""

import itertools
import random
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.backends.postgresql.psycopg_any import DateTimeTZRange
from django.utils import timezone

from vps.accounts.models import User
from vps.billing.models import Charge, Payment
from vps.lots.models import Lot, Slot, Tariff
from vps.reservations.models import Reservation
from vps.vehicles.models import Vehicle

_serial = itertools.count(1)

SLOT_PREFIX = {"Standard": "ST", "TwoWheeler": "TW", "EV": "EV", "Accessible": "AC"}
VEHICLE_FOR_SLOT = {"Standard": "Car", "TwoWheeler": "TwoWheeler", "EV": "EV", "Accessible": "Car"}


def make_driver(email=None, **fields):
    n = next(_serial)
    fields.setdefault("mobile", f"9{n:09d}")
    return User.objects.create_user(
        email=email or f"driver{n}@example.com", full_name=f"Driver {n}", **fields
    )


def make_staff(role=User.Role.ATTENDANT, email=None, **fields):
    n = next(_serial)
    fields.setdefault("mobile", f"8{n:09d}")
    return User.objects.create_user(email=email or f"staff{n}@example.com", role=role, **fields)


def make_vehicle(owner, vehicle_type="Car", registration_no=None):
    n = next(_serial)
    return Vehicle.objects.create(
        owner=owner,
        registration_no=registration_no or f"KA01AB{n:04d}",
        vehicle_type=vehicle_type,
    )


def make_lot(name=None, slots=None, opens_at=time(6), closes_at=time(23)):
    """A lot with slots given as {slot_type: count}, coded ST-001, EV-001 and so on."""
    n = next(_serial)
    lot = Lot.objects.create(
        name=name or f"Lot {n}", address=f"{n} Ring Road", opens_at=opens_at, closes_at=closes_at
    )
    Slot.objects.bulk_create(
        Slot(
            lot=lot, code=f"{SLOT_PREFIX[slot_type]}-{i:03d}", slot_type=slot_type, distance_rank=i
        )
        for slot_type, count in (slots or {"Standard": 1}).items()
        for i in range(1, count + 1)
    )
    return lot


def make_tariff(lot, slot_type="Standard", rate="40.00", effective_from=None):
    return Tariff.objects.create(
        lot=lot,
        slot_type=slot_type,
        hourly_rate_inr=Decimal(rate),
        effective_from=effective_from or timezone.localdate() - timedelta(days=365),
    )


def make_reservation(driver, slot, start, hours=2, status=Reservation.Status.RESERVED, **fields):
    """A booking for the driver's first active vehicle (one is created if they have none)."""
    vehicle = driver.vehicles.filter(is_active=True).first() if driver else None
    if driver and vehicle is None:
        vehicle = make_vehicle(driver, VEHICLE_FOR_SLOT[slot.slot_type])
    n = next(_serial)
    return Reservation.objects.create(
        booking_ref=fields.pop("booking_ref", f"VPS-F-{n:06d}"),
        driver=driver,
        vehicle_reg_no=fields.pop("vehicle_reg_no", vehicle.registration_no if vehicle else ""),
        slot=slot,
        period=DateTimeTZRange(start, start + timedelta(hours=hours)),
        status=status,
        **fields,
    )


def make_charge(reservation, amount="80.00", kind=Charge.Kind.PARKING):
    return Charge.objects.create(reservation=reservation, kind=kind, amount_inr=Decimal(amount))


def make_payment(charge, method=Payment.Method.UPI, recorded_by=None):
    return Payment.objects.create(
        charge=charge, method=method, recorded_by=recorded_by or make_staff()
    )


# ---------------------------------------------------------------------------
# Demo data set
# ---------------------------------------------------------------------------

DEMO_LOT_NAME = "Demo Central"
DEMO_SLOTS = {"Standard": 350, "TwoWheeler": 60, "EV": 60, "Accessible": 30}
DEMO_RATES = {"Standard": "40.00", "TwoWheeler": "15.00", "EV": "50.00", "Accessible": "30.00"}
DEMO_DRIVERS = 120
DEMO_DAYS_BEFORE, DEMO_DAYS_AFTER = 20, 9  # today included: 30 days in all


def demo_plan(seed, today):
    """The demo bookings as plain tuples, so a seed always gives the same data set.

    Each tuple is (day offset, slot index, start hour, hours, driver index, outcome). Every
    slot takes at most one booking a day, so bookings never overlap.
    """
    rng = random.Random(seed)
    slot_count = sum(DEMO_SLOTS.values())
    plan = []
    for offset in range(-DEMO_DAYS_BEFORE, DEMO_DAYS_AFTER + 1):
        weekend = (today + timedelta(days=offset)).weekday() >= 5
        for slot_index in rng.sample(range(slot_count), rng.randint(90, 140 if weekend else 220)):
            start_hour = rng.randint(7, 19)
            hours = rng.randint(1, min(4, 22 - start_hour))
            if offset < 0:
                outcome = rng.choices(["completed", "no_show", "cancelled"], [85, 8, 7])[0]
            elif offset == 0:
                outcome = "today"
            else:
                outcome = rng.choices(["reserved", "cancelled"], [93, 7])[0]
            plan.append(
                (offset, slot_index, start_hour, hours, rng.randrange(DEMO_DRIVERS), outcome)
            )
    return plan


@transaction.atomic
def seed_demo(seed=2026, now=None):
    """Create the demo lot, drivers and bookings; return a summary dict, or None if it exists."""
    if Lot.objects.filter(name=DEMO_LOT_NAME).exists():
        return None
    now = now or timezone.now()
    today = timezone.localdate(now)
    rng = random.Random(seed + 1)
    lot = make_lot(DEMO_LOT_NAME, DEMO_SLOTS)
    for slot_type, rate in DEMO_RATES.items():
        make_tariff(lot, slot_type, rate)
    slots = list(lot.slots.order_by("slot_type", "distance_rank"))
    attendant = make_staff(email="demo.gate@example.com")
    drivers = [
        User.objects.create_user(
            email=f"demo.driver{i:03d}@example.com", full_name=f"Demo Driver {i}"
        )
        for i in range(DEMO_DRIVERS)
    ]
    Vehicle.objects.bulk_create(
        Vehicle(owner=driver, registration_no=f"KA05DM{i:04d}", vehicle_type="Car")
        for i, driver in enumerate(drivers)
    )
    plates = {v.owner_id: v.registration_no for v in Vehicle.objects.filter(owner__in=drivers)}

    bookings, charges_for = [], []
    for n, (offset, slot_index, start_hour, hours, driver_index, outcome) in enumerate(
        demo_plan(seed, today), start=1
    ):
        slot, driver = slots[slot_index], drivers[driver_index]
        start = timezone.make_aware(
            datetime.combine(today + timedelta(days=offset), time(start_hour))
        )
        end = start + timedelta(hours=hours)
        status, entry, exit_ = Reservation.Status.RESERVED, None, None
        if outcome == "completed":
            status = Reservation.Status.COMPLETED
            entry = start + timedelta(minutes=rng.randint(-10, 10))
            exit_ = end + timedelta(minutes=rng.choice([-20, -5, 0, 5, 25, 70]))
        elif outcome == "no_show":
            status = Reservation.Status.EXPIRED
        elif outcome == "cancelled":
            status = Reservation.Status.CANCELLED
        elif outcome == "today" and rng.random() < 0.4:
            # Parked right now: entered 15-90 minutes ago, leaving later. The window stays
            # clear of the same slot's bookings on the days before and after.
            start = now - timedelta(minutes=rng.randint(15, 90))
            end = now + timedelta(minutes=rng.randint(30, 150))
            status, entry = Reservation.Status.ACTIVE, start
        elif outcome == "today" and start <= now:
            # Parked now, or already left earlier today.
            entry = start
            if end <= now:
                status, exit_ = Reservation.Status.COMPLETED, end
            else:
                status = Reservation.Status.ACTIVE
        elif outcome == "today" and now - start > timedelta(minutes=15):
            status = Reservation.Status.EXPIRED
        bookings.append(
            Reservation(
                booking_ref=f"VPS-D-{n:06d}",
                driver=driver,
                vehicle_reg_no=plates[driver.pk],
                slot=slot,
                period=DateTimeTZRange(start, end),
                status=status,
                entry_time=entry,
                exit_time=exit_,
            )
        )
        if status == Reservation.Status.COMPLETED:
            billed = max(1, -(-int((exit_ - entry).total_seconds()) // 1800) / 2)
            charges_for.append(
                (n, Charge.Kind.PARKING, Decimal(DEMO_RATES[slot.slot_type]) * Decimal(str(billed)))
            )
        elif status == Reservation.Status.EXPIRED:
            charges_for.append((n, Charge.Kind.NO_SHOW, Decimal("50.00")))

    Reservation.objects.bulk_create(bookings, batch_size=1000)
    by_ref = dict(Reservation.objects.filter(slot__lot=lot).values_list("booking_ref", "pk"))
    charges = Charge.objects.bulk_create(
        Charge(
            reservation_id=by_ref[f"VPS-D-{n:06d}"],
            kind=kind,
            amount_inr=amount.quantize(Decimal("0.01")),
        )
        for n, kind, amount in charges_for
    )
    # Most charges are settled; the rest show up as unpaid balances.
    Payment.objects.bulk_create(
        Payment(charge=charge, method=rng.choice(Payment.Method.values), recorded_by=attendant)
        for charge in charges
        if rng.random() < 0.85
    )
    return {
        "seed": seed,
        "slots": len(slots),
        "drivers": len(drivers),
        "reservations": len(bookings),
        "charges": len(charges),
        "days": DEMO_DAYS_BEFORE + DEMO_DAYS_AFTER + 1,
    }
