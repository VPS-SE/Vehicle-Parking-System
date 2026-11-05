# Vehicle Parking System

A web application for managing parking slots and tracking vehicles. It is the Level-3 mini-project for Software Engineering (UE24CS341A), Semester 5, Department of Computer Science and Engineering, PES University.

## Team


Team 10, Section C.

| Name | SRN | GitHub |
|---|---|---|
|D Harikrishnan  | PES1UG24CS136 | [@dhkrish06](https://github.com/dhkrish06) |
| Dhruv Purushotham Raju | PES1UG24CS154 | [@dhruvpurushotham1718-ui](https://github.com/dhruvpurushotham1718-ui) |
| A Gitanjali | PES1UG24CS170 | [@git17616](https://github.com/git17616) |
| Vivian Sobers E | PES1UG24CS901 | [@VivianSobers](https://github.com/VivianSobers) |

## Planned stack

- Backend: Python, Django and Django REST Framework
- Model service: FastAPI
- Database: PostgreSQL
- Frontend: server-rendered Django templates

## Tooling

| Purpose | Tool |
|---|---|
| Version control | Git and GitHub |
| Agile planning and bug tracking | GitHub Projects |
| CI | GitHub Actions: ruff, PostgreSQL tests, coverage gates and security scans |
| Testing | pytest with branch coverage |

## Deliverables

Part 1 deliverables are in [`docs/part-1/`](docs/part-1/) as Word files:

| Deliverable | File |
|---|---|
| Software Requirements Specification | [`VPS_SRS.docx`](docs/part-1/VPS_SRS.docx) |
| Software Test Plan, with test cases | [`VPS_Test_Plan.docx`](docs/part-1/VPS_Test_Plan.docx) |
| Software Architecture and Design Specification | [`VPS_SAD.docx`](docs/part-1/VPS_SAD.docx) |

The UML diagrams are in [`docs/part-1/diagrams/`](docs/part-1/diagrams/) as PlantUML sources with rendered PNGs.

## Running locally

Use Python 3.12 or newer and a local PostgreSQL 16 database. Create the database
and user, then set their credentials in `.env` along with a generated Django
secret key. Django reads exported environment variables; it does not load `.env`
automatically. The example file uses shell-compatible values.

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

The database user needs permission to create the test database for PostgreSQL
tests. To run tests without PostgreSQL, use `VPS_TEST_SQLITE=1 pytest`.

### With Docker Compose

Install Docker with the Compose plugin, then copy the example environment file:

```sh
cp .env.example .env
```

Edit `.env` with a generated Django secret key and a local database password,
then start the services:

```sh
docker compose up --build
```

Open http://localhost:8000/healthz to check the application and database.
The web service runs migrations, then serves the app with Gunicorn using
`GUNICORN_WORKERS` worker processes (8 by default, one database connection each).
Gunicorn does not reload on source changes: run `docker compose restart web`, or use
`python manage.py runserver` on the host while developing. PostgreSQL data stays in a named volume. On first initialization,
the database gets `btree_gist` in the application database and `template1` so
new test databases also have the extension.

To run tests from the host, install `requirements-dev.txt` in the virtual
environment as above, then start the Compose database and export `.env`:

```sh
docker compose up -d db
# Wait for db to be healthy in docker compose ps before running tests.
set -a
source .env
set +a
export POSTGRES_HOST=localhost
.venv/bin/pytest -q
```

Stop the services with `docker compose down`. To reset the database, use
`docker compose down -v`; this removes the named volume and its data.

### No-show expiry

The Compose `scheduler` service shares the web image and environment. It waits for
the database and web service to be healthy (so migrations have finished), then runs
`python manage.py expire_no_shows` every 60 seconds. Reserved bookings expire only
when more than 15 minutes have passed since their start, freeing the slot and
recording a Rs 50.00 no-show charge. Repeated runs do not charge again.

On a server, run the same command every minute with cron, using the application's
Python environment and exported Django/database settings:

```cron
* * * * * cd /app && python manage.py expire_no_shows
```

### Demo data

To fill an empty database with the demo data set (STP Section 5), run:

```sh
python manage.py seed_demo_data --seed 2026
```

It creates the lot "Demo Central" with 500 slots (350 Standard, 60 Two-wheeler, 60 EV,
30 Accessible), a tariff for each slot type, 120 drivers, and 30 days of reservations:
completed stays with parking charges (most of them paid), no-shows, cancellations,
vehicles parked now, and future bookings. The same seed always gives the same plan. If
the demo lot already exists, the command adds nothing. For tests, `vps/factories.py` has
`make_*` functions for drivers, staff, vehicles, lots, tariffs, reservations, charges and
payments.

### Occupancy forecast

The forecast is a separate FastAPI service in `forecast/` (FR-FCST-01 to FR-FCST-03). For a
lot, a vehicle type and an arrival up to 24 hours ahead, `GET /v1/forecast` returns the chance
that an eligible slot is free, with a Low, Medium or High band. The search page shows it next
to the slot count. If the service does not answer within 2 seconds, or `FORECAST_URL` is
empty, search still works and the panel says "Forecast not available".

`python -m forecast.train.train` retrains the model from completed reservations. It connects
through the read-only `forecast_ro` role, which can read only the lot, slot and reservation
columns it needs. Until there are 4 weeks of history it trains on simulated arrivals instead,
and the page labels the result "Estimate". With Compose, the `forecast-trainer` service runs
the job at start-up and then once a week, and `forecast` serves the latest model. Set
`FORECAST_DB_PASSWORD` in `.env` before the database volume is first created; the role is made
by `docker/postgres/init/02-forecast-role.sh`.

To run it without Docker:

```sh
python -m venv .venv-forecast
.venv-forecast/bin/pip install -r forecast/requirements-dev.txt
FORECAST_DB_URL=postgresql://forecast_ro:PASSWORD@localhost:5432/vps \
  .venv-forecast/bin/python -m forecast.train.train --model-dir models
FORECAST_MODEL_DIR=models .venv-forecast/bin/uvicorn forecast.app.main:app --port 8001
(cd forecast && ../.venv-forecast/bin/pytest)
```

Then start Django with `FORECAST_URL=http://localhost:8001`.

## Status

Sprint 1 is under way. The Django project skeleton is in place. CI runs ruff, the test suite on PostgreSQL 16 with a 70% line and 60% branch coverage gate, pip-audit and a Gitleaks secret scan on every pull request.
