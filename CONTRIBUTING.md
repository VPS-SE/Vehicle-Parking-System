# Contributing

Vehicle Parking System is the Team 10 project for Software Engineering (UE24CS341A) at PES
University. This page is how the team works on it; outside contributions follow the same rules.

## Where work comes from

Every change starts as an issue on the [VPS project board](https://github.com/orgs/VSP-SE/projects/2):
a user story, task or bug linked to its SRS requirement (FR-..., NFR-..., SEC-...) and epic, with
story points, an assignee and a sprint. Pick up only issues assigned to you, and move them through
Backlog, Ready, In progress, In review and Done.

## Setting up

Follow **Quick start** in the README: Docker Compose, or a virtualenv with a local PostgreSQL 16.
Use `python manage.py seed_demo_data --seed 2026` for a realistic data set. The four PES lots are
created automatically when the web container starts.

## Branches and commits

- Branch from `main`: `feat/<topic>`, `fix/<topic>`, `docs/<topic>`, `test/<topic>` or
  `chore/<topic>`. `main` is protected, so all changes go through a pull request.
- Commit messages are `type: message`, 4 to 6 words, lower case, with no trailers, for example
  `fix: align occupancy table columns`. Types: `feat`, `fix`, `docs`, `test`, `refactor`,
  `chore`.

## Code

- Python 3.12, Django 5.2, server-rendered templates with HTMX. Business rules go in each app's
  `services.py`; views authenticate, check the role, validate with a form, call one service
  function and render (see the SAD, Section 4.1).
- Write the test first for rules whose correctness is hard to see by eye: charges, time windows,
  allocation and concurrency.
- Run before pushing:

  ```sh
  ruff check .
  pytest --cov --cov-branch --cov-report=xml && python scripts/check_coverage.py coverage.xml
  ```

  CI fails below 70% line or 60% branch coverage.
- Pages must work at 360 px wide and pass WCAG 2.1 AA contrast. Use the colour tokens in
  `static/css/vps.css` rather than new hex values.
- Never commit `.env`, data dumps or credentials. Gitleaks scans every pull request.

## Pull requests

Fill in the pull request template: the issue it closes, the requirements and test cases it
covers, and how you tested it. The PR is raised by the member assigned to the issue and reviewed
and merged by the repository owner. CI (lint, forecast tests, the PostgreSQL test suite with the
coverage gate, and the security scans) must be green before merging.

## Documents

The SRS, SAD and Test Plan are in `docs/part-1/`. If a change departs from them, add a row to
`docs/part-4/deviations.md` in the same pull request. Test reports and raw evidence are in
`docs/part-3/`.

## Conduct

Everyone working on the project follows the [Code of Conduct](CODE_OF_CONDUCT.md).
