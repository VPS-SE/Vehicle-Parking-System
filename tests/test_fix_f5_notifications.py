"""Tests for Finding F5: decoupled transaction and network I/O for email sending.

Edge cases covered:
1. send_mail executes when connection.in_atomic_block is False (transactional test, so no
   test-wide atomic block hides the result).
2. Failure path records last_error and resets status (does not leave row sending).
3. Notification reaching MAX_ATTEMPTS transitions to FAILED and clears claimed_at.
4. Stale sending notification (exceeding timeout) is retried.
5. Fresh sending notification (within timeout) is skipped.
6. A notification is attempted at most once per process_pending_notifications run (tried list).
7. queue_reservation_notification remains idempotent on event_key.
"""

from datetime import time, timedelta

import pytest
from django.db import connection
from django.db.backends.postgresql.psycopg_any import DateTimeTZRange
from django.utils import timezone

from vps.accounts.models import User
from vps.lots.models import Lot, Slot
from vps.notifications import services as notif_services
from vps.notifications.models import ReservationNotification
from vps.reservations.models import Reservation

pytestmark = pytest.mark.django_db


@pytest.fixture
def driver():
    return User.objects.create_user(email="f5_driver@example.com", full_name="F5 Driver")


@pytest.fixture
def lot():
    lot_obj = Lot.objects.create(
        name="Lot F5",
        address="100 Technology Road",
        opens_at=time(6),
        closes_at=time(23),
    )
    Slot.objects.create(lot=lot_obj, code="F5-01", distance_rank=1)
    return lot_obj


@pytest.fixture
def reservation(driver, lot):
    now = timezone.now()
    return Reservation.objects.create(
        booking_ref="VPS-261105-0050",
        driver=driver,
        vehicle_reg_no="KA01F51234",
        slot=lot.slots.get(),
        period=DateTimeTZRange(now + timedelta(hours=1), now + timedelta(hours=3)),
        status=Reservation.Status.RESERVED,
    )


@pytest.mark.django_db(transaction=True)
def test_send_mail_sees_connection_not_in_atomic_block(monkeypatch, reservation):
    """send_mail must execute with connection.in_atomic_block False."""
    notif = notif_services.queue_reservation_notification(
        reservation,
        ReservationNotification.Event.CREATED,
    )

    in_atomic_flags = []

    def mock_send_mail(*args, **kwargs):
        in_atomic_flags.append(connection.in_atomic_block)
        return 1

    monkeypatch.setattr("vps.notifications.services.send_mail", mock_send_mail)
    result = notif_services.process_pending_notifications(batch_size=1)

    assert result == {"sent": 1, "failed": 0}
    assert len(in_atomic_flags) == 1
    assert in_atomic_flags[0] is False

    notif.refresh_from_db()
    assert notif.status == ReservationNotification.Status.SENT
    assert notif.sent_at is not None
    assert notif.claimed_at is None
    assert notif.last_error == ""


def test_failure_path_records_last_error_and_resets_status(monkeypatch, reservation):
    """When send_mail fails, last_error is recorded and status is reset to PENDING."""
    notif = notif_services.queue_reservation_notification(
        reservation,
        ReservationNotification.Event.CREATED,
    )

    def failing_send_mail(*args, **kwargs):
        raise RuntimeError("SMTP server connection timeout")

    monkeypatch.setattr("vps.notifications.services.send_mail", failing_send_mail)
    result = notif_services.process_pending_notifications(batch_size=1)

    assert result == {"sent": 0, "failed": 1}

    notif.refresh_from_db()
    # Row must not be left sending
    assert notif.status == ReservationNotification.Status.PENDING
    assert notif.claimed_at is None
    assert notif.attempts == 1
    assert "SMTP server connection timeout" in notif.last_error


def test_failure_path_marks_failed_after_max_attempts(monkeypatch, reservation):
    """When attempts reaches MAX_ATTEMPTS, status becomes FAILED and claimed_at is None."""
    notif = notif_services.queue_reservation_notification(
        reservation,
        ReservationNotification.Event.CREATED,
    )
    notif.attempts = notif_services.MAX_ATTEMPTS - 1
    notif.save(update_fields=["attempts"])

    def failing_send_mail(*args, **kwargs):
        raise RuntimeError("Permanent SMTP rejection")

    monkeypatch.setattr("vps.notifications.services.send_mail", failing_send_mail)
    result = notif_services.process_pending_notifications(batch_size=1)

    assert result == {"sent": 0, "failed": 1}

    notif.refresh_from_db()
    assert notif.status == ReservationNotification.Status.FAILED
    assert notif.claimed_at is None
    assert notif.attempts == notif_services.MAX_ATTEMPTS
    assert "Permanent SMTP rejection" in notif.last_error


def test_stale_in_progress_row_is_retried(monkeypatch, reservation):
    """A row stuck in SENDING longer than timeout must be picked up and retried."""
    now = timezone.now()
    notif = notif_services.queue_reservation_notification(
        reservation,
        ReservationNotification.Event.CREATED,
    )
    # Simulate an abandoned job that crashed 15 minutes ago
    notif.status = ReservationNotification.Status.SENDING
    notif.claimed_at = now - timedelta(minutes=15)
    notif.attempts = 1
    notif.save(update_fields=["status", "claimed_at", "attempts"])

    sent_calls = []

    def mock_send_mail(*args, **kwargs):
        sent_calls.append(kwargs.get("recipient_list") or args[3])
        return 1

    monkeypatch.setattr("vps.notifications.services.send_mail", mock_send_mail)
    result = notif_services.process_pending_notifications(batch_size=1)

    assert result == {"sent": 1, "failed": 0}
    assert len(sent_calls) == 1

    notif.refresh_from_db()
    assert notif.status == ReservationNotification.Status.SENT
    assert notif.sent_at is not None
    assert notif.claimed_at is None
    assert notif.attempts == 2


def test_fresh_in_progress_row_is_skipped(monkeypatch, reservation):
    """A row claimed recently (< timeout) by another worker must NOT be picked up."""
    now = timezone.now()
    notif = notif_services.queue_reservation_notification(
        reservation,
        ReservationNotification.Event.CREATED,
    )
    # Claimed 2 minutes ago (well within the 10-minute timeout)
    fresh_claimed_at = now - timedelta(minutes=2)
    notif.status = ReservationNotification.Status.SENDING
    notif.claimed_at = fresh_claimed_at
    notif.attempts = 1
    notif.save(update_fields=["status", "claimed_at", "attempts"])

    sent_calls = []

    def mock_send_mail(*args, **kwargs):
        sent_calls.append(args)
        return 1

    monkeypatch.setattr("vps.notifications.services.send_mail", mock_send_mail)
    result = notif_services.process_pending_notifications(batch_size=1)

    assert result == {"sent": 0, "failed": 0}
    assert len(sent_calls) == 0

    notif.refresh_from_db()
    # Row remains untouched sending
    assert notif.status == ReservationNotification.Status.SENDING
    assert notif.claimed_at == fresh_claimed_at
    assert notif.attempts == 1


def test_retry_once_per_run_via_tried_list(monkeypatch, reservation):
    """A failed notification is not retried within the same run even with batch_size > 1."""
    notif = notif_services.queue_reservation_notification(
        reservation,
        ReservationNotification.Event.CREATED,
    )

    attempt_counter = [0]

    def failing_send_mail(*args, **kwargs):
        attempt_counter[0] += 1
        raise RuntimeError("Transient delivery error")

    monkeypatch.setattr("vps.notifications.services.send_mail", failing_send_mail)
    # Request a batch size of 5; since there is only 1 notification, it shouldn't be retried
    result = notif_services.process_pending_notifications(batch_size=5)

    assert result == {"sent": 0, "failed": 1}
    assert attempt_counter[0] == 1

    notif.refresh_from_db()
    assert notif.status == ReservationNotification.Status.PENDING
    assert notif.attempts == 1


def test_idempotent_event_key(reservation):
    """queue_reservation_notification returns the same row on duplicate calls."""
    first = notif_services.queue_reservation_notification(
        reservation,
        ReservationNotification.Event.CREATED,
    )
    second = notif_services.queue_reservation_notification(
        reservation,
        ReservationNotification.Event.CREATED,
    )

    assert first.pk == second.pk
    assert ReservationNotification.objects.count() == 1
