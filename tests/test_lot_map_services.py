from datetime import timedelta

import pytest
from django.db.backends.postgresql.psycopg_any import DateTimeTZRange
from django.utils import timezone

from vps import factories
from vps.lots.models import SlotBlock
from vps.lots.services import find_parked_vehicle, lot_map_state
from vps.reservations.models import Reservation

pytestmark = pytest.mark.django_db


def test_states_match_occupancy_rules():
    now = timezone.now()
    lot = factories.make_lot(slots={"Standard": 5})
    occupied = lot.slots.get(code="ST-001")
    blocked = lot.slots.get(code="ST-002")
    reserved = lot.slots.get(code="ST-003")
    free = lot.slots.get(code="ST-004")
    blocked_and_active = lot.slots.get(code="ST-005")

    driver = factories.make_driver()
    factories.make_reservation(
        driver,
        occupied,
        now - timedelta(hours=1),
        hours=2,
        status=Reservation.Status.ACTIVE,
    )
    SlotBlock.objects.create(
        slot=blocked,
        period=DateTimeTZRange(now - timedelta(minutes=30), now + timedelta(minutes=30)),
        reason="Repair",
    )
    factories.make_reservation(
        driver,
        reserved,
        now - timedelta(minutes=30),
        hours=2,
        status=Reservation.Status.RESERVED,
    )
    SlotBlock.objects.create(
        slot=blocked_and_active,
        period=DateTimeTZRange(now - timedelta(minutes=30), now + timedelta(minutes=30)),
        reason="Repair",
    )
    factories.make_reservation(
        driver,
        blocked_and_active,
        now - timedelta(minutes=15),
        hours=1,
        status=Reservation.Status.ACTIVE,
    )

    states = lot_map_state(lot, now=now)
    assert states[occupied.pk].state == "occupied"
    assert states[blocked.pk].state == "blocked"
    assert states[reserved.pk].state == "reserved"
    assert states[free.pk].state == "free"
    assert states[blocked_and_active.pk].state == "occupied"


def test_state_carries_reservation():
    now = timezone.now()
    lot = factories.make_lot(slots={"Standard": 4})
    driver = factories.make_driver()
    occupied = factories.make_reservation(
        driver,
        lot.slots.get(code="ST-001"),
        now - timedelta(hours=1),
        hours=2,
        status=Reservation.Status.ACTIVE,
    )
    reserved = factories.make_reservation(
        driver,
        lot.slots.get(code="ST-002"),
        now - timedelta(minutes=30),
        hours=2,
        status=Reservation.Status.RESERVED,
    )
    SlotBlock.objects.create(
        slot=lot.slots.get(code="ST-003"),
        period=DateTimeTZRange(now - timedelta(minutes=30), now + timedelta(minutes=30)),
        reason="Repair",
    )

    states = lot_map_state(lot, now=now)
    assert states[occupied.slot_id].reservation == occupied
    assert states[reserved.slot_id].reservation == reserved
    assert states[lot.slots.get(code="ST-003").pk].reservation is None
    assert states[lot.slots.get(code="ST-004").pk].reservation is None


def test_query_count(django_assert_max_num_queries):
    now = timezone.now()
    lot = factories.make_lot(slots={"Standard": 10})
    with django_assert_max_num_queries(3):
        states = lot_map_state(lot, now=now)
    assert len(states) == 10


def test_find_parked_vehicle_normalises():
    now = timezone.now()
    lot = factories.make_lot(slots={"Standard": 1})
    driver = factories.make_driver()
    active = factories.make_reservation(
        driver,
        lot.slots.get(code="ST-001"),
        now - timedelta(minutes=30),
        hours=2,
        status=Reservation.Status.ACTIVE,
        vehicle_reg_no="KA05DM0001",
    )
    assert find_parked_vehicle("ka 05 dm-0001") == active


def test_find_ignores_completed_and_reserved():
    now = timezone.now()
    lot = factories.make_lot(slots={"Standard": 2})
    driver = factories.make_driver()
    factories.make_reservation(
        driver,
        lot.slots.get(code="ST-001"),
        now - timedelta(hours=3),
        hours=1,
        status=Reservation.Status.COMPLETED,
        vehicle_reg_no="KA05DM0001",
        entry_time=now - timedelta(hours=3),
        exit_time=now - timedelta(hours=2),
    )
    reserved = factories.make_reservation(
        driver,
        lot.slots.get(code="ST-002"),
        now - timedelta(minutes=20),
        hours=2,
        status=Reservation.Status.RESERVED,
        vehicle_reg_no="KA05DM0001",
    )

    assert find_parked_vehicle("KA05DM0001") is None

    reserved.status = Reservation.Status.ACTIVE
    reserved.entry_time = now - timedelta(minutes=10)
    reserved.save(update_fields=["status", "entry_time"])
    assert find_parked_vehicle("KA05DM0001") == reserved


def test_find_blank_and_unknown():
    now = timezone.now()
    lot = factories.make_lot(slots={"Standard": 1})
    driver = factories.make_driver()
    factories.make_reservation(
        driver,
        lot.slots.get(code="ST-001"),
        now - timedelta(minutes=20),
        hours=1,
        status=Reservation.Status.ACTIVE,
        vehicle_reg_no="KA05DM0001",
    )
    assert find_parked_vehicle("") is None
    assert find_parked_vehicle("ZZ99ZZ9999") is None
