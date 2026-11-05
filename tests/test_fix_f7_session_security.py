import runpy
from datetime import timedelta
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.sessions.models import Session
from django.test import override_settings
from django.utils import timezone

from vps.accounts.models import User

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PASSWORD = "ValidPassword2026!"


def load_production_settings():
    return runpy.run_path(str(PROJECT_ROOT / "vps" / "settings.py"))


def test_session_and_cookie_settings_values_development():
    """Verify session and cookie settings loaded in development/test."""
    assert settings.SESSION_COOKIE_AGE == 1800
    assert settings.SESSION_SAVE_EVERY_REQUEST is True
    assert settings.SESSION_COOKIE_HTTPONLY is True
    assert settings.SESSION_COOKIE_SAMESITE == "Lax"


def test_session_and_cookie_settings_values_production(monkeypatch):
    """Verify production settings (DEBUG=False) enforce all SEC-04/SEC-08 flags."""
    monkeypatch.delenv("DJANGO_DEBUG", raising=False)
    prod = load_production_settings()
    assert prod["DEBUG"] is False
    assert prod["SESSION_COOKIE_AGE"] == 1800
    assert prod["SESSION_SAVE_EVERY_REQUEST"] is True
    assert prod["SESSION_COOKIE_HTTPONLY"] is True
    assert prod["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert prod["SESSION_COOKIE_SECURE"] is True
    assert prod["CSRF_COOKIE_SECURE"] is True
    assert prod["SECURE_SSL_REDIRECT"] is True
    assert prod["SECURE_HSTS_SECONDS"] == 31536000
    assert prod["SECURE_REDIRECT_EXEMPT"] == [r"^healthz$"]


@pytest.mark.django_db
def test_session_key_rotated_at_sign_in(client):
    """SEC-08: Session identifier shall be rotated at sign-in."""
    user = User.objects.create_user(email="driver@example.com", password=PASSWORD)

    # Establish an initial anonymous session
    session = client.session
    session["initial_marker"] = "pre-login"
    session.save()
    anon_session_key = client.session.session_key
    assert anon_session_key is not None

    # Sign in as user
    response = client.post("/accounts/login/", {"email": user.email, "password": PASSWORD})
    assert response.status_code == 302

    # The session key must rotate to a new, non-empty identifier
    auth_session_key = client.session.session_key
    assert auth_session_key is not None
    assert auth_session_key != anon_session_key
    # Session state preserved and user authenticated
    assert client.session.get("initial_marker") == "pre-login"
    assert client.session.get("_auth_user_id") == str(user.pk)


@pytest.mark.django_db
def test_session_expiry_is_1800s_and_pushed_forward_on_later_request(client, monkeypatch):
    """SEC-08: 30-minute idle sliding expiration pushed forward on request."""
    user = User.objects.create_user(email="driver@example.com", password=PASSWORD)

    start_time = timezone.now()
    monkeypatch.setattr("django.utils.timezone.now", lambda: start_time)

    response = client.post("/accounts/login/", {"email": user.email, "password": PASSWORD})
    assert response.status_code == 302

    session_cookie = response.cookies.get(settings.SESSION_COOKIE_NAME)
    assert session_cookie is not None
    assert session_cookie["max-age"] == 1800

    session_key = client.session.session_key
    db_session = Session.objects.get(session_key=session_key)
    initial_expire = db_session.expire_date
    expected_initial = start_time + timedelta(seconds=1800)
    assert abs((initial_expire - expected_initial).total_seconds()) < 5

    # Simulate 10 minutes (600s) passing before user makes another request
    later_time = start_time + timedelta(seconds=600)
    monkeypatch.setattr("django.utils.timezone.now", lambda: later_time)

    # Make a GET request; SESSION_SAVE_EVERY_REQUEST saves the session
    get_resp = client.get("/vehicles/")
    assert get_resp.status_code == 200

    db_session.refresh_from_db()
    refreshed_expire = db_session.expire_date
    expected_refreshed = later_time + timedelta(seconds=1800)
    assert refreshed_expire > initial_expire
    assert abs((refreshed_expire - expected_refreshed).total_seconds()) < 5


@pytest.mark.django_db
def test_idle_session_expires_after_30_minutes(client, monkeypatch):
    """SEC-08: Session ends after 30 minutes without activity."""
    user = User.objects.create_user(email="driver@example.com", password=PASSWORD)

    start_time = timezone.now()
    monkeypatch.setattr("django.utils.timezone.now", lambda: start_time)

    client.post("/accounts/login/", {"email": user.email, "password": PASSWORD})
    assert client.get("/").url == "/vehicles/"

    # Stay idle for 31 minutes (1860s)
    idle_time = start_time + timedelta(seconds=1860)
    monkeypatch.setattr("django.utils.timezone.now", lambda: idle_time)

    # Subsequent request should find the session expired and redirect to login
    response = client.get("/")
    assert response.status_code == 302
    assert response.url == "/accounts/login/"


@pytest.mark.django_db
@override_settings(
    DEBUG=False,
    SESSION_COOKIE_SECURE=True,
    CSRF_COOKIE_SECURE=True,
    SECURE_SSL_REDIRECT=False,
)
def test_cookies_marked_secure_with_debug_false(client):
    """SEC-04: Session and CSRF cookies are marked Secure in deployment."""
    user = User.objects.create_user(email="driver@example.com", password=PASSWORD)

    # Access login page over HTTPS
    get_resp = client.get("/accounts/login/", secure=True)
    csrf_cookie = get_resp.cookies.get(settings.CSRF_COOKIE_NAME)
    assert csrf_cookie is not None
    assert csrf_cookie["secure"] is True

    # Sign in over HTTPS
    post_resp = client.post(
        "/accounts/login/",
        {"email": user.email, "password": PASSWORD},
        secure=True,
    )
    session_cookie = post_resp.cookies.get(settings.SESSION_COOKIE_NAME)
    assert session_cookie is not None
    assert session_cookie["secure"] is True
    assert session_cookie["httponly"] is True
    assert session_cookie["samesite"] == "Lax"
