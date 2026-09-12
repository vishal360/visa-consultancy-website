"""
Email delivery.

Two modes, chosen automatically:

* SMTP mode   -- SMTP_HOST is configured, so messages go out over SMTP.
* Offline mode -- no SMTP_HOST, so each message is written to data/outbox/ as a
  standards-compliant .eml file. Nothing is lost and the booking flow still
  works end to end in development.

Either way every attempt is recorded in the `email_log` table.

Sending happens on a background thread so a slow mail server never delays the
HTTP response to the visitor.
"""

from __future__ import annotations

import html
import re
import smtplib
import threading
import traceback
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from typing import Sequence

from . import db
from .config import BASE_DIR, OUTBOX_DIR, settings

_send_lock = threading.Lock()


# --------------------------------------------------------------------------- #
# Low-level send
# --------------------------------------------------------------------------- #
def _build_message(
    to: Sequence[str], subject: str, text_body: str, html_body: str | None
) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((settings.mail_from_name, settings.mail_from))
    msg["To"] = ", ".join(to)
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=settings.mail_from.split("@")[-1] or None)
    msg["X-Mailer"] = f"{settings.brand_name} booking system"
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")
    return msg


def _write_to_outbox(msg: EmailMessage, subject: str) -> str:
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    slug = re.sub(r"[^a-z0-9]+", "-", subject.lower()).strip("-")[:50] or "message"
    path = OUTBOX_DIR / f"{stamp}-{slug}.eml"
    path.write_bytes(bytes(msg))
    try:
        return str(path.relative_to(BASE_DIR))
    except ValueError:
        return str(path)


def _smtp_send(msg: EmailMessage, to: Sequence[str]) -> None:
    if settings.smtp_use_ssl:
        server: smtplib.SMTP = smtplib.SMTP_SSL(
            settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout
        )
    else:
        server = smtplib.SMTP(
            settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout
        )
    try:
        server.ehlo()
        if settings.smtp_use_tls and not settings.smtp_use_ssl:
            server.starttls()
            server.ehlo()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg, from_addr=settings.mail_from, to_addrs=list(to))
    finally:
        try:
            server.quit()
        except smtplib.SMTPException:
            server.close()


def send_email(
    to: Sequence[str],
    subject: str,
    text_body: str,
    html_body: str | None = None,
    *,
    kind: str = "",
    related_ref: str = "",
) -> dict:
    """Send (or queue) one email synchronously. Never raises."""
    recipients = [addr for addr in to if addr and "@" in addr]
    if not recipients:
        db.log_email([], subject, "failed", kind, related_ref, "No valid recipients")
        return {"status": "failed", "error": "No valid recipients"}

    msg = _build_message(recipients, subject, text_body, html_body)

    if not settings.smtp_configured:
        try:
            path = _write_to_outbox(msg, subject)
            db.log_email(
                recipients, subject, "queued", kind, related_ref, outbox_file=path
            )
            print(f"[mail] offline mode -> {path}  (to: {', '.join(recipients)})")
            return {"status": "queued", "outbox_file": path}
        except OSError as exc:
            db.log_email(recipients, subject, "failed", kind, related_ref, str(exc))
            return {"status": "failed", "error": str(exc)}

    try:
        with _send_lock:
            _smtp_send(msg, recipients)
        db.log_email(recipients, subject, "sent", kind, related_ref)
        print(f"[mail] sent '{subject}' to {', '.join(recipients)}")
        return {"status": "sent"}
    except Exception as exc:  # noqa: BLE001 - deliberately broad; email is best-effort
        error = f"{type(exc).__name__}: {exc}"
        # Preserve the message so nothing is silently lost.
        outbox_file = ""
        try:
            outbox_file = _write_to_outbox(msg, subject)
        except OSError:
            pass
        db.log_email(
            recipients, subject, "failed", kind, related_ref, error, outbox_file
        )
        print(f"[mail] FAILED '{subject}': {error}")
        if settings.debug:
            traceback.print_exc()
        return {"status": "failed", "error": error}


def send_email_async(*args, **kwargs) -> None:
    """Fire-and-forget wrapper so HTTP handlers stay fast."""
    thread = threading.Thread(
        target=send_email, args=args, kwargs=kwargs, daemon=True, name="mailer"
    )
    thread.start()


# --------------------------------------------------------------------------- #
# Presentation helpers
# --------------------------------------------------------------------------- #
def pretty_date(iso_date: str) -> str:
    try:
        return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%A %d %B %Y")
    except ValueError:
        return iso_date


def pretty_time(hhmm: str) -> str:
    try:
        return datetime.strptime(hhmm, "%H:%M").strftime("%H:%M")
    except ValueError:
        return hhmm


def _shell(title: str, intro: str, rows: list[tuple[str, str]], footer: str) -> str:
    """Minimal, email-client-safe HTML (tables + inline styles only)."""
    row_html = "".join(
        f"""
        <tr>
          <td style="padding:10px 16px;border-bottom:1px solid #e8ecf3;color:#5b6478;
                     font-size:13px;font-family:Arial,Helvetica,sans-serif;
                     white-space:nowrap;vertical-align:top;">{html.escape(label)}</td>
          <td style="padding:10px 16px;border-bottom:1px solid #e8ecf3;color:#131a2a;
                     font-size:14px;font-weight:bold;
                     font-family:Arial,Helvetica,sans-serif;">{value}</td>
        </tr>"""
        for label, value in rows
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:24px 12px;background:#f2f5fa;">
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
         style="max-width:620px;margin:0 auto;background:#ffffff;border-radius:14px;
                overflow:hidden;box-shadow:0 4px 18px rgba(15,28,60,.09);">
    <tr>
      <td style="background:#0b1f4d;padding:26px 24px;">
        <div style="color:#ffd700;font-size:12px;letter-spacing:2px;text-transform:uppercase;
                    font-family:Arial,Helvetica,sans-serif;">
          {html.escape(settings.brand_name)}
        </div>
        <div style="color:#ffffff;font-size:22px;font-weight:bold;margin-top:6px;
                    font-family:Arial,Helvetica,sans-serif;">
          {html.escape(title)}
        </div>
      </td>
    </tr>
    <tr>
      <td style="padding:24px 24px 6px;color:#39445c;font-size:15px;line-height:1.6;
                 font-family:Arial,Helvetica,sans-serif;">
        {intro}
      </td>
    </tr>
    <tr>
      <td style="padding:12px 8px 20px;">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
          {row_html}
        </table>
      </td>
    </tr>
    <tr>
      <td style="padding:0 24px 26px;color:#5b6478;font-size:13px;line-height:1.6;
                 font-family:Arial,Helvetica,sans-serif;">
        {footer}
      </td>
    </tr>
    <tr>
      <td style="background:#f7f9fc;padding:16px 24px;color:#7a839a;font-size:12px;
                 line-height:1.6;font-family:Arial,Helvetica,sans-serif;
                 border-top:1px solid #e8ecf3;">
        {html.escape(settings.brand_name)} &middot; {html.escape(settings.office_address)}<br>
        {html.escape(settings.contact_phone)} &middot;
        <a href="mailto:{html.escape(settings.contact_email)}"
           style="color:#1b57d6;">{html.escape(settings.contact_email)}</a>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _text_block(rows: list[tuple[str, str]]) -> str:
    width = max((len(label) for label, _ in rows), default=0)
    return "\n".join(f"  {label.ljust(width)}  {value}" for label, value in rows)


def _escape_rows(rows: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return [(label, html.escape(value)) for label, value in rows]


def _set_row(rows: list[tuple[str, str]], label: str, value: str) -> None:
    """Replace a row's value by label, ignoring rows that are not present."""
    for index, (existing, _) in enumerate(rows):
        if existing == label:
            rows[index] = (existing, value)
            return


def _first_name(full_name: str) -> str:
    parts = (full_name or "").split()
    return parts[0] if parts else "there"


# --------------------------------------------------------------------------- #
# Booking emails
# --------------------------------------------------------------------------- #
def _booking_rows(booking: dict) -> list[tuple[str, str]]:
    return [
        ("Reference", booking["reference"]),
        ("Date", pretty_date(booking["slot_date"])),
        ("Time", f"{pretty_time(booking['slot_time'])} ({settings.timezone_label})"),
        ("Service", booking["service_name"]),
        ("Format", booking["mode_name"]),
        ("Name", booking["full_name"]),
        ("Email", booking["email"]),
        ("Phone", booking["phone"]),
        ("Nationality", booking.get("nationality") or "—"),
        ("Applicants", str(booking.get("applicants", 1))),
        ("Timeline", booking.get("travel_timeline") or "—"),
    ]


def notify_admin_new_booking(booking: dict) -> None:
    """Email the consultancy about a new booking."""
    rows = _booking_rows(booking)
    subject = (
        f"New consultation: {booking['full_name']} — "
        f"{pretty_date(booking['slot_date'])} {pretty_time(booking['slot_time'])}"
    )

    message = (booking.get("message") or "").strip()
    html_rows = _escape_rows(rows)
    _set_row(
        html_rows,
        "Reference",
        f"<span style='font-family:monospace;font-size:15px;'>"
        f"{html.escape(booking['reference'])}</span>",
    )
    _set_row(
        html_rows,
        "Email",
        f"<a href='mailto:{html.escape(booking['email'])}' style='color:#1b57d6;'>"
        f"{html.escape(booking['email'])}</a>",
    )
    _set_row(
        html_rows,
        "Phone",
        f"<a href='tel:{html.escape(booking['phone'])}' style='color:#1b57d6;'>"
        f"{html.escape(booking['phone'])}</a>",
    )
    if message:
        html_rows.append(("Message", html.escape(message).replace("\n", "<br>")))

    admin_link = f"{settings.base_url}/admin/bookings?q={booking['reference']}"
    html_body = _shell(
        "New consultation booked",
        "A visitor has just booked a consultation through the website. "
        "The slot is held with <strong>pending</strong> status until you confirm it.",
        html_rows,
        f"<a href='{html.escape(admin_link)}' "
        f"style='display:inline-block;background:#1b57d6;color:#ffffff;padding:11px 20px;"
        f"border-radius:8px;text-decoration:none;font-weight:bold;'>"
        f"Open in dashboard</a>",
    )

    text_rows = list(rows)
    if message:
        text_rows.append(("Message", message.replace("\n", " / ")))
    text_body = (
        "NEW CONSULTATION BOOKED\n"
        "=======================\n\n"
        f"{_text_block(text_rows)}\n\n"
        f"Manage this booking: {admin_link}\n"
    )

    send_email_async(
        settings.notify_emails,
        subject,
        text_body,
        html_body,
        kind="booking_admin",
        related_ref=booking["reference"],
    )


def send_client_booking_confirmation(booking: dict) -> None:
    """Email the visitor their booking receipt."""
    subject = f"Your consultation is booked — {booking['reference']}"
    rows = [
        ("Reference", booking["reference"]),
        ("Date", pretty_date(booking["slot_date"])),
        ("Time", f"{pretty_time(booking['slot_time'])} ({settings.timezone_label})"),
        ("Service", booking["service_name"]),
        ("Format", booking["mode_name"]),
    ]

    mode_note = {
        "video": "We will email you a secure video-call link shortly before the session.",
        "phone": f"One of our advisers will call you on <strong>{html.escape(booking['phone'])}</strong>.",
        "office": f"Please arrive 10 minutes early at {html.escape(settings.office_address)}.",
    }.get(booking.get("mode_id", "video"), "")

    html_body = _shell(
        "Consultation request received",
        f"Hi {html.escape(_first_name(booking['full_name']))}, "
        "thank you for booking with us. Your slot is reserved and a consultant will "
        "confirm it by email shortly.",
        _escape_rows(rows),
        f"<p style='margin:0 0 10px;'>{mode_note}</p>"
        "<p style='margin:0 0 10px;'><strong>What to prepare:</strong> your passport "
        "bio-page, any previous Ukrainian visas or refusals, and a rough idea of your "
        "intended travel dates.</p>"
        f"<p style='margin:0;'>Need to reschedule? Reply to this email or call "
        f"{html.escape(settings.contact_phone)} quoting "
        f"<strong>{html.escape(booking['reference'])}</strong>.</p>",
    )

    text_body = (
        f"Hi {booking['full_name']},\n\n"
        "Thank you for booking a consultation with "
        f"{settings.brand_name}. Your slot is reserved and we will confirm shortly.\n\n"
        f"{_text_block(rows)}\n\n"
        "What to prepare: your passport bio-page, any previous Ukrainian visas or\n"
        "refusals, and a rough idea of your intended travel dates.\n\n"
        f"Need to reschedule? Reply to this email or call {settings.contact_phone}\n"
        f"quoting {booking['reference']}.\n\n"
        f"— {settings.brand_name}\n{settings.office_address}\n"
    )

    send_email_async(
        [booking["email"]],
        subject,
        text_body,
        html_body,
        kind="booking_client",
        related_ref=booking["reference"],
    )


def send_status_update(booking: dict, old_status: str) -> None:
    """Tell the client their booking status changed (confirmed / cancelled)."""
    status = booking["status"]
    headline = {
        "confirmed": "Your consultation is confirmed",
        "cancelled": "Your consultation has been cancelled",
        "completed": "Thank you for your consultation",
    }.get(status)
    if not headline:
        return

    intro = {
        "confirmed": "Good news — a consultant has confirmed your appointment. "
        "We are looking forward to speaking with you.",
        "cancelled": "Your appointment has been cancelled. If this was not "
        "intended, please get in touch and we will find you a new slot.",
        "completed": "Thanks for meeting with us. A written summary of the advice "
        "and next steps will follow separately.",
    }[status]

    rows = [
        ("Reference", booking["reference"]),
        ("Date", pretty_date(booking["slot_date"])),
        ("Time", f"{pretty_time(booking['slot_time'])} ({settings.timezone_label})"),
        ("Service", booking["service_name"]),
        ("Format", booking["mode_name"]),
        ("Status", status.title()),
    ]

    html_body = _shell(
        headline,
        f"Hi {html.escape(_first_name(booking['full_name']))}, {intro}",
        _escape_rows(rows),
        f"Questions? Reply to this email or call "
        f"{html.escape(settings.contact_phone)}.",
    )
    text_body = (
        f"{headline.upper()}\n\n"
        f"Hi {booking['full_name']}, {intro}\n\n"
        f"{_text_block(rows)}\n\n"
        f"Questions? Reply to this email or call {settings.contact_phone}.\n\n"
        f"— {settings.brand_name}\n"
    )

    send_email_async(
        [booking["email"]],
        f"{headline} — {booking['reference']}",
        text_body,
        html_body,
        kind=f"status_{status}",
        related_ref=booking["reference"],
    )


# --------------------------------------------------------------------------- #
# Enquiry emails
# --------------------------------------------------------------------------- #
def notify_admin_new_enquiry(enquiry: dict) -> None:
    rows = [
        ("Reference", enquiry["reference"]),
        ("Name", enquiry["full_name"]),
        ("Email", enquiry["email"]),
        ("Phone", enquiry.get("phone") or "—"),
        ("Topic", enquiry.get("topic") or "—"),
    ]
    message = enquiry["message"].strip()

    html_rows = [(label, html.escape(value)) for label, value in rows]
    html_rows[2] = (
        "Email",
        f"<a href='mailto:{html.escape(enquiry['email'])}' style='color:#1b57d6;'>"
        f"{html.escape(enquiry['email'])}</a>",
    )
    html_rows.append(("Message", html.escape(message).replace("\n", "<br>")))

    html_body = _shell(
        "New website enquiry",
        "Someone has sent a message through the contact form.",
        html_rows,
        f"<a href='{settings.base_url}/admin/enquiries' "
        f"style='display:inline-block;background:#1b57d6;color:#ffffff;padding:11px 20px;"
        f"border-radius:8px;text-decoration:none;font-weight:bold;'>Open dashboard</a>",
    )
    text_body = (
        "NEW WEBSITE ENQUIRY\n"
        "===================\n\n"
        f"{_text_block(rows)}\n\n"
        f"Message:\n{message}\n\n"
        f"Dashboard: {settings.base_url}/admin/enquiries\n"
    )

    send_email_async(
        settings.notify_emails,
        f"New enquiry from {enquiry['full_name']}",
        text_body,
        html_body,
        kind="enquiry_admin",
        related_ref=enquiry["reference"],
    )


def send_client_enquiry_ack(enquiry: dict) -> None:
    rows = [
        ("Reference", enquiry["reference"]),
        ("Topic", enquiry.get("topic") or "General enquiry"),
    ]
    html_body = _shell(
        "We received your message",
        f"Hi {html.escape(_first_name(enquiry['full_name']))}, "
        "thanks for getting in touch. A consultant will reply within one business day.",
        _escape_rows(rows),
        "In a hurry? You can book a consultation slot directly at "
        f"<a href='{settings.base_url}/#booking' style='color:#1b57d6;'>"
        f"{html.escape(settings.base_url)}</a>.",
    )
    text_body = (
        f"Hi {enquiry['full_name']},\n\n"
        "Thanks for getting in touch. A consultant will reply within one business day.\n\n"
        f"{_text_block(rows)}\n\n"
        f"In a hurry? Book a consultation directly: {settings.base_url}/#booking\n\n"
        f"— {settings.brand_name}\n"
    )
    send_email_async(
        [enquiry["email"]],
        f"We received your message — {enquiry['reference']}",
        text_body,
        html_body,
        kind="enquiry_client",
        related_ref=enquiry["reference"],
    )


def send_test_email(to: str) -> dict:
    """Synchronous deliverability check, used by the CLI and admin dashboard."""
    rows = [
        ("Mode", "SMTP" if settings.smtp_configured else "Offline (outbox)"),
        ("Host", settings.smtp_host or "—"),
        ("From", settings.mail_from),
        ("Sent at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    ]
    return send_email(
        [to],
        f"[{settings.brand_name}] Email configuration test",
        "This is a test message from your booking system.\n\n"
        f"{_text_block(rows)}\n\nIf you can read this, delivery works.\n",
        _shell(
            "Email configuration test",
            "This is a test message from your booking system. "
            "If you can read this, delivery works.",
            _escape_rows(rows),
            "You can safely delete this message.",
        ),
        kind="test",
    )
