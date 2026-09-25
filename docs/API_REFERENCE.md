# Library Attendance API Reference

This document lists the HTTP endpoints implemented by the FastAPI backend.

## Base URLs

- Local API: `http://127.0.0.1:8000`
- Local Swagger UI: `http://127.0.0.1:8000/docs`
- Local ReDoc: `http://127.0.0.1:8000/redoc`
- Local OpenAPI schema: `http://127.0.0.1:8000/openapi.json`
- Production API: pending deployment

All application endpoints begin with `/api`. Browser requests must include
credentials because user and librarian authentication use HTTP-only cookies.

## Access Levels

| Access | Description |
| --- | --- |
| Public | No authenticated session required |
| QR user | Google-authenticated library user session required |
| Staff | Any signed-in Librarian, Librarian Associate, or Auditor |
| Editor | Librarian or Librarian Associate |
| Librarian | Librarian role only |
| Local only | Available only when `APP_ENV=local` and `ENABLE_DEV_LIBRARIANS=true` |

## System and Authentication

| Method | Local URL | Access | Purpose |
| --- | --- | --- | --- |
| `GET` | `http://127.0.0.1:8000/api/health` | Public | Backend health check |
| `GET` | `http://127.0.0.1:8000/api/auth/status` | Public | Google authentication configuration status |
| `GET` | `http://127.0.0.1:8000/api/auth/google?next=/scan/{token}` | Public | Begin Google SSO; `next` accepts only a scan path |
| `GET` | `http://127.0.0.1:8000/api/auth/google/callback` | Google callback | Complete SSO, classify the Workspace user, set the user cookie, and redirect |
| `GET` | `http://127.0.0.1:8000/api/auth/me` | QR user | Current authenticated library user and profile |
| `POST` | `http://127.0.0.1:8000/api/auth/dev-login` | Local only | Create/sign in the local QR test user |
| `POST` | `http://127.0.0.1:8000/api/auth/logout` | Public | Clear the QR user cookie |
| `POST` | `http://127.0.0.1:8000/api/admin/login` | Public | Sign in a staff account and set the librarian cookie |
| `GET` | `http://127.0.0.1:8000/api/admin/me` | Staff | Current signed-in staff account |
| `POST` | `http://127.0.0.1:8000/api/admin/logout` | Public | Clear the librarian cookie |
| `GET` | `http://127.0.0.1:8000/api/admin/dev-accounts` | Local only | Development role-selector accounts and temporary passwords |

Staff login body:

```json
{
  "email": "librarian@life.edu.ph",
  "password": "minimum-10-characters"
}
```

## Staff Accounts

| Method | Local URL | Access | Purpose |
| --- | --- | --- | --- |
| `GET` | `http://127.0.0.1:8000/api/admin/accounts` | Editor | List staff accounts |
| `POST` | `http://127.0.0.1:8000/api/admin/accounts` | Editor | Create a staff account |
| `PATCH` | `http://127.0.0.1:8000/api/admin/accounts/{account_id}` | Editor | Change a staff role or active status |

Create body:

```json
{
  "name": "Juan Dela Cruz",
  "email": "juan.delacruz@life.edu.ph",
  "password": "minimum-10-characters",
  "role": "librarian_associate"
}
```

Valid roles are `librarian`, `librarian_associate`, and `auditor`. Only a
Librarian can assign or manage the `librarian` role.

Update body:

```json
{
  "role": "auditor",
  "is_active": true
}
```

## Daily QR and Check-In

| Method | Local URL | Access | Purpose |
| --- | --- | --- | --- |
| `GET` | `http://127.0.0.1:8000/api/library/sessions/current` | Editor | Get or create today's session and return its scan URL |
| `POST` | `http://127.0.0.1:8000/api/library/sessions` | Editor | Get or create today's QR session |
| `POST` | `http://127.0.0.1:8000/api/library/scan/{token}` | QR user | Record the authenticated user's check-in |
| `POST` | `http://127.0.0.1:8000/api/library/scan/{token}/guest` | Public | Record a guest check-in against a valid QR token |
| `POST` | `http://127.0.0.1:8000/api/library/attendance/manual` | Editor | Record a manual user or visitor check-in |

Guest check-in body:

```json
{
  "name": "Guest Name",
  "organization": "Organization Name",
  "purpose": "Research"
}
```

Manual check-in body for an existing user:

```json
{
  "user_number": "LC-2026-00124",
  "purpose": "Research",
  "checked_in_at": "2026-09-19T09:30:00+08:00",
  "note": "Optional audit note"
}
```

For a visitor, omit `user_number` and provide `visitor_name`; `organization`,
`purpose`, `checked_in_at`, and `note` are optional. Omitting `checked_in_at`
records the current time.

## Library Users

| Method | Local URL | Access | Purpose |
| --- | --- | --- | --- |
| `GET` | `http://127.0.0.1:8000/api/library/users` | Staff | Search and paginate library users |
| `GET` | `http://127.0.0.1:8000/api/library/users/export.csv` | Staff | Download all users matching the active search and category filters |
| `POST` | `http://127.0.0.1:8000/api/library/users/import.csv?dry_run=true` | Librarian | Validate a roster CSV and return create/update counts |
| `POST` | `http://127.0.0.1:8000/api/library/users/import.csv?dry_run=false` | Librarian | Apply a validated roster CSV bulk update |
| `POST` | `http://127.0.0.1:8000/api/library/users/import-staff.csv?dry_run=true` | Librarian | Preview an employee masterlist CSV; set `dry_run=false` to apply |
| `POST` | `http://127.0.0.1:8000/api/library/users` | Librarian | Create a library user |
| `GET` | `http://127.0.0.1:8000/api/library/users/{number}` | Staff | User profile and visit summary |
| `PUT` | `http://127.0.0.1:8000/api/library/users/{number}` | Librarian | Update a library user |
| `GET` | `http://127.0.0.1:8000/api/library/users/{number}/visits` | Staff | Complete visit history for a user |

List query parameters:

- `q`: name, email, user number, program, section, or department search
- `user_type`: exact normalized user category
- `page`: integer, minimum `1`
- `page_size`: integer from `1` to `200`, default `50`

Create and update body:

```json
{
  "number": "LC-2026-00124",
  "name": "Maria Santos",
  "email": "maria.santos@life.edu.ph",
  "user_type": "student",
  "program": "BS-ENTREP",
  "year_level": "1st Year",
  "section": "1A",
  "department": "Academic Affairs",
  "organization": "",
  "is_active": true
}
```

Valid categories are `student`, `faculty`, `non-teaching personnel`,
`administrator`, and `visitor`. Google-linked email, number, and category fields
remain managed by Google Workspace.

CSV imports use the columns shown in `docs/roster-template.csv`, accept files up
to 5 MB, and reconcile existing SSO profiles by email before creating users.
Google-managed identity and category values are preserved while program, year
level, section, department, organization, and active status are updated.

The directory's **Import staff masterlist** action accepts CSV headers from the
AY 26-27 employee masterlist: `Employee ID`, `Lsst Name` (or `Last Name`),
`First Name`, `Middle Name`, `Preferred Name`, `Employment Status`, `Department`,
`Position`, `Immediate Supervisor`, `Date Hired`, `Regularization Date`, and
`Contact No.` A `User Type` column is required for every row, using `faculty`,
`non-teaching personnel` (also accepts `Non-Teaching`), or `administrator`. Optional `Email` and `Status`
columns are accepted. Missing emails are stored with an internal placeholder
and can be added later. Missing or `NA` employee IDs remain blank in the
directory and CSV export, and can be entered in the profile editor. Stable
internal identifiers based on name and department support reimport. The preview
modal reports counts for blank IDs, missing emails, and ignored columns.
Unused blank payroll and personal-identifier columns in the source masterlist
are not stored in the library directory.

## Attendance and Dashboard

| Method | Local URL | Access | Purpose |
| --- | --- | --- | --- |
| `GET` | `http://127.0.0.1:8000/api/library/attendance` | Staff | Search and paginate attendance records |
| `GET` | `http://127.0.0.1:8000/api/library/dashboard` | Staff | Today's totals, unique users, peak hour, and recent visits |

Attendance query parameters:

- `q`: user name or user number search
- `user_type`: exact normalized user category
- `page`: integer, minimum `1`
- `page_size`: integer from `1` to `500`, default `100`

## Reports and Exports

| Method | Local URL | Access | Purpose |
| --- | --- | --- | --- |
| `GET` | `http://127.0.0.1:8000/api/library/reports` | Staff | Filtered report data and chart series |
| `GET` | `http://127.0.0.1:8000/api/library/reports/export.xlsx` | Staff | Download the filtered Excel report |
| `GET` | `http://127.0.0.1:8000/api/library/reports/export.pdf` | Staff | Download the filtered PDF report |

All three report routes accept the same query parameters:

- `date_from`, `date_to`: ISO dates such as `2026-08-01`
- `academic_year`: `All` or `YYYY-YYYY`
- `semester`: `All`, `1st Semester`, `2nd Semester`, or `Outside Semester`
- `grouping`: `Daily`, `Weekly`, `Monthly`, or `Annual`
- `user_type`: `All` or a normalized user category
- `year_level`, `section`, `program`, `department`: `All` or an exact value

Example:

```text
http://127.0.0.1:8000/api/library/reports?date_from=2026-08-01&date_to=2026-08-31&grouping=Daily&user_type=student
```

## Settings

| Method | Local URL | Access | Purpose |
| --- | --- | --- | --- |
| `GET` | `http://127.0.0.1:8000/api/library/settings` | Librarian | Full settings, configuration status, and audit history |
| `PUT` | `http://127.0.0.1:8000/api/library/settings` | Librarian | Validate and save all library settings |
| `GET` | `http://127.0.0.1:8000/api/library/settings/display` | Public | QR-display wording and room-booking link only |

Settings audit entries include `actorId`, `user`, `actorEmail`, `at`,
`changedFields`, `beforeValues`, and `afterValues`. Older entries can have null
snapshots. Values for keys that resemble passwords, secrets, tokens,
credentials, or private keys are stored as `[REDACTED]`.

The complete settings schema is available interactively in Swagger at
`http://127.0.0.1:8000/docs` under `LibrarySettings`.

## Common Responses

- `204`: login or logout completed without a response body
- `401`: authentication is missing or invalid
- `403`: the signed-in account lacks the required role
- `404`: record, QR session, or development-only route is unavailable
- `409`: duplicate or protected-state conflict
- `422`: request or filter validation failed
- `503`: Google authentication is not configured
