# Approved alternate Google emails

Librarians can approve a personal Google email for an existing library user in
Library Users > Edit > Approved alternate Google email. Approval and revocation
are saved independently of the main profile form and recorded in audit history.

The Google callback still requires a verified email. External accounts must have
an active approval and an active library profile. The first successful sign-in
binds the approval to the Google subject. The user's primary school email,
school Google subject, category, student number, and academic information remain
unchanged. Google Workspace directory lookup is skipped for the personal account.

- `GET /api/library/users/{number}/alternate-google-emails`
- `PUT /api/library/users/{number}/alternate-google-email`

The PUT body contains `email` and `is_active`. Both endpoints require Librarian
permissions. An email belonging to another primary or alternate account is rejected.

## Justin Garcia

After deploying and applying migration `b17e8d920ac4`, locate student number
`250101000011` and confirm the profile is Justin Willis Cu Garcia. Approve
`justinjustin31@gmail.com`. Keep the primary school email unchanged. Have Justin
scan the current QR, choose this personal account, and confirm the visit appears
on his existing profile.

Google OAuth must use an External audience; if the consent application is in
Testing, this email must also be an allowed test user. An Internal-only OAuth
application cannot authorize personal Gmail accounts.

Revocation prevents future personal-account sign-ins; an already-issued session
continues to follow the application's existing session lifetime.
