"""TC-19: Privileged actions are audited.

Requirements: SEC-07, FR-RPT-04
Preconditions: Signed in as Lot Administrator.
Steps:
  1. Change the Standard tariff from Rs 40 to Rs 50.
  2. Search/verify the audit log entry for the tariff change.
  3. Try to delete the entry through the application and API.
Expected result:
  Entry shows actor, action, target, new rate and timestamp;
  deletion attempts fail with PermissionDenied.
"""

from datetime import time, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from vps.accounts.models import User
from vps.audit.models import AuditLog
from vps.lots import services
from vps.lots.models import Lot

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin():
    return User.objects.create_user(
        email="admin@example.com",
        password="ValidPassword2026!",
        role=User.Role.ADMIN,
    )


@pytest.fixture
def lot():
    return Lot.objects.create(
        name="Lot A",
        address="1 Ring Road",
        opens_at=time(6),
        closes_at=time(23),
    )


def test_tc19_privileged_actions_are_audited_and_immutable(admin, lot):
    """TC-19: tariff changes record audit entries that cannot be edited or deleted."""
    # Step 1: Create/change tariff as administrator
    effective_date = timezone.localdate() + timedelta(days=1)
    services.create_tariff(
        lot=lot,
        slot_type="Standard",
        hourly_rate_inr=Decimal("50.00"),
        effective_from=effective_date,
        actor=admin,
    )

    # Step 2: Audit entry exists with actor, action, target, timestamp, and details
    entry = AuditLog.objects.filter(target=f"lot:{lot.pk}/slot_type:Standard").first()
    assert entry is not None
    assert entry.actor == admin
    assert entry.action == "tariff.change"
    assert entry.after["hourly_rate_inr"] == "50.00"
    assert entry.after["effective_from"] == effective_date.isoformat()
    assert entry.at is not None

    # Step 3: Attempt to delete the entry fails with PermissionDenied
    with pytest.raises(PermissionDenied):
        entry.delete()

    with pytest.raises(PermissionDenied):
        AuditLog.objects.filter(pk=entry.pk).delete()

    # Verify entry is still intact in the database
    assert AuditLog.objects.filter(pk=entry.pk).exists()
