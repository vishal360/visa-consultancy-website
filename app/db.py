"""
SQLite persistence layer.

Uses only the stdlib `sqlite3` module. Connections are per-thread (the HTTP
server is threaded) and WAL mode is enabled so reads never block writes.
"""

from __future__ import annotations

import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Sequence

from .config import settings

_local = threading.local()
_init_lock = threading.Lock()
_initialised = False

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bookings (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    reference         TEXT    NOT NULL UNIQUE,
    full_name         TEXT    NOT NULL,
    email             TEXT    NOT NULL,
    phone             TEXT    NOT NULL,
    nationality       TEXT    NOT NULL DEFAULT '',
    service_id        TEXT    NOT NULL,
    service_name      TEXT    NOT NULL,
    mode_id           TEXT    NOT NULL DEFAULT 'video',
    mode_name         TEXT    NOT NULL DEFAULT 'Video call',
    slot_date         TEXT    NOT NULL,              -- YYYY-MM-DD
    slot_time         TEXT    NOT NULL,              -- HH:MM (24h)
    applicants        INTEGER NOT NULL DEFAULT 1,
    travel_timeline   TEXT    NOT NULL DEFAULT '',
    message           TEXT    NOT NULL DEFAULT '',
    status            TEXT    NOT NULL DEFAULT 'pending',
    admin_notes       TEXT    NOT NULL DEFAULT '',
    source            TEXT    NOT NULL DEFAULT 'website',
    ip_address        TEXT    NOT NULL DEFAULT '',
    user_agent        TEXT    NOT NULL DEFAULT '',
    consent           INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT    NOT NULL,
    updated_at        TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bookings_date   ON bookings (slot_date);
CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings (status);
CREATE INDEX IF NOT EXISTS idx_bookings_email  ON bookings (email);

CREATE TABLE IF NOT EXISTS enquiries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    reference   TEXT    NOT NULL UNIQUE,
    full_name   TEXT    NOT NULL,
    email       TEXT    NOT NULL,
    phone       TEXT    NOT NULL DEFAULT '',
    topic       TEXT    NOT NULL DEFAULT '',
    message     TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'new',
    ip_address  TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_enquiries_status ON enquiries (status);

CREATE TABLE IF NOT EXISTS admin_users (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    email          TEXT    NOT NULL UNIQUE,
    name           TEXT    NOT NULL DEFAULT '',
    password_hash  TEXT    NOT NULL,
    is_active      INTEGER NOT NULL DEFAULT 1,
    last_login_at  TEXT,
    created_at     TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token       TEXT    PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    csrf_token  TEXT    NOT NULL,
    ip_address  TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL,
    expires_at  TEXT    NOT NULL,
    FOREIGN KEY (user_id) REFERENCES admin_users (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions (expires_at);

CREATE TABLE IF NOT EXISTS email_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    recipients    TEXT    NOT NULL,
    subject       TEXT    NOT NULL,
    kind          TEXT    NOT NULL DEFAULT '',
    related_ref   TEXT    NOT NULL DEFAULT '',
    status        TEXT    NOT NULL,            -- sent | queued | failed
    error         TEXT    NOT NULL DEFAULT '',
    outbox_file   TEXT    NOT NULL DEFAULT '',
    created_at    TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_email_log_ref ON email_log (related_ref);

CREATE TABLE IF NOT EXISTS blocked_slots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_date   TEXT NOT NULL,
    slot_time   TEXT NOT NULL DEFAULT '',   -- empty string blocks the whole day
    reason      TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    UNIQUE (slot_date, slot_time)
);

CREATE TABLE IF NOT EXISTS activity_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER,
    action      TEXT NOT NULL,
    detail      TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);
"""


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def utcnow() -> str:
    """ISO-8601 UTC timestamp with second precision."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_reference(prefix: str = "VC") -> str:
    """Human-friendly, unambiguous reference such as VC-7QK2-M4XP."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no I/O/0/1
    block = lambda: "".join(secrets.choice(alphabet) for _ in range(4))  # noqa: E731
    return f"{prefix}-{block()}-{block()}"


def get_connection() -> sqlite3.Connection:
    """Thread-local connection, initialising the schema on first use."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(
            settings.db_path, timeout=15.0, isolation_level=None, check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 8000")
        conn.execute("PRAGMA synchronous = NORMAL")
        _local.conn = conn
    _ensure_initialised(conn)
    return conn


def _ensure_initialised(conn: sqlite3.Connection) -> None:
    global _initialised
    if _initialised:
        return
    with _init_lock:
        if _initialised:
            return
        conn.executescript(SCHEMA)

        # A partial unique index is the strongest possible guard against double
        # booking, but it only holds when a slot seats exactly one appointment.
        # With MAX_PER_SLOT > 1 we drop it and rely on the transactional count
        # check inside create_booking() instead.
        if settings.max_per_slot == 1:
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_bookings_slot_unique "
                "ON bookings (slot_date, slot_time) "
                "WHERE status IN ('pending', 'confirmed')"
            )
        else:
            conn.execute("DROP INDEX IF EXISTS idx_bookings_slot_unique")

        conn.execute(
            "INSERT INTO schema_meta (key, value) VALUES ('version', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (str(SCHEMA_VERSION),),
        )
        _initialised = True


def query(sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
    return get_connection().execute(sql, params).fetchall()


def query_one(sql: str, params: Sequence[Any] = ()) -> sqlite3.Row | None:
    return get_connection().execute(sql, params).fetchone()


def execute(sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
    return get_connection().execute(sql, params)


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict]:
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------- #
# Bookings
# --------------------------------------------------------------------------- #
LIVE_STATUSES = ("pending", "confirmed")


class SlotTakenError(Exception):
    """Raised when the requested slot was claimed by someone else."""


def slot_is_taken(slot_date: str, slot_time: str) -> bool:
    row = query_one(
        "SELECT COUNT(*) AS n FROM bookings "
        "WHERE slot_date = ? AND slot_time = ? AND status IN ('pending','confirmed')",
        (slot_date, slot_time),
    )
    return bool(row and row["n"] >= settings.max_per_slot)


def taken_slots_between(start_date: str, end_date: str) -> dict[str, set[str]]:
    """Map of date -> set of taken times across a date range."""
    rows = query(
        "SELECT slot_date, slot_time, COUNT(*) AS n FROM bookings "
        "WHERE slot_date BETWEEN ? AND ? AND status IN ('pending','confirmed') "
        "GROUP BY slot_date, slot_time",
        (start_date, end_date),
    )
    taken: dict[str, set[str]] = {}
    for row in rows:
        if row["n"] >= settings.max_per_slot:
            taken.setdefault(row["slot_date"], set()).add(row["slot_time"])
    return taken


def blocked_map(start_date: str, end_date: str) -> tuple[set[str], dict[str, set[str]]]:
    """Return (fully blocked dates, date -> blocked times)."""
    rows = query(
        "SELECT slot_date, slot_time FROM blocked_slots WHERE slot_date BETWEEN ? AND ?",
        (start_date, end_date),
    )
    full_days: set[str] = set()
    times: dict[str, set[str]] = {}
    for row in rows:
        if row["slot_time"]:
            times.setdefault(row["slot_date"], set()).add(row["slot_time"])
        else:
            full_days.add(row["slot_date"])
    return full_days, times


def create_booking(data: dict) -> dict:
    """Insert a booking, raising SlotTakenError on a slot collision."""
    now = utcnow()
    conn = get_connection()
    for _ in range(6):  # retry only for reference collisions
        reference = new_reference("VC")
        try:
            conn.execute("BEGIN IMMEDIATE")
            if slot_is_taken(data["slot_date"], data["slot_time"]):
                conn.execute("ROLLBACK")
                raise SlotTakenError(
                    "That time slot has just been booked by someone else."
                )
            cur = conn.execute(
                """
                INSERT INTO bookings (
                    reference, full_name, email, phone, nationality,
                    service_id, service_name, mode_id, mode_name,
                    slot_date, slot_time, applicants, travel_timeline, message,
                    status, source, ip_address, user_agent, consent,
                    created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    reference,
                    data["full_name"],
                    data["email"],
                    data["phone"],
                    data.get("nationality", ""),
                    data["service_id"],
                    data["service_name"],
                    data.get("mode_id", "video"),
                    data.get("mode_name", "Video call"),
                    data["slot_date"],
                    data["slot_time"],
                    int(data.get("applicants", 1)),
                    data.get("travel_timeline", ""),
                    data.get("message", ""),
                    "pending",
                    data.get("source", "website"),
                    data.get("ip_address", ""),
                    data.get("user_agent", "")[:400],
                    1 if data.get("consent") else 0,
                    now,
                    now,
                ),
            )
            conn.execute("COMMIT")
            return get_booking(cur.lastrowid)  # type: ignore[arg-type]
        except sqlite3.IntegrityError as exc:
            conn.execute("ROLLBACK")
            message = str(exc).lower()
            if "idx_bookings_slot_unique" in message or "slot_date" in message:
                raise SlotTakenError(
                    "That time slot has just been booked by someone else."
                ) from exc
            if "reference" in message:
                continue  # astronomically unlikely; try a new reference
            raise
        except SlotTakenError:
            raise
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
    raise RuntimeError("Could not allocate a unique booking reference.")


def get_booking(booking_id: int) -> dict:
    row = query_one("SELECT * FROM bookings WHERE id = ?", (booking_id,))
    if row is None:
        raise LookupError(f"Booking {booking_id} not found")
    return dict(row)


def get_booking_by_reference(reference: str) -> dict | None:
    return row_to_dict(
        query_one("SELECT * FROM bookings WHERE reference = ?", (reference.upper(),))
    )


def list_bookings(
    status: str = "",
    search: str = "",
    date_from: str = "",
    date_to: str = "",
    service_id: str = "",
    limit: int = 100,
    offset: int = 0,
    order: str = "slot",
) -> tuple[list[dict], int]:
    """Filtered, paginated booking list. Returns (rows, total_matching)."""
    where: list[str] = []
    params: list[Any] = []

    if status and status != "all":
        if status == "live":
            where.append("status IN ('pending','confirmed')")
        else:
            where.append("status = ?")
            params.append(status)
    if service_id and service_id != "all":
        where.append("service_id = ?")
        params.append(service_id)
    if date_from:
        where.append("slot_date >= ?")
        params.append(date_from)
    if date_to:
        where.append("slot_date <= ?")
        params.append(date_to)
    if search:
        needle = f"%{search.strip()}%"
        where.append(
            "(full_name LIKE ? OR email LIKE ? OR phone LIKE ? OR reference LIKE ?"
            " OR message LIKE ? OR nationality LIKE ?)"
        )
        params.extend([needle] * 6)

    clause = f"WHERE {' AND '.join(where)}" if where else ""
    total_row = query_one(f"SELECT COUNT(*) AS n FROM bookings {clause}", params)
    total = int(total_row["n"]) if total_row else 0

    order_sql = {
        "slot": "slot_date DESC, slot_time DESC",
        "slot_asc": "slot_date ASC, slot_time ASC",
        "created": "created_at DESC",
    }.get(order, "slot_date DESC, slot_time DESC")

    rows = query(
        f"SELECT * FROM bookings {clause} ORDER BY {order_sql} LIMIT ? OFFSET ?",
        [*params, int(limit), int(offset)],
    )
    return rows_to_dicts(rows), total


def update_booking_status(booking_id: int, status: str) -> dict:
    if status not in settings.BOOKING_STATUSES:
        raise ValueError(f"Unknown status: {status}")
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE bookings SET status = ?, updated_at = ? WHERE id = ?",
            (status, utcnow(), booking_id),
        )
    except sqlite3.IntegrityError as exc:
        # Re-activating a cancelled booking whose slot was re-sold.
        raise SlotTakenError(
            "Cannot reactivate: another live booking already holds that slot."
        ) from exc
    return get_booking(booking_id)


def update_booking_notes(booking_id: int, notes: str) -> dict:
    execute(
        "UPDATE bookings SET admin_notes = ?, updated_at = ? WHERE id = ?",
        (notes, utcnow(), booking_id),
    )
    return get_booking(booking_id)


def delete_booking(booking_id: int) -> None:
    execute("DELETE FROM bookings WHERE id = ?", (booking_id,))


# --------------------------------------------------------------------------- #
# Enquiries
# --------------------------------------------------------------------------- #
def create_enquiry(data: dict) -> dict:
    now = utcnow()
    reference = new_reference("EN")
    cur = execute(
        """
        INSERT INTO enquiries (
            reference, full_name, email, phone, topic, message,
            status, ip_address, created_at, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?)
        """,
        (
            reference,
            data["full_name"],
            data["email"],
            data.get("phone", ""),
            data.get("topic", ""),
            data["message"],
            "new",
            data.get("ip_address", ""),
            now,
            now,
        ),
    )
    row = query_one("SELECT * FROM enquiries WHERE id = ?", (cur.lastrowid,))
    return dict(row)  # type: ignore[arg-type]


def list_enquiries(
    status: str = "", search: str = "", limit: int = 100, offset: int = 0
) -> tuple[list[dict], int]:
    where: list[str] = []
    params: list[Any] = []
    if status and status != "all":
        where.append("status = ?")
        params.append(status)
    if search:
        needle = f"%{search.strip()}%"
        where.append(
            "(full_name LIKE ? OR email LIKE ? OR message LIKE ? OR reference LIKE ?)"
        )
        params.extend([needle] * 4)
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    total_row = query_one(f"SELECT COUNT(*) AS n FROM enquiries {clause}", params)
    total = int(total_row["n"]) if total_row else 0
    rows = query(
        f"SELECT * FROM enquiries {clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        [*params, int(limit), int(offset)],
    )
    return rows_to_dicts(rows), total


def update_enquiry_status(enquiry_id: int, status: str) -> dict | None:
    execute(
        "UPDATE enquiries SET status = ?, updated_at = ? WHERE id = ?",
        (status, utcnow(), enquiry_id),
    )
    return row_to_dict(query_one("SELECT * FROM enquiries WHERE id = ?", (enquiry_id,)))


# --------------------------------------------------------------------------- #
# Blocked slots
# --------------------------------------------------------------------------- #
def block_slot(slot_date: str, slot_time: str = "", reason: str = "") -> None:
    execute(
        "INSERT INTO blocked_slots (slot_date, slot_time, reason, created_at) "
        "VALUES (?,?,?,?) ON CONFLICT(slot_date, slot_time) DO UPDATE SET reason = excluded.reason",
        (slot_date, slot_time, reason, utcnow()),
    )


def unblock_slot(slot_date: str, slot_time: str = "") -> None:
    execute(
        "DELETE FROM blocked_slots WHERE slot_date = ? AND slot_time = ?",
        (slot_date, slot_time),
    )


def list_blocked(limit: int = 200) -> list[dict]:
    return rows_to_dicts(
        query(
            "SELECT * FROM blocked_slots ORDER BY slot_date ASC, slot_time ASC LIMIT ?",
            (limit,),
        )
    )


# --------------------------------------------------------------------------- #
# Email log
# --------------------------------------------------------------------------- #
def log_email(
    recipients: Sequence[str],
    subject: str,
    status: str,
    kind: str = "",
    related_ref: str = "",
    error: str = "",
    outbox_file: str = "",
) -> None:
    execute(
        "INSERT INTO email_log (recipients, subject, kind, related_ref, status, error, outbox_file, created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (
            ", ".join(recipients),
            subject,
            kind,
            related_ref,
            status,
            error[:1000],
            outbox_file,
            utcnow(),
        ),
    )


def list_email_log(limit: int = 50, related_ref: str = "") -> list[dict]:
    if related_ref:
        return rows_to_dicts(
            query(
                "SELECT * FROM email_log WHERE related_ref = ? ORDER BY id DESC LIMIT ?",
                (related_ref, limit),
            )
        )
    return rows_to_dicts(
        query("SELECT * FROM email_log ORDER BY id DESC LIMIT ?", (limit,))
    )


# --------------------------------------------------------------------------- #
# Activity log
# --------------------------------------------------------------------------- #
def log_activity(user_id: int | None, action: str, detail: str = "") -> None:
    execute(
        "INSERT INTO activity_log (user_id, action, detail, created_at) VALUES (?,?,?,?)",
        (user_id, action, detail[:500], utcnow()),
    )


def list_activity(limit: int = 40) -> list[dict]:
    return rows_to_dicts(
        query(
            "SELECT a.*, u.name AS user_name, u.email AS user_email "
            "FROM activity_log a LEFT JOIN admin_users u ON u.id = a.user_id "
            "ORDER BY a.id DESC LIMIT ?",
            (limit,),
        )
    )


# --------------------------------------------------------------------------- #
# Dashboard statistics
# --------------------------------------------------------------------------- #
def dashboard_stats() -> dict:
    today = datetime.now(timezone.utc).date().isoformat()
    week_ago = (datetime.now(timezone.utc).date() - timedelta(days=7)).isoformat()
    month_ahead = (datetime.now(timezone.utc).date() + timedelta(days=30)).isoformat()

    def scalar(sql: str, params: Sequence[Any] = ()) -> int:
        row = query_one(sql, params)
        return int(row["n"]) if row else 0

    by_status = {
        row["status"]: int(row["n"])
        for row in query("SELECT status, COUNT(*) AS n FROM bookings GROUP BY status")
    }
    by_service = rows_to_dicts(
        query(
            "SELECT service_name, COUNT(*) AS n FROM bookings "
            "GROUP BY service_name ORDER BY n DESC LIMIT 8"
        )
    )
    daily = rows_to_dicts(
        query(
            "SELECT slot_date, COUNT(*) AS n FROM bookings "
            "WHERE slot_date BETWEEN ? AND ? GROUP BY slot_date ORDER BY slot_date",
            (today, month_ahead),
        )
    )
    return {
        "total_bookings": scalar("SELECT COUNT(*) AS n FROM bookings"),
        "pending": by_status.get("pending", 0),
        "confirmed": by_status.get("confirmed", 0),
        "completed": by_status.get("completed", 0),
        "cancelled": by_status.get("cancelled", 0),
        "no_show": by_status.get("no-show", 0),
        "today": scalar(
            "SELECT COUNT(*) AS n FROM bookings WHERE slot_date = ? "
            "AND status IN ('pending','confirmed')",
            (today,),
        ),
        "upcoming": scalar(
            "SELECT COUNT(*) AS n FROM bookings WHERE slot_date >= ? "
            "AND status IN ('pending','confirmed')",
            (today,),
        ),
        "new_last_7_days": scalar(
            "SELECT COUNT(*) AS n FROM bookings WHERE date(created_at) >= ?",
            (week_ago,),
        ),
        "new_enquiries": scalar(
            "SELECT COUNT(*) AS n FROM enquiries WHERE status = 'new'"
        ),
        "total_enquiries": scalar("SELECT COUNT(*) AS n FROM enquiries"),
        "emails_sent": scalar("SELECT COUNT(*) AS n FROM email_log WHERE status = 'sent'"),
        "emails_queued": scalar(
            "SELECT COUNT(*) AS n FROM email_log WHERE status = 'queued'"
        ),
        "emails_failed": scalar(
            "SELECT COUNT(*) AS n FROM email_log WHERE status = 'failed'"
        ),
        "by_status": by_status,
        "by_service": by_service,
        "daily": daily,
    }


def export_bookings_csv(**filters: Any) -> str:
    """CSV dump of the bookings matching the given list_bookings() filters."""
    import csv
    import io

    filters.setdefault("limit", 100000)
    rows, _ = list_bookings(**filters)
    columns = [
        "reference",
        "created_at",
        "slot_date",
        "slot_time",
        "status",
        "full_name",
        "email",
        "phone",
        "nationality",
        "service_name",
        "mode_name",
        "applicants",
        "travel_timeline",
        "message",
        "admin_notes",
        "source",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer, fieldnames=columns, extrasaction="ignore", lineterminator="\r\n"
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in columns})
    return buffer.getvalue()
