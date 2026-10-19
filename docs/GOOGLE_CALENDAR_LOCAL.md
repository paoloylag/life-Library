# Local Google Calendar testing

Calendar is opt-in and disabled unless `GOOGLE_CALENDAR_ENABLED=true`.
Local and production connections use separate OAuth clients and encryption keys.
See `GOOGLE_CALENDAR_PRODUCTION.md` for production deployment safeguards.

## Google Cloud setup

1. Select the development OAuth client's Google Cloud project.
2. Enable **Google Calendar API** under APIs & Services > Library.
3. Open Google Auth Platform > Data Access > Add or remove scopes. Add
   `https://www.googleapis.com/auth/calendar.events.owned`.
4. In Google Auth Platform > Clients, edit the **local development** web client.
   Keep the sign-in callback and add this authorized redirect URI:
   `http://127.0.0.1:8001/api/calendar/callback`.
5. If the OAuth app uses External / Testing, add the testing school accounts in
   Audience > Test users. Workspace policy may require administrator approval.

The normal sign-in scope remains `openid email profile`. Calendar access is
requested only after the user clicks Connect Google Calendar. The selected
Google subject must match the currently signed-in Library User. An account
chooser and explicit Calendar consent are required. Declining does not prevent
booking. Testing-mode refresh tokens may expire, requiring reconnection.

## Local environment

The Git-ignored `.env` contains:

```dotenv
GOOGLE_CALENDAR_ENABLED=true
GOOGLE_CALENDAR_REDIRECT_URI=http://127.0.0.1:8001/api/calendar/callback
GOOGLE_CALENDAR_ENCRYPTION_KEY=<Fernet key generated locally>
```

Keep the encryption key private and backed up with the other local secrets.
Changing or losing it requires users to reconnect their calendars. Never put
tokens or this key in frontend environment variables or Git.

Local startup creates the two new tables without changing existing bookings.
Migration `f63c942de570` is included in the reconciled release, but do not
run Alembic blindly against the legacy local database initialized by create_all.

## Behavior

- A user connects from the public booking page after Google sign-in.
- Current/upcoming bookings are queued when connected. New bookings, extensions,
  early endings and cancellations update the durable queue in the booking transaction.
- A local async worker checks the queue every five seconds. It creates/updates an
  event in the booker's **primary** calendar; it does not send attendee invitations.
- Events contain the resource, Reservation #, Manila time, booking-management
  link, pass reminders and the relevant guideline link. Other members' personal
  information is not copied into the event.
- The stable provider event ID prevents duplicate inserts after interrupted requests.
- The refresh token is encrypted at rest. Access tokens are refreshed as needed
  for each job and kept in memory, never returned to the browser.
- Transient failures retry with increasing delay (up to five attempts). Users can
  retry failed syncs or reconnect after expired/revoked consent. Booking success
  does not depend on a successful Google API request.
- Disconnect deletes the local credential. It leaves existing Google events
  intact and stops further updates; the user can revoke consent in Google Account.
- Existing manual bookings sync to the selected organizer when their user ID is
  recorded and they have connected their calendar. Other room members are not synced.

Google's owned-events scope can access events on calendars the user owns. The
application code only writes its own deterministic booking event IDs; a primary
calendar integration cannot use the narrower app-created-secondary-calendar scope.

## Test checklist

1. Sign in at `http://127.0.0.1:5173/library/book` with a real school account.
2. Connect Google Calendar and approve the same account.
3. Create a local booking and verify one private event appears with its Reservation #.
4. Extend/end the session and verify the same event's end time changes.
5. Create then cancel a future booking and verify its event is removed.
6. Disconnect and verify new bookings still work without new calendar events.

Automated tests use mocked Google responses; live consent/event verification
requires the Google Cloud changes and a human account. No real calendar events
are created by automated regression tests.
