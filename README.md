# Library Attendance System

Independent FastAPI + React implementation. The `lifetrack-l12` repository is reference-only.

See [PROJECT_MANIFEST.md](PROJECT_MANIFEST.md) for the product scope, architecture, implementation status, routes, deployment model, and MVP priorities.

## Local setup

1. Copy `.env.example` to `.env`; SQLite is the default zero-setup development database.
2. In `backend`, run `pip install -e ".[dev]"`, then `uvicorn app.main:app --reload`.
3. In `frontend`, run `pnpm install`, then `pnpm dev`.
4. In `frontend`, run `npm install`, then `npm run dev`.

## Docker setup

1. Copy `.env.example` to `.env` and set `SECRET_KEY` plus the Google OAuth values.
2. Set a local `POSTGRES_PASSWORD` in `.env`.
3. Run `docker compose up --build`.

Compose starts PostgreSQL on port `5432` and the FastAPI service on port `8000`.
The API container runs `alembic upgrade head` before starting Uvicorn. SQLite remains
the default for direct, non-container local development.

Set `GOOGLE_SERVICE_ACCOUNT_HOST_FILE` to the local JSON file's absolute path for
Docker Compose. It is mounted read-only and is not copied into the image. See
`docs/CURRENT_IMPLEMENTATION.md` for the verified state and Cloud Run checklist.

## Database migrations

From `backend`, create a migration after changing a model with:

```text
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

API docs: `http://localhost:8000/docs`. Web app: `http://localhost:5173/life-Library/`.


## Google authentication

The QR scan flow uses Google OpenID Connect through FastAPI. Google client secrets stay on the backend and must never be exposed through Vite or committed to Git.

1. In Google Cloud Console, create an OAuth 2.0 **Web application** client.
2. Add `http://localhost:8000/api/auth/google/callback` as an authorized redirect URI for local development.
3. For production, add the deployed HTTPS API callback, for example `https://api.example.edu/api/auth/google/callback`.
4. Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, and the confirmed `GOOGLE_ALLOWED_DOMAIN` in the backend environment.
5. In production set `COOKIE_SECURE=true` and `COOKIE_SAMESITE=none` only when the frontend and API are genuinely cross-site. Prefer hosting both on the same institutional site.
6. Set the GitHub repository Actions variable `VITE_API_URL` to the public HTTPS FastAPI origin, without a trailing slash.

Google Directory classifies `/Students` as students, `/Academics/Faculty` as
faculty, and all other organizational units as non-teaching personnel.

### Keyless Google Directory access

Local development can use `GOOGLE_SERVICE_ACCOUNT_FILE`. Cloud Run should leave
that value empty and use these settings instead:

```text
GOOGLE_SERVICE_ACCOUNT_EMAIL=librarian@lci-library-attendance.iam.gserviceaccount.com
GOOGLE_WORKSPACE_DELEGATED_ADMIN=dt@life.edu.ph
GOOGLE_DIRECTORY_SCOPE=https://www.googleapis.com/auth/admin.directory.user.readonly
```

Attach the service account to the Cloud Run service, enable the IAM Service Account
Credentials API, and grant the runtime identity `roles/iam.serviceAccountTokenCreator`
on that service account. The application then signs a short-lived delegated JWT with
Google IAM; no private key is stored in the deployed container.

## Local QR check-in test

1. Open the QR display at `http://localhost:5173/life-Library/qr-display`.
2. Scan the code from a phone on the same Wi-Fi network.
3. On the verification page, choose **Use local test account**.
4. Confirm the displayed QR Test Student identity and select **Record library check-in**.

The local test account is available only when `APP_ENV=local`. Production builds do not show it. The current daily QR is issued by FastAPI, stored as a hash, expires at midnight in `Asia/Manila`, and survives browser refreshes.
