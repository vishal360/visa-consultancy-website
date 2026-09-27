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

### 1. Get a Gmail App Password first

You cannot use your normal Google password for SMTP. With 2-Step Verification
enabled on the account, go to <https://myaccount.google.com/apppasswords>,
create a password for "Mail", and keep the 16-character value. That is your
`SMTP_PASSWORD`.

### 2. Create the service

1. Sign up at <https://render.com> and connect GitHub. The repo is private, so
   approve Render's access to it.
2. **New → Blueprint**, select `visa-consultancy-website`. Render reads
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
take about a minute to wake. Both are disqualifying for a booking site. Budget
roughly $7/month for the instance plus $0.25/GB/month for the disk.

Useful afterwards: the **Shell** tab in the Render dashboard gives you a
terminal in the browser, so you can run `python3 run.py change-email …` or
`set-password` without SSH or installing anything locally.

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
      `CONTACT_PHONE`
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
