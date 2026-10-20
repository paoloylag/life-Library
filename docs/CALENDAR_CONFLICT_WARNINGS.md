# Personal Calendar Conflict Warnings

Before a user confirms a booking, the booking form checks the connected account's
primary Google Calendar for overlapping busy events. It uses the existing
`calendar.events.owned` permission; no new OAuth scope is requested.

The check is advisory, not a reservation lock. A busy event displays a warning and
requires an explicit **Book Anyway** action. If Google cannot be checked, the
user can retry or select **Book Without Check**. Unconnected or disabled Calendar
integrations do not add a warning. The booking API still enforces library
availability, participant conflicts, opening hours and usage limits normally.

Cancelled, transparent/free and self-declined events are ignored. Recurring
instances and all-day busy events are included by Google's bounded event query.
Pagination is bounded, with a ten-second overall timeout; incomplete checks are
reported as unavailable rather than clear. Only an advisory state reaches the
browser. No event titles, descriptions, attendees' identities or tokens are
returned, logged or stored. Manual bookings do not read the selected user's
calendar; the check is only for the currently Google-authenticated organizer.

Changing resource or start time invalidates the warning. A warning override is
single-use and expires after 30 seconds, prompting a fresh check if necessary.
Events can change after checking, so the warning is not a guarantee that the
personal calendar will remain conflict-free. Secondary/shared calendars are not
checked. Extensions remain subject to the existing library availability checks.

API: `POST /api/calendar/conflicts`, with `resource_id` and optional timezone-aware
`starts_at`. Session length comes from the resource policy, never the caller.
No database migration or production configuration change is required.

Google method reference: https://developers.google.com/workspace/calendar/api/v3/reference/events/list
