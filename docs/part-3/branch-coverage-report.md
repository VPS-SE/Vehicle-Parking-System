# Branch Coverage Report

Branch coverage of the application and the forecast service, from the same runs as the Code Coverage Report (`coverage run --branch`). Measured on 5 November 2026.

## Result

Application: 506 of 556 branches taken, **91.01%**. The Test Plan gate is 60%. The gate script passed (see the Code Coverage Report).

Forecast service: 56 branches, 4 partial (`evidence/forecast-coverage.txt`).

## Per module

| Module | Branches | Partial | Branch coverage |
|---|---|---|---|
| `vps/accounts/models.py` | 6 | 0 | 100.0%* |
| `vps/accounts/permissions.py` | 10 | 0 | 100.0%* |
| `vps/accounts/roles.py` | 2 | 0 | 100.0%* |
| `vps/accounts/services.py` | 60 | 7 | 88.3%* |
| `vps/accounts/views.py` | 32 | 1 | 96.9%* |
| `vps/allocation/services.py` | 32 | 3 | 90.6%* |
| `vps/audit/models.py` | 2 | 0 | 100.0%* |
| `vps/audit/services.py` | 4 | 0 | 100.0%* |
| `vps/billing/services.py` | 26 | 0 | 100.0%* |
| `vps/billing/views.py` | 2 | 0 | 100.0%* |
| `vps/environment.py` | 8 | 0 | 100.0%* |
| `vps/factories.py` | 34 | 2 | 94.1%* |
| `vps/gate/forms.py` | 2 | 0 | 100.0%* |
| `vps/gate/services.py` | 70 | 3 | 95.7%* |
| `vps/gate/views.py` | 22 | 0 | 100.0%* |
| `vps/lots/forms.py` | 2 | 0 | 100.0%* |
| `vps/lots/services.py` | 68 | 2 | 97.1%* |
| `vps/lots/views.py` | 20 | 1 | 95.0%* |
| `vps/notifications/services.py` | 10 | 1 | 90.0%* |
| `vps/reports/forms.py` | 8 | 1 | 87.5%* |
| `vps/reports/management/commands/seed_demo_data.py` | 2 | 0 | 100.0%* |
| `vps/reports/services.py` | 30 | 0 | 100.0%* |
| `vps/reports/views.py` | 10 | 2 | 80.0%* |
| `vps/reservations/forecast.py` | 10 | 0 | 100.0%* |
| `vps/reservations/forms.py` | 4 | 0 | 100.0%* |
| `vps/reservations/services.py` | 40 | 1 | 97.5%* |
| `vps/reservations/views.py` | 16 | 2 | 87.5%* |
| `vps/settings.py` | 4 | 0 | 100.0%* |
| `vps/urls.py` | 2 | 1 | 50.0%* |
| `vps/vehicles/services.py` | 14 | 1 | 92.9%* |
| `vps/vehicles/views.py` | 4 | 0 | 100.0%* |
| `forecast/app/main.py` | 12 | 0 | 100.0%* |
| `forecast/common.py` | 4 | 0 | 100.0%* |
| `forecast/tests/test_forecast.py` | 4 | 0 | 100.0%* |
| `forecast/train/observations.py` | 14 | 1 | 92.9%* |
| `forecast/train/simulate.py` | 14 | 1 | 92.9%* |
| `forecast/train/train.py` | 8 | 2 | 75.0%* |

\* Counted as (branches minus partial branches) over branches. A partial branch is a condition where only one of its two outcomes ran. The overall figure above comes from `coverage.xml`, which counts each outcome separately, so the two measures differ slightly.

## Partial branches in the business modules

| Module | Missed lines and branches | What is not exercised |
|---|---|---|
| `vps/accounts/services.py` | 58-62, 69, 88-89, 96-97, 118-122, 163, 168, 198, 203, 233, 281 | Lines 58-62 and 118-122: the `IntegrityError` fallbacks in `register_driver` and `create_staff`, which run only if two requests race past the duplicate-e-mail check. Lines 69 and 88-89: `create_staff` refusing a non-staff role or a field that fails model validation; the staff form already limits the role and checks the fields. Lines 96-97: `create_staff` refusing a weak password. The form does not check this, so it is a real gap: no test creates a staff account with a weak password (driver registration tests cover the same validator). Lines 163, 168, 198 and 203: the not-admin and not-staff guards in `deactivate_staff` and `reactivate_staff`. The views already refuse these callers, so the guards are never reached through them. Line 233: the empty-IP case of the per-IP sign-in limit. Line 281: a counted failure that has no first-failure time. |
| `vps/allocation/services.py` | 26, 43, 60 | Lines 26, 43 and 60: the final `return False`, `set()` and `[]` for a vehicle type outside Car, Two-wheeler and EV. The model's choices make this impossible. |
| `vps/billing/services.py` | 121-125 | Lines 121-125: the `IntegrityError` fallback in `waive_charge` for two admins waiving the same charge at the same moment; the row lock and the already-waived check catch every other case. |
| `vps/gate/services.py` | 91, 318, 425->432 | Line 91: an empty check-out query, which the form refuses first. Line 318: a tariff lookup for a booking with no entry time. Branch 425->432: an overstay amount of zero. |
| `vps/lots/services.py` | 59, 140-152, 185, 204-208, 356-364 | Line 59 and lines 140-152, 204-208 and 356-364: `IntegrityError` fallbacks after the duplicate slot code, overlapping block and duplicate tariff date pre-checks. Line 185: the missing start or end guard, which the form already enforces. |
| `vps/notifications/services.py` | 116 | Line 116: an e-mail backend that returns something other than 1 without raising an error. |
| `vps/reservations/services.py` | 113-117, 185-190, 274 | Lines 113-117: a constraint violation other than the overlap constraint while moving a booking, which is re-raised. Lines 185-190: the overlap fallback in `_try_book`. Since the D-4 fix, bookings in a lot take a lock before choosing a slot, so concurrent tests no longer reach the overlap constraint; it stays as the database's last guard. Line 274: a non-driver calling `cancel_reservation` directly. The view refuses such callers first. |
| `vps/vehicles/services.py` | 50 | Line 50: re-raising an `IntegrityError` that is not the duplicate-plate constraint. |

Most of these lines are defensive. One kind is a fallback for two requests racing past a check made just before the write: testing those needs two transactions interleaved at an exact point. The other kind is a guard behind a check the view or form already makes. The races the Test Plan names are tested: TC-07 (50 parallel bookings for the last slot) and the concurrent-booking test (30 parallel bookings, 30 slots). `vps/audit/services.py` and `vps/reports/services.py` have no missed lines.

