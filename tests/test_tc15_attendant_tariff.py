"""TC-15: Attendant cannot change a tariff.

Requirements: SEC-03, BR-01
Preconditions: Signed in as Gate Attendant.
Steps:
  1. Send POST /lots/tariffs/save/ directly with a valid CSRF token and a new rate.
Expected result:
  HTTP 403; tariff unchanged; the denied attempt is logged.
"""

from datetime import time, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from vps.accounts.models import User
from vps.lots.models import Lot, Tariff

pytestmark = pytest.mark.django_db


@pytest.fixture
def attendant():
    return User.objects.create_user(
        email="attendant@example.com",
        password="ValidPassword2026!",
        role=User.Role.ATTENDANT,
    )


@pytest.fixture
def lot():
    return Lot.objects.create(
        name="Lot A",
        address="1 Ring Road",
        opens_at=time(6),
        closes_at=time(23),
    )


@pytest.fixture
def existing_tariff(lot):
    return Tariff.objects.create(
        lot=lot,
        slot_type="Standard",
        hourly_rate_inr=Decimal("40.00"),
        effective_from=timezone.localdate(),
    )


def test_tc15_attendant_cannot_change_tariff(client, attendant, lot, existing_tariff, caplog):
    """TC-15: attendant POST to tariff save endpoint returns 403, logs denial, leaves DB unchanged."""
    client.force_login(attendant)
    tomorrow = timezone.localdate() + timedelta(days=1)

    initial_count = Tariff.objects.count()
    initial_rate = Tariff.objects.get(pk=existing_tariff.pk).hourly_rate_inr

    with caplog.at_level("WARNING", logger="vps.security"):
        response = client.post(
            "/lots/tariffs/save/",
            {
                "lot_id": lot.pk,
                "slot_type": "Standard",
                "hourly_rate_inr": "50.00",
                "effective_from": tomorrow.isoformat(),
            },
        )

    # HTTP 403 Forbidden
    assert response.status_code == 403

    # Tariff is unchanged in database
    assert Tariff.objects.count() == initial_count
    existing_tariff.refresh_from_db()
    assert existing_tariff.hourly_rate_inr == initial_rate

    # The denied attempt is logged in the security logger
    assert any("Role access denied" in record.message for record in caplog.records)
    assert any(str(attendant.pk) in record.message for record in caplog.records)
    assert any("/lots/tariffs/save/" in record.message for record in caplog.records)
