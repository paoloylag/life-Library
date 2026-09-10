# Current Implementation Status

Last verified: September 10, 2026

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
- The production authentication code can request a short-lived delegated token
  through IAM Credentials `signJwt` without a JSON private key.

## Production keyless deployment pending

The keyless code is implemented and covered by automated tests, but it has not
yet been exercised on Cloud Run. The Google Cloud CLI is installed locally but
does not yet have an authenticated administrator account.

To complete production verification:

1. Authenticate the Google Cloud CLI with a project administrator.
2. Set project `lci-library-attendance`.
3. Enable Cloud Run, Cloud Build, Artifact Registry, IAM Credentials, Admin SDK,
   and the selected managed PostgreSQL service APIs.
4. Grant `roles/iam.serviceAccountTokenCreator` on
   `librarian@lci-library-attendance.iam.gserviceaccount.com` to the Cloud Run
   runtime identity.
5. Deploy with `GOOGLE_SERVICE_ACCOUNT_FILE` unset and
   `GOOGLE_SERVICE_ACCOUNT_EMAIL` set to the librarian service account.
6. Verify a real Directory lookup and QR check-in from the deployed service.

## Secrets

- `.env` is ignored by Git.
- Service-account JSON and credential filenames are ignored by Git.
- No OAuth client secret, database password, or service-account key is tracked.
- The local JSON key should be deleted after Cloud Run keyless access is verified.
