# Third-party notices

The Vehicle Parking System code is released under the MIT License (see `LICENSE`). It uses the
components below, which keep their own licenses. Versions are the ones pinned in the
requirements files.

## Bundled in this repository

| Component | Where | License |
|---|---|---|
| Inter and Inter Tight fonts | `static/fonts/` | SIL Open Font License 1.1, full text in `static/fonts/LICENSE-Inter.txt` |

## Loaded at runtime

| Component | How | License |
|---|---|---|
| HTMX 2.0.4 | `<script>` from unpkg.com in `templates/base.html` | BSD Zero-Clause (0BSD) |

## Python packages: web application (`requirements.txt`)

| Package | Version | License |
|---|---|---|
| Django | 5.2.18 | BSD-3-Clause |
| Django REST Framework | 3.18.3 | BSD-3-Clause |
| psycopg (binary) | 3.3.6 | LGPL-3.0-only |
| Gunicorn | 26.2.0 | MIT |
| WhiteNoise | 6.12.0 | MIT |

psycopg is used unmodified as a separately installed library, which the LGPL allows without
applying the LGPL to this project.

## Python packages: forecast service (`forecast/requirements.txt`)

| Package | Version | License |
|---|---|---|
| FastAPI | 0.162.0 | MIT |
| Uvicorn | 0.54.0 | BSD-3-Clause |
| scikit-learn | 1.9.1 | BSD-3-Clause |
| joblib | 1.6.0 | BSD-3-Clause |
| psycopg (binary) | 3.3.8 | LGPL-3.0-only |

These pull in NumPy and SciPy (BSD-3-Clause), Starlette (BSD-3-Clause) and Pydantic (MIT).

## Development and test tools (`requirements-dev.txt`, `forecast/requirements-dev.txt`)

pytest (MIT), pytest-django (BSD-3-Clause), pytest-cov (MIT), Ruff (MIT) and HTTPX
(BSD-3-Clause, forecast tests only). The system tests also use Playwright (Apache-2.0), axe-core (MPL-2.0, through
axe-playwright-python) and Locust (MIT), which are installed separately and not shipped.

## Container images

`postgres:16` (PostgreSQL License) and `python:3.12-slim` (Python Software Foundation License,
plus the Debian packages in the image).
