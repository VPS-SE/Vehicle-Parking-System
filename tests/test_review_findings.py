"""Reproduction tests for code review findings F1 through F7.

Each test is marked @pytest.mark.xfail(strict=True, reason="F<n>: <one line>")
so the test suite stays green, and flips to failure (XPASS) when the application
code is corrected.
"""

from datetime import time, timedelta
from decimal import Decimal

import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.backends.postgresql.psycopg_any import DateTimeTZRange
from django.utils import timezone

from vps.accounts import services as account_services
from vps.accounts.models import User
from vps.accounts.roles import Function, can
from vps.audit.models import AuditLog
from vps.billing.models import Charge
from vps.billing.services import unpaid_total
from vps.gate import services as gate_services
from vps.lots import services as lot_services
from vps.lots.models import Lot, Slot
from vps.notifications import services as notif_services
from vps.notifications.models import ReservationNotification
from vps.reservations.models import Reservation
from vps.vehicles.models import Vehicle

pytestmark = pytest.mark.django_db


@pytest.fixture
def lot():
    return Lot.objects.create(
        name="Lot Review",
        address="10 University Road",
        opens_at=time(6),
        closes_at=time(23),
    )


@pytest.fixture
def slot(lot):
    return Slot.objects.create(lot=lot, code="R-01", distance_rank=1)


def test_f01_case_insensitive_duplicate_email_rejected():
    """F1: registering ASHA@example.com when asha@example.com exists must be rejected."""
    account_services.register_driver(
        full_name="Asha Rao",
        email="asha@example.com",
        mobile="9876543210",
        password="ValidPassword2026!",
    )
    assert User.objects.filter(email__iexact="asha@example.com").count() == 1

    # Attempting to register ASHA@example.com must raise ValidationError
    with pytest.raises(ValidationError) as exc:
        account_services.register_driver(
            full_name="Asha Rao",
            email="ASHA@example.com",
            mobile="9876543211",
            password="ValidPassword2026!",
        )
    assert "email" in exc.value.message_dict
    assert User.objects.filter(email__iexact="asha@example.com").count() == 1


def test_f02_account_lockout_after_five_failed_logins(client):
    """F2: 5 failed logins within window must lock account and return HTTP 423 on 6th attempt."""
    account_services.register_driver(
        full_name="Asha Rao",
        email="asha@example.com",
        mobile="9876543210",
        password="CorrectPassword2026!",
    )

    # 5 failed sign-in attempts
    for _ in range(5):
        resp = client.post(
            "/accounts/login/",
            {"email": "asha@example.com", "password": "WrongPassword!"},
        )
        assert resp.status_code == 200

    # 6th attempt with correct password must be locked with HTTP 423
    resp6 = client.post(
        "/accounts/login/",
        {"email": "asha@example.com", "password": "CorrectPassword2026!"},
    )
    assert resp6.status_code == 423
    user = User.objects.get(email="asha@example.com")
    assert user.locked_until is not None
    assert user.locked_until > timezone.now()


@pytest.mark.xfail(
    strict=True,
    reason="F3: Lot Administrator denied access to correct entry times (Table 5 Appendix B.3)",
)
def test_f03_admin_permitted_to_correct_entry_time(client, slot):
    """F3: Lot Administrator must be permitted to correct entry times per permission matrix."""
    admin = User.objects.create_user(
        email="admin@example.com",
        password="ValidPassword2026!",
        role=User.Role.ADMIN,
    )
    driver = User.objects.create_user(email="driver@example.com")
    car = Vehicle.objects.create(owner=driver, registration_no="KA01AB1234", vehicle_type="Car")

    now = timezone.now()
    reservation = Reservation.objects.create(
        booking_ref="VPS-261104-0010",
        driver=driver,
        vehicle_reg_no=car.registration_no,
        slot=slot,
        period=DateTimeTZRange(now - timedelta(hours=3), now + timedelta(hours=1)),
        status=Reservation.Status.ACTIVE,
        entry_time=now - timedelta(hours=3),
    )

    paper_entry = now - timedelta(hours=2)
    # Admin must be permitted by can() and correct_entry_time service
    assert can(admin, Function.CORRECT_TIMES) is True

    # Calling service as admin should succeed without ValidationError
    updated = gate_services.correct_entry_time(
        attendant=admin,
        query=reservation.booking_ref,
        entry_time=paper_entry,
        reason="Power outage during entry",
    )
    assert updated.entry_time == paper_entry

    # Calling view as admin should return 302/200, not 403
    client.force_login(admin)
    view_resp = client.get("/gate/correct-entry/")
    assert view_resp.status_code == 200


@pytest.mark.xfail(
    strict=True,
    reason="F4: Slot blocks and staff creation do not write audit log entries (SEC-07)",
)
def test_f04_slot_blocks_and_staff_creation_are_audited(slot):
    """F4: SEC-07 mandates audit entries for every slot block and staff creation."""
    User.objects.create_user(
        email="admin@example.com",
        role=User.Role.ADMIN,
    )
    now = timezone.now()

    # Block slot
    lot_services.block_slot(
        slot=slot,
        starts_at=now,
        ends_at=now + timedelta(hours=2),
        reason="Sensor repair",
    )

    # Must generate an audit log entry for slot block
    assert AuditLog.objects.filter(target__icontains=slot.code).exists()

    # Create staff
    account_services.create_staff(
        full_name="Gate Staff",
        email="gatestaff@example.com",
        mobile="9876543219",
        password="ValidPassword2026!",
        role=User.Role.ATTENDANT,
    )

    # Must generate an audit log entry for staff creation
    assert AuditLog.objects.filter(target__icontains="gatestaff@example.com").exists()


@pytest.mark.xfail(
    strict=True,
    reason="F5: send_mail network I/O executed while holding PostgreSQL row locks in transaction",
)
def test_f05_email_sending_not_performed_inside_database_transaction(monkeypatch, slot):
    """F5: send_mail network call must execute outside atomic database transaction block."""
    driver = User.objects.create_user(email="driver@example.com", full_name="Driver User")
    now = timezone.now()
    reservation = Reservation.objects.create(
        booking_ref="VPS-261104-0020",
        driver=driver,
        vehicle_reg_no="KA01AB9999",
        slot=slot,
        period=DateTimeTZRange(now, now + timedelta(hours=2)),
        status=Reservation.Status.RESERVED,
    )
    notif_services.queue_reservation_notification(
        reservation,
        ReservationNotification.Event.CREATED,
    )

    was_in_atomic = []

    def fake_send_mail(*args, **kwargs):
        was_in_atomic.append(connection.in_atomic_block)
        return 1

    monkeypatch.setattr("vps.notifications.services.send_mail", fake_send_mail)
    notif_services.process_pending_notifications(batch_size=1)

    assert len(was_in_atomic) == 1
    # send_mail must NOT be called while connection.in_atomic_block is True
    assert was_in_atomic[0] is False


@pytest.mark.xfail(
    strict=True,
    reason="F6: unpaid_total(None) aggregates all walk-in charges instead of returning 0.00",
)
def test_f06_unpaid_total_for_none_driver_returns_zero(slot):
    """F6: unpaid_total(None) must return 0.00 and not leak walk-in charges."""
    now = timezone.now()
    # Walk-in reservation has driver=None
    walk_in = Reservation.objects.create(
        booking_ref="VPS-261104-0030",
        driver=None,
        vehicle_reg_no="KA05MN4321",
        slot=slot,
        period=DateTimeTZRange(now - timedelta(hours=2), now),
        status=Reservation.Status.COMPLETED,
        is_walk_in=True,
        entry_time=now - timedelta(hours=2),
        exit_time=now,
    )
    Charge.objects.create(
        reservation=walk_in,
        kind=Charge.Kind.PARKING,
        amount_inr=Decimal("80.00"),
    )

    # For None / unauthenticated driver, unpaid_total must be Decimal('0.00')
    assert unpaid_total(None) == Decimal("0.00")


@pytest.mark.xfail(
    strict=True,
    reason="F7: SESSION_COOKIE_AGE and SESSION_SAVE_EVERY_REQUEST (SEC-08) not configured in settings",
)
def test_f07_session_cookie_configuration_enforces_sec04_sec08():
    """F7: SEC-08 requires 30-minute idle session timeout; settings default to 14 days."""
    # SEC-08 requires 30 minutes (1800 seconds) idle expiration
    cookie_age = getattr(settings, "SESSION_COOKIE_AGE", None)
    save_every_req = getattr(settings, "SESSION_SAVE_EVERY_REQUEST", False)

    assert cookie_age is not None
    assert cookie_age <= 1800, f"SESSION_COOKIE_AGE is {cookie_age}, must be <= 1800s"
    assert save_every_req is True, "SESSION_SAVE_EVERY_REQUEST must be True for idle sliding timeout"
