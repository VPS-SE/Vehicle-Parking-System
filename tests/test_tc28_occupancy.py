"""FR-SRCH-03 / TC-28: free, reserved, occupied and blocked counts per lot and slot type."""

from datetime import datetime, time, timedelta

import pytest
from django.db.backends.postgresql.psycopg_any import DateTimeTZRange
from django.utils import timezone

from vps.accounts.models import User
from vps.gate.services import check_in_vehicle
from vps.lots import services
from vps.lots.models import Lot, Slot, SlotBlock
from vps.reservations.models import Reservation

pytestmark = pytest.mark.django_db
NOON = timezone.make_aware(datetime(2026, 11, 4, 12))


@pytest.fixture
def lot():
    lot = Lot.objects.create(
        name="Lot A", address="Ring Road", opens_at=time(6), closes_at=time(23)
    )
    for code, slot_type in (
        ("S1", "Standard"),
        ("S2", "Standard"),
        ("S3", "Standard"),
        ("S4", "Standard"),
        ("S5", "Standard"),
        ("E1", "EV"),
        ("T1", "TwoWheeler"),
    ):
        Slot.objects.create(lot=lot, code=code, slot_type=slot_type, distance_rank=1)
    return lot


def reserve(lot, code, start, end, status="Reserved", ref=None):
    return Reservation.objects.create(
        booking_ref=ref or f"VPS-OCC-{code}",
        vehicle_reg_no=f"KA01AB00{code[-1]}{len(code)}",
        slot=lot.slots.get(code=code),
        period=DateTimeTZRange(start, end),
        status=status,
        entry_time=start if status == "Active" else None,
    )


def counts(lot, now=NOON):
    (row,) = [r for r in services.lot_occupancy(now=now) if r["lot"] == lot]
    return {
        t["slot_type"]: (t["free"], t["reserved"], t["occupied"], t["blocked"])
        for t in row["types"]
    }


def test_each_slot_is_counted_once_in_the_right_state(lot):
    reserve(lot, "S1", NOON - timedelta(hours=1), NOON + timedelta(hours=1))
    reserve(lot, "S2", NOON - timedelta(hours=2), NOON - timedelta(minutes=5), status="Active")
    SlotBlock.objects.create(
        slot=lot.slots.get(code="S3"),
        period=DateTimeTZRange(NOON - timedelta(hours=1), NOON + timedelta(hours=1)),
        reason="Paint",
    )
    # Blocked and occupied at once: the parked vehicle wins.
    reserve(lot, "S4", NOON - timedelta(hours=1), NOON + timedelta(hours=2), status="Active")
    SlotBlock.objects.create(
        slot=lot.slots.get(code="S4"),
        period=DateTimeTZRange(NOON + timedelta(hours=3), NOON + timedelta(hours=4)),
        reason="Later",
    )
    # Not counted now: a later booking, a finished one, a cancelled one, a past block.
    reserve(lot, "S5", NOON + timedelta(hours=2), NOON + timedelta(hours=3))
    reserve(lot, "E1", NOON - timedelta(hours=3), NOON - timedelta(hours=2), status="Completed")
    reserve(lot, "T1", NOON - timedelta(hours=1), NOON + timedelta(hours=1), status="Cancelled")

    assert counts(lot) == {
        "Standard": (1, 1, 2, 1),
        "EV": (1, 0, 0, 0),
        "TwoWheeler": (1, 0, 0, 0),
    }


def test_totals_and_archived_lots(lot):
    archived = Lot.objects.create(
        name="Old Lot", address="Elsewhere", opens_at=time(6), closes_at=time(23), is_archived=True
    )
    Slot.objects.create(lot=archived, code="X1", distance_rank=1)
    reserve(lot, "S1", NOON - timedelta(hours=1), NOON + timedelta(hours=1), status="Active")

    rows = services.lot_occupancy(now=NOON)

    assert [r["lot"] for r in rows] == [lot]
    assert rows[0]["total"] == {"free": 6, "reserved": 0, "occupied": 1, "blocked": 0, "slots": 7}


def test_tc28_check_in_changes_the_counts(lot):
    """Step 1: an attendant checks a vehicle in; reserved becomes occupied."""
    attendant = User.objects.create_user(email="gate@example.com", role=User.Role.ATTENDANT)
    booking = reserve(lot, "S1", NOON, NOON + timedelta(hours=2))
    assert counts(lot)["Standard"] == (4, 1, 0, 0)

    check_in_vehicle(booking.booking_ref, attendant, now=NOON)

    assert counts(lot)["Standard"] == (4, 0, 1, 0)


def test_page_is_public_and_refreshes_every_30_seconds(client, lot):
    reserve(lot, "S1", timezone.now() - timedelta(hours=1), timezone.now() + timedelta(hours=1))

    page = client.get("/lots/occupancy/")
    partial = client.get("/lots/occupancy/", headers={"HX-Request": "true"})

    html = page.content.decode()
    assert page.status_code == 200
    assert 'hx-get="/lots/occupancy/"' in html
    assert 'hx-trigger="every 30s"' in html
    assert "Lot A" in html
    assert partial.status_code == 200
    assert "<html" not in partial.content.decode()
    assert "Lot A" in partial.content.decode()
    assert partial.context["rows"][0]["total"]["reserved"] == 1


def test_occupancy_is_linked_for_everyone(client, lot):
    assert 'href="/lots/occupancy/"' in client.get("/accounts/login/").content.decode()
