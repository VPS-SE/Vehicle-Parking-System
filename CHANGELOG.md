# Changelog

All notable changes to the Vehicle Parking System. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/). Pull request numbers are in brackets.

## [1.1.0] - 2026-11-12

Final demo release, end of Sprint 3.

### Added

- Lot map for drivers: the confirmation page and My bookings show where the booked slot is in
  the lot and draw the route from the entry gate (FR-LOT-05) [#136].
- Live lot map for administrators: every bay coloured by state, refreshed every 10 seconds,
  with search by registration number across lots (FR-LOT-06) [#136].
- The four PES University lots (RR Front Gate, RR Back Gate, EC Engineering, EC Medical, 832
  slots) with hours and tariffs, created automatically when the web container starts [#136, #137].
- Cancel booking button for reserved bookings in My bookings (FR-RES-04) [#139].
- Deviations from the SRS, SAD and Test Plan in `docs/part-4/deviations.md`; Sprint 2 and
  final walkthrough videos in `videos/` [#146].
- License (MIT), third-party notices, contributing guide, code of conduct, security policy,
  issue templates and this changelog.

### Changed

- Every page redesigned with a shared design system and a light colour scheme; 0 axe-core
  violations, no sideways scrolling at 390 px [#134, #135].
- README rewritten with screenshots, architecture, booking rules and badges [#132, #133].
- Test reports re-run on the final code: 816 app tests, 96.16% line and 91.28% branch
  coverage, 52 of 54 Test Plan cases passing [#146].

### Fixed

- Occupancy-by-slot-type table headers and totals now line up with their columns [#138].
- PES lots seeded before any admin account existed had no tariffs, so their bookings could not
  be checked out (defect D-7) [#145].

## [1.0.0] - 2026-11-06

First complete release, covering Sprints 1 to 3 of the course project.

### Added

- Accounts: driver registration and sign-in, password reset by e-mail, account lockout and
  rate limiting, staff accounts and deactivation, accessible-parking permits [#75, #76, #79,
  #80, #93, #101, #116].
- Vehicles: register up to five vehicles, with protected removal while a booking is live
  [#77, #92].
- Lots and slots: lot and slot management, tariffs per slot type, blocking a slot for a period
  with automatic moves for affected bookings [#71, #81, #94, #103, #109, #117].
- Search and booking: availability search, nearest-slot allocation that is safe under
  concurrent bookings, booking limits, cancellation with a late fee, no-show expiry, booking
  history and e-mail notifications [#73, #74, #82 to #88, #95, #98, #105, #112, #114].
- Gate: one-screen console, check-in with reallocation when the slot is still occupied,
  walk-ins, check-out with parking and overstay charges, payments by cash, UPI or card,
  printable receipts and time corrections after an outage [#91, #96, #99, #100, #102, #104,
  #107, #108, #110, #111, #115].
- Reports: live occupancy, revenue and occupancy reports with CSV export, append-only audit log
  with search, charge waivers [#97, #118, #123 to #126, #129].
- Occupancy forecast: separate FastAPI service with weekly training; search keeps working when
  it is down [#127].
- Delivery: Docker Compose with Gunicorn, CI with lint, PostgreSQL tests, coverage gate,
  pip-audit and Gitleaks; Part 3 test reports, system and load tests [#64 to #67, #120 to #122,
  #128, #131].

### Fixed

- Booking deadlocks and false "no slot available" errors under 50 concurrent users
  (defect D-4) [#130].
- Code review findings F1 to F7 and G1 to G3 [#121].

[1.1.0]: https://github.com/VSP-SE/Vehicle-Parking-System/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/VSP-SE/Vehicle-Parking-System/releases/tag/v1.0.0
