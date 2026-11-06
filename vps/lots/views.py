"""Administrator lot pages; business rules belong to services."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import (
    require_GET,
    require_http_methods,
    require_POST,
    require_safe,
)

from vps.accounts.permissions import function_required
from vps.accounts.roles import Function
from vps.lots import services
from vps.lots.forms import LotForm, SlotBlockForm, TariffForm
from vps.lots.models import Lot, Tariff
from vps.lots.plan import build_lot_plan
from vps.vehicles.services import normalise_registration


@function_required(Function.MANAGE_LOTS)
@require_safe
def lot_list(request):
    archived = request.GET.get("archived") == "1"
    lots = Lot.objects.filter(is_archived=True) if archived else Lot.objects.active()
    return render(
        request,
        "lots/list.html",
        {
            "lots": lots.annotate(slot_count=Count("slots")),
            "archived": archived,
        },
    )


def _lot_form(request, lot=None):
    form = LotForm(request.POST if request.method == "POST" else None, instance=lot)
    if request.method == "POST" and form.is_valid():
        try:
            if lot is None:
                services.create_lot(**form.cleaned_data)
            else:
                services.update_lot(lot, **form.cleaned_data)
        except ValidationError as error:
            if hasattr(error, "error_dict"):
                for field, errors in error.error_dict.items():
                    form.add_error(field, errors)
            else:
                form.add_error(None, error)
        else:
            action = "created" if lot is None else "updated"
            messages.success(request, f"Parking lot {action} successfully.")
            return redirect("lots:list")
    return render(request, "lots/form.html", {"form": form, "lot": lot})


@function_required(Function.MANAGE_LOTS)
def lot_create(request):
    return _lot_form(request)


@function_required(Function.MANAGE_LOTS)
def lot_edit(request, pk):
    return _lot_form(request, get_object_or_404(Lot, pk=pk))


@function_required(Function.MANAGE_LOTS)
@require_POST
def lot_archive(request, pk):
    services.archive_lot(get_object_or_404(Lot, pk=pk))
    messages.success(request, "Parking lot archived successfully.")
    return redirect("lots:list")


@function_required(Function.MANAGE_LOTS)
@require_POST
def lot_restore(request, pk):
    services.restore_lot(get_object_or_404(Lot, pk=pk))
    messages.success(request, "Parking lot restored successfully.")
    return redirect("lots:list")


@function_required(Function.MANAGE_LOTS)
@require_http_methods(["GET", "POST"])
def block_slot(request, pk):
    """FR-LOT-03/04: block a slot; Reserved bookings in the period are moved or cancelled."""
    lot = get_object_or_404(Lot.objects.active(), pk=pk)
    form = SlotBlockForm(request.POST if request.method == "POST" else None, lot=lot)
    if request.method == "POST" and form.is_valid():
        try:
            block = services.block_slot(**form.cleaned_data, actor=request.user)
        except ValidationError as error:
            for field, errors in error.error_dict.items():
                form.add_error(field if field in form.fields else None, errors)
        else:
            messages.success(
                request,
                f"Slot {block.slot.code} blocked: {len(block.moved)} booking(s) moved, "
                f"{len(block.cancelled)} cancelled free of charge.",
            )
            for reservation in block.moved:
                messages.info(request, f"{reservation.booking_ref} moved to {reservation.slot.code}.")
            for reservation in block.cancelled:
                messages.warning(
                    request, f"{reservation.booking_ref} cancelled: no other slot was free."
                )
            return redirect("lots:block", pk=lot.pk)
    return render(request, "lots/block.html", {"form": form, "lot": lot})


def _tariff_page(request, form):
    """FR-BILL-01: the tariff form and every configured tariff, newest first per lot and type."""
    return render(
        request,
        "lots/tariffs.html",
        {
            "form": form,
            "lots": Lot.objects.active(),
            "tariffs": Tariff.objects.select_related("lot"),
            "save_tariff_url": reverse("lots:tariff_create"),
            "tariff_error": " ".join(error for errors in form.errors.values() for error in errors),
        },
    )


@function_required(Function.MANAGE_LOTS)
@require_safe
def tariff_list(request):
    return _tariff_page(request, TariffForm())


@function_required(Function.MANAGE_LOTS)
@require_POST
def tariff_create(request):
    form = TariffForm(request.POST)
    if form.is_valid():
        try:
            tariff = services.create_tariff(
                lot=form.cleaned_data["lot_id"],
                slot_type=form.cleaned_data["slot_type"],
                hourly_rate_inr=form.cleaned_data["hourly_rate_inr"],
                effective_from=form.cleaned_data["effective_from"],
                actor=request.user,
            )
        except ValidationError as error:
            for field, errors in error.error_dict.items():
                form.add_error(field if field in form.fields else None, errors)
        else:
            messages.success(
                request,
                f"Tariff saved: Rs {tariff.hourly_rate_inr:.2f} per hour for "
                f"{tariff.get_slot_type_display()} slots at {tariff.lot.name} "
                f"from {tariff.effective_from:%d %b %Y}.",
            )
            return redirect("lots:tariffs")
    return _tariff_page(request, form)


@require_GET
def occupancy(request):
    """FR-SRCH-03: public live occupancy; the page re-fetches its table every 30 seconds."""
    htmx = request.headers.get("HX-Request") == "true"
    return render(
        request,
        "lots/occupancy_table.html" if htmx else "lots/occupancy.html",
        {"rows": services.lot_occupancy(), "updated_at": timezone.localtime()},
    )


def _route_points(route):
    return " ".join(f"{x},{y}" for x, y in route)


def _bay_views(plan, states=None, highlight=None, link_base=""):
    states = states or {}
    rows = []
    for bay in plan.bays:
        state = states.get(bay.slot_id)
        rows.append(
            {
                "slot_id": bay.slot_id,
                "code": bay.code,
                "slot_type": bay.slot_type,
                "state": state.state if state else "free",
                "row": bay.row,
                "x": bay.x,
                "y": bay.y,
                "w": bay.w,
                "h": bay.h,
                "label_x": bay.cx,
                "label_y": bay.cy + 4,
                "mark_x": bay.x + 5,
                "mark_y": bay.y + 10,
                "is_you": bay.slot_id == highlight,
                "href": f"{link_base}slot={bay.slot_id}" if link_base else "",
            }
        )
    return rows


@function_required(Function.MANAGE_LOTS)
@require_safe
def lot_map(request):
    lots = list(Lot.objects.active().order_by("name"))
    q = (request.GET.get("q") or "").strip()
    lot_param = request.GET.get("lot")
    slot_param = request.GET.get("slot")
    search_result = None
    search_message = ""
    selected_lot = None
    highlight = None

    if q:
        search_result = services.find_parked_vehicle(q)
        if search_result and not search_result.slot.lot.is_archived:
            selected_lot = search_result.slot.lot
            highlight = search_result.slot_id
        else:
            display = normalise_registration(q.replace("-", "")) or (
                q.upper().replace(" ", "").replace("-", "")
            )
            search_message = f"{display} is not parked in any lot right now."

    if selected_lot is None:
        selected_lot = next((lot for lot in lots if str(lot.pk) == lot_param), None)
        if selected_lot is None and lots:
            selected_lot = lots[0]

    states = {}
    plan = None
    route = ()
    route_points = ""
    slot_detail = None
    slot_rows = []
    bay_views = []
    link_base = ""

    if selected_lot is not None:
        slots = list(selected_lot.slots.all())
        if slots:
            states = services.lot_map_state(selected_lot)
            plan = build_lot_plan(slots)
            if highlight is None and slot_param and slot_param.isdigit():
                slot_id = int(slot_param)
                if plan.bay_for(slot_id):
                    highlight = slot_id
            if highlight is not None:
                route = plan.route_to(highlight)
                route_points = _route_points(route)
            if slot_param and slot_param.isdigit() and plan.bay_for(int(slot_param)):
                slot_id = int(slot_param)
                state = states.get(slot_id)
                slot_detail = {"slot": selected_lot.slots.get(pk=slot_id), "state": state}
            link_base = f"{reverse('lots:map')}?lot={selected_lot.pk}&"
            bay_views = _bay_views(plan, states=states, highlight=highlight, link_base=link_base)
            slot_rows = [
                {"code": bay["code"], "slot_type": bay["slot_type"], "state": bay["state"]}
                for bay in bay_views
            ]

    context = {
        "lots": lots,
        "selected_lot": selected_lot,
        "plan": plan,
        "states": states,
        "highlight": highlight,
        "route": route,
        "route_points": route_points,
        "bay_views": bay_views,
        "search_query": q,
        "search_result": search_result,
        "search_message": search_message,
        "slot_detail": slot_detail,
        "slot_rows": slot_rows,
        "link_base": link_base,
        "refresh_query": request.GET.urlencode(),
        "updated_at": timezone.localtime(),
    }
    template = "lots/map_panel.html" if request.headers.get("HX-Request") == "true" else "lots/map.html"
    return render(request, template, context)
