#!/usr/bin/env bash
# End-to-end smoke test: boots the server, exercises every public and admin
# flow with curl, then shuts down. Run from the project root:
#     bash scripts/e2e_test.sh
set -uo pipefail

PORT="${PORT:-8111}"
BASE="http://127.0.0.1:${PORT}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG=/tmp/vc-e2e-server.log
COOKIES=/tmp/vc-e2e-cookies.txt
PASS=0
FAIL=0

cd "$ROOT"

say()  { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }
ok()   { PASS=$((PASS+1)); printf '  \033[32mPASS\033[0m %s\n' "$*"; }
bad()  { FAIL=$((FAIL+1)); printf '  \033[31mFAIL\033[0m %s\n' "$*"; }

# check <description> <expected> <actual>
check() {
  if [ "$2" = "$3" ]; then ok "$1 ($3)"; else bad "$1 — expected $2, got $3"; fi
}
# contains <description> <needle> <file>
contains() {
  if grep -q -- "$2" "$3"; then ok "$1"; else bad "$1 — '$2' not found"; fi
}

code() { curl -s -o "$2" -w '%{http_code}' "$1"; }

cleanup() {
  [ -n "${SERVER_PID:-}" ] && kill "$SERVER_PID" 2>/dev/null
  wait "${SERVER_PID:-}" 2>/dev/null
}
trap cleanup EXIT

# --------------------------------------------------------------------------
say "Starting server on port ${PORT}"
rm -f "$COOKIES"
PORT="$PORT" DEBUG=true python3 -u run.py serve > "$LOG" 2>&1 &
SERVER_PID=$!

for i in $(seq 1 40); do
  if curl -s -o /dev/null "${BASE}/" 2>/dev/null; then break; fi
  sleep .25
done
if ! curl -s -o /dev/null "${BASE}/" 2>/dev/null; then
  bad "server did not start"; sed -n '1,40p' "$LOG"; exit 1
fi
ok "server is up"
sed -n '1,14p' "$LOG" | sed 's/^/    /'

# --------------------------------------------------------------------------
say "Public pages"
check "GET /"          200 "$(code "${BASE}/" /tmp/e_home.html)"
check "GET /privacy"   200 "$(code "${BASE}/privacy" /tmp/e_priv.html)"
check "GET /thanks"    200 "$(code "${BASE}/thanks" /tmp/e_thanks.html)"
check "GET /missing"   404 "$(code "${BASE}/nope" /tmp/e_404.html)"
check "static CSS"     200 "$(code "${BASE}/static/css/styles.css" /tmp/e.css)"
check "static JS"      200 "$(code "${BASE}/static/js/app.js" /tmp/e.js)"
check "favicon"        200 "$(code "${BASE}/static/img/favicon.svg" /tmp/e.svg)"
check "traversal blocked" 404 "$(code "${BASE}/static/../app/config.py" /tmp/e_trav)"

if grep -q '{{' /tmp/e_home.html; then
  bad "homepage contains unsubstituted {{ }}"
else
  ok "homepage fully rendered (no {{ }} left)"
fi
contains "homepage renders visa cards"  'visa-card'   /tmp/e_home.html
contains "homepage renders boot JSON"   'bootData'    /tmp/e_home.html
contains "homepage has booking form"    'bookingForm' /tmp/e_home.html

# --------------------------------------------------------------------------
say "Public API — availability"
curl -s "${BASE}/api/config" -o /tmp/e_config.json
contains "/api/config lists services" '"services"' /tmp/e_config.json

curl -s "${BASE}/api/availability?limit=3" -o /tmp/e_next.json
contains "/api/availability returns next days" '"mode": "next"' /tmp/e_next.json

DAY=$(python3 -c "
import json;d=json.load(open('/tmp/e_next.json'));print(d['days'][0]['date'])")
TIME=$(python3 -c "
import json
d=json.load(open('/tmp/e_next.json'))
print(next(s['time'] for s in d['days'][0]['slots'] if s['available']))")
TIME2=$(python3 -c "
import json
d=json.load(open('/tmp/e_next.json'))
ts=[s['time'] for s in d['days'][0]['slots'] if s['available']]
print(ts[1] if len(ts)>1 else ts[0])")
echo "    first free slot: ${DAY} ${TIME} (second: ${TIME2})"

curl -s "${BASE}/api/availability?date=${DAY}" -o /tmp/e_day.json
contains "single-day availability" '"slots"' /tmp/e_day.json
check "bad date rejected" 400 "$(code "${BASE}/api/availability?date=notadate" /tmp/e_bad.json)"

MONTH=$(date -u +%m); YEAR=$(date -u +%Y)
curl -s "${BASE}/api/availability/month?year=${YEAR}&month=${MONTH}" -o /tmp/e_month.json
contains "month grid returns days" '"first_weekday"' /tmp/e_month.json
check "bad month rejected" 400 "$(code "${BASE}/api/availability/month?year=2026&month=44" /tmp/e_bm.json)"

# --------------------------------------------------------------------------
say "Booking creation"
BOOK=$(cat <<JSON
{"full_name":"Priya Sharma","email":"priya.test@example.com",
 "phone":"+91 98200 55014","nationality":"Indian","service_id":"student",
 "mode_id":"video","applicants":"2","travel_timeline":"1-3-months",
 "slot_date":"${DAY}","slot_time":"${TIME}","consent":"true",
 "message":"Testing the booking flow end to end."}
JSON
)
STATUS=$(curl -s -o /tmp/e_book.json -w '%{http_code}' -X POST "${BASE}/api/bookings" \
  -H 'Content-Type: application/json' -d "$BOOK")
check "POST /api/bookings creates booking" 201 "$STATUS"
REF=$(python3 -c "
import json
try: print(json.load(open('/tmp/e_book.json')).get('reference',''))
except Exception: print('')")
if [ -n "$REF" ]; then ok "got reference: $REF"; else bad "no reference returned"; fi

# Double booking must be rejected with 409.
STATUS=$(curl -s -o /tmp/e_dup.json -w '%{http_code}' -X POST "${BASE}/api/bookings" \
  -H 'Content-Type: application/json' -d "$BOOK")
check "duplicate slot rejected" 409 "$STATUS"
contains "409 returns fresh availability" '"day"' /tmp/e_dup.json

# That slot should now report as booked.
curl -s "${BASE}/api/availability?date=${DAY}" -o /tmp/e_day2.json
TAKEN=$(python3 -c "
import json
d=json.load(open('/tmp/e_day2.json'))['day']
s=next(x for x in d['slots'] if x['time']=='${TIME}')
print(s['reason'] if not s['available'] else 'still-free')")
check "slot now marked booked" "booked" "$TAKEN"

# Validation errors.
STATUS=$(curl -s -o /tmp/e_inv.json -w '%{http_code}' -X POST "${BASE}/api/bookings" \
  -H 'Content-Type: application/json' \
  -d '{"full_name":"X","email":"bad","phone":"1","service_id":"nope","consent":""}')
check "invalid booking rejected" 422 "$STATUS"
contains "field errors returned" '"errors"' /tmp/e_inv.json

# Honeypot: silently accepted, nothing stored.
STATUS=$(curl -s -o /tmp/e_spam.json -w '%{http_code}' -X POST "${BASE}/api/bookings" \
  -H 'Content-Type: application/json' \
  -d "{\"full_name\":\"Bot\",\"email\":\"bot@spam.com\",\"phone\":\"+919820055014\",\"service_id\":\"student\",\"slot_date\":\"${DAY}\",\"slot_time\":\"${TIME2}\",\"consent\":\"true\",\"website\":\"http://spam.example\"}")
check "honeypot accepted silently" 200 "$STATUS"
contains "honeypot flagged" '"spam": true' /tmp/e_spam.json

# Form-encoded submission must work too.
STATUS=$(curl -s -o /tmp/e_form.json -w '%{http_code}' -X POST "${BASE}/api/bookings" \
  --data-urlencode "full_name=Form Encoded" \
  --data-urlencode "email=form.test@example.com" \
  --data-urlencode "phone=+91 98330 55127" \
  --data-urlencode "service_id=work" \
  --data-urlencode "mode_id=phone" \
  --data-urlencode "slot_date=${DAY}" \
  --data-urlencode "slot_time=${TIME2}" \
  --data-urlencode "consent=true")
check "form-encoded booking works" 201 "$STATUS"

# --------------------------------------------------------------------------
say "Booking lookup"
check "lookup by reference" 200 "$(code "${BASE}/api/bookings/${REF}" /tmp/e_look.json)"
contains "lookup masks email" 'email_masked' /tmp/e_look.json
if grep -q 'priya.test@example.com' /tmp/e_look.json; then
  bad "lookup leaked the full email address"
else
  ok "lookup does not leak full email"
fi
check "unknown reference 404s" 404 "$(code "${BASE}/api/bookings/VC-0000-0000" /tmp/e_look404.json)"

# --------------------------------------------------------------------------
say "Enquiry submission"
STATUS=$(curl -s -o /tmp/e_enq.json -w '%{http_code}' -X POST "${BASE}/api/enquiries" \
  -H 'Content-Type: application/json' \
  -d '{"full_name":"Rohit Mehta","email":"rohit.test@example.com","phone":"+91 99400 55183","topic":"documents","message":"Which documents do I need for a Type D student visa?"}')
check "POST /api/enquiries" 201 "$STATUS"
contains "enquiry reference returned" '"reference"' /tmp/e_enq.json

STATUS=$(curl -s -o /tmp/e_enqbad.json -w '%{http_code}' -X POST "${BASE}/api/enquiries" \
  -H 'Content-Type: application/json' -d '{"full_name":"A","email":"x","message":"hi"}')
check "invalid enquiry rejected" 422 "$STATUS"

# --------------------------------------------------------------------------
say "Emails generated (offline outbox)"
COUNT=$(ls -1 data/outbox/*.eml 2>/dev/null | wc -l | tr -d ' ')
if [ "$COUNT" -ge 4 ]; then
  ok "outbox has $COUNT .eml files (admin + client for booking and enquiry)"
else
  bad "expected at least 4 emails in outbox, found $COUNT"
fi
if ls data/outbox/*.eml >/dev/null 2>&1 && grep -lq "$REF" data/outbox/*.eml; then
  ok "booking reference appears in a generated email"
else
  bad "no email contains reference $REF"
fi

# --------------------------------------------------------------------------
say "Admin authentication"
check "unauthenticated /admin redirects" 303 "$(code "${BASE}/admin" /tmp/e_adm.html)"
check "login page renders" 200 "$(code "${BASE}/admin/login" /tmp/e_login.html)"
contains "login form present" 'name="password"' /tmp/e_login.html

STATUS=$(curl -s -o /dev/null -w '%{http_code}' -c "$COOKIES" -X POST "${BASE}/admin/login" \
  --data-urlencode "email=vpukralink@gmail.com" \
  --data-urlencode "password=WrongPassword" \
  --data-urlencode "next=/admin")
check "bad credentials rejected" 401 "$STATUS"

STATUS=$(curl -s -o /dev/null -w '%{http_code}' -c "$COOKIES" -X POST "${BASE}/admin/login" \
  --data-urlencode "email=vpukralink@gmail.com" \
  --data-urlencode "password=ChangeMe123!" \
  --data-urlencode "next=/admin")
check "valid login redirects" 303 "$STATUS"
if grep -q 'vc_session' "$COOKIES"; then ok "session cookie set"; else bad "no session cookie"; fi
if grep -qi 'httponly' "$COOKIES"; then ok "cookie is HttpOnly"; else bad "cookie not HttpOnly"; fi

# --------------------------------------------------------------------------
say "Admin dashboard (authenticated)"
check "dashboard loads" 200 "$(curl -s -b "$COOKIES" -o /tmp/e_dash.html -w '%{http_code}' "${BASE}/admin")"
if grep -q '{{' /tmp/e_dash.html; then
  bad "dashboard has unsubstituted {{ }}"
else
  ok "dashboard fully rendered"
fi
contains "dashboard shows stat cards" 'stat-card' /tmp/e_dash.html
check "bookings page loads"  200 "$(curl -s -b "$COOKIES" -o /tmp/e_bk.html -w '%{http_code}' "${BASE}/admin/bookings")"
check "enquiries page loads" 200 "$(curl -s -b "$COOKIES" -o /tmp/e_eq.html -w '%{http_code}' "${BASE}/admin/enquiries")"

curl -s -b "$COOKIES" "${BASE}/admin/api/bookings?per_page=100" -o /tmp/e_abk.json
contains "admin booking list returns data" '"bookings"' /tmp/e_abk.json
if grep -q "$REF" /tmp/e_abk.json; then
  ok "new booking visible in admin list"
else
  bad "new booking $REF missing from admin list"
fi

# Search filter
curl -s -b "$COOKIES" "${BASE}/admin/api/bookings?q=priya" -o /tmp/e_search.json
FOUND=$(python3 -c "
import json;d=json.load(open('/tmp/e_search.json'));print(d.get('total',0))")
if [ "$FOUND" -ge 1 ]; then ok "admin search finds booking (total=$FOUND)"; else bad "admin search found nothing"; fi

BID=$(python3 -c "
import json
d=json.load(open('/tmp/e_abk.json'))
print(next(b['id'] for b in d['bookings'] if b['reference']=='${REF}'))")
CSRF=$(python3 -c "
import re,sys
h=open('/tmp/e_dash.html').read()
m=re.search(r'name=\"csrf_token\"[^>]*value=\"([^\"]+)\"',h) or re.search(r'\"csrfToken\":\s*\"([^\"]+)\"',h)
print(m.group(1) if m else '')")
if [ -n "$CSRF" ]; then ok "CSRF token found in dashboard"; else bad "no CSRF token in dashboard"; fi

say "Admin mutations & CSRF enforcement"
STATUS=$(curl -s -o /tmp/e_nocsrf.json -w '%{http_code}' -b "$COOKIES" \
  -X POST "${BASE}/admin/api/bookings/${BID}/status" --data-urlencode "status=confirmed")
check "status change without CSRF blocked" 403 "$STATUS"

STATUS=$(curl -s -o /tmp/e_csrf.json -w '%{http_code}' -b "$COOKIES" \
  -X POST "${BASE}/admin/api/bookings/${BID}/status" \
  -H "X-CSRF-Token: ${CSRF}" \
  --data-urlencode "status=confirmed" --data-urlencode "notify=true")
check "status change with CSRF succeeds" 200 "$STATUS"
contains "booking now confirmed" '"status": "confirmed"' /tmp/e_csrf.json

STATUS=$(curl -s -o /tmp/e_notes.json -w '%{http_code}' -b "$COOKIES" \
  -X POST "${BASE}/admin/api/bookings/${BID}/notes" \
  -H "X-CSRF-Token: ${CSRF}" \
  --data-urlencode "notes=Verified passport expiry. Needs apostilled diploma.")
check "notes saved" 200 "$STATUS"
contains "notes persisted" 'apostilled diploma' /tmp/e_notes.json

STATUS=$(curl -s -o /tmp/e_badstatus.json -w '%{http_code}' -b "$COOKIES" \
  -X POST "${BASE}/admin/api/bookings/${BID}/status" \
  -H "X-CSRF-Token: ${CSRF}" --data-urlencode "status=bogus")
check "invalid status rejected" 400 "$STATUS"

curl -s -b "$COOKIES" "${BASE}/admin/api/stats" -o /tmp/e_stats.json
contains "admin stats endpoint" '"total_bookings"' /tmp/e_stats.json
curl -s -b "$COOKIES" "${BASE}/admin/api/emails" -o /tmp/e_mails.json
contains "admin email log" '"emails"' /tmp/e_mails.json
curl -s -b "$COOKIES" "${BASE}/admin/api/enquiries" -o /tmp/e_aenq.json
contains "admin enquiry list" '"enquiries"' /tmp/e_aenq.json

say "Slot blocking"
BLOCKDAY=$(python3 -c "
import json;d=json.load(open('/tmp/e_next.json'));print(d['days'][-1]['date'])")
STATUS=$(curl -s -o /tmp/e_block.json -w '%{http_code}' -b "$COOKIES" \
  -X POST "${BASE}/admin/api/slots/block" -H "X-CSRF-Token: ${CSRF}" \
  --data-urlencode "date=${BLOCKDAY}" --data-urlencode "reason=Team offsite")
check "block whole day" 200 "$STATUS"
curl -s "${BASE}/api/availability?date=${BLOCKDAY}" -o /tmp/e_blocked.json
OPENC=$(python3 -c "
import json;print(json.load(open('/tmp/e_blocked.json'))['day']['open_count'])")
check "blocked day has no open slots" 0 "$OPENC"
STATUS=$(curl -s -o /dev/null -w '%{http_code}' -b "$COOKIES" \
  -X POST "${BASE}/admin/api/slots/unblock" -H "X-CSRF-Token: ${CSRF}" \
  --data-urlencode "date=${BLOCKDAY}")
check "unblock day" 200 "$STATUS"
curl -s "${BASE}/api/availability?date=${BLOCKDAY}" -o /tmp/e_unblocked.json
OPENC=$(python3 -c "
import json;print(json.load(open('/tmp/e_unblocked.json'))['day']['open_count'])")
if [ "$OPENC" -gt 0 ]; then ok "day reopened ($OPENC slots)"; else bad "day still closed"; fi

say "CSV export"
curl -s -b "$COOKIES" -D /tmp/e_csvhead.txt "${BASE}/admin/export.csv" -o /tmp/e_export.csv
contains "CSV content-type"       'text/csv'    /tmp/e_csvhead.txt
contains "CSV attachment header"  'attachment'  /tmp/e_csvhead.txt
contains "CSV has header row"     'reference'   /tmp/e_export.csv
if grep -q "$REF" /tmp/e_export.csv; then ok "export contains new booking"; else bad "export missing $REF"; fi

say "Session teardown"
check "logout redirects" 303 "$(curl -s -b "$COOKIES" -c "$COOKIES" -o /dev/null -w '%{http_code}' "${BASE}/admin/logout")"
STATUS=$(curl -s -b "$COOKIES" -o /dev/null -w '%{http_code}' "${BASE}/admin/api/stats")
check "API rejects dead session" 401 "$STATUS"

# --------------------------------------------------------------------------
say "Server error log"
if grep -qE 'Traceback|Internal Server Error' "$LOG"; then
  bad "server logged a traceback:"
  grep -n -A12 'Traceback' "$LOG" | head -40
else
  ok "no tracebacks in server log"
fi

# --------------------------------------------------------------------------
printf '\n\033[1m================ RESULT ================\033[0m\n'
printf '  passed: \033[32m%s\033[0m\n  failed: \033[31m%s\033[0m\n\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
