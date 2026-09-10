import logging
from dataclasses import dataclass

import httpx
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
    if normalized == "/academics/faculty" or normalized.startswith("/academics/faculty/"):
        return "faculty"
    return "non-teaching personnel"


def directory_is_configured() -> bool:
    return bool(settings.google_service_account_file and settings.google_workspace_delegated_admin)


def lookup_directory_identity(email: str) -> DirectoryIdentity | None:
    if not directory_is_configured():
        return None

    try:
        credentials = service_account.Credentials.from_service_account_file(
            settings.google_service_account_file,
            scopes=[settings.google_directory_scope],
        ).with_subject(settings.google_workspace_delegated_admin)
        credentials.refresh(GoogleAuthRequest())
        response = httpx.get(
            f"https://admin.googleapis.com/admin/directory/v1/users/{email}",
            params={"projection": "basic"},
            headers={"Authorization": f"Bearer {credentials.token}"},
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
