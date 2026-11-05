import csv
from datetime import timedelta

from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from vps.accounts.permissions import function_required
from vps.accounts.roles import Function
from vps.reports import services
from vps.reports.forms import RevenueReportForm


def _csv_response(start_date, end_date, rows):
    filename = f"revenue_{start_date:%Y-%m-%d}_to_{end_date:%Y-%m-%d}.csv"
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(
        ["Lot", "Address", "Slot type", "Payment method", "Payment count", "Revenue (INR)"]
    )
    writer.writerows(
        [
            row["lot_name"],
            row["lot_address"],
            row["slot_type_label"],
            row["payment_method_label"],
            row["payment_count"],
            f'{row["revenue_inr"]:.2f}',
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
        rows = services.revenue_totals(
            form.cleaned_data["start_date"], form.cleaned_data["end_date"]
        )
    return render(request, "reports/revenue.html", {"form": form, "rows": rows})


@function_required(Function.REPORTS)
@require_GET
def revenue_csv(request):
    form = RevenueReportForm(request.GET)
    if not form.is_valid():
        errors = "; ".join(
            error for field_errors in form.errors.values() for error in field_errors
        )
        return HttpResponseBadRequest(errors)
    start_date = form.cleaned_data["start_date"]
    end_date = form.cleaned_data["end_date"]
    return _csv_response(
        start_date, end_date, services.revenue_totals(start_date, end_date)
    )
