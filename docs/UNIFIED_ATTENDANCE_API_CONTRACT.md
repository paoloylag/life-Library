# Unified attendance: library QR compatibility contract

Status: proposed implementation contract, version 1.0.0. Prepared 2026-10-20 against `origin/main` commit `76a5ec8` in `paoloylag/life-Library`. This branch changes documentation only; the unified attendance backend has not been inspected or implemented.

## Scope and integration boundary

The unified attendance system must implement the browser-facing contract in [library-qr.openapi.json](library-qr.openapi.json), either directly or behind a library compatibility adapter. Keep the current `/api` paths and response shapes. Internal unified-system endpoints and database models may differ. The production browser origin is `https://library.life.edu.ph`; prefer routing the migrated endpoints through that origin.

The scope is QR issuance, identity verification, authenticated and guest check-in, plus the dependencies needed to keep those workflows working. Booking, calendar, email, directory administration, reporting and staff administration remain with the library service unless separately migrated. Moving the frontend's single `VITE_API_URL` moves **all** its API calls, so do not point it at a QR-only backend. Route selected paths through a gateway or retain a library adapter.

Shared `/api/auth/*` endpoints are also used by bookings and Google staff access. A new login cookie must continue to resolve the same library identity for those consumers. Either keep authentication in the library adapter, or provide a trusted server-side identity/session bridge. Do not assume a unified-system cookie is readable or trusted by the existing service.

## Required HTTP surface

The accompanying OpenAPI file specifies the QR compatibility surface, including request fields, success bodies and errors. All JSON uses UTF-8; timestamps are RFC 3339 with an explicit offset (prefer UTC `Z`); dates are `YYYY-MM-DD`. Identifiers and references are stable. Empty optional profile text is `""`, not null. Additive response fields are allowed; existing fields and enum values cannot change without a coordinated frontend release.

| Method and path | Authorization | Behavior |
| --- | --- | --- |
| GET `/api/auth/status` | Public | Google configuration status and allowed domain |
| GET `/api/auth/google?next=...` | Public | Browser redirect to Google; retain safe scan return path and query |
| GET `/api/auth/google/callback` | OAuth state | Verify Google callback, set session, redirect back |
| GET `/api/auth/me` | Library user | Identity and linked library profile; 401 when signed out |
| POST `/api/auth/logout` | Public | Clear user cookie; 204 |
| POST `/api/admin/login` | Public | Existing staff credential login; 204 with staff cookie |
| GET `/api/admin/me` | Staff | Staff identity and role for frontend access checks |
| POST `/api/admin/logout` | Public | Clear staff and user cookies; 204 |
| GET `/api/library/settings/display` | Public | Library name, QR wording and booking link |
| GET `/api/library/sessions/current` | Librarian, associate, QR display | Get or create daily session |
| POST `/api/library/sessions` | Librarian, associate | Same daily-session result, not forced rotation |
| POST `/api/library/scan/{token}` | Library user | Check in authenticated identity; no body |
| POST `/api/library/scan/{token}/guest` | Public + valid QR | Create visitor and check-in from supplied details |

The OpenAPI security alternatives indicate available cookies; role and active-account checks remain mandatory. An auditor cannot issue/read the daily QR. A QR-display account cannot access dashboards or other administrative APIs. Google-linked staff require an explicit active staff grant; a school email or faculty category alone grants no staff permissions.

## Authentication and identity

Browser fetches use `credentials: include`. Existing user sessions last 43,200 seconds (12 hours); staff sessions last 28,800 seconds (8 hours). Cookies are HttpOnly, path `/`, Secure in production; configure SameSite for the actual deployment. Cross-origin deployments require an explicit allowed origin, credentialed CORS and working preflight. Never use wildcard origins with cookies. Enforce trusted-origin checks for mutations at the new boundary and validate OAuth state. The current OAuth flow uses an additional middleware session cookie to preserve state.

The callback validates the provider token and verified email. Institution accounts use the configured Google hosted domain and Directory identity. Approved alternate Google accounts must resolve to their existing member profile under the current approval rules, not create a second person. Preserve mappings from Google subject and approved alternate account to library user ID/profile number and unified person ID. Email is mutable and must not be the only durable cross-system key.

Current callback errors redirect to the safe frontend destination with `auth_error=account_not_allowed` or `auth_error=google_auth_failed`. Unconfigured Google login returns 503 JSON. Invalid return destinations fall back to `/`; `/scan/{token}` with query parameters and `/book` are supported. Reject external/open redirects. Callback success returns to the frontend and does not itself record a visit: ScanPage loads `/api/auth/me`, then automatically posts the scan once. Manual retry is also possible.

An inactive user gets 401. A user with no active linked library profile cannot check in (403); `/auth/me` may still return a null profile. Preserve category strings (`student`, `faculty`, `non-teaching personnel`, `administrator`, `visitor`) and profile number/program/year/section/department. Existing UI currently renders an administrator as Student on the scan receipt; this is a frontend limitation, not a reason to reclassify the backend identity.

## Daily QR and check-in semantics

- Attendance days use **Asia/Manila** irrespective of the editable display timezone. A session expires at 23:59:59.999999 local time. Server time decides validity, inclusive of stored start/end bounds; a new date produces a new daily token.
- Repeated daily-session reads return the same valid URL and survive process restarts. The display polls every 60 seconds. `scan_url` points at the frontend scan page (including its configured base path), never the API POST route. Tokens are opaque to clients and must not reveal identity.
- Current tokens are deterministic HMAC values with only hashes stored. The replacement may use another secure issuance method if daily stability and expiry remain compatible. Avoid logging raw tokens. Concurrent first reads must create one effective daily session.
- Unknown, closed, not-yet-valid and expired tokens return 410 with `detail: "QR code is invalid or expired"`. Backend validation is mandatory even if a frontend `expires` query parameter is absent or manipulated.
- Authenticated scans derive the person from the session, never a submitted user ID. Write a visit with `source=qr`, `status=checked_in`, server timestamp and library location/context. This is check-in only: there is no QR checkout or occupancy toggle.
- Compare the most recent visit for the same profile and daily session (including manual visits). If elapsed time is **less than** `duplicateWindowMinutes * 60`, return 200 `action=duplicate` with the original timestamp and reference and write nothing. At the exact boundary, create a new visit. The setting defaults to 5 minutes and accepts 1–60; `DUPLICATE_SCAN_SECONDS=20` is not the active rule.
- Duplicate detection and insert must be atomic under concurrent requests. Return success only after durable commit. A newly written visit returns 200 `action=check_in`. Preserve `LC-` plus a minimum eight-digit legacy visit ID, or persist an equivalent stable legacy-reference mapping without collisions.
- `qrExpiryMinutes`, opening/closing hours and configurable display timezone do not currently control QR validity. Do not introduce opening-hour rejection or a shorter TTL as an accidental migration change.

## Guests and retry limitations

Guest JSON requires `name` (2–255 characters) and `purpose` (2–180); `organization` is optional/null, maximum 180. The UI requires organization, but the API does not. The current backend validates lengths before trimming, stores trimmed values, and rejects an active internal member with the same case-insensitive trimmed name (409, directing them to Google). Do not silently tighten these rules in a compatibility release.

Each successful guest request creates a new visitor identity and visit (`source=guest`, `status=checked_in`), returning a generated `user_number` such as `VIS-2026-A1B2C3`. Guest submissions currently have no duplicate suppression or idempotency key. Do not automatically retry a guest POST after an ambiguous timeout. Durable request-key idempotency would be a recommended coordinated frontend/backend improvement, not an existing guarantee. Authenticated retries within the duplicate window are safe, but retries after that window can create another visit.

## Errors

Business errors use JSON `{ "detail": "Human-readable message" }`. Preserve 401 (missing/expired/inactive identity), 403 (role or profile rejection), 409 (guest/member conflict), 410 (invalid QR), 422 (invalid payload), and 503 (Google unavailable/configuration missing). FastAPI field-validation 422 responses currently contain a `detail` array of validation issues; the schema preserves that distinction. Do not return an HTML login page or 200 error envelope to a JSON call. OAuth routes are browser redirects, not JSON fetches.

## Keep the rest of the library consistent

A successful scan must appear in the library attendance list, dashboard, reports/exports and user visit history/counts. These remain contractual dependencies even if their HTTP implementations stay with the library service. See [API_REFERENCE.md](API_REFERENCE.md) for the broader route inventory and the actual handlers in `backend/app/main.py` for response behavior.

Use one authoritative visit store with a library read adapter, or a durable outbox/projection into the library database. Never perform two independent best-effort writes. If projecting, use a unique external event ID, idempotent application, ordering/retry handling, reconciliation and an agreed visibility-lag target before rollout. The existing UI assumes committed visits can be read immediately; synchronous read-through is the default compatibility target.

Migration mapping must preserve: unified person ID ↔ library user ID/profile number; unified attendance ID ↔ legacy visit ID/reference; session/date/location; timestamp; source (`qr`, `guest`, `manual`); purpose; audit note and recorded-by identity where present. Preserve historical visits, archived members, approved alternate accounts and staff grants. Keep library attendance isolated from other unified-system locations. QR duplicates must also see a manual visit written by the retained library API.

Bookings share users, staff sessions and settings; leaving their routes on the library service still requires consistent identities and archived status. Staff account administration and duplicate-window setting updates must continue to affect the migrated operations. Avoid a copied configuration value that never receives updates.

## Cutover and acceptance checklist

1. Implement the compatibility adapter and identity mapping in a nonproduction environment. Register its callback URI and validate cookies/CORS from the real frontend origin. Keep production dev-login disabled (404); it is not required in the production contract.
2. Validate both staff password login and explicitly granted Google staff access. Verify auditor/QR-display role restrictions, sign-out and expired sessions.
3. Read the daily QR twice and after a restart: same day, same URL. Exercise concurrent first reads, midnight Manila rollover, closed/unknown tokens and exact expiry boundaries.
4. Complete school and approved-alternate Google flows; reject unverified/disallowed identities. Verify null/inactive profiles, safe return URLs, query preservation and booking sign-in.
5. Scan once, retry inside the configured window, scan at the boundary, and send concurrent requests: correct action/reference/count, no duplicate insert. Repeat after a manual check-in and with another user/location.
6. Check guest success, missing/oversized fields, internal-name conflict, expired QR and timeout behavior. Verify visitor numbers and history.
7. Verify each committed check-in in attendance, dashboard, profile history, reports and exports with correct Manila date, category and source. Compare migrated totals and references against the source data.
8. At cutover, stop legacy scan writes, reconcile the final delta, switch selected routes and issue the active QR. Either preserve active tokens through a temporary validator or explicitly refresh displays; old tokens must not become a second write path. Existing signed sessions need a validated bridge or a planned re-login.
9. Smoke-test scanning and retained booking/admin features. Rollback must reconcile all newly committed visits back to the legacy read/write system before reopening legacy writes; a route rollback alone is insufficient.

Before implementation, the unified-system team must confirm its API host, authentication/identity bridge, library location identifier, storage/read-projection ownership, staff-grant/settings synchronization, and history/cutover plan. These are integration decisions, not evidence that the target already supports this contract.

## Source evidence

- `frontend/src/ScanPage.tsx`: identity lookup, automatic scan, guest form, receipts and error consumption.
- `frontend/src/main.tsx`: daily QR fetching, 60-second refresh and staff routing.
- `frontend/src/api.ts`, `frontend/src/settings.ts`: shared API origin, credentialed fetch and public display settings.
- `backend/app/main.py`: route inputs, outputs, OAuth redirects and guest validation.
- `backend/app/services.py`: daily token/session bounds, duplicate logic, visitor creation.
- `backend/app/auth.py`: session duration, active account and role/grant checks.
- `backend/app/library_settings.py`: live duplicate-window configuration.
