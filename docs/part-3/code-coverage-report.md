# Code Coverage Report

Line coverage of the application (`vps/`) and of the forecast service (`forecast/`). Measured on 5 November 2026.

## How it was measured

```
./run-coverage.sh run --branch -m pytest -q -p no:cacheprovider
./run-coverage.sh report -m > docs/part-3/evidence/coverage.txt
./run-coverage.sh xml -o docs/part-3/evidence/coverage.xml
python scripts/check_coverage.py docs/part-3/evidence/coverage.xml
```

`pyproject.toml` sets the source to `vps` and leaves out migrations. The forecast service was measured separately with pytest-cov (`evidence/forecast-coverage.txt`).

## Result

Application: 2314 of 2412 lines covered, **95.94%**. The Test Plan gate is 70%, and `scripts/check_coverage.py` printed:

```
Line coverage: 95.94% (required: 70.00%)
Branch coverage: 91.01% (required: 60.00%)
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
| `vps/factories.py` | 115 | 2 | 98.3% |
| `vps/gate/apps.py` | 4 | 0 | 100.0% |
| `vps/gate/forms.py` | 23 | 0 | 100.0% |
| `vps/gate/services.py` | 192 | 2 | 99.0% |
| `vps/gate/urls.py` | 4 | 0 | 100.0% |
| `vps/gate/views.py` | 139 | 6 | 95.7% |
| `vps/lots/apps.py` | 4 | 0 | 100.0% |
| `vps/lots/forms.py` | 36 | 0 | 100.0% |
| `vps/lots/models.py` | 54 | 1 | 98.1% |
| `vps/lots/services.py` | 185 | 19 | 89.7% |
| `vps/lots/urls.py` | 4 | 0 | 100.0% |
| `vps/lots/views.py` | 93 | 6 | 93.5% |
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
| `vps/reservations/views.py` | 84 | 3 | 96.4% |
| `vps/settings.py` | 47 | 0 | 100.0% |
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
| `vps/accounts/services.py` | 87.8% | 58-62, 69, 88-89, 96-97, 118-122, 163, 168, 198, 203, 233, 281 | Race fallbacks (`IntegrityError` after the duplicate-e-mail check) and role guards that the views already enforce. See the Branch Coverage Report. |
| `vps/urls.py` | 88.9% | 26 | See the missed line list. |
| `vps/lots/services.py` | 89.7% | 59, 140-152, 185, 204-208, 356-364 | Missed lines are `IntegrityError` fallbacks after the pre-checks (duplicate slot code, overlapping block, duplicate tariff date) and one missing-time guard. |
| `vps/billing/models.py` | 92.3% | 27, 47, 69 | See the missed line list. |
| `vps/reservations/services.py` | 93.2% | 113-117, 185-190, 274 | See the missed line list. |
| `vps/lots/views.py` | 93.5% | 46-51, 106 | See the missed line list. |

In `forecast/train/train.py` the uncovered lines are `load_history` and `main`, which read from PostgreSQL. They were run by hand against the seeded demo database while #127 was being built. No automated test covers them.

