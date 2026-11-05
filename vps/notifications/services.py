"""Reservation e-mails (FR-RES-07): queued with the change, sent by the scheduler."""

from datetime import timedelta
from smtplib import SMTPException

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from vps.notifications.models import ReservationNotification

MAX_ATTEMPTS = 5
STALE_CLAIM = timedelta(minutes=10)


def queue_reservation_notification(reservation, event):
    """Queue an email for a reservation event."""

    if not reservation.driver or not reservation.driver.email:
        return None

    event_labels = {
        ReservationNotification.Event.CREATED: "created",
        ReservationNotification.Event.CANCELLED: "cancelled",
        ReservationNotification.Event.MOVED: "rescheduled",
        ReservationNotification.Event.EXPIRED: "expired",
    }

    label = event_labels[event]

    subject = f"Parking booking {label}: {reservation.booking_ref}"

    message = (
        f"Hello {reservation.driver.full_name},\n\n"
        f"Your parking booking has been {label}.\n\n"
        f"Booking reference: {reservation.booking_ref}\n"
        f"Vehicle: {reservation.vehicle_reg_no}\n"
        f"Parking slot: {reservation.slot}\n"
        f"Status: {reservation.status}\n\n"
        "Vehicle Parking System"
    )

    period = reservation.period
    # The slot is part of the key, so a booking moved twice gets an e-mail for each move.
    event_key = (
        f"{reservation.pk}:{event}:{reservation.slot_id}:"
        f"{period.lower.isoformat()}:{period.upper.isoformat()}"
    )

    notification, _ = ReservationNotification.objects.get_or_create(
        event_key=event_key,
        defaults={
            "reservation": reservation,
            "event": event,
            "recipient_email": reservation.driver.email,
            "subject": subject,
            "message": message,
        },
    )

    return notification


def _claim_next(tried, now, stale_after):
    """Mark the oldest sendable row as SENDING and commit, so no lock is held while mailing.

    A row left in SENDING by a process that died is picked up again after stale_after.
    """
    Status = ReservationNotification.Status
    with transaction.atomic():
        notification = (
            ReservationNotification.objects.select_for_update(skip_locked=True)
            .filter(
                Q(status=Status.PENDING)
                | Q(status=Status.SENDING, claimed_at__lte=now - stale_after),
                attempts__lt=MAX_ATTEMPTS,
            )
            .exclude(pk__in=tried)
            .order_by("created_at")
            .first()
        )
        if notification is not None:
            notification.status = Status.SENDING
            notification.claimed_at = now
            notification.attempts += 1
            notification.save(update_fields=["status", "claimed_at", "attempts"])
    return notification


def process_pending_notifications(batch_size=50, stale_after=STALE_CLAIM):
    """Send pending notification e-mails, one short transaction before and after each send."""
    Status = ReservationNotification.Status
    sent = 0
    failed = 0
    # One attempt per notification per run: the scheduler runs every minute, so retries
    # are spread out instead of using up every attempt during one short mail outage.
    tried = []

    for _ in range(batch_size):
        notification = _claim_next(tried, timezone.now(), stale_after)
        if notification is None:
            break
        tried.append(notification.pk)

        try:
            result = send_mail(
                subject=notification.subject,
                message=notification.message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[notification.recipient_email],
                fail_silently=False,
            )
            if result != 1:
                raise RuntimeError("Email backend did not confirm delivery.")
        except (SMTPException, OSError, RuntimeError) as error:
            notification.last_error = str(error)
            notification.status = (
                Status.FAILED if notification.attempts >= MAX_ATTEMPTS else Status.PENDING
            )
            failed += 1
        else:
            notification.status = Status.SENT
            notification.sent_at = timezone.now()
            notification.last_error = ""
            sent += 1

        notification.claimed_at = None
        notification.save(update_fields=["status", "sent_at", "last_error", "claimed_at"])

    return {"sent": sent, "failed": failed}
