# Deviations from the SRS, SAD and Test Plan

Vehicle Parking System, Team 10, Section C. Final demo, 12 November 2026.

The SRS, SAD and Test Plan in `docs/part-1/` were written before development started. This page lists where the delivered system differs from them and why. Each change was made during a sprint, went through a pull request with CI, and has tests. Requirement IDs refer to the SRS.

## 1. Requirements (SRS)

### 1.1 Added requirements

| ID | Requirement | Why | Delivered in | Tested by |
|---|---|---|---|---|
| FR-LOT-05 | After booking, a Driver shall see a map of the lot showing the booked slot and the route from the entry gate to it, on the confirmation page and from My bookings. | Drivers at a large lot (292 slots at RR Back Gate) asked where in the lot their slot is. A slot code alone does not answer that. | PR #136 (issue #140) | TC-52 |
| FR-LOT-06 | A Lot Administrator shall see a live map of a lot with every slot coloured as free, reserved, occupied or blocked, refreshed at least every 30 seconds, and shall be able to find a parked vehicle by its registration number. | Gate staff are asked "where is my car?" and the occupancy table only gives counts. | PR #136 (issue #140) | TC-52 |

The live map refreshes every 10 seconds while the page is visible and stops when the tab is hidden.

### 1.2 Changed or clarified requirements

| ID | SRS text | What was delivered | Why |
|---|---|---|---|
| FR-LOT-01, FR-LOT-02 | Administrators create lots and slots. | The same, plus a seed command that creates the four PES University lots (RR Front Gate 136 slots, RR Back Gate 292, EC Engineering 262, EC Medical 142) with hours 07:00 to 22:00 and tariffs per slot type. It runs when the web container starts and does nothing once the lots exist. | The demo needed the real campus lots. Typing 832 slots through the form is not practical. (PRs #136, #137, #145; TC-53) |
| FR-RES-04 | A Driver shall be able to cancel a Reserved reservation. | The rule was built in Sprint 2, but no page linked to it. A Cancel booking button was added to My bookings in Sprint 3. | Found while recording the final demo (defect D-6). (PR #139; TC-54) |
| NFR-USE-02 | Pages work at 360 px and meet WCAG 2.1 AA colour contrast. | Unchanged, and met by a full redesign of every page in a light colour scheme. axe-core finds 0 violations on the 15 pages checked, and no page scrolls sideways at 390 px. | The first UI met the requirement but looked unfinished. (PRs #134, #135, #138; TC-42) |

### 1.3 Not delivered

No requirement in the SRS was dropped. Online payment was never in scope (the SRS records payments taken at the gate by cash, UPI or card). A mock payment gateway was discussed in Sprint 3 and deliberately left out.

## 2. Architecture and design (SAD)

| SAD section | Planned | Delivered | Why |
|---|---|---|---|
| 3.6 Technology stack, 4.3 API design | JSON endpoints under `/api/v1/` served by Django REST Framework, used by the HTMX pages and by tests. | No `/api/v1/` endpoints. Pages post HTML forms to Django views, and HTMX swaps in server-rendered partials. The service functions behind each endpoint in Section 4.3 exist and are called by those views. DRF is installed and only its permission base class is used. The JSON endpoints that do exist are the lot map feeds (`/lots/<id>/map/state.json`, `/lots/map/parked.json`) and the forecast service API (`/v1/forecast`, `/v1/health`), which is as designed. | Every screen is server-rendered, so nothing needed a separate JSON API. Building one would have added a second set of views to secure and test with no user of it. The role checks, validation and error rules in Sections 3.9 and 4.4 apply to the form views in the same way. |
| 3.6 Technology stack | nginx reverse proxy terminating TLS; static files served by nginx. | Gunicorn serves the application directly and WhiteNoise serves static files. There is no `deploy/nginx/` folder. TLS was tested on Gunicorn's own TLS listener with a self-signed certificate. | The project has no hosted server, only Docker Compose on a laptop. The Django security settings (HSTS, secure cookies, HTTPS redirect) are in place for when a proxy is added. |
| 3.6 Technology stack | cron on the application server runs the expiry job every minute and the retraining weekly. | A `scheduler` container in Compose runs `expire_no_shows` and `send_reservation_notifications` in a loop every minute, and a `forecast-trainer` container retrains the model on start and then every week. | Compose has no cron. A loop in a container does the same job and starts and stops with the rest of the system. |
| 4.7 Open issues: e-mail delivery | Celery or a database outbox polled by cron; the outbox was the plan. | Database outbox (`ReservationNotification`) sent by the scheduler. In development the console e-mail backend is used. | As planned. |
| 4.5 UX design: forecast panel | The forecast uses a model trained on past reservations, with "Estimate" shown when the baseline model is used. | The demo data has 20 days of history, so the service runs the simulated baseline model and the page labels it "Estimate". | The history model needs 4 weeks of data. The SAD already planned the "Estimate" label for this case. |
| 3.5 Architecture pattern | Layered modular monolith plus a separate forecast service. | As designed. New code (the lot map) follows the same layers: `vps/lots/plan.py` computes the layout, `vps/lots/services.py` reads slot states, views render a server-side SVG, and `static/js/lotmap.js` adds zoom, pan, live refresh and search on top. | |

The component, sequence and data-model diagrams in `docs/part-1/diagrams/` still describe the system. The lot map adds no tables; it reads the existing lots, slots, blocks and reservations.

## 3. Test Plan

| Test Plan item | Planned | What happened | Why |
|---|---|---|---|
| Test cases | TC-01 to TC-44 | TC-45 to TC-51 were added on 5 November for seven requirements with no test case (defect D-3). TC-52 to TC-54 were added on 12 November for the Sprint 3 work above. | Traceability check found the gaps. |
| Section 6, environment | A staging server with nginx and a real certificate. | One laptop: PostgreSQL 16 in Docker, Gunicorn, a self-signed certificate. testssl.sh and a ZAP scan were not run. | No server was available. |
| TC-41 | Timed trial with first-time users. | Not run. | Needs recruited users and a stopwatch session. |
| TC-51 | 99% availability over a month. | Not run. | Needs a deployed system monitored for a calendar month. |
| Load tests | Run against the deployed system. | Run on the laptop on 5 November with Locust; not repeated on the final code. The Sprint 3 changes after that date are pages, the lot map and seed data, none of which are on the booking path that was load tested. | Time. |

The results of every run are in `docs/part-3/`: the Unit Test, System Validation, Code Coverage and Branch Coverage reports, with raw output in `docs/part-3/evidence/`.

## 4. Process

| Planned | What happened | Why |
|---|---|---|
| Two sprints: Sprint 1 (14 to 23 October) and Sprint 2 (26 to 30 October). | A third sprint from 2 November: Part 3 testing, the code review fixes, reports, charge waivers, then the redesign, lot map, PES lots and the final demo. | Part 3 testing and the review findings needed their own sprint. |
| Every backlog item created before its sprint. | Issues #140 to #144 were added to Sprint 3 after the work was done, so the board records the lot map, PES lots, redesign, cancel button and README with their story points. | The work was requested during the final demo preparation and went straight into pull requests. |
