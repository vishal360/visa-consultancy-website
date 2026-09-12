"""
Admin routes: authentication plus the consultant-facing dashboard.

Page routes render server-side HTML. Mutations go through JSON endpoints that
require both a valid session cookie and a matching CSRF token.
"""

from __future__ import annotations

import html
from datetime import datetime, timedelta

from .. import auth, db, mailer, scheduling
from ..config import settings
from ..web import (
    Request,
    Response,
    error_response,
    html_response,
    json_for_script,
    json_response,
    login_limiter,
    redirect,
    render,
)

LOGIN_PATH = "/admin/login"


def register(router) -> None:
    router.add("GET", "/admin", dashboard)
    router.add("GET", "/admin/login", login_page)
    router.add("POST", "/admin/login", login_submit)
    router.add("GET", "/admin/logout", logout)
    router.add("POST", "/admin/logout", logout)
    router.add("GET", "/admin/bookings", bookings_page)
    router.add("GET", "/admin/enquiries", enquiries_page)
    router.add("GET", "/admin/export.csv", export_csv)

    # JSON API consumed by the dashboard UI.
    router.add("GET", "/admin/api/bookings", api_bookings)
    router.add("GET", "/admin/api/bookings/<booking_id>", api_booking_detail)
    router.add("POST", "/admin/api/bookings/<booking_id>/status", api_set_status)
    router.add("POST", "/admin/api/bookings/<booking_id>/notes", api_set_notes)
    router.add("POST", "/admin/api/bookings/<booking_id>/delete", api_delete_booking)
    router.add("GET", "/admin/api/enquiries", api_enquiries)
    router.add("POST", "/admin/api/enquiries/<enquiry_id>/status", api_enquiry_status)
    router.add("GET", "/admin/api/stats", api_stats)
    router.add("GET", "/admin/api/emails", api_emails)
    router.add("POST", "/admin/api/slots/block", api_block_slot)
    router.add("POST", "/admin/api/slots/unblock", api_unblock_slot)
    router.add("GET", "/admin/api/slots", api_list_blocked)
    router.add("POST", "/admin/api/test-email", api_test_email)


# --------------------------------------------------------------------------- #
# Guards
# --------------------------------------------------------------------------- #
def _require_session(request: Request) -> dict | None:
    return request.session


def _guard_page(request: Request) -> Response | None:
    """Redirect browser requests to the login page when unauthenticated."""
    if _require_session(request) is None:
        target = request.path
        if request.path.startswith("/admin") and request.path != LOGIN_PATH:
            return redirect(f"{LOGIN_PATH}?next={target}")
        return redirect(LOGIN_PATH)
    return None


def _guard_api(request: Request, *, require_csrf: bool = True) -> tuple[dict | None, Response | None]:
    """Return (session, error_response). Enforces auth and CSRF for writes."""
    session = _require_session(request)
    if session is None:
        return None, error_response("Your session has expired. Please sign in again.", 401)
    if require_csrf and request.method == "POST":
        submitted = request.headers.get("X-CSRF-Token", "") or request.field("csrf_token")
        if not auth.check_csrf(session, submitted):
            return None, error_response("Invalid or missing CSRF token.", 403)
    return session, None


# --------------------------------------------------------------------------- #
# Auth pages
# --------------------------------------------------------------------------- #
def _admin_context(session: dict | None = None) -> dict:
    name = (session or {}).get("name") or (session or {}).get("email", "")
    return {
        "brand_name": settings.brand_name,
        "year": datetime.now().year,
        "user_name": name,
        "user_email": (session or {}).get("email", ""),
        "user_initial": (name[:1] or "?").upper(),
        "csrf_token": (session or {}).get("csrf_token", ""),
        "timezone_label": settings.timezone_label,
    }


def login_page(request: Request, error: str = "", email: str = "") -> Response:
    if request.session is not None:
        return redirect("/admin")
    next_path = request.get("next", "/admin")
    if not next_path.startswith("/admin"):
        next_path = "/admin"

    mail_hint = (
        f"SMTP via {settings.smtp_host}"
        if settings.smtp_configured
        else "Offline mode — emails saved to data/outbox/"
    )
    return html_response(
        render(
            "admin_login.html",
            **_admin_context(),
            error=error,
            email=email,
            next_path=next_path,
            mail_hint=mail_hint,
        ),
        status=401 if error else 200,
    )


def login_submit(request: Request) -> Response:
    email = request.field("email").strip()
    password = request.field("password")
    next_path = request.field("next") or "/admin"
    if not next_path.startswith("/admin"):
        next_path = "/admin"

    allowed, retry_after = login_limiter.check(f"login:{request.client_ip}")
    if not allowed:
        minutes = max(1, retry_after // 60)
        return login_page(
            request,
            error=f"Too many attempts. Please wait about {minutes} minute(s).",
            email=email,
        )

    user = auth.authenticate(email, password)
    if user is None:
        db.log_activity(None, "login.failed", f"{email} from {request.client_ip}")
        return login_page(request, error="Incorrect email or password.", email=email)

    session = auth.create_session(user["id"], request.client_ip)
    db.log_activity(user["id"], "login.success", request.client_ip)

    response = redirect(next_path)
    response.set_cookie(
        auth.SESSION_COOKIE,
        session["token"],
        max_age=settings.session_ttl_hours * 3600,
    )
    return response


def logout(request: Request) -> Response:
    token = request.cookies.get(auth.SESSION_COOKIE, "")
    session = request.session
    if session:
        db.log_activity(session["id"], "logout", "")
    auth.destroy_session(token)
    response = redirect(LOGIN_PATH)
    response.delete_cookie(auth.SESSION_COOKIE)
    return response


# --------------------------------------------------------------------------- #
# Dashboard pages
# --------------------------------------------------------------------------- #
def dashboard(request: Request) -> Response:
    guard = _guard_page(request)
    if guard:
        return guard
    session = request.session or {}

    stats = db.dashboard_stats()
    upcoming, _ = db.list_bookings(status="live", limit=8, order="slot_asc")
    today_iso = scheduling.today().isoformat()
    upcoming = [b for b in upcoming if b["slot_date"] >= today_iso]

    boot = {
        "csrfToken": session.get("csrf_token", ""),
        "statuses": settings.BOOKING_STATUSES,
        "services": [{"id": s["id"], "name": s["name"]} for s in settings.SERVICES],
        "timezone": settings.timezone_label,
        "view": "overview",
    }

    return html_response(
        render(
            "admin_dashboard.html",
            **_admin_context(session),
            raw_boot=json_for_script(boot),
            raw_stat_cards=_render_stat_cards(stats),
            raw_upcoming=_render_upcoming(upcoming),
            raw_activity=_render_activity(db.list_activity(12)),
            raw_service_breakdown=_render_service_breakdown(stats["by_service"]),
            raw_status_filter=_render_status_options(),
            raw_service_filter=_render_service_filter(),
            mail_mode=(
                f"SMTP · {settings.smtp_host}"
                if settings.smtp_configured
                else "Offline · data/outbox/"
            ),
            emails_sent=stats["emails_sent"],
            emails_queued=stats["emails_queued"],
            emails_failed=stats["emails_failed"],
            active_view="overview",
        )
    )


def bookings_page(request: Request) -> Response:
    guard = _guard_page(request)
    if guard:
        return guard
    session = request.session or {}
    boot = {
        "csrfToken": session.get("csrf_token", ""),
        "statuses": settings.BOOKING_STATUSES,
        "services": [{"id": s["id"], "name": s["name"]} for s in settings.SERVICES],
        "timezone": settings.timezone_label,
        "view": "bookings",
        "initialQuery": request.get("q", ""),
        "initialStatus": request.get("status", "all"),
    }
    return html_response(
        render(
            "admin_bookings.html",
            **_admin_context(session),
            raw_boot=json_for_script(boot),
            raw_status_filter=_render_status_options(),
            raw_service_filter=_render_service_filter(),
            initial_query=request.get("q", ""),
            active_view="bookings",
        )
    )


def enquiries_page(request: Request) -> Response:
    guard = _guard_page(request)
    if guard:
        return guard
    session = request.session or {}
    boot = {
        "csrfToken": session.get("csrf_token", ""),
        "view": "enquiries",
        "statuses": ["new", "in-progress", "answered", "closed"],
    }
    return html_response(
        render(
            "admin_enquiries.html",
            **_admin_context(session),
            raw_boot=json_for_script(boot),
            active_view="enquiries",
        )
    )


def export_csv(request: Request) -> Response:
    guard = _guard_page(request)
    if guard:
        return guard
    csv_text = db.export_bookings_csv(
        status=request.get("status", "all"),
        search=request.get("q", ""),
        date_from=request.get("from", ""),
        date_to=request.get("to", ""),
        service_id=request.get("service", "all"),
    )
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    db.log_activity((request.session or {}).get("id"), "export.csv", stamp)
    return Response(
        "\ufeff" + csv_text,  # BOM so Excel opens UTF-8 correctly
        content_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="bookings-{stamp}.csv"',
            "Cache-Control": "no-store",
        },
    )


# --------------------------------------------------------------------------- #
# JSON API
# --------------------------------------------------------------------------- #
def api_bookings(request: Request) -> Response:
    session, err = _guard_api(request, require_csrf=False)
    if err:
        return err
    page = max(1, request.get_int("page", 1))
    per_page = max(5, min(request.get_int("per_page", 25), 200))
    rows, total = db.list_bookings(
        status=request.get("status", "all"),
        search=request.get("q", ""),
        date_from=request.get("from", ""),
        date_to=request.get("to", ""),
        service_id=request.get("service", "all"),
        limit=per_page,
        offset=(page - 1) * per_page,
        order=request.get("order", "slot"),
    )
    for row in rows:
        row["pretty_date"] = mailer.pretty_date(row["slot_date"])
        row["is_past"] = row["slot_date"] < scheduling.today().isoformat()
    return json_response(
        {
            "ok": True,
            "bookings": rows,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": max(1, (total + per_page - 1) // per_page),
        }
    )


def api_booking_detail(request: Request) -> Response:
    session, err = _guard_api(request, require_csrf=False)
    if err:
        return err
    try:
        booking = db.get_booking(int(request.params["booking_id"]))
    except (ValueError, LookupError):
        return error_response("Booking not found.", 404)
    booking["pretty_date"] = mailer.pretty_date(booking["slot_date"])
    return json_response(
        {
            "ok": True,
            "booking": booking,
            "emails": db.list_email_log(20, booking["reference"]),
        }
    )


def api_set_status(request: Request) -> Response:
    session, err = _guard_api(request)
    if err:
        return err
    status = request.field("status").strip()
    notify = request.field("notify").lower() in {"true", "1", "on", "yes"}
    if status not in settings.BOOKING_STATUSES:
        return error_response(
            f"Status must be one of: {', '.join(settings.BOOKING_STATUSES)}", 400
        )
    try:
        booking_id = int(request.params["booking_id"])
        before = db.get_booking(booking_id)
    except (ValueError, LookupError):
        return error_response("Booking not found.", 404)

    if before["status"] == status:
        return json_response({"ok": True, "booking": before, "unchanged": True})

    try:
        booking = db.update_booking_status(booking_id, status)
    except db.SlotTakenError as exc:
        return error_response(str(exc), 409)

    db.log_activity(
        (session or {}).get("id"),
        "booking.status",
        f"{booking['reference']}: {before['status']} → {status}",
    )
    email_sent = False
    if notify:
        mailer.send_status_update(booking, before["status"])
        email_sent = status in {"confirmed", "cancelled", "completed"}

    booking["pretty_date"] = mailer.pretty_date(booking["slot_date"])
    return json_response({"ok": True, "booking": booking, "email_sent": email_sent})


def api_set_notes(request: Request) -> Response:
    session, err = _guard_api(request)
    if err:
        return err
    try:
        booking_id = int(request.params["booking_id"])
        db.get_booking(booking_id)
    except (ValueError, LookupError):
        return error_response("Booking not found.", 404)
    notes = request.field("notes")[:4000]
    booking = db.update_booking_notes(booking_id, notes)
    db.log_activity((session or {}).get("id"), "booking.notes", booking["reference"])
    return json_response({"ok": True, "booking": booking})


def api_delete_booking(request: Request) -> Response:
    session, err = _guard_api(request)
    if err:
        return err
    try:
        booking_id = int(request.params["booking_id"])
        booking = db.get_booking(booking_id)
    except (ValueError, LookupError):
        return error_response("Booking not found.", 404)
    db.delete_booking(booking_id)
    db.log_activity(
        (session or {}).get("id"), "booking.deleted", booking["reference"]
    )
    return json_response({"ok": True, "deleted": booking["reference"]})


def api_enquiries(request: Request) -> Response:
    session, err = _guard_api(request, require_csrf=False)
    if err:
        return err
    page = max(1, request.get_int("page", 1))
    per_page = max(5, min(request.get_int("per_page", 25), 200))
    rows, total = db.list_enquiries(
        status=request.get("status", "all"),
        search=request.get("q", ""),
        limit=per_page,
        offset=(page - 1) * per_page,
    )
    return json_response(
        {
            "ok": True,
            "enquiries": rows,
            "total": total,
            "page": page,
            "pages": max(1, (total + per_page - 1) // per_page),
        }
    )


def api_enquiry_status(request: Request) -> Response:
    session, err = _guard_api(request)
    if err:
        return err
    status = request.field("status").strip()
    if status not in {"new", "in-progress", "answered", "closed"}:
        return error_response("Invalid status.", 400)
    try:
        enquiry_id = int(request.params["enquiry_id"])
    except ValueError:
        return error_response("Enquiry not found.", 404)
    enquiry = db.update_enquiry_status(enquiry_id, status)
    if enquiry is None:
        return error_response("Enquiry not found.", 404)
    db.log_activity(
        (session or {}).get("id"), "enquiry.status", f"{enquiry['reference']} → {status}"
    )
    return json_response({"ok": True, "enquiry": enquiry})


def api_stats(request: Request) -> Response:
    session, err = _guard_api(request, require_csrf=False)
    if err:
        return err
    return json_response({"ok": True, "stats": db.dashboard_stats()})


def api_emails(request: Request) -> Response:
    session, err = _guard_api(request, require_csrf=False)
    if err:
        return err
    return json_response(
        {
            "ok": True,
            "emails": db.list_email_log(
                max(1, min(request.get_int("limit", 50), 200)),
                request.get("ref", ""),
            ),
            "mode": "smtp" if settings.smtp_configured else "offline",
        }
    )


def api_block_slot(request: Request) -> Response:
    session, err = _guard_api(request)
    if err:
        return err
    slot_date = request.field("date").strip()
    slot_time = request.field("time").strip()
    reason = request.field("reason").strip()[:200]
    if scheduling.parse_date(slot_date) is None:
        return error_response("Use a date formatted as YYYY-MM-DD.", 400)
    if slot_time and scheduling.parse_time(slot_time) is None:
        return error_response("Use a time formatted as HH:MM.", 400)
    db.block_slot(slot_date, slot_time, reason)
    db.log_activity(
        (session or {}).get("id"), "slot.blocked", f"{slot_date} {slot_time or 'all day'}"
    )
    return json_response({"ok": True, "blocked": db.list_blocked()})


def api_unblock_slot(request: Request) -> Response:
    session, err = _guard_api(request)
    if err:
        return err
    slot_date = request.field("date").strip()
    slot_time = request.field("time").strip()
    if scheduling.parse_date(slot_date) is None:
        return error_response("Use a date formatted as YYYY-MM-DD.", 400)
    db.unblock_slot(slot_date, slot_time)
    db.log_activity(
        (session or {}).get("id"),
        "slot.unblocked",
        f"{slot_date} {slot_time or 'all day'}",
    )
    return json_response({"ok": True, "blocked": db.list_blocked()})


def api_list_blocked(request: Request) -> Response:
    session, err = _guard_api(request, require_csrf=False)
    if err:
        return err
    return json_response({"ok": True, "blocked": db.list_blocked()})


def api_test_email(request: Request) -> Response:
    session, err = _guard_api(request)
    if err:
        return err
    recipient = request.field("email").strip() or (session or {}).get("email", "")
    if "@" not in recipient:
        return error_response("Provide a valid email address.", 400)
    result = mailer.send_test_email(recipient)
    db.log_activity(
        (session or {}).get("id"), "email.test", f"{recipient} → {result['status']}"
    )
    return json_response({"ok": result["status"] != "failed", "result": result})


# --------------------------------------------------------------------------- #
# Server-rendered fragments
# --------------------------------------------------------------------------- #
def _e(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _render_stat_cards(stats: dict) -> str:
    cards = [
        ("Today", stats["today"], "Consultations scheduled today", "today"),
        ("Awaiting confirmation", stats["pending"], "Need your review", "pending"),
        ("Confirmed", stats["confirmed"], "Ready to go", "confirmed"),
        ("Upcoming", stats["upcoming"], "Live bookings from today", "upcoming"),
        ("New enquiries", stats["new_enquiries"], "Unread contact messages", "enquiries"),
        ("Last 7 days", stats["new_last_7_days"], "Bookings created this week", "recent"),
    ]
    return "\n".join(
        f"""
<article class="stat-card stat-card--{_e(key)}">
  <p class="stat-card__label">{_e(label)}</p>
  <p class="stat-card__value">{_e(value)}</p>
  <p class="stat-card__hint">{_e(hint)}</p>
</article>"""
        for label, value, hint, key in cards
    )


def _render_upcoming(bookings: list[dict]) -> str:
    if not bookings:
        return """
<div class="empty">
  <p class="empty__icon" aria-hidden="true">📭</p>
  <p><strong>No upcoming consultations.</strong></p>
  <p>New bookings from the website will appear here automatically.</p>
</div>"""
    rows = []
    for booking in bookings:
        rows.append(
            f"""
<tr data-booking-id="{_e(booking['id'])}">
  <td>
    <span class="cell-date">{_e(mailer.pretty_date(booking['slot_date']))}</span>
    <span class="cell-time">{_e(booking['slot_time'])}</span>
  </td>
  <td>
    <strong>{_e(booking['full_name'])}</strong>
    <span class="cell-sub">{_e(booking['email'])}</span>
  </td>
  <td>{_e(booking['service_name'])}</td>
  <td><span class="badge badge--{_e(booking['status'])}">{_e(booking['status'])}</span></td>
  <td class="cell-actions">
    <button class="btn-mini" type="button" data-open-booking="{_e(booking['id'])}">
      View
    </button>
  </td>
</tr>"""
        )
    return "\n".join(rows)


def _render_activity(entries: list[dict]) -> str:
    if not entries:
        return '<li class="feed__empty">Nothing logged yet.</li>'
    items = []
    for entry in entries:
        who = entry.get("user_name") or entry.get("user_email") or "Website visitor"
        try:
            when = datetime.fromisoformat(entry["created_at"]).strftime("%d %b %H:%M")
        except (ValueError, KeyError):
            when = ""
        items.append(
            f"""
<li class="feed__item">
  <span class="feed__action">{_e(entry['action'])}</span>
  <span class="feed__detail">{_e(entry.get('detail', ''))}</span>
  <span class="feed__meta">{_e(who)} · {_e(when)}</span>
</li>"""
        )
    return "\n".join(items)


def _render_service_breakdown(rows: list[dict]) -> str:
    if not rows:
        return '<p class="muted">No bookings yet.</p>'
    peak = max(row["n"] for row in rows) or 1
    return "\n".join(
        f"""
<div class="bar">
  <span class="bar__label">{_e(row['service_name'])}</span>
  <span class="bar__track">
    <span class="bar__fill" style="width:{round(row['n'] / peak * 100)}%"></span>
  </span>
  <span class="bar__value">{_e(row['n'])}</span>
</div>"""
        for row in rows
    )


def _render_status_options() -> str:
    options = ['<option value="all">All statuses</option>',
               '<option value="live">Live (pending + confirmed)</option>']
    options += [
        f'<option value="{_e(status)}">{_e(status.replace("-", " ").title())}</option>'
        for status in settings.BOOKING_STATUSES
    ]
    return "\n".join(options)


def _render_service_filter() -> str:
    options = ['<option value="all">All services</option>']
    options += [
        f'<option value="{_e(s["id"])}">{_e(s["name"])}</option>'
        for s in settings.SERVICES
    ]
    return "\n".join(options)
