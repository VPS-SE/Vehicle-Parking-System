# Code Review: VPS Application and Presentation Layers

**Project:** Vehicle Parking System (Django 5.2 + PostgreSQL 16) — Team 10, Section C  
**Deliverable:** Part-3 Code Quality & Security Audit  
**Scope:** `vps/` (accounts, allocation, audit, billing, gate, lots, notifications, reports, reservations, vehicles), `templates/`, and project settings.  
**Review Date:** November 4, 2026  
**Auditor:** Test Engineering Team  

---

## 1. Executive Summary

An extensive manual code review of the core Django applications and presentation templates was conducted, focusing on functional correctness, security, data leaks, permission boundaries, race hazards, time-zone awareness, and template performance.

Overall, the application architecture demonstrates strong engineering in concurrency controls (PostgreSQL `DateTimeTZRange` exclusion constraints with `btree_gist`, advisory locks for walk-ins, and `select_for_update` row serialization) and query efficiency (e.g., prefetching and foreign key selection on list views).

Seven concrete findings were identified and ranked by severity:
- **High Severity:** 2 findings (F1: Case-sensitive email validation causing duplicate accounts; F2: Unimplemented account lockout on failed sign-ins).
- **Medium Severity:** 4 findings (F3: Lot Administrator denied access to correct entry times; F4: Missing audit logging for slot blocks and staff creation; F5: Synchronous SMTP network call inside database transaction with row locks; F7: Session cookie configuration lacking 30-minute idle sliding expiration).
- **Low Severity:** 1 finding (F6: `unpaid_total(None)` queries walk-in reservations instead of returning zero).

Each finding has an automated reproduction test in `tests/test_review_findings.py` marked `@pytest.mark.xfail(strict=True, reason="F<n>: ...")`.

---

## 2. Review of Sound Areas

The following modules were reviewed and found to be correctly implemented:

1. **Race Safety and Concurrency (`vps/reservations/services.py`, `vps/gate/services.py`, `vps/vehicles/services.py`):**
   - Concurrent bookings competing for the last available slot are safely arbitrated by PostgreSQL's `reservation_slot_period_no_overlap` exclusion constraint. The losing transaction catches the constraint violation and transparently retries candidate slots via `allocate_slot_with_retry` up to 3 times before raising `NO_SLOT` (tested in TC-07).
   - Driver booking limits (maximum 2 open `Reserved` bookings) are serialized using `User.objects.select_for_update().get(pk=driver.pk)` within the booking transaction, preventing double-tab bypasses.
   - Walk-in arrivals utilize PostgreSQL transactional advisory locks (`SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))`) on normalized registration numbers, preventing race conditions across lots.
   - Active vehicle registration limits (maximum 5) serialize concurrent additions on the driver row.

2. **Access Control & IDOR Protection (`vps/reservations/views.py`, `vps/gate/views.py`, `vps/vehicles/views.py`):**
   - Reservation confirmations (`/reservations/<booking_ref>/confirmation/`), history, and cancellations strictly filter by `driver=request.user`, preventing Insecure Direct Object References (IDOR).
   - Printable receipts (`/gate/printable-receipt/<booking_ref>/`) enforce that only Gate Attendants or the specific Driver who booked can view the receipt; attempts by third-party drivers raise `Http404`.
   - Driver vehicle list and vehicle additions enforce `owner=request.user` and role `Driver`.

3. **Billing, Rounding & Overstay Calculations (`vps/gate/services.py`, `vps/billing/services.py`):**
   - The 30-minute block rounding with a 1-hour minimum charge is calculated correctly in `_billable_hours` (tested in TC-13).
   - The 10-minute departure grace period and 1.5× rate multiplier for overstays are applied precisely according to FR-BILL-03 (tested in TC-14).
   - Historical tariffs are retrieved using `effective_from__lte=entry_date` ordered by `-effective_from`, guaranteeing that parked vehicles are billed at the rate active upon entry even if rates change later (tested in TC-33).

4. **Template Performance & Query Optimization (`templates/`, `vps/lots/views.py`, `vps/reservations/views.py`):**
   - Lot listing (`lot_list`) uses `.annotate(slot_count=Count("slots"))` to eliminate N+1 queries.
   - Booking history (`booking_history`) uses `select_related("slot__lot")` and `Prefetch("charges", queryset=Charge.objects.select_related("payment").order_by("id"))`, preventing query multiplication across paginated items.
   - Attendant payments view selects related reservations in a single join.
   - All forms properly include `{% csrf_token %}` and validate inputs server-side.

---

## 3. Findings Ranked by Severity

### F1: Case-Sensitive Email Validation Permits Duplicate Driver Accounts
- **ID:** F1
- **Severity:** High
- **Component:** `vps/accounts/services.py:21`, `vps/accounts/services.py:31` (and `create_staff` at lines 58, 83)
- **Failing Scenario:**
  1. An account is registered with email `asha@example.com`.
  2. Another registration request is submitted with email `ASHA@example.com`.
  3. `User.objects.normalize_email("ASHA@example.com")` only normalizes the domain part, preserving `ASHA` as the username/local-part.
  4. `User.objects.filter(email=email).exists()` performs a case-sensitive lookup in PostgreSQL, returning `False`.
  5. The second account is created without error.
  6. Two accounts exist for the same logical email address, violating FR-AUTH-01 and TC-02 ("Register again with e-mail ASHA@example.com... Registration refused with 'An account with this e-mail already exists'; no new account created").
- **Reproduction Test:** `tests/test_review_findings.py::test_f01_case_insensitive_duplicate_email_rejected`
- **Suggested Fix:**
  Normalize the entire email string to lowercase:
  ```python
  email = User.objects.normalize_email(email.strip()).lower()
  ```
  Additionally, query with `email__iexact=email`:
  ```python
  if User.objects.filter(email__iexact=email).exists():
      errors["email"] = [DUPLICATE_EMAIL]
  ```
  In the database, ensure a unique index on `LOWER(email)`:
  ```python
  UniqueConstraint(
      OpClass(Lower("email"), name="varchar_ops"),
      name="accounts_user_email_lower_uniq",
  )
  ```

---

### F2: Account Lockout After 5 Failed Sign-Ins (SEC-02 / TC-03) is Unimplemented
- **ID:** F2
- **Severity:** High
- **Component:** `vps/accounts/views.py:58-75`, `vps/accounts/models.py:48-49`
- **Failing Scenario:**
  1. An attacker or user submits 5 consecutive invalid login attempts for an account within 2 minutes.
  2. The sign-in view in `vps/accounts/views.py` calls `authenticate(request, **form.cleaned_data)`.
  3. On failure, it renders `accounts/login.html` with "Invalid e-mail or password" but does NOT increment `user.failed_attempts`, does NOT set `user.locked_until`, and does NOT emit an `auth.failed` audit entry.
  4. On the 6th attempt (even with the correct password), the user signs in successfully instead of being locked out with HTTP 423.
  5. Violates SEC-02 and TC-03.
- **Reproduction Test:** `tests/test_review_findings.py::test_f02_account_lockout_after_five_failed_logins`
- **Suggested Fix:**
  In `vps/accounts/views.py:sign_in`, locate the user by email before authentication:
  - If `user.locked_until and user.locked_until > timezone.now()`, return `HttpResponse("Account locked", status=423)`.
  - When authentication fails for an existing user:
    - Increment `user.failed_attempts += 1`.
    - If `user.failed_attempts >= 5`: set `user.locked_until = timezone.now() + timedelta(minutes=15)`.
    - Log `auth.failed` in `AuditLog`.
  - When authentication succeeds:
    - Reset `user.failed_attempts = 0` and `user.locked_until = None`.

---

### F3: Lot Administrator Denied Permission to Correct Entry Times
- **ID:** F3
- **Severity:** Medium
- **Component:** `vps/gate/services.py:292-293`, `vps/gate/views.py:102-104`
- **Failing Scenario:**
  1. In the SRS Appendix B.3 Role Permission Matrix (Table 5), "Correct entry or exit time" is explicitly permitted for both `Gate Attendant: Yes` and `Lot Administrator: Yes`.
  2. `vps/accounts/roles.py` defines `Function.CORRECT_TIMES: {Role.ATTENDANT, Role.ADMIN}`.
  3. However, `vps/gate/views.py:correct_entry` is decorated with `@function_required(Function.GATE_OPERATIONS)` which restricts access to Gate Attendants only.
  4. In `vps/gate/services.py:correct_entry_time`, the service checks `if not can(attendant, Function.GATE_OPERATIONS): raise ValidationError(...)`.
  5. When a Lot Administrator accesses `/gate/correct-entry/` or attempts to correct an entry time following an outage, they receive HTTP 403 Forbidden or a validation error.
- **Reproduction Test:** `tests/test_review_findings.py::test_f03_admin_permitted_to_correct_entry_time`
- **Suggested Fix:**
  In `vps/gate/views.py`:
  ```python
  @function_required(Function.CORRECT_TIMES)
  @require_http_methods(["GET", "POST"])
  def correct_entry(request):
  ```
  In `vps/gate/services.py:correct_entry_time`:
  ```python
  if not can(attendant, Function.CORRECT_TIMES):
      raise ValidationError({"__all__": "Only staff with time correction privileges may correct entry times."})
  ```

---

### F4: Slot Blocks and Staff Creation Omit Required Audit Log Entries
- **ID:** F4
- **Severity:** Medium
- **Component:** `vps/lots/services.py:157-208`, `vps/accounts/services.py:56-107`
- **Failing Scenario:**
  1. SEC-07 mandates: "The audit log shall record actor, action, target, old value, new value and timestamp for every tariff change, slot block, staff account change, payment, charge waiver and manual time correction."
  2. `vps/lots/services.py:block_slot` accepts parameters for slot, starts_at, ends_at, reason, but does NOT accept `actor` and never writes an entry to `AuditLog`.
  3. `vps/accounts/services.py:create_staff` creates staff users (`User`) but does not record an audit log entry for the new staff account.
- **Reproduction Test:** `tests/test_review_findings.py::test_f04_slot_blocks_and_staff_creation_are_audited`
- **Suggested Fix:**
  1. In `vps/lots/services.py:block_slot`, accept `actor=None` and call:
     ```python
     log_action(
         actor=actor,
         action="slot.blocked",
         target=f"slot:{slot.lot_id}/{slot.code}",
         before=None,
         after={"starts_at": starts_at.isoformat(), "ends_at": ends_at.isoformat(), "reason": reason},
     )
     ```
  2. In `vps/accounts/services.py:create_staff`, accept `actor=None` and log `staff.created` with the created staff email and role.

---

### F5: Synchronous SMTP Network Call Executed Inside Database Transaction
- **ID:** F5
- **Severity:** Medium
- **Component:** `vps/notifications/services.py:65-115`
- **Failing Scenario:**
  1. In `process_pending_notifications`, each batch item is processed inside an atomic database block: `with transaction.atomic():`.
  2. The notification row is locked using `select_for_update(skip_locked=True)`.
  3. While holding this row lock in an open PostgreSQL transaction, `send_mail(...)` makes an external network connection to the configured SMTP server over TLS/TCP.
  4. If the SMTP server is slow, experiences packet loss, or hangs before timing out (up to 30–60 seconds), the database transaction remains open, holding lock resources, occupying database connections, and risking connection pool exhaustion.
- **Reproduction Test:** `tests/test_review_findings.py::test_f05_email_sending_not_performed_inside_database_transaction`
- **Suggested Fix:**
  Separate database state transitions from network I/O:
  1. Within a short atomic transaction, transition the notification status to an intermediate state (e.g., `SENDING`) and record attempt increment.
  2. Perform `send_mail(...)` outside the database transaction block.
  3. In a subsequent short transaction, update status to `SENT` (with `sent_at`) or `FAILED` (with `last_error`).

---

### F6: `unpaid_total(None)` Aggregates Walk-In Charges Instead of Returning Zero
- **ID:** F6
- **Severity:** Low
- **Component:** `vps/billing/services.py:73-77`
- **Failing Scenario:**
  1. `vps/billing/services.py:unpaid_total(driver)` executes:
     ```python
     Charge.objects.filter(reservation__driver=driver, payment__isnull=True).aggregate(...)
     ```
  2. For walk-in vehicles, `reservation.driver` is `None`.
  3. When `unpaid_total(None)` is called (or if a view context passes an unauthenticated/guest user), the ORM filter matches `reservation__driver=None`, summing unpaid charges across all walk-ins in the system.
  4. Returns the sum of walk-in debts instead of `Decimal("0.00")`.
- **Reproduction Test:** `tests/test_review_findings.py::test_f06_unpaid_total_for_none_driver_returns_zero`
- **Suggested Fix:**
  Add a guard clause at the start of `unpaid_total`:
  ```python
  def unpaid_total(driver):
      if not driver or not getattr(driver, "is_authenticated", True):
          return Decimal("0.00")
      ...
  ```

---

### F7: Session Cookie Configuration Missing 30-Minute Idle Timeout and Security Flags
- **ID:** F7
- **Severity:** Medium
- **Component:** `vps/settings.py`
- **Failing Scenario:**
  1. SEC-08 specifies: "A signed-in session shall end after 30 minutes without activity."
  2. SEC-04 specifies: "...session cookies shall be Secure, HttpOnly and SameSite=Lax."
  3. In `vps/settings.py`, `SESSION_COOKIE_AGE` is not defined (defaulting to Django's 1,209,600 seconds / 14 days), `SESSION_SAVE_EVERY_REQUEST` is not enabled (required for sliding idle expiration on GET requests), and `SESSION_COOKIE_SECURE` is not set.
- **Reproduction Test:** `tests/test_review_findings.py::test_f07_session_cookie_configuration_enforces_sec04_sec08`
- **Suggested Fix:**
  In `vps/settings.py`, configure:
  ```python
  SESSION_COOKIE_AGE = 1800  # 30 minutes (SEC-08)
  SESSION_SAVE_EVERY_REQUEST = True
  SESSION_COOKIE_SECURE = not DEBUG  # SEC-04
  SESSION_COOKIE_HTTPONLY = True
  SESSION_COOKIE_SAMESITE = "Lax"
  ```
