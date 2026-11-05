from datetime import timedelta

from django import forms


class RevenueReportForm(forms.Form):
    start_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    end_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        if start_date and end_date:
            if end_date < start_date:
                self.add_error("end_date", "End date must be on or after the start date.")
            elif end_date - start_date >= timedelta(days=31):
                self.add_error("end_date", "The selected date range cannot exceed 31 days.")
        return cleaned_data
