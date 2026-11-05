"""Report calculations."""

from django.db.models import Count, F, Sum

from vps.billing.models import Payment
from vps.lots.models import Slot


def revenue_totals(start_date, end_date):
    """Return revenue grouped by lot, slot type and payment method for inclusive dates."""
    rows = (
        Payment.objects.filter(paid_at__date__range=(start_date, end_date))
        .values(
            lot_id=F("charge__reservation__slot__lot_id"),
            lot_name=F("charge__reservation__slot__lot__name"),
            lot_address=F("charge__reservation__slot__lot__address"),
            slot_type=F("charge__reservation__slot__slot_type"),
            payment_method=F("method"),
        )
        .annotate(payment_count=Count("pk"), revenue_inr=Sum("charge__amount_inr"))
        .order_by("lot_name", "lot_address", "slot_type", "payment_method")
    )
    slot_type_labels = dict(Slot.SlotType.choices)
    payment_method_labels = dict(Payment.Method.choices)
    return [
        {
            **row,
            "slot_type_label": slot_type_labels[row["slot_type"]],
            "payment_method_label": payment_method_labels[row["payment_method"]],
        }
        for row in rows
    ]
