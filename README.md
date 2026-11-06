# Vehicle Parking System

Vehicle Parking System is Team 10 Section C's Level-3 mini-project for Software Engineering (UE24CS341A), Semester 5, Department of CSE, PES University. Drivers find and book parking slots, gate attendants check vehicles in and out and take payments, and lot administrators manage lots, tariffs, staff and reports. It is a Django web app on PostgreSQL, with a separate FastAPI service that forecasts slot availability.

## Features by role

### Drivers

- Register, sign in, sign out, and reset password by email.
- Register vehicles at `/vehicles/`.
- Search slots by lot, vehicle type, and time at `/reservations/search/` with an occupancy forecast shown beside the result.
- Book parking and receive a confirmation page plus confirmation email with a booking reference.
- Cancel a booking.
- View booking history and unpaid balance at `/reservations/history/`.

### Gate attendants

- Dashboard and gate operations at `/gate/`.
- Check in a booked vehicle, with reallocation if the allocated slot is still occupied.
- Register walk-ins.
- Check out with parking and overstay charges.
- Record payments at `/gate/payments/`.
- Generate printable receipts.
- Correct entry and exit times after an outage.

### Lot administrators

- Manage lots and tariffs at `/lots/` and `/lots/tariffs/`: create, edit, archive, restore.
- Block a slot for a period and move affected bookings.
- Monitor live occupancy at `/lots/occupancy/`.
- Manage staff accounts and driver accessible-parking permits at `/accounts/staff/`: create, deactivate, reactivate.
- Run revenue and occupancy reports with CSV export at `/reports/revenue/` and `/reports/occupancy/`.
- Search audit logs at `/reports/audit/`.
- Apply charge waivers with a required written reason at `/billing/waivers/`.

### System behavior

- Race-safe allocation serialises concurrent bookings within a lot.
- No-show expiry adds a Rs 50.00 charge.
- Append-only audit log records staff actions.
- Health check at `/healthz`.
- Django admin at `/admin/`.

## Architecture

```text
Browser clients (drivers, gate attendants, administrators)
        |
        v
web (Django + Gunicorn, port 8000) <----> db (PostgreSQL 16)
        |                                  |  init scripts: btree_gist + forecast role
        |                                  |
        +-----------> forecast (FastAPI, internal port 8001)
        |
scheduler (expire_no_shows + send_reservation_notifications every 60s)

forecast-trainer (startup run, then weekly retrain) <----> db (read-only forecast_ro)
forecast-trainer <---------------------------------------> forecast_models volume
forecast <------------------------------------------------> forecast_models volume
```

`web` runs migrations and serves Django through Gunicorn. `scheduler` shares the web image, waits for healthy `db` and `web`, then runs periodic background management commands. `forecast` serves occupancy predictions from the latest trained model, and `forecast-trainer` retrains at startup and then weekly, retrying hourly until a model exists. `db` uses PostgreSQL 16 with initialization scripts in `docker/postgres/init/`.

## Tech stack

| Area | Technologies |
|---|---|
| Core language and web | Python 3.12, Django 5.2.18, Django REST Framework 3.18.3 |
| Database and serving | PostgreSQL 16 with `btree_gist`, psycopg 3, Gunicorn 26.2.0 |
| Forecast service | FastAPI 0.162.0, Uvicorn 0.54.0, scikit-learn 1.9.1, joblib |
| Frontend | Server-rendered Django templates with HTMX |
| Dev and quality | pytest 9, pytest-django, pytest-cov, ruff 0.17.0 |

## Getting started

### 1) Docker Compose

Copy the environment template:

```sh
cp .env.example .env
```

Edit `.env` with a generated Django secret key and local database and forecast-role passwords.

Start all services:

```sh
docker compose up --build
```

Check health at `http://localhost:8000/healthz`.

Run tests from the host against the Compose database:

```sh
docker compose up -d db
# Wait for db to be healthy in docker compose ps before running tests.
set -a
source .env
set +a
export POSTGRES_HOST=localhost
.venv/bin/pytest -q
```

Stop services:

```sh
docker compose down
```

Reset database volume:

```sh
docker compose down -v
```

### 2) Local run without Docker

Use Python 3.12 or newer and PostgreSQL 16:

```sh
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
# Edit .env with your local values, then export them into the shell.
set -a
source .env
set +a
python manage.py migrate
python manage.py runserver
pytest
```

For SQLite-based tests:

```sh
VPS_TEST_SQLITE=1 pytest
```

### Environment variables

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | Django secret key. |
| `DJANGO_DEBUG` | Debug mode toggle for local development. |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames Django accepts. |
| `POSTGRES_DB` | PostgreSQL database name. |
| `POSTGRES_USER` | PostgreSQL user name. |
| `POSTGRES_PASSWORD` | PostgreSQL user password. |
| `POSTGRES_HOST` | PostgreSQL host for Django. |
| `POSTGRES_PORT` | PostgreSQL host port. |
| `FORECAST_DB_PASSWORD` | Password used for the forecast read-only database role. |
| `FORECAST_URL` | Forecast service URL used by Django, or empty to disable forecast calls. |
| `GUNICORN_WORKERS` | Gunicorn worker count in Compose web service. |
| `EMAIL_HOST` | SMTP server hostname. |
| `EMAIL_PORT` | SMTP server port. |
| `EMAIL_HOST_USER` | SMTP account username. |
| `EMAIL_HOST_PASSWORD` | SMTP account password. |
| `EMAIL_USE_TLS` | SMTP TLS toggle. |
| `VPS_TEST_SQLITE` | Test backend switch (`1` for SQLite tests). |

## Demo data, no-show expiry, and forecast service

### Demo data

Seed the demo dataset:

```sh
python manage.py seed_demo_data --seed 2026
```

This creates lot **Demo Central** with 500 slots, tariffs by slot type, 120 drivers, and 30 days of reservations including completed stays, no-shows, cancellations, active parking, and future bookings. Running it again does not duplicate the demo lot.

### No-show expiry

`scheduler` runs `python manage.py expire_no_shows` every 60 seconds. A reserved booking expires after more than 15 minutes past start time, frees the slot, and adds a one-time Rs 50.00 no-show charge.

Server cron equivalent:

```cron
* * * * * cd /app && python manage.py expire_no_shows
```

### Forecast service

`forecast/` provides occupancy prediction for arrival times up to 24 hours ahead via `GET /v1/forecast`. The booking search page shows this forecast next to slot results. If `FORECAST_URL` is empty, or if the service does not respond within 2 seconds, booking search still works and shows forecast as unavailable.

Model training command:

```sh
python -m forecast.train.train
```

Compose behavior:
- `forecast-trainer` runs at startup and then weekly.
- Training uses the `forecast_ro` read-only role created by `docker/postgres/init/02-forecast-role.sh`.
- Set `FORECAST_DB_PASSWORD` before first initialization of a fresh database volume.

Run forecast without Docker:

```sh
python -m venv .venv-forecast
.venv-forecast/bin/pip install -r forecast/requirements-dev.txt
FORECAST_DB_URL=postgresql://forecast_ro:PASSWORD@localhost:5432/vps \
  .venv-forecast/bin/python -m forecast.train.train --model-dir models
FORECAST_MODEL_DIR=models .venv-forecast/bin/uvicorn forecast.app.main:app --port 8001
(cd forecast && ../.venv-forecast/bin/pytest)
```

Then start Django with `FORECAST_URL=http://localhost:8001` set.

## Testing and CI

### Local test commands

- Unit and integration tests (PostgreSQL): `pytest`
- Unit and integration tests (SQLite): `VPS_TEST_SQLITE=1 pytest`
- Coverage:
  1. `pytest --cov --cov-branch --cov-report=xml`
  2. `python scripts/check_coverage.py coverage.xml`
- Forecast service tests: `(cd forecast && ../.venv-forecast/bin/pytest)`
- System tests (running server required): `pytest -c tests/system/pytest.ini`

System tests in `tests/system/` read:
- `VPS_BASE_URL` (default `http://127.0.0.1:8100`)
- `VPS_HTTP_PROD_URL`
- `VPS_TLS_URL`
- `VPS_SERVER_LOGS`

`Playwright`, `axe-playwright-python`, and `Locust` are required for system and load testing and are installed separately from the requirements files. Load tests use the `locust_*.py` scripts in `tests/system/`.

Coverage gate defaults: 70% line and 60% branch.

### CI on every pull request

GitHub Actions runs:
- Ruff lint
- Forecast service tests
- Main test suite on PostgreSQL 16 with coverage and gate check
- `pip-audit` on both requirements files
- Gitleaks secret scan of full repository history

### Reported results

- 771 tests passed
- 95.94% line coverage
- 91.01% branch coverage
- 49 of the 51 Test Plan test cases pass, 2 are not run, none fail

Evidence and reports:
- [`docs/part-3/unit-test-report.md`](docs/part-3/unit-test-report.md)
- [`docs/part-3/code-coverage-report.md`](docs/part-3/code-coverage-report.md)
- [`docs/part-3/branch-coverage-report.md`](docs/part-3/branch-coverage-report.md)
- [`docs/part-3/system-validation-report.md`](docs/part-3/system-validation-report.md)
- [`docs/part-3/code-review.md`](docs/part-3/code-review.md)
- [`docs/part-3/code-review-2.md`](docs/part-3/code-review-2.md)
- [`docs/part-3/tc-audit.md`](docs/part-3/tc-audit.md)
- [`docs/part-3/evidence/`](docs/part-3/evidence/)

## Project structure

```text
vps/                          Django project apps: accounts, allocation, audit, billing, gate, lots, notifications, reports, reservations, vehicles
forecast/                     FastAPI forecast service and model training job
docker/postgres/init/         PostgreSQL initialization scripts
scripts/                      Utility scripts (includes check_coverage.py)
templates/                    Server-rendered Django templates
tests/                        Unit and integration tests
tests/system/                 Browser and load tests (Playwright and Locust scripts)
docs/                         Project documentation (part-1 and part-3)
videos/                       Demo video assets
compose.yaml                  Multi-service local environment
```

## Documentation links

- Part 1 deliverables: [`docs/part-1/`](docs/part-1/)
- SRS: [`docs/part-1/VPS_SRS.docx`](docs/part-1/VPS_SRS.docx)
- Test Plan: [`docs/part-1/VPS_Test_Plan.docx`](docs/part-1/VPS_Test_Plan.docx)
- SAD: [`docs/part-1/VPS_SAD.docx`](docs/part-1/VPS_SAD.docx)
- Diagrams: [`docs/part-1/diagrams/`](docs/part-1/diagrams/)
- Part 3 reports and evidence: [`docs/part-3/`](docs/part-3/)
- Demo video: [`videos/VPS-Sprint-1-Demo.mp4`](videos/VPS-Sprint-1-Demo.mp4)

## Team

Team 10, Section C.

| Name | SRN | GitHub |
|---|---|---|
|D Harikrishnan  | PES1UG24CS136 | [@dhkrish06](https://github.com/dhkrish06) |
| Dhruv Purushotham Raju | PES1UG24CS154 | [@dhruvpurushotham1718-ui](https://github.com/dhruvpurushotham1718-ui) |
| A Gitanjali | PES1UG24CS170 | [@git17616](https://github.com/git17616) |
| Vivian Sobers E | PES1UG24CS901 | [@VivianSobers](https://github.com/VivianSobers) |

Course: Software Engineering (UE24CS341A), Semester 5, Department of CSE, PES University.
