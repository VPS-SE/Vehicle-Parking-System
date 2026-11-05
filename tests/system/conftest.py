"""Fixtures for system tests against running VPS instance."""

import os

import pytest
from playwright.sync_api import Browser

PASSWORD = "SysTest!2026pass"
ADMIN_EMAIL = "sys.admin@example.com"
GATE_EMAIL = "sys.gate@example.com"
DRIVER_EMAIL = "sys.driver@example.com"


@pytest.fixture(scope="session")
def base_url() -> str:
    return os.environ.get("VPS_BASE_URL", "http://127.0.0.1:8100").rstrip("/")


@pytest.fixture(scope="session")
def http_prod_url() -> str:
    return os.environ.get("VPS_HTTP_PROD_URL", "http://127.0.0.1:8180").rstrip("/")


@pytest.fixture(scope="session")
def tls_url() -> str:
    return os.environ.get("VPS_TLS_URL", "https://127.0.0.1:8443").rstrip("/")


@pytest.fixture(scope="session")
def server_logs_path() -> str:
    return os.environ.get(
        "VPS_SERVER_LOGS",
        "logs",
    )


@pytest.fixture(scope="session")
def driver_context(browser: Browser, base_url: str):
    """Session-scoped context for Driver (sys.driver) to avoid rate limiting."""
    context = browser.new_context()
    page = context.new_page()
    page.goto(f"{base_url}/accounts/login/")
    page.fill("#email", DRIVER_EMAIL)
    page.fill("#password", PASSWORD)
    page.click("button[type='submit']")
    page.wait_for_url(lambda url: "/accounts/login/" not in url)
    page.wait_for_load_state("networkidle")
    yield context
    context.close()


@pytest.fixture(scope="session")
def admin_context(browser: Browser, base_url: str):
    """Session-scoped context for Lot Administrator to avoid rate limiting."""
    context = browser.new_context()
    page = context.new_page()
    page.goto(f"{base_url}/accounts/login/")
    page.fill("#email", ADMIN_EMAIL)
    page.fill("#password", PASSWORD)
    page.click("button[type='submit']")
    page.wait_for_url(lambda url: "/accounts/login/" not in url)
    page.wait_for_load_state("networkidle")
    yield context
    context.close()


@pytest.fixture(scope="session")
def gate_context(browser: Browser, base_url: str):
    """Session-scoped context for Gate Attendant to avoid rate limiting."""
    context = browser.new_context()
    page = context.new_page()
    page.goto(f"{base_url}/accounts/login/")
    page.fill("#email", GATE_EMAIL)
    page.fill("#password", PASSWORD)
    page.click("button[type='submit']")
    page.wait_for_url(lambda url: "/accounts/login/" not in url)
    page.wait_for_load_state("networkidle")
    yield context
    context.close()
