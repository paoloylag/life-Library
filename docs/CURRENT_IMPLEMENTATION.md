# Current Implementation Status

Last verified: September 19, 2026

## Implemented and verified

- FastAPI backend image builds with Docker.
- Docker Compose starts PostgreSQL 16 and the API with health checks.
- PostgreSQL data persists in a named Docker volume.
- Alembic applies the initial attendance schema before the API starts.
- Direct local development uses PostgreSQL. The retained SQLite demo dataset was
  imported with its 16 users, 31 sessions, 85 visits, four staff accounts, and
  saved settings; the source database remains available as a rollback copy.
- `python -m app.migrate_sqlite_to_postgres` provides a guarded, transactional
  path for importing a SQLite dataset after Alembic creates the target schema.
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
- Librarians can add and edit library-user profiles in Library Users,
  including student, faculty, non-teaching, administrator, and visitor records.
  Auditor and librarian associate accounts retain read-only directory access. Google-linked
  email, number, and category are not manually editable.
- Development Docker startup applies deterministic roster and attendance seeds;
  production startup never seeds data.
- Production roster tooling supports CSV validation, dry runs, and create/update
  imports without overriding Google-managed identity fields. The first real
  Librarian can be created in a one-off task using a secret-backed password.
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
- New settings audit entries store the librarian ID, name, email, timestamp,
  changed field names, and complete before-and-after JSON snapshots. Keys that
  look like passwords, secrets, tokens, credentials, or private keys are
  redacted before persistence. Audit rows created before this schema expansion
  remain readable as legacy entries without snapshots.
- The Settings page loads and saves through `/api/library/settings`. If the
  backend has no saved settings, it offers browser-saved values for a one-time
  manual save to the shared backend. Browser storage is cleared only after
  that save succeeds.
- The QR display reads only its public wording from
  `/api/library/settings/display`. QR duplicate prevention uses the saved
  scan window. Reports use the saved initial grouping and user-type filter.
- Settings may hold one HTTPS room-booking URL for Nap Rooms and Collaboration
  Rooms. When configured, the full-screen display shows a smaller booking QR
  alongside the primary attendance QR. No booking URL has been supplied yet.
- Opening hours, timezone, current term, school reference lists, planned
  librarian roles, visitor fields, and retention years are stored but are not
  yet enforced by attendance, account provisioning, or automatic deletion.

## Librarian access

- The daily QR URL, dashboard, users, attendance, reports, and Settings API
  require a signed-in librarian account even in local development.
- Librarian may manage all Settings, library users, staff roles, and attendance.
  Librarian Associate may manage QR display and manual check-ins. Auditor may
  view dashboard, users, attendance,
  and reports but cannot retrieve the daily QR URL or change attendance.
- Alembic migration `b4d718c70aa1` maps former Administrator accounts to
  Librarian and former Librarian accounts to Librarian Associate, preserving
  their access. The isolated local demo database has been migrated and backed up.
- Manual check-ins retain the signed-in librarian ID and return their name in
  attendance history. Real accounts can be created with
  `python -m app.create_librarian`, choosing a role at the prompt.
- Development test accounts require `APP_ENV=local` and
  `ENABLE_DEV_LIBRARIANS=true`. The role picker is shown only in Vite dev mode.
  Test accounts are refused when the opt-in is off or the backend is not local.
  Never expose the opt-in local server to untrusted networks.
- The development role switch is also available from the signed-in account
  menu when the same local opt-in is enabled. Production builds omit it.
- Librarians and Librarian Associates can create staff accounts and assign
  associate or auditor roles from Staff Accounts. Only Librarians can create or
  manage Librarian accounts. Staff can change eligible roles and active status;
  nobody can remove their own access or edit development test accounts.

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
The AWS staging environment is running at
`https://library-staging.life.edu.ph`. It uses CloudFront, a private S3 origin,
an ALB-backed ECS Fargate service, and a private encrypted RDS PostgreSQL 16.15
database. The staging schema is verified at migration head `c31a9e4d27f8`.

The production database launch and restore process is documented in
`docs/PRODUCTION_DATABASE_RUNBOOK.md`. AWS access has been verified through the
`life-library` IAM Identity Center profile. The shared CloudFront certificate
for `library.life.edu.ph` and `library-staging.life.edu.ph` is issued. The
validated CloudFormation definition is in `infra/aws/app-stack.yaml`; managed
staging resources reuse the existing Life Portal staging VPC and NAT egress.
The production stack has not been deployed.

## Secrets

- `.env` is ignored by Git.
- Service-account JSON and credential filenames are ignored by Git.
- No OAuth client secret, database password, or service-account key is tracked.
- The service-account JSON must remain outside the repository and must be rotated
  immediately if it is ever exposed.
