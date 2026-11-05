from datetime import timedelta

from django import forms

from vps.lots.models import Lot

MAX_REPORT_DAYS = 31


class RevenueReportForm(forms.Form):
    """A date range of up to 31 days, both ends included (FR-RPT-02, FR-RPT-03)."""

    start_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    end_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        if start_date and end_date:
            if end_date < start_date:
                self.add_error("end_date", "End date must be on or after the start date.")
            elif end_date - start_date >= timedelta(days=MAX_REPORT_DAYS):
                self.add_error("end_date", "The selected date range cannot exceed 31 days.")
        return cleaned_data


class OccupancyReportForm(RevenueReportForm):
    lot = forms.ModelChoiceField(queryset=Lot.objects.order_by("name"))

    field_order = ("lot", "start_date", "end_date")


class AuditSearchForm(forms.Form):
    """FR-RPT-04: every field is optional; an empty form lists the newest entries."""

    actor = forms.CharField(required=False, max_length=254, label="Actor e-mail")
    action = forms.CharField(required=False, max_length=50)
    start_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    end_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def clean(self):
        cleaned_data = super().clean()
        start_date, end_date = cleaned_data.get("start_date"), cleaned_data.get("end_date")
        if start_date and end_date and end_date < start_date:
            self.add_error("end_date", "End date must be on or after the start date.")
        return cleaned_data
