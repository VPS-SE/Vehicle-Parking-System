import csv
from datetime import date, datetime, time
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


@pytest.fixture
def report_data():
    lot = Lot.objects.create(
        name="Central Lot", address="1 Main Road", opens_at=time(6), closes_at=time(23)
    )
    other_lot = Lot.objects.create(
        name="West Lot", address="2 Main Road", opens_at=time(6), closes_at=time(23)
    )
    standard = Slot.objects.create(lot=lot, code="S1", slot_type=Slot.SlotType.STANDARD, distance_rank=1)
    ev = Slot.objects.create(lot=lot, code="E1", slot_type=Slot.SlotType.EV, distance_rank=2)
    other_standard = Slot.objects.create(
        lot=other_lot, code="S1", slot_type=Slot.SlotType.STANDARD, distance_rank=1
    )
    attendant = User.objects.create_user(email="report.attendant@example.com", role=User.Role.ATTENDANT)

    def add_charge(index, slot, amount):
        reservation = Reservation.objects.create(
            booking_ref=f"VPS-RPT-{index:04d}",
            vehicle_reg_no=f"KA01AB{index:04d}",
            slot=slot,
            period=DateTimeTZRange(
                timezone.make_aware(datetime(2026, 1, 10, 8)),
                timezone.make_aware(datetime(2026, 1, 10, 9)),
            ),
            status=Reservation.Status.COMPLETED,
        )
        charge = Charge.objects.create(
            reservation=reservation, kind=Charge.Kind.PARKING, amount_inr=Decimal(amount)
        )
        return charge

    def add_payment(index, slot, amount, method, paid_at):
        charge = add_charge(index, slot, amount)
        payment = Payment.objects.create(charge=charge, method=method, recorded_by=attendant)
        Payment.objects.filter(pk=payment.pk).update(paid_at=paid_at)
        return charge

    in_range = timezone.make_aware(datetime(2026, 1, 15, 12))
    last_day = timezone.make_aware(datetime(2026, 1, 31, 23, 59))
    add_payment(1, standard, "12.50", Payment.Method.CASH, in_range)
    add_payment(2, standard, "7.50", Payment.Method.CASH, in_range)
    add_payment(3, standard, "20.00", Payment.Method.UPI, in_range)
    add_payment(4, ev, "30.00", Payment.Method.CASH, in_range)
    add_payment(5, other_standard, "40.00", Payment.Method.CASH, in_range)
    add_payment(8, standard, "10.00", Payment.Method.CASH, last_day)
    add_payment(
        6,
        standard,
        "100.00",
        Payment.Method.CARD,
        timezone.make_aware(datetime(2025, 12, 31, 23, 59)),
    )
    add_charge(7, standard, "500.00")
    return lot


def admin_user():
    return User.objects.create_user(email="lot.admin@example.com", role=User.Role.ADMIN)


@pytest.mark.django_db
def test_revenue_totals_group_each_dimension_and_exclude_outside_dates_and_unpaid(report_data):
    rows = services.revenue_totals(START, END)

    assert len(rows) == 4
    standard_cash = next(
        row
        for row in rows
        if row["lot_name"] == "Central Lot"
        and row["slot_type"] == Slot.SlotType.STANDARD
        and row["payment_method"] == Payment.Method.CASH
    )
    assert standard_cash["payment_count"] == 3
    assert standard_cash["revenue_inr"] == Decimal("30.00")
    assert standard_cash["slot_type_label"] == "Standard"
    assert standard_cash["payment_method_label"] == "Cash"
    assert all(row["revenue_inr"] != Decimal("100.00") for row in rows)


@pytest.mark.django_db
def test_revenue_page_shows_aggregated_report_and_csv_action(client, report_data):
    client.force_login(admin_user())
    response = client.get(
        "/reports/revenue/", {"start_date": START.isoformat(), "end_date": END.isoformat()}
    )

    assert response.status_code == 200
    html = response.content.decode()
    assert "Central Lot" in html
    assert "Electric vehicle" in html
    assert "30.00" in html
    assert "/reports/revenue.csv?start_date=2026-01-01&amp;end_date=2026-01-31" in html


@pytest.mark.django_db
def test_revenue_csv_exports_selected_grouped_totals(client, report_data):
    client.force_login(admin_user())
    response = client.get(
        "/reports/revenue.csv", {"start_date": START.isoformat(), "end_date": END.isoformat()}
    )

    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv; charset=utf-8"
    assert response["Content-Disposition"] == (
        'attachment; filename="revenue_2026-01-01_to_2026-01-31.csv"'
    )
    records = list(csv.reader(StringIO(response.content.decode())))
    assert records[0] == [
        "Lot",
        "Address",
        "Slot type",
        "Payment method",
        "Payment count",
        "Revenue (INR)",
    ]
    assert ["Central Lot", "1 Main Road", "Standard", "Cash", "3", "30.00"] in records
    assert len(records) == 5


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


@pytest.mark.parametrize("role,status", [(User.Role.DRIVER, 403), (User.Role.ATTENDANT, 403)])
@pytest.mark.django_db
def test_revenue_report_is_admin_only(client, role, status):
    client.force_login(User.objects.create_user(email="staff@example.com", role=role))

    assert client.get("/reports/revenue/").status_code == status
    assert client.get(
        "/reports/revenue.csv", {"start_date": START.isoformat(), "end_date": END.isoformat()}
    ).status_code == status
