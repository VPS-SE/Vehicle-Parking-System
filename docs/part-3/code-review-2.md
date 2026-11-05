# Code Review 2: Extended Audit & Regression Analysis

**Project:** Vehicle Parking System (Django 5.2 + PostgreSQL 16) — Team 10, Section C  
**Deliverable:** Part-3 Extended Code Quality, Regression & Security Review  
**Branch:** `fix/review-findings` (commit `1acd5c4`)  
**Scope:** Verification of fixes F1–F7 (`b962c35..HEAD`), comprehensive audit of `vps/` (accounts, allocation, audit, billing, gate, lots, notifications, reports, reservations, vehicles), `templates/`, and project settings.  
**Review Date:** November 5, 2026  
**Auditor:** Test Engineering Team  

---

## 1. Executive Summary

An extended manual and automated code review of the Vehicle Parking System was conducted following the implementation of fixes for findings F1 through F7. The review evaluated the completeness and correctness of earlier fixes, analyzed git history (`b962c35..HEAD`), and performed a systematic audit across all application layers, models, services, views, and templates.

The audit verified that fixes F1 through F7 have been implemented cleanly, address their target failure modes, and do not introduce database constraint regressions or migration conflicts. Concurrency mechanisms (PostgreSQL range exclusion constraints with GiST, transactional advisory locks, and row locks), financial decimal quantization, time-zone localization, and log hygiene (SEC-09) were verified to be sound.

Three new concrete findings (ranked G1 to G3) were discovered and confirmed with strict reproduction tests in `tests/test_review_findings_2.py`:
- **High Severity (1 finding):** G1 — Gate Attendants and Lot Administrators are denied the ability to search parking slot availability (`vps/reservations/forms.py:20`, `vps/reservations/views.py:29-54`).
- **Medium Severity (1 finding):** G2 — Lot Administrators are denied permission to record outage exit times due to an incomplete F3 fix (`vps/gate/services.py:346-347`, `vps/gate/views.py:86-88`).
- **Low Severity (1 finding):** G3 — Staff creation view redirects to an orphaned template that fails to render success flash messages and navigation headers (`templates/accounts/create_staff.html:1-41`, `vps/accounts/views.py:135-141`).

All three findings are demonstrated by reproduction tests marked `@pytest.mark.xfail(strict=True)`.

---

## 2. Review of Sound Areas and Verification of Fixes F1–F7

### Verification of Previous Findings (F1–F7)

1. **F1: Case-Insensitive Email Validation and Migrations (`vps/accounts/`):**
   - **Implementation:** `UserManager.normalize_email` lowercases email addresses (`vps/accounts/models.py:12-15`). `User` defines `UniqueConstraint(Lower("email"), name="accounts_user_email_lower_uniq")` (`vps/accounts/models.py:73-78`). Migration `0003_user_accounts_user_email_lower_uniq.py` lowercases existing emails in `RunPython` before adding the index, failing fast on duplicates. Migration `0004_user_first_failed_at.py` linearizes the dependency chain (`0002 -> 0003 -> 0004`).
   - **Services:** `register_driver` and `create_staff` normalize inputs and check `User.objects.filter(email__iexact=email).exists()`, safely handling database constraint races with `EMAIL_CONSTRAINTS`.
   - **Assessment:** Correct, complete, and verified sound (`tests/test_review_findings.py::test_f01_case_insensitive_duplicate_email_rejected` passes).

2. **F2: Account Lockout & Per-IP Rate Limiting (SEC-02, TC-03):**
   - **Implementation:** `vps/accounts/services.py:252-329` implements sliding window failed-attempt tracking. Upon the 5th failure within 15 minutes, `user.locked_until` is set to `now + timedelta(minutes=15)`. `AuditLog` emits `auth.failed` on every bad attempt and `auth.locked` upon lockout.
   - **Sign-in Flow:** `vps/accounts/views.py:57-90` checks `is_ip_rate_limited(ip)` (10/min -> HTTP 429) and `is_locked(user)` (HTTP 423 with formatted local unlock time). On successful authentication, `reset_failed_sign_in` resets counters.
   - **Assessment:** Correct and verified sound (`tests/test_review_findings.py::test_f02_account_lockout_after_five_failed_logins` passes).

3. **F3: Lot Administrator Entry Time Corrections (SRS Table 5):**
   - **Implementation:** `vps/accounts/roles.py:19, 30` defines `Function.CORRECT_TIMES: {Role.ATTENDANT, Role.ADMIN}`. `vps/gate/views.py:109` annotates `correct_entry` with `@function_required(Function.CORRECT_TIMES)`, and `vps/gate/services.py:276` permits callers with `Function.CORRECT_TIMES`.
   - **Assessment:** Entry time corrections for Lot Administrators are sound and tested (`tests/test_review_findings.py::test_f03_admin_permitted_to_correct_entry_time` passes). Note that exit time corrections remain restricted, which is documented under finding G2.

4. **F4: Audit Logging for Slot Blocks and Staff Creation (SEC-07):**
   - **Implementation:** `vps/lots/services.py:208-219` logs `slot.blocked` with `actor`, `starts_at`, `ends_at`, `reason`, `moved_count`, and `cancelled_count`. `vps/accounts/services.py:111-116` logs `staff.created` with `role` and `full_name`. Both view handlers (`vps/lots/views.py:87` and `vps/accounts/views.py:130`) pass `actor=request.user`.
   - **Assessment:** Complete and verified sound (`tests/test_review_findings.py::test_f04_slot_blocks_and_staff_creation_are_audited` passes).

5. **F5: Asynchronous Notification Sending and Row Claiming (FR-RES-07):**
   - **Implementation:** `vps/notifications/services.py:66-132` decouples database transactions from network I/O. `_claim_next` acquires the row via `select_for_update(skip_locked=True)`, transitions status to `SENDING`, records `claimed_at = now`, and commits immediately. `send_mail` executes outside the database transaction. A separate short transaction records `SENT` or retries up to 5 attempts. Dead worker claims (>10 minutes) are reclaimed.
   - **Assessment:** Complete, robust against network hanging, and verified sound (`tests/test_review_findings.py::test_f05_email_sending_not_performed_inside_database_transaction` passes).

6. **F6: `unpaid_total(None)` Null Safety (FR-BILL-05):**
   - **Implementation:** `vps/billing/services.py:65-72` adds a guard returning `Decimal("0.00")` when `getattr(driver, "pk", None) is None`, preventing unintentional aggregation of walk-in reservations (`driver__isnull=True`).
   - **Assessment:** Complete and verified sound (`tests/test_review_findings.py::test_f06_unpaid_total_for_none_driver_returns_zero` passes).

7. **F7: Session and Cookie Security Configuration (SEC-04, SEC-08):**
   - **Implementation:** `vps/settings.py:118-130` defines `SESSION_COOKIE_AGE = 1800` (30 minutes), `SESSION_SAVE_EVERY_REQUEST = True` (sliding idle expiration), `SESSION_COOKIE_HTTPONLY = True`, and `SESSION_COOKIE_SAMESITE = "Lax"`. In production (`not DEBUG`), `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_SSL_REDIRECT`, and `SECURE_HSTS_SECONDS = 31536000` (1 year) are enforced.
   - **Assessment:** Verified sound against SEC-04 and SEC-08 (`tests/test_review_findings.py::test_f07_session_cookie_configuration_enforces_sec04_sec08` passes).

---

### Additional Architecture and Presentation Audits

- **Slot Block Reallocation & Cancellation (`vps/lots/services.py:224-268`):**
  - When blocking a slot (`block_slot`), `_clear_blocked_slot` locks overlapping `RESERVED` reservations. It attempts reallocation via `move_reservation` using `eligible_slot_types` and preference rules. If no slot fits, the booking is cancelled free of charge (`fee_inr = "0.00"`), audited, and queued for notification. Tested in TC-26 (`tests/test_tc26_block_moves.py`).
- **Concurrency & Race Arbitration:**
  - Reservations use exclusion constraint `reservation_slot_period_no_overlap` (`vps/reservations/models.py:35-41`). Failed insert/move attempts trigger retries across eligible candidate slots via `allocate_slot_with_retry`.
  - Walk-in arrivals utilize PostgreSQL advisory transaction locks (`pg_advisory_xact_lock(hashtextextended('walkin:PLATE', 0))`) preventing concurrent arrival races on identical plates across lots (`vps/gate/services.py:205-209`).
  - Active vehicle limits (maximum 5) serialize concurrent additions on the `User` row (`vps/vehicles/services.py:39`).
- **Money Quantization & Tariffs:**
  - `_billable_hours` correctly rounds up to 30-minute intervals with a 1-hour minimum charge. Charges are quantized to two decimal places (`Decimal("0.01")`). Overstay charges apply a 1.5× multiplier after the 10-minute departure grace period.
  - Tariffs are looked up by `effective_from__lte=entry_date` ordered by `-effective_from`, billing parked vehicles at the tariff active at check-in time (`vps/gate/services.py:321-329`).
- **Time Zone Handling:**
  - Operating hours and date bounds consistently use `timezone.localtime(...)` against `TIME_ZONE = "Asia/Kolkata"`. Naive inputs from HTML5 `datetime-local` inputs are localized by Django's form parsing when `USE_TZ = True`.
- **Sensitive Data & Information Leaks (SEC-09):**
  - All user passwords use PBKDF2 with SHA-256 (`vps/accounts/models.py:22`).
  - Passwords, hashes, and reset tokens never appear in `AuditLog` rows, session data, or security warning logs (`tests/test_tc22_token_is_not_logged` and `tests/test_no_password_or_hash_appears_in_any_audit_row` pass).
- **Template Query Efficiency & Escaping:**
  - List views utilize annotations (`lots.annotate(slot_count=Count("slots"))`) and prefetching (`select_related("slot__lot")`, `Prefetch("charges")`), avoiding N+1 queries.
  - Auto-escaping is active across all Django templates without dangerous `|safe` filters on user-supplied inputs.

---

## 3. Findings Ranked by Severity

### G1: Gate Attendants and Lot Administrators Denied Ability to Search Parking Slots

- **ID:** G1
- **Severity:** High
- **Component:** `vps/reservations/forms.py:20`, `vps/reservations/views.py:29-54`
- **SRS Requirement:** FR-SRCH-01, SRS Appendix B.3 Table 5 Permission Matrix (Row "Search available slots" explicitly allows `Driver: Yes`, `Gate Attendant: Yes`, `Lot Administrator: Yes`).
- **Concrete Failing Scenario:**
  1. A Gate Attendant signs in. Under `vps/accounts/views.py:home`, the attendant is redirected directly to `/reservations/search/` (their primary dashboard landing destination).
  2. The navigation bar (`templates/base.html`) provides a "Slot search" link pointing to `/reservations/search/`.
  3. The view `slot_search` is decorated with `@function_required(Function.SEARCH)`, which correctly grants access to Attendants and Administrators.
  4. However, `ReservationSearchForm.__init__` forces:
     ```python
     self.fields["vehicle"].queryset = Vehicle.objects.filter(owner=user, is_active=True)
     ```
  5. Gate Attendants and Lot Administrators do not own vehicles (and are forbidden from registering any under `Function.MANAGE_OWN_VEHICLES`). Consequently, `form.fields["vehicle"].queryset` is empty, and the HTML `<select id="vehicle" name="vehicle" required>` has no selectable choices.
  6. When an Attendant or Administrator submits a search for an active parking lot and time window (e.g. `GET /reservations/search/?lot=1&start=2026-11-06T10:00&end=2026-11-06T12:00`), `form.is_valid()` fails because `vehicle` is required and no valid vehicle PK was provided.
  7. `context["search_error"]` is set to `"Choose a lot, one of your vehicles, a start and an end."` and `slot_count` remains `None`.
  8. Staff members are completely incapable of checking slot availability, breaking FR-SRCH-01 and the Table 5 Permission Matrix.
- **Reproduction Test:** `tests/test_review_findings_2.py::test_g01_staff_can_search_parking_slots`
- **Suggested Fix:**
  In `vps/reservations/forms.py`, allow the `vehicle` field to be optional for staff users, or allow staff to query by `vehicle_type` or query overall lot availability without a vehicle. For example:
  ```python
  class ReservationSearchForm(forms.Form):
      lot = forms.ModelChoiceField(queryset=Lot.objects.none())
      vehicle = forms.ModelChoiceField(queryset=Vehicle.objects.none(), required=False)
      vehicle_type = forms.ChoiceField(choices=Vehicle.VehicleType.choices, required=False)
      start = forms.DateTimeField(input_formats=[DATETIME_LOCAL])
      end = forms.DateTimeField(input_formats=[DATETIME_LOCAL])

      def __init__(self, *args, user, **kwargs):
          super().__init__(*args, **kwargs)
          self.fields["lot"].queryset = Lot.objects.active()
          if can(user, Function.OWN_RESERVATIONS):
              self.fields["vehicle"].queryset = Vehicle.objects.filter(owner=user, is_active=True)
              self.fields["vehicle"].required = True
          else:
              self.fields["vehicle"].required = False
  ```
  In `vps/reservations/views.py:slot_search`, evaluate slot availability for staff using either the chosen vehicle, vehicle type, or total eligible slots for the lot.

---

### G2: Lot Administrator Denied Permission to Record Outage Exit Times (Incomplete F3 Fix)

- **ID:** G2
- **Severity:** Medium
- **Component:** `vps/gate/services.py:346-347`, `vps/gate/views.py:86-88`
- **SRS Requirement:** FR-GATE-06, SAF-03, SRS Appendix B.3 Table 5 Permission Matrix (Row "Correct entry or exit time" explicitly allows `Gate Attendant: Yes`, `Lot Administrator: Yes`).
- **Concrete Failing Scenario:**
  1. A network or power outage occurs at a parking lot, and departing vehicles have their exit times noted on paper. Once connectivity resumes, staff must record the past exit time with a mandatory reason within 24 hours per FR-GATE-06.
  2. While review finding F3 identified that Lot Administrators were denied permission to correct entry times and resolved it for `correct_entry` and `correct_entry_time`, manual exit time corrections remain tied to the checkout workflow.
  3. In `vps/gate/views.py:checkout`, the view is decorated with `@function_required(Function.GATE_OPERATIONS)`. When a Lot Administrator accesses `/gate/checkout/`, they receive HTTP 403 Forbidden.
  4. In `vps/gate/services.py:checkout_vehicle`, the service unconditionally asserts:
     ```python
     if not can(attendant, Function.GATE_OPERATIONS):
         raise ValidationError({"__all__": "Only Gate Attendants may check out vehicles."})
     ```
  5. Even when a caller supplies `exit_time` and `reason` (performing a past exit time correction under FR-GATE-06), a Lot Administrator is rejected with a `ValidationError` because `can(admin, Function.GATE_OPERATIONS)` evaluates to `False`.
  6. Lot Administrators are prevented from performing exit time corrections, violating the Table 5 Permission Matrix.
- **Reproduction Test:** `tests/test_review_findings_2.py::test_g02_admin_permitted_to_record_outage_exit_time`
- **Suggested Fix:**
  1. In `vps/gate/services.py:checkout_vehicle`, allow callers holding either `Function.GATE_OPERATIONS` or `Function.CORRECT_TIMES` when `exit_time is not None`:
     ```python
     required_func = Function.CORRECT_TIMES if exit_time is not None else Function.GATE_OPERATIONS
     if not can(attendant, required_func):
         raise ValidationError({"__all__": "Only authorized staff may record vehicle checkouts."})
     ```
  2. In `vps/gate/views.py`, either adjust `@role_required` on `checkout` to permit `Function.CORRECT_TIMES` when handling outage exit times, or provide a dedicated exit time correction route (e.g. `/gate/correct-exit/`) mirroring `correct_entry`.

---

### G3: Staff Creation Template Fails to Render Success Messages and Navigation

- **ID:** G3
- **Severity:** Low
- **Component:** `templates/accounts/create_staff.html:1-41`, `vps/accounts/views.py:135-141`
- **SRS Requirement:** FR-AUTH-05, UI consistency and accessibility.
- **Concrete Failing Scenario:**
  1. A Lot Administrator creates a new Gate Attendant or Lot Administrator account at `/accounts/staff/create/`.
  2. Upon successful validation, `vps/accounts/views.py:create_staff` queues a flash notification:
     ```python
     messages.success(request, f"Staff account created for {staff.email}.")
     return redirect("accounts:create_staff")
     ```
  3. The browser follows the redirect back to `/accounts/staff/create/`.
  4. However, `templates/accounts/create_staff.html` is an unstyled, isolated HTML document: it does not extend `base.html` and does not include `{% for message in messages %}`.
  5. The success message is dropped and never displayed to the administrator.
  6. Additionally, the page lacks the site header, user status, logout button, and navigation links back to `/accounts/staff/` (the Manage Staff list).
- **Reproduction Test:** `tests/test_review_findings_2.py::test_g03_staff_creation_renders_success_message`
- **Suggested Fix:**
  Update `templates/accounts/create_staff.html` to extend `base.html`:
  ```html
  {% extends "base.html" %}

  {% block title %}Create Staff Account | VPS{% endblock %}

  {% block content %}
  <section class="staff-form-page">
    <h1>Create Staff Account</h1>
    <p>Create a Gate Attendant or Lot Administrator account.</p>

    <form method="post" novalidate>
      {% csrf_token %}
      ...
      <button type="submit">Create Staff Account</button>
      <a href="{% url 'accounts:staff_list' %}">Back to staff accounts</a>
    </form>
  </section>
  {% endblock %}
  ```
