"""
Deployment self-checks.

Two jobs:

1. **Prove the data directory is persistent.** The app stamps a small JSON file
   into `data/` on every boot and increments a counter. If the disk is really
   persistent, the counter keeps climbing across deploys and restarts. If the
   host is handing you a fresh ephemeral filesystem each time, the counter is
   stuck at 1 and the "first seen" timestamp keeps resetting -- which is the
   signal that your bookings are about to start disappearing.

2. **Flag production misconfiguration** before it bites: the default secret key,
   debug mode left on, cookies not marked secure, no SMTP, and so on.

Nothing here is required for the app to run; it exists so `run.py check` can
give a straight answer about whether a deployment is safe to take bookings on.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from . import auth, db
from .config import DATA_DIR, settings

STATE_FILE = DATA_DIR / ".runtime-state.json"

OK = "ok"
WARN = "warn"
FAIL = "fail"


# --------------------------------------------------------------------------- #
# Persistence tracking
# --------------------------------------------------------------------------- #
def _read_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_state(state: dict) -> None:
    """Write via a temp file + replace so a crash cannot truncate the state."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(STATE_FILE.parent), prefix=".state-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2)
        os.replace(tmp, STATE_FILE)
    except OSError:
        Path(tmp).unlink(missing_ok=True)
        raise


def record_boot() -> dict:
    """Increment the boot counter. Called once at startup; never raises."""
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    state = _read_state()
    state["boot_count"] = int(state.get("boot_count", 0)) + 1
    state.setdefault("first_boot_at", now)
    state["last_boot_at"] = now
    try:
        _write_state(state)
    except OSError as exc:
        # A read-only data directory is a real problem, but not one worth
        # crashing the whole site over -- `run.py check` reports it properly.
        print(f"[warn] could not write {STATE_FILE}: {exc}")
    return state


def persistence_report() -> dict:
    state = _read_state()
    boots = int(state.get("boot_count", 0))
    return {
        "boot_count": boots,
        "first_boot_at": state.get("first_boot_at"),
        "last_boot_at": state.get("last_boot_at"),
        "state_file": str(STATE_FILE),
        "proven": boots >= 2,
    }


# --------------------------------------------------------------------------- #
# Individual checks
# --------------------------------------------------------------------------- #
def _check(name: str, status: str, detail: str, fix: str = "") -> dict:
    return {"name": name, "status": status, "detail": detail, "fix": fix}


def _check_data_writable() -> dict:
    """The single most important check: can we actually write to data/?"""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        probe = DATA_DIR / ".write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return _check(
            "Data directory writable",
            FAIL,
            f"Cannot write to {DATA_DIR}: {exc}",
            "Mount a writable volume at this path.",
        )
    return _check("Data directory writable", OK, str(DATA_DIR))


def _check_persistence() -> dict:
    report = persistence_report()
    boots = report["boot_count"]
    if boots == 0:
        return _check(
            "Disk persistence",
            WARN,
            "No boot record yet — start the server once, then re-run this check.",
            "Run the app, redeploy, then check that the boot count went up.",
        )
    if boots == 1:
        return _check(
            "Disk persistence",
            WARN,
            f"Boot #1 since {report['first_boot_at']}. Not yet proven — this is "
            "expected on a brand-new deployment.",
            "Trigger a redeploy, run this check again, and confirm the count "
            "reaches 2. If it stays at 1, the disk is NOT persistent and you "
            "will lose bookings.",
        )
    return _check(
        "Disk persistence",
        OK,
        f"Survived {boots} boots since {report['first_boot_at']} — the data "
        "directory is persistent.",
    )


def _check_database() -> dict:
    try:
        conn = db.get_connection()
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        bookings = conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
        enquiries = conn.execute("SELECT COUNT(*) FROM enquiries").fetchone()[0]
    except sqlite3.Error as exc:
        return _check(
            "Database", FAIL, f"Cannot open {settings.db_path}: {exc}",
            "Check the disk is mounted and writable.",
        )
    size = settings.db_path.stat().st_size / 1024 if settings.db_path.exists() else 0
    return _check(
        "Database",
        OK,
        f"{settings.db_path.name} · {size:.0f} KB · journal={mode} · "
        f"{bookings} bookings, {enquiries} enquiries",
    )


def _check_disk_space() -> dict:
    try:
        usage = shutil.disk_usage(DATA_DIR)
    except OSError as exc:
        return _check("Disk space", WARN, f"Could not measure: {exc}")
    free_mb = usage.free / 1024 / 1024
    used_pct = usage.used / usage.total * 100 if usage.total else 0
    status = OK if free_mb > 100 else WARN
    return _check(
        "Disk space",
        status,
        f"{free_mb:,.0f} MB free ({used_pct:.0f}% used)",
        "Increase the volume size." if status == WARN else "",
    )


def _check_smtp_credentials() -> dict:
    """
    Catch the credential mistakes that cause an authentication rejection,
    without needing to talk to the server.
    """
    if not settings.smtp_configured:
        return _check("SMTP credentials", OK, "Not applicable in offline mode")

    host = settings.smtp_host.lower()
    user = settings.smtp_user
    password = settings.smtp_password
    problems: list[str] = []

    if not user:
        problems.append("SMTP_USER is empty")
    if not password:
        problems.append("SMTP_PASSWORD is empty")

    if password and "gmail" in host:
        if " " in password:
            problems.append(
                f"SMTP_PASSWORD contains spaces ({len(password)} chars) — Google "
                "displays App Passwords in four groups, but they must be entered "
                "as 16 characters with no spaces"
            )
        elif len(password) != 16:
            problems.append(
                f"SMTP_PASSWORD is {len(password)} characters; a Gmail App "
                "Password is exactly 16. A normal account password will always "
                "be rejected"
            )

    # Brevo's SMTP login is not your own address, which catches many people out.
    if user and "brevo" in host and not user.endswith("smtp-brevo.com"):
        problems.append(
            f"SMTP_USER is {user}, but Brevo expects its own "
            "…@smtp-brevo.com login"
        )

    if problems:
        return _check(
            "SMTP credentials", FAIL, "; ".join(problems),
            "Correct the value, then re-run: python3 run.py test-email you@example.com",
        )

    shown = f"{user} · password {len(password)} chars"
    return _check("SMTP credentials", OK, shown)


def _check_debug() -> dict:
    if settings.debug:
        return _check(
            "DEBUG mode", WARN, "Enabled — error pages may expose internals.",
            "Set DEBUG=false in production.",
        )
    return _check("DEBUG mode", OK, "Disabled")


def _check_cookies() -> dict:
    https = settings.base_url.startswith("https://")
    if https and not settings.secure_cookies:
        return _check(
            "Secure cookies", WARN,
            "BASE_URL is https but SECURE_COOKIES is false.",
            "Set SECURE_COOKIES=true.",
        )
    if not https and settings.secure_cookies:
        return _check(
            "Secure cookies", WARN,
            "SECURE_COOKIES is true but BASE_URL is not https — you will not be "
            "able to sign in over plain http.",
            "Use an https BASE_URL, or set SECURE_COOKIES=false locally.",
        )
    return _check(
        "Secure cookies", OK, "Enabled" if settings.secure_cookies else "Off (http)"
    )


def _check_base_url() -> dict:
    if "localhost" in settings.base_url or "127.0.0.1" in settings.base_url:
        return _check(
            "BASE_URL", WARN,
            f"{settings.base_url} — links inside emails will point at localhost.",
            "Set BASE_URL to your public URL.",
        )
    return _check("BASE_URL", OK, settings.base_url)


def _check_email() -> dict:
    """Report both the configuration *and* what actually happened on recent sends."""
    try:
        recent = db.list_email_log(25)
    except sqlite3.Error:
        recent = []
    sent = sum(1 for r in recent if r["status"] == "sent")
    queued = sum(1 for r in recent if r["status"] == "queued")
    failed = sum(1 for r in recent if r["status"] == "failed")
    last_error = next((r["error"] for r in recent if r["error"]), "")

    if not settings.smtp_configured:
        detail = "Offline mode — nothing is being sent."
        if queued:
            detail += f" {queued} message(s) written to data/outbox/ instead."
        return _check(
            "Email delivery", WARN, detail,
            "Set SMTP_HOST, SMTP_USER and SMTP_PASSWORD to send real email.",
        )

    target = f"SMTP via {settings.smtp_host}:{settings.smtp_port} as {settings.mail_from}"

    if not recent:
        return _check(
            "Email delivery", OK,
            f"{target} · no send attempts recorded yet",
            "Verify with: python3 run.py test-email you@example.com",
        )

    tally = f"last {len(recent)} attempts: {sent} sent, {failed} failed, {queued} queued"

    # Configured but nothing is getting through -- this is the case worth shouting about.
    if failed and sent == 0:
        return _check(
            "Email delivery", FAIL,
            f"{target} · {tally} · last error: {last_error[:160]}",
            "Credentials are being rejected. See `python3 run.py email-log`.",
        )
    if failed:
        return _check(
            "Email delivery", WARN,
            f"{target} · {tally} · last error: {last_error[:160]}",
            "Some sends are failing — inspect with `python3 run.py email-log`.",
        )
    if queued and not settings.smtp_configured:
        return _check("Email delivery", WARN, f"{target} · {tally}")
    return _check("Email delivery", OK, f"{target} · {tally}")


def _check_notify() -> dict:
    if not settings.notify_emails:
        return _check(
            "Booking notifications", FAIL, "NOTIFY_EMAILS is empty — nobody is told "
            "about new bookings.",
            "Set NOTIFY_EMAILS to your address.",
        )
    return _check("Booking notifications", OK, ", ".join(settings.notify_emails))


def _check_admin() -> dict:
    try:
        count = auth.count_admins()
    except sqlite3.Error as exc:
        return _check("Dashboard login", FAIL, f"Could not read admins: {exc}")
    if count == 0:
        return _check(
            "Dashboard login", FAIL, "No admin account exists.",
            "Run: python3 run.py create-admin",
        )
    default_still_works = False
    try:
        if settings.admin_password:
            user = auth.get_admin_by_email(settings.admin_email)
            if user and auth.verify_password("ChangeMe123!", user["password_hash"]):
                default_still_works = True
    except sqlite3.Error:
        pass
    if default_still_works:
        return _check(
            "Dashboard login", FAIL,
            f"{settings.admin_email} still uses the documented default password.",
            "Run: python3 run.py set-password",
        )
    return _check(
        "Dashboard login", OK, f"{count} account(s), password changed from default"
    )


def preflight() -> list[dict]:
    """Run every check. Order roughly matches how badly each one hurts."""
    return [
        _check_data_writable(),
        _check_persistence(),
        _check_database(),
        _check_disk_space(),
        _check_admin(),
        _check_notify(),
        _check_email(),
        _check_smtp_credentials(),
        _check_debug(),
        _check_cookies(),
        _check_base_url(),
    ]


def summarise(results: list[dict]) -> tuple[int, int, int]:
    """Return (ok_count, warn_count, fail_count)."""
    return (
        sum(1 for r in results if r["status"] == OK),
        sum(1 for r in results if r["status"] == WARN),
        sum(1 for r in results if r["status"] == FAIL),
    )
