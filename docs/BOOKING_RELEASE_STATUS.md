# Booking MVP release preparation

Prepared on October 18, 2026 (Asia/Manila).

## Verified

- Release branch starts at production main `1fd607c`.
- Existing approved alternate-email implementation and deployed migrations retained.
- Booking migrations appended after production head `c28f9e031bd5`.
- 70 backend tests passed, including fresh and production-baseline SQLite upgrades.
- Disposable local PostgreSQL rehearsal passed: existing user retained, seven real
  resources created, no demo bookings, and repeat upgrade safe.
- Frontend production build passed with base path `/`.
- Earlier phone/iPad browser checks covered booking flows, modals, cancellation,
  report grouping, pagination, and toasts. Browser checks do not replace real Google OAuth.
- No Calendar event creation or outbound email included.
- Local demo seeding script excluded from this release.

## Required Before Rollout

- Backup and rollback preflight completed; details below.
- Review/merge the release branch and run Deploy AWS production.
- Complete live school Google sign-in and approved-alternate-email checks.
- Confirm QR attendance still works; book, extend/end/cancel, inspect reports and roles.
- Review the initial resource policies before students begin booking.

## Production Preflight

- AWS CLI authorization renewed for account `165115313524`, region `ap-southeast-1`.
- Library database is available, with 14-day automated backups and deletion protection.
- Rollback API task definition: `life-library-production-api:16` (one running task).
- Pre-release snapshot verified available: `life-library-pre-bookings-20261018-923c7fb`.
  Created October 18, 2026 at 4:18 PM Asia/Manila (08:18 UTC).
- Production application code, schema, frontend assets, and service configuration
  have not been changed. No other system was touched.

See [Booking Module](BOOKING_MODULE.md) for restrictions and rollback guidance.
