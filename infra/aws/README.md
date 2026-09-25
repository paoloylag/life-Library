# AWS deployment

The library application follows the existing Life Portal deployment pattern:
CloudFront serves a private S3 frontend and sends `/api/*` to an ALB-backed
FastAPI service on ECS Fargate. Fargate and RDS run in private subnets.

## Prerequisites

- AWS CLI profile `life-library` authenticated through IAM Identity Center.
- Region `ap-southeast-1` for application resources.
- An ACM certificate in `us-east-1` covering the selected application domain.
- An immutable `life-library-backend` ECR image tagged with the Git commit SHA.
- The existing `library/google-service-account` Secrets Manager secret.
- Google OAuth configured with the final callback URL.

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

The stack creates billable resources, including RDS, a NAT gateway, an ALB,
CloudFront, and Fargate. Review the change set before executing it.

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
    CloudFrontOriginPrefixListId=pl-31a34658
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
