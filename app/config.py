"""
Application configuration.

Values are read from environment variables, which can be supplied either by the
real environment or by a `.env` file sitting next to `run.py`. No third-party
dependencies are used -- the `.env` parser is intentionally small.
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATE_DIR = BASE_DIR / "templates"
DATA_DIR = BASE_DIR / "data"
OUTBOX_DIR = DATA_DIR / "outbox"


def load_dotenv(path: Path | None = None) -> None:
    """Populate os.environ from a .env file. Existing vars always win."""
    path = path or (BASE_DIR / ".env")
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Strip matching surrounding quotes.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def _env_int(key: str, default: int) -> int:
    try:
        return int(_env(key, str(default)))
    except ValueError:
        return default


def _env_bool(key: str, default: bool) -> bool:
    value = _env(key, "yes" if default else "no").lower()
    return value in {"1", "true", "yes", "on"}


class Settings:
    """Resolved settings snapshot. Instantiate *after* load_dotenv()."""

    def __init__(self) -> None:
        # --- Server ---
        self.host = _env("HOST", "0.0.0.0")
        self.port = _env_int("PORT", 8000)
        self.debug = _env_bool("DEBUG", True)
        # Public base URL used when building links inside emails.
        self.base_url = _env("BASE_URL", f"http://localhost:{self.port}").rstrip("/")

        # --- Branding ---
        self.brand_name = _env("BRAND_NAME", "Dnipro Visa Partners")
        self.brand_tagline = _env(
            "BRAND_TAGLINE", "Ukraine immigration & visa specialists"
        )
        self.contact_email = _env("CONTACT_EMAIL", "hello@dniprovisa.example")
        self.contact_phone = _env("CONTACT_PHONE", "+380 44 123 4567")
        self.office_address = _env(
            "OFFICE_ADDRESS", "12 Khreshchatyk St, Kyiv 01001, Ukraine"
        )

        # --- Database ---
        self.db_path = Path(_env("DB_PATH", str(DATA_DIR / "app.db")))

        # --- Security ---
        # Used to sign session cookies. MUST be overridden in production.
        self.secret_key = _env("SECRET_KEY", "dev-only-insecure-secret-change-me")
        self.session_ttl_hours = _env_int("SESSION_TTL_HOURS", 12)
        self.secure_cookies = _env_bool("SECURE_COOKIES", False)

        # --- Bootstrap admin (created on first run if no admins exist) ---
        self.admin_email = _env("ADMIN_EMAIL", "admin@dniprovisa.example")
        self.admin_password = _env("ADMIN_PASSWORD", "ChangeMe123!")
        self.admin_name = _env("ADMIN_NAME", "Consultant")

        # --- SMTP / email ---
        self.smtp_host = _env("SMTP_HOST")
        self.smtp_port = _env_int("SMTP_PORT", 587)
        self.smtp_user = _env("SMTP_USER")
        self.smtp_password = _env("SMTP_PASSWORD")
        self.smtp_use_tls = _env_bool("SMTP_USE_TLS", True)  # STARTTLS on port 587
        self.smtp_use_ssl = _env_bool("SMTP_USE_SSL", False)  # implicit TLS, port 465
        self.smtp_timeout = _env_int("SMTP_TIMEOUT", 20)
        self.mail_from = _env("MAIL_FROM", self.contact_email)
        self.mail_from_name = _env("MAIL_FROM_NAME", self.brand_name)
        # Where booking notifications land. Comma-separated list.
        self.notify_emails = [
            addr.strip()
            for addr in _env("NOTIFY_EMAILS", self.contact_email).split(",")
            if addr.strip()
        ]

        # --- Booking rules ---
        self.timezone_label = _env("TIMEZONE_LABEL", "EET (UTC+2)")
        self.slot_minutes = _env_int("SLOT_MINUTES", 45)
        # Lead time before the earliest bookable slot, and how far ahead we open.
        self.min_lead_hours = _env_int("MIN_LEAD_HOURS", 12)
        self.booking_window_days = _env_int("BOOKING_WINDOW_DAYS", 60)
        self.max_per_slot = _env_int("MAX_PER_SLOT", 1)

        # --- Abuse protection ---
        self.rate_limit_max = _env_int("RATE_LIMIT_MAX", 12)
        self.rate_limit_window_seconds = _env_int("RATE_LIMIT_WINDOW_SECONDS", 600)

    # Weekly opening hours: weekday index (Mon=0 .. Sun=6) -> list of start times.
    # Closed days simply map to an empty list.
    OPENING_HOURS: dict[int, list[str]] = {
        0: ["09:00", "10:00", "11:00", "13:00", "14:00", "15:00", "16:00"],
        1: ["09:00", "10:00", "11:00", "13:00", "14:00", "15:00", "16:00"],
        2: ["09:00", "10:00", "11:00", "13:00", "14:00", "15:00", "16:00"],
        3: ["09:00", "10:00", "11:00", "13:00", "14:00", "15:00", "16:00"],
        4: ["09:00", "10:00", "11:00", "13:00", "14:00", "15:00"],
        5: ["10:00", "11:00", "12:00"],
        6: [],
    }

    # Dates the office is closed regardless of weekday (YYYY-MM-DD).
    HOLIDAYS: set[str] = {
        "2026-01-01",  # New Year's Day
        "2026-01-07",  # Christmas
        "2026-03-08",  # International Women's Day
        "2026-05-01",  # Labour Day
        "2026-08-24",  # Independence Day
        "2026-12-25",  # Christmas
    }

    # Consultation services offered. `id` values are what the frontend submits.
    SERVICES: list[dict] = [
        {
            "id": "tourist-c",
            "name": "Short-stay visa (Type C)",
            "duration": 45,
            "price": "€90",
            "summary": "Tourism, family visits and short business trips up to 90 days.",
        },
        {
            "id": "long-d",
            "name": "Long-stay visa (Type D)",
            "duration": 60,
            "price": "€140",
            "summary": "The gateway to a Ukrainian temporary residence permit.",
        },
        {
            "id": "student",
            "name": "Student visa & university placement",
            "duration": 60,
            "price": "€120",
            "summary": "Invitation letters, accreditation checks and enrolment support.",
        },
        {
            "id": "work",
            "name": "Work permit & employment visa",
            "duration": 60,
            "price": "€160",
            "summary": "Employer sponsorship, permit filing and residence registration.",
        },
        {
            "id": "business",
            "name": "Business & investor route",
            "duration": 60,
            "price": "€180",
            "summary": "Company formation, investor visas and corporate relocation.",
        },
        {
            "id": "family",
            "name": "Family reunification",
            "duration": 45,
            "price": "€130",
            "summary": "Spouse, child and dependent-parent applications.",
        },
        {
            "id": "residence",
            "name": "Temporary / permanent residence",
            "duration": 60,
            "price": "€150",
            "summary": "TRP and PRP filings, renewals and status changes.",
        },
        {
            "id": "appeal",
            "name": "Refusal review & appeal",
            "duration": 45,
            "price": "€110",
            "summary": "Post-refusal analysis and a corrected re-application plan.",
        },
        {
            "id": "other",
            "name": "Something else / not sure yet",
            "duration": 30,
            "price": "Free",
            "summary": "A short orientation call to point you at the right route.",
        },
    ]

    CONSULTATION_MODES: list[dict] = [
        {"id": "video", "name": "Video call", "hint": "Zoom or Google Meet link"},
        {"id": "phone", "name": "Phone call", "hint": "We ring the number you give us"},
        {"id": "office", "name": "In person", "hint": "At our Kyiv office"},
    ]

    BOOKING_STATUSES: list[str] = [
        "pending",
        "confirmed",
        "completed",
        "cancelled",
        "no-show",
    ]

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host)

    def service_by_id(self, service_id: str) -> dict | None:
        return next((s for s in self.SERVICES if s["id"] == service_id), None)

    def mode_by_id(self, mode_id: str) -> dict | None:
        return next((m for m in self.CONSULTATION_MODES if m["id"] == mode_id), None)

    def slots_for_weekday(self, weekday: int) -> list[str]:
        return list(self.OPENING_HOURS.get(weekday, []))


load_dotenv()
settings = Settings()

DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
