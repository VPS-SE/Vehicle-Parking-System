# Unit Test Report

Vehicle Parking System, Team 10, Section C. Part 3. Tests run on 5 November 2026.

## Scope

Unit and integration tests for the Django application (`tests/`) and for the forecast service (`forecast/tests/`). They call services, views and templates through pytest and the Django test client, on a real PostgreSQL database. Browser and load tests are in the System Validation Report.

## Environment

- Application tests: Django 5.2.18, Python 3.13.14, PostgreSQL 16.15, pytest 9.1.1, pytest-django 4.14.0, coverage 7.16.2. Local PostgreSQL 16 in Docker, with `btree_gist` enabled.
- Forecast tests: FastAPI 0.162.0, scikit-learn 1.9.1, Python 3.13.14.
- CI runs the same suites on every pull request, on ubuntu-latest with Python 3.12.

## Runs

| Suite | Command | Started | Tests | Passed | Failed | Errors | Skipped | Time (s) | Raw output |
|---|---|---|---|---|---|---|---|---|---|
| Application | `./run-tests.sh -q --junitxml=docs/part-3/evidence/junit.xml` | 2026-11-05 18:19 | 723 | 723 | 0 | 0 | 0 | 112.2 | `evidence/junit.xml` |
| Forecast service | `./run-forecast-tests.sh -q --junitxml=...` | 2026-11-05 18:21 | 16 | 16 | 0 | 0 | 0 | 1.8 | `evidence/forecast-junit.xml` |

The coverage run at 20:12 ran the application suite again and also got 723 passed (`evidence/coverage-run.txt`). No test is marked xfail or skipped. The ten code review findings (F1 to F7, G1 to G3) were fixed before this run, so their reproduction tests now run as ordinary tests.

## Results by test file

| Test file | Tests | Passed | Failed |
|---|---|---|---|
| `tests/test_accessible_permit.py` | 13 | 13 | 0 |
| `tests/test_accounts_views.py` | 24 | 24 | 0 |
| `tests/test_allocation.py` | 14 | 14 | 0 |
| `tests/test_audit.py` | 5 | 5 | 0 |
| `tests/test_audit_search.py` | 6 | 6 | 0 |
| `tests/test_base_template.py` | 2 | 2 | 0 |
| `tests/test_booking_flow.py` | 19 | 19 | 0 |
| `tests/test_booking_history.py` | 8 | 8 | 0 |
| `tests/test_booking_history_template.py` | 3 | 3 | 0 |
| `tests/test_cancellation.py` | 12 | 12 | 0 |
| `tests/test_check_coverage.py` | 8 | 8 | 0 |
| `tests/test_check_in.py` | 9 | 9 | 0 |
| `tests/test_checkout.py` | 43 | 43 | 0 |
| `tests/test_driver_registration_template.py` | 3 | 3 | 0 |
| `tests/test_driver_unpaid_balance_template.py` | 5 | 5 | 0 |
| `tests/test_environment.py` | 19 | 19 | 0 |
| `tests/test_expiry.py` | 12 | 12 | 0 |
| `tests/test_factories_and_seed.py` | 4 | 4 | 0 |
| `tests/test_fix_f1_email_case_insensitivity.py` | 5 | 5 | 0 |
| `tests/test_fix_f2_account_lockout.py` | 8 | 8 | 0 |
| `tests/test_fix_f3_admin_time_correction.py` | 5 | 5 | 0 |
| `tests/test_fix_f4_audit_slot_blocks_and_staff.py` | 5 | 5 | 0 |
| `tests/test_fix_f5_notifications.py` | 7 | 7 | 0 |
| `tests/test_fix_f6_unpaid_total.py` | 7 | 7 | 0 |
| `tests/test_fix_f7_session_security.py` | 6 | 6 | 0 |
| `tests/test_fix_g1_staff_search.py` | 9 | 9 | 0 |
| `tests/test_forecast_panel.py` | 8 | 8 | 0 |
| `tests/test_gate_dashboard.py` | 17 | 17 | 0 |
| `tests/test_gate_dashboard_template.py` | 4 | 4 | 0 |
| `tests/test_healthz.py` | 4 | 4 | 0 |
| `tests/test_login_template.py` | 2 | 2 | 0 |
| `tests/test_lots.py` | 91 | 91 | 0 |
| `tests/test_models.py` | 20 | 20 | 0 |
| `tests/test_notifications.py` | 11 | 11 | 0 |
| `tests/test_occupancy_report.py` | 11 | 11 | 0 |
| `tests/test_password_reset.py` | 5 | 5 | 0 |
| `tests/test_payments.py` | 29 | 29 | 0 |
| `tests/test_permissions.py` | 17 | 17 | 0 |
| `tests/test_printable_receipt.py` | 7 | 7 | 0 |
| `tests/test_printable_receipt_template.py` | 3 | 3 | 0 |
| `tests/test_reallocation.py` | 8 | 8 | 0 |
| `tests/test_reservation_confirmation_template.py` | 2 | 2 | 0 |
| `tests/test_reservations.py` | 28 | 28 | 0 |
| `tests/test_revenue_report.py` | 7 | 7 | 0 |
| `tests/test_review_findings.py` | 7 | 7 | 0 |
| `tests/test_review_findings_2.py` | 3 | 3 | 0 |
| `tests/test_roles.py` | 29 | 29 | 0 |
| `tests/test_settings.py` | 8 | 8 | 0 |
| `tests/test_slot_blocks.py` | 5 | 5 | 0 |
| `tests/test_slot_search_template.py` | 2 | 2 | 0 |
| `tests/test_staff_creation.py` | 5 | 5 | 0 |
| `tests/test_staff_management.py` | 10 | 10 | 0 |
| `tests/test_tariff_management_template.py` | 3 | 3 | 0 |
| `tests/test_tariffs.py` | 11 | 11 | 0 |
| `tests/test_tc02_duplicate_email.py` | 1 | 1 | 0 |
| `tests/test_tc04_vehicle_format.py` | 1 | 1 | 0 |
| `tests/test_tc15_attendant_tariff.py` | 1 | 1 | 0 |
| `tests/test_tc16_csrf.py` | 1 | 1 | 0 |
| `tests/test_tc17_sql_injection.py` | 1 | 1 | 0 |
| `tests/test_tc19_audit_trail.py` | 1 | 1 | 0 |
| `tests/test_tc26_block_moves.py` | 6 | 6 | 0 |
| `tests/test_tc28_occupancy.py` | 5 | 5 | 0 |
| `tests/test_tc39_password_storage.py` | 1 | 1 | 0 |
| `tests/test_tc43_quality_gates.py` | 10 | 10 | 0 |
| `tests/test_time_correction.py` | 14 | 14 | 0 |
| `tests/test_vehicle_registration_template.py` | 3 | 3 | 0 |
| `tests/test_vehicle_removal.py` | 7 | 7 | 0 |
| `tests/test_vehicles.py` | 16 | 16 | 0 |
| `tests/test_walk_in.py` | 37 | 37 | 0 |
| `forecast/tests/test_forecast.py` | 16 | 16 | 0 |

## Test cases covered

Each Test Plan case below has unit or integration tests that ran and passed. The full list of test functions per case is in `evidence/tc-mapping.txt`, generated from the JUnit files.

| TC | Title | Unit and integration tests | Passed |
|---|---|---|---|
| TC-01 | Register a Driver with valid details | `tests/test_accounts_views.py`, `tests/test_driver_registration_template.py` | 5 tests, 5 passed |
| TC-02 | Reject duplicate e-mail at registration | `tests/test_fix_f1_email_case_insensitivity.py`, `tests/test_tc02_duplicate_email.py` | 7 tests, 7 passed |
| TC-03 | Lock account after 5 failed sign-ins | `tests/test_fix_f2_account_lockout.py`, `tests/test_review_findings.py` | 10 tests, 10 passed |
| TC-04 | Validate vehicle registration number format | `tests/test_tc04_vehicle_format.py`, `tests/test_vehicles.py` | 5 tests, 5 passed |
| TC-05 | Search excludes blocked and occupied slots | `tests/test_booking_flow.py`, `tests/test_reservations.py` | 3 tests, 3 passed |
| TC-06 | Allocate the preferred, nearest slot | `tests/test_allocation.py`, `tests/test_reservations.py` | 3 tests, 3 passed |
| TC-07 | Exactly one booking wins the last slot | `tests/test_reservations.py` | 20 tests, 20 passed |
| TC-08 | Enforce reservation limit and unpaid charges | `tests/test_reservations.py` | 2 tests, 2 passed |
| TC-09 | Late cancellation records a fee | `tests/test_cancellation.py` | 12 tests, 12 passed |
| TC-10 | Unclaimed reservation expires | `tests/test_expiry.py`, `tests/test_notifications.py` | 2 tests, 2 passed |
| TC-11 | Check-in window is enforced | `tests/test_check_in.py` | 2 tests, 2 passed |
| TC-12 | Register a walk-in vehicle | `tests/test_walk_in.py` | 1 test, 1 passed |
| TC-13 | Compute parking charge with rounding and minimum | `tests/test_checkout.py`, `tests/test_printable_receipt.py` | 4 tests, 4 passed |
| TC-14 | Bill overstay at 1.5 times the rate | `tests/test_checkout.py` | 5 tests, 5 passed |
| TC-15 | Attendant cannot change a tariff | `tests/test_tariffs.py`, `tests/test_tc15_attendant_tariff.py` | 4 tests, 4 passed |
| TC-16 | State change without CSRF token is rejected | `tests/test_tc16_csrf.py` | 1 test, 1 passed |
| TC-17 | SQL injection input is handled safely | `tests/test_tc17_sql_injection.py` | 1 test, 1 passed |
| TC-19 | Privileged actions are audited | `tests/test_audit.py`, `tests/test_audit_search.py`, `tests/test_tc19_audit_trail.py` | 13 tests, 13 passed |
| TC-20 | Search works when the forecast service is down | `tests/test_forecast_panel.py` | 2 tests, 2 passed |
| TC-21 | Only administrators create staff; deactivation blocks sign-in | `tests/test_staff_creation.py`, `tests/test_staff_management.py` | 15 tests, 15 passed |
| TC-22 | Password reset link is single-use and expires | `tests/test_password_reset.py` | 3 tests, 3 passed |
| TC-23 | Accessible slots only for permit holders | `tests/test_accessible_permit.py` | 1 test, 1 passed |
| TC-24 | Vehicle limit and protected removal | `tests/test_vehicle_removal.py`, `tests/test_vehicles.py` | 8 tests, 8 passed |
| TC-25 | Create lots and slots with unique codes | `tests/test_lots.py` | 14 tests, 14 passed |
| TC-26 | Blocking a slot moves affected reservations | `tests/test_tc26_block_moves.py` | 6 tests, 6 passed |
| TC-27 | Search window validation | `tests/test_booking_flow.py` | 6 tests, 6 passed |
| TC-28 | Live occupancy view refreshes | `tests/test_tc28_occupancy.py` | 6 tests, 6 passed |
| TC-29 | Booking history is paged and ordered | `tests/test_booking_history.py` | 8 tests, 8 passed |
| TC-30 | Record a payment and clear unpaid charges | `tests/test_driver_unpaid_balance_template.py`, `tests/test_payments.py` | 3 tests, 3 passed |
| TC-31 | Manual time correction is limited and audited | `tests/test_time_correction.py` | 4 tests, 4 passed |
| TC-32 | Reallocate when the reserved slot is still occupied | `tests/test_check_in.py`, `tests/test_reallocation.py` | 2 tests, 2 passed |
| TC-33 | Tariff in force at entry is used | `tests/test_checkout.py`, `tests/test_tariffs.py` | 3 tests, 3 passed |
| TC-34 | Occupancy and revenue reports export to CSV | `tests/test_occupancy_report.py`, `tests/test_revenue_report.py` | 19 tests, 19 passed |
| TC-35 | Forecast bands and baseline label | `forecast/tests/test_forecast.py`, `tests/test_forecast_panel.py` | 12 tests, 12 passed |
| TC-38 | TLS, cookie flags and idle timeout | `tests/test_fix_f7_session_security.py` | 7 tests, 7 passed |
| TC-39 | Password storage and data masking | `tests/test_tc39_password_storage.py` | 1 test, 1 passed |
| TC-40 | No secrets in the repository | `tests/test_settings.py` | 1 test, 1 passed |
| TC-43 | Coverage and lint gates in CI | `tests/test_check_coverage.py`, `tests/test_tc43_quality_gates.py` | 18 tests, 18 passed |
| TC-44 | Code review findings are fixed and regression-tested | `tests/test_fix_f1_email_case_insensitivity.py`, `tests/test_fix_f2_account_lockout.py`, `tests/test_fix_f3_admin_time_correction.py`, `tests/test_fix_f4_audit_slot_blocks_and_staff.py`, `tests/test_fix_f5_notifications.py`, `tests/test_fix_f6_unpaid_total.py`, `tests/test_fix_f7_session_security.py`, `tests/test_fix_g1_staff_search.py`, `tests/test_review_findings.py`, `tests/test_review_findings_2.py` | 62 tests, 62 passed |

## Failures

None. Both suites passed with 0 failures and 0 errors.

