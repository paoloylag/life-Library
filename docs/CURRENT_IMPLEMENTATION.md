# Current Implementation Status

Last verified: September 18, 2026

## Implemented and verified

- FastAPI backend image builds with Docker.
- Docker Compose starts PostgreSQL 16 and the API with health checks.
- PostgreSQL data persists in a named Docker volume.
- Alembic applies the initial attendance schema before the API starts.
- Direct local development continues to use SQLite by default.
- Google OpenID Connect authenticates Life College accounts.
- Google Directory API reads each Workspace user's organizational unit.
- `/Students` maps to Student.
- `/Academics/Faculty` maps to Faculty.
- All other organizational units map to Non-Teaching Personnel.
- Local Docker mounts the service-account JSON read-only from a path stored only
  in the ignored `.env` file. The key is not copied into the image.
- Dashboard metrics and recent activity are read from PostgreSQL.
- Attendance search, user-category filters, manual check-ins, and visitor QR
  check-ins are persisted through FastAPI.
- Library Users provides backend search, surname ordering, profile details, and
  complete visit histories.
- Administrators can add and edit library-user profiles in Library Users,
  including student, faculty, non-teaching, administrator, and visitor records.
  Auditor and librarian accounts retain read-only directory access. Google-linked
  email, number, and category are not manually editable.
- Development Docker startup applies deterministic roster and attendance seeds;
  production startup never seeds data.
- Reports now read filtered attendance from FastAPI/PostgreSQL rather than the
  frontend seed store. The Reports view, Excel workbook, and PDF use the same
  backend aggregation and filters.
- Report endpoints are `GET /api/library/reports`,
  `GET /api/library/reports/export.xlsx`, and
  `GET /api/library/reports/export.pdf`. They require the librarian session in
  production; local development follows the existing development bypass.
- Exports include executive statistics, categories, student breakdowns,
  attendance trends, peak hours, semester comparisons, and filtered check-ins.
  Excel has sized columns, branded headers, and charts; PDF has charts and tables.

## Reporting calendar and limitations

- Academic year begins on the first weekday of August. First semester is
  August-December; second semester is January-May. Dates outside those windows
  are labeled Outside Semester.
- Student open days are Tuesday-Friday, 9:00-18:00. Staff open days are
  Monday-Friday, 7:00-17:00. For a mixed-user report, the open-day denominator
  uses Monday-Friday. Holiday closures are not yet excluded.
- Historical program, year-level, section, and department reports use the
  user's current profile because visits do not yet store a profile snapshot.
- Average weekly and monthly visits divide by calendar weeks and months in the
  selected date range. Average daily visits divide by scheduled open days.

## Library settings

- Settings and their audit history are now stored in the backend database.
  Production reads and writes require a librarian session. Local development
  follows the existing librarian-auth bypass.
- The Settings page loads and saves through `/api/library/settings`. If the
  backend has no saved settings, it offers browser-saved values for a one-time
  manual save to the shared backend. Browser storage is cleared only after
  that save succeeds.
- The QR display reads only its public wording from
  `/api/library/settings/display`. QR duplicate prevention uses the saved
  scan window. Reports use the saved initial grouping and user-type filter.
- Opening hours, timezone, current term, school reference lists, planned
  librarian roles, visitor fields, and retention years are stored but are not
  yet enforced by attendance, account provisioning, or automatic deletion.

## Librarian access

- The daily QR URL, dashboard, users, attendance, reports, and Settings API
  require a signed-in librarian account even in local development.
- Administrator may manage Settings and attendance. Librarian may manage QR
  display and manual check-ins. Auditor may view dashboard, users, attendance,
  and reports but cannot retrieve the daily QR URL or change attendance.
- Manual check-ins retain the signed-in librarian ID and return their name in
  attendance history. Real accounts can be created with
  `python -m app.create_librarian`, choosing a role at the prompt.
- Development test accounts require `APP_ENV=local` and
  `ENABLE_DEV_LIBRARIANS=true`. The role picker is shown only in Vite dev mode.
  Test accounts are refused when the opt-in is off or the backend is not local.
  Never expose the opt-in local server to untrusted networks.

## Google Directory credentials

The backend uses the locally stored service-account JSON and impersonates
`dt@life.edu.ph` through Workspace domain-wide delegation. The approved scope is
`https://www.googleapis.com/auth/admin.directory.user.readonly`.

Docker mounts the JSON read-only from the host path configured in the ignored
`.env` file. For an AWS-hosted process, `GOOGLE_SERVICE_ACCOUNT_SECRET_ID`
selects Secrets Manager instead. The backend uses the ECS task role to fetch
the JSON into memory and the secret ARN takes precedence over a configured file.
The ARN must be requested in its own AWS region (`ap-southeast-1` for the
current secret). The backend image has been built, smoke-tested, and pushed to
ECR as `165115313524.dkr.ecr.ap-southeast-1.amazonaws.com/life-library-backend:secrets-manager-20260918`.
The ECS service is not running yet; production database, OAuth, URL, and other
secret settings are still required before launch.

## Secrets

- `.env` is ignored by Git.
- Service-account JSON and credential filenames are ignored by Git.
- No OAuth client secret, database password, or service-account key is tracked.
- The service-account JSON must remain outside the repository and must be rotated
  immediately if it is ever exposed.
