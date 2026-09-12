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

## Option A — Render (easiest)

Roughly five minutes, and the repo already contains
[`render.yaml`](render.yaml) so most settings come across automatically.

1. Sign up at <https://render.com> and connect your GitHub account.
2. **New → Blueprint**, select the `visa-consultancy` repo. Render reads
   `render.yaml`.
3. Fill in the variables it prompts for (`sync: false` ones):
   `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `SMTP_*`, `MAIL_FROM`, `NOTIFY_EMAILS`.
   Leave `SECRET_KEY` alone — Render generates it.
4. Deploy. You get `https://visa-consultancy.onrender.com`.
5. Set `BASE_URL` to that URL and redeploy, so links inside emails are correct.

A paid plan (currently ~$7/month) is required because the free tier has no
persistent disk and also spins the process down when idle. Both are
disqualifying here.

**Custom domain:** Settings → Custom Domain, add `yourdomain.com`, then create
the CNAME record Render shows you at your registrar. TLS is automatic. Update
`BASE_URL` afterwards.

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
      `OFFICE_ADDRESS`
- [ ] Visa content in `app/content.py` checked against current official rules
- [ ] `templates/privacy.html` reviewed for your jurisdiction
- [ ] Database backups scheduled

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
