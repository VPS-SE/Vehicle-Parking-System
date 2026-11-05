from types import SimpleNamespace

from django import forms

from vps.accounts.roles import Function, can
from vps.lots.models import Lot
from vps.vehicles.models import Vehicle

DATETIME_LOCAL = "%Y-%m-%dT%H:%M"


class ReservationSearchForm(forms.Form):
    """Lot, vehicle and window; used both to search (GET) and to book (POST).

    Drivers choose one of their own vehicles. Staff have no vehicles (FR-SRCH-01 lets them
    search too), so they choose a vehicle type instead, or leave it empty to count every slot.
    """

    lot = forms.ModelChoiceField(queryset=Lot.objects.none())
    vehicle = forms.ModelChoiceField(queryset=Vehicle.objects.none(), required=False)
    vehicle_type = forms.ChoiceField(
        choices=[("", "Any vehicle type"), *Vehicle.VehicleType.choices], required=False
    )
    start = forms.DateTimeField(input_formats=[DATETIME_LOCAL])
    end = forms.DateTimeField(input_formats=[DATETIME_LOCAL])

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.for_driver = can(user, Function.OWN_RESERVATIONS)
        self.fields["lot"].queryset = Lot.objects.active()
        if self.for_driver:
            self.fields["vehicle"].queryset = Vehicle.objects.filter(owner=user, is_active=True)
            self.fields["vehicle"].required = True

    def search_vehicle(self):
        """The vehicle to match slots against, or None for staff searching every slot type."""
        if self.for_driver:
            return self.cleaned_data["vehicle"]
        vehicle_type = self.cleaned_data.get("vehicle_type")
        return SimpleNamespace(vehicle_type=vehicle_type, owner=None) if vehicle_type else None
