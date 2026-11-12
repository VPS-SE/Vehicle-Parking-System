# Security policy

## Supported versions

| Version | Supported |
|---|---|
| 1.1.x (current `main`) | Yes |
| 1.0.x | No, upgrade to 1.1 |

## Reporting a vulnerability

Please do not open a public issue for a security problem. Use GitHub's private reporting
instead: **Security** tab, then **Report a vulnerability**. Include the steps to reproduce,
the page or endpoint involved, and what an attacker could do.

We aim to acknowledge a report within 3 days and to fix confirmed issues in the next pull
request to `main`. This is a university project maintained by four students, so there is no
paid bug bounty.

## What is already in place

The security requirements (SEC-01 to SEC-10) are in the SRS, and how each was tested is in
Section 8 of `docs/part-3/system-validation-report.md`. In short:

- Passwords hashed with PBKDF2; accounts lock for 15 minutes after 5 failed sign-ins, and
  sign-in is rate limited per IP.
- Role checks on every view; Drivers, Gate Attendants and Lot Administrators see only their own
  functions.
- CSRF protection on every state change, HTTPS redirect, HSTS and secure, HTTP-only cookies when
  `DJANGO_DEBUG` is off; sessions expire after 30 idle minutes.
- An append-only audit log of privileged actions.
- Drivers' mobile numbers are masked on staff pages and never written to logs.
- Every pull request runs Gitleaks over the whole history and `pip-audit` on both
  requirements files. Bandit finds no high-severity issues (`docs/part-3/evidence/bandit.txt`).
  Secrets live in `.env`, which is never committed.
