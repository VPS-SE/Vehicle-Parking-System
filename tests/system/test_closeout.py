"""Closeout system tests for VPS.

Covers:
- TC-38: TLS negotiation, Strict-Transport-Security, cookie flags, and HTTP redirect
- TC-39: Driver mobile masking across attendant pages and log hygiene check
- TC-42: Axe accessibility auditing (WCAG 2.1 AA) and color-contrast verification
- TC-37: 10 Mbps throttled page load times (< 3 s) and page weights (<= 500 KB)
- TC-50: Charge waiver workflow, blank reason refusal, audit logging, gate payments disappearance, attendant 403
"""

import csv
import json
import re
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import Browser

PASSWORD = "SysTest!2026pass"
EVIDENCE_DIR = Path("docs/part-3/evidence")


def _driver_search_url(base_url: str, driver_context) -> str:
    """A search URL with results for sys.driver's first vehicle (its id differs per database)."""
    page = driver_context.new_page()
    page.goto(f"{base_url}/reservations/search/")
    vehicle = page.locator("#vehicle option[value]:not([value=''])").first.get_attribute("value")
    page.close()
    return (
        f"{base_url}/reservations/search/?lot=1&vehicle={vehicle}"
        "&start=2026-11-06T10:00&end=2026-11-06T12:00"
    )


# ---------------------------------------------------------------------------
# TC-38: TLS, Cookies and HTTP Redirection
# ---------------------------------------------------------------------------


def test_tc38_tls_and_cookie_security(browser: Browser, tls_url: str, http_prod_url: str):
    """TC-38 (SEC-04): Verify TLS 1.2+, HSTS, Secure cookies on 8443, and HTTP 301 redirect on 8180."""
    # 1. Negotiate TLS and verify cookies on 8443 (self-signed, ignore_https_errors)
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()

    resp = page.goto(f"{tls_url}/accounts/login/")
    assert resp is not None
    # Verify Strict-Transport-Security header
    hsts = resp.headers.get("strict-transport-security", "")
    assert "max-age=" in hsts, f"Strict-Transport-Security header missing or invalid: {hsts}"

    # Sign in on TLS
    page.fill("#email", "sys.admin@example.com")
    page.fill("#password", PASSWORD)
    page.click("button[type='submit']")
    page.wait_for_load_state("networkidle")

    # Check cookies
    cookies = context.cookies()
    session_cookie = next((c for c in cookies if c["name"] == "sessionid"), None)
    csrf_cookie = next((c for c in cookies if c["name"] == "csrftoken"), None)

    assert session_cookie is not None, "sessionid cookie missing on TLS login"
    assert session_cookie["secure"] is True, "sessionid must have Secure flag"
    assert session_cookie["httpOnly"] is True, "sessionid must have HttpOnly flag"
    assert session_cookie["sameSite"].lower() == "lax", "sessionid must have SameSite=Lax"

    assert csrf_cookie is not None, "csrftoken cookie missing on TLS login"
    assert csrf_cookie["secure"] is True, "csrftoken must have Secure flag on TLS"
    assert csrf_cookie["sameSite"].lower() == "lax", "csrftoken must have SameSite=Lax"

    context.close()

    # 2. Check 8180: plain HTTP returns 301 redirect, /healthz stays HTTP 200
    p1 = subprocess.run(
        ["curl", "-s", "-i", f"{http_prod_url}/"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "301 Moved Permanently" in p1.stdout
    assert "Location: https://" in p1.stdout

    p2 = subprocess.run(
        ["curl", "-s", "-i", f"{http_prod_url}/healthz"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "200 OK" in p2.stdout
    assert '{"status": "ok"}' in p2.stdout

    # 3. Check TLS versions: TLS 1.2+ negotiates, TLS 1.1 is refused
    p_tls12 = subprocess.run(
        ["curl", "-k", "-sv", "--tlsv1.2", f"{tls_url}/"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert p_tls12.returncode == 0
    assert "SSL connection using TLS" in p_tls12.stderr

    p_tls11 = subprocess.run(
        ["curl", "-k", "-sv", "--tls-max", "1.1", f"{tls_url}/"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert p_tls11.returncode != 0
    assert (
        "alert" in p_tls11.stderr.lower()
        or "error" in p_tls11.stderr.lower()
        or "no protocols available" in p_tls11.stderr.lower()
    )


# ---------------------------------------------------------------------------
# TC-39: Data Masking and Server Log Hygiene
# ---------------------------------------------------------------------------


def test_tc39_mobile_masking_across_attendant_pages(
    browser: Browser,
    base_url: str,
    driver_context,
    gate_context,
):
    """TC-39 (SEC-09): Ensure sys.driver's full mobile (9800000003) never appears on attendant pages."""
    driver_page = driver_context.new_page()

    # Step 1: Ensure sys.driver has a vehicle registered
    driver_page.goto(f"{base_url}/vehicles/")
    driver_page.wait_for_load_state("networkidle")
    if driver_page.locator("#registration_no").count() > 0:
        plate = f"KA01SY{int(time.time() * 1000) % 9000 + 1000}"
        driver_page.fill("#registration_no", plate)
        driver_page.select_option("#vehicle_type", "Car")
        driver_page.click(".vehicle-form button[type='submit']")
        driver_page.wait_for_load_state("networkidle")

    # Step 1b: If driver has open reservations >= 2, cancel one to stay under BR-03 limit
    driver_page.goto(f"{base_url}/reservations/history/")
    driver_page.wait_for_load_state("networkidle")
    history_content = driver_page.content()
    for ref_match in re.finditer(r"VPS-\d{6}-(\d+)", history_content):
        res_id = ref_match.group(1)
        driver_page.evaluate(
            f"""
            async () => {{
                const csrfMatch = document.cookie.match(/csrftoken=([^;]+)/);
                const csrf = csrfMatch ? csrfMatch[1] : '';
                await fetch('/reservations/{res_id}/cancel/', {{
                    method: 'POST',
                    headers: {{'X-CSRFToken': csrf}}
                }});
            }}
            """
        )
        break

    # Step 2: Book a slot starting in 5 minutes (within check-in window)
    driver_page.goto(f"{base_url}/reservations/search/")
    driver_page.wait_for_load_state("networkidle")
    driver_page.select_option("#lot", value="1")
    vehicle_select = driver_page.locator("#vehicle")
    for opt in vehicle_select.locator("option").all():
        val = opt.get_attribute("value")
        if val:
            driver_page.select_option("#vehicle", value=val)
            break

    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    start_dt = now + timedelta(minutes=5)
    end_dt = start_dt + timedelta(minutes=30)
    if start_dt.hour < 6 or (start_dt.hour >= 22 and start_dt.minute > 25):
        # Fallback to tomorrow if outside operating hours
        start_dt = (now + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
        end_dt = start_dt + timedelta(hours=2)

    driver_page.fill("#start", start_dt.strftime("%Y-%m-%dT%H:%M"))
    driver_page.fill("#end", end_dt.strftime("%Y-%m-%dT%H:%M"))
    driver_page.click(".search-form button[type='submit']")
    driver_page.wait_for_selector("#search-results .search-result", timeout=10000)

    driver_page.click(".booking-form button[type='submit']")
    driver_page.wait_for_load_state("networkidle")
    if "/reservations/confirmation/" not in driver_page.url:
        main_html = driver_page.locator("main").inner_text()
        print("SEARCH/BOOKING MAIN TEXT:", main_html)
    assert "/reservations/confirmation/" in driver_page.url
    conf_content = driver_page.content()
    match = re.search(r"VPS-\d{6}-\d{4}", conf_content)
    assert match is not None, "Booking reference not found in confirmation page"
    booking_ref = match.group(0)
    driver_page.close()

    # Step 3: Open every attendant page and check for mobile masking
    gate_page = gate_context.new_page()

    # Page 1: Gate dashboard
    gate_page.goto(f"{base_url}/gate/")
    gate_page.wait_for_load_state("networkidle")
    assert "9800000003" not in gate_page.content()

    # Page 2: Gate check-in
    gate_page.fill("#checkin-reference", booking_ref)
    gate_page.click("#check-in button[type='submit']")
    gate_page.wait_for_load_state("networkidle")
    assert "9800000003" not in gate_page.content()

    # Page 3: Gate check-out
    gate_page.goto(f"{base_url}/gate/checkout/")
    gate_page.wait_for_load_state("networkidle")
    gate_page.fill("input[name='query']", booking_ref)
    gate_page.click("main button[type='submit']")
    gate_page.wait_for_load_state("networkidle")
    assert "9800000003" not in gate_page.content()

    # Page 4: Checkout receipt
    assert f"/gate/receipt/{booking_ref}/" in gate_page.url
    assert "9800000003" not in gate_page.content()

    # Page 5: Printable receipt
    gate_page.goto(f"{base_url}/gate/receipt/{booking_ref}/print/")
    gate_page.wait_for_load_state("networkidle")
    assert "9800000003" not in gate_page.content()

    # Page 6: Payments search
    gate_page.goto(f"{base_url}/gate/payments/?q={booking_ref}")
    gate_page.wait_for_load_state("networkidle")
    assert "9800000003" not in gate_page.content()

    # Clear charge so sys.driver has zero unpaid balance
    if "Record payment" in gate_page.content():
        gate_page.click("button:has-text('Record payment')")
        gate_page.wait_for_load_state("networkidle")

    gate_page.close()


def test_tc39_server_logs_hygiene(server_logs_path: str):
    """TC-39 (SEC-09): Grep server logs; neither password SysTest!2026pass nor 'pbkdf2_sha256$' may appear."""
    log_dir = Path(server_logs_path)
    log_files = [
        log_dir / "web.log",
        log_dir / "web-access.log",
        log_dir / "web-tls.log",
        log_dir / "web-http-prod.log",
        log_dir / "forecast.log",
    ]

    for log_path in log_files:
        if not log_path.exists():
            continue
        content = log_path.read_text(errors="replace")
        assert "SysTest!2026pass" not in content, (
            f"Plaintext password found in server log {log_path.name}"
        )
        assert "pbkdf2_sha256$" not in content, f"Password hash found in server log {log_path.name}"


# ---------------------------------------------------------------------------
# TC-42: Accessibility Audit (Axe WCAG 2.1 AA) and Color Contrast
# ---------------------------------------------------------------------------


def test_tc42_axe_wcag_and_contrast(
    browser: Browser,
    base_url: str,
    admin_context,
    gate_context,
    driver_context,
):
    """TC-42 (NFR-USE-02): Run axe-core across 15 VPS pages.

    Fails if any page has a color-contrast violation. Saves violations to axe-violations.json.
    """
    pages_to_audit = [
        # Anonymous pages
        ("sign-in", f"{base_url}/accounts/login/", "anon"),
        ("register", f"{base_url}/accounts/register/", "anon"),
        ("live-occupancy", f"{base_url}/lots/occupancy/", "anon"),
        # Driver pages
        ("driver-vehicles", f"{base_url}/vehicles/", "driver"),
        ("search-with-results", _driver_search_url(base_url, driver_context), "driver"),
        ("booking-history", f"{base_url}/reservations/history/", "driver"),
        # Gate Attendant pages
        ("gate-dashboard", f"{base_url}/gate/", "gate"),
        ("payments", f"{base_url}/gate/payments/", "gate"),
        ("check-out", f"{base_url}/gate/checkout/", "gate"),
        # Admin pages
        ("admin-lots", f"{base_url}/lots/", "admin"),
        ("tariffs", f"{base_url}/lots/tariffs/", "admin"),
        ("revenue-report", f"{base_url}/reports/revenue/", "admin"),
        ("occupancy-report", f"{base_url}/reports/occupancy/", "admin"),
        ("audit-log", f"{base_url}/reports/audit/", "admin"),
        ("waive-charges", f"{base_url}/billing/waivers/", "admin"),
    ]

    anon_context = browser.new_context()
    contexts = {
        "anon": anon_context,
        "driver": driver_context,
        "gate": gate_context,
        "admin": admin_context,
    }

    axe = Axe()
    all_violations = {}
    contrast_violations = []

    for name, url, role in pages_to_audit:
        ctx = contexts[role]
        page = ctx.new_page()
        page.goto(url)
        page.wait_for_load_state("networkidle")

        result = axe.run(
            page,
            options={
                "runOnly": {
                    "type": "tag",
                    "values": ["wcag2a", "wcag2aa", "wcag21aa"],
                }
            },
        )
        violations = result.response.get("violations", [])
        all_violations[name] = violations

        for v in violations:
            if v["id"] == "color-contrast":
                contrast_violations.append((name, v))

        page.close()

    anon_context.close()

    # Save all violations to JSON
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    out_file = EVIDENCE_DIR / "axe-violations.json"
    out_file.write_text(json.dumps(all_violations, indent=2))

    # Assert no color-contrast violations
    assert not contrast_violations, (
        f"Found {len(contrast_violations)} color-contrast violations: "
        f"{[item[0] for item in contrast_violations]}"
    )


# ---------------------------------------------------------------------------
# TC-37: Throttled Network Load Times and Page Weights
# ---------------------------------------------------------------------------


def test_tc37_cdp_network_throttling(
    browser: Browser,
    base_url: str,
    admin_context,
    gate_context,
    driver_context,
):
    """TC-37 (NFR-PERF-04): Measure load time (< 3 s) and page weight (<= 500 KB) under 10 Mbps CDP throttling."""
    pages_to_test = [
        ("sign-in", f"{base_url}/accounts/login/", "anon"),
        ("register", f"{base_url}/accounts/register/", "anon"),
        ("live-occupancy", f"{base_url}/lots/occupancy/", "anon"),
        ("driver-vehicles", f"{base_url}/vehicles/", "driver"),
        ("search-with-results", _driver_search_url(base_url, driver_context), "driver"),
        ("booking-history", f"{base_url}/reservations/history/", "driver"),
        ("gate-dashboard", f"{base_url}/gate/", "gate"),
        ("payments", f"{base_url}/gate/payments/", "gate"),
        ("check-out", f"{base_url}/gate/checkout/", "gate"),
        ("admin-lots", f"{base_url}/lots/", "admin"),
        ("tariffs", f"{base_url}/lots/tariffs/", "admin"),
        ("revenue-report", f"{base_url}/reports/revenue/", "admin"),
        ("occupancy-report", f"{base_url}/reports/occupancy/", "admin"),
        ("audit-log", f"{base_url}/reports/audit/", "admin"),
        ("waive-charges", f"{base_url}/billing/waivers/", "admin"),
    ]

    anon_context = browser.new_context()
    contexts = {
        "anon": anon_context,
        "driver": driver_context,
        "gate": gate_context,
        "admin": admin_context,
    }

    results = []

    for name, url, role in pages_to_test:
        ctx = contexts[role]
        page = ctx.new_page()

        # Create CDP session for throttling
        cdp = ctx.new_cdp_session(page)
        cdp.send("Network.enable")
        cdp.send(
            "Network.emulateNetworkConditions",
            {
                "offline": False,
                "latency": 20,
                "downloadThroughput": 1250000,
                "uploadThroughput": 1250000,
                "connectionType": "cellular4g",
            },
        )
        cdp.send("Network.clearBrowserCache")
        cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})

        bytes_transferred = 0

        def on_loading_finished(event):
            nonlocal bytes_transferred
            bytes_transferred += event.get("encodedDataLength", 0)

        cdp.on("Network.loadingFinished", on_loading_finished)

        t_start = time.perf_counter()
        page.goto(url, wait_until="load")
        load_time_s = time.perf_counter() - t_start

        results.append(
            {
                "page": name,
                "url": url,
                "load_time_s": round(load_time_s, 3),
                "bytes_transferred": bytes_transferred,
                "size_kb": round(bytes_transferred / 1024, 2),
            }
        )

        cdp.detach()
        page.close()

    anon_context.close()

    # Save results to CSV
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    csv_file = EVIDENCE_DIR / "throttled-pages.csv"
    with open(csv_file, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["page", "url", "load_time_s", "bytes_transferred", "size_kb"]
        )
        writer.writeheader()
        writer.writerows(results)

    # Check assertions: load time < 3 s and bytes <= 500 KB (512,000 bytes)
    for r in results:
        assert r["load_time_s"] < 3.0, (
            f"Page {r['page']} took {r['load_time_s']} s to load (target < 3.0 s)"
        )
        assert r["bytes_transferred"] <= 512000, (
            f"Page {r['page']} transferred {r['bytes_transferred']} bytes (target <= 500 KB)"
        )


# ---------------------------------------------------------------------------
# TC-50: Charge Waiver, Reason Validation, and Audit Logging
# ---------------------------------------------------------------------------


def test_tc50_waive_charge_admin_and_audit(
    browser: Browser,
    base_url: str,
    admin_context,
    gate_context,
):
    """TC-50 (BR-09 & AUD-01): Admin waives unpaid charge with written reason;

    blank reason refused; audit log updated; attendant gets 403.
    """
    gate_page = gate_context.new_page()

    # 1. Seed unpaid charge through UI: Gate attendant registers a walk-in vehicle
    gate_page.goto(f"{base_url}/gate/walk-in/")
    gate_page.wait_for_load_state("networkidle")
    plate = f"KA05WV{int(time.time() * 1000) % 9000 + 1000}"
    gate_page.fill("#id_registration_no", plate)
    gate_page.select_option("#id_vehicle_type", "Car")
    gate_page.select_option("#id_lot", value="1")
    gate_page.click("main button[type='submit']")
    gate_page.wait_for_selector(".message-success", timeout=10000)

    content = gate_page.content()
    match = re.search(r"VPS-\d{6}-\d{4}", content)
    assert match is not None, "Walk-in booking ref not found in gate response"
    booking_ref = match.group(0)

    # 2. Check out the vehicle through the UI to generate an unpaid parking charge
    gate_page.goto(f"{base_url}/gate/checkout/")
    gate_page.wait_for_load_state("networkidle")
    gate_page.fill("input[name='query']", plate)
    gate_page.click("main button[type='submit']")
    gate_page.wait_for_load_state("networkidle")
    assert f"/gate/receipt/{booking_ref}/" in gate_page.url

    # 3. Attendant sees the unpaid charge in payments search
    gate_page.goto(f"{base_url}/gate/payments/?q={booking_ref}")
    gate_page.wait_for_load_state("networkidle")
    assert booking_ref in gate_page.content()
    assert "Parking" in gate_page.content()

    # 4. Attendant is refused /billing/waivers/ (HTTP 403)
    gate_waiver_resp = gate_page.goto(f"{base_url}/billing/waivers/")
    assert gate_waiver_resp.status == 403
    gate_page.close()

    # 5. Admin opens /billing/waivers/ and searches for the charge
    admin_page = admin_context.new_page()
    admin_page.goto(f"{base_url}/billing/waivers/?q={booking_ref}")
    admin_page.wait_for_load_state("networkidle")

    waiver_content = admin_page.content()
    assert booking_ref in waiver_content
    assert "Parking" in waiver_content
    assert "Rs 40.00" in waiver_content

    # Extract charge ID from form action
    charge_match = re.search(r'action="/billing/waivers/(\d+)/"', waiver_content)
    assert charge_match is not None, "Waiver form action not found"
    charge_id = charge_match.group(1)

    # 6. Blank reason is refused
    admin_page.evaluate(
        f"() => {{ document.getElementById('reason-{charge_id}').removeAttribute('required'); }}"
    )
    admin_page.fill(f"#reason-{charge_id}", "   ")
    admin_page.click("button:has-text('Waive charge')")
    admin_page.wait_for_load_state("networkidle")

    # Verify refused message and charge still present
    blank_refused_content = admin_page.content()
    assert "Give a written reason for waiving this charge" in blank_refused_content
    assert booking_ref in blank_refused_content

    # 7. Written reason waives the charge
    waiver_reason = "Customer emergency walkin courtesy waiver"
    admin_page.fill(f"#reason-{charge_id}", waiver_reason)
    admin_page.click("button:has-text('Waive charge')")
    admin_page.wait_for_load_state("networkidle")

    success_content = admin_page.content()
    assert "Waived the Rs 40.00 parking charge" in success_content

    # 8. Verify waiver appears in Audit Log (/reports/audit/)
    admin_page.goto(f"{base_url}/reports/audit/")
    admin_page.wait_for_load_state("networkidle")
    audit_table = admin_page.locator("table tbody").inner_text()
    assert "charge.waived" in audit_table
    assert waiver_reason in audit_table
    assert f"charge:{charge_id}" in audit_table or booking_ref in audit_table

    admin_page.close()

    # 9. Charge is gone from attendant's /gate/payments/ search
    gate_page2 = gate_context.new_page()
    gate_page2.goto(f"{base_url}/gate/payments/?q={booking_ref}")
    gate_page2.wait_for_load_state("networkidle")
    gate_table_content = gate_page2.content()
    assert "No unpaid charges found" in gate_table_content
    gate_page2.close()
