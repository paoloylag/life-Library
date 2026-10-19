# Library booking email infrastructure

Configured on October 19, 2026 in AWS account `165115313524`, region
`ap-southeast-1` (Singapore), stack `life-library-production-email`.

## Sending configuration

| Setting | Value |
| --- | --- |
| Sender | `Life College Library <library@life.edu.ph>` |
| Region | `ap-southeast-1` |
| Configuration set | `life-library-production-bookings` |
| Verified identity | `life.edu.ph` |
| Feedback queue | `life-library-production-email-events` |

The SES account already had production access. The domain already had verified
DKIM. No DNS, MX, SPF, DMARC, identity-default, or account-wide sending settings
were changed. In particular, the shared identity keeps its existing
`my-first-configuration-set` default. Library messages must explicitly provide
the Library configuration set on each `sesv2.send_email` request.

The existing Library ECS task role has the additive inline policy
`LibraryBookingEmail`. It permits `ses:SendEmail` only for `library@life.edu.ph`
using this region and the listed SES resources. Existing permissions are retained.
No SMTP users, long-lived access keys or new secrets were created. The mailbox
itself is managed by Google Workspace; SES verification does not create an inbox.

## Delivery feedback

The configuration set publishes SEND, DELIVERY, BOUNCE, COMPLAINT, REJECT,
RENDERING_FAILURE and DELIVERY_DELAY to a Library-only SNS topic. Its subscription
delivers raw events to the encrypted SQS queue, retained for 14 days. The task
role can receive, delete and manage visibility of messages only in that queue.

Topic and queue policies restrict publishing by service, source ARN and account.
The queue denies non-TLS requests. No dedicated IPs or additional application
servers were provisioned; SES/SNS/SQS usage can incur metered charges.

The initial SQS message may be an SES destination-validation notification rather
than JSON event data. Consumers must tolerate and classify validation messages.

## Verification

- CloudFormation stack creation succeeded.
- Domain verified for sending, DKIM SUCCESS and production access confirmed.
- IAM simulation allows the approved From address and denies other addresses.
- `sesv2.send_email` accepted a message to AWS's success mailbox simulator using
  the Library configuration set. No real student or staff was a test recipient.
- The simulator's matching Delivery event arrived through SNS in the encrypted
  SQS queue, confirming the complete feedback path. Only that test event was removed.

## Approved inbox test

On October 19, five `[TEST]` samples (confirmation, cancellation, extension,
15-minute reminder and session ended) were sent only to `paolo.ylag@life.edu.ph`.
SES Delivery feedback was confirmed for all five. Sample content was clearly
marked and no booking records were created or modified. This is the approved
recipient for further email testing; do not use the real user directory.

## Application integration still required

This stack does not enable automatic booking emails by itself. Implement:

1. Transactional outbox and background sender with bounded retries.
2. HTML and plain-text rendering, addressed only to the booker's saved email.
3. Confirmation, cancellation, extension and session-ended notifications.
4. `ConfigurationSetName` and non-PII message tags on every send.
5. SES message-ID tracking and an idempotent SQS feedback consumer.
6. Bounce/complaint suppression handling, failure status and librarian resend.
7. End-to-end inbox tests and a separately reviewed application rollout.

Sending should use the ECS task role and SDK default credential chain, not SMTP
credentials. Local tests must be explicitly enabled and use AWS simulators or an
approved test recipient; never bulk-email the real user directory during testing.

Infrastructure source: `infra/aws/email-stack.yaml`.
Safe send test: `infra/aws/ses-simulator-test.json` (AWS simulator only).
