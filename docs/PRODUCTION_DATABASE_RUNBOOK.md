# Production Database Runbook

This runbook is the launch procedure for the Life College Library Attendance
database. Run it against the production AWS account in `ap-southeast-1`.

## 1. Provision Amazon RDS for PostgreSQL

Use PostgreSQL 16 with these minimum safeguards:

- Private subnets only; `Publicly accessible` must be disabled.
- Allow port 5432 only from the backend ECS task security group.
- Encrypt storage with AWS KMS.
- Enable deletion protection.
- Set automated backup retention to at least 7 days.
- Enable automatic minor-version updates and copy tags to snapshots.
- Use Multi-AZ when the approved budget permits. A Single-AZ MVP must have a
  documented outage window and a tested restore procedure.
- Store the database username, password, host, port, and database name in AWS
  Secrets Manager. Do not put credentials in the task definition as plain text.

The application URL format is:

```text
postgresql+asyncpg://USERNAME:PASSWORD@HOST:5432/DATABASE
```

URL-encode special characters in the username and password.

## 2. Configure the ECS task

Supply `DATABASE_URL` from Secrets Manager and set `APP_ENV=production`.
Disable development accounts:

```text
ENABLE_DEV_LIBRARIANS=false
```

The ECS task security group must reach the RDS security group. RDS must not
accept traffic from `0.0.0.0/0`.

## 3. Apply migrations

Before starting or updating the ECS service, run the backend image as a one-off
ECS task with the production task role, network, and secrets:

```bash
alembic upgrade head
alembic current
```

The expected migration head is `b4d718c70aa1`. A failed migration blocks the
release. Do not seed production data.

## 4. Create the first Librarian

Temporarily inject `LIBRARIAN_INITIAL_PASSWORD` from a restricted Secrets
Manager secret into a one-off ECS task, then run:

```bash
python -m app.create_librarian \
  --email librarian@life.edu.ph \
  --name "Head Librarian" \
  --role librarian
```

The password must contain at least 10 characters. Delete or rotate the temporary
initial-password secret after the account signs in successfully.

## 5. Import the roster

Prepare a UTF-8 CSV using `docs/roster-template.csv`. Store production rosters
in a private encrypted S3 object and grant `s3:GetObject` only to the one-off
import task role. Supported columns are:

```text
number,name,email,user_type,program,year_level,section,department,organization,is_active
```

Valid user types are `student`, `faculty`, `non-teaching personnel`,
`administrator`, and `visitor`. Validate first:

```bash
python -m app.import_roster s3://PRIVATE-BUCKET/rosters/library-users.csv --dry-run
```

Only after the dry run succeeds:

```bash
python -m app.import_roster s3://PRIVATE-BUCKET/rosters/library-users.csv
```

The import updates records by user number and rejects duplicate numbers or
emails. It does not override the email or category of Google-linked users.
Attendance records are never deleted by this command.

## 6. Verify before opening access

Confirm all of the following:

1. `alembic current` reports `b4d718c70aa1`.
2. The Librarian can sign in and open Settings.
3. The roster count and several sample profiles are correct.
4. A manual check-in persists after an API restart.
5. A Google-authenticated QR check-in appears in Attendance and Reports.
6. An auditor cannot modify attendance, settings, users, or staff accounts.

## 7. Backup and restore rehearsal

Before launch, create a manual RDS snapshot and record its identifier. Restore
that snapshot to a separate private test instance, connect a temporary backend
task to it, and verify:

- Migration head and table counts
- Librarian login
- User profiles and visit history
- Report generation

Delete the temporary restored instance after verification. Repeat the restore
rehearsal at least quarterly and after substantial schema changes. Monitor RDS
events for backup failures, low storage, high CPU, and connection exhaustion.

## Current Blocker

The local AWS CLI currently has no active credentials. RDS inspection and
provisioning cannot proceed until `aws login` or the approved IAM Identity
Center profile is configured and `aws sts get-caller-identity` succeeds.
