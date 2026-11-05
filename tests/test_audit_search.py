"""FR-RPT-04 / TC-19: Lot Administrators search the audit log by actor, action and date."""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from unittest import mock

import pytest
from django.utils import timezone

from vps.accounts.models import User
from vps.audit.models import AuditLog
from vps.audit.services import log_action
from vps.lots import services as lot_services
from vps.lots.models import Lot
from vps.reports import services

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin():
    return User.objects.create_user(email="admin@example.com", role=User.Role.ADMIN)


def logged_at(day, **fields):
    moment = timezone.make_aware(datetime.combine(day, time(12)))
    with mock.patch("django.utils.timezone.now", return_value=moment):
        return log_action(**fields)


def test_tc19_tariff_change_is_found_with_old_and_new_value(client, admin):
    lot = Lot.objects.create(name="L", address="A", opens_at=time(6), closes_at=time(23))
    today = timezone.localdate()
    lot_services.create_tariff(
        lot=lot,
        slot_type="Standard",
        hourly_rate_inr=Decimal("40.00"),
        effective_from=today,
        actor=admin,
    )
    lot_services.create_tariff(
        lot=lot,
        slot_type="Standard",
        hourly_rate_inr=Decimal("50.00"),
        effective_from=today + timedelta(days=1),
        actor=admin,
    )
    client.force_login(admin)
    response = client.get("/reports/audit/", {"action": "tariff"})
    entries = list(response.context["page"])
    assert response.status_code == 200
    assert len(entries) == 2
    newest = entries[0]
    assert newest.actor == admin
    assert newest.before["hourly_rate_inr"] == "40.00"
    assert newest.after["hourly_rate_inr"] == "50.00"
    assert entries[1].before is None
    html = response.content.decode()
    assert "tariff.change" in html and "admin@example.com" in html

    # The log is read-only through the application.
    assert client.delete("/reports/audit/").status_code == 405
    assert client.post("/reports/audit/", {"id": newest.pk}).status_code == 405
    assert AuditLog.objects.count() == 2


def test_filters_by_actor_action_and_inclusive_dates(admin):
    other = User.objects.create_user(email="gate@example.com", role=User.Role.ATTENDANT)
    logged_at(date(2026, 1, 1), actor=admin, action="slot.blocked", target="a")
    logged_at(date(2026, 1, 5), actor=other, action="payment.recorded", target="b")
    logged_at(date(2026, 1, 9), actor=admin, action="staff.created", target="c")
    logged_at(date(2026, 1, 9), actor=None, action="auth.failed", target="d")

    def targets(**query):
        return [e.target for e in services.search_audit(**query)]

    assert targets() == ["d", "c", "b", "a"]
    assert targets(actor="ADMIN@") == ["c", "a"]
    assert targets(action="payment") == ["b"]
    assert targets(start_date=date(2026, 1, 5), end_date=date(2026, 1, 9)) == ["d", "c", "b"]
    assert targets(end_date=date(2026, 1, 1)) == ["a"]
    assert targets(actor="admin", action="staff", start_date=date(2026, 1, 9)) == ["c"]


def test_page_lists_newest_first_and_paginates(client, admin):
    for i in range(55):
        log_action(actor=admin, action="slot.blocked", target=f"t{i}")
    client.force_login(admin)
    first = client.get("/reports/audit/")
    assert first.context["page"].paginator.count == 55
    assert len(first.context["page"]) == 50
    second = client.get("/reports/audit/", {"action": "slot", "page": 2})
    assert len(second.context["page"]) == 5
    assert "action=slot&amp;page=1" in second.content.decode()


def test_bad_date_range_is_refused(client, admin):
    client.force_login(admin)
    response = client.get("/reports/audit/", {"start_date": "2026-01-09", "end_date": "2026-01-01"})
    assert response.context["page"] is None
    assert response.context["form"].errors["end_date"]


@pytest.mark.parametrize("role", [User.Role.DRIVER, User.Role.ATTENDANT])
def test_audit_search_is_admin_only(client, role):
    client.force_login(User.objects.create_user(email="x@example.com", role=role))
    assert client.get("/reports/audit/").status_code == 403
