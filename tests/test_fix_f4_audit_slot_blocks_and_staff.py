"""Tests for Finding F4: SEC-07 audit logging for slot blocks and staff account changes."""

import json
from datetime import time, timedelta

import pytest
from django.utils import timezone

from vps.accounts import services as account_services
from vps.accounts.models import User
from vps.audit.models import AuditLog
from vps.lots import services as lot_services
from vps.lots.models import Lot, Slot

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin():
    return User.objects.create_user(
        email="admin@example.com",
        password="AdminPassword2026!",
        full_name="Lot Administrator",
        mobile="9876543210",
        role=User.Role.ADMIN,
    )


@pytest.fixture
def lot():
    return Lot.objects.create(
        name="Lot F4",
        address="4 Audit Boulevard",
        opens_at=time(6),
        closes_at=time(23),
    )


@pytest.fixture
def slot(lot):
    return Slot.objects.create(lot=lot, code="F4-01", distance_rank=1)


def test_view_block_slot_records_actor(client, lot, slot, admin):
    """Actor (request.user) must be recorded in AuditLog when block_slot is called via view."""
    client.force_login(admin)
    now = timezone.now().replace(microsecond=0)
    starts_at = now + timedelta(hours=1)
    ends_at = now + timedelta(hours=3)

    response = client.post(
        f"/lots/{lot.pk}/block/",
        {
            "slot": slot.pk,
            "starts_at": starts_at.strftime("%Y-%m-%dT%H:%M"),
            "ends_at": ends_at.strftime("%Y-%m-%dT%H:%M"),
            "reason": "Routine inspection",
        },
        follow=True,
    )
    assert response.status_code == 200

    audit = AuditLog.objects.filter(
        action="slot.blocked", target=f"slot:{lot.pk}/{slot.code}"
    ).first()
    assert audit is not None
    assert audit.actor == admin
    assert audit.before is None
    assert audit.after["reason"] == "Routine inspection"
    assert audit.after["moved_count"] == 0
    assert audit.after["cancelled_count"] == 0
    assert "starts_at" in audit.after
    assert "ends_at" in audit.after


def test_view_create_staff_records_actor(client, admin):
    """Actor (request.user) must be recorded in AuditLog when create_staff is called via view."""
    client.force_login(admin)
    staff_email = "viewstaff@example.com"

    response = client.post(
        "/accounts/staff/create/",
        {
            "full_name": "View Created Staff",
            "email": staff_email,
            "mobile": "9876543215",
            "password": "ValidPassword2026!",
            "role": User.Role.ATTENDANT,
        },
        follow=True,
    )
    assert response.status_code == 200

    audit = AuditLog.objects.filter(action="staff.created", target=f"user:{staff_email}").first()
    assert audit is not None
    assert audit.actor == admin
    assert audit.before is None
    assert audit.after["role"] == User.Role.ATTENDANT
    assert audit.after["full_name"] == "View Created Staff"


def test_blocking_slot_with_no_bookings_still_logs(slot, admin):
    """Blocking an empty slot still creates a slot.blocked audit entry with zero counts."""
    now = timezone.now()
    starts_at = now + timedelta(hours=2)
    ends_at = now + timedelta(hours=4)

    block = lot_services.block_slot(
        slot=slot,
        starts_at=starts_at,
        ends_at=ends_at,
        reason="Resurfacing bay",
        actor=admin,
    )
    assert block.moved == []
    assert block.cancelled == []

    audit = AuditLog.objects.filter(
        action="slot.blocked", target=f"slot:{slot.lot_id}/{slot.code}"
    ).first()
    assert audit is not None
    assert audit.actor == admin
    assert audit.before is None
    assert audit.after["starts_at"] == starts_at.isoformat()
    assert audit.after["ends_at"] == ends_at.isoformat()
    assert audit.after["reason"] == "Resurfacing bay"
    assert audit.after["moved_count"] == 0
    assert audit.after["cancelled_count"] == 0


def test_each_staff_change_writes_one_row_with_correct_before_after(admin):
    """Each staff change (create, deactivate, reactivate) writes 1 audit row; no-ops write 0."""
    staff_email = "lifecycle@example.com"

    # 1. Staff creation
    created = account_services.create_staff(
        full_name="Lifecycle Staff",
        email=staff_email,
        mobile="9876543216",
        password="ValidPassword2026!",
        role=User.Role.ATTENDANT,
        actor=admin,
    )

    create_audits = AuditLog.objects.filter(action="staff.created", target=f"user:{staff_email}")
    assert create_audits.count() == 1
    create_entry = create_audits.first()
    assert create_entry.actor == admin
    assert create_entry.before is None
    assert create_entry.after == {
        "role": User.Role.ATTENDANT,
        "full_name": "Lifecycle Staff",
    }

    # 2. Deactivation
    account_services.deactivate_staff(admin, created)
    deact_audits = AuditLog.objects.filter(action="staff.deactivated", target=f"user:{created.pk}")
    assert deact_audits.count() == 1
    deact_entry = deact_audits.first()
    assert deact_entry.actor == admin
    assert deact_entry.before == {"is_active": True}
    assert deact_entry.after == {"is_active": False}

    # 3. Repeated deactivation should be a no-op and write NO new audit entries
    account_services.deactivate_staff(admin, created)
    assert deact_audits.count() == 1

    # 4. Reactivation
    account_services.reactivate_staff(admin, created)
    react_audits = AuditLog.objects.filter(action="staff.reactivated", target=f"user:{created.pk}")
    assert react_audits.count() == 1
    react_entry = react_audits.first()
    assert react_entry.actor == admin
    assert react_entry.before == {"is_active": False}
    assert react_entry.after == {"is_active": True}

    # 5. Repeated reactivation should be a no-op and write NO new audit entries
    account_services.reactivate_staff(admin, created)
    assert react_audits.count() == 1


def test_no_password_or_hash_appears_in_any_audit_row(admin):
    """SEC-09: No screen or log shall show a password, password hash or reset token."""
    secret_pass = "P@ssw0rd_SuperSecret_999!"
    staff = account_services.create_staff(
        full_name="Secret Security Check",
        email="securitycheck@example.com",
        mobile="9876543217",
        password=secret_pass,
        role=User.Role.ATTENDANT,
        actor=admin,
    )

    # Deactivate and reactivate to have a full set of audit rows
    account_services.deactivate_staff(admin, staff)
    account_services.reactivate_staff(admin, staff)

    staff_hash = staff.password
    assert staff_hash.startswith(("pbkdf2_", "argon2"))

    for entry in AuditLog.objects.all():
        serialized = json.dumps(
            {
                "target": entry.target,
                "action": entry.action,
                "before": entry.before,
                "after": entry.after,
            }
        )
        assert secret_pass not in serialized, f"Plaintext password leaked in audit log {entry.pk}"
        assert staff_hash not in serialized, f"Password hash leaked in audit log {entry.pk}"
        if entry.after:
            assert "password" not in entry.after
            assert "hash" not in entry.after
        if entry.before:
            assert "password" not in entry.before
            assert "hash" not in entry.before
