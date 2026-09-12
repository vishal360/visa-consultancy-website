#!/usr/bin/env python3
"""
Entry point and management CLI.

    python3 run.py                      start the web server
    python3 run.py serve                same thing, explicitly
    python3 run.py create-admin         add a dashboard user
    python3 run.py set-password         change a user's password
    python3 run.py list-admins          show dashboard users
    python3 run.py test-email [addr]    verify your email configuration
    python3 run.py seed-demo [n]        insert sample bookings to explore the UI
    python3 run.py stats                print a summary of the database
    python3 run.py reset --yes          delete all data and start fresh

Requires only the Python standard library (3.10+).
"""

from __future__ import annotations

import getpass
import random
import sys
from datetime import timedelta

from app import auth, db, mailer, scheduling
from app.config import settings
from app.main import create_app
from app.web import run_server


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
def cmd_serve(_args: list[str]) -> int:
    run_server(create_app())
    return 0


def _prompt_password(confirm: bool = True) -> str | None:
    password = getpass.getpass("Password: ")
    problems = auth.password_problems(password)
    if problems:
        print("Password must " + ", ".join(problems) + ".")
        return None
    if confirm and password != getpass.getpass("Confirm password: "):
        print("Passwords do not match.")
        return None
    return password


def cmd_create_admin(args: list[str]) -> int:
    db.get_connection()
    email = (args[0] if args else input("Email: ")).strip().lower()
    if "@" not in email:
        print("That does not look like an email address.")
        return 1
    if auth.get_admin_by_email(email):
        print(f"An admin with {email} already exists. Use set-password instead.")
        return 1
    name = input("Display name: ").strip()
    password = _prompt_password()
    if password is None:
        return 1
    auth.create_admin(email, password, name)
    print(f"Created dashboard user {email}.")
    return 0


def cmd_set_password(args: list[str]) -> int:
    db.get_connection()
    email = (args[0] if args else input("Email: ")).strip().lower()
    if not auth.get_admin_by_email(email):
        print(f"No admin found with email {email}.")
        return 1
    password = _prompt_password()
    if password is None:
        return 1
    auth.set_admin_password(email, password)
    # Force a re-login everywhere.
    db.execute(
        "DELETE FROM sessions WHERE user_id = "
        "(SELECT id FROM admin_users WHERE email = ?)",
        (email,),
    )
    print(f"Password updated for {email}. Existing sessions were signed out.")
    return 0


def cmd_list_admins(_args: list[str]) -> int:
    db.get_connection()
    rows = db.query("SELECT email, name, is_active, last_login_at FROM admin_users")
    if not rows:
        print("No dashboard users yet. Run: python3 run.py create-admin")
        return 0
    print(f"{'EMAIL':<34} {'NAME':<20} {'ACTIVE':<7} LAST LOGIN")
    for row in rows:
        print(
            f"{row['email']:<34} {(row['name'] or '—'):<20} "
            f"{('yes' if row['is_active'] else 'no'):<7} {row['last_login_at'] or 'never'}"
        )
    return 0


def cmd_test_email(args: list[str]) -> int:
    db.get_connection()
    recipient = args[0] if args else settings.notify_emails[0]
    print(f"Mode: {'SMTP' if settings.smtp_configured else 'offline (outbox)'}")
    if settings.smtp_configured:
        print(f"Host: {settings.smtp_host}:{settings.smtp_port}")
    print(f"Sending test message to {recipient} …")
    result = mailer.send_test_email(recipient)
    if result["status"] == "sent":
        print("Delivered. Check the inbox (and the spam folder).")
    elif result["status"] == "queued":
        print(f"Written to {result.get('outbox_file')}")
        print("Set SMTP_HOST in .env to deliver real email.")
    else:
        print(f"FAILED: {result.get('error')}")
        return 1
    return 0


DEMO_NAMES = [
    ("Priya Sharma", "priya.sharma@example.in", "+91 98200 55014", "Indian"),
    ("Rohit Mehta", "rohit.mehta@example.in", "+91 98330 55127", "Indian"),
    ("Aisha Khan", "aisha.khan@example.in", "+91 99400 55183", "Indian"),
    ("Vikram Nair", "vikram.nair@example.in", "+91 98450 55206", "Indian"),
    ("Sneha Reddy", "sneha.reddy@example.in", "+91 90000 55291", "Indian"),
    ("Arjun Patel", "arjun.patel@example.in", "+91 99780 55314", "Indian"),
    ("Kavya Iyer", "kavya.iyer@example.in", "+91 94440 55378", "Indian"),
    ("Imran Sheikh", "imran.sheikh@example.in", "+91 98690 55402", "Indian"),
    ("Neha Gupta", "neha.gupta@example.in", "+91 98110 55465", "Indian"),
    ("Sandeep Singh", "sandeep.singh@example.in", "+91 98140 55519", "Indian"),
]

DEMO_MESSAGES = [
    "I was refused last year for missing legalisation and want to reapply properly.",
    "Starting a master's programme in Kharkiv this autumn and need the student route.",
    "An employer in Kyiv is sponsoring me — unsure who applies for the permit first.",
    "Looking to register an LLC and move myself plus two staff over.",
    "My spouse holds a Ukrainian residence permit and I want to join her.",
    "Just a short holiday, but my passport expires in five months.",
    "Need to convert my Type D visa into a temporary residence permit.",
    "",
]


def cmd_seed_demo(args: list[str]) -> int:
    """Populate realistic sample bookings so the dashboard has something to show."""
    db.get_connection()
    try:
        count = int(args[0]) if args else 12
    except ValueError:
        count = 12
    count = max(1, min(count, 60))

    services = settings.SERVICES
    modes = settings.CONSULTATION_MODES
    timelines = ["As soon as possible", "Within 1–3 months", "Within 3–6 months", ""]

    # Collect free slots across the booking window, plus some in the recent past
    # so the dashboard shows completed history too.
    window_start, window_end = scheduling.booking_window()
    future_slots: list[tuple[str, str]] = []
    cursor = window_start
    while cursor <= window_end and len(future_slots) < count * 3:
        info = scheduling.day_availability(cursor)
        for slot in info["slots"]:
            if slot["available"]:
                future_slots.append((info["date"], slot["time"]))
        cursor += timedelta(days=1)

    past_slots: list[tuple[str, str]] = []
    cursor = window_start - timedelta(days=1)
    while cursor >= window_start - timedelta(days=21) and len(past_slots) < count:
        if scheduling.is_open(cursor):
            for hhmm in settings.slots_for_weekday(cursor.weekday()):
                past_slots.append((cursor.isoformat(), hhmm))
        cursor -= timedelta(days=1)

    random.shuffle(future_slots)
    random.shuffle(past_slots)

    future_count = max(1, int(count * 0.65))
    chosen = future_slots[:future_count] + past_slots[: count - future_count]
    if not chosen:
        print("No free slots available to seed into.")
        return 1

    created = 0
    for index, (slot_date, slot_time) in enumerate(chosen):
        name, email, phone, nationality = DEMO_NAMES[index % len(DEMO_NAMES)]
        if index >= len(DEMO_NAMES):
            name = f"{name.split()[0]} {chr(65 + index % 26)}."
            email = email.replace("@", f"{index}@")
        service = random.choice(services)
        mode = random.choice(modes)
        try:
            booking = db.create_booking(
                {
                    "full_name": name,
                    "email": email,
                    "phone": phone,
                    "nationality": nationality,
                    "service_id": service["id"],
                    "service_name": service["name"],
                    "mode_id": mode["id"],
                    "mode_name": mode["name"],
                    "slot_date": slot_date,
                    "slot_time": slot_time,
                    "applicants": random.choice([1, 1, 1, 2, 2, 3, 4]),
                    "travel_timeline": random.choice(timelines),
                    "message": random.choice(DEMO_MESSAGES),
                    "consent": True,
                    "source": "demo-seed",
                    "ip_address": "127.0.0.1",
                    "user_agent": "seed-script",
                }
            )
        except db.SlotTakenError:
            continue

        # Give the sample data a realistic spread of statuses.
        is_past = slot_date < scheduling.today().isoformat()
        if is_past:
            status = random.choice(["completed", "completed", "completed", "no-show"])
        else:
            status = random.choice(
                ["pending", "pending", "confirmed", "confirmed", "confirmed", "cancelled"]
            )
        if status != "pending":
            try:
                db.update_booking_status(booking["id"], status)
            except db.SlotTakenError:
                pass
        created += 1

    # A few sample enquiries as well.
    for index in range(min(4, count)):
        name, email, phone, _ = DEMO_NAMES[(index + 3) % len(DEMO_NAMES)]
        db.create_enquiry(
            {
                "full_name": name,
                "email": email,
                "phone": phone,
                "topic": random.choice(list({"General question", "Processing times",
                                             "Document requirements", "Fees and pricing"})),
                "message": random.choice(
                    [m for m in DEMO_MESSAGES if m]
                ),
                "ip_address": "127.0.0.1",
            }
        )

    print(f"Seeded {created} bookings and 4 enquiries.")

    # Make sure there is actually a way to log in and look at the seeded data.
    was_created, message = auth.ensure_bootstrap_admin()
    if was_created:
        print(f"{message}")
    print("\nStart the server and open http://localhost:"
          f"{settings.port}/admin to browse them:")
    print("    python3 run.py")
    print(f"    sign in as {settings.admin_email}")
    return 0


def cmd_stats(_args: list[str]) -> int:
    db.get_connection()
    stats = db.dashboard_stats()
    print(f"\n  {settings.brand_name} — database summary")
    print("  " + "-" * 44)
    for label, key in [
        ("Total bookings", "total_bookings"),
        ("Pending", "pending"),
        ("Confirmed", "confirmed"),
        ("Completed", "completed"),
        ("Cancelled", "cancelled"),
        ("Today", "today"),
        ("Upcoming", "upcoming"),
        ("Enquiries (new)", "new_enquiries"),
        ("Enquiries (total)", "total_enquiries"),
        ("Emails sent", "emails_sent"),
        ("Emails queued", "emails_queued"),
        ("Emails failed", "emails_failed"),
    ]:
        print(f"  {label:<22} {stats[key]}")
    print(f"\n  Database: {settings.db_path}")
    print(f"  Admin users: {auth.count_admins()}\n")
    return 0


def cmd_reset(args: list[str]) -> int:
    if "--yes" not in args:
        print("This deletes every booking, enquiry and dashboard user.")
        print("Re-run with --yes to confirm: python3 run.py reset --yes")
        return 1
    db.get_connection()
    for table in (
        "bookings",
        "enquiries",
        "sessions",
        "admin_users",
        "email_log",
        "blocked_slots",
        "activity_log",
    ):
        db.execute(f"DELETE FROM {table}")
    db.execute("VACUUM")
    print("Database cleared.")
    created, message = auth.ensure_bootstrap_admin()
    print(f"{message}")
    return 0


COMMANDS = {
    "serve": cmd_serve,
    "run": cmd_serve,
    "create-admin": cmd_create_admin,
    "set-password": cmd_set_password,
    "list-admins": cmd_list_admins,
    "test-email": cmd_test_email,
    "seed-demo": cmd_seed_demo,
    "stats": cmd_stats,
    "reset": cmd_reset,
}


def main(argv: list[str]) -> int:
    if not argv:
        return cmd_serve([])
    command = argv[0].lower()
    if command in {"-h", "--help", "help"}:
        print(__doc__)
        return 0
    handler = COMMANDS.get(command)
    if handler is None:
        print(f"Unknown command: {command}\n")
        print(__doc__)
        return 1
    return handler(argv[1:])


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(130)
