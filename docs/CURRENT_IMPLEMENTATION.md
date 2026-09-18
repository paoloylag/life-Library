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
- Development Docker startup applies deterministic roster and attendance seeds;
  production startup never seeds data.

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
