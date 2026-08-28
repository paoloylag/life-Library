# Library Attendance System

Independent FastAPI + React implementation. The `lifetrack-l12` repository is reference-only.

See [PROJECT_MANIFEST.md](PROJECT_MANIFEST.md) for the product scope, architecture, implementation status, routes, deployment model, and MVP priorities.

## Local setup

1. Copy `.env.example` to `.env` and configure Google OAuth.
2. Run `docker compose up -d db`.
3. In `backend`, run `pip install -e ".[dev]"`, then `uvicorn app.main:app --reload`.
4. In `frontend`, run `npm install`, then `npm run dev`.

API docs: `http://localhost:8000/docs`. Web app: `http://localhost:5173`.

