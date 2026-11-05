"""FR-LOT-04 / TC-26: blocking a slot moves its Reserved bookings, or cancels them free."""

from datetime import time, timedelta

import pytest
from django.db.backends.postgresql.psycopg_any import DateTimeTZRange
from django.utils import timezone

from vps.accounts.models import User
from vps.audit.models import AuditLog
from vps.lots import services
from vps.lots.models import Lot, Slot
from vps.notifications.models import ReservationNotification
from vps.reservations.models import Reservation
from vps.vehicles.models import Vehicle

pytestmark = pytest.mark.django_db
DAY = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)


def at(hour):
    return DAY.replace(hour=hour)


@pytest.fixture
def admin():
    return User.objects.create_user(email="admin@example.com", role=User.Role.ADMIN)


@pytest.fixture
def lot():
    lot = Lot.objects.create(
        name="Lot A", address="Ring Road", opens_at=time(6), closes_at=time(23)
    )
    for code, rank in (("S1", 1), ("S4", 4), ("S5", 5)):
        Slot.objects.create(lot=lot, code=code, distance_rank=rank)
    return lot


def booking(
    lot, code, start, end, ref="VPS-261103-0001", vehicle_type="Car", email="d@example.com"
):
    driver = User.objects.create_user(email=email, full_name="Asha Rao")
    reg = f"KA01AB{ref[-4:]}"
    Vehicle.objects.create(owner=driver, registration_no=reg, vehicle_type=vehicle_type)
    return Reservation.objects.create(
        booking_ref=ref,
        driver=driver,
        vehicle_reg_no=reg,
        slot=lot.slots.get(code=code),
        period=DateTimeTZRange(start, end),
    )


def block(lot, code, start, end, admin):
    return services.block_slot(
        slot=lot.slots.get(code=code),
        starts_at=start,
        ends_at=end,
        reason="Resurfacing",
        actor=admin,
    )


def test_tc26_booking_moves_then_is_cancelled_free(lot, admin):
    r = booking(lot, "S1", at(14), at(16))
    # S5 is taken for the window by another booking.
    Reservation.objects.create(
        booking_ref="VPS-261103-0002",
        vehicle_reg_no="KA02CD0002",
        slot=lot.slots.get(code="S5"),
        period=DateTimeTZRange(at(13), at(17)),
    )

    first = block(lot, "S1", at(13), at(17), admin)

    r.refresh_from_db()
    assert r.slot.code == "S4"
    assert r.status == Reservation.Status.RESERVED
    assert [m.booking_ref for m in first.moved] == [r.booking_ref]
    moved = ReservationNotification.objects.get(event="moved")
    assert "S4" in moved.message
    assert moved.recipient_email == "d@example.com"

    second = block(lot, "S4", at(13), at(17), admin)

    r.refresh_from_db()
    assert r.status == Reservation.Status.CANCELLED
    assert not r.charges.exists()
    assert [c.booking_ref for c in second.cancelled] == [r.booking_ref]
    assert ReservationNotification.objects.filter(event="cancelled", reservation=r).exists()
    actions = list(
        AuditLog.objects.filter(action__startswith="reservation.")
        .order_by("id")
        .values_list("action", "after")
    )
    assert actions[0] == ("reservation.moved_by_block", {"from_slot": "S1", "to_slot": "S4"})
    assert actions[1][0] == "reservation.cancelled_by_block"
    assert actions[1][1]["fee_inr"] == "0.00"


def test_only_overlapping_reserved_bookings_are_touched(lot, admin):
    later = booking(lot, "S1", at(18), at(19))
    parked = Reservation.objects.create(
        booking_ref="VPS-261103-0003",
        vehicle_reg_no="KA03EF0003",
        slot=lot.slots.get(code="S1"),
        period=DateTimeTZRange(at(12), at(15)),
        status=Reservation.Status.ACTIVE,
        entry_time=at(12),
    )

    result = block(lot, "S1", at(13), at(17), admin)

    later.refresh_from_db()
    parked.refresh_from_db()
    assert later.slot.code == "S1"
    assert parked.slot.code == "S1"
    assert result.moved == [] and result.cancelled == []
    assert not ReservationNotification.objects.exists()


def test_moves_follow_eligibility_and_preference(lot, admin):
    Slot.objects.create(lot=lot, code="E1", slot_type="EV", distance_rank=9)
    Slot.objects.create(lot=lot, code="T1", slot_type="TwoWheeler", distance_rank=1)
    ev = booking(lot, "S1", at(10), at(11), vehicle_type="EV")

    block(lot, "S1", at(9), at(12), admin)

    ev.refresh_from_db()
    assert ev.slot.code == "E1"


def test_two_bookings_on_the_blocked_slot_get_different_slots(lot, admin):
    one = booking(lot, "S1", at(10), at(11))
    two = booking(lot, "S1", at(12), at(13), ref="VPS-261103-0004", email="e@example.com")

    block(lot, "S1", at(9), at(14), admin)

    one.refresh_from_db()
    two.refresh_from_db()
    assert (one.slot.code, two.slot.code) == ("S4", "S4")
    assert one.status == two.status == Reservation.Status.RESERVED


def test_block_page_reports_moves_and_cancellations(client, lot, admin):
    booking(lot, "S1", at(14), at(16))
    client.force_login(admin)
    url = f"/lots/{lot.pk}/block/"

    page = client.get(url)
    response = client.post(
        url,
        {
            "slot": lot.slots.get(code="S1").pk,
            "starts_at": at(13).strftime("%Y-%m-%dT%H:%M"),
            "ends_at": at(17).strftime("%Y-%m-%dT%H:%M"),
            "reason": "Resurfacing",
        },
        follow=True,
    )

    assert page.status_code == 200
    html = response.content.decode()
    assert "Slot S1 blocked" in html
    assert "VPS-261103-0001 moved to S4" in html


def test_block_page_shows_errors_and_is_admin_only(client, lot, admin):
    client.force_login(admin)
    url = f"/lots/{lot.pk}/block/"
    response = client.post(
        url,
        {
            "slot": lot.slots.get(code="S1").pk,
            "starts_at": at(13).strftime("%Y-%m-%dT%H:%M"),
            "ends_at": at(12).strftime("%Y-%m-%dT%H:%M"),
            "reason": "x",
        },
    )
    assert "End time must be later than start time." in response.content.decode()

    client.force_login(User.objects.create_user(email="g@example.com", role=User.Role.ATTENDANT))
    assert client.get(url).status_code == 403
