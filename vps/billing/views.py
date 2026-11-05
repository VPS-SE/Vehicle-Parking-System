"""BR-09: Lot Administrators find outstanding charges and waive them with a reason."""

from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from vps.accounts.permissions import function_required
from vps.accounts.roles import Function
from vps.billing.models import Charge, Waiver
from vps.billing.services import REASON_MAX_LENGTH, unpaid_charges, waive_charge


@function_required(Function.WAIVE_CHARGES)
@require_GET
def waivers(request):
    """Search outstanding charges and list the most recent waivers."""
    query = request.GET.get("q", "")
    recent = Waiver.objects.select_related("charge__reservation", "waived_by")[:20]
    return render(
        request,
        "billing/waivers.html",
        {
            "q": query,
            "charges": unpaid_charges(query),
            "recent": recent,
            "reason_max_length": REASON_MAX_LENGTH,
        },
    )


@function_required(Function.WAIVE_CHARGES)
@require_POST
def waive(request, charge_id):
    """Waive one charge and return to the same search with the result."""
    charge = get_object_or_404(Charge.objects.select_related("reservation"), pk=charge_id)
    back = reverse("billing:waivers") + "?" + urlencode({"q": request.POST.get("q", "")})
    try:
        waive_charge(request.user, charge, request.POST.get("reason", ""))
    except ValidationError as error:
        for message in error.messages:
            messages.error(request, message)
    else:
        messages.success(
            request,
            f"Waived the Rs {charge.amount_inr:.2f} {charge.get_kind_display().lower()} "
            f"charge on {charge.reservation.booking_ref}.",
        )
    return redirect(back)
