from datetime import timedelta
import json

from botocore.exceptions import ClientError
import pytest
from sqlalchemy import select

from app import booking_emails as mail
from app.auth import issue_student
from app.config import settings
from app.models import BookingEmail, BookingResource, FacilityBooking, StudentProfile, User
from test_librarian_auth import auth_context, add_librarian, login


@pytest.fixture
def email_config(monkeypatch):
    monkeypatch.setattr(settings, "booking_email_enabled", True)
    monkeypatch.setattr(settings, "booking_email_test_recipient", "")
    monkeypatch.setattr(settings, "frontend_url", "https://library.life.edu.ph")


async def booking(db, client):
    user = User(name="Booker <Test>", email="booker@life.edu.ph", google_id="booker-google", role="student", is_active=True)
    db.add(user)
    resource = BookingResource(name="Nap Pod 1", kind="nap_pod", duration_minutes=45, max_minutes=90, capacity=1, is_active=True)
    db.add(resource)
    await db.flush()
    db.add(StudentProfile(user_id=user.id, student_number="EMAIL-1", user_type="student", is_active=True))
    b = FacilityBooking(resource_id=resource.id, owner_id=user.id, starts_at=mail.now()+timedelta(hours=1),
        ends_at=mail.now()+timedelta(hours=2), participants=[{"user_id":user.id,"name":user.name}], source="user", actions=[{"action":"booked"}])
    db.add(b)
    await db.commit()
    client.cookies.set("library_session", issue_student(user.id, google_authenticated=True))
    return b, user


@pytest.mark.asyncio
async def test_queue_recipient_dedupe_schedules_and_render(auth_context, email_config):
    client, db = auth_context
    b, user = await booking(db, client)
    await mail.booking_changed(db, b, "confirmed")
    await mail.booking_changed(db, b, "confirmed")
    await db.commit()
    rows = (await db.scalars(select(BookingEmail))).all()
    assert len(rows) == 3 and {r.kind for r in rows} == {"confirmed","reminder","ended"}
    assert {r.recipient for r in rows} == {user.email}
    confirmed = next(r for r in rows if r.kind == "confirmed")
    subject, html, plain = mail.render(confirmed)
    assert subject == "Booking Confirmed - Nap Pod"
    assert "Booker &lt;Test&gt;" in html and "Booker <Test>" not in html
    assert "https://library.life.edu.ph/book?view=history" in html
    assert "/guidelines/nap-pod" in html and "127.0.0.1" not in html
    assert f"Reservation #{b.id}" in plain
    b.ends_at += timedelta(minutes=30)
    b.actions = [*b.actions, {"action":"extended"}]
    await mail.booking_changed(db, b, "extended")
    await db.commit()
    assert next(r for r in rows if r.kind == "ended").next_attempt_at == b.ends_at
    b.actions = [*b.actions, {"action":"cancelled"}]
    await mail.booking_changed(db, b, "cancelled")
    await db.commit()
    assert all(r.state == "skipped" for r in rows)
    assert await db.scalar(select(BookingEmail.id).where(BookingEmail.kind == "cancelled"))


@pytest.mark.asyncio
async def test_send_retry_delivery_and_suppression(auth_context, email_config, monkeypatch):
    client, db = auth_context
    b, _ = await booking(db, client)
    row = await mail.queue_email(db, b, "confirmed")
    await db.commit()
    calls = []
    class SES:
        def send_email(self, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                raise ClientError({"Error":{"Code":"TooManyRequestsException"}}, "SendEmail")
            return {"MessageId":"provider-1"}
    monkeypatch.setattr(mail, "aws_client", lambda service: SES())
    await mail.send_due(db)
    assert row.state == "pending" and row.attempts == 1
    row.next_attempt_at = mail.now()-timedelta(seconds=1)
    await db.commit()
    await mail.send_due(db)
    assert row.state == "sent" and row.provider_id == "provider-1"
    assert calls[-1]["Destination"] == {"ToAddresses":["booker@life.edu.ph"]}
    assert "CcAddresses" not in calls[-1]["Destination"]
    monkeypatch.setattr(settings, "booking_email_feedback_queue", "https://sqs.example/queue")
    class SQS:
        def receive_message(self, **kwargs):
            return {"Messages":[{"Body":json.dumps({"eventType":"Bounce","mail":{"messageId":"provider-1"}}),"ReceiptHandle":"receipt"}]}
        def delete_message(self, **kwargs): pass
    monkeypatch.setattr(mail, "aws_client", lambda service: SQS())
    await mail.consume_feedback(db)
    assert row.state == "bounced"
    other = await mail.queue_email(db, b, "extended", key="another")
    assert other.state == "suppressed"


@pytest.mark.asyncio
async def test_ambiguous_send_is_not_automatically_retried(auth_context, email_config, monkeypatch):
    client, db = auth_context
    b, _ = await booking(db, client)
    row = await mail.queue_email(db, b, "confirmed")
    await db.commit()
    class SES:
        def send_email(self, **kwargs): raise TimeoutError("private-provider-error")
    monkeypatch.setattr(mail, "aws_client", lambda service: SES())
    await mail.send_due(db)
    assert row.state == "uncertain" and "private-provider-error" not in row.last_error
    await mail.send_due(db)
    assert row.attempts == 1
    assert await db.get(FacilityBooking, b.id)


@pytest.mark.asyncio
async def test_test_allowlist_holds_other_recipients(auth_context, email_config, monkeypatch):
    client, db = auth_context
    b, _ = await booking(db, client)
    monkeypatch.setattr(settings,"booking_email_test_recipient","paolo.ylag@life.edu.ph")
    row = await mail.queue_email(db, b, "confirmed")
    assert row.state == "held"


@pytest.mark.asyncio
async def test_retry_limit_and_cancelled_reminder(auth_context, email_config, monkeypatch):
    client, db = auth_context
    b, _ = await booking(db, client)
    row = await mail.queue_email(db, b, "confirmed")
    await db.commit()
    class SES:
        def send_email(self, **kwargs):
            raise ClientError({"Error":{"Code":"ServiceUnavailableException"}},"SendEmail")
    monkeypatch.setattr(mail,"aws_client",lambda service:SES())
    for _ in range(5):
        row.next_attempt_at=mail.now()-timedelta(seconds=1)
        await db.commit()
        await mail.send_due(db)
    assert row.state == "failed" and row.attempts == 5
    reminder=await mail.queue_email(db,b,"reminder")
    b.actions=[*b.actions,{"action":"cancelled"}]
    await db.commit()
    await mail.send_due(db)
    assert reminder.state == "skipped"


@pytest.mark.asyncio
async def test_pass_acknowledgement_owner_only_and_idempotent(auth_context):
    client, db = auth_context
    b, user = await booking(db, client)
    client.cookies.clear()
    assert (await client.post(f"/api/bookings/{b.id}/acknowledge-pass")).status_code == 401
    other=User(name="Other User",email="other@life.edu.ph",google_id="other-google",role="student",is_active=True)
    db.add(other)
    await db.flush()
    db.add(StudentProfile(user_id=other.id,student_number="EMAIL-2",user_type="student",is_active=True))
    await db.commit()
    client.cookies.set("library_session",issue_student(other.id,google_authenticated=True))
    assert (await client.post(f"/api/bookings/{b.id}/acknowledge-pass")).status_code == 403
    client.cookies.set("library_session",issue_student(user.id,google_authenticated=True))
    for _ in range(2):
        assert (await client.post(f"/api/bookings/{b.id}/acknowledge-pass")).status_code == 204
    assert len([a for a in b.actions if a["action"] == "pass_reminder_acknowledged"]) == 1
    response=await client.get("/api/bookings",headers={"X-Booking-Mode":"user"})
    assert response.json()["items"][0]["pass_reminder_acknowledged"] is True


@pytest.mark.asyncio
async def test_email_monitor_and_resend_authorization(auth_context, email_config):
    client, db = auth_context
    b, _ = await booking(db, client)
    row=await mail.queue_email(db,b,"confirmed")
    row.state="failed"
    await db.commit()
    assert (await client.get("/api/bookings/emails")).status_code == 401
    await add_librarian(db,"auditor")
    await login(client,"auditor")
    assert (await client.get("/api/bookings/emails")).status_code == 200
    assert (await client.post(f"/api/bookings/emails/{row.id}/resend")).status_code == 403
    await add_librarian(db,"librarian")
    await login(client,"librarian")
    assert (await client.post(f"/api/bookings/emails/{row.id}/resend")).status_code == 204
    assert row.state == "resend_requested"
    assert (await client.post(f"/api/bookings/emails/{row.id}/resend")).status_code == 409
