"""
Admin authentication: PBKDF2 password hashing and server-side sessions.

Sessions live in the `sessions` table and are referenced by an opaque random
cookie value, so nothing sensitive is stored client-side.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from . import db
from .config import settings

PBKDF2_ITERATIONS = 240_000
SESSION_COOKIE = "vc_session"


# --------------------------------------------------------------------------- #
# Passwords
# --------------------------------------------------------------------------- #
def hash_password(password: str, *, iterations: int = PBKDF2_ITERATIONS) -> str:
    """Return `pbkdf2_sha256$iterations$salt$hash` (all hex/base-16 safe)."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), iterations
    )
    return f"pbkdf2_sha256${iterations}${salt}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations_s, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt),
            int(iterations_s),
        )
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False


def password_problems(password: str) -> list[str]:
    """Basic strength rules, surfaced to the user rather than silently enforced."""
    problems: list[str] = []
    if len(password) < 10:
        problems.append("be at least 10 characters long")
    if not any(c.isalpha() for c in password):
        problems.append("contain a letter")
    if not any(c.isdigit() for c in password):
        problems.append("contain a number")
    return problems


# --------------------------------------------------------------------------- #
# Admin users
# --------------------------------------------------------------------------- #
def create_admin(email: str, password: str, name: str = "") -> dict:
    email = email.strip().lower()
    cur = db.execute(
        "INSERT INTO admin_users (email, name, password_hash, is_active, created_at) "
        "VALUES (?,?,?,1,?)",
        (email, name.strip(), hash_password(password), db.utcnow()),
    )
    row = db.query_one("SELECT * FROM admin_users WHERE id = ?", (cur.lastrowid,))
    return dict(row)  # type: ignore[arg-type]


def get_admin_by_email(email: str) -> dict | None:
    return db.row_to_dict(
        db.query_one(
            "SELECT * FROM admin_users WHERE email = ?", (email.strip().lower(),)
        )
    )


def count_admins() -> int:
    row = db.query_one("SELECT COUNT(*) AS n FROM admin_users")
    return int(row["n"]) if row else 0


def set_admin_password(email: str, password: str) -> bool:
    cur = db.execute(
        "UPDATE admin_users SET password_hash = ? WHERE email = ?",
        (hash_password(password), email.strip().lower()),
    )
    return cur.rowcount > 0


def ensure_bootstrap_admin() -> tuple[bool, str]:
    """
    Create the first admin from env config when the table is empty.

    Returns (created, message).
    """
    if count_admins() > 0:
        return False, "Admin account already exists."
    email = settings.admin_email
    password = settings.admin_password
    if not email or not password:
        return False, "ADMIN_EMAIL / ADMIN_PASSWORD not set; no admin created."
    create_admin(email, password, settings.admin_name)
    return True, f"Bootstrap admin created for {email}."


def authenticate(email: str, password: str) -> dict | None:
    """Verify credentials. Runs a dummy hash on unknown users to level timing."""
    user = get_admin_by_email(email)
    if user is None:
        verify_password(password, hash_password("timing-equaliser", iterations=1000))
        return None
    if not user["is_active"]:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    db.execute(
        "UPDATE admin_users SET last_login_at = ? WHERE id = ?",
        (db.utcnow(), user["id"]),
    )
    return user


# --------------------------------------------------------------------------- #
# Sessions
# --------------------------------------------------------------------------- #
def create_session(user_id: int, ip_address: str = "") -> dict:
    token = secrets.token_urlsafe(40)
    csrf_token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    expires = now + timedelta(hours=settings.session_ttl_hours)
    db.execute(
        "INSERT INTO sessions (token, user_id, csrf_token, ip_address, created_at, expires_at) "
        "VALUES (?,?,?,?,?,?)",
        (token, user_id, csrf_token, ip_address, now.isoformat(), expires.isoformat()),
    )
    purge_expired_sessions()
    return {"token": token, "csrf_token": csrf_token, "expires_at": expires.isoformat()}


def get_session_user(token: str) -> dict | None:
    """Resolve a session cookie to an active admin user, or None."""
    if not token:
        return None
    row = db.query_one(
        "SELECT s.token, s.csrf_token, s.expires_at, u.id, u.email, u.name, u.is_active "
        "FROM sessions s JOIN admin_users u ON u.id = s.user_id "
        "WHERE s.token = ?",
        (token,),
    )
    if row is None:
        return None
    data = dict(row)
    if not data["is_active"]:
        return None
    try:
        expires = datetime.fromisoformat(data["expires_at"])
    except ValueError:
        return None
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= datetime.now(timezone.utc):
        destroy_session(token)
        return None
    return data


def destroy_session(token: str) -> None:
    if token:
        db.execute("DELETE FROM sessions WHERE token = ?", (token,))


def purge_expired_sessions() -> None:
    db.execute(
        "DELETE FROM sessions WHERE expires_at <= ?",
        (datetime.now(timezone.utc).isoformat(),),
    )


def check_csrf(session: dict | None, submitted: str) -> bool:
    if not session or not submitted:
        return False
    return hmac.compare_digest(str(session.get("csrf_token", "")), submitted)
