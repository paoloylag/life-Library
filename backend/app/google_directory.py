import json
import logging
from dataclasses import dataclass

import boto3
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
    if normalized == "/academics/faculty" or normalized.startswith(
        "/academics/faculty/"
    ):
        return "faculty"
    return "non-teaching personnel"


def directory_is_configured() -> bool:
    return bool(
        (settings.google_service_account_secret_id or settings.google_service_account_file)
        and settings.google_workspace_delegated_admin
    )


def directory_access_token() -> str:
    if settings.google_service_account_secret_id:
        client = boto3.client(
            "secretsmanager",
            region_name=settings.aws_region or None,
        )
        response = client.get_secret_value(
            SecretId=settings.google_service_account_secret_id,
        )
        secret_string = response.get("SecretString")
        if not secret_string:
            raise ValueError("Google service-account secret must contain a SecretString")
        credentials = service_account.Credentials.from_service_account_info(
            json.loads(secret_string),
            scopes=[settings.google_directory_scope],
        )
    else:
        credentials = service_account.Credentials.from_service_account_file(
            settings.google_service_account_file,
            scopes=[settings.google_directory_scope],
        )
    credentials = credentials.with_subject(settings.google_workspace_delegated_admin)
    credentials.refresh(GoogleAuthRequest())
    return str(credentials.token)


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
