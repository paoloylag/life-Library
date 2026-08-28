# Project Manifest

## Project Identity

- **Name:** Life College Library Attendance
- **Repository:** `paoloylag/life-Library`
- **Primary branch:** `main`
- **Status:** MVP prototype and backend scaffold
- **Institution:** Life College
- **Attendance model:** Check-in only

## Purpose

The system records and reports library visits for students, faculty, non-teaching personnel, administrators, and visitors. Librarians manage daily QR codes and manual check-ins, while QR users verify their identity through their institutional Google account.

## Technology Stack

| Layer | Technology |
| --- | --- |
| Frontend | React 19, TypeScript, Vite 6 |
| Styling | Tailwind CSS 4 and project CSS |
| Icons | Lucide React |
| QR | `qrcode.react` |
| Reports | ExcelJS, jsPDF, jsPDF AutoTable |
| Backend | Python, FastAPI |
| Data access | SQLAlchemy async |
| Database | PostgreSQL |
| Authentication | Librarian credentials and Google OAuth/OpenID Connect |
| Local services | Docker Compose |
| Static deployment | GitHub Pages via GitHub Actions |

## Repository Layout

```text
.github/workflows/pages.yml  GitHub Pages build and deployment
backend/app/                 FastAPI application, auth, models, services
backend/pyproject.toml       Python dependencies and tooling
frontend/public/             Static brand assets
frontend/src/                React screens, stores, settings, styles
docker-compose.yml           Local PostgreSQL service
.env.example                 Environment variable template
README.md                    Quick-start instructions
PROJECT_MANIFEST.md          Product and implementation inventory
```

## User Types

- Student
- Faculty / Teaching Personnel
- Non-Teaching Personnel
- Administrator
- Visitor
- Librarian / Library Registrar

## Implemented Frontend Modules

| Module | Current capability | Data status |
| --- | --- | --- |
| Dashboard | Daily metrics, recent activity, QR generation, QR display, manual check-in entry point | Seeded/local browser state |
| Attendance | Check-in-only attendance list, filters, manual check-in with automatic or manual date/time | Seeded/local browser state |
| Students | Searchable user directory and individual visit-history pages | Seeded/local browser state |
| Reports | Date and organization filters, executive summary, breakdowns, charts, Excel export, PDF export | Seeded/local browser state |
| Settings | Library details, QR behavior, attendance rules, academic calendar, school structure | Local browser state |
| QR scan | Token/expiry handling and user-type-aware success presentation | Prototype flow |
| Dark mode | Persistent theme and module-specific contrast styling | Functional |

## Reporting Scope

- Total visits and unique visitors
- Return visits, returning users, and averages per open day/user
- Daily, weekly, monthly, and annual trend grouping
- Peak days and peak hours
- Academic year, semester, and custom reporting period
- User-category usage
- Student usage by program, year level, and section
- Month and semester comparisons
- Attendance trend, category, and student-breakdown charts
- Branded Excel and PDF exports

## Backend Inventory

### Available API endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Service health check |
| `GET` | `/api/auth/google` | Begin Google user authentication |
| `GET` | `/api/auth/google/callback` | Complete Google authentication |
| `GET` | `/api/auth/me` | Return the authenticated QR user |
| `POST` | `/api/admin/login` | Librarian credential login |
| `GET` | `/api/admin/me` | Return the authenticated librarian |
| `POST` | `/api/admin/logout` | End librarian session |
| `POST` | `/api/library/sessions` | Create or replace the active daily QR session |
| `POST` | `/api/library/scan/{token}` | Record an authenticated check-in |
| `GET` | `/api/library/dashboard` | Return today's visit summary |

### Database entities

- `Librarian`: credential-based administrative account
- `User`: Google identity and general user category
- `StudentProfile`: student number, program, section, and type metadata
- `LibrarySession`: dated QR token, validity window, status, and creator
- `LibraryVisit`: check-in timestamp, source, adjustment metadata, and session

## Environment Variables

| Variable | Description |
| --- | --- |
| `DATABASE_URL` | Async PostgreSQL connection string |
| `SECRET_KEY` | Cookie/session signing secret; replace in every deployed environment |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `GOOGLE_REDIRECT_URI` | Backend OAuth callback URL |
| `GOOGLE_ALLOWED_DOMAIN` | Institutional Google Workspace domain |
| `FRONTEND_URL` | Allowed frontend origin and post-login destination |

Do not commit `.env` or production credentials. The domain in `.env.example` is a placeholder and must be replaced with Life College's confirmed Google Workspace domain.

## Routes

| Frontend route | View |
| --- | --- |
| `/` | Librarian dashboard |
| `/attendance` | Attendance and manual check-in |
| `/students` | User directory |
| `/students/{student_number}` | Individual visit history |
| `/reports` | Reports and exports |
| `/settings` | System settings |
| `/qr-display` | Full-screen student QR display |
| `/scan/{token}` | QR authentication/check-in flow |

For GitHub Pages, routes are served below `/life-Library/`. The deployment creates a `404.html` SPA fallback for direct-route loading.

## Deployment

### GitHub Pages

The workflow at `.github/workflows/pages.yml` builds and deploys the static React frontend after pushes to `main`. Expected URL:

`https://paoloylag.github.io/life-Library/`

GitHub Pages must use **GitHub Actions** as its Pages source. It does not host FastAPI, PostgreSQL, server-side sessions, or Google OAuth callbacks.

### Production services still required

- A Python-compatible backend host
- A managed PostgreSQL database
- HTTPS frontend and backend domains
- Google Cloud OAuth credentials and approved redirect URIs
- Production secrets supplied through the hosting platform
- CORS and cookie settings suitable for the final domains

## Integration Status

| Capability | Status |
| --- | --- |
| Seeded dashboard and navigation | Implemented |
| Check-in-only user experience | Implemented in frontend |
| Manual check-in interface | Implemented in frontend |
| Student visit pages | Implemented with seeded data |
| Reports, charts, Excel, and PDF | Implemented with seeded data |
| Persistent PostgreSQL attendance | Backend scaffold; frontend integration pending |
| Librarian login screen/session enforcement | Backend scaffold; UI currently intentionally bypassed |
| Google SSO check-in | Backend scaffold; credentials and frontend integration pending |
| Production QR token flow | Backend scaffold; frontend currently uses a demonstration token |
| Server-backed settings | Pending |
| Deployment of API/database | Pending |
| Automated backend tests and migrations | Pending |

## MVP Completion Priorities

1. Add database migrations and seed/import tooling.
2. Connect dashboard, attendance, students, and reports to FastAPI.
3. Implement the backend manual check-in endpoint with audit metadata.
4. Complete librarian login UI and protect administrative routes.
5. Configure Life College Google Workspace OAuth and scan callback flow.
6. Add user/profile administration for all supported categories.
7. Replace browser-local settings with server-persisted settings.
8. Add API, authentication, duplicate-scan, export, and end-to-end tests.
9. Deploy FastAPI and PostgreSQL, then configure production domains and secrets.
10. Perform privacy, retention, backup, accessibility, and security review before launch.

## Operating Rules

- A visit is a check-in event; there is no check-out workflow.
- QR codes are session-bound and expire according to configured policy.
- School Google authentication identifies QR users; librarian authentication remains credential-based.
- Manual entries must retain source, librarian, date/time, and adjustment reason for auditability.
- Duplicate-scan protection must be enforced by the backend.
- Student and attendance records are institutional data and require least-privilege access and an approved retention policy.

## Local Development

```powershell
Copy-Item .env.example .env
docker compose up -d db

Set-Location backend
pip install -e ".[dev]"
uvicorn app.main:app --reload

Set-Location ..\frontend
pnpm install
pnpm dev
```

- Frontend: `http://localhost:5173`
- API documentation: `http://localhost:8000/docs`
- API health: `http://localhost:8000/api/health`

