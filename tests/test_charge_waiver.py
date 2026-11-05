"""BR-09: a Lot Administrator may waive a charge only with a written reason, which is audited."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from vps.accounts.models import User
from vps.audit.models import AuditLog
from vps.billing import services
from vps.billing.models import Charge, Waiver
from vps.factories import (
    make_charge,
    make_driver,
    make_lot,
    make_payment,
    make_reservation,
    make_staff,
)
from vps.reports.services import revenue_report
from vps.reservations.models import Reservation
from vps.reservations.services import check_booking_limits

pytestmark = pytest.mark.django_db
REASON = "Barrier fault at exit gate kept the driver waiting 40 minutes."


@pytest.fixture
def admin():
    return make_staff(role=User.Role.ADMIN)


@pytest.fixture
def charge():
    driver = make_driver()
    slot = make_lot().slots.get()
    start = timezone.now() - timedelta(days=1)
    reservation = make_reservation(
        driver, slot, start, status=Reservation.Status.EXPIRED, booking_ref="VPS-261105-0042"
    )
    return make_charge(reservation, amount="50.00", kind=Charge.Kind.NO_SHOW)


def test_waiver_records_reason_and_audit_entry(admin, charge):
    waiver = services.waive_charge(admin, charge, f"  {REASON}  ")

    assert waiver.reason == REASON
    assert waiver.waived_by == admin
    entry = AuditLog.objects.get(action="charge.waived")
    assert entry.actor == admin
    assert entry.target == f"charge:{charge.pk}"
    assert entry.before == {"amount_inr": "50.00", "status": "unpaid"}
    assert entry.after == {
        "reservation": "VPS-261105-0042",
        "kind": "NoShow",
        "amount_inr": "50.00",
        "status": "waived",
        "reason": REASON,
    }


@pytest.mark.parametrize("reason", ["", "   ", None])
def test_waiver_needs_written_reason(admin, charge, reason):
    with pytest.raises(ValidationError) as error:
        services.waive_charge(admin, charge, reason)
    assert error.value.message_dict == {"reason": [services.REASON_REQUIRED]}
    assert not Waiver.objects.exists()
    assert not AuditLog.objects.filter(action="charge.waived").exists()


def test_waiver_reason_has_length_limit(admin, charge):
    with pytest.raises(ValidationError) as error:
        services.waive_charge(admin, charge, "x" * (services.REASON_MAX_LENGTH + 1))
    assert "reason" in error.value.message_dict
    services.waive_charge(admin, charge, "x" * services.REASON_MAX_LENGTH)


@pytest.mark.parametrize("role", [User.Role.ATTENDANT, User.Role.DRIVER])
def test_only_admins_may_waive(charge, role):
    with pytest.raises(ValidationError):
        services.waive_charge(make_staff(role=role), charge, REASON)
    assert not Waiver.objects.exists()


def test_paid_charge_cannot_be_waived(admin, charge):
    make_payment(charge)
    with pytest.raises(ValidationError) as error:
        services.waive_charge(admin, charge, REASON)
    assert error.value.message_dict == {"__all__": [services.ALREADY_PAID]}


def test_charge_cannot_be_waived_twice(admin, charge):
    services.waive_charge(admin, charge, REASON)
    with pytest.raises(ValidationError) as error:
        services.waive_charge(admin, charge, "Second attempt")
    assert error.value.message_dict == {"__all__": [services.ALREADY_WAIVED]}
    assert AuditLog.objects.filter(action="charge.waived").count() == 1


def test_waived_charge_cannot_be_paid(admin, charge):
    services.waive_charge(admin, charge, REASON)
    with pytest.raises(ValidationError) as error:
        services.record_payment(make_staff(), charge, "Cash")
    assert error.value.message_dict == {"__all__": [services.ALREADY_WAIVED]}


def test_database_rejects_blank_reason(admin, charge):
    with pytest.raises(IntegrityError), transaction.atomic():
        Waiver.objects.create(charge=charge, reason="  ", waived_by=admin)


def test_waived_charge_no_longer_owed(admin, charge):
    driver = charge.reservation.driver
    other = make_charge(charge.reservation, amount="30.00", kind=Charge.Kind.LATE_CANCEL)
    assert services.unpaid_total(driver) == Decimal("80.00")

    services.waive_charge(admin, charge, REASON)

    assert services.unpaid_total(driver) == Decimal("30.00")
    assert list(services.unpaid_charges(charge.reservation.booking_ref)) == [other]
    with pytest.raises(ValidationError):  # BR-04 still applies to the other charge
        check_booking_limits(driver)
    services.waive_charge(admin, other, REASON)
    check_booking_limits(driver)  # nothing outstanding, so booking is allowed again


def test_revenue_report_does_not_count_waived_charge_as_unpaid(admin, charge):
    day = timezone.localdate(charge.reservation.period.lower)
    (row,) = revenue_report(day, day)
    assert row["unpaid_inr"] == Decimal("50.00")

    services.waive_charge(admin, charge, REASON)

    (row,) = revenue_report(day, day)
    assert row["late_noshow_inr"] == Decimal("50.00")
    assert row["unpaid_inr"] == Decimal("0.00")


# Views


def test_admin_waives_charge_through_page(client, admin, charge):
    client.force_login(admin)
    ref = charge.reservation.booking_ref

    page = client.get("/billing/waivers/", {"q": ref})
    assert page.status_code == 200
    assert ref in page.content.decode()

    response = client.post(f"/billing/waivers/{charge.pk}/", {"reason": REASON, "q": ref})
    assert response.status_code == 302
    assert response["Location"] == f"/billing/waivers/?q={ref}"
    page = client.get(response["Location"])
    body = page.content.decode()
    assert "Waived the Rs 50.00 no-show charge on VPS-261105-0042." in body
    assert "No unpaid charges found." in body
    assert REASON in body  # listed under recent waivers
    assert Waiver.objects.get().charge == charge


def test_page_reports_missing_reason(client, admin, charge):
    client.force_login(admin)
    response = client.post(f"/billing/waivers/{charge.pk}/", {"reason": ""}, follow=True)
    assert services.REASON_REQUIRED in response.content.decode()
    assert not Waiver.objects.exists()


@pytest.mark.parametrize("role", [User.Role.ATTENDANT, User.Role.DRIVER])
def test_page_is_admin_only(client, charge, role):
    client.force_login(make_staff(role=role))
    assert client.get("/billing/waivers/").status_code == 403
    assert client.post(f"/billing/waivers/{charge.pk}/", {"reason": REASON}).status_code == 403
    assert not Waiver.objects.exists()


def test_page_requires_sign_in(client, charge):
    response = client.get("/billing/waivers/")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


def test_waive_rejects_get_and_unknown_charge(client, admin, charge):
    client.force_login(admin)
    assert client.get(f"/billing/waivers/{charge.pk}/").status_code == 405
    assert client.post("/billing/waivers/999999/", {"reason": REASON}).status_code == 404


def test_driver_history_shows_waived(client, admin, charge):
    services.waive_charge(admin, charge, REASON)
    client.force_login(charge.reservation.driver)
    body = client.get("/reservations/history/").content.decode()
    assert "(Waived)" in body


def test_admin_nav_links_to_waivers(client, admin):
    client.force_login(admin)
    assert 'href="/billing/waivers/"' in client.get("/reports/audit/").content.decode()
