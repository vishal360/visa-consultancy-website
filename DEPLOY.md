# Deploying

Two things this app needs from a host:

1. **A long-running process.** It is a real HTTP server, not serverless
   functions. Anything that sleeps or recycles the process between requests is
   the wrong shape.
2. **A persistent disk for `data/`.** `data/app.db` holds every booking and
   enquiry. On most platforms the filesystem is wiped on each deploy unless you
   explicitly attach a volume — **skip this and you will silently lose bookings
   on your next deploy.** This is the single most common way to get this wrong.

TLS is handled for you on the managed platforms below. If you self-host, put a
reverse proxy in front — see the VPS section.

---

## Which host to pick

| | Render / Railway (managed) | Hetzner / DigitalOcean (VPS) |
| --- | --- | --- |
| Deploying a change | `git push`, done | `git pull` + restart over SSH |
| HTTPS certificate | automatic | you install Caddy once |
| OS patching, firewall | not your problem | yours forever |
| Running `run.py` commands | browser shell (Render) | SSH |
| Backups | you still script them | you still script them |
| Cost | ~$5–7/month | ~$4–6/month |

The VPS saves a couple of dollars a month and costs you a sysadmin job. Unless
you want that job, take the managed option — the price difference is not the
interesting variable here.

**Do not use DigitalOcean App Platform** (their PaaS, as opposed to a Droplet).
Its basic tier has an ephemeral filesystem, so `data/app.db` would be destroyed
on every deploy. If you go with DigitalOcean, use a Droplet and follow Option C.

## Option A — Render (easiest)

Roughly five minutes, and the repo already contains
[`render.yaml`](render.yaml) so most settings come across automatically.

### The three passwords, which are all different

This trips everyone up, so to be explicit:

| Password | Who creates it | Where it goes | What it does |
| --- | --- | --- | --- |
| Your **Gmail account password** | you already have it | **nowhere in this app** | logs you into Gmail itself |
| A **Gmail App Password** | Google generates it (16 characters) | `SMTP_PASSWORD` | lets the website send email through your Gmail |
| Your **dashboard password** | you invent it | `ADMIN_PASSWORD` | logs you into `/admin` |

Your real Gmail password is never entered anywhere in this application. Google
blocks plain-password sign-ins from apps once 2-Step Verification is on, which is
why the App Password exists: it is a separate, single-purpose credential you can
revoke on its own without touching your main account.

The dashboard password is unrelated to Gmail entirely — it is just the password
for this website's admin area. Pick something new.

### 1. Get a Gmail App Password first

With 2-Step Verification enabled on the account, go to
<https://myaccount.google.com/apppasswords>, create a password for "Mail", and
keep the 16-character value it shows you (Google only displays it once). That is
your `SMTP_PASSWORD`.

### 2. Create the service — choose Blueprint, not Web Service

Render's **+ New** menu offers Web Service, Static Site, Blueprint, Postgres and
others. Pick **Blueprint**. It reads `render.yaml` from the repo and sets up the
web service, the persistent disk and every environment variable in one step.
Choosing "Web Service" instead works, but then you have to add the disk and all
the variables by hand, and forgetting the disk is exactly the mistake that
deletes your bookings.

For reference, if you ever do configure it manually:

| Setting | Value |
| --- | --- |
| Service type | **Web Service** (it runs a server, so not a Static Site) |
| Language / runtime | **Python 3** |
| Build command | `python3 --version` (nothing to install) |
| Start command | `python3 run.py` |
| Instance plan | **0.5 CPU / 512 MB** — listed as `0.5c-512mb`, formerly "Starter" |
| Disk | 1 GB mounted at `/opt/render/project/src/data` |

Do **not** pick the **Free** instance: it cannot have a persistent disk and it
sleeps after 15 minutes of inactivity.

1. Sign up at <https://render.com> and connect GitHub. The repo is private, so
   approve Render's access to it.
2. **+ New → Blueprint**, select `visa-consultancy-website`. Render reads
   `render.yaml` and proposes a web service with a 1 GB disk attached.
3. Fill in the variables it prompts for:

   | Variable | Value |
   | --- | --- |
   | `ADMIN_EMAIL` | the address you will sign in with |
   | `ADMIN_PASSWORD` | a strong password, not the documented default |
   | `SMTP_HOST` | `smtp.gmail.com` |
   | `SMTP_USER` | your Gmail address |
   | `SMTP_PASSWORD` | the 16-character App Password |
   | `MAIL_FROM` | the same Gmail address |
   | `NOTIFY_EMAILS` | where booking alerts should land |
   | `BASE_URL` | leave blank for now |

   Leave `SECRET_KEY` alone — Render generates a strong one.
4. Apply. The first build takes a couple of minutes; there is nothing to
   install, so it is mostly just cloning the repo.

### 3. Point BASE_URL at the real URL

Once deployed you get something like
`https://visa-consultancy.onrender.com`. Set `BASE_URL` to exactly that (no
trailing slash) and save — Render redeploys automatically. Until you do, links
inside emails point at localhost.

### 4. Verify the deployment, *before* taking real bookings

Open the **Shell** tab on your service and run:

```bash
python3 run.py check
```

Every line should read `PASS`. Two you must not ignore:

- **Disk persistence** — on a brand-new service this says *"Boot #1 … not yet
  proven"*, which is expected. Trigger a manual redeploy (**Manual Deploy →
  Deploy latest commit**), then run `python3 run.py check` again. The boot count
  must reach **2 or more**. If it is still stuck at 1, the disk did not mount
  and every booking would be erased on your next deploy — stop and fix that
  first.
- **Dashboard login** — fails while the documented default password is still in
  use. Fix with `python3 run.py set-password`.

Then confirm email actually leaves the building:

```bash
python3 run.py test-email your@email.com
```

Check the inbox *and* the spam folder. Finally, book a test consultation through
the public site and confirm the notification arrives, then delete it from the
dashboard.

A paid instance is required: Render only lets you attach a persistent disk to a
paid service, and free services spin down after 15 minutes of inactivity and
take about a minute to wake. Both are disqualifying for a booking site.

Budget roughly **$7/month** for the 0.5 CPU / 512 MB instance, plus **$0.25/month**
for the 1 GB disk at Render's published $0.25/GB. Treat the figure Render shows
you on the Apply screen as authoritative — it is the only number guaranteed to be
current.

This is a **recurring monthly charge**, not a one-off. Render meters it prorated
to the second, but a website has to stay up, so in practice you accrue the full
monthly amount every month. The per-second billing matters only when you stop:
delete or suspend the service and charges stop there and then, with no
minimum term. The Hobby workspace itself has no monthly fee, so you are paying
for the instance and disk only, not a plan on top.

### What the Hobby plan includes each month

Billing → Included Usage in the dashboard shows these allowances, which reset
monthly and cost nothing:

| Allowance | Included | What it means here |
| --- | --- | --- |
| Bandwidth | **5 GB** | ~35,000 first-time visits, see below |
| Custom domains | **2** | enough for `yourdomain.com` + `www` |
| Services | **25** | this app is 1 |
| Pipeline (build) minutes | **500** | builds are trivial, nothing to install |
| Free instance hours | **750** | only applies to *free* instances, not yours |

That last row is worth understanding: the 750 hours are for Render's **free**
instance type. A paid instance does not draw from that pool, so seeing `0 / 750`
used is normal and expected on a paid service — it is not a sign that anything
is wrong.

### Will the bill move around?

Barely. The instance and the disk are flat charges. The only line that scales
with traffic is bandwidth, charged at $0.15/GB *after* the 5 GB included — and
this site is light:

| | |
| --- | --- |
| Page weight for a first-time visitor | ~148 KB (HTML + CSS + JS + icon) |
| Included 5 GB covers | **~35,000 first-time visits/month** (~1,180/day) |
| If you somehow doubled that | 5 GB overage = **$0.75** |

Returning visitors re-download almost nothing, since static assets carry long
cache headers, so real headroom is higher still. Bandwidth will not be a
meaningful part of your bill.

The **Unbilled Charges** tab shows what is accruing right now; **Invoices** shows
your cycle dates and past bills. Those are the authoritative views — glance at
them after the first month to confirm the total matches what you expected.

Useful afterwards: the **Shell** tab in the Render dashboard gives you a
terminal in the browser, so you can run `python3 run.py change-email …` or
`set-password` without SSH or installing anything locally.

### Custom domain

Render gives you a free `*.onrender.com` subdomain. Your own domain is a separate
purchase from a registrar — Render does not sell domains.

1. **Buy the domain** from a registrar. Cloudflare sells at cost, Namecheap and
   Hostinger are cheap, BigRock is India-based. Expect roughly ₹800–1,500 a year
   for a `.com`; `.in` is often cheaper. A `.com` is only yours if nobody already
   owns it, so check availability first and have a fallback in mind.
2. **Add it in Render:** service → Settings → Custom Domain. The Hobby plan
   includes **2 custom domains free**, which is exactly enough for
   `vpukralink.com` and `www.vpukralink.com`. Further domains are $0.25/month
   each, so this costs you nothing extra.
3. **Create the DNS record** Render shows you at the registrar — a `CNAME` for
   `www`, or an `ALIAS`/`A` record for the bare domain.
4. Wait for DNS to propagate (minutes to a few hours). TLS is issued
   automatically, no certificate work needed.
5. **Update `BASE_URL`** to the new domain so email links are right.

---

## Option B — Fly.io or Railway

Both work the same way using the included [`Dockerfile`](Dockerfile).

**Fly.io** — mount a volume at `/app/data`:

```bash
fly launch --no-deploy            # generates fly.toml from the Dockerfile
fly volumes create data --size 1 --region waw
fly secrets set SECRET_KEY="$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))')" \
                ADMIN_EMAIL=you@example.com \
                ADMIN_PASSWORD='a-strong-password' \
                SMTP_HOST=smtp.gmail.com SMTP_USER=you@gmail.com \
                SMTP_PASSWORD='your-app-password' \
                MAIL_FROM=you@gmail.com NOTIFY_EMAILS=you@gmail.com \
                DEBUG=false SECURE_COOKIES=true
fly deploy
```

Then add the mount to `fly.toml`:

```toml
[[mounts]]
  source = "data"
  destination = "/app/data"
```

**Railway** — New Project → Deploy from GitHub. Add a Volume mounted at
`/app/data`, then set the same environment variables under Variables.

---

## Option C — Your own VPS (most control, ~$5/month)

Works on any Ubuntu/Debian box (Hetzner, DigitalOcean, Vultr, Contabo). Nothing
to install beyond Python, which is already there.

```bash
# --- on the server, as root ---
adduser --disabled-password --gecos "" visa
cd /home/visa
git clone https://github.com/vishal360/visa-consultancy.git app
cd app
cp .env.example .env
nano .env            # set SECRET_KEY, ADMIN_*, SMTP_*, BASE_URL,
                     # DEBUG=false, SECURE_COOKIES=true, PORT=8000
chown -R visa:visa /home/visa
```

Create `/etc/systemd/system/visa.service` so it starts on boot and restarts on
crash:

```ini
[Unit]
Description=Visa consultancy website
After=network.target

[Service]
Type=simple
User=visa
WorkingDirectory=/home/visa/app
ExecStart=/usr/bin/python3 run.py
Restart=always
RestartSec=3

# Basic hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ReadWritePaths=/home/visa/app/data

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable --now visa
systemctl status visa        # confirm it is running
```

Now put Caddy in front for automatic HTTPS (simpler than nginx — it obtains and
renews certificates on its own):

```bash
apt install -y caddy
```

`/etc/caddy/Caddyfile`:

```
yourdomain.com {
    reverse_proxy 127.0.0.1:8000
}
```

```bash
systemctl reload caddy
```

Point an `A` record for `yourdomain.com` at the server's IP. Certificates are
issued automatically on first request.

**Back up the database** — this is not optional:

```bash
# /etc/cron.daily/visa-backup  (chmod +x)
#!/bin/sh
sqlite3 /home/visa/app/data/app.db ".backup '/home/visa/backups/app-$(date +%F).db'"
find /home/visa/backups -name 'app-*.db' -mtime +30 -delete
```

Use `.backup` rather than copying the file — it is safe to run while the server
is live. Copy the backups off the machine periodically.

---

## Before you go live

- [ ] `SECRET_KEY` set to a long random value
      (`python3 -c "import secrets; print(secrets.token_urlsafe(48))"`)
- [ ] `ADMIN_PASSWORD` changed from the default, or run
      `python3 run.py set-password`
- [ ] `DEBUG=false` — otherwise error pages leak internal details
- [ ] `SECURE_COOKIES=true` — you are on HTTPS now
- [ ] `BASE_URL` matches your real domain, so email links work
- [ ] `data/` is on a persistent volume
- [ ] `python3 run.py test-email you@example.com` actually arrives
- [ ] Real contact details in `BRAND_NAME`, `CONTACT_EMAIL`, `CONTACT_PHONE`,
      `CONTACT_PHONE`
- [ ] Visa content in `app/content.py` checked against current official rules
- [ ] `templates/privacy.html` reviewed for your jurisdiction
- [ ] Database backups scheduled

## "The setting you are looking for is not available for your account"

This is what Google says when you open the App Passwords page and the feature is
hidden. Almost always it means **2-Step Verification is not switched on** — App
Passwords simply do not exist as an option until it is.

Fix it:

1. Go to <https://myaccount.google.com/signinoptions/twosv> and turn on 2-Step
   Verification (you will need your phone).
2. Go back to <https://myaccount.google.com/apppasswords>. The page now works.

Still hidden after enabling 2SV? Then one of these applies:

- **It is a Google Workspace account** (an email on your own domain rather than
  `@gmail.com`) and the administrator has disabled App Passwords. Only the admin
  can re-enable it.
- **The account is enrolled in Google's Advanced Protection Program**, which
  blocks App Passwords by design.
- **Your only second factor is a passkey or security key.** Add a phone number
  as a backup second step and the option usually appears.

If none of those can be changed, do not fight it — use Brevo instead.

### Alternative: Brevo (no App Password needed)

Brevo gives you 300 emails a day free, permanently, and does not require you to
own a domain. It is also purpose-built for transactional email, so
deliverability is generally better than relaying through a personal Gmail.

1. Sign up at <https://www.brevo.com> and verify your email address.
2. Add `vpukralink@gmail.com` as a **verified sender** (Senders, Domains & IPs →
   Senders). Brevo emails you a confirmation link.
3. Open **SMTP & API → SMTP** and generate an **SMTP key**.
4. Set these on Render:

   | Variable | Value |
   | --- | --- |
   | `SMTP_HOST` | `smtp-relay.brevo.com` |
   | `SMTP_PORT` | `587` |
   | `SMTP_USE_TLS` | `true` |
   | `SMTP_USER` | the login Brevo shows, e.g. `9a1b2c001@smtp-brevo.com` |
   | `SMTP_PASSWORD` | the **SMTP key** from step 3 |
   | `MAIL_FROM` | `vpukralink@gmail.com` (the sender you verified) |

Two mistakes to avoid, because they account for most Brevo failures:

- `SMTP_USER` is **not** your own email address. It is the odd-looking
  `…@smtp-brevo.com` login on the SMTP page.
- Use the **SMTP key**, not an **API key**. They are different credentials on
  the same screen and the API key will fail to authenticate.

Then verify: `python3 run.py test-email vpukralink@gmail.com`

### You are not blocked on this

Email is the one piece that can be fixed after launch. With `SMTP_HOST` unset
the site runs in offline mode: bookings still save, still appear in the
dashboard, and the emails that *would* have been sent are written to
`data/outbox/` on the persistent disk, viewable under each booking in the
dashboard. Nothing is lost. Deploy first, sort email out second — just do it
before you point real clients at the site, since they would otherwise get no
confirmation.

## Email deliverability

Mail sent from a cloud host often lands in spam. Two fixes, in order of
preference:

1. **Use a transactional provider** — SendGrid, Mailgun, Postmark, Amazon SES.
   Free tiers cover hundreds of emails a month, and they handle reputation for
   you. Just point the `SMTP_*` variables at them.
2. **If you use your own domain**, add SPF, DKIM and DMARC DNS records. Your
   provider gives you the exact values.

Gmail with an App Password works fine for low volume, but send *from* the Gmail
address — spoofing a different `MAIL_FROM` gets filtered.
