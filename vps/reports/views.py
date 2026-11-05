import csv
from datetime import timedelta

from django.core.paginator import Paginator
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_GET

from vps.accounts.permissions import function_required
from vps.accounts.roles import Function
from vps.reports import services
from vps.reports.forms import AuditSearchForm, OccupancyReportForm, RevenueReportForm

REVENUE_COLUMNS = [
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


def _csv_response(start_date, end_date, rows):
    filename = f"revenue_{start_date:%Y-%m-%d}_to_{end_date:%Y-%m-%d}.csv"
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(REVENUE_COLUMNS)
    writer.writerows(
        [
            row["lot_name"],
            f"{row['date']:%Y-%m-%d}",
            row["slot_type_label"],
            row["completed_stays"],
            *(f"{row[column]:.2f}" for column in services.REVENUE_AMOUNTS),
        ]
        for row in rows
    )
    return response


@function_required(Function.REPORTS)
@require_GET
def revenue(request):
    today = timezone.localdate()
    initial = {"start_date": today - timedelta(days=30), "end_date": today}
    form = RevenueReportForm(request.GET or None, initial=initial)
    rows = None
    if form.is_bound and form.is_valid():
        rows = services.revenue_report(
            form.cleaned_data["start_date"], form.cleaned_data["end_date"]
        )
    return render(request, "reports/revenue.html", {"form": form, "rows": rows})


@function_required(Function.REPORTS)
@require_GET
def revenue_csv(request):
    form = RevenueReportForm(request.GET)
    if not form.is_valid():
        errors = "; ".join(error for field_errors in form.errors.values() for error in field_errors)
        return HttpResponseBadRequest(errors)
    start_date = form.cleaned_data["start_date"]
    end_date = form.cleaned_data["end_date"]
    return _csv_response(start_date, end_date, services.revenue_report(start_date, end_date))


OCCUPANCY_COLUMNS = [
    "Lot",
    "Date",
    "Hour",
    "Slot type",
    "Total slots",
    "Average occupied slots",
    "Average occupancy (%)",
    "Average blocked slots",
]


def _occupancy_rows(form):
    data = form.cleaned_data
    return services.occupancy_report(data["lot"], data["start_date"], data["end_date"])


@function_required(Function.REPORTS)
@require_GET
def occupancy(request):
    """FR-RPT-02: average occupancy of one lot for each hour of a date range."""
    today = timezone.localdate()
    initial = {"start_date": today - timedelta(days=6), "end_date": today}
    form = OccupancyReportForm(request.GET or None, initial=initial)
    rows = _occupancy_rows(form) if form.is_bound and form.is_valid() else None
    return render(request, "reports/occupancy.html", {"form": form, "rows": rows})


@function_required(Function.REPORTS)
@require_GET
def occupancy_csv(request):
    form = OccupancyReportForm(request.GET)
    if not form.is_valid():
        errors = "; ".join(error for field in form.errors.values() for error in field)
        return HttpResponseBadRequest(errors)
    data = form.cleaned_data
    filename = (
        f"occupancy_{slugify(data['lot'].name)}_"
        f"{data['start_date']:%Y-%m-%d}_to_{data['end_date']:%Y-%m-%d}.csv"
    )
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(OCCUPANCY_COLUMNS)
    writer.writerows(
        [
            row["lot_name"],
            f"{row['date']:%Y-%m-%d}",
            f"{row['hour']:02d}",
            row["slot_type_label"],
            row["total_slots"],
            f"{row['average_occupied']:.2f}",
            f"{row['occupancy_pct']:.1f}",
            f"{row['average_blocked']:.2f}",
        ]
        for row in _occupancy_rows(form)
    )
    return response


@function_required(Function.REPORTS)
@require_GET
def audit_log(request):
    """FR-RPT-04: search the audit log by actor, action and date range (read-only)."""
    form = AuditSearchForm(request.GET or None)
    entries = None
    if not form.is_bound:
        entries = services.search_audit()
    elif form.is_valid():
        entries = services.search_audit(**form.cleaned_data)
    page = Paginator(entries, 50).get_page(request.GET.get("page")) if entries is not None else None
    query = request.GET.copy()
    query.pop("page", None)
    return render(
        request,
        "reports/audit.html",
        {
            "form": form,
            "page": page,
            "query": query.urlencode(),
            "actions": services.audit_actions(),
        },
    )
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(OCCUPANCY_COLUMNS)
    writer.writerows(
        [
            row["lot_name"],
            f"{row['date']:%Y-%m-%d}",
            f"{row['hour']:02d}",
            row["slot_type_label"],
            row["total_slots"],
            f"{row['average_occupied']:.2f}",
            f"{row['occupancy_pct']:.1f}",
            f"{row['average_blocked']:.2f}",
        ]
        for row in _occupancy_rows(form)
    )
    return response
