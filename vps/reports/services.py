"""Report calculations."""

from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, Q
from django.utils import timezone

from vps.billing.models import Charge, Payment
from vps.lots.models import Slot

REVENUE_AMOUNTS = (
    "parking_inr",
    "overstay_inr",
    "late_noshow_inr",
    "cash_inr",
    "upi_inr",
    "card_inr",
    "unpaid_inr",
)
_CHARGE_COLUMN = {
    Charge.Kind.PARKING: "parking_inr",
    Charge.Kind.OVERSTAY: "overstay_inr",
    Charge.Kind.LATE_CANCEL: "late_noshow_inr",
    Charge.Kind.NO_SHOW: "late_noshow_inr",
}
_PAYMENT_COLUMN = {
    Payment.Method.CASH: "cash_inr",
    Payment.Method.UPI: "upi_inr",
    Payment.Method.CARD: "card_inr",
}


def revenue_report(start_date, end_date):
    """FR-RPT-03 and SRS Table 4: one row per lot, date and slot type, both dates included.

    A charge is dated by its booking's exit time, or by the booking's start when the vehicle
    never parked (late cancellation, no-show). Payments are dated by when they were taken, so
    a day's payments can settle charges from an earlier day. Unpaid is what is still owed on
    the day's charges; a waived charge (BR-09) is not owed. Completed stays are bookings that left that day.
    """
    from vps.reservations.models import Reservation

    window_start = timezone.make_aware(datetime.combine(start_date, time.min))
    window_end = timezone.make_aware(datetime.combine(end_date + timedelta(days=1), time.min))
    rows = {}

    def bucket(lot_id, lot_name, moment, slot_type):
        key = (lot_name, lot_id, timezone.localdate(moment), slot_type)
        if key not in rows:
            rows[key] = {"completed_stays": 0, **dict.fromkeys(REVENUE_AMOUNTS, Decimal("0.00"))}
        return rows[key]

    in_window = Q(
        reservation__exit_time__gte=window_start, reservation__exit_time__lt=window_end
    ) | Q(
        reservation__exit_time__isnull=True,
        reservation__period__startswith__gte=window_start,
        reservation__period__startswith__lt=window_end,
    )
    charges = Charge.objects.filter(in_window).values_list(
        "reservation__slot__lot_id",
        "reservation__slot__lot__name",
        "reservation__exit_time",
        "reservation__period",
        "reservation__slot__slot_type",
        "kind",
        "amount_inr",
        "payment__id",
        "waiver__id",
    )
    for lot_id, lot_name, exit_time, period, slot_type, kind, amount, paid, waived in charges:
        row = bucket(lot_id, lot_name, exit_time or period.lower, slot_type)
        row[_CHARGE_COLUMN[kind]] += amount
        if paid is None and waived is None:  # BR-09: a waived charge is no longer owed
            row["unpaid_inr"] += amount

    payments = Payment.objects.filter(
        paid_at__gte=window_start, paid_at__lt=window_end
    ).values_list(
        "charge__reservation__slot__lot_id",
        "charge__reservation__slot__lot__name",
        "paid_at",
        "charge__reservation__slot__slot_type",
        "method",
        "charge__amount_inr",
    )
    for lot_id, lot_name, paid_at, slot_type, method, amount in payments:
        bucket(lot_id, lot_name, paid_at, slot_type)[_PAYMENT_COLUMN[method]] += amount

    stays = Reservation.objects.filter(
        status=Reservation.Status.COMPLETED, exit_time__gte=window_start, exit_time__lt=window_end
    ).values_list("slot__lot_id", "slot__lot__name", "exit_time", "slot__slot_type")
    for lot_id, lot_name, exit_time, slot_type in stays:
        bucket(lot_id, lot_name, exit_time, slot_type)["completed_stays"] += 1

    labels = dict(Slot.SlotType.choices)
    return [
        {"lot_name": lot_name, "date": day, "slot_type_label": labels[slot_type], **values}
        for (lot_name, _lot_id, day, slot_type), values in sorted(rows.items())
    ]


def _spread_by_hour(start, end, add):
    """Call add(local_date, hour, minutes) for each local clock hour that [start, end) covers."""
    start, end = timezone.localtime(start), timezone.localtime(end)
    cursor = start
    while cursor < end:
        hour_end = cursor.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        stop = min(hour_end, end)
        add(cursor.date(), cursor.hour, (stop - cursor).total_seconds() / 60)
        cursor = stop


def occupancy_report(lot, start_date, end_date, now=None):
    """FR-RPT-02: per date, hour and slot type, the average occupied and blocked slots.

    An hour's average is the slot-minutes used in it divided by 60, so a slot taken for half
    an hour counts as 0.5. A vehicle still parked counts up to now. Rows cover every hour of
    every date in the range (inclusive) for each slot type the lot has.
    """
    from vps.lots.models import SlotBlock
    from vps.reservations.models import Reservation

    now = now or timezone.now()
    window_start = timezone.make_aware(datetime.combine(start_date, time.min))
    window_end = timezone.make_aware(datetime.combine(end_date + timedelta(days=1), time.min))
    totals = dict(
        lot.slots.values("slot_type").annotate(n=Count("pk")).values_list("slot_type", "n")
    )
    occupied, blocked = defaultdict(float), defaultdict(float)

    stays = (
        Reservation.objects.filter(
            slot__lot=lot, entry_time__isnull=False, entry_time__lt=window_end
        )
        .filter(
            Q(exit_time__isnull=True, status=Reservation.Status.ACTIVE)
            | Q(exit_time__gt=window_start)
        )
        .values_list("slot__slot_type", "entry_time", "exit_time")
    )
    for slot_type, entry, exit_ in stays:
        begin, finish = max(entry, window_start), min(exit_ or now, window_end)

        def add_stay(day, hour, minutes, slot_type=slot_type):
            occupied[day, hour, slot_type] += minutes

        _spread_by_hour(begin, finish, add_stay)

    blocks = SlotBlock.objects.filter(
        slot__lot=lot, period__overlap=(window_start, window_end)
    ).values_list("slot__slot_type", "period")
    for slot_type, period in blocks:
        begin, finish = max(period.lower, window_start), min(period.upper, window_end)

        def add_block(day, hour, minutes, slot_type=slot_type):
            blocked[day, hour, slot_type] += minutes

        _spread_by_hour(begin, finish, add_block)

    labels = dict(Slot.SlotType.choices)
    rows = []
    day = start_date
    while day <= end_date:
        for hour in range(24):
            for slot_type in sorted(totals):
                key = (day, hour, slot_type)
                average = occupied[key] / 60
                rows.append(
                    {
                        "lot_name": lot.name,
                        "date": day,
                        "hour": hour,
                        "slot_type": slot_type,
                        "slot_type_label": labels[slot_type],
                        "total_slots": totals[slot_type],
                        "average_occupied": average,
                        "occupancy_pct": 100 * average / totals[slot_type],
                        "average_blocked": blocked[key] / 60,
                    }
                )
        day += timedelta(days=1)
    return rows


def search_audit(actor="", action="", start_date=None, end_date=None):
    """FR-RPT-04: audit entries filtered by actor e-mail, action and date range, newest first.

    actor matches part of the e-mail; action matches from the start, so "tariff" finds every
    tariff entry. Both ends of the date range are included.
    """
    from vps.audit.models import AuditLog

    entries = AuditLog.objects.select_related("actor")
    if actor:
        entries = entries.filter(actor__email__icontains=actor.strip())
    if action:
        entries = entries.filter(action__istartswith=action.strip())
    if start_date:
        entries = entries.filter(
            at__gte=timezone.make_aware(datetime.combine(start_date, time.min))
        )
    if end_date:
        next_day = timezone.make_aware(datetime.combine(end_date + timedelta(days=1), time.min))
        entries = entries.filter(at__lt=next_day)
    return entries.order_by("-at", "-id")


def audit_actions():
    """The distinct action names recorded so far, for the search box's suggestions."""
    from vps.audit.models import AuditLog

    return list(AuditLog.objects.order_by("action").values_list("action", flat=True).distinct())
