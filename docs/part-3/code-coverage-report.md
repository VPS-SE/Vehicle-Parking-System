# Code Coverage Report

Line coverage of the application (`vps/`) and of the forecast service (`forecast/`). Measured on 12 November 2026 on the final code: `main` at 185d8e8 plus the PES tariff fix (PR #145).

## How it was measured

```
coverage run --branch -m pytest -q -p no:cacheprovider --junitxml=docs/part-3/evidence/junit.xml
coverage report -m > docs/part-3/evidence/coverage.txt
coverage xml -o docs/part-3/evidence/coverage.xml
python scripts/check_coverage.py docs/part-3/evidence/coverage.xml
```

`pyproject.toml` sets the source to `vps` and leaves out migrations. The forecast service was measured separately with pytest-cov (`evidence/forecast-coverage.txt`).

## Result

Application: 2606 of 2710 lines covered, **96.16%**. The Test Plan gate is 70%, and `scripts/check_coverage.py` printed:

```
Line coverage: 96.16% (required: 70.00%)
Branch coverage: 91.28% (required: 60.00%)
Coverage gate PASSED
```

Forecast service: 252 of 278 statements covered (the TOTAL line, branches included, shows 90%).

## Per module (application)

| Module | Statements | Missed | Line coverage |
|---|---|---|---|
| `vps/accounts/apps.py` | 4 | 0 | 100.0% |
| `vps/accounts/forms.py` | 16 | 0 | 100.0% |
| `vps/accounts/models.py` | 55 | 0 | 100.0% |
| `vps/accounts/permissions.py` | 36 | 0 | 100.0% |
| `vps/accounts/permit_forms.py` | 3 | 0 | 100.0% |
| `vps/accounts/roles.py` | 23 | 0 | 100.0% |
| `vps/accounts/services.py` | 172 | 21 | 87.8% |
| `vps/accounts/urls.py` | 4 | 0 | 100.0% |
| `vps/accounts/views.py` | 138 | 3 | 97.8% |
| `vps/allocation/apps.py` | 4 | 0 | 100.0% |
| `vps/allocation/services.py` | 59 | 3 | 94.9% |
| `vps/asgi.py` | 4 | 4 | 0.0% |
| `vps/audit/apps.py` | 4 | 0 | 100.0% |
| `vps/audit/models.py` | 28 | 1 | 96.4% |
| `vps/audit/services.py` | 13 | 0 | 100.0% |
| `vps/billing/apps.py` | 4 | 0 | 100.0% |
| `vps/billing/models.py` | 39 | 3 | 92.3% |
| `vps/billing/services.py` | 65 | 3 | 95.4% |
| `vps/billing/urls.py` | 4 | 0 | 100.0% |
| `vps/billing/views.py` | 28 | 0 | 100.0% |
| `vps/environment.py` | 24 | 0 | 100.0% |
| `vps/factories.py` | 115 | 1 | 99.1% |
| `vps/gate/apps.py` | 4 | 0 | 100.0% |
| `vps/gate/forms.py` | 23 | 0 | 100.0% |
| `vps/gate/services.py` | 192 | 2 | 99.0% |
| `vps/gate/urls.py` | 4 | 0 | 100.0% |
| `vps/gate/views.py` | 139 | 6 | 95.7% |
| `vps/lots/apps.py` | 4 | 0 | 100.0% |
| `vps/lots/forms.py` | 36 | 0 | 100.0% |
| `vps/lots/management/commands/seed_pes_lots.py` | 12 | 0 | 100.0% |
| `vps/lots/models.py` | 54 | 1 | 98.1% |
| `vps/lots/pes.py` | 42 | 1 | 97.6% |
| `vps/lots/plan.py` | 107 | 5 | 95.3% |
| `vps/lots/services.py` | 215 | 20 | 90.7% |
| `vps/lots/urls.py` | 4 | 0 | 100.0% |
| `vps/lots/views.py` | 176 | 6 | 96.6% |
| `vps/notifications/apps.py` | 4 | 0 | 100.0% |
| `vps/notifications/management/commands/send_reservation_notifications.py` | 7 | 0 | 100.0% |
| `vps/notifications/models.py` | 29 | 1 | 96.6% |
| `vps/notifications/services.py` | 56 | 1 | 98.2% |
| `vps/reports/apps.py` | 4 | 0 | 100.0% |
| `vps/reports/forms.py` | 31 | 0 | 100.0% |
| `vps/reports/management/commands/seed_demo_data.py` | 12 | 0 | 100.0% |
| `vps/reports/services.py` | 90 | 0 | 100.0% |
| `vps/reports/urls.py` | 4 | 0 | 100.0% |
| `vps/reports/views.py` | 81 | 2 | 97.5% |
| `vps/reservations/apps.py` | 4 | 0 | 100.0% |
| `vps/reservations/forecast.py` | 35 | 0 | 100.0% |
| `vps/reservations/forms.py` | 24 | 0 | 100.0% |
| `vps/reservations/management/commands/expire_no_shows.py` | 7 | 0 | 100.0% |
| `vps/reservations/models.py` | 27 | 0 | 100.0% |
| `vps/reservations/services.py` | 148 | 10 | 93.2% |
| `vps/reservations/urls.py` | 4 | 0 | 100.0% |
| `vps/reservations/views.py` | 105 | 3 | 97.1% |
| `vps/settings.py` | 50 | 0 | 100.0% |
| `vps/urls.py` | 9 | 1 | 88.9% |
| `vps/vehicles/apps.py` | 4 | 0 | 100.0% |
| `vps/vehicles/forms.py` | 15 | 0 | 100.0% |
| `vps/vehicles/models.py` | 18 | 1 | 94.4% |
| `vps/vehicles/services.py` | 43 | 1 | 97.7% |
| `vps/vehicles/urls.py` | 4 | 0 | 100.0% |
| `vps/vehicles/views.py` | 25 | 0 | 100.0% |
| `vps/views.py` | 12 | 0 | 100.0% |
| `vps/wsgi.py` | 4 | 4 | 0.0% |

## Per module (forecast service)

| Module | Statements | Missed | Line coverage |
|---|---|---|---|
| `forecast/app/main.py` | 44 | 0 | 100.0% |
| `forecast/common.py` | 17 | 0 | 100.0% |
| `forecast/tests/test_forecast.py` | 87 | 0 | 100.0% |
| `forecast/train/observations.py` | 28 | 0 | 100.0% |
| `forecast/train/simulate.py` | 27 | 1 | 96.3% |
| `forecast/train/train.py` | 75 | 25 | 66.7% |

## Least-covered modules

| Module | Line coverage | Missed lines | Why |
|---|---|---|---|
| `vps/asgi.py`, `vps/wsgi.py` | 0.0% | 3, 5, 7, 9 | Server entry points. Gunicorn imports `wsgi.py`; the test client never does. Both ran in the system tests, which are not measured. |
| `vps/accounts/services.py` | 87.8% | 58-62, 69, 88-89, 96-97, 118-122, 163, 168, 198, 203, 233, 281 | Race fallbacks (`IntegrityError` after the duplicate-e-mail check) and role guards that the views already enforce. See the Branch Coverage Report. |
| `vps/urls.py` | 88.9% | 26 | The static-files route added only when DEBUG is on. |
| `vps/lots/services.py` | 90.7% | 62, 143-148, 155, 188, 207-211, 359-360, 365-367, 449 | `IntegrityError` fallbacks after the pre-checks (duplicate slot code, overlapping block, duplicate tariff date), one missing-time guard, and line 449: a registration that is empty after removing spaces and hyphens, which the lot map search refuses earlier. |
| `vps/billing/models.py` | 92.3% | 27, 47, 69 | `__str__` methods. |
| `vps/reservations/services.py` | 93.2% | 113-117, 185-186, 189-190, 274 | See the Branch Coverage Report. |

In `forecast/train/train.py` the uncovered lines are `load_history` and `main`, which read from PostgreSQL. They were run by hand against the seeded demo database while #127 was being built. No automated test covers them.

