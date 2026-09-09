# Library Attendance System

Independent FastAPI + React implementation. The `lifetrack-l12` repository is reference-only.

See [PROJECT_MANIFEST.md](PROJECT_MANIFEST.md) for the product scope, architecture, implementation status, routes, deployment model, and MVP priorities.

## Local setup

1. Copy `.env.example` to `.env` and configure Google OAuth.
2. Run `docker compose up -d db`.
3. In `backend`, run `pip install -e ".[dev]"`, then `uvicorn app.main:app --reload`.
4. In `frontend`, run `npm install`, then `npm run dev`.

API docs: `http://localhost:8000/docs`. Web app: `http://localhost:5173/life-Library/`.


## Google authentication

The QR scan flow uses Google OpenID Connect through FastAPI. Google client secrets stay on the backend and must never be exposed through Vite or committed to Git.

1. In Google Cloud Console, create an OAuth 2.0 **Web application** client.
2. Add `http://localhost:8000/api/auth/google/callback` as an authorized redirect URI for local development.
3. For production, add the deployed HTTPS API callback, for example `https://api.example.edu/api/auth/google/callback`.
4. Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, and the confirmed `GOOGLE_ALLOWED_DOMAIN` in the backend environment.
5. In production set `COOKIE_SECURE=true` and `COOKIE_SAMESITE=none` only when the frontend and API are genuinely cross-site. Prefer hosting both on the same institutional site.
6. Set the GitHub repository Actions variable `VITE_API_URL` to the public HTTPS FastAPI origin, without a trailing slash.

Pre-provision each user's email and library profile before launch. The first successful Google login links the trusted Google subject ID to the matching email. Accounts without an active profile can authenticate but cannot record attendance.
