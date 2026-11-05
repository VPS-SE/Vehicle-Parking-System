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
def admin_context(browser: Browser, base_url: str):
    """Session-scoped context for Lot Administrator to avoid rate limiting."""
    context = browser.new_context()
    page = context.new_page()
    page.goto(f"{base_url}/accounts/login/")
    page.fill("#email", ADMIN_EMAIL)
    page.fill("#password", PASSWORD)
    page.click("button[type='submit']")
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
    page.wait_for_load_state("networkidle")
    yield context
    context.close()
