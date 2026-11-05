"""FR-RPT-02 / TC-34: hourly occupancy report for one lot, with CSV export (#58)."""

import csv
import itertools
from datetime import date, datetime, time, timedelta
from io import StringIO

import pytest
from django.db.backends.postgresql.psycopg_any import DateTimeTZRange
from django.utils import timezone

from vps.accounts.models import User
from vps.lots.models import Lot, Slot, SlotBlock
from vps.reports import services
from vps.reports.forms import OccupancyReportForm
from vps.reservations.models import Reservation

DAY = date(2026, 1, 10)


def at(hour, minute=0, day=DAY):
    return timezone.make_aware(datetime.combine(day, time(hour, minute)))


@pytest.fixture
def lot():
    lot = Lot.objects.create(name="Central", address="1 Road", opens_at=time(6), closes_at=time(23))
    for i in range(1, 5):
        Slot.objects.create(lot=lot, code=f"S{i}", slot_type="Standard", distance_rank=i)
    Slot.objects.create(lot=lot, code="E1", slot_type="EV", distance_rank=9)
    return lot


_refs = itertools.count(1)


def stay(lot, code, entry, exit_, status=Reservation.Status.COMPLETED):
    n = next(_refs)
    slot = lot.slots.get(code=code)
    end = exit_ or entry + timedelta(hours=1)
    return Reservation.objects.create(
        booking_ref=f"VPS-OCC-{n:04d}",
        vehicle_reg_no=f"KA01AA{n:04d}",
        slot=slot,
        period=DateTimeTZRange(entry, max(end, entry + timedelta(minutes=1))),
        status=status,
        entry_time=entry,
        exit_time=exit_,
    )


def row(rows, day, hour, slot_type="Standard"):
    return next(
        r for r in rows if r["date"] == day and r["hour"] == hour and r["slot_type"] == slot_type
    )


@pytest.mark.django_db
def test_hour_average_counts_slot_minutes(lot):
    # S1 occupied the whole 09:00 hour, S2 for half of it: 1.5 of 4 slots on average.
    stay(lot, "S1", at(8, 30), at(10, 15))
    stay(lot, "S2", at(9, 30), at(11))
    rows = services.occupancy_report(lot, DAY, DAY)
    nine = row(rows, DAY, 9)
    assert nine["total_slots"] == 4
    assert nine["average_occupied"] == pytest.approx(1.5)
    assert nine["occupancy_pct"] == pytest.approx(37.5)
    assert row(rows, DAY, 8)["average_occupied"] == pytest.approx(0.5)
    assert row(rows, DAY, 10)["average_occupied"] == pytest.approx(1.25)
    assert row(rows, DAY, 11)["average_occupied"] == 0


@pytest.mark.django_db
def test_blocked_slots_are_averaged_over_the_hour(lot):
    SlotBlock.objects.create(
        slot=lot.slots.get(code="S3"), period=DateTimeTZRange(at(14, 15), at(16)), reason="Repair"
    )
    rows = services.occupancy_report(lot, DAY, DAY)
    assert row(rows, DAY, 14)["average_blocked"] == pytest.approx(0.75)
    assert row(rows, DAY, 15)["average_blocked"] == pytest.approx(1)
    assert row(rows, DAY, 16)["average_blocked"] == 0


@pytest.mark.django_db
def test_every_hour_and_slot_type_is_listed(lot):
    rows = services.occupancy_report(lot, DAY, DAY + timedelta(days=1))
    assert len(rows) == 2 * 24 * 2
    assert {r["slot_type"] for r in rows} == {"Standard", "EV"}
    assert row(rows, DAY, 0, "EV")["total_slots"] == 1


@pytest.mark.django_db
def test_parked_vehicle_counts_until_now_and_other_states_do_not(lot):
    now = at(12, 30)
    stay(lot, "E1", at(12), None, status=Reservation.Status.ACTIVE)
    Reservation.objects.create(
        booking_ref="VPS-OCC-R",
        vehicle_reg_no="KA01ZZ0001",
        slot=lot.slots.get(code="S3"),
        period=DateTimeTZRange(at(12), at(14)),
        status=Reservation.Status.RESERVED,
    )
    rows = services.occupancy_report(lot, DAY, DAY, now=now)
    assert row(rows, DAY, 12, "EV")["average_occupied"] == pytest.approx(0.5)
    assert row(rows, DAY, 13, "EV")["average_occupied"] == 0
    assert row(rows, DAY, 12)["average_occupied"] == 0


@pytest.mark.django_db
def test_stay_across_midnight_is_split_between_days(lot):
    stay(lot, "S4", at(23, 30), at(0, 30, DAY + timedelta(days=1)))
    rows = services.occupancy_report(lot, DAY, DAY + timedelta(days=1))
    assert row(rows, DAY, 23)["average_occupied"] == pytest.approx(0.5)
    assert row(rows, DAY + timedelta(days=1), 0)["average_occupied"] == pytest.approx(0.5)


@pytest.mark.parametrize(
    "start,end,valid",
    [
        ("2026-01-01", "2026-01-31", True),
        ("2026-01-01", "2026-02-01", False),
        ("2026-01-05", "2026-01-04", False),
    ],
)
@pytest.mark.django_db
def test_form_limits_range_to_31_days(lot, start, end, valid):
    form = OccupancyReportForm({"lot": lot.pk, "start_date": start, "end_date": end})
    assert form.is_valid() is valid


@pytest.mark.django_db
def test_page_and_csv(client, lot):
    stay(lot, "S1", at(9), at(10))
    client.force_login(User.objects.create_user(email="a@example.com", role=User.Role.ADMIN))
    params = {"lot": lot.pk, "start_date": "2026-01-10", "end_date": "2026-01-10"}
    page = client.get("/reports/occupancy/", params)
    assert page.status_code == 200
    assert "25.0" in page.content.decode()
    response = client.get("/reports/occupancy.csv", params)
    assert response["Content-Type"] == "text/csv; charset=utf-8"
    assert (
        'filename="occupancy_central_2026-01-10_to_2026-01-10.csv"'
        in response["Content-Disposition"]
    )
    records = list(csv.reader(StringIO(response.content.decode())))
    assert records[0] == [
        "Lot",
        "Date",
        "Hour",
        "Slot type",
        "Total slots",
        "Average occupied slots",
        "Average occupancy (%)",
        "Average blocked slots",
    ]
    assert ["Central", "2026-01-10", "09", "Standard", "4", "1.00", "25.0", "0.00"] in records
    assert len(records) == 1 + 24 * 2
    assert (
        client.get("/reports/occupancy.csv", {**params, "end_date": "2026-02-20"}).status_code
        == 400
    )


@pytest.mark.parametrize("role", [User.Role.DRIVER, User.Role.ATTENDANT])
@pytest.mark.django_db
def test_report_is_admin_only(client, lot, role):
    client.force_login(User.objects.create_user(email="x@example.com", role=role))
    assert client.get("/reports/occupancy/").status_code == 403
    assert client.get("/reports/occupancy.csv").status_code == 403
