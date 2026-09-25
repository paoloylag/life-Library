import json
from types import SimpleNamespace
from unittest.mock import Mock

from app import google_directory


def test_secrets_manager_credentials_take_precedence(monkeypatch):
    monkeypatch.setattr(
        google_directory,
        "settings",
        SimpleNamespace(
            google_service_account_secret_id="arn:aws:secretsmanager:ap-southeast-1:123:secret:test",
            google_service_account_file="/unused/local.json",
            aws_region="ap-southeast-1",
            google_workspace_delegated_admin="dt@life.edu.ph",
            google_directory_scope="directory-scope",
        ),
    )
    secret = {"type": "service_account", "client_email": "test@example.com"}
    client = Mock()
    client.get_secret_value.return_value = {"SecretString": json.dumps(secret)}
    monkeypatch.setattr(google_directory.boto3, "client", Mock(return_value=client))
    credentials = Mock(token="test-token")
    credentials.with_subject.return_value = credentials
    from_info = Mock(return_value=credentials)
    from_file = Mock()
    monkeypatch.setattr(google_directory.service_account.Credentials, "from_service_account_info", from_info)
    monkeypatch.setattr(google_directory.service_account.Credentials, "from_service_account_file", from_file)

    assert google_directory.directory_is_configured()
    assert google_directory.directory_access_token() == "test-token"
    google_directory.boto3.client.assert_called_once_with(
        "secretsmanager", region_name="ap-southeast-1"
    )
    client.get_secret_value.assert_called_once_with(
        SecretId="arn:aws:secretsmanager:ap-southeast-1:123:secret:test"
    )
    from_info.assert_called_once_with(secret, scopes=["directory-scope"])
    from_file.assert_not_called()
    credentials.with_subject.assert_called_once_with("dt@life.edu.ph")


def test_local_file_credentials_remain_supported(monkeypatch):
    monkeypatch.setattr(
        google_directory,
        "settings",
        SimpleNamespace(
            google_service_account_secret_id="",
            google_service_account_file="/local/credentials.json",
            google_workspace_delegated_admin="dt@life.edu.ph",
            google_directory_scope="directory-scope",
        ),
    )
    credentials = Mock(token="local-token")
    credentials.with_subject.return_value = credentials
    from_file = Mock(return_value=credentials)
    monkeypatch.setattr(google_directory.service_account.Credentials, "from_service_account_file", from_file)
    client = Mock()
    monkeypatch.setattr(google_directory.boto3, "client", client)

    assert google_directory.directory_is_configured()
    assert google_directory.directory_access_token() == "local-token"
    from_file.assert_called_once_with(
        "/local/credentials.json", scopes=["directory-scope"]
    )
    client.assert_not_called()
