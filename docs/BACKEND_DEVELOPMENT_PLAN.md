# Backend and QR Check-In Development Plan

## Objective

Turn the current browser-based prototype into a persistent Life College library attendance application with server-issued daily QR codes, Google identity verification, librarian administration, auditable manual check-ins, and database-backed reports.

Development branch: `feature/backend-qr-checkin`

## LifeOS Alignment

The implementation will follow `lifeos-tenant-boilerplate` conventions while keeping library-specific behavior inside this repository.

Target layout:

```text
api/
  lifeos_library_attendance/
    __init__.py
    main.py                 FastAPI app, middleware, static frontend serving
    config.py               Environment-driven settings
    session.py              Signed application sessions and cookie policy
    auth/                   Librarian and Google OIDC flows
    attendance/             QR sessions, scans, manual check-ins
    users/                  Library-user roster and profiles
    reports/                Aggregations and export data
    db/                     SQLAlchemy models, session, migrations, seeds
src/                        React application using the LifeOS shell
public/                     LifeOS and Life College brand assets
docs/                       Setup, architecture, operations, and test guides
Dockerfile                  Multi-stage React build plus FastAPI runtime
docker-compose.yml          Application and PostgreSQL services
requirements.txt            Pinned Python dependencies
package.json                Root frontend and API scripts
.env.example                Environment contract without secrets
```

Uniform conventions:

- React, TypeScript, Vite, Lucide icons, and the LifeOS shell/navigation patterns.
- FastAPI configured from environment variables through `pydantic-settings`.
- One production container serves the compiled React app and API.
- Signed, HTTP-only application cookies; secure cookies outside local development.
- PostgreSQL locally and Amazon RDS-compatible PostgreSQL in production.
- Product roles and library data remain owned by this application.
- No source files are imported from the old LifeTrack repository.

## Authentication Model

### Librarians

- Email/password login with Argon2 password hashing.
- Roles: `library_admin`, `librarian`, and optional `report_viewer`.
- Protected administrative routes and API endpoints.
- Session expiry, logout, disabled-account enforcement, and audit logging.

### Library Users

- Google OpenID Connect using the Life College Workspace domain `life.edu.ph`.
- Validate issuer, audience, signature, email verification, hosted-domain claim, state, and nonce.
- Match the verified Google email or durable Google subject to an active library-user profile.
- Do not accept profile fields sent by the browser as identity evidence.
- Visitors use a librarian-approved/manual workflow in the MVP; external Google accounts can be added later as a separate policy.

### LifeOS Compatibility

- Preserve a durable `people_id` field for future LifeOS identity linkage.
- Keep the session payload and role boundaries compatible with the tenant-boilerplate pattern.
- LifeOS SAML can later become an additional librarian sign-in provider without changing attendance records.

## Attendance Data Model

- `librarians`: local administrative identities and roles.
- `library_users`: common identity for student, faculty, non-teaching, administrator, and visitor categories.
- `student_profiles`: program, year level, and section fields for students.
- `google_identities`: provider subject, verified email, hosted domain, and last login.
- `academic_periods`: academic year and semester date boundaries.
- `library_sessions`: server-issued daily QR token hash, validity, status, and issuing librarian/system actor.
- `library_visits`: immutable check-in event, user, session, timestamp, and source.
- `attendance_adjustments`: correction reason, before/after values, librarian, and timestamp.
- `system_settings`: library name, timezone, duplicate window, QR schedule, and reporting defaults.
- `audit_events`: authentication and administrative actions without storing OAuth tokens.

Dates are stored in UTC and displayed in `Asia/Manila`. QR tokens are stored only as hashes.

## QR Check-In Contract

1. The backend creates or returns the active QR session for the local calendar day.
2. The QR contains a public HTTPS scan URL with an opaque random token.
3. Scanning opens a mobile-first verification page.
4. The user signs in with Google if no valid application session exists.
5. The backend validates the Google identity and active roster profile.
6. `POST /api/attendance/scan/{token}` validates token status and expiry atomically.
7. The backend applies duplicate-scan protection and creates one immutable visit.
8. The API returns a receipt with user, category, check-in time, and reference number.
9. The dashboard receives the new visit through polling initially; server events can follow later.

The frontend will no longer generate authoritative tokens or write attendance to `localStorage`.

## Delivery Phases

### Phase 1: Boilerplate-Aligned Foundation

- Move the app toward the root `src/` and `api/lifeos_library_attendance/` layout.
- Add root scripts matching the boilerplate: `dev`, `api`, `build`, and `preview`.
- Add the multi-stage Dockerfile and app-plus-database Compose services.
- Centralize environment settings, CORS, cookies, public URLs, and health checks.
- Add Alembic and an initial schema migration.
- Add local seed commands for librarians and representative library users.

Exit criteria: a clean clone can start the app and PostgreSQL from documented commands, run migrations, and pass health checks.

### Phase 2: Authentication

- Implement librarian login/session/logout and route protection.
- Complete Google OIDC authorization-code flow with state and nonce validation.
- Implement library-user profile matching and clear inactive/unmatched states.
- Add authentication audit events and safe error handling.
- Document local desktop OAuth and public HTTPS mobile OAuth setups.

Exit criteria: a librarian and a rostered `@life.edu.ph` user can each establish, inspect, and end a secure session.

### Phase 3: Authoritative Daily QR

- Create daily QR session endpoints and automatic rotation in `Asia/Manila`.
- Generate cryptographically random tokens and persist only their hashes.
- Support active, expired, revoked, and replaced states.
- Connect dashboard and `/qr-display` to the active backend-issued URL.
- Remove browser-generated production tokens.

Exit criteria: only the current backend-issued QR can reach an eligible check-in flow, including after server restart.

### Phase 4: Check-In and Manual Attendance

- Implement transactional QR check-in and duplicate protection.
- Implement librarian manual check-in with automatic or authorized manual time.
- Record source, actor, reason, and adjustment history.
- Connect Attendance, Dashboard, and Library Users pages to API data.
- Support search and surname-first sorting from the database.

Exit criteria: QR and manual check-ins persist once, appear across all relevant views, and survive refresh/restart.

### Phase 5: Reports and Settings

- Replace seeded reports with database aggregations.
- Implement all existing period, category, program, year, section, and grouping filters.
- Drive charts, executive summary, Excel, and PDF from one server-filtered dataset contract.
- Persist MVP settings and academic periods.
- Add pagination and sensible query limits.

Exit criteria: dashboard counts and exports reconcile with raw attendance records for the same filter set.

### Phase 6: Quality, Security, and Deployment

- Add unit, API integration, migration, and browser end-to-end tests.
- Test expired/replayed QR tokens, duplicate scans, domain rejection, unmatched users, and permissions.
- Add CI for Python lint/tests, TypeScript checks, production build, and migration validation.
- Deploy FastAPI plus PostgreSQL behind HTTPS; GitHub Pages may remain a preview only.
- Configure production Google OAuth redirect URIs and secrets.
- Add backups, retention policy, restore rehearsal, rate limiting, and monitoring.

Exit criteria: a phone on any network completes Google sign-in and check-in against staging, with audit and recovery procedures verified.

## Initial API Surface

```text
GET    /healthz
GET    /api/auth/session
POST   /api/auth/login
POST   /api/auth/logout
GET    /api/auth/google
GET    /api/auth/google/callback
GET    /api/library-users
GET    /api/library-users/{id}
GET    /api/library-users/{id}/visits
GET    /api/attendance
POST   /api/attendance/manual
POST   /api/attendance/scan/{token}
GET    /api/qr/current
POST   /api/qr/rotate
POST   /api/qr/revoke
GET    /api/dashboard
GET    /api/reports/summary
GET    /api/settings
PUT    /api/settings
```

## Test Strategy

- Unit tests: token hashing, expiry, duplicate rules, timezone boundaries, roles, and report calculations.
- API tests: authentication, authorization, validation, pagination, filters, and transaction behavior.
- Database tests: migrations up/down, constraints, concurrency, and seeded roster matching.
- Browser tests: librarian login, QR display, Google callback simulation, mobile scan, success receipt, and manual check-in.
- Security tests: open redirects, forged cookies, OAuth state/nonce mismatch, cross-domain accounts, replayed QR tokens, and unauthorized report access.

## Immediate Work Queue

1. Restructure to the LifeOS boilerplate layout without changing visible behavior.
2. Add PostgreSQL to the app service, Alembic migrations, and deterministic seed data.
3. Create the session/auth module and protect librarian APIs.
4. Implement backend-owned daily QR issuance and connect the display.
5. Complete Google OIDC roster matching.
6. Implement transactional check-in and connect the three core views.
7. Add automated tests before expanding reporting and settings.

## Definition of MVP Complete

- Librarians authenticate before accessing administrative views.
- The backend automatically issues one active daily QR code.
- A rostered Life College user can scan, authenticate with Google, and record one check-in.
- Duplicate scans do not create unintended visits.
- Librarians can record and audit manual check-ins.
- Dashboard, attendance, library-user history, and core reports use the same PostgreSQL records.
- The flow works from a real mobile phone through public HTTPS.
- Secrets are not committed, migrations are reproducible, tests pass in CI, and backups are configured.
