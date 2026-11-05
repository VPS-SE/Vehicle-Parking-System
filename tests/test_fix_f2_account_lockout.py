"""Tests for F2: Account lockout and IP rate limiting (SEC-02, TC-03)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from vps.accounts import services as account_services
from vps.accounts.models import User
from vps.audit.models import AuditLog

pytestmark = pytest.mark.django_db


@pytest.fixture
def driver():
    return account_services.register_driver(
        full_name="Asha Rao",
        email="asha@example.com",
        mobile="9876543210",
        password="CorrectPassword2026!",
    )


def test_failures_older_than_15_minutes_do_not_count_toward_five(client, driver):
    """SEC-02: failures older than 15 minutes expire and do not count toward the 5."""
    driver.failed_attempts = 4
    driver.first_failed_at = timezone.now() - timedelta(minutes=16)
    driver.save(update_fields=["failed_attempts", "first_failed_at"])

    # 5th attempt in total, but first 4 occurred > 15 minutes ago
    resp = client.post(
        "/accounts/login/",
        {"email": driver.email, "password": "WrongPassword!"},
    )
    assert resp.status_code == 200

    driver.refresh_from_db()
    assert driver.locked_until is None
    assert driver.failed_attempts == 1
    assert driver.first_failed_at is not None
    assert timezone.now() - driver.first_failed_at < timedelta(minutes=1)


def test_lock_expires_after_15_minutes_and_correct_password_works(client, driver):
    """SEC-02: after 15 minutes lockout expires; correct password signs in and resets counter."""
    past_time = timezone.now() - timedelta(minutes=16)
    driver.failed_attempts = 5
    driver.first_failed_at = past_time
    driver.locked_until = timezone.now() - timedelta(seconds=1)
    driver.save(update_fields=["failed_attempts", "first_failed_at", "locked_until"])

    resp = client.post(
        "/accounts/login/",
        {"email": driver.email, "password": "CorrectPassword2026!"},
    )
    assert resp.status_code == 302
    assert resp.url == "/"

    driver.refresh_from_db()
    assert driver.failed_attempts == 0
    assert driver.first_failed_at is None
    assert driver.locked_until is None


def test_success_before_fifth_failure_resets_counter(client, driver):
    """SEC-02: successful sign-in before the 5th failure resets the counter to 0."""
    for _ in range(4):
        resp = client.post(
            "/accounts/login/",
            {"email": driver.email, "password": "WrongPassword!"},
        )
        assert resp.status_code == 200

    driver.refresh_from_db()
    assert driver.failed_attempts == 4
    assert driver.locked_until is None

    # Sign in successfully on 5th attempt
    resp_success = client.post(
        "/accounts/login/",
        {"email": driver.email, "password": "CorrectPassword2026!"},
    )
    assert resp_success.status_code == 302

    driver.refresh_from_db()
    assert driver.failed_attempts == 0
    assert driver.first_failed_at is None
    assert driver.locked_until is None

    # A subsequent failure starts back from 1
    client.post("/accounts/logout/")
    resp_fail = client.post(
        "/accounts/login/",
        {"email": driver.email, "password": "WrongPassword!"},
    )
    assert resp_fail.status_code == 200
    driver.refresh_from_db()
    assert driver.failed_attempts == 1


def test_lockout_423_page_shows_unlock_time(client, driver):
    """TC-03: attempt 6 returns HTTP 423 with the unlock time shown in the error alert."""
    for _ in range(5):
        resp = client.post(
            "/accounts/login/",
            {"email": driver.email, "password": "WrongPassword!"},
        )
        assert resp.status_code == 200

    driver.refresh_from_db()
    assert driver.locked_until is not None
    local_unlock = timezone.localtime(driver.locked_until)
    unlock_time = local_unlock.strftime("%H:%M")

    # 6th attempt with correct password
    resp6 = client.post(
        "/accounts/login/",
        {"email": driver.email, "password": "CorrectPassword2026!"},
    )
    assert resp6.status_code == 423
    body = resp6.content.decode()
    assert unlock_time in body
    assert "Account locked until" in body
    assert resp6.context["unlock_time"] == unlock_time
    assert resp6.context["locked_until"] == driver.locked_until


def test_five_failed_sign_ins_record_five_audit_rows(client, driver):
    """TC-03: 5 failed sign-ins create 5 auth.failed audit entries; locked attempt adds none."""
    for _ in range(5):
        client.post(
            "/accounts/login/",
            {"email": driver.email, "password": "WrongPassword!"},
        )

    # Attempt 6 while locked
    resp6 = client.post(
        "/accounts/login/",
        {"email": driver.email, "password": "CorrectPassword2026!"},
    )
    assert resp6.status_code == 423

    failed_logs = AuditLog.objects.filter(action="auth.failed")
    assert failed_logs.count() == 5
    for entry in failed_logs:
        assert entry.target == f"user:{driver.pk}"
        assert entry.after.get("email") == driver.email
        assert "password" not in (entry.before or {})
        assert "password" not in (entry.after or {})

    # auth.locked is also recorded when lockout triggered
    locked_logs = AuditLog.objects.filter(action="auth.locked")
    assert locked_logs.count() == 1
    assert locked_logs.first().target == f"user:{driver.pk}"


def test_unknown_email_gives_200_not_423(client):
    """SEC-02: unknown e-mails always return 200 with generic error and do not leak user status."""
    for _ in range(6):
        resp = client.post(
            "/accounts/login/",
            {"email": "unknown-user@example.com", "password": "AnyPassword123!"},
        )
        assert resp.status_code == 200
        assert resp.context["login_error"] == "Invalid e-mail or password"
        assert not User.objects.filter(email="unknown-user@example.com").exists()

    logs = AuditLog.objects.filter(action="auth.failed", target="email:unknown-user@example.com")
    assert logs.count() == 6


def test_ip_rate_limiting_eleventh_attempt_gets_429(client):
    """SEC-02: sign-in attempts limited to 10 per minute per IP address; 11th gets 429."""
    ip = "198.51.100.42"

    for i in range(10):
        resp = client.post(
            "/accounts/login/",
            {"email": f"user{i}@example.com", "password": "password"},
            REMOTE_ADDR=ip,
        )
        assert resp.status_code == 200

    # 11th attempt from same IP within 1 minute gets 429
    resp11 = client.post(
        "/accounts/login/",
        {"email": "user11@example.com", "password": "password"},
        REMOTE_ADDR=ip,
    )
    assert resp11.status_code == 429

    # Another IP address is not rate-limited
    resp_other = client.post(
        "/accounts/login/",
        {"email": "user12@example.com", "password": "password"},
        REMOTE_ADDR="198.51.100.99",
    )
    assert resp_other.status_code == 200


def test_wrong_password_on_expired_lockout_restarts_counter(client, driver):
    """SEC-02: after lockout expires, a new failed attempt restarts counter at 1."""
    driver.failed_attempts = 5
    driver.first_failed_at = timezone.now() - timedelta(minutes=20)
    driver.locked_until = timezone.now() - timedelta(seconds=1)
    driver.save(update_fields=["failed_attempts", "first_failed_at", "locked_until"])

    resp = client.post(
        "/accounts/login/",
        {"email": driver.email, "password": "WrongPassword!"},
    )
    assert resp.status_code == 200

    driver.refresh_from_db()
    assert driver.failed_attempts == 1
    assert driver.locked_until is None
    assert timezone.now() - driver.first_failed_at < timedelta(minutes=1)
