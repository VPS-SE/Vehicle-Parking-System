# Test Case Audit: TC-01 to TC-43

**Project:** Vehicle Parking System (VPS) — Team 10, Section C  
**Reference Deliverables:** VPS Test Plan version 1.0 (`docs/part-1/VPS_Test_Plan.pdf`), Section 16; VPS SRS version 1.0 (`docs/part-1/VPS_SRS.pdf`)  
**Audit Date:** November 4, 2026  
**Auditor:** Test Engineering Team  

---

## 1. Overview & Methodology

Section 16 of the Software Test Plan defines 43 test cases (TC-01 through TC-43) tracing to functional (FR), security (SEC), safety (SAF), business (BR), and non-functional requirements (NFR). This audit verifies which automated test functions currently exercise each test case, determines the test coverage category, and details any deviations, omissions, or gaps.

### Coverage Classification
- **Full:** All specified steps, preconditions, and assertions are automated in the test suite and pass.
- **Partial:** Some steps or conditions are exercised, but specific scenarios, edge cases, or inputs from the STP are missing or unverified.
- **None:** No automated test currently exercises the test case.
- **In development (Sprint 3):** Requirements scheduled for Sprint 3 delivery (issues #19, #33, #35, #57–#63).
- **Manual-system-only:** System-level or non-functional validations requiring external browsers, multi-browser Playwright sweeps, Locust load generators, OWASP ZAP scanners, or physical human trials.

---

## 2. Test Case Audit Table

| TC | Title | Requirements | Level | Automated Tests | Coverage | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-01** | Register a Driver with valid details | FR-AUTH-01, FR-AUTH-02 | System | `tests/test_accounts_views.py::test_registration_signs_in`<br>`tests/test_driver_registration_template.py::test_registration_template_renders_required_fields` | Full | End-to-end driver registration flow verified via Django test client: GET `/accounts/register/`, POST valid driver details (full_name, email, mobile, password), account created with role `Driver`, user signed in to session, redirected to Driver landing page (`/vehicles/`). |
| **TC-02** | Reject duplicate e-mail at registration | FR-AUTH-01 | Integration | `tests/test_accounts_views.py::test_duplicate_email`<br>`tests/test_driver_registration_template.py::test_registration_template_shows_duplicate_email_error` | Partial | Duplicate email rejection with message "An account with this e-mail already exists" is tested for exact string matches. However, case-insensitive duplicate matching (`ASHA@example.com` vs `asha@example.com`) is not enforced in the current service (Finding F1). Unified gap coverage in `tests/test_tc02_duplicate_email.py`. |
| **TC-03** | Lock account after 5 failed sign-ins | SEC-02, FR-AUTH-02 | Integration | `tests/test_accounts_views.py::test_failed_login` | None | Single failed sign-in is tested. 5 failed attempts triggering account lockout, HTTP 423 status code with unlock time, and `auth.failed` audit logging are not implemented in `vps/accounts/views.py` (Finding F2). |
| **TC-04** | Validate vehicle registration number format | FR-VEH-02, FR-VEH-03 | Unit | `tests/test_vehicles.py::test_add_vehicle`<br>`tests/test_vehicles.py::test_valid_formats`<br>`tests/test_vehicles.py::test_vehicle_rules`<br>`tests/test_vehicles.py::test_duplicate_and_inactive` | Partial | Individual validation rules (whitespace stripping, BH series, invalid formats, active duplicate) are tested across `test_vehicles.py`, but the exact 4-step sequence from TC-04 was not unified in a single test. Fully covered in `tests/test_tc04_vehicle_format.py`. |
| **TC-05** | Search excludes blocked and occupied slots | FR-SRCH-01, FR-LOT-03, SAF-01 | Integration | `tests/test_booking_flow.py::test_search_counts_free_eligible_slots`<br>`tests/test_reservations.py::test_free_slots_skip_blocked_occupied_and_ineligible` | Full | Slot search query correctly excludes active maintenance blocks (`SlotBlock`) and overlapping reservations, returning exactly eligible free slots (S1, S4). |
| **TC-06** | Allocate the preferred, nearest slot | FR-ALLOC-01, FR-ALLOC-02, FR-RES-01 | Unit | `tests/test_reservations.py::test_reserve_creates_reserved_booking_with_reference`<br>`tests/test_allocation.py::test_choose_best_slot_prefers_type_then_rank_then_code`<br>`tests/test_booking_flow.py::test_booking_shows_reference_and_slot` | Full | EV booking prefers EV charging slot (EV1) over nearer standard slots; second EV receives lowest distance rank then lowest code standard slot (S1). |
| **TC-07** | Exactly one booking wins the last slot | FR-RES-02, FR-ALLOC-03, NFR-REL-01 | Integration | `tests/test_reservations.py::test_exactly_one_booking_wins_the_last_slot` | Full | Concurrency test executes 50 simultaneous threads across 20 iterations against a single free slot; verifies exactly 1 winner gets a reservation, 49 get `NO_SLOT`, and no database overlap occurs. |
| **TC-08** | Enforce reservation limit and unpaid charges | FR-RES-03 | Integration | `tests/test_reservations.py::test_two_reserved_bookings_block_a_third`<br>`tests/test_reservations.py::test_unpaid_charge_blocks_booking_until_paid` | Full | Step 1 verifies 3rd open booking is refused with `LIMIT_REACHED`. Step 2 verifies cancellation followed by an unpaid no-show charge refuses booking with `UNPAID_CHARGE` until payment is recorded. |
| **TC-09** | Late cancellation records a fee | FR-RES-04 | Unit | `tests/test_cancellation.py::test_tc09_early_cancellation_is_free`<br>`tests/test_cancellation.py::test_tc09_late_cancellation_charges_rs30`<br>`tests/test_cancellation.py::test_exactly_sixty_minutes_ahead_is_free` | Full | R1 cancelled 90 min before start is free with no charge; R2 cancelled 30 min before start incurs Rs 30.00 late cancellation fee; 60 min boundary verified. |
| **TC-10** | Unclaimed reservation expires | FR-RES-05, FR-RES-07 | Integration | `tests/test_expiry.py::test_tc10_expires_only_after_grace_period_and_releases_slot`<br>`tests/test_notifications.py::test_tc10_expiry_queues_an_expired_email` | Full | Advancing clock to 10:14 (within 15-min grace) keeps booking Reserved; advancing to 10:16 marks it Expired, frees slot, creates Rs 50.00 no-show fee, audits the change, and queues an expiry notification email. |
| **TC-11** | Check-in window is enforced | FR-GATE-01, FR-GATE-02 | System | `tests/test_check_in.py::test_check_in_too_early`<br>`tests/test_check_in.py::test_check_in_success_within_window`<br>`tests/test_gate_dashboard.py::test_dashboard_checkin_refuses_early_arrival`<br>`tests/test_gate_dashboard.py::test_dashboard_checkin_activates_reserved_booking` | Full | Arrival at 09:40 (too early) is refused with message naming earliest allowed time (09:45); arrival at 09:50 is accepted, status changes to Active, and entry time is recorded. Verified at service and console UI levels. |
| **TC-12** | Register a walk-in vehicle | FR-GATE-03 | System | `tests/test_walk_in.py::test_tc12_uses_slot_free_until_closing`<br>`tests/test_gate_dashboard.py::test_dashboard_walk_in_registers_vehicle` | Full | Walk-in registration creates Active reservation on slot free until closing time with booking reference; slot is marked occupied. |
| **TC-13** | Compute parking charge with rounding and minimum | FR-BILL-02, FR-GATE-04, FR-BILL-04 | Unit | `tests/test_checkout.py::test_tc13_rounded_parking_charge`<br>`tests/test_printable_receipt.py::test_tc13_printable_receipt_shows_every_required_item` | Full | Stays of 20 min (Rs 40.00, 1h min), 61 min (Rs 60.00, 1.5h), and 130 min (Rs 100.00, 2.5h) tested; printable receipt contains every required FR-BILL-04 field. |
| **TC-14** | Bill overstay at 1.5 times the rate | FR-BILL-03 | Unit | `tests/test_checkout.py::test_tc14_grace_and_overstay_rounding` | Full | Exit at 12:08 (within 10-min grace) incurs 0 overstay; exit at 12:40 bills Rs 80 parking plus Rs 30.00 overstay (30 min rounded at 1.5x rate). |
| **TC-15** | Attendant cannot change a tariff | SEC-03, BR-01 | Integration | `tests/test_tariffs.py::test_tariff_pages_are_admin_only`<br>`tests/test_permissions.py::test_decorator_denies_and_logs_once` | Partial | Existing test verifies HTTP 403 on POST `/lots/tariffs/save/`, but did not verify tariff in database remained unchanged and security denial was logged. Unified gap coverage in `tests/test_tc15_attendant_tariff.py`. |
| **TC-16** | State change without CSRF token is rejected | SEC-05 | Integration | `tests/test_accounts_views.py::test_anonymous_home_and_csrf`<br>`tests/test_lots.py::test_csrf_required` | Partial | CSRF enforcement was tested on lots and logout views, but not on reservation cancellation POST `/reservations/<id>/cancel/`. Unified gap coverage in `tests/test_tc16_csrf.py`. |
| **TC-17** | SQL injection input is handled safely | SEC-06 | System | none | Partial | Step 1 (malicious search query `1 OR 1=1` and vehicle nickname `x'); DROP TABLE vehicle;--`) can be faithfully reproduced via integration test. Step 2 (OWASP ZAP active scan) is manual-system-only. Unified Step 1 coverage in `tests/test_tc17_sql_injection.py`. |
| **TC-18** | Search meets the response-time target | NFR-PERF-01, NFR-PERF-03 | System | none | Manual-system-only | Requires Locust load testing framework running 50 virtual users searching continuously for 10 minutes on a staging database of 500 slots. |
| **TC-19** | Privileged actions are audited | SEC-07, FR-RPT-04 | Integration | `tests/test_tariffs.py::test_create_tariff_is_saved_and_audited`<br>`tests/test_audit.py::test_saved_entries_cannot_be_edited`<br>`tests/test_audit.py::test_entries_cannot_be_deleted` | Partial | Tariff creation auditing and append-only tamper resistance are tested. Step 2 (searching audit log via UI) is part of FR-RPT-04 / issue #60 which is in development (Sprint 3). Unified Step 1 & 3 coverage in `tests/test_tc19_audit_trail.py`. |
| **TC-20** | Search works when the forecast service is down | FR-FCST-03 | Integration | none | In development (Sprint 3) | Forecast service integration and fallback panel ("Forecast not available") are part of issues #62 and #63 in Sprint 3. |
| **TC-21** | Only administrators create staff; deactivation blocks sign-in | FR-AUTH-03, FR-AUTH-05 | Integration | `tests/test_staff_creation.py::test_attendant_cannot_create_staff`<br>`tests/test_staff_creation.py::test_admin_can_create_gate_attendant`<br>`tests/test_staff_management.py::test_admin_can_deactivate_staff`<br>`tests/test_staff_management.py::test_deactivation_invalidates_existing_staff_session`<br>`tests/test_staff_management.py::test_deactivated_staff_cannot_sign_in` | Full | Complete multi-step verification: attendant attempt blocked with 403; admin creates staff; deactivation invalidates session and rejects sign-in. |
| **TC-22** | Password reset link is single-use and expires | FR-AUTH-04, SEC-09 | Integration | `tests/test_password_reset.py::test_tc22_link_resets_password_once`<br>`tests/test_password_reset.py::test_tc22_link_expires_after_30_minutes`<br>`tests/test_password_reset.py::test_tc22_token_is_not_logged` | Full | First reset succeeds; second use refused; link opened after 31 minutes refused; token never appears in application logs. |
| **TC-23** | Accessible slots only for permit holders | FR-AUTH-06, FR-ALLOC-01, SAF-02 | Unit | `tests/test_accessible_permit.py::test_tc23_only_permit_holders_get_accessible_slots` | Full | Driver Q (no permit) sees 0 free slots and cannot reserve; Driver P (permit holder) is allocated Accessible slot H-01. |
| **TC-24** | Vehicle limit and protected removal | FR-VEH-01, FR-VEH-04 | Unit | `tests/test_vehicles.py::test_vehicle_limit`<br>`tests/test_vehicle_removal.py::test_cannot_remove_vehicle_with_reserved_booking`<br>`tests/test_vehicle_removal.py::test_remove_vehicle_without_booking_succeeds` | Full | 6th vehicle addition refused at 5-vehicle limit; removing vehicle with live reservation refused; removing unreserved vehicle succeeds (soft delete). |
| **TC-25** | Create lots and slots with unique codes | FR-LOT-01, FR-LOT-02 | Integration | `tests/test_lots.py::test_tc25_create_lot_d`<br>`tests/test_lots.py::test_create_slot_success`<br>`tests/test_lots.py::test_create_slot_rejects_duplicate_code_in_same_lot`<br>`tests/test_lots.py::test_create_slot_rejects_non_positive_distance_rank` | Full | Admin creates Lot D (06:00 to 23:00); adds slot D-01 (Standard, rank 1); duplicate slot code is rejected; rank 0 is rejected with field messages. |
| **TC-26** | Blocking a slot moves affected reservations | FR-LOT-04, FR-RES-07 | Integration | none | In development (Sprint 3) | Moving reservations off a blocked slot and notifying drivers (issue #33) is in active development for Sprint 3. |
| **TC-27** | Search window validation | FR-SRCH-02 | Unit | `tests/test_booking_flow.py::test_search_window_rules` | Full | Window validation rejects: past start, >7 days ahead, <30 min, >24 hr, and outside operating hours, with messages naming the broken rule. |
| **TC-28** | Live occupancy view refreshes | FR-SRCH-03, FR-RPT-01 | System | none | In development (Sprint 3) | Live occupancy view and automated 30-second refresh (issue #35) are in active development for Sprint 3. |
| **TC-29** | Booking history is paged and ordered | FR-RES-06 | Integration | `tests/test_booking_history.py::test_booking_history_shows_newest_first`<br>`tests/test_booking_history.py::test_booking_history_paginates_twenty_per_page`<br>`tests/test_booking_history.py::test_booking_history_displays_booking_details` | Full | Booking history displays newest first, paginates 20 per page, and presents all required fields and payment statuses. |
| **TC-30** | Record a payment and clear unpaid charges | FR-GATE-05, FR-BILL-05, BR-04 | Integration | `tests/test_payments.py::test_tc30_payment_unblocks_next_reservation`<br>`tests/test_driver_unpaid_balance_template.py::test_tc30_home_page_shows_only_unpaid_charges` | Full | Unpaid no-show fee shown on Driver home; attendant records payment; balance clears to Rs 0.00; payment audited; driver can book again. |
| **TC-31** | Manual time correction is limited and audited | FR-GATE-06, SAF-03, SEC-07 | Integration | `tests/test_time_correction.py::test_tc31_step1_past_exit_is_billed_and_audited_with_reason`<br>`tests/test_time_correction.py::test_tc31_step2_exit_more_than_24_hours_ago_is_refused`<br>`tests/test_time_correction.py::test_tc31_step3_correction_without_reason_is_refused` | Full | Exit time 2 hours ago with reason is accepted and audited; exit time 25 hours ago (>24h) is refused; correction without reason is refused. |
| **TC-32** | Reallocate when the reserved slot is still occupied | FR-GATE-07 | Integration | `tests/test_reallocation.py::test_tc32_occupied_slot_is_swapped_for_a_free_one`<br>`tests/test_check_in.py::test_check_in_reallocates_when_slot_occupied` | Full | Check-in when booked slot S1 is occupied reallocates booking to free slot S2 and displays new slot code on attendant console. |
| **TC-33** | Tariff in force at entry is used | FR-BILL-01, BR-08 | Unit | `tests/test_tariffs.py::test_tc33_charge_uses_tariff_in_force_at_entry`<br>`tests/test_checkout.py::test_tc33_uses_tariff_at_entry` | Full | New tariff effective today does not alter charge for vehicle entered yesterday (billed at Rs 40/h); vehicle entering today is billed at Rs 50/h. |
| **TC-34** | Occupancy and revenue reports export to CSV | FR-RPT-02, FR-RPT-03 | Integration | none | In development (Sprint 3) | Occupancy and revenue reports and CSV export are part of issues #57, #58, #59 in Sprint 3. |
| **TC-35** | Forecast bands and baseline label | FR-FCST-01, FR-FCST-02 | Unit | none | In development (Sprint 3) | Forecast probability bands (Low, Medium, High) and "Estimate" baseline label are issue #61 in Sprint 3. |
| **TC-36** | Booking, gate and forecast response times | NFR-PERF-02, NFR-PERF-05 | System | none | Manual-system-only | Requires Locust load testing suite mixing reservations, check-ins, check-outs across 50 users and 1,000 forecast calls. |
| **TC-37** | Page weight and load time | NFR-PERF-04 | System | none | Manual-system-only | Requires browser network throttling (10 Mbps) to verify page transfer size (<=500 KB) and load latency (<=3s). |
| **TC-38** | TLS, cookie flags and idle timeout | SEC-04, SEC-08 | System | none | Manual-system-only | Requires staging deployment behind nginx reverse proxy with HTTPS redirection, TLS 1.2+, cookie flag inspection, and 31-minute idle timeout. |
| **TC-39** | Password storage and data masking | SEC-01, SEC-09 | Integration | none | Partial | Password storage starting with `pbkdf2_sha256$` and weak password rejection can be tested at integration level. Attendant screen mobile masking (`3210`) is not implemented on the console. Covered Steps 1-2 in `tests/test_tc39_password_storage.py`. |
| **TC-40** | No secrets in the repository | SEC-10 | System | `tests/test_settings.py::test_production_settings_require_secret` | Manual-system-only | Settings require environment secrets; verified in CI via gitleaks secret scanning step (`.github/workflows/ci.yml`). |
| **TC-41** | First-time booking within 3 minutes | NFR-USE-01 | Acceptance | none | Manual-system-only | Usability acceptance test requiring human trials with 5 classmates completing booking in <3 minutes across <=4 screens. |
| **TC-42** | Small screens and colour contrast | NFR-USE-02, NFR-PRT-01 | System | `tests/test_base_template.py::test_base_template_includes_htmx_and_responsive_styles` | Manual-system-only | Responsive viewport meta is unit tested. Full cross-browser rendering at 360px viewport and axe-core WCAG AA contrast checks require Playwright. |
| **TC-43** | Coverage and lint gates in CI | NFR-MNT-01, NFR-MNT-02, NFR-TST-01 | System | `tests/test_check_coverage.py::test_coverage_gate`<br>`tests/test_check_coverage.py::test_custom_thresholds`<br>`tests/test_check_coverage.py::test_invalid_report_fails_closed` | Manual-system-only | Coverage gate script (`scripts/check_coverage.py`) enforcing 70% line and 60% branch rate is unit tested. Full PR gate and branch protection are enforced in GitHub CI. |

---

## 3. Summary of Coverage Categories

| Category | Count | Test Cases |
| :--- | :---: | :--- |
| **Full** | 22 | TC-01, TC-05, TC-06, TC-07, TC-08, TC-09, TC-10, TC-11, TC-12, TC-13, TC-14, TC-21, TC-22, TC-23, TC-24, TC-25, TC-27, TC-29, TC-30, TC-31, TC-32, TC-33 |
| **Partial** | 6 | TC-02, TC-04, TC-15, TC-16, TC-17, TC-19 |
| **None** | 2 | TC-03, TC-39 |
| **In development (Sprint 3)** | 5 | TC-20, TC-26, TC-28, TC-34, TC-35 |
| **Manual-system-only** | 8 | TC-18, TC-36, TC-37, TC-38, TC-40, TC-41, TC-42, TC-43 |
| **Total** | **43** | **TC-01 to TC-43** |

---

## 4. Verification

### Test Suite Execution
- **Command:** `./run-tests.sh -q`
- **Output:**
  ```text
  604 passed, 7 xfailed in 74.04s (0:01:14)
  ```

### Linter Execution
- **Command:** `./.venv/bin/ruff check .`
- **Output:**
  ```text
  All checks passed!
  ```
