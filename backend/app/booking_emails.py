"""Durable booker-only email delivery. Provider calls never run in booking requests."""
import asyncio
from datetime import datetime, timedelta, timezone
from html import escape
import json
import logging
from pathlib import Path
from string import Template
from uuid import uuid4
from zoneinfo import ZoneInfo

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.auth import current_librarian
from app.config import settings
from app.database import SessionLocal, get_db
from app.models import BookingEmail, BookingResource, FacilityBooking, User

router = APIRouter(prefix="/api/bookings/emails", tags=["Booking email delivery"])
logger = logging.getLogger(__name__)
EMAIL_TEMPLATE = Template(Path(__file__).with_name("booking-email.html").read_text(encoding="utf-8"))
TITLES = {"confirmed": "Booking Confirmed", "cancelled": "Booking Cancelled",
    "extended": "Session Extended", "reminder": "Booking Starts in 15 Minutes", "ended": "Session Ended"}
COPY = {"confirmed": "Your library booking is confirmed. We look forward to welcoming you.",
    "cancelled": "Your booking has been cancelled. The reserved time is now available to other users.",
    "extended": "Your session has been extended. Your updated booking details are below.",
    "reminder": "Your booking starts in 15 minutes. Please arrive at the library counter before your session.",
    "ended": "Your session has ended. Please return your pass to the librarian and collect your ID."}


def now():
    return datetime.now(timezone.utc)


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def aws_client(service):
    return boto3.client(service, region_name=settings.aws_region or "ap-southeast-1",
        config=Config(connect_timeout=5, read_timeout=15, retries={"max_attempts": 0}))


async def snapshot(db, booking):
    user_id = booking.owner_id or (booking.participants[0].get("user_id") if booking.participants else None)
    user = await db.get(User, user_id) if user_id else None
    resource = await db.get(BookingResource, booking.resource_id)
    return user, {"number": booking.id, "name": user.name if user else "Library User",
        "resource": resource.name, "resource_type": {"nap_pod": "Nap Pod", "collaboration_room": "Collaboration Room",
        "computer": "Library Computer"}.get(resource.kind, resource.name), "resource_kind": resource.kind,
        "starts_at": aware(booking.starts_at).isoformat(), "ends_at": aware(booking.ends_at).isoformat(),
        "members": [p["name"] for p in booking.participants] + [name for action in booking.actions
            if action.get("action") == "booked" for name in action.get("additional_member_names", [])]}


async def queue_email(db, booking, kind, due=None, key=None):
    await db.flush()
    user, payload = await snapshot(db, booking)
    recipient = user.email.strip().lower() if user else ""
    key = key or f"booking:{booking.id}:{kind}"
    row = await db.scalar(select(BookingEmail).where(BookingEmail.dedupe_key == key).with_for_update())
    if row and row.state not in ("pending", "held"):
        return row
    suppressed = recipient and await db.scalar(select(BookingEmail.id).where(
        BookingEmail.recipient == recipient, BookingEmail.state.in_(["bounced", "complained"])).limit(1))
    if not row:
        row = BookingEmail(dedupe_key=key, booking_id=booking.id, kind=kind, recipient=recipient, attempts=0)
        db.add(row)
    row.payload, row.updated_at, row.next_attempt_at = payload, now(), due or now()
    row.state = "skipped" if not recipient else "suppressed" if suppressed else "held" if (
        settings.booking_email_test_recipient and recipient != settings.booking_email_test_recipient.lower()) else "pending"
    row.last_error = "Booker has no saved email address" if not recipient else "Recipient suppressed after a bounce or complaint" if suppressed else None
    return row


async def booking_changed(db, booking, kind):
    if not settings.booking_email_enabled:
        return
    await db.flush()
    if kind == "confirmed":
        await queue_email(db, booking, kind)
        if aware(booking.starts_at) > now() + timedelta(minutes=15):
            await queue_email(db, booking, "reminder", aware(booking.starts_at) - timedelta(minutes=15))
        await queue_email(db, booking, "ended", aware(booking.ends_at))
    elif kind == "cancelled":
        for row in (await db.scalars(select(BookingEmail).where(BookingEmail.booking_id == booking.id,
                BookingEmail.state.in_(["pending", "held"])).with_for_update())).all():
            row.state = "skipped"
        await queue_email(db, booking, kind)
    elif kind == "extended":
        await queue_email(db, booking, kind, key=f"booking:{booking.id}:extended:{len(booking.actions)}")
        await queue_email(db, booking, "ended", aware(booking.ends_at))
        if aware(booking.starts_at) > now():
            await queue_email(db, booking, "reminder", max(now(), aware(booking.starts_at) - timedelta(minutes=15)))
    else:
        await queue_email(db, booking, "ended")


def render(row):
    p, kind = row.payload, row.kind
    title = TITLES[kind]
    base = settings.frontend_url.rstrip("/")
    manage = base + "/book?view=history"
    slug = {"nap_pod": "nap-pod", "collaboration_room": "collaboration-room"}.get(p["resource_kind"])
    guideline = base + "/guidelines/" + slug if slug else None
    start, end = [datetime.fromisoformat(p[key]).astimezone(ZoneInfo("Asia/Manila")) for key in ("starts_at", "ends_at")]
    details = [("Resource", p["resource"]), ("Date", start.strftime("%B %d, %Y")),
        ("Time", start.strftime("%I:%M %p") + " - " + end.strftime("%b %d, %I:%M %p") + " (Manila)"),
        ("Booked by", p["name"]), ("Reference", f"Reservation #{p['number']}")]
    if p.get("members") and p["resource_kind"] == "collaboration_room":
        details.insert(4, ("Members", ", ".join(p["members"])))
    reminder = "Please return your pass to the librarian and collect your ID." if kind == "ended" else (
        "Before using the facility, please surrender your ID to the librarian and collect your pass.")
    rows = "".join(f'<tr><td style="padding:12px 0;border-bottom:1px solid #e5e7eb;color:#626a76;width:38%">{escape(k)}</td><td style="padding:12px 0;border-bottom:1px solid #e5e7eb">{escape(v)}</td></tr>' for k, v in details)
    guideline_html = f'<p>Please follow the <a href="{escape(guideline, quote=True)}" style="color:#690f0d">usage guidelines</a> accepted during booking.</p>' if guideline else ""
    pass_html = f'<div style="background:#f2e8dc;border-left:4px solid #9e1d20;padding:20px;margin:24px 0">{escape(reminder)}</div>' if kind != "cancelled" else ""
    body = f'<p style="font-size:11px;font-weight:700;color:#008292;margin:0 0 10px">{escape(title.upper())}</p><h1 class="email-heading" style="font:700 32px/1.2 Georgia,serif;color:#690f0d;margin:0 0 24px">{escape(title)}</h1><p>Hi {escape(p["name"])},</p><p>{escape(COPY[kind])}</p><table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;margin:24px 0">{rows}</table>{pass_html}{guideline_html}<table role="presentation" cellspacing="0" cellpadding="0" style="margin:26px 0"><tr><td bgcolor="#690f0d" style="border-radius:6px;text-align:center"><a href="{escape(manage, quote=True)}" style="display:inline-block;padding:15px 24px;background:#690f0d;border:1px solid #690f0d;border-radius:6px;color:white;font:700 14px Arial,sans-serif;text-decoration:none">View My Bookings</a></td></tr></table><p style="font-size:12px;color:#626a76">Google sign-in is required to access your bookings. Only the booker can manage the reservation.</p><p style="margin:28px 0 0">Life College Library<br><a href="mailto:library@life.edu.ph" style="color:#690f0d">library@life.edu.ph</a></p>'
    html = EMAIL_TEMPLATE.substitute(title=escape(title), preheader=escape(COPY[kind]), body=body)
    plain = f"Hi {p['name']},\n\n{COPY[kind]}\n\n" + "\n".join(f"{k}: {v}" for k, v in details)
    if kind != "cancelled":
        plain += "\n\n" + reminder
    plain += "\n\nManage booking: " + manage
    if guideline:
        plain += "\nGuidelines: " + guideline
    prefix = "[TEST] " if settings.booking_email_test_recipient else ""
    return prefix + title + " - " + p["resource_type"], html, plain


async def send_due(db):
    timestamp = now()
    # An interrupted provider call may have succeeded. Never auto-resend uncertain sends.
    for stale in (await db.scalars(select(BookingEmail).where(BookingEmail.state == "sending",
            BookingEmail.updated_at < timestamp - timedelta(minutes=10)).with_for_update(skip_locked=True))).all():
        stale.state, stale.last_error = "uncertain", "Delivery result unknown after an interrupted send; check before resending"
    row = await db.scalar(select(BookingEmail).where(BookingEmail.state == "pending",
        BookingEmail.next_attempt_at <= timestamp).order_by(BookingEmail.next_attempt_at).with_for_update(skip_locked=True).limit(1))
    if not row:
        await db.commit()
        return
    suppressed = await db.scalar(select(BookingEmail.id).where(BookingEmail.recipient == row.recipient,
        BookingEmail.state.in_(["bounced", "complained"])).limit(1))
    booking = await db.get(FacilityBooking, row.booking_id)
    cancelled = any(a.get("action") == "cancelled" for a in booking.actions)
    if suppressed or (cancelled and row.kind != "cancelled") or (row.kind == "reminder" and (
            aware(booking.starts_at) <= timestamp or timestamp - aware(row.next_attempt_at) > timedelta(minutes=2))):
        row.state = "suppressed" if suppressed else "skipped"
        await db.commit()
        return
    row.state, row.updated_at = "sending", timestamp
    row.attempts += 1
    await db.commit()
    subject, html, plain = render(row)
    try:
        result = await asyncio.to_thread(aws_client("sesv2").send_email,
            FromEmailAddress=f"Life College Library <{settings.booking_email_sender}>",
            Destination={"ToAddresses": [row.recipient]}, ReplyToAddresses=[settings.booking_email_sender],
            Content={"Simple": {"Subject": {"Data": subject, "Charset": "UTF-8"}, "Body": {
                "Html": {"Data": html, "Charset": "UTF-8"}, "Text": {"Data": plain, "Charset": "UTF-8"}}}},
            ConfigurationSetName=settings.booking_email_configuration_set,
            EmailTags=[{"Name": "application", "Value": "life-library"}, {"Name": "notification-id", "Value": str(row.id)}])
        row.state, row.provider_id, row.last_error = "sent", result["MessageId"], None
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        retryable = code in {"ThrottlingException", "TooManyRequestsException", "ServiceUnavailableException", "InternalFailure"}
        row.state = "pending" if retryable and row.attempts < 5 else "failed"
        row.last_error = "Email provider rejected the request; retry scheduled" if row.state == "pending" else "Email could not be sent; librarian review required"
        row.next_attempt_at = now() + timedelta(seconds=min(3600, 30 * 2 ** row.attempts))
    except Exception:
        row.state, row.last_error = "uncertain", "Delivery result unknown; review before resending to avoid duplicates"
    row.updated_at = now()
    await db.commit()


async def consume_feedback(db):
    if not settings.booking_email_feedback_queue:
        return
    sqs = aws_client("sqs")
    batch = await asyncio.to_thread(sqs.receive_message, QueueUrl=settings.booking_email_feedback_queue,
        MaxNumberOfMessages=10, WaitTimeSeconds=1, VisibilityTimeout=60)
    for message in batch.get("Messages", []):
        try:
            event = json.loads(message["Body"])
            if "Message" in event:
                event = json.loads(event["Message"])
        except (ValueError, TypeError):
            event = {}  # Dedicated SES topic also emits validation/control messages.
        if not isinstance(event, dict):
            event = {}
        provider_id = event.get("mail", {}).get("messageId")
        row = await db.scalar(select(BookingEmail).where(BookingEmail.provider_id == provider_id).with_for_update()) if provider_id else None
        notification_ids = event.get("mail", {}).get("tags", {}).get("notification-id", [])
        early = await db.get(BookingEmail, int(notification_ids[0])) if notification_ids and str(notification_ids[0]).isdigit() else None
        if not row and early and early.state == "sending":
            # Feedback may arrive before the sending task commits the provider ID.
            await asyncio.to_thread(sqs.change_message_visibility, QueueUrl=settings.booking_email_feedback_queue,
                ReceiptHandle=message["ReceiptHandle"], VisibilityTimeout=15)
            continue
        if (not row and early and early.state == "uncertain" and provider_id
                and event.get("mail", {}).get("tags", {}).get("application") == ["life-library"]):
            row = early
            row.provider_id = provider_id
        if row:
            state = {"Delivery": "delivered", "Bounce": "bounced", "Complaint": "complained", "Reject": "failed", "Rendering Failure": "failed"}.get(event.get("eventType"))
            if state and (row.state not in {"bounced", "complained"} or state in {"bounced", "complained"}):
                row.state, row.updated_at = state, now()
                row.last_error = "Recipient suppressed after a bounce or complaint" if state in {"bounced", "complained"} else "Provider delivery failed" if state == "failed" else None
        await db.commit()
        await asyncio.to_thread(sqs.delete_message, QueueUrl=settings.booking_email_feedback_queue, ReceiptHandle=message["ReceiptHandle"])


async def worker():
    while True:
        try:
            async with SessionLocal() as db:
                await send_due(db)
                await consume_feedback(db)
        except Exception:
            logger.warning("Booking email worker iteration failed")
        await asyncio.sleep(5)


async def email_staff(user=Depends(current_librarian)):
    if user.role not in {"librarian", "librarian_associate", "auditor"}:
        raise HTTPException(403, "Staff access required")
    return user


@router.get("")
async def status(user=Depends(email_staff), db=Depends(get_db)):
    rows = (await db.scalars(select(BookingEmail).order_by(BookingEmail.updated_at.desc()).limit(100))).all()
    return {"enabled": settings.booking_email_enabled, "test_recipient": settings.booking_email_test_recipient,
        "items": [{"id": r.id, "booking_id": r.booking_id, "kind": r.kind, "state": r.state,
            "attempts": r.attempts, "updated_at": r.updated_at.isoformat(), "last_error": r.last_error} for r in rows]}


@router.post("/{notification_id}/resend", status_code=204)
async def resend(notification_id: int, user=Depends(email_staff), db=Depends(get_db)):
    if user.role not in {"librarian", "librarian_associate"}:
        raise HTTPException(403, "Only librarians can resend booking emails")
    if not settings.booking_email_enabled:
        raise HTTPException(409, "Email delivery is disabled")
    row = await db.scalar(select(BookingEmail).where(BookingEmail.id == notification_id).with_for_update())
    if not row:
        raise HTTPException(404, "Email notification unavailable")
    if row.state not in {"failed", "uncertain"}:
        raise HTTPException(409, "Only failed or uncertain emails can be resent")
    booking = await db.get(FacilityBooking, row.booking_id)
    if row.kind not in {"confirmed", "cancelled", "extended"}:
        raise HTTPException(409, "Time-sensitive reminders cannot be resent")
    if any(a.get("action") == "cancelled" for a in booking.actions) and row.kind != "cancelled":
        raise HTTPException(409, "This booking is cancelled; its earlier notifications cannot be resent")
    await queue_email(db, booking, row.kind, key=f"resend:{row.id}:{uuid4().hex}")
    booking.actions = [*booking.actions, {"action": "email_resend_requested", "notification_id": row.id,
        "actor": f"manual:{user.id}", "at": now().isoformat()}]
    row.state, row.updated_at = "resend_requested", now()
    await db.commit()
