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

The former `library-staging.life.edu.ph` environment was permanently
decommissioned on September 28, 2026. Do not recreate it without a new cost and
security review. Production runs at `library.life.edu.ph`.

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

## Environment status

Production uses the template with `Environment=production`. It enables
Multi-AZ RDS, 14-day RDS backups, 35-day AWS Backup retention, and 90-day logs.

## GitHub Actions deployment

The `Deploy AWS production` workflow performs a complete application release:

1. Runs backend tests and builds the frontend.
2. Builds and pushes an immutable commit-SHA backend image to ECR.
3. Registers a new ECS task definition without changing the running service.
4. Runs Alembic against that exact task revision and stops on migration failure.
5. Updates ECS, waits for service stability, and relies on the deployment circuit
   breaker for an unhealthy rollout.
6. Builds and uploads the frontend, invalidates CloudFront, and smoke-tests the
   home page, a direct SPA route, and API health.

The production workflow is manually dispatched from `main`. It uses GitHub OIDC
and does not store AWS access keys. There is no AWS staging deployment workflow.

### One-time AWS setup

If this AWS account does not have GitHub's OIDC provider, create it in IAM under
**Identity providers -> Add provider**:

```text
Provider type: OpenID Connect
Provider URL: https://token.actions.githubusercontent.com
Audience: sts.amazonaws.com
```

Copy the resulting provider ARN and deploy the restricted production role. The
template pins both the GitHub account and repository numeric IDs so renaming or
recreating either identity cannot silently inherit deployment access:

```powershell
aws cloudformation deploy `
  --profile life-library `
  --region ap-southeast-1 `
  --stack-name life-library-github-actions-production `
  --template-file infra/aws/github-actions-role.yaml `
  --capabilities CAPABILITY_NAMED_IAM `
  --parameter-overrides `
    GitHubOidcProviderArn=arn:aws:iam::165115313524:oidc-provider/token.actions.githubusercontent.com `
    DeploymentEnvironment=production `
    GitHubEnvironment=aws-production
```

Read the role ARN:

```powershell
aws cloudformation describe-stacks `
  --profile life-library `
  --region ap-southeast-1 `
  --stack-name life-library-github-actions-production `
  --query "Stacks[0].Outputs[?OutputKey=='DeploymentRoleArn'].OutputValue" `
  --output text
```

### One-time GitHub setup

In the repository, open **Settings -> Environments**, select `aws-production`, and
add the environment variable below:

```text
AWS_DEPLOY_ROLE_ARN=<DeploymentRoleArn output>
```

Restrict the environment to `main`. Required reviewers can be enabled for
production releases.

## Current production deployment

```text
URL: https://library.life.edu.ph
Stack: life-library-production
ECS cluster/service: life-library-production / life-library-production-api
Frontend bucket: life-library-production-frontendbucket-aom3hwirjkcv
CloudFront distribution: E2VQ0JG5I6PKB4
Database: life-library-production-postgres (PostgreSQL 16.15, Multi-AZ)
Backend image: 165115313524.dkr.ecr.ap-southeast-1.amazonaws.com/life-library-backend:6549f2f7708c083c4a21821b7da9f5c3bf12c5dd
Initial snapshot: life-library-production-initial-20260925
```

Production uses the protected `aws-production` GitHub environment and the
`life-library-github-production-deploy` role. Only `main` may deploy. The
workflow remains manually dispatched so every production release is deliberate.

Before Google sign-in is opened to users, add this authorized redirect URI to
the Google OAuth web client:

```text
https://library.life.edu.ph/api/auth/google/callback
```
