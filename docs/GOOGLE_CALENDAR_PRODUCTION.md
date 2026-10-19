# Production Google Calendar

Calendar access is optional and separate from Google sign-in. Only the matching,
Google-authenticated Library User can connect their primary calendar. No local
refresh tokens are copied into production.

## Prerequisites

- Enable Calendar API and authorize the owned-events scope in the production project.
- Keep the existing sign-in callback and add
  `https://library.life.edu.ph/api/calendar/callback` to the production web client.
- Run `infra/aws/prepare_calendar_secret.py` with the authorized AWS profile.
  This adds `googleCalendarEncryptionKey` to the existing application secret,
  preserving all other values and never printing secret values.
- Keep the encryption key backed up through Secrets Manager version history.
  Do not rotate it without re-encryption or requiring users to reconnect.

## Release

The production workflow injects the Calendar enable flag, HTTPS callback, and
Secrets Manager key reference into the new ECS task definition. The existing
execution role already has read access to the application secret. No additional
AWS permissions, public endpoints, or service-account Calendar access are needed.

Migration `f63c942de570` adds two tables without modifying existing reservations.
The in-process worker uses PostgreSQL row locks and skip-locked selection so
overlapping ECS tasks do not process the same queued job concurrently. Each
event has a stable ID for retry protection. Google errors do not undo bookings.

For a future full CloudFormation stack update, pass `GoogleCalendarEnabled=true`
after preparing the application secret; its default remains disabled for new stacks.

## Verification and Rollback

Verify health and authorization, then sign in on production, connect Calendar,
and test booking creation, extension, early ending and cancellation. Read back
the real events and verify Manila time, booking-management and guideline links.
Leave only clearly labelled, explicitly approved test events for inspection.

The previous task definition is `life-library-production-api:18`. Reverting the
service to it disables Calendar without removing the additive migration tables.
Existing Google events remain. Do not downgrade tables containing user tokens
or restore a database snapshot as a routine application rollback.

Automatic booking emails remain disabled and are not part of this release.
