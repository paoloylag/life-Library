# AWS deployment

The library application follows the existing Life Portal deployment pattern:
CloudFront serves a private S3 frontend and sends `/api/*` to an ALB-backed
FastAPI service on ECS Fargate. Fargate and RDS run in private subnets. Each
environment reuses its existing Life Portal VPC and NAT egress while keeping
separate library security groups and application resources.

## Prerequisites

- AWS CLI profile `life-library` authenticated through IAM Identity Center.
- Region `ap-southeast-1` for application resources.
- An ACM certificate in `us-east-1` covering the selected application domain.
- An immutable `life-library-backend` ECR image tagged with the Git commit SHA.
- The existing `library/google-service-account` Secrets Manager secret.
- Google OAuth configured with the final callback URL.
- Amazon RDS PostgreSQL 16.15, the currently validated Singapore minor release.

Verified shared resources:

```text
Hosted zone: Z08338573S1OV33OP5NQH
CloudFront certificate: arn:aws:acm:us-east-1:165115313524:certificate/19d8be84-fea6-452a-8427-4ed933a4dd10
CloudFront origin prefix list: pl-31a34658
Google service-account secret: arn:aws:secretsmanager:ap-southeast-1:165115313524:secret:library/google-service-account-hM92ky
```

Use staging first, normally `library-staging.life.edu.ph`. Production should use
`library.life.edu.ph` only after the complete staging acceptance checklist passes.

## Validate

```powershell
aws cloudformation validate-template `
  --profile life-library `
  --region ap-southeast-1 `
  --template-body file://infra/aws/app-stack.yaml
```

Find the CloudFront origin-facing managed prefix list:

```powershell
aws ec2 describe-managed-prefix-lists `
  --profile life-library `
  --region ap-southeast-1 `
  --query "PrefixLists[?PrefixListName=='com.amazonaws.global.cloudfront.origin-facing'].PrefixListId" `
  --output text
```

## Deploy staging

The stack creates billable resources, including RDS, an ALB, CloudFront, and
Fargate. Review the change set before executing it.

```powershell
aws cloudformation deploy `
  --profile life-library `
  --region ap-southeast-1 `
  --stack-name life-library-staging `
  --template-file infra/aws/app-stack.yaml `
  --capabilities CAPABILITY_NAMED_IAM `
  --no-execute-changeset `
  --parameter-overrides `
    Environment=staging `
    DomainName=library-staging.life.edu.ph `
    HostedZoneId=Z08338573S1OV33OP5NQH `
    CloudFrontCertificateArn=arn:aws:acm:us-east-1:165115313524:certificate/19d8be84-fea6-452a-8427-4ed933a4dd10 `
    BackendImageUri=165115313524.dkr.ecr.ap-southeast-1.amazonaws.com/life-library-backend:REPLACE_WITH_COMMIT_SHA `
    GoogleServiceAccountSecretArn=arn:aws:secretsmanager:ap-southeast-1:165115313524:secret:library/google-service-account-hM92ky `
    CloudFrontOriginPrefixListId=pl-31a34658 `
    VpcId=vpc-0ace0dca3161e7f1c `
    PublicSubnetAId=subnet-065b777d41b993641 `
    PublicSubnetBId=subnet-0ea34346051aaa240 `
    PrivateSubnetAId=subnet-00b390497aac92764 `
    PrivateSubnetBId=subnet-0de3dca6fb32c2ee7
```

After reviewing the generated change set, execute it explicitly in CloudFormation.

## Required post-stack steps

1. Update the generated `/life-library/staging/application` secret with the real
   `googleClientId` and `googleClientSecret`. Preserve its generated `secretKey`.
2. Build the frontend with `VITE_API_URL=""`, `VITE_BASE_PATH=/`, and
   `VITE_PUBLIC_APP_URL=https://library-staging.life.edu.ph`.
3. Upload `frontend/dist/` to the output frontend bucket and invalidate CloudFront.
4. Run `alembic upgrade head` as a one-off ECS task using the stack task definition.
5. Start or redeploy the ECS service after secrets and migrations are ready.
6. Add the staging callback to the Google OAuth web client.
7. Test librarian login, QR Google SSO, guest check-in, manual check-in, reports,
   exports, authorization boundaries, restart persistence, and backup restore.

Production uses the same template with `Environment=production`. It enables
Multi-AZ RDS, 14-day RDS backups, 35-day AWS Backup retention, and 90-day logs.

## Current staging deployment

```text
URL: https://library-staging.life.edu.ph
Stack: life-library-staging
ECS cluster/service: life-library-staging / life-library-staging-api
Frontend bucket: life-library-staging-frontendbucket-jhbta9dsntpq
CloudFront distribution: E62T77HU1C092
Database: life-library-staging-postgres (PostgreSQL 16.15)
Migration head: c31a9e4d27f8
Backend image: 165115313524.dkr.ecr.ap-southeast-1.amazonaws.com/life-library-backend:ff0cb7b
```

The Google OAuth secret is populated and the public frontend, API health route,
and direct SPA routing are verified. Before user acceptance testing, add
`https://library-staging.life.edu.ph/api/auth/google/callback` to the Google
OAuth web client's authorized redirect URIs and create the first Librarian using
the secure one-off procedure in `docs/PRODUCTION_DATABASE_RUNBOOK.md`.

## GitHub Actions deployment

The `Deploy AWS staging` workflow performs a complete application release:

1. Runs backend tests and builds the frontend.
2. Builds and pushes an immutable commit-SHA backend image to ECR.
3. Registers a new ECS task definition without changing the running service.
4. Runs Alembic against that exact task revision and stops on migration failure.
5. Updates ECS, waits for service stability, and relies on the deployment circuit
   breaker for an unhealthy rollout.
6. Builds and uploads the frontend, invalidates CloudFront, and smoke-tests the
   home page, a direct SPA route, and API health.

The workflow deploys staging whenever `feature/backend-qr-checkin` is pushed. It
can also be started manually from **Actions -> Deploy AWS staging -> Run
workflow** after the workflow reaches the default branch. It uses GitHub OIDC
and does not store AWS access keys.

### One-time AWS setup

If this AWS account does not have GitHub's OIDC provider, create it in IAM under
**Identity providers -> Add provider**:

```text
Provider type: OpenID Connect
Provider URL: https://token.actions.githubusercontent.com
Audience: sts.amazonaws.com
```

Copy the resulting provider ARN and deploy the restricted staging role:

```powershell
aws cloudformation deploy `
  --profile life-library `
  --region ap-southeast-1 `
  --stack-name life-library-github-actions `
  --template-file infra/aws/github-actions-role.yaml `
  --capabilities CAPABILITY_NAMED_IAM `
  --parameter-overrides `
    GitHubOidcProviderArn=arn:aws:iam::165115313524:oidc-provider/token.actions.githubusercontent.com
```

Read the role ARN:

```powershell
aws cloudformation describe-stacks `
  --profile life-library `
  --region ap-southeast-1 `
  --stack-name life-library-github-actions `
  --query "Stacks[0].Outputs[?OutputKey=='DeploymentRoleArn'].OutputValue" `
  --output text
```

### One-time GitHub setup

In the repository, open **Settings -> Environments**, create `aws-staging`, and
add the environment variable below:

```text
AWS_DEPLOY_ROLE_ARN=<DeploymentRoleArn output>
```

Restrict the environment to `feature/backend-qr-checkin`. Optional required
reviewers can be enabled before staging releases. Keep production in a separate
GitHub environment and IAM role; the staging role cannot deploy production.
