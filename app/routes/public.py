"""
Public-facing routes: the marketing site and the booking / enquiry API.
"""

from __future__ import annotations

from datetime import datetime

from .. import db, mailer, scheduling, validation
from ..config import settings
from ..content import FAQS, PROCESS_STEPS, TESTIMONIALS, TRUST_BADGES, VISA_TYPES, WIZARD
from ..web import (
    Request,
    Response,
    error_response,
    html_response,
    json_for_script,
    json_response,
    redirect,
    render,
    submission_limiter,
)


def register(router) -> None:
    router.add("GET", "/", home)
    router.add("GET", "/thanks", thanks)
    router.add("GET", "/privacy", privacy)

    router.add("GET", "/api/config", api_config)
    router.add("GET", "/api/availability", api_availability)
    router.add("GET", "/api/availability/month", api_availability_month)
    router.add("POST", "/api/bookings", api_create_booking)
    router.add("GET", "/api/bookings/<reference>", api_lookup_booking)
    router.add("POST", "/api/enquiries", api_create_enquiry)


# --------------------------------------------------------------------------- #
# Shared template context
# --------------------------------------------------------------------------- #
def _boot_payload() -> dict:
    """Everything the frontend JS needs, embedded on first paint."""
    return {
        "services": [
            {
                "id": s["id"],
                "name": s["name"],
                "duration": s["duration"],
                "summary": s["summary"],
            }
            for s in settings.SERVICES
        ],
        "modes": settings.CONSULTATION_MODES,
        "timelines": [
            {"id": key, "label": label}
            for key, label in validation.TRAVEL_TIMELINES.items()
        ],
        "topics": [
            {"id": key, "label": label}
            for key, label in validation.ENQUIRY_TOPICS.items()
        ],
        "wizard": WIZARD,
        "timezone": settings.timezone_label,
        "slotMinutes": settings.slot_minutes,
        "minLeadHours": settings.min_lead_hours,
        "bookingWindowDays": settings.booking_window_days,
        "brand": settings.brand_name,
    }


def _page_context() -> dict:
    year = datetime.now().year
    return {
        "brand_name": settings.brand_name,
        "brand_tagline": settings.brand_tagline,
        "contact_email": settings.contact_email,
        "contact_phone": settings.contact_phone,
        "contact_phone_href": "".join(
            ch for ch in settings.contact_phone if ch.isdigit() or ch == "+"
        ),
        "timezone_label": settings.timezone_label,
        "year": year,
    }


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #
def home(request: Request) -> Response:
    context = _page_context()

    markup = render(
        "index.html",
        **context,
        raw_boot=json_for_script(_boot_payload()),
        raw_visa_cards=_render_visa_cards(),
        raw_process_steps=_render_process_steps(),
        raw_trust_badges=_render_trust_badges(),
        raw_testimonials=_render_testimonials(),
        raw_faqs=_render_faqs(),
        raw_service_options=_render_service_options(),
        raw_mode_options=_render_mode_options(),
        raw_timeline_options=_render_timeline_options(),
        raw_topic_options=_render_topic_options(),
        raw_opening_hours=_render_opening_hours(),
    )
    return html_response(markup)


def thanks(request: Request) -> Response:
    reference = request.get("ref", "")
    booking = db.get_booking_by_reference(reference) if reference else None
    context = _page_context()
    if booking:
        details = (
            f"{mailer.pretty_date(booking['slot_date'])} at "
            f"{booking['slot_time']} ({settings.timezone_label})"
        )
        summary = f"{booking['service_name']} — {booking['mode_name']}"
    else:
        details = ""
        summary = ""
    return html_response(
        render(
            "thanks.html",
            **context,
            reference=reference or "—",
            details=details,
            summary=summary,
            client_email=booking["email"] if booking else "",
        )
    )


def privacy(request: Request) -> Response:
    return html_response(render("privacy.html", **_page_context()))


# --------------------------------------------------------------------------- #
# API: configuration & availability
# --------------------------------------------------------------------------- #
def api_config(request: Request) -> Response:
    return json_response({"ok": True, **_boot_payload()})


def api_availability(request: Request) -> Response:
    """
    Availability for a single day: /api/availability?date=YYYY-MM-DD
    Without a date, returns the next few days that have open slots.
    """
    date_param = request.get("date")
    if not date_param:
        return json_response(
            {
                "ok": True,
                "mode": "next",
                "days": scheduling.next_available_days(
                    max(1, min(request.get_int("limit", 5), 14))
                ),
            }
        )

    day = scheduling.parse_date(date_param)
    if day is None:
        return error_response("Use a date formatted as YYYY-MM-DD.", 400)

    window_start, window_end = scheduling.booking_window()
    if not (window_start <= day <= window_end):
        return json_response(
            {
                "ok": True,
                "mode": "day",
                "day": {
                    "date": day.isoformat(),
                    "pretty": day.strftime("%A %d %B %Y"),
                    "is_open": False,
                    "out_of_window": True,
                    "slots": [],
                    "open_count": 0,
                    "timezone": settings.timezone_label,
                },
            }
        )

    return json_response(
        {"ok": True, "mode": "day", "day": scheduling.day_availability(day)}
    )


def api_availability_month(request: Request) -> Response:
    """Calendar grid data: /api/availability/month?year=2026&month=9"""
    now = datetime.now()
    year = request.get_int("year", now.year)
    month = request.get_int("month", now.month)
    if not (2020 <= year <= 2100) or not (1 <= month <= 12):
        return error_response("Invalid year or month.", 400)
    return json_response({"ok": True, **scheduling.month_availability(year, month)})


# --------------------------------------------------------------------------- #
# API: bookings
# --------------------------------------------------------------------------- #
def _slot_conflict_response(message: str, slot_date: str) -> Response:
    """409 plus the current state of that day, so the UI can refresh in place."""
    day = scheduling.parse_date(slot_date)
    return json_response(
        {
            "ok": False,
            "error": message,
            "errors": {"slot_time": message},
            "day": scheduling.day_availability(day) if day else None,
        },
        status=409,
    )


def api_create_booking(request: Request) -> Response:
    payload = request.payload()

    allowed, retry_after = submission_limiter.check(f"booking:{request.client_ip}")
    if not allowed:
        return error_response(
            "Too many submissions from your connection. Please try again shortly.",
            429,
            retry_after=retry_after,
        )

    # Silently accept bot submissions so they get no feedback signal.
    if validation.looks_like_spam(payload):
        return json_response(
            {"ok": True, "reference": db.new_reference("VC"), "spam": True}
        )

    data, errors = validation.validate_booking(payload)
    if errors:
        conflict = errors.pop("_conflict", "")
        if conflict and len(errors) == 1 and "slot_time" in errors:
            # The slot was open when the form loaded but is gone now. Answer 409
            # with refreshed availability so the UI can re-render immediately.
            return _slot_conflict_response(
                errors["slot_time"], str(data.get("slot_date", ""))
            )
        return json_response(
            {
                "ok": False,
                "error": "Please check the highlighted fields.",
                "errors": errors,
            },
            status=422,
        )

    data["ip_address"] = request.client_ip
    data["user_agent"] = request.headers.get("User-Agent", "")
    data["source"] = "website"

    try:
        booking = db.create_booking(data)
    except db.SlotTakenError as exc:
        # Lost the race between validation and the insert.
        return _slot_conflict_response(str(exc), str(data.get("slot_date", "")))

    # Emails are dispatched on background threads; never blocks the response.
    mailer.notify_admin_new_booking(booking)
    mailer.send_client_booking_confirmation(booking)
    db.log_activity(None, "booking.created", f"{booking['reference']} via website")

    return json_response(
        {
            "ok": True,
            "reference": booking["reference"],
            "booking": {
                "reference": booking["reference"],
                "full_name": booking["full_name"],
                "email": booking["email"],
                "service_name": booking["service_name"],
                "mode_name": booking["mode_name"],
                "slot_date": booking["slot_date"],
                "slot_time": booking["slot_time"],
                "pretty_date": mailer.pretty_date(booking["slot_date"]),
                "timezone": settings.timezone_label,
                "status": booking["status"],
            },
            "redirect": f"/thanks?ref={booking['reference']}",
        },
        status=201,
    )


def api_lookup_booking(request: Request) -> Response:
    """Let a visitor check their own booking by reference."""
    reference = request.params.get("reference", "").strip().upper()
    allowed, retry_after = submission_limiter.check(f"lookup:{request.client_ip}")
    if not allowed:
        return error_response("Too many lookups. Try again shortly.", 429,
                             retry_after=retry_after)

    booking = db.get_booking_by_reference(reference)
    if booking is None:
        return error_response("No booking found with that reference.", 404)

    # Only non-sensitive fields, and the email is masked.
    email = booking["email"]
    name, _, domain = email.partition("@")
    masked = f"{name[:2]}{'*' * max(len(name) - 2, 1)}@{domain}" if domain else ""
    return json_response(
        {
            "ok": True,
            "booking": {
                "reference": booking["reference"],
                "status": booking["status"],
                "slot_date": booking["slot_date"],
                "slot_time": booking["slot_time"],
                "pretty_date": mailer.pretty_date(booking["slot_date"]),
                "service_name": booking["service_name"],
                "mode_name": booking["mode_name"],
                "email_masked": masked,
                "timezone": settings.timezone_label,
            },
        }
    )


# --------------------------------------------------------------------------- #
# API: enquiries
# --------------------------------------------------------------------------- #
def api_create_enquiry(request: Request) -> Response:
    payload = request.payload()

    allowed, retry_after = submission_limiter.check(f"enquiry:{request.client_ip}")
    if not allowed:
        return error_response(
            "Too many messages from your connection. Please try again shortly.",
            429,
            retry_after=retry_after,
        )

    if validation.looks_like_spam(payload):
        return json_response({"ok": True, "spam": True})

    data, errors = validation.validate_enquiry(payload)
    if errors:
        return json_response(
            {
                "ok": False,
                "error": "Please check the highlighted fields.",
                "errors": errors,
            },
            status=422,
        )

    data["ip_address"] = request.client_ip
    enquiry = db.create_enquiry(data)

    mailer.notify_admin_new_enquiry(enquiry)
    mailer.send_client_enquiry_ack(enquiry)
    db.log_activity(None, "enquiry.created", enquiry["reference"])

    return json_response(
        {
            "ok": True,
            "reference": enquiry["reference"],
            "message": "Thanks — we'll reply within one business day.",
        },
        status=201,
    )


# --------------------------------------------------------------------------- #
# Server-rendered content fragments
# --------------------------------------------------------------------------- #
def _e(value: object) -> str:
    import html as _html

    return _html.escape("" if value is None else str(value), quote=True)


def _render_visa_cards() -> str:
    cards = []
    for index, visa in enumerate(VISA_TYPES):
        bullets = "".join(f"<li>{_e(item)}</li>" for item in visa["highlights"])
        docs = "".join(f"<li>{_e(item)}</li>" for item in visa["documents"])
        cards.append(
            f"""
<article class="visa-card reveal" data-visa="{_e(visa['id'])}" style="--delay:{index * 60}ms">
  <div class="visa-card__inner">
    <header class="visa-card__head">
      <span class="visa-card__icon" aria-hidden="true">{visa['icon']}</span>
      <div>
        <h3 class="visa-card__title">{_e(visa['name'])}</h3>
        <p class="visa-card__type">{_e(visa['type_label'])}</p>
      </div>
    </header>
    <p class="visa-card__summary">{_e(visa['summary'])}</p>
    <dl class="visa-card__meta">
      <div><dt>Stay</dt><dd>{_e(visa['stay'])}</dd></div>
      <div><dt>Processing</dt><dd>{_e(visa['processing'])}</dd></div>
      <div><dt>Entries</dt><dd>{_e(visa['entries'])}</dd></div>
    </dl>
    <ul class="visa-card__list">{bullets}</ul>
    <details class="visa-card__docs">
      <summary>Documents you'll need <span aria-hidden="true">＋</span></summary>
      <ul>{docs}</ul>
    </details>
    <button class="btn btn--ghost visa-card__cta" type="button"
            data-book-service="{_e(visa['service_id'])}">
      Book this consultation
    </button>
  </div>
</article>"""
        )
    return "\n".join(cards)


def _render_process_steps() -> str:
    steps = []
    for index, step in enumerate(PROCESS_STEPS, start=1):
        steps.append(
            f"""
<li class="step reveal" style="--delay:{index * 80}ms">
  <div class="step__marker"><span>{index}</span></div>
  <div class="step__body">
    <h3 class="step__title">{_e(step['title'])}</h3>
    <p class="step__text">{_e(step['text'])}</p>
    <span class="step__meta">{_e(step['duration'])}</span>
  </div>
</li>"""
        )
    return "\n".join(steps)


def _render_trust_badges() -> str:
    return "\n".join(
        f"""
<li><span aria-hidden="true">{badge['icon']}</span> {_e(badge['label'])}</li>"""
        for badge in TRUST_BADGES
    )


def _render_testimonials() -> str:
    return "\n".join(
        f"""
<article class="quote" role="group" aria-roledescription="slide"
         aria-label="Testimonial {index + 1} of {len(TESTIMONIALS)}">
  <p class="quote__stars" aria-label="{item['rating']} out of 5 stars">
    {'★' * item['rating']}{'☆' * (5 - item['rating'])}
  </p>
  <blockquote class="quote__text">{_e(item['text'])}</blockquote>
  <footer class="quote__meta">
    <span class="quote__avatar" aria-hidden="true">{_e(item['initials'])}</span>
    <span>
      <strong>{_e(item['name'])}</strong>
      <small>{_e(item['detail'])}</small>
    </span>
  </footer>
</article>"""
        for index, item in enumerate(TESTIMONIALS)
    )


def _render_faqs() -> str:
    return "\n".join(
        f"""
<details class="faq reveal" style="--delay:{index * 50}ms">
  <summary>
    <span>{_e(item['question'])}</span>
    <span class="faq__sign" aria-hidden="true"></span>
  </summary>
  <div class="faq__body"><p>{_e(item['answer'])}</p></div>
</details>"""
        for index, item in enumerate(FAQS)
    )


def _render_service_options() -> str:
    return "\n".join(
        f"""
<label class="option-card">
  <input type="radio" name="service_id" value="{_e(service['id'])}">
  <span class="option-card__body">
    <span class="option-card__title">{_e(service['name'])}</span>
    <span class="option-card__summary">{_e(service['summary'])}</span>
    <span class="option-card__meta">
      <span>{service['duration']} min</span><span>Fee quoted on the call</span>
    </span>
  </span>
</label>"""
        for service in settings.SERVICES
    )


def _render_mode_options() -> str:
    icons = {"video": "🎥", "phone": "📞"}
    return "\n".join(
        f"""
<label class="pill-option">
  <input type="radio" name="mode_id" value="{_e(mode['id'])}"
         {'checked' if mode['id'] == 'video' else ''}>
  <span>
    <span class="pill-option__icon" aria-hidden="true">{icons.get(mode['id'], '•')}</span>
    <strong>{_e(mode['name'])}</strong>
    <small>{_e(mode['hint'])}</small>
  </span>
</label>"""
        for mode in settings.CONSULTATION_MODES
    )


def _render_timeline_options() -> str:
    options = ['<option value="">Select a timeline…</option>']
    options += [
        f'<option value="{_e(key)}">{_e(label)}</option>'
        for key, label in validation.TRAVEL_TIMELINES.items()
    ]
    return "\n".join(options)


def _render_topic_options() -> str:
    options = ['<option value="">What is your question about?</option>']
    options += [
        f'<option value="{_e(key)}">{_e(label)}</option>'
        for key, label in validation.ENQUIRY_TOPICS.items()
    ]
    return "\n".join(options)


def _render_opening_hours() -> str:
    return "\n".join(
        f"""
<div class="hours__row{'' if row['open'] else ' hours__row--closed'}">
  <span>{_e(row['day'])}</span><span>{_e(row['hours'])}</span>
</div>"""
        for row in scheduling.opening_hours_summary()
    )
