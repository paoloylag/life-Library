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

- Verify an available production RDS snapshot and record its identifier/time.
- Record the currently deployed ECS task definition for rollback.
- Review/merge the release branch and run Deploy AWS production.
- Complete live school Google sign-in and approved-alternate-email checks.
- Confirm QR attendance still works; book, extend/end/cancel, inspect reports and roles.
- Review the initial resource policies before students begin booking.

AWS CLI SSO was expired during preparation. No production database, AWS
configuration, frontend assets, or running production service was changed.

See [Booking Module](BOOKING_MODULE.md) for restrictions and rollback guidance.
