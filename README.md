# Ukraine Visa Consultancy — website & booking platform

An interactive marketing site for a Ukrainian visa consultancy, with an
appointment booking system, automatic email notifications, and a private
dashboard for managing the people who book you.

**Zero third-party dependencies.** Everything runs on the Python 3.10+ standard
library (`http.server`, `sqlite3`, `smtplib`) and hand-written vanilla
JavaScript. No `pip install`, no `npm install`, no build step.

---

## Quick start

```bash
cd visa-consultancy
cp .env.example .env          # then edit it — see Configuration below
python3 run.py                # starts on http://localhost:8000
```

Open:

| URL | What it is |
| --- | --- |
| <http://localhost:8000/> | Public website |
| <http://localhost:8000/admin> | Consultant dashboard |

The first run creates the database and a dashboard login from `ADMIN_EMAIL` /
`ADMIN_PASSWORD` in your `.env` (defaults: `vpukralink@gmail.com` /
`ChangeMe123!` — change the password).

Want data to look at straight away?

```bash
python3 run.py seed-demo 20    # inserts sample bookings and enquiries
```

---

## What visitors can do

- **Browse eight visa routes** — short-stay (Type C), long-stay (Type D),
  student, work, business/investor, family reunification, residence permits and
  refusal appeals. Each card carries stay length, processing time, and an
  expandable document checklist.
- **Run the eligibility checker** — a four-question wizard that scores answers
  and recommends the right route, then drops the visitor straight into the
  booking form with that service preselected.
- **Book a consultation** in three steps: pick a service → pick a date and time
  from a live availability calendar → fill in contact details. Times already
  taken are struck through, quiet days are marked "few left", and closed days
  are greyed out.
- **Check an existing booking** by typing their reference (`VC-XXXX-XXXX`).
- **Send a general enquiry** without booking anything.

Consultations are held by **video or phone** — there is no office to visit — and
fees are deliberately not published, since they are quoted on the call once the
case is understood.

Also included: light/dark theme toggle, scroll-reveal animations, a testimonial
carousel with swipe support, an FAQ accordion, full keyboard accessibility, and a
`prefers-reduced-motion` path that disables animation entirely.

## What you get as the owner

**Emails.** Every booking sends you a notification (with the client's name,
phone, email, chosen slot and their message) and sends the client a
confirmation. Changing a booking to *confirmed*, *cancelled* or *completed*
emails the client about it. Enquiries work the same way.

**Dashboard** at `/admin`:

- **Overview** — counts for today, awaiting confirmation, confirmed, upcoming,
  new enquiries and last-7-days; the next consultations; a most-requested
  services chart; an activity log; email-delivery health; and a widget to block
  out days or single slots so the website stops offering them.
- **Bookings** — search by name, email, phone, reference or message content;
  filter by status, service and date range; sort; paginate. Clicking *Manage*
  opens a detail drawer with the full submission, one-click status changes
  (optionally emailing the client), private consultant notes, the email history
  for that booking, and delete.
- **Enquiries** — inbox for contact-form messages with status tracking
  (new → in progress → answered → closed) and reply-by-email links.
- **CSV export** that respects whichever filters you currently have applied.

---

## Configuration

Everything is driven by environment variables, read from `.env` (or the real
environment, which always wins). See [`.env.example`](.env.example) for the
annotated full list. The ones that matter most:

### Branding

```ini
BRAND_NAME=V&P UkraLink
BRAND_TAGLINE=Ukraine visa & immigration consultants
CONTACT_EMAIL=vpukralink@gmail.com
CONTACT_PHONE=+91 7048900551
```

### Receiving booking emails

Leave `SMTP_HOST` empty and the app runs in **offline mode**: every message is
written to `data/outbox/` as a standards-compliant `.eml` file you can open in
any mail client, and logged in the database. Nothing is lost, and the whole
booking flow works end to end without mail credentials — useful for local
development.

To actually send mail, fill in your provider's details:

```ini
# Gmail — use an App Password, not your account password
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USER=you@gmail.com
SMTP_PASSWORD=your-16-char-app-password

MAIL_FROM=you@gmail.com
NOTIFY_EMAILS=you@gmail.com,colleague@gmail.com   # who gets notified
```

Then verify it:

```bash
python3 run.py test-email you@gmail.com
```

Other providers work the same way — SendGrid (`smtp.sendgrid.net`, user
`apikey`), Mailgun, Amazon SES, or your own mail server. Use
`SMTP_USE_SSL=true` with `SMTP_PORT=465` for implicit TLS instead of STARTTLS.

### Availability rules

```ini
SLOT_MINUTES=45              # length of one consultation
MIN_LEAD_HOURS=12            # earliest a visitor may book from now
BOOKING_WINDOW_DAYS=60       # how far ahead the calendar opens
MAX_PER_SLOT=1               # appointments per slot
TIMEZONE_LABEL=IST (UTC+5:30)  # what visitors see
TIMEZONE_OFFSET_MINUTES=330    # what the arithmetic uses (330 = +5:30)
```

Consultations run **11:00–18:00 IST Monday to Friday**, with a shorter Saturday
and Sundays closed. Those hours, the public holidays and the service list live in
[`app/config.py`](app/config.py) — `OPENING_HOURS` (per weekday), `HOLIDAYS`,
and `SERVICES`. Edit those to match how you actually work; the calendar, the
booking form and the emails all follow automatically.

Only the fixed-date Indian national holidays are pre-filled. Festival dates such
as Diwali and Holi move each year, so add the ones you observe to `HOLIDAYS`
yourself.

### Security

```ini
SECRET_KEY=<long random string>   # python3 -c "import secrets; print(secrets.token_urlsafe(48))"
SECURE_COOKIES=true               # set true once you serve over HTTPS
SESSION_TTL_HOURS=12
```

---

## Command line

```bash
python3 run.py                    # start the server
python3 run.py list-admins        # show who can sign in
python3 run.py set-password       # change a password (signs that user out everywhere)
python3 run.py change-email       # change a sign-in email
python3 run.py create-admin       # add another dashboard user
python3 run.py delete-admin       # remove a dashboard user
python3 run.py test-email [addr]  # verify email configuration
python3 run.py seed-demo [n]      # insert n sample bookings (default 12)
python3 run.py stats              # print a database summary
python3 run.py reset --yes        # wipe all data and start over
```

### Changing the dashboard login

`ADMIN_EMAIL` and `ADMIN_PASSWORD` in `.env` are only read **once**, on the very
first run, to create the initial account. Editing them afterwards has no effect —
use the commands instead:

```bash
python3 run.py change-email old@example.com new@example.com
python3 run.py set-password new@example.com     # prompts, never echoes
```

Both drop any active sessions, so the change applies immediately. Changing the
sign-in email does **not** move where booking notifications are sent — that is
`NOTIFY_EMAILS` in `.env`.

Locked out entirely? Create a fresh account on the server with
`python3 run.py create-admin`, then delete the old one.

---

## Project layout

```
visa-consultancy/
├── run.py                 Entry point + management CLI
├── .env.example           Annotated configuration template
├── app/
│   ├── config.py          Settings, opening hours, services, holidays
│   ├── db.py              SQLite schema and all queries
│   ├── auth.py            PBKDF2 passwords, server-side sessions, CSRF
│   ├── scheduling.py      Availability engine (slots, calendar, validation)
│   ├── validation.py      Form validation and honeypot spam check
│   ├── mailer.py          SMTP delivery + offline outbox, email templates
│   ├── content.py         All marketing copy (visa types, FAQs, wizard)
│   ├── web.py             Micro framework: routing, requests, templates
│   ├── main.py            Application assembly
│   └── routes/
│       ├── public.py      Website pages + booking/enquiry API
│       └── admin.py       Dashboard pages + management API
├── templates/             Server-rendered HTML
├── static/css|js|img/     Stylesheets and vanilla JS
├── scripts/e2e_test.sh    End-to-end test suite (74 assertions)
└── data/                  SQLite database + email outbox (gitignored)
```

### HTTP API

Public:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/config` | Services, modes, wizard config |
| `GET` | `/api/availability` | Next days with free slots |
| `GET` | `/api/availability?date=YYYY-MM-DD` | Slots for one day |
| `GET` | `/api/availability/month?year=&month=` | Calendar grid data |
| `POST` | `/api/bookings` | Create a booking |
| `GET` | `/api/bookings/{reference}` | Public status lookup (email masked) |
| `POST` | `/api/enquiries` | Submit a contact message |

Admin routes live under `/admin/api/…` and require a session cookie; writes
also require the CSRF token.

---

## Testing

```bash
bash scripts/e2e_test.sh
```

Boots a server on a spare port and exercises 74 assertions with `curl`: page
rendering, static assets, directory-traversal protection, availability
calculations, booking creation, **double-booking rejection**, validation
failures, the honeypot, JSON *and* form-encoded submissions, reference lookup
with email masking, enquiries, email generation, login (good and bad
credentials), session cookie flags, every dashboard page, admin filtering and
search, **CSRF enforcement**, status updates, notes, slot blocking, CSV export,
and session expiry. It fails the build if the server logged any traceback.

---

## Deploying

See **[DEPLOY.md](DEPLOY.md)** for step-by-step instructions covering Render,
Fly.io/Railway and a plain VPS, plus a pre-launch checklist.

Two requirements to keep in mind wherever you host it: the app needs a
**long-running process** (it is not serverless), and `data/` must be on a
**persistent volume** or you will lose bookings on every redeploy.

## Notes before going live

- **Change `SECRET_KEY`, `ADMIN_PASSWORD` and the contact details.** The
  defaults are for local development only.
- **Put it behind a reverse proxy** (nginx, Caddy) terminating HTTPS, then set
  `SECURE_COOKIES=true` and `DEBUG=false`. `http.server` is fine for modest
  traffic behind a proxy; it is not intended as an internet-facing edge server.
- **Back up `data/app.db`.** It holds every booking and enquiry.
- **Review the visa content.** The processing times and document lists in
  `app/content.py` are realistic placeholders, not verified legal guidance.
  Check them against current Ukrainian State Migration Service and MFA rules
  before publishing, and have the privacy notice in `templates/privacy.html`
  reviewed against the data-protection law that applies to you.

## Security measures included

Parameterised SQL throughout; HTML autoescaping in the template renderer;
PBKDF2-SHA256 password hashing (240k iterations); opaque server-side sessions
in HttpOnly/SameSite cookies; CSRF tokens on all dashboard mutations; a partial
unique index that makes double-booking impossible at the database level; IP rate
limiting on submissions and logins; a honeypot field; request body size caps;
path-traversal protection on static files; and `X-Content-Type-Options` /
`X-Frame-Options` / `Referrer-Policy` headers.
