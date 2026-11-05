"""Tests for finding F3: Lot Administrators may correct entry times (SRS Table 5).

SRS Appendix B.3 Table 5:
- Gate Attendants and Lot Administrators may 'Correct entry or exit time'.
- Normal gate operations (check-in, ordinary check-out, walk-ins) remain restricted
  to Gate Attendants only.
"""

from datetime import datetime, time, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db.backends.postgresql.psycopg_any import DateTimeTZRange
from django.utils import timezone

from vps.accounts.models import User
from vps.audit.models import AuditLog
from vps.gate import services as gate_services
from vps.lots.models import Lot, Slot, Tariff
from vps.reservations.models import Reservation

pytestmark = pytest.mark.django_db
LOCAL = "%Y-%m-%dT%H:%M"


@pytest.fixture
def lot():
    lot = Lot.objects.create(
        name="Lot F3",
        address="100 Main Road",
        opens_at=time(6),
        closes_at=time(23),
    )
    return lot


@pytest.fixture
def slot(lot):
    return Slot.objects.create(lot=lot, code="F3-01", distance_rank=1)


@pytest.fixture
def tariff(lot):
    return Tariff.objects.create(
        lot=lot,
        slot_type="Standard",
        hourly_rate_inr="50.00",
        effective_from=timezone.now().date() - timedelta(days=5),
    )


@pytest.fixture
def admin_user():
    return User.objects.create_user(
        email="admin_f3@example.com",
        password="ValidPassword2026!",
        role=User.Role.ADMIN,
    )


@pytest.fixture
def attendant_user():
    return User.objects.create_user(
        email="attendant_f3@example.com",
        password="ValidPassword2026!",
        role=User.Role.ATTENDANT,
    )


@pytest.fixture
def driver_user():
    return User.objects.create_user(
        email="driver_f3@example.com",
        password="ValidPassword2026!",
        role=User.Role.DRIVER,
    )


@pytest.fixture
def active_booking(slot, tariff):
    now = timezone.now()
    entry_time = now - timedelta(hours=3)
    return Reservation.objects.create(
        booking_ref="VPS-261105-0001",
        vehicle_reg_no="KA01F31234",
        slot=slot,
        period=DateTimeTZRange(entry_time, entry_time + timedelta(hours=6)),
        status=Reservation.Status.ACTIVE,
        entry_time=entry_time,
    )


def test_admin_can_get_and_post_correction_page_audited(client, admin_user, active_booking):
    """Admin can GET and POST /gate/correct-entry/, and the audit row names the admin."""
    client.force_login(admin_user)

    # GET correction page
    get_resp = client.get("/gate/correct-entry/")
    assert get_resp.status_code == 200
    assert "Correct entry time" in get_resp.content.decode()

    # POST correction page
    paper_entry = timezone.localtime(active_booking.entry_time - timedelta(minutes=30))
    post_resp = client.post(
        "/gate/correct-entry/",
        {
            "query": active_booking.booking_ref,
            "entry_time": paper_entry.strftime(LOCAL),
            "reason": "Gate barrier was offline during entry",
        },
    )
    assert post_resp.status_code == 302
    assert post_resp.url == "/gate/correct-entry/"

    active_booking.refresh_from_db()
    expected_entry = paper_entry.replace(second=0, microsecond=0)
    assert active_booking.entry_time == expected_entry

    log = AuditLog.objects.get(
        action="reservation.entry_corrected",
        target=f"reservation:{active_booking.booking_ref}",
    )
    assert log.actor == admin_user
    assert datetime.fromisoformat(log.after["entry_time"]) == expected_entry
    assert log.after["reason"] == "Gate barrier was offline during entry"


def test_driver_denied_access_to_time_corrections(
    client, driver_user, active_booking, attendant_user
):
    """Driver gets 403 on correction endpoints and ValidationError from services."""
    client.force_login(driver_user)
    paper_time = timezone.localtime() - timedelta(hours=1)

    # Driver cannot GET or POST correct-entry
    assert client.get("/gate/correct-entry/").status_code == 403
    assert (
        client.post(
            "/gate/correct-entry/",
            {
                "query": active_booking.booking_ref,
                "entry_time": paper_time.strftime(LOCAL),
                "reason": "Driver attempt",
            },
        ).status_code
        == 403
    )

    # Driver cannot POST checkout even with exit_time
    assert (
        client.post(
            "/gate/checkout/",
            {
                "query": active_booking.booking_ref,
                "exit_time": paper_time.strftime(LOCAL),
                "reason": "Driver attempt",
            },
        ).status_code
        == 403
    )

    # Driver cannot call services directly
    now = timezone.now()
    with pytest.raises(ValidationError):
        gate_services.correct_entry_time(
            attendant=driver_user,
            query=active_booking.booking_ref,
            entry_time=now - timedelta(hours=2),
            reason="Driver attempt",
            now=now,
        )

    with pytest.raises(ValidationError):
        gate_services.checkout_vehicle(
            query=active_booking.booking_ref,
            attendant=driver_user,
            now=now,
            exit_time=now - timedelta(hours=1),
            reason="Driver attempt",
        )


def test_admin_cannot_use_ordinary_gate_operations(client, admin_user, active_booking, lot, slot):
    """Admin cannot use ordinary check-in, check-out or walk-ins (views return 403, services raise)."""
    client.force_login(admin_user)

    # Ordinary check-out page
    assert client.get("/gate/checkout/").status_code == 403
    # Ordinary check-out POST (without exit_time)
    assert client.post("/gate/checkout/", {"query": active_booking.booking_ref}).status_code == 403

    # Gate console dashboard and endpoints
    assert client.get("/gate/").status_code == 403
    assert (
        client.post("/gate/check-in/", {"reference": active_booking.booking_ref}).status_code == 403
    )
    assert (
        client.post(
            "/gate/dashboard-checkout/", {"reference": active_booking.booking_ref}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/gate/dashboard-walk-in/",
            {"lot": lot.pk, "registration_no": "KA01AB9999", "vehicle_type": "Car"},
        ).status_code
        == 403
    )

    # Walk-in page
    assert client.get("/gate/walk-in/").status_code == 403
    assert (
        client.post(
            "/gate/walk-in/",
            {"lot": lot.pk, "registration_no": "KA01AB9999", "vehicle_type": "Car"},
        ).status_code
        == 403
    )

    # Service layer: ordinary check-out refused for admin
    with pytest.raises(ValidationError) as exc:
        gate_services.checkout_vehicle(active_booking.booking_ref, attendant=admin_user)
    assert "Only Gate Attendants may check out vehicles." in str(exc.value)

    # Service layer: walk-in refused for admin
    with pytest.raises(ValidationError) as exc:
        gate_services.register_walk_in(
            attendant=admin_user,
            lot=lot,
            registration_no="KA01AB9999",
            vehicle_type="Car",
        )
    assert "Only Gate Attendants may register walk-in vehicles." in str(exc.value)

    # Service layer: check-in refused for admin
    slot2 = Slot.objects.create(lot=lot, code="F3-02", distance_rank=2)
    reserved = Reservation.objects.create(
        booking_ref="VPS-261105-0002",
        vehicle_reg_no="KA02CD5678",
        slot=slot2,
        period=DateTimeTZRange(timezone.now(), timezone.now() + timedelta(hours=2)),
        status=Reservation.Status.RESERVED,
    )
    with pytest.raises(ValidationError) as exc:
        gate_services.check_in_vehicle(reserved.booking_ref, attendant=admin_user)
    assert "Only Gate Attendants may check in vehicles." in str(exc.value)


def test_attendant_behaviour_unchanged(client, attendant_user, active_booking):
    """Gate Attendant can still perform entry corrections, ordinary check-out and outage check-out."""
    client.force_login(attendant_user)

    # Attendant can GET and POST correct-entry
    assert client.get("/gate/correct-entry/").status_code == 200
    paper_entry = timezone.localtime(active_booking.entry_time - timedelta(minutes=15))
    resp_entry = client.post(
        "/gate/correct-entry/",
        {
            "query": active_booking.booking_ref,
            "entry_time": paper_entry.strftime(LOCAL),
            "reason": "Attendant outage correction",
        },
    )
    assert resp_entry.status_code == 302
    assert resp_entry.url == "/gate/correct-entry/"

    log_entry = AuditLog.objects.get(
        action="reservation.entry_corrected",
        target=f"reservation:{active_booking.booking_ref}",
    )
    assert log_entry.actor == attendant_user

    # Attendant can GET and POST ordinary check-out
    assert client.get("/gate/checkout/").status_code == 200
    resp_checkout = client.post(
        "/gate/checkout/",
        {"query": active_booking.booking_ref},
    )
    assert resp_checkout.status_code == 302
    assert f"/gate/receipt/{active_booking.booking_ref}/" in resp_checkout.url

    active_booking.refresh_from_db()
    assert active_booking.status == Reservation.Status.COMPLETED

    log_checkout = AuditLog.objects.get(
        action="reservation.checked_out",
        target=f"reservation:{active_booking.booking_ref}",
    )
    assert log_checkout.actor == attendant_user
    assert "corrected_from_paper" not in log_checkout.after


def test_nav_link_visible_only_to_correct_times_users(
    client, admin_user, attendant_user, driver_user
):
    """Correct entry link in templates/base.html visible to Admin and Attendant, not Driver."""
    client.force_login(admin_user)
    admin_resp = client.get("/lots/")
    assert 'href="/gate/correct-entry/"' in admin_resp.content.decode()
    assert "Correct entry" in admin_resp.content.decode()

    client.force_login(attendant_user)
    attendant_resp = client.get("/gate/dashboard-checkout/")  # Any attendant page, or GET /gate/
    attendant_resp = client.get("/gate/")
    assert 'href="/gate/correct-entry/"' in attendant_resp.content.decode()
    assert "Correct entry" in attendant_resp.content.decode()

    client.force_login(driver_user)
    driver_resp = client.get("/vehicles/")
    assert 'href="/gate/correct-entry/"' not in driver_resp.content.decode()
    assert "Correct entry" not in driver_resp.content.decode()
