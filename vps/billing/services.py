"""Payment recording (FR-GATE-05), charge waivers (BR-09) and unpaid-charge lookup."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum

from vps.accounts.roles import Function, can
from vps.audit.models import AuditLog
from vps.billing.models import Charge, Payment, Waiver
from vps.vehicles.services import normalise_registration

ALREADY_PAID = "This charge has already been paid."
ALREADY_WAIVED = "This charge has already been waived."
REASON_REQUIRED = "Give a written reason for waiving this charge."
REASON_MAX_LENGTH = 500

# A charge is outstanding until it is either paid or waived.
OUTSTANDING = Q(payment__isnull=True, waiver__isnull=True)


def record_payment(attendant, charge, method):
    """FR-GATE-05: record one payment and its audit entry atomically."""
    if not can(attendant, Function.GATE_OPERATIONS):
        raise ValidationError({"__all__": "Only Gate Attendants may record payments."})
    if method not in Payment.Method.values:
        raise ValidationError({"method": "Choose Cash, UPI or Card."})
    try:
        with transaction.atomic():
            charge = Charge.objects.select_for_update().get(pk=charge.pk)
            if Payment.objects.filter(charge=charge).exists():
                raise ValidationError({"__all__": ALREADY_PAID})
            if Waiver.objects.filter(charge=charge).exists():
                raise ValidationError({"__all__": ALREADY_WAIVED})
            payment = Payment.objects.create(charge=charge, method=method, recorded_by=attendant)
            AuditLog.objects.create(
                actor=attendant,
                action="payment.recorded",
                target=f"charge:{charge.pk}",
                after={
                    "reservation": charge.reservation.booking_ref,
                    "kind": charge.kind,
                    "amount_inr": str(charge.amount_inr),
                    "method": method,
                },
            )
    except IntegrityError as error:
        if getattr(getattr(error.__cause__, "diag", None), "constraint_name", None) == (
            "billing_payment_charge_id_key"
        ):
            raise ValidationError({"__all__": ALREADY_PAID}) from error
        raise
    return payment


def unpaid_charges(query):
    """FR-GATE-05: find unpaid charges by booking reference or normalised registration."""
    query = query.strip()
    if not query:
        return []
    return (
        Charge.objects.filter(
            Q(reservation__booking_ref__iexact=query)
            | Q(reservation__vehicle_reg_no=normalise_registration(query)),
            OUTSTANDING,
        )
        .select_related("reservation")
        .order_by("id")
    )


def unpaid_total(driver):
    """FR-BILL-05: the sum of a Driver's charges that are neither paid nor waived."""
    if getattr(driver, "pk", None) is None:  # None, AnonymousUser or an unsaved user
        return Decimal("0.00")
    total = Charge.objects.filter(OUTSTANDING, reservation__driver=driver).aggregate(
        total=Sum("amount_inr")
    )["total"]
    return total or Decimal("0.00")


def waive_charge(admin, charge, reason):
    """BR-09: an Admin waives an outstanding charge with a written reason, audited atomically."""
    if not can(admin, Function.WAIVE_CHARGES):
        raise ValidationError({"__all__": "Only Lot Administrators may waive charges."})
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError({"reason": REASON_REQUIRED})
    if len(reason) > REASON_MAX_LENGTH:
        raise ValidationError(
            {"reason": f"Keep the reason to {REASON_MAX_LENGTH} characters or fewer."}
        )
    try:
        with transaction.atomic():
            charge = Charge.objects.select_for_update().get(pk=charge.pk)
            if Payment.objects.filter(charge=charge).exists():
                raise ValidationError({"__all__": ALREADY_PAID})
            if Waiver.objects.filter(charge=charge).exists():
                raise ValidationError({"__all__": ALREADY_WAIVED})
            waiver = Waiver.objects.create(charge=charge, reason=reason, waived_by=admin)
            AuditLog.objects.create(
                actor=admin,
                action="charge.waived",
                target=f"charge:{charge.pk}",
                before={"amount_inr": str(charge.amount_inr), "status": "unpaid"},
                after={
                    "reservation": charge.reservation.booking_ref,
                    "kind": charge.kind,
                    "amount_inr": str(charge.amount_inr),
                    "status": "waived",
                    "reason": reason,
                },
            )
    except IntegrityError as error:
        if getattr(getattr(error.__cause__, "diag", None), "constraint_name", None) == (
            "billing_waiver_charge_id_key"
        ):
            raise ValidationError({"__all__": ALREADY_WAIVED}) from error
        raise
    return waiver
