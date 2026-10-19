# Facility booking MVP

## Release scope

Resource booking is independent of attendance QR check-ins. Google Calendar
event creation and outbound email are not included.

- Public home `/` opens Google sign-in and My Bookings. `/book` starts resource selection.
- Staff sign-in: `/staff`. Explicit Google role grants are managed in Staff Accounts.
- Librarian overview: `/bookings`; manual entry: `/bookings/manual`.
- Google-authenticated active students and staff can book. Approved alternate
  Google emails remain supported. Visitors and local test-login sessions cannot book.
- Librarian and Librarian Associate can manually book for existing Library Users.
  Auditors have read-only access; only Librarians manage resource policies and types.
- Booking hours: configurable in Settings, default daily 06:00-18:00 Asia/Manila.
  Entire sessions and extensions must fit. Attendance hours remain independent.
- Book Now uses server time. Book Later permits reservations within the next 24 hours.
- Nap Pod sessions are 45 minutes, with an initial 90-minute maximum including extensions.
  Computers have a maximum of 120 minutes. Collaboration Room policy is configurable.
- Collaboration Rooms require at least three distinct people including the organizer,
  selected from active Library Users. Student organizers can select students only.
- Nap Pod and Collaboration Room guidelines require fresh agreement per booking;
  the version, full text, actor and timestamp are saved with the booking audit.
- Public guidelines: `/guidelines/nap-pod` and `/guidelines/collaboration-room`.
- Overlapping bookings for the same resource or person are rejected.
- Extension eligibility includes resource, user, closing-time and usage-limit checks.
- End Session releases unused time. Cancel Booking releases upcoming reservations,
  retains audit/history, and excludes cancelled bookings from utilization reports.
- Availability refreshes every minute; session-ended prompts need an open page.
- Confirmation toasts last six seconds; booking error toasts auto-dismiss after 1.5 seconds.
- Usage analytics has resource/date filters, charts, CSV export and paginated breakdowns.

## Production migration

The deployed migration chain is preserved:
`a19d6e74c2f1 -> b17e8d920ac4 -> c28f9e031bd5 -> f32b761a902d -> d41a720bc358 -> e52b831cd469`.

The new additive migration creates only `staff_google_access`; no existing users
are granted staff roles automatically. A full Librarian must grant access explicitly.
Existing password accounts can be linked only with the same current role and email.

The booking migration creates seven initial resources: Nap Pods 1-4,
Collaboration Rooms 1-2, and Computer 1. No demo users, bookings or historical
attendance are added. Review the initial resource policies before public use.

The old local development checkout has tables created outside Alembic. Do not
stamp or migrate that database blindly. This reconciled release branch is the
deployment source; preserve local data separately.

## API

- `GET /api/bookings/identity`: Google booking eligibility.
- `GET /api/bookings/availability`: public availability without user details.
- `GET /api/bookings`: own history, or staff-wide view.
- `POST /api/bookings`: reserve now or at a timezone-aware future start.
- `POST /api/bookings/{id}/extend`: extend an eligible active session.
- `POST /api/bookings/{id}/end`: end an active session early.
- `POST /api/bookings/{id}/cancel`: cancel an upcoming booking.
- `GET/POST /api/bookings/resources`, `PUT /api/bookings/resources/{id}`: inventory.
- `GET/POST /api/bookings/resource-types`: list types or create a custom type.
- `GET /api/bookings/reports/usage`: staff summaries with date bounds.

User requests explicitly send `X-Booking-Mode: user`; manual requests send
`X-Booking-Mode: manual`. Backend authentication and permissions are authoritative.

## Release checklist

1. Full backend suite and fresh/production-baseline migration tests pass.
2. Production-base frontend build and browser checks pass.
3. Verify an available pre-release RDS snapshot and preserve the prior ECS task definition.
4. Commit/review the release branch, then merge approved changes to main.
5. Run Deploy AWS production through GitHub Actions. Migration failure stops rollout.
6. Verify real Google sign-in, QR attendance, booking/cancellation, reports and role restrictions.
7. Confirm production has no development logins or demo bookings.

Rollback: revert frontend/API images to the previous release if needed. Leave the
additive booking tables intact; do not downgrade/drop tables with real bookings.
Restore an RDS snapshot only under a separately approved recovery procedure.
