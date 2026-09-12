"""
Input validation for public form submissions.

Every validator returns cleaned data plus a field->message error map, so the
frontend can highlight the exact input that needs attention. Server-side rules
mirror the client-side ones; the client is treated purely as a convenience.
"""

from __future__ import annotations

import re

from .config import settings
from .scheduling import parse_date, slot_is_bookable

# Deliberately pragmatic rather than RFC-complete: catches real typos without
# rejecting unusual but valid addresses.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")
# Digits, spaces and the usual punctuation; must hold at least 7 digits.
PHONE_ALLOWED_RE = re.compile(r"^[+()\-.\s0-9]+$")
NAME_RE = re.compile(r"^[^\d<>{}@]+$")

MAX_LENGTHS = {
    "full_name": 120,
    "email": 200,
    "phone": 40,
    "nationality": 80,
    "message": 4000,
    "travel_timeline": 60,
    "topic": 120,
}

TRAVEL_TIMELINES = {
    "asap": "As soon as possible",
    "1-3-months": "Within 1–3 months",
    "3-6-months": "Within 3–6 months",
    "6-plus-months": "More than 6 months away",
    "researching": "Just researching",
}

# Reasons a slot is unavailable *right now* even though it was offered earlier.
# These represent contention rather than bad input, so they map to HTTP 409.
SLOT_CONFLICT_CODES = {"taken", "blocked"}

ENQUIRY_TOPICS = {
    "general": "General question",
    "documents": "Document requirements",
    "timelines": "Processing times",
    "pricing": "Fees and pricing",
    "refusal": "Previous refusal",
    "partnership": "Business / partnership",
}


def _clean(value: object, limit: int) -> str:
    """Trim, collapse whitespace runs, strip control characters, truncate."""
    text = "" if value is None else str(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(ch for ch in text if ch == "\n" or ch == "\t" or ch >= " ")
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:limit]


def validate_name(value: str, errors: dict, field: str = "full_name") -> str:
    name = _clean(value, MAX_LENGTHS["full_name"])
    if len(name) < 2:
        errors[field] = "Please enter your full name."
    elif not NAME_RE.match(name):
        errors[field] = "Please use letters only, without digits or symbols."
    return name


def validate_email(value: str, errors: dict, field: str = "email") -> str:
    email = _clean(value, MAX_LENGTHS["email"]).lower()
    if not email:
        errors[field] = "Please enter your email address."
    elif not EMAIL_RE.match(email):
        errors[field] = "That email address does not look right."
    return email


def validate_phone(value: str, errors: dict, required: bool = True,
                   field: str = "phone") -> str:
    phone = _clean(value, MAX_LENGTHS["phone"])
    if not phone:
        if required:
            errors[field] = "Please enter a phone number we can reach you on."
        return phone
    if not PHONE_ALLOWED_RE.match(phone):
        errors[field] = "Use digits, spaces and + ( ) - only."
    elif not 7 <= sum(ch.isdigit() for ch in phone) <= 15:
        errors[field] = "Please include the full number with country code."
    return phone


def validate_message(value: str, errors: dict, required: bool = False,
                     min_length: int = 10, field: str = "message") -> str:
    message = _clean(value, MAX_LENGTHS["message"])
    if required:
        if not message:
            errors[field] = "Please tell us how we can help."
        elif len(message) < min_length:
            errors[field] = f"Please give us a little more detail ({min_length}+ characters)."
    return message


def looks_like_spam(payload: dict) -> bool:
    """
    Honeypot check.

    The form ships a hidden `website` field that real users never see. Anything
    filling it in is a bot.
    """
    return bool(str(payload.get("website", "")).strip())


# --------------------------------------------------------------------------- #
# Booking
# --------------------------------------------------------------------------- #
def validate_booking(payload: dict) -> tuple[dict, dict]:
    """Return (cleaned_booking_data, errors)."""
    errors: dict[str, str] = {}
    data: dict[str, object] = {}

    data["full_name"] = validate_name(payload.get("full_name", ""), errors)
    data["email"] = validate_email(payload.get("email", ""), errors)
    data["phone"] = validate_phone(payload.get("phone", ""), errors)
    data["nationality"] = _clean(
        payload.get("nationality", ""), MAX_LENGTHS["nationality"]
    )
    data["message"] = validate_message(payload.get("message", ""), errors)

    # --- service ---
    service_id = _clean(payload.get("service_id", ""), 40)
    service = settings.service_by_id(service_id)
    if service is None:
        errors["service_id"] = "Please choose the service you need."
        data["service_id"] = ""
        data["service_name"] = ""
    else:
        data["service_id"] = service["id"]
        data["service_name"] = service["name"]

    # --- consultation mode ---
    mode_id = _clean(payload.get("mode_id", "video"), 20) or "video"
    mode = settings.mode_by_id(mode_id)
    if mode is None:
        errors["mode_id"] = "Please choose how you would like to meet."
        data["mode_id"] = "video"
        data["mode_name"] = "Video call"
    else:
        data["mode_id"] = mode["id"]
        data["mode_name"] = mode["name"]

    # --- applicants ---
    try:
        applicants = int(str(payload.get("applicants", 1)).strip() or 1)
    except ValueError:
        applicants = 1
    if not 1 <= applicants <= 20:
        errors["applicants"] = "Enter a number of applicants between 1 and 20."
        applicants = max(1, min(applicants, 20))
    data["applicants"] = applicants

    # --- travel timeline ---
    timeline_key = _clean(payload.get("travel_timeline", ""), 40)
    if timeline_key and timeline_key not in TRAVEL_TIMELINES:
        errors["travel_timeline"] = "Please pick one of the listed timelines."
        data["travel_timeline"] = ""
    else:
        data["travel_timeline"] = TRAVEL_TIMELINES.get(timeline_key, "")

    # --- slot ---
    slot_date_raw = _clean(payload.get("slot_date", ""), 10)
    slot_time_raw = _clean(payload.get("slot_time", ""), 5)
    day = parse_date(slot_date_raw)
    if day is None:
        errors["slot_date"] = "Please choose a date for your consultation."
    if not slot_time_raw:
        errors["slot_time"] = "Please choose a time slot."
    if day is not None and slot_time_raw:
        ok, reason, code = slot_is_bookable(day, slot_time_raw)
        if not ok:
            errors["slot_time"] = reason
            # Surfaced separately so the route can answer 409 (and hand back
            # fresh availability) when the slot was simply claimed first.
            if code in SLOT_CONFLICT_CODES:
                errors["_conflict"] = code
    data["slot_date"] = slot_date_raw
    data["slot_time"] = slot_time_raw

    # --- consent ---
    consent = str(payload.get("consent", "")).strip().lower()
    data["consent"] = consent in {"true", "1", "on", "yes"}
    if not data["consent"]:
        errors["consent"] = "Please agree to us storing your details to contact you."

    return data, errors


# --------------------------------------------------------------------------- #
# Enquiry
# --------------------------------------------------------------------------- #
def validate_enquiry(payload: dict) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    data: dict[str, object] = {}

    data["full_name"] = validate_name(payload.get("full_name", ""), errors)
    data["email"] = validate_email(payload.get("email", ""), errors)
    data["phone"] = validate_phone(payload.get("phone", ""), errors, required=False)
    data["message"] = validate_message(
        payload.get("message", ""), errors, required=True, min_length=10
    )

    topic_key = _clean(payload.get("topic", ""), 40)
    if topic_key and topic_key not in ENQUIRY_TOPICS:
        errors["topic"] = "Please pick one of the listed topics."
        data["topic"] = ""
    else:
        data["topic"] = ENQUIRY_TOPICS.get(topic_key, "General question")

    return data, errors
