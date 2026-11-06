# System Validation Report

Vehicle Parking System, Team 10, Section C. Part 3. System testing on 5 November 2026. The final runs used branch `test/part3-closeout`: `main` plus the charge waiver and Gunicorn change (PR #129) and the booking lock fix (PR #130). Those two PRs must be merged for `main` to match what was tested.

## 1. Summary

The Test Plan now has 51 test cases. TC-45 to TC-51 were added on 5 November for the seven requirements that had no test case. 49 passed and 2 were not run. None failed. The two not run need things a laptop cannot give: TC-41 is a timed trial with first-time users, and TC-51 is a month of monitored uptime. All four exit criteria are met, with the caveat that TC-51 is listed but not executed (Section 6).

Testing found two new application defects, both fixed and re-tested (Section 7). The serious one, D-4, showed up only under concurrent bookings. With 50 users booking at once, 39% of bookings failed: some with HTTP 500 from database deadlocks, others refused as "no slot" while hundreds were free. After the fix the same load ran with no failures.

## 2. Environment

- Web application: Django 5.2.18 on Python 3.13.14, served by Gunicorn with 8 sync workers (the Compose setup), DEBUG on, at http://127.0.0.1:8100. For the security checks the same code also ran with DEBUG off: plain HTTP at http://127.0.0.1:8180 and TLS at https://127.0.0.1:8443 with a self-signed certificate.
- Database: PostgreSQL 16.15 in Docker, `max_connections` 100. A fresh database seeded with `manage.py seed_demo_data --seed 2026`: 500 slots, 120 drivers, 4145 reservations over 30 days, 2708 charges. The lot's closing time was moved from 23:00 to 23:59 so the evening booking load test could check vehicles in.
- Accounts: one admin, one attendant and one driver with a known password, plus 200 load drivers (one car each) and 10 load attendants. `tests/system/make_load_accounts.py` creates them and writes a signed-in session for each, so the load tests do not hit the sign-in rate limit.
- Forecast service: FastAPI at http://127.0.0.1:8101, with the simulated baseline model (the demo data has 20 days of history; the history model needs 4 weeks).
- Tools: Playwright 1.64.1 (Chromium headless), axe-playwright-python 0.1.8, Locust 2.47.0, bandit 1.9.4, curl and OpenSSL.
- Not the staging server in Test Plan Section 6, which does not exist: one laptop, no nginx.

## 3. Runs

| Run | Command | Started | Result | Raw output |
|---|---|---|---|---|
| Unit and integration, with coverage | `./run-coverage.sh run -m pytest` | 22:48 | 771 passed, 0 failed | `evidence/junit.xml`, `evidence/coverage-run.txt` |
| Forecast service | `./run-forecast-tests.sh` | 22:35 | 16 passed | `evidence/forecast-junit.xml` |
| Browser (system) tests | `./run-system-tests.sh` | 22:47 | 17 passed, 0 failed | `evidence/system-junit.xml` |
| Load: bookings, check-in, check-out, 50 users | Locust, 120 s | 22:28 | 0 failures | `evidence/locust-booking50*` |
| Same, before the D-4 fix | Locust, 120 s | 22:21 | 187 failures | `evidence/locust-booking50-before-fix.txt` |
| Load: 200 separate sessions | Locust, 120 s | 22:30 | 0 failures | `evidence/locust-sessions200*` |
| Load: search, 50 users | Locust, 60 s | 22:40 | 0 failures | `evidence/locust-gunicorn50*` |
| Load: forecast service, 20 users | Locust, 60 s | 20:54 | 0 failures | `evidence/locust-forecast*` |
| TLS and redirect checks | curl, openssl s_client | 22:41 | see TC-38 | `evidence/tls-checks.txt` |
| Accessibility | axe-core in Playwright | 22:47 (with the browser tests) | 0 violations | `evidence/axe-violations.json`, `evidence/axe-sanity.txt` |
| Static security scan | `bandit -r vps forecast` | 22:51 | 0 high, 1 medium, 3 low | `evidence/bandit.txt` |

The forecast load test ran earlier on 5 November against the same forecast code. The earlier development-server load runs (`evidence/locust50*`, `evidence/locust200*`) are kept as the evidence for defect D-1.

The browser tests are in `tests/system/test_system.py` and `tests/system/test_closeout.py`, the business-rule tests in `tests/test_tc45_tc49_business_rules.py`, and the load scripts in `tests/system/locust_*.py`. The agy test agent wrote most of them. I fixed three of its scripts before the runs counted. The booking load script treated failed bookings and check-ins as successes. The load scripts sent the wrong session after the server reset the cookie. Two browser tests used fixed plates or dates, so they failed when run again on the same database. Every number in this report is copied from the files above.

## 4. Test case results

Pass: every test mapped to the case ran and passed, and together they cover the case's steps. Not run: nothing was executed. The test functions for each case are listed in `evidence/tc-mapping.txt`.

| TC | Title | Requirements | Type / level / priority | Status | Evidence | Notes |
|---|---|---|---|---|---|---|
| TC-01 | Register a Driver with valid details | FR-AUTH-01, FR-AUTH-02 | Functional / System / High | **Pass** | 5 tests, 5 passed: `test_system.py`, `test_accounts_views.py`, `test_driver_registration_template.py` |  |
| TC-02 | Reject duplicate e-mail at registration | FR-AUTH-01 | Functional / Integration / High | **Pass** | 7 tests, 7 passed: `test_system.py`, `test_fix_f1_email_case_insensitivity.py`, `test_tc02_duplicate_email.py` |  |
| TC-03 | Lock account after 5 failed sign-ins | SEC-02, FR-AUTH-02 | Security / Integration / High | **Pass** | 10 tests, 10 passed: `test_system.py`, `test_fix_f2_account_lockout.py`, `test_review_findings.py` |  |
| TC-04 | Validate vehicle registration number format | FR-VEH-02, FR-VEH-03 | Functional / Unit / Medium | **Pass** | 5 tests, 5 passed: `test_system.py`, `test_tc04_vehicle_format.py`, `test_vehicles.py` |  |
| TC-05 | Search excludes blocked and occupied slots | FR-SRCH-01, FR-LOT-03, SAF-01 | Functional / Integration / High | **Pass** | 3 tests, 3 passed: `test_system.py`, `test_booking_flow.py`, `test_reservations.py` |  |
| TC-06 | Allocate the preferred, nearest slot | FR-ALLOC-01, FR-ALLOC-02, FR-RES-01 | Functional / Unit / High | **Pass** | 3 tests, 3 passed: `test_system.py`, `test_allocation.py`, `test_reservations.py` |  |
| TC-07 | Exactly one booking wins the last slot | FR-RES-02, FR-ALLOC-03, NFR-REL-01 | Non-functional (reliability) / Integration / High | **Pass** | 20 tests, 20 passed: `test_reservations.py` |  |
| TC-08 | Enforce reservation limit and unpaid charges | FR-RES-03 | Functional / Integration / Medium | **Pass** | 2 tests, 2 passed: `test_reservations.py` |  |
| TC-09 | Late cancellation records a fee | FR-RES-04 | Functional / Unit / Medium | **Pass** | 12 tests, 12 passed: `test_cancellation.py` |  |
| TC-10 | Unclaimed reservation expires | FR-RES-05, FR-RES-07 | Functional / Integration / High | **Pass** | 2 tests, 2 passed: `test_expiry.py`, `test_notifications.py` |  |
| TC-11 | Check-in window is enforced | FR-GATE-01, FR-GATE-02 | Functional / System / High | **Pass** | 2 tests, 2 passed: `test_check_in.py` |  |
| TC-12 | Register a walk-in vehicle | FR-GATE-03 | Functional / System / Medium | **Pass** | 1 test, 1 passed: `test_walk_in.py` |  |
| TC-13 | Compute parking charge with rounding and minimum | FR-BILL-02, FR-GATE-04, FR-BILL-04 | Functional / Unit / High | **Pass** | 4 tests, 4 passed: `test_checkout.py`, `test_printable_receipt.py` |  |
| TC-14 | Bill overstay at 1.5 times the rate | FR-BILL-03 | Functional / Unit / High | **Pass** | 5 tests, 5 passed: `test_checkout.py` |  |
| TC-15 | Attendant cannot change a tariff | SEC-03, BR-01 | Security / Integration / High | **Pass** | 4 tests, 4 passed: `test_system.py`, `test_tariffs.py`, `test_tc15_attendant_tariff.py` |  |
| TC-16 | State change without CSRF token is rejected | SEC-05 | Security / Integration / High | **Pass** | 1 test, 1 passed: `test_tc16_csrf.py` |  |
| TC-17 | SQL injection input is handled safely | SEC-06 | Security / System / High | **Pass** | 1 test, 1 passed: `test_tc17_sql_injection.py` |  |
| TC-18 | Search meets the response-time target | NFR-PERF-01, NFR-PERF-03 | Non-functional (performance) / System / Medium | **Pass** | Load tests, Section 5 | NFR-PERF-01: with 50 users the 95th percentile for search was 35 ms on Gunicorn (8 workers); the target is 1 s. NFR-PERF-03: 200 users, each with its own signed-in session, made 16135 requests in 120 s with 0 failures (search 95th percentile 630 ms). The server's access log shows no redirects to the sign-in page during the run, so every request was signed in. |
| TC-19 | Privileged actions are audited | SEC-07, FR-RPT-04 | Security / Integration / Medium | **Pass** | 13 tests, 13 passed: `test_system.py`, `test_audit.py`, `test_audit_search.py`, `test_tc19_audit_trail.py` |  |
| TC-20 | Search works when the forecast service is down | FR-FCST-03 | Functional / Integration / Low | **Pass** | 2 tests, 2 passed: `test_forecast_panel.py` |  |
| TC-21 | Only administrators create staff; deactivation blocks sign-in | FR-AUTH-03, FR-AUTH-05 | Functional / Integration / High | **Pass** | 15 tests, 15 passed: `test_staff_creation.py`, `test_staff_management.py` |  |
| TC-22 | Password reset link is single-use and expires | FR-AUTH-04, SEC-09 | Security / Integration / Medium | **Pass** | 3 tests, 3 passed: `test_password_reset.py` |  |
| TC-23 | Accessible slots only for permit holders | FR-AUTH-06, FR-ALLOC-01, SAF-02 | Functional / Unit / High | **Pass** | 1 test, 1 passed: `test_accessible_permit.py` |  |
| TC-24 | Vehicle limit and protected removal | FR-VEH-01, FR-VEH-04 | Functional / Unit / Medium | **Pass** | 8 tests, 8 passed: `test_vehicle_removal.py`, `test_vehicles.py` |  |
| TC-25 | Create lots and slots with unique codes | FR-LOT-01, FR-LOT-02 | Functional / Integration / Medium | **Pass** | 14 tests, 14 passed: `test_lots.py` |  |
| TC-26 | Blocking a slot moves affected reservations | FR-LOT-04, FR-RES-07 | Functional / Integration / High | **Pass** | 6 tests, 6 passed: `test_tc26_block_moves.py` |  |
| TC-27 | Search window validation | FR-SRCH-02 | Functional / Unit / Medium | **Pass** | 6 tests, 6 passed: `test_booking_flow.py` |  |
| TC-28 | Live occupancy view refreshes | FR-SRCH-03, FR-RPT-01 | Functional / System / Medium | **Pass** | 6 tests, 6 passed: `test_system.py`, `test_tc28_occupancy.py` |  |
| TC-29 | Booking history is paged and ordered | FR-RES-06 | Functional / Integration / Low | **Pass** | 8 tests, 8 passed: `test_booking_history.py` |  |
| TC-30 | Record a payment and clear unpaid charges | FR-GATE-05, FR-BILL-05, BR-04 | Functional / Integration / High | **Pass** | 3 tests, 3 passed: `test_driver_unpaid_balance_template.py`, `test_payments.py` |  |
| TC-31 | Manual time correction is limited and audited | FR-GATE-06, SAF-03, SEC-07 | Functional / Integration / Medium | **Pass** | 4 tests, 4 passed: `test_time_correction.py` |  |
| TC-32 | Reallocate when the reserved slot is still occupied | FR-GATE-07 | Functional / Integration / Medium | **Pass** | 2 tests, 2 passed: `test_check_in.py`, `test_reallocation.py` |  |
| TC-33 | Tariff in force at entry is used | FR-BILL-01, BR-08 | Functional / Unit / High | **Pass** | 3 tests, 3 passed: `test_checkout.py`, `test_tariffs.py` |  |
| TC-34 | Occupancy and revenue reports export to CSV | FR-RPT-02, FR-RPT-03 | Functional / Integration / Low | **Pass** | 19 tests, 19 passed: `test_system.py`, `test_occupancy_report.py`, `test_revenue_report.py` |  |
| TC-35 | Forecast bands and baseline label | FR-FCST-01, FR-FCST-02 | Functional / Unit / Low | **Pass** | 12 tests, 12 passed: `test_forecast.py`, `test_system.py`, `test_forecast_panel.py` |  |
| TC-36 | Booking, gate and forecast response times | NFR-PERF-02, NFR-PERF-05 | Non-functional (performance) / System / Medium | **Pass** | Load tests, Section 5 | NFR-PERF-02: 50 users made 2990 bookings in 120 s, each checked in, checked out and paid, with 0 failures. 95th percentiles: reserve 120 ms, check-in 63 ms, check-out 59 ms (target 2 s). The first run failed (defect D-4, fixed): 187 of 475 bookings failed and the reserve 95th percentile was 43 s. NFR-PERF-05: the forecast service answered 8914 requests from 20 users with a 95th percentile of 6 ms (target 500 ms). |
| TC-37 | Page weight and load time | NFR-PERF-04 | Non-functional (performance) / System / Low | **Pass** | 1 test, 1 passed: `test_closeout.py` | Chromium with the network throttled to 10 Mbps (CDP), empty cache, 15 pages across all roles. Slowest load event 0.342 s (booking-history); largest transfer 64 KB (audit-log). Targets 3 s and 500 KB. The server was on the same machine, so only bandwidth and 20 ms latency were simulated. |
| TC-38 | TLS, cookie flags and idle timeout | SEC-04, SEC-08 | Security / System / High | **Pass** | 8 tests, 8 passed: `test_closeout.py`, `test_system.py`, `test_fix_f7_session_security.py` | Run on a local Gunicorn TLS listener with a self-signed certificate and DEBUG off, because the staging server in Test Plan Section 6 does not exist. TLS 1.3 and 1.2 connect; a client offering only TLS 1.1 gets a protocol-version alert and the server logs UNSUPPORTED_PROTOCOL. HSTS is sent (max-age 31536000). After sign-in, sessionid is Secure, HttpOnly and SameSite=Lax, and csrftoken is Secure and SameSite=Lax. Plain HTTP answers 301 to https://, and /healthz stays on HTTP. Idle timeout and key rotation are covered by unit tests. Output in `evidence/tls-checks.txt`. |
| TC-39 | Password storage and data masking | SEC-01, SEC-09 | Security / Integration / High | **Pass** | 3 tests, 3 passed: `test_closeout.py`, `test_tc39_password_storage.py` | Unit tests check the PBKDF2 hash and weak-password refusal. The browser test booked a slot as the driver with mobile 9800000003 and opened the gate dashboard, check-in, check-out, receipt, printable receipt and payments search as an attendant: the number did not appear on any of them (attendant pages show no mobile number at all). After all system and load runs, the server logs contain neither the test password nor a `pbkdf2_sha256$` hash. |
| TC-40 | No secrets in the repository | SEC-10 | Security / System / Medium | **Pass** | 1 test, 1 passed: `test_settings.py` | Unit test checks that settings refuse to start without DJANGO_SECRET_KEY. The gitleaks scan in CI's Security scans job passed on PRs #125, #126 and #127. |
| TC-41 | First-time booking within 3 minutes | NFR-USE-01 | Non-functional (usability) / Acceptance / Medium | **Not run** | - | Needs a timed trial with people; not done. |
| TC-42 | Small screens and colour contrast | NFR-USE-02, NFR-PRT-01 | Non-functional (usability) / System / Low | **Pass** | 2 tests, 2 passed: `test_closeout.py`, `test_system.py` | Playwright ran the driver flow at 360 px with no horizontal scroll. axe-core 4 (WCAG 2.0 A and AA, 2.1 AA rules) ran on 15 pages across all roles and found 0 violations, including colour contrast (`evidence/axe-violations.json`). A deliberately low-contrast control page was flagged by the same setup, so the checker was working. |
| TC-43 | Coverage and lint gates in CI | NFR-MNT-01, NFR-MNT-02, NFR-TST-01 | Non-functional (maintainability) / System / Medium | **Pass** | 18 tests, 18 passed: `test_check_coverage.py`, `test_tc43_quality_gates.py` | Unit tests check the gate thresholds and CI configuration. Branch protection on main was seen in practice on 5 Nov: merging PR #125 without approval was refused ("the base branch policy prohibits the merge"). |
| TC-44 | Code review findings are fixed and regression-tested | FR-AUTH-01, FR-SRCH-01, FR-GATE-06, SEC-02, SEC-03, SEC-04, SEC-07, SEC-08 | Static (code review) / Integration / High | **Pass** | 62 tests, 62 passed: `test_fix_f1_email_case_insensitivity.py`, `test_fix_f2_account_lockout.py`, `test_fix_f3_admin_time_correction.py`, `test_fix_f4_audit_slot_blocks_and_staff.py`, `test_fix_f5_notifications.py`, `test_fix_f6_unpaid_total.py`, `test_fix_f7_session_security.py`, `test_fix_g1_staff_search.py`, `test_review_findings.py`, `test_review_findings_2.py` |  |
| TC-45 | Only Gate Attendants perform gate operations and payments | BR-02 | Security / Integration / High | **Pass** | 1 test, 1 passed: `test_tc45_tc49_business_rules.py` |  |
| TC-46 | A third Reserved booking is refused until one is cancelled | BR-03, FR-RES-03 | Functional / Integration / High | **Pass** | 1 test, 1 passed: `test_tc45_tc49_business_rules.py` |  |
| TC-47 | Cancellation and no-show fees at the 60-minute boundary | BR-05, FR-RES-04 | Functional / Unit / High | **Pass** | 1 test, 1 passed: `test_tc45_tc49_business_rules.py` |  |
| TC-48 | A booking is held for 15 minutes after its start | BR-06, FR-RES-05 | Functional / Unit / High | **Pass** | 1 test, 1 passed: `test_tc45_tc49_business_rules.py` |  |
| TC-49 | Billing blocks, 1-hour minimum and overstay grace | BR-07, FR-BILL-02, FR-BILL-03 | Functional / Unit / High | **Pass** | 17 tests, 17 passed: `test_tc45_tc49_business_rules.py` |  |
| TC-50 | An administrator waives a charge with a written reason | BR-09, SEC-07 | Functional / System / High | **Pass** | 23 tests, 23 passed: `test_closeout.py`, `test_charge_waiver.py` |  |
| TC-51 | Monthly availability of the deployed system | NFR-AVL-01 | Non-functional (availability) / System / Medium | **Not run** | - | Needs a deployed system monitored over a calendar month. |

## 5. Performance

All runs on Gunicorn with 8 workers. In the search run, signed-in drivers searched availability (three requests in four) and loaded the live occupancy page. In the 200-session run, each simulated user had its own driver session. In the booking run, each user booked a 30-minute slot starting two minutes later. An attendant then checked it in, checked it out and recorded the payment, so the driver could book again. The tables come from the Locust CSV files, which Locust writes a moment before it stops, so the summary printed at the end of each `*-run.txt` shows a few more requests.


**Search, 50 users** (response times in ms)

| Request | Count | Failures | Median | 95th | 99th | Max |
|---|---|---|---|---|---|---|
| /reservations/search/ | 2065 | 0 | 27 | 35 | 49 | 74 |
| /lots/occupancy/ | 692 | 0 | 38 | 48 | 72 | 91 |
| Aggregated | 2757 | 0 | 28 | 43 | 57 | 91 |

**200 separate signed-in sessions** (response times in ms)

| Request | Count | Failures | Median | 95th | 99th | Max |
|---|---|---|---|---|---|---|
| /reservations/search/ | 9723 | 0 | 460 | 630 | 720 | 878 |
| /lots/occupancy/ | 3183 | 0 | 450 | 620 | 710 | 847 |
| /reservations/history/ | 3229 | 0 | 440 | 610 | 680 | 823 |
| Aggregated | 16135 | 0 | 460 | 630 | 710 | 878 |

**Bookings and gate, 50 users** (response times in ms)

| Request | Count | Failures | Median | 95th | 99th | Max |
|---|---|---|---|---|---|---|
| reserve | 2990 | 0 | 66 | 120 | 170 | 252 |
| check-in | 2990 | 0 | 38 | 63 | 93 | 123 |
| check-out | 2989 | 0 | 34 | 59 | 88 | 121 |
| payment | 2988 | 0 | 32 | 52 | 70 | 116 |
| /gate/payments/ | 2989 | 0 | 35 | 56 | 80 | 122 |
| Aggregated | 14996 | 0 | 36 | 85 | 120 | 252 |

**Bookings and gate, 50 users, before the D-4 fix** (from `evidence/locust-booking50-before-fix.txt`)

| Request | Count | Failures | Median | 95th | 99th | Max |
|---|---|---|---|---|---|---|
| reserve | 475 | 187 | 79 | 43000 | 45000 | 45581 |
| check-in | 286 | 0 | 43 | 72 | 4100 | 33924 |
| check-out | 286 | 0 | 39 | 78 | 25000 | 36024 |

**Forecast service, 20 users** (response times in ms)

| Request | Count | Failures | Median | 95th | 99th | Max |
|---|---|---|---|---|---|---|
| /v1/forecast | 8914 | 0 | 3 | 6 | 8 | 39 |

**Pages on a 10 Mbps connection** (`evidence/throttled-pages.csv`)

| Page | Load event (s) | Transferred (KB) |
|---|---|---|
| sign-in | 0.203 | 38.5 |
| register | 0.283 | 39.6 |
| live-occupancy | 0.28 | 45.8 |
| driver-vehicles | 0.233 | 39.2 |
| search-with-results | 0.253 | 41.4 |
| booking-history | 0.342 | 55.6 |
| gate-dashboard | 0.221 | 41.7 |
| payments | 0.323 | 38.9 |
| check-out | 0.284 | 39.4 |
| admin-lots | 0.17 | 39.0 |
| tariffs | 0.289 | 44.6 |
| revenue-report | 0.266 | 39.0 |
| occupancy-report | 0.249 | 39.3 |
| audit-log | 0.307 | 63.8 |
| waive-charges | 0.191 | 41.6 |

- NFR-PERF-01 (search within 1 s at the 95th percentile, 500 slots, 50 users): met, 35 ms.
- NFR-PERF-02 (booking, check-in and check-out within 2 s at the 95th percentile): met after the D-4 fix: reserve 120 ms, check-in 63 ms, check-out 59 ms. Before the fix the reserve 95th percentile was 43 s.
- NFR-PERF-03 (200 concurrent signed-in sessions without load errors): met. 16135 requests, 0 failures. The access log shows no redirects to the sign-in page during the run. Response times rose with the load (search 95th percentile 630 ms with 200 users) but stayed under the 1 s search target.
- NFR-PERF-04 (3 s and 500 KB per page on 10 Mbps): met on all 15 pages. The server was on the same machine, so only bandwidth and 20 ms of latency were simulated.
- NFR-PERF-05 (forecast within 500 ms at the 95th percentile): met, 6 ms.

## 6. Exit criteria (Test Plan Section 5)

| Criterion | Result | Detail |
|---|---|---|
| All High priority test cases pass | Met | 27 High priority cases, all passed. TC-38 ran against a local TLS listener, because there is no staging server. |
| No open S1 or S2 defects | Met, once PR #130 is merged | D-4 (S2) was found and fixed during this testing. The fix is in PR #130 and was re-tested on the test branch. No other defect is open. |
| Coverage targets met | Met | 95.94% line, 91.01% branch; targets 70% and 60% (`evidence/coverage-gate.txt`). |
| Traceability shows every requirement covered | Met, with one case not run | All 81 requirement IDs in the SRS now appear in a test case. TC-45 to TC-51 were added for BR-02, BR-03, BR-05, BR-06, BR-07, BR-09 and NFR-AVL-01. TC-51 (NFR-AVL-01) has not been run, so availability is covered on paper only. |

## 7. Defects

| ID | Severity | Description | Evidence | Status |
|---|---|---|---|---|
| D-1 | S3 | Under 200 concurrent users the Django development server returned HTTP 500 because PostgreSQL ran out of connections, and `compose.yaml` used that server. | `evidence/locust200_failures.csv` | Fixed in PR #129: Compose and the Docker image run Gunicorn. Re-tested: 200 sessions, 0 failures. |
| D-2 | S3 | BR-09 charge waiver was not implemented. | Code search, earlier run | Fixed in PR #129. Re-tested by TC-50. |
| D-3 | S4 | No test case covered BR-02, BR-03, BR-05, BR-06, BR-07, BR-09 or NFR-AVL-01. | Traceability check | Fixed: TC-45 to TC-51 added. |
| D-4 | S2 | Concurrent bookings in one lot all chose the same best slot, then queued on the overlap constraint. Some deadlocked (HTTP 500). Others gave up after 3 attempts with "No slot available" while slots were free. Steps: run `tests/system/locust_booking.py` with 50 users, or the new unit test `test_concurrent_bookings_with_free_slots_all_succeed` (30 drivers, 30 slots), which failed 5 of 5 times before the fix. | `evidence/locust-booking50-before-fix.txt`, `evidence/deadlock-excerpt.txt` | Fixed in PR #130: slot allocation in a lot is serialised with a transaction-level lock. Re-tested: 0 failures, reserve 95th percentile 120 ms. |
| D-5 | S4 | The forecast panel was a `div` with `aria-label` and no role, which axe-core listed for review (aria-prohibited-attr) and screen readers may ignore. | `evidence/axe-sanity.txt` (before and after) | Fixed in PR #130: it is now a labelled `section`. |

## 8. Security validation (Test Plan Section 5.1)

| Requirement | Planned method | What was run | Result |
|---|---|---|---|
| SEC-01 password hashing and policy | Inspect hash format; weak passwords | TC-39 unit tests: PBKDF2 hash stored, weak passwords refused | Pass |
| SEC-02 lockout and rate limit | Scripted failed sign-ins; burst from one IP | TC-03 browser test: 5 wrong passwords, then the correct one gets HTTP 423. Unit tests: the 15-minute window and the 11th attempt in a minute from one IP gets HTTP 429 | Pass |
| SEC-03 server-side role checks | Every endpoint as every role | TC-15, TC-21 and TC-45 tests, the role decorator tests, and browser checks that an attendant gets 403 on the tariff and waiver pages | Pass |
| SEC-04 HTTPS and cookies | Redirect, TLS version, cookie flags on staging | On a local TLS listener (no staging server): TLS 1.2 and 1.3 accepted, TLS 1.1 refused by the server, HSTS sent, cookies Secure, HttpOnly (session) and SameSite=Lax, HTTP redirected with 301. testssl.sh not run | Pass (local) |
| SEC-05 CSRF | State-changing requests without a token | TC-16 test | Pass |
| SEC-06 input validation, injection | Malicious input; ZAP active scan; bandit | TC-17 test. bandit: 0 high, 1 medium (the forecast client opens a URL from the `FORECAST_URL` setting, which only the operator controls), 3 low (`random` used for demo data and simulation, not security). ZAP was not run | Partial |
| SEC-07 audit log | Privileged actions; check entries; try to modify | TC-19, TC-31 and TC-50 tests, audit search tests, browser tests that a tariff change and a charge waiver (with its reason) appear in the audit log | Pass |
| SEC-08 idle timeout, session rotation | Session id before and after sign-in; wait out timeout | Unit tests for the 1800 s age, sliding expiry and key rotation at sign-in. | Pass |
| SEC-09 masking, no secrets in logs | Inspect attendant screen; grep logs | TC-39 browser test: the driver's mobile number appears on none of the six attendant pages for their booking. Server logs searched after all runs: no password and no password hash. TC-22: the reset token is not logged | Pass |
| SEC-10 secrets outside the repository | gitleaks in CI | The Security scans job (gitleaks and pip-audit) passed on PRs #125 to #130 | Pass |

## 9. Open risks

- There is no staging server. TLS was checked on Gunicorn's own TLS listener with a self-signed certificate, not behind nginx with a real certificate, and testssl.sh and a ZAP scan were not run.
- TC-41 (first booking in under 3 minutes by a new user) and TC-51 (99% monthly availability) have not been run.
- The forecast was only checked with the simulated baseline, because the demo data has 20 days of history and the history model needs 4 weeks.
- The D-4 fix serialises bookings per lot. At 50 users the reserve 95th percentile was 120 ms, but a much busier lot would queue for longer. Bookings in different lots do not wait for each other.
