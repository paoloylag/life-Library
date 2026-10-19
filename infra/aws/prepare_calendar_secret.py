"""Add a dedicated Calendar encryption key without replacing existing secrets."""
import json

import boto3
from cryptography.fernet import Fernet


def main():
    session = boto3.Session(profile_name="life-library", region_name="ap-southeast-1")
    assert session.client("sts").get_caller_identity()["Account"] == "165115313524"
    ecs = session.client("ecs")
    service = ecs.describe_services(cluster="life-library-production", services=["life-library-production-api"])["services"][0]
    task = ecs.describe_task_definition(taskDefinition=service["taskDefinition"])["taskDefinition"]
    container = next(c for c in task["containerDefinitions"] if c["name"] == "api")
    ref = next(s["valueFrom"] for s in container["secrets"] if s["name"] == "GOOGLE_CLIENT_ID")
    assert ref.endswith(":googleClientId::")
    secret_id = ref.removesuffix(":googleClientId::")
    secrets = session.client("secretsmanager")
    current = secrets.get_secret_value(SecretId=secret_id)
    payload = json.loads(current["SecretString"])
    assert payload.get("googleClientId") and payload.get("googleClientSecret")
    if "googleCalendarEncryptionKey" not in payload:
        payload["googleCalendarEncryptionKey"] = Fernet.generate_key().decode()
        secrets.put_secret_value(SecretId=secret_id, SecretString=json.dumps(payload))
        print("Added dedicated Calendar encryption key; existing application credentials preserved.")
    else:
        Fernet(payload["googleCalendarEncryptionKey"].encode())
        print("Existing Calendar encryption key retained.")
    print("Production OAuth client:", payload["googleClientId"])


if __name__ == "__main__":
    main()
