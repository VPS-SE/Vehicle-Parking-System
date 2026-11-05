"""System test suite for VPS (Playwright).

Covers STP Section 16 test cases against the live running services:
- TC-01: Register a Driver with valid details
- TC-02: Reject duplicate e-mail at registration (case-insensitive)
- TC-03: Lock account after 5 failed sign-ins (HTTP 423)
- TC-04: Validate vehicle registration number format
- TC-05, TC-06: Slot availability search and booking by driver
- TC-15: Attendant cannot access tariff management
- TC-19: Privileged action auditing (tariff change appears in audit log)
- TC-20, TC-35: Forecast panel displays percentage, band, and 'Estimate'
- TC-28: Live occupancy monitoring dashboard
- TC-34: Occupancy and revenue CSV exports (32-day limit enforcement)
- TC-38: Cookie security flags (HttpOnly and SameSite=Lax)
- TC-42: Responsive mobile booking flow (360px viewport, no horizontal scroll)
"""

import re
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from playwright.sync_api import Browser, expect

PASSWORD = "SysTest!2026pass"


@pytest.fixture(scope="module")
def driver_user(browser: Browser, base_url: str):
    """Register a fresh driver for the driver flow tests."""
    ts = int(time.time() * 1000)
    email = f"systest_driver_{ts}@example.com"
    mobile = f"9{ts % 1000000000:09d}"
    context = browser.new_context()
    page = context.new_page()

    page.goto(f"{base_url}/accounts/register/")
    page.fill("#full_name", "Asha Rao")
    page.fill("#email", email)
    page.fill("#mobile", mobile)
    page.fill("#password", PASSWORD)
    page.click(".registration-form button[type='submit']")
    page.wait_for_load_state("networkidle")
    assert "/vehicles/" in page.url

    yield {
        "email": email,
        "mobile": mobile,
        "ts": ts,
        "context": context,
        "page": page,
    }
    context.close()


def test_tc01_register_driver(driver_user):
    """TC-01: Register a Driver with valid details."""
    page = driver_user["page"]
    assert "/vehicles/" in page.url
    expect(page.locator("h1")).to_contain_text("Add a vehicle")
    expect(page.locator(".balance-card")).to_be_visible()


def test_tc02_duplicate_email(browser: Browser, base_url: str, driver_user):
    """TC-02: Reject duplicate e-mail at registration (any letter case)."""
    context = browser.new_context()
    page = context.new_page()
    page.goto(f"{base_url}/accounts/register/")
    page.fill("#full_name", "Duplicate User")
    page.fill("#email", driver_user["email"].upper())
    page.fill("#mobile", f"9{(driver_user['ts'] + 1) % 1000000000:09d}")
    page.fill("#password", PASSWORD)
    page.click(".registration-form button[type='submit']")
    page.wait_for_load_state("networkidle")

    assert "/vehicles/" not in page.url
    content = page.content()
    assert "already exists" in content
    context.close()


def test_tc04_vehicle_format(driver_user):
    """TC-04: Validate vehicle registration number format."""
    page = driver_user["page"]
    page.goto(page.url)
    page.wait_for_load_state("networkidle")
    ts = driver_user["ts"]

    plate1_input = f"ka 0{ts % 9 + 1} ab 1234"
    plate1_norm = f"KA0{ts % 9 + 1}AB1234"
    plate2 = f"22BH{ts % 9000 + 1000}AA"
    plate3_invalid = f"KA0{ts % 9 + 1}AB12"

    # Step 1: Add vehicle with spaces -> stored as normalized
    page.fill("#registration_no", plate1_input)
    page.select_option("#vehicle_type", "Car")
    page.click(".vehicle-form button[type='submit']")
    page.wait_for_load_state("networkidle")
    content = page.content()
    assert plate1_norm in content
    driver_user["primary_plate"] = plate1_norm

    # Step 2: Add 22BH series vehicle -> accepted
    page.fill("#registration_no", plate2)
    page.select_option("#vehicle_type", "Car")
    page.click(".vehicle-form button[type='submit']")
    page.wait_for_load_state("networkidle")
    assert plate2 in page.content()

    # Step 3: Add invalid format -> rejected
    page.fill("#registration_no", plate3_invalid)
    page.select_option("#vehicle_type", "Car")
    page.click(".vehicle-form button[type='submit']")
    page.wait_for_load_state("networkidle")
    content = page.content()
    assert "valid vehicle registration number" in content or "invalid" in content.lower()

    # Step 4: Duplicate plate -> rejected
    page.fill("#registration_no", plate1_norm)
    page.select_option("#vehicle_type", "Car")
    page.click(".vehicle-form button[type='submit']")
    page.wait_for_load_state("networkidle")
    content = page.content()
    assert "already exists" in content or "registered" in content.lower()


def test_tc05_tc06_tc20_tc35_search_booking_forecast(driver_user, base_url: str):
    """TC-05, TC-06, TC-20, TC-35: Search and booking by driver, forecast panel verification."""
    page = driver_user["page"]
    page.goto(f"{base_url}/reservations/search/")
    page.wait_for_load_state("networkidle")

    # Select lot Demo Central (value "1")
    page.select_option("#lot", value="1")

    # Select vehicle
    plate = driver_user["primary_plate"]
    page.select_option("#vehicle", label=f"{plate} — Car")

    # Time window: tomorrow 10:00 to 12:00 IST
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    start_dt = f"{tomorrow}T10:00"
    end_dt = f"{tomorrow}T12:00"

    page.fill("#start", start_dt)
    page.fill("#end", end_dt)

    page.click(".search-form button[type='submit']")
    page.wait_for_selector("#search-results .search-result", timeout=10000)

    # TC-05: Verify free slots found
    results_text = page.locator("#search-results").inner_text()
    assert "suitable slot" in results_text

    # TC-20 & TC-35: Verify forecast panel
    forecast_panel = page.locator(".forecast-panel")
    expect(forecast_panel).to_be_visible()
    forecast_text = forecast_panel.inner_text()
    # Check percentage, band (Low/Medium/High), and "Estimate"
    assert re.search(r"\d+%", forecast_text) is not None
    assert any(b in forecast_text for b in ("Low", "Medium", "High"))
    assert "Estimate" in forecast_text

    # TC-06: Confirm booking
    page.click(".booking-form button[type='submit']")
    page.wait_for_load_state("networkidle")

    # Verify confirmation page
    assert "/reservations/confirmation/" in page.url
    conf_text = page.content()
    assert "VPS-" in conf_text
    assert "Slot" in conf_text or "slot" in conf_text


def test_tc15_attendant_refused_tariff_page(gate_context, base_url: str):
    """TC-15: An attendant is refused the tariff page (HTTP 403)."""
    page = gate_context.new_page()
    response = page.goto(f"{base_url}/lots/tariffs/")
    assert response.status == 403
    page.close()


def test_tc19_admin_changes_tariff_and_audited(admin_context, base_url: str):
    """TC-19: An admin changes a tariff and finds the change in the audit log."""
    page = admin_context.new_page()
    page.goto(f"{base_url}/lots/tariffs/")
    page.wait_for_load_state("networkidle")

    # Change tariff with unique future date to avoid duplicate constraint
    page.select_option("#tariff-lot", value="1")
    page.select_option("#tariff-slot-type", value="Standard")
    page.fill("#tariff-rate", "55.00")
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    unique_days = 20 + (int(time.time()) % 150)
    effective_date = (now + timedelta(days=unique_days)).strftime("%Y-%m-%d")
    page.fill("#tariff-effective-from", effective_date)
    page.click(".tariff-form button[type='submit']")
    page.wait_for_load_state("networkidle")

    content = page.content()
    assert "Tariff saved" in content

    # View audit log
    page.goto(f"{base_url}/reports/audit/")
    page.wait_for_load_state("networkidle")

    audit_text = page.locator("table tbody").inner_text()
    assert "tariff.change" in audit_text
    assert "sys.admin@example.com" in audit_text
    page.close()


def test_tc28_live_occupancy_page(browser: Browser, base_url: str):
    """TC-28: Live occupancy page renders monitoring elements and htmx refresh."""
    context = browser.new_context()
    page = context.new_page()
    page.goto(f"{base_url}/lots/occupancy/")
    page.wait_for_load_state("networkidle")

    expect(page.locator("h1")).to_contain_text("Parking Occupancy")
    occ_div = page.locator("#occupancy")
    expect(occ_div).to_be_visible()
    assert occ_div.get_attribute("hx-get") == "/lots/occupancy/"
    assert occ_div.get_attribute("hx-trigger") == "every 30s"

    # Verify metrics for Demo Central
    expect(page.locator(".occ-lot")).to_be_visible()
    expect(page.locator(".occ-lot-heading h2")).to_contain_text("Demo Central")
    expect(page.locator(".occ-metric-value.occ-free")).to_be_visible()
    context.close()


def test_tc34_report_csvs(admin_context, base_url: str):
    """TC-34: Revenue and occupancy CSV exports; verify 32-day range is refused."""
    page = admin_context.new_page()

    # 1. 7-day revenue CSV
    rev_ok = page.request.get(
        f"{base_url}/reports/revenue.csv?start_date=2026-10-01&end_date=2026-10-07"
    )
    assert rev_ok.status == 200
    assert "text/csv" in rev_ok.headers.get("content-type", "")
    rev_csv = rev_ok.text()
    assert "Lot,Date,Slot type" in rev_csv

    # 2. 7-day occupancy CSV
    occ_ok = page.request.get(
        f"{base_url}/reports/occupancy.csv?lot=1&start_date=2026-10-01&end_date=2026-10-07"
    )
    assert occ_ok.status == 200
    assert "text/csv" in occ_ok.headers.get("content-type", "")
    occ_csv = occ_ok.text()
    assert "Lot,Date,Hour,Slot type" in occ_csv

    # 3. 32-day revenue CSV refused (2026-10-01 to 2026-11-02 is 32 days inclusive)
    rev_bad = page.request.get(
        f"{base_url}/reports/revenue.csv?start_date=2026-10-01&end_date=2026-11-02"
    )
    assert rev_bad.status == 400
    assert "31 days" in rev_bad.text()

    # 4. 32-day occupancy CSV refused
    occ_bad = page.request.get(
        f"{base_url}/reports/occupancy.csv?lot=1&start_date=2026-10-01&end_date=2026-11-02"
    )
    assert occ_bad.status == 400
    assert "31 days" in occ_bad.text()

    page.close()


def test_tc38_cookie_flags(admin_context):
    """TC-38: Session cookie flags over HTTP (HttpOnly, SameSite=Lax).

    Note: Secure flag and TLS cannot be tested over plain HTTP in local dev.
    They are recorded as not testable here.
    """
    cookies = admin_context.cookies()
    session_cookie = next((c for c in cookies if c["name"] == "sessionid"), None)
    assert session_cookie is not None, "sessionid cookie should be present after login"
    assert session_cookie["httpOnly"] is True
    assert session_cookie["sameSite"].lower() == "lax"


def test_tc42_mobile_booking_flow_360px(browser: Browser, base_url: str):
    """TC-42: Driver booking flow at 360 px width with no horizontal scroll."""
    ts = int(time.time() * 1000)
    email = f"d{ts % 100000}@vps.in"
    mobile = f"9{(ts + 3) % 1000000000:09d}"
    plate = f"KA0{ts % 9 + 1}MB{ts % 9000 + 1000}"

    context = browser.new_context(viewport={"width": 360, "height": 640})
    page = context.new_page()

    def assert_no_horizontal_scroll():
        scroll_width = page.evaluate("() => document.documentElement.scrollWidth")
        client_width = page.evaluate("() => document.documentElement.clientWidth")
        assert scroll_width <= client_width, (
            f"Horizontal scroll on {page.url}: scrollWidth={scroll_width} > clientWidth={client_width}"
        )

    # 1. Register page at 360px
    page.goto(f"{base_url}/accounts/register/")
    page.wait_for_load_state("networkidle")
    assert_no_horizontal_scroll()

    page.fill("#full_name", "Mobile Driver")
    page.fill("#email", email)
    page.fill("#mobile", mobile)
    page.fill("#password", PASSWORD)
    page.click(".registration-form button[type='submit']")
    page.wait_for_load_state("networkidle")
    assert "/vehicles/" in page.url

    # 2. Add vehicle
    page.fill("#registration_no", plate)
    page.select_option("#vehicle_type", "Car")
    page.click(".vehicle-form button[type='submit']")
    page.wait_for_load_state("networkidle")
    assert plate in page.content()

    # 3. Booking flow Screen 1: Search page at 360px
    page.goto(f"{base_url}/reservations/search/")
    page.wait_for_load_state("networkidle")
    assert_no_horizontal_scroll()

    # Screen 2: Search results at 360px
    page.select_option("#lot", value="1")
    page.select_option("#vehicle", label=f"{plate} — Car")
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    page.fill("#start", f"{tomorrow}T14:00")
    page.fill("#end", f"{tomorrow}T16:00")
    page.click(".search-form button[type='submit']")
    page.wait_for_selector("#search-results .search-result", timeout=10000)
    assert_no_horizontal_scroll()

    # Screen 3: Booking confirmation at 360px
    page.click(".booking-form button[type='submit']")
    page.wait_for_load_state("networkidle")
    assert "/reservations/confirmation/" in page.url
    assert_no_horizontal_scroll()

    context.close()


def test_tc03_lockout_and_http_423(browser: Browser, base_url: str):
    """TC-03: Lock account after 5 failed sign-ins and return HTTP 423."""
    ts = int(time.time() * 1000)
    lockout_email = f"lockout_{ts}@example.com"
    mobile = f"9{(ts + 7) % 1000000000:09d}"

    # 1. Register fresh driver in context1
    context1 = browser.new_context()
    page1 = context1.new_page()
    page1.goto(f"{base_url}/accounts/register/")
    page1.fill("#full_name", "Lockout Target")
    page1.fill("#email", lockout_email)
    page1.fill("#mobile", mobile)
    page1.fill("#password", PASSWORD)
    page1.click(".registration-form button[type='submit']")
    page1.wait_for_load_state("networkidle")
    assert "/vehicles/" in page1.url
    context1.close()

    # 2. Use a completely unauthenticated context2 for sign-in attempts
    context2 = browser.new_context()
    page2 = context2.new_page()

    # 3. 5 failed sign-in attempts
    for attempt in range(1, 6):
        page2.goto(f"{base_url}/accounts/login/")
        page2.fill("#email", lockout_email)
        page2.fill("#password", "WrongPassword!2026")
        page2.click("button[type='submit']")
        page2.wait_for_load_state("networkidle")
        content = page2.content()
        assert "Invalid e-mail or password" in content

    # 4. 6th attempt with correct password returns HTTP 423
    page2.goto(f"{base_url}/accounts/login/")
    page2.fill("#email", lockout_email)
    page2.fill("#password", PASSWORD)
    with page2.expect_response(
        lambda r: f"{base_url}/accounts/login/" in r.url and r.request.method == "POST"
    ) as resp_info:
        page2.click("button[type='submit']")
    response = resp_info.value
    assert response.status == 423
    content = page2.content()
    assert "Account locked until" in content or "locked" in content.lower()
    context2.close()
