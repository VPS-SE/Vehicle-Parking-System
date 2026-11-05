"""FR-RPT-03 / TC-34: revenue report per lot, date and slot type (SRS Table 4)."""

import csv
import itertools
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from io import StringIO

import pytest
from django.db.backends.postgresql.psycopg_any import DateTimeTZRange
from django.utils import timezone

from vps.accounts.models import User
from vps.billing.models import Charge, Payment
from vps.lots.models import Lot, Slot
from vps.reports import services
from vps.reports.forms import RevenueReportForm
from vps.reservations.models import Reservation

START = date(2026, 1, 1)
END = date(2026, 1, 31)
_refs = itertools.count(1)


def at(day, hour, minute=0):
    return timezone.make_aware(datetime.combine(date(2026, 1, day), time(hour, minute)))


@pytest.fixture
def lots():
    central = Lot.objects.create(
        name="Central Lot", address="1 Main Road", opens_at=time(6), closes_at=time(23)
    )
    west = Lot.objects.create(
        name="West Lot", address="2 Main Road", opens_at=time(6), closes_at=time(23)
    )
    return {
        "standard": Slot.objects.create(lot=central, code="S1", distance_rank=1),
        "ev": Slot.objects.create(lot=central, code="E1", slot_type="EV", distance_rank=2),
        "west": Slot.objects.create(lot=west, code="S1", distance_rank=1),
    }


@pytest.fixture
def attendant():
    return User.objects.create_user(email="gate@example.com", role=User.Role.ATTENDANT)


def booking(slot, start, exit_time=None, status=Reservation.Status.COMPLETED):
    n = next(_refs)
    return Reservation.objects.create(
        booking_ref=f"VPS-RPT-{n:04d}",
        vehicle_reg_no=f"KA01AB{n:04d}",
        slot=slot,
        period=DateTimeTZRange(start, start + timedelta(hours=1)),
        status=status,
        entry_time=start if exit_time else None,
        exit_time=exit_time,
    )


def charge(reservation, amount, kind=Charge.Kind.PARKING, paid=None, attendant=None):
    c = Charge.objects.create(reservation=reservation, kind=kind, amount_inr=Decimal(amount))
    if paid:
        method, paid_at = paid
        p = Payment.objects.create(charge=c, method=method, recorded_by=attendant)
        Payment.objects.filter(pk=p.pk).update(paid_at=paid_at)
    return c


@pytest.fixture
def report_data(lots, attendant):
    s = lots["standard"]
    stay = booking(s, at(10, 8), exit_time=at(10, 10))
    charge(stay, "80.00", paid=(Payment.Method.CASH, at(10, 10)), attendant=attendant)
    charge(
        stay,
        "30.00",
        Charge.Kind.OVERSTAY,
        paid=(Payment.Method.UPI, at(10, 10)),
        attendant=attendant,
    )
    stay2 = booking(s, at(10, 12), exit_time=at(10, 13))
    charge(stay2, "40.00")  # unpaid
    noshow = booking(s, at(10, 15), status=Reservation.Status.EXPIRED)
    charge(
        noshow,
        "50.00",
        Charge.Kind.NO_SHOW,
        paid=(Payment.Method.CARD, at(12, 9)),
        attendant=attendant,
    )
    ev = booking(lots["ev"], at(10, 9), exit_time=at(10, 11))
    charge(ev, "100.00", paid=(Payment.Method.CASH, at(10, 11)), attendant=attendant)
    old = booking(
        lots["west"], at(1, 9) - timedelta(days=1), exit_time=at(1, 9) - timedelta(hours=23)
    )
    charge(
        old, "999.00", paid=(Payment.Method.CASH, at(1, 9) - timedelta(days=1)), attendant=attendant
    )
    return lots


def find(rows, lot, day, slot_type="Standard"):
    return next(
        r
        for r in rows
        if r["lot_name"] == lot
        and r["date"] == date(2026, 1, day)
        and r["slot_type_label"] == slot_type
    )


@pytest.mark.django_db
def test_charges_payments_and_unpaid_per_lot_date_and_slot_type(report_data):
    rows = services.revenue_report(START, END)
    day = find(rows, "Central Lot", 10)
    assert day["completed_stays"] == 2
    assert day["parking_inr"] == Decimal("120.00")
    assert day["overstay_inr"] == Decimal("30.00")
    assert day["late_noshow_inr"] == Decimal("50.00")
    assert (day["cash_inr"], day["upi_inr"], day["card_inr"]) == (
        Decimal("80.00"),
        Decimal("30.00"),
        Decimal("0.00"),
    )
    assert day["unpaid_inr"] == Decimal("40.00")
    # The no-show fee was paid two days later: the payment is counted on the 12th.
    assert find(rows, "Central Lot", 12)["card_inr"] == Decimal("50.00")
    assert find(rows, "Central Lot", 10, "Electric vehicle")["cash_inr"] == Decimal("100.00")
    assert all(r["lot_name"] != "West Lot" for r in rows)


@pytest.mark.django_db
def test_revenue_page_and_csv(client, report_data):
    client.force_login(User.objects.create_user(email="admin@example.com", role=User.Role.ADMIN))
    params = {"start_date": START.isoformat(), "end_date": END.isoformat()}
    page = client.get("/reports/revenue/", params)
    assert page.status_code == 200
    html = page.content.decode()
    assert "Central Lot" in html and "120.00" in html
    assert "/reports/revenue.csv?start_date=2026-01-01&amp;end_date=2026-01-31" in html

    response = client.get("/reports/revenue.csv", params)
    assert response["Content-Type"] == "text/csv; charset=utf-8"
    assert response["Content-Disposition"] == (
        'attachment; filename="revenue_2026-01-01_to_2026-01-31.csv"'
    )
    records = list(csv.reader(StringIO(response.content.decode())))
    assert records[0] == [
        "Lot",
        "Date",
        "Slot type",
        "Completed stays",
        "Parking charges (Rs)",
        "Overstay charges (Rs)",
        "Late-cancellation and no-show charges (Rs)",
        "Cash payments (Rs)",
        "UPI payments (Rs)",
        "Card payments (Rs)",
        "Unpaid total (Rs)",
    ]
    assert [
        "Central Lot",
        "2026-01-10",
        "Standard",
        "2",
        "120.00",
        "30.00",
        "50.00",
        "80.00",
        "30.00",
        "0.00",
        "40.00",
    ] in records
    assert len(records) == 4


@pytest.mark.parametrize(
    "start_date,end_date,valid",
    [
        ("2026-01-01", "2026-01-31", True),
        ("2026-01-01", "2026-02-01", False),
        ("2026-01-02", "2026-01-01", False),
    ],
)
def test_revenue_report_date_range_validation(start_date, end_date, valid):
    form = RevenueReportForm({"start_date": start_date, "end_date": end_date})
    assert form.is_valid() is valid


@pytest.mark.parametrize("role", [User.Role.DRIVER, User.Role.ATTENDANT])
@pytest.mark.django_db
def test_revenue_report_is_admin_only(client, role):
    client.force_login(User.objects.create_user(email="staff@example.com", role=role))
    params = {"start_date": START.isoformat(), "end_date": END.isoformat()}
    assert client.get("/reports/revenue/").status_code == 403
    assert client.get("/reports/revenue.csv", params).status_code == 403
