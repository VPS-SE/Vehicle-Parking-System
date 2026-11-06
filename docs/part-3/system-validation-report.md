# System Validation Report

Vehicle Parking System, Team 10, Section C. Part 3. System testing on 5 November 2026, against `main` with every Sprint 3 feature merged.

## 1. Summary

Of the 44 test cases in the Test Plan, 37 passed, 6 passed in part and 1 was not run. None failed. Most "Partial" results have a step that needs something we did not have locally: the staging server with TLS, a 10 Mbps link, a booking and gate load script, or an accessibility checker. TC-39 is partial because its mobile-masking step has no automated check. Two of the four exit criteria are met: coverage, and no open S1 or S2 defects. The High priority criterion is not fully met (TC-38, TC-39). The traceability criterion is not met, because 7 SRS requirements have no test case. One of them, the charge waiver (BR-09), is also not implemented (Section 7).

## 2. Environment

- Web application: Django 5.2.18 on Python 3.13.14, at http://127.0.0.1:8100 (development server) and http://127.0.0.1:8102 (Gunicorn, 8 sync workers) for the load tests.
- Database: PostgreSQL 16.15 in Docker, `max_connections` 100. Seeded with `manage.py seed_demo_data --seed 2026`: 500 slots, 120 drivers, 4145 reservations over 30 days, 2696 charges.
- Forecast service: FastAPI at http://127.0.0.1:8101. Model trained by `python -m forecast.train.train` through the read-only role. The demo data has 20 days of history, so the trainer used the simulated baseline.
- Test accounts: one admin, one attendant and one driver with a known password. The browser tests register their own drivers.
- Tools: Playwright 1.64.1 (Chromium headless), Locust 2.47.0.
- Not the staging server in Test Plan Section 6: a single laptop, no nginx, no TLS.

## 3. Runs

| Run | Command | Started | Result | Raw output |
|---|---|---|---|---|
| Unit and integration | `./run-tests.sh`, `./run-coverage.sh` | 18:19 and 20:12 | 723 passed, 0 failed (both runs) | `evidence/junit.xml`, `evidence/coverage-run.txt` |
| Forecast service | `./run-forecast-tests.sh` | 18:21 | 16 passed | `evidence/forecast-junit.xml` |
| Browser (system) tests | `./run-system-tests.sh` | 20:34 | 11 passed, 0 failed | `evidence/system-junit.xml` |
| Load, 20 users, dev server | Locust, 60 s | 20:37 (file written 20:38) | 0 failures | `evidence/locust_stats.csv` |
| Load, 50 users, dev server | Locust, 60 s | 20:51 | 0 failures | `evidence/locust50_stats.csv` |
| Load, 200 users, dev server | Locust, 90 s | 20:52 | 644 failures | `evidence/locust200_*.csv` |
| Load, 50 and 200 users, Gunicorn | Locust, 60 s and 90 s | 20:55 and 20:56 | 0 failures | `evidence/locust-gunicorn*_stats.csv` |
| Load, forecast service, 20 users | Locust, 60 s | 20:54 | 0 failures | `evidence/locust-forecast_stats.csv` |

The browser tests are in `tests/system/test_system.py` and the load scripts in `tests/system/locustfile.py` and `tests/system/locust_forecast.py`. The browser tests and the first load script were written by the agy test agent; I wrote the forecast load script. Every number in this report is copied from the files above.

## 4. Test case results

Pass: every test mapped to the case ran and passed, and together they cover the case's steps. Partial: the tests passed, but at least one step could not be run here (explained in the notes). Not run: nothing was executed. The test functions for each case are listed in `evidence/tc-mapping.txt`.

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
| TC-18 | Search meets the response-time target | NFR-PERF-01, NFR-PERF-03 | Non-functional (performance) / System / Medium | **Partial** | Load tests, Section 5 | NFR-PERF-01 met: with 50 users the 95th percentile for search was 32 ms on Gunicorn (8 workers) and 130 ms on the Django development server; the target is 1 s. NFR-PERF-03 only partly shown: 200 users on Gunicorn made 16221 requests with 0 failures, but all users shared one signed-in session, so 200 separate sessions were not tested. On the development server, 200 users gave 644 failures out of 1796 (HTTP 500: PostgreSQL ran out of connections, one per request thread). |
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
| TC-36 | Booking, gate and forecast response times | NFR-PERF-02, NFR-PERF-05 | Non-functional (performance) / System / Medium | **Partial** | Load tests, Section 5 | NFR-PERF-05 met: the forecast service answered 8914 requests from 20 users with a 95th percentile of 6 ms (target 500 ms). NFR-PERF-02 not measured: the load test did not create bookings, check in or check out. |
| TC-37 | Page weight and load time | NFR-PERF-04 | Non-functional (performance) / System / Low | **Partial** | Load tests, Section 5 | Average HTML size measured by Locust: search page 23625 bytes, occupancy page 30352 bytes. CSS is inline and htmx is the only script. Load time on a 10 Mbps connection was not measured. |
| TC-38 | TLS, cookie flags and idle timeout | SEC-04, SEC-08 | Security / System / High | **Partial** | 7 tests, 7 passed: `test_system.py`, `test_fix_f7_session_security.py` | Cookies are HttpOnly and SameSite=Lax in the browser test. The 30-minute idle timeout, session key rotation and the Secure flag under DEBUG=False are covered by unit tests. TLS and the HTTP-to-HTTPS redirect need the staging server and were not testable here. |
| TC-39 | Password storage and data masking | SEC-01, SEC-09 | Security / Integration / High | **Partial** | 1 test, 1 passed: `test_tc39_password_storage.py` | The unit test checks the PBKDF2 hash and that weak passwords are refused. The mobile number masking step was not tested. A search of the templates found that no attendant screen shows a driver's mobile number at all, so there is nothing to mask, but nothing checks this automatically. |
| TC-40 | No secrets in the repository | SEC-10 | Security / System / Medium | **Pass** | 1 test, 1 passed: `test_settings.py` | Unit test checks that settings refuse to start without DJANGO_SECRET_KEY. The gitleaks scan in CI's Security scans job passed on PRs #125, #126 and #127. |
| TC-41 | First-time booking within 3 minutes | NFR-USE-01 | Non-functional (usability) / Acceptance / Medium | **Not run** | - | Needs a timed trial with people; not done. |
| TC-42 | Small screens and colour contrast | NFR-USE-02, NFR-PRT-01 | Non-functional (usability) / System / Low | **Partial** | 1 test, 1 passed: `test_system.py` | Playwright ran the driver flow at 360 px with no horizontal scroll. The axe-core colour contrast check was not run. |
| TC-43 | Coverage and lint gates in CI | NFR-MNT-01, NFR-MNT-02, NFR-TST-01 | Non-functional (maintainability) / System / Medium | **Pass** | 18 tests, 18 passed: `test_check_coverage.py`, `test_tc43_quality_gates.py` | Unit tests check the gate thresholds and CI configuration. Branch protection on main was seen in practice on 5 Nov: merging PR #125 without approval was refused ("the base branch policy prohibits the merge"). |
| TC-44 | Code review findings are fixed and regression-tested | FR-AUTH-01, FR-SRCH-01, FR-GATE-06, SEC-02, SEC-03, SEC-04, SEC-07, SEC-08 | Static (code review) / Integration / High | **Pass** | 62 tests, 62 passed: `test_fix_f1_email_case_insensitivity.py`, `test_fix_f2_account_lockout.py`, `test_fix_f3_admin_time_correction.py`, `test_fix_f4_audit_slot_blocks_and_staff.py`, `test_fix_f5_notifications.py`, `test_fix_f6_unpaid_total.py`, `test_fix_f7_session_security.py`, `test_fix_g1_staff_search.py`, `test_review_findings.py`, `test_review_findings_2.py` |  |

## 5. Performance

Signed-in drivers searched availability with real parameters (three requests in four) and loaded the live occupancy page (one in four). Every simulated user shared one driver session.


**50 users, Django development server** (response times in ms)

| Request | Count | Failures | Median | 95th | 99th | Max |
|---|---|---|---|---|---|---|
| /reservations/search/ | 2042 | 0 | 41 | 130 | 170 | 321 |
| /lots/occupancy/ | 655 | 0 | 55 | 140 | 200 | 299 |
| Aggregated | 2697 | 0 | 45 | 130 | 170 | 321 |

**50 users, Gunicorn** (response times in ms)

| Request | Count | Failures | Median | 95th | 99th | Max |
|---|---|---|---|---|---|---|
| /reservations/search/ | 2121 | 0 | 26 | 32 | 78 | 194 |
| /lots/occupancy/ | 679 | 0 | 36 | 43 | 75 | 174 |
| Aggregated | 2800 | 0 | 27 | 40 | 76 | 194 |

**200 users, Gunicorn** (response times in ms)

| Request | Count | Failures | Median | 95th | 99th | Max |
|---|---|---|---|---|---|---|
| /reservations/search/ | 12201 | 0 | 31 | 85 | 140 | 207 |
| /lots/occupancy/ | 4020 | 0 | 43 | 100 | 160 | 224 |
| Aggregated | 16221 | 0 | 35 | 91 | 140 | 224 |

**200 users, Django development server** (response times in ms)

| Request | Count | Failures | Median | 95th | 99th | Max |
|---|---|---|---|---|---|---|
| /reservations/search/ | 1337 | 481 | 3700 | 20000 | 38000 | 39590 |
| /lots/occupancy/ | 459 | 163 | 3200 | 17000 | 32000 | 36155 |
| Aggregated | 1796 | 644 | 3600 | 19000 | 37000 | 39590 |

**Forecast service, 20 users** (ms)

| Request | Count | Failures | Median | 95th | 99th | Max |
|---|---|---|---|---|---|---|
| /v1/forecast | 8914 | 0 | 3 | 6 | 8 | 39 |

- NFR-PERF-01 (search within 1 s at the 95th percentile, 500 slots, 50 users): met. The 95th percentile was 32 ms on Gunicorn and 130 ms on the development server.
- NFR-PERF-03 (200 concurrent signed-in sessions without load errors): not fully shown. On Gunicorn, 200 users made 16221 requests with 0 failures, but they all used one session. On the development server, 644 of 1796 requests failed with HTTP 500, because each request thread opened its own database connection and PostgreSQL refused new clients after 100 ("sorry, too many clients already" in the server log).
- NFR-PERF-05 (forecast within 500 ms at the 95th percentile): met. The 95th percentile was 6 ms.
- NFR-PERF-02 (booking and check-in or check-out within 2 s): not measured.

## 6. Exit criteria (Test Plan Section 5)

| Criterion | Result | Detail |
|---|---|---|
| All High priority test cases pass | Not fully met | 21 High priority cases; all passed except TC-38, TC-39. In TC-38 the cookie and timeout steps passed, but TLS and the HTTPS redirect need the staging server. TC-39 has no automated check of mobile masking. |
| No open S1 or S2 defects | Met | No S1 or S2 defects are open. The ten code review findings (F1-F7, G1-G3) are fixed. The open defects in Section 7 are S3 and S4. |
| Coverage targets met | Met | 96.13% line, 91.42% branch; targets 70% and 60% (`evidence/coverage-gate.txt`). |
| Traceability shows every requirement covered | Not met | 74 of the 81 requirement IDs in the SRS appear in some test case. No test case lists BR-02, BR-03, BR-05, BR-06, BR-07, BR-09 or NFR-AVL-01. Most of these business rules are checked indirectly by TC-08, TC-09, TC-10, TC-13 and TC-14, which test the same behaviour. BR-09 (an admin may waive a charge with a written reason) is neither implemented nor tested. NFR-AVL-01 (99% availability) needs a monitored deployment. |

## 7. Defects and gaps found

| ID | Severity | Description | Evidence | Status |
|---|---|---|---|---|
| D-1 | S3 | Under 200 concurrent users the Django development server returns HTTP 500, because PostgreSQL runs out of connections. `compose.yaml` runs the web service with `runserver`, so a Compose deployment has the same limit. Gunicorn with 8 workers served the same load with no errors. | `evidence/locust200_failures.csv` | Open. Use Gunicorn outside development. |
| D-2 | S3 | BR-09 charge waiver is not implemented: there is no page or service to waive a charge with a reason. | Code search for "waive" finds nothing in `vps/` or `templates/` | Open |
| D-3 | S4 | No test case covers BR-02, BR-03, BR-05, BR-06, BR-07 and NFR-AVL-01 by ID; see Section 6. | Traceability check | Open |

## 8. Security validation (Test Plan Section 5.1)

| Requirement | Planned method | What was run | Result |
|---|---|---|---|
| SEC-01 password hashing and policy | Inspect hash format; weak passwords | TC-39 unit tests: PBKDF2 hash stored, weak passwords refused | Pass |
| SEC-02 lockout and rate limit | Scripted failed sign-ins; burst from one IP | TC-03 browser test: 5 wrong passwords, then the correct one gets HTTP 423. Unit tests: the 15-minute window and the 11th attempt in a minute from one IP gets HTTP 429 | Pass |
| SEC-03 server-side role checks | Every endpoint as every role | TC-15 and TC-21 tests and the role decorator tests; browser test for the attendant on the tariff page (403) | Pass |
| SEC-04 HTTPS and cookies | Redirect, TLS version, cookie flags on staging | HttpOnly and SameSite=Lax checked in the browser; Secure flag and redirect settings checked in unit tests with DEBUG=False. testssl.sh not run: no staging server | Partial |
| SEC-05 CSRF | State-changing requests without a token | TC-16 test | Pass |
| SEC-06 input validation, injection | Malicious input; ZAP active scan; bandit | TC-17 test. ZAP and bandit were not run | Partial |
| SEC-07 audit log | Privileged actions; check entries; try to modify | TC-19 and TC-31 tests, audit search tests, browser test of a tariff change found in the audit log | Pass |
| SEC-08 idle timeout, session rotation | Session id before and after sign-in; wait out timeout | Unit tests for the 1800 s age, sliding expiry and key rotation at sign-in. The 30-minute wait was not done in a browser | Pass |
| SEC-09 masking, no secrets in logs | Inspect attendant screen; grep logs | TC-22 test: the reset token is not logged. No attendant template shows a mobile number, which was found by searching the templates; no automated check of the masking | Partial |
| SEC-10 secrets outside the repository | gitleaks in CI | The Security scans job (gitleaks and pip-audit) passed on PRs #125, #126 and #127 | Pass |

## 9. Open risks

- Nothing was run on the staging setup in Test Plan Section 6: TLS, nginx and testssl.sh. TC-38 and SEC-04 stay partial until it exists.
- The forecast was only checked with the simulated baseline, because the demo data has 20 days of history and the history model needs 4 weeks. The unit tests check that the history model learns a busy hour from synthetic stays, not from real bookings.
- Load tests used one shared driver session and only read requests. Bookings, check-ins and check-outs under load (NFR-PERF-02) were not measured.
