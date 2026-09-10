import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import google.auth
import httpx
from google.auth.transport.requests import AuthorizedSession
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DirectoryIdentity:
    org_unit_path: str
    user_type: str


def user_type_from_org_unit(org_unit_path: str) -> str:
    normalized = "/" + org_unit_path.strip().strip("/").lower()
    if normalized == "/students" or normalized.startswith("/students/"):
        return "student"
    if normalized == "/academics/faculty" or normalized.startswith(
        "/academics/faculty/"
    ):
        return "faculty"
    return "non-teaching personnel"


def directory_is_configured() -> bool:
    has_identity = bool(
        settings.google_service_account_file or settings.google_service_account_email
    )
    return bool(has_identity and settings.google_workspace_delegated_admin)


def delegated_jwt_claims(now: datetime | None = None) -> dict[str, str | int]:
    issued_at = now or datetime.now(UTC)
    return {
        "iss": settings.google_service_account_email,
        "sub": settings.google_workspace_delegated_admin,
        "scope": settings.google_directory_scope,
        "aud": "https://oauth2.googleapis.com/token",
        "iat": int(issued_at.timestamp()),
        "exp": int((issued_at + timedelta(minutes=55)).timestamp()),
    }


def keyless_access_token() -> str:
    source_credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    session = AuthorizedSession(source_credentials)
    service_account_name = (
        "projects/-/serviceAccounts/" + settings.google_service_account_email
    )
    sign_response = session.post(
        f"https://iamcredentials.googleapis.com/v1/{service_account_name}:signJwt",
        json={"payload": json.dumps(delegated_jwt_claims())},
        timeout=10,
    )
    sign_response.raise_for_status()
    signed_jwt = sign_response.json()["signedJwt"]

    token_response = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": signed_jwt,
        },
        timeout=10,
    )
    token_response.raise_for_status()
    return str(token_response.json()["access_token"])


def directory_access_token() -> str:
    if settings.google_service_account_file:
        credentials = service_account.Credentials.from_service_account_file(
            settings.google_service_account_file,
            scopes=[settings.google_directory_scope],
        ).with_subject(settings.google_workspace_delegated_admin)
        credentials.refresh(GoogleAuthRequest())
        return str(credentials.token)
    return keyless_access_token()


def lookup_directory_identity(email: str) -> DirectoryIdentity | None:
    if not directory_is_configured():
        return None

    try:
        response = httpx.get(
            f"https://admin.googleapis.com/admin/directory/v1/users/{email}",
            params={"projection": "basic"},
            headers={"Authorization": f"Bearer {directory_access_token()}"},
            timeout=10,
        )
        response.raise_for_status()
        org_unit_path = str(response.json().get("orgUnitPath") or "/")
        return DirectoryIdentity(
            org_unit_path=org_unit_path,
            user_type=user_type_from_org_unit(org_unit_path),
        )
    except Exception:
        logger.exception("Google Directory lookup failed for %s", email)
        return None
