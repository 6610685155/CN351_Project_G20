# BUDGY — Web Application Security Assessment

**Course:** CN351 — Web Application Security
**Deliverable:** Vulnerable application + methodology report
**Methodology reference:** *The Web Application Hacker's Handbook*, Chapter 21 — "A Web Application Hacker's Methodology" (see `book.md`)

---

## 1. Introduction

This document accompanies **BUDGY**, an intentionally vulnerable web application built for an
authorized security exercise. BUDGY is a realistic personal-finance / budget-tracking application:
users register, log in, create money accounts, record income/expense/transfer transactions,
categorise them, and view dashboards and statistics.

To satisfy the assignment, three meaningful, exploitable vulnerabilities have been deliberately
introduced into a single new feature — the **Transaction History / Search** page
(`/<user_id>/transactions/`). They are:

| # | Vulnerability | Class (OWASP) | Where |
|---|---------------|---------------|-------|
| 1 | **Broken Access Control (IDOR)** | A01:2021 | `home/views.py → transaction_history()` |
| 2 | **SQL Injection** | A03:2021 | `home/views.py → transaction_history()` (raw SQL) |
| 3 | **Stored Cross-Site Scripting (XSS)** | A03:2021 | `home/templates/home/transaction_history.html` (`|safe`) |

Each vulnerability below is presented exactly as Chapter 21 prescribes: first the application is
**mapped and analysed**, then the **attack surface and parameters** are identified, a **hypothesis**
is formed, the hypothesis is **tested**, and finally the bug is **exploited**. The goal is not merely
to show the attack but to show *how it was arrived at systematically*.

---

## 2. Overview of the Application

### 2.1 Functionality

BUDGY is a multi-user budgeting tool. Core features:

- **Authentication** — register, log in, log out, forgot/reset password (`authorized` app).
- **Accounts** — create/rename/delete money accounts ("Cash", "Bank", …) with balances.
- **Transactions** — record **income**, **expense**, and **transfer** entries, each tied to a
  category and an account; balances update automatically.
- **Categories** — user-defined category names per transaction type.
- **Transaction History / Search** — list and keyword-search a user's transactions *(new feature, contains the planted vulnerabilities)*.
- **Statistics & Dashboard** — pie/line charts and monthly summaries via JSON APIs.
- **Settings** — change username/email/profile picture/password, delete account, toggle a desktop "mascot".

### 2.2 Technologies Used

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12 |
| Framework | Django 5.2 |
| Database | SQLite 3 (dev) / PostgreSQL via `dj_database_url` (prod) |
| Templating | Django Templates (server-side) |
| Frontend | Bootstrap 5.3, Font Awesome, vanilla JS, Chart.js |
| Static serving | WhiteNoise |
| Auth | `django.contrib.auth` (PBKDF2-SHA256 password hashing) |

### 2.3 How to run

```bash
cd budgy
python manage.py migrate
# seed two normal users (alice/bob) and an admin, with sample transactions:
python manage.py shell -c "exec(open('seed_demo.py').read())"
python manage.py runserver
```

Demo credentials created by `seed_demo.py`:

| Username | Password | Role |
|----------|----------|------|
| `alice` | `Alice#2025` | normal user |
| `bob` | `Bob#2025` | normal user |
| `admin` | `SuperSecret#Admin1` | superuser |

> User IDs are auto-increment integers. After seeding, log in and read your own ID from the
> redirect URL (e.g. `/5/home/` → your ID is `5`). The walkthroughs below use **alice** as the
> attacker and **bob** as the victim; substitute whatever IDs your instance assigns.

An optional self-check that exercises all three bugs at once:

```bash
python manage.py shell -c "exec(open('verify_exploits.py').read())"
```

---

## 3. Phase 0 — Mapping & Analysis (Chapter 21, Steps 1–2)

Before attacking any single parameter, Chapter 21 requires that we **map the application's content**
(§1) and **analyse it** (§2). This phase is shared by all three vulnerabilities.

### 3.1 Map the application's content (§1.1 Explore Visible Content, §1.5 Enumerate Identifier-Specified Functions)

Browsing the application as a logged-in user and reviewing `home/urls.py` and `authorized/urls.py`
yields the URL inventory. The striking pattern is that almost every authenticated URL embeds a
**numeric user identifier** in the path:

```
/<user_id>/home/
/<user_id>/dashboard/
/<user_id>/transaction/income/
/<user_id>/transaction/expense/
/<user_id>/transactions/          <-- history/search (target)
/<user_id>/stats/
/<user_id>/accounts/
```

This is precisely the "identifier-specified function" pattern of §1.5 — the resource a request acts
on is selected by an identifier in the URL. That immediately flags **access control** (§6) as a
fruitful area.

### 3.2 Identify data entry points (§2.2)

For the target page `/<user_id>/transactions/`, the user-controllable inputs are:

| Entry point | Source | Used for |
|-------------|--------|----------|
| `user_id` | URL path segment | selecting *whose* transactions to show |
| `q` | URL query string (`?q=...`) | keyword search over category name |
| `category_name` | POST body on transaction/category forms | stored, later displayed in history |
| session cookie | `Cookie` header | authentication |

### 3.3 Identify technologies (§2.3) & map the attack surface (§2.4)

Response headers and behaviour reveal Django (CSRF cookie names, admin at `/admin/`, `DEBUG`
stack traces). Mapping these inputs to likely vulnerability classes (§2.4) produces our test plan:

| Input | Hypothesis (vuln class) | Methodology section |
|-------|------------------------|---------------------|
| `user_id` in path | Broken access control / IDOR | §6 Test Access Controls |
| `q` query parameter | SQL injection | §7.1 Fuzz, §7.2 SQL Injection |
| `category_name` reflected into history | Stored XSS | §7.1 Fuzz, §7.3 XSS |

The three sections below follow these threads to completion.

---

## 4. Vulnerability #1 — Broken Access Control (IDOR)

### 4.1 Description

An **Insecure Direct Object Reference**: the Transaction History page trusts the `user_id` taken
from the URL to decide whose data to return, and never checks that it matches the logged-in user.
Any authenticated user can read **any other user's** financial history simply by changing the number
in the URL — a textbook *horizontal privilege escalation*.

### 4.2 Where it exists

`budgy/home/views.py`, `transaction_history()`:

```python
@login_required(login_url="/login/")
def transaction_history(request, user_id):
    ...
    sql = (
        "SELECT trans_id, trans_type, date, amount, category_trans "
        "FROM home_transaction "
        "WHERE user_id = " + str(user_id)      # <-- uses URL value, not request.user
    )
```

The view is gated by `@login_required` (you must be *some* valid user) but it filters by the path's
`user_id` instead of `request.user.id`, and performs **no ownership check**. Compare this with the
secure views in the same file (e.g. `home_page`, `account_management_page`) which correctly use
`Account.objects.filter(user=request.user)`.

### 4.3 Methodology (Chapter 21 §6 — Test Access Controls)

- **§6.1 Understand the access-control requirements.** BUDGY's data is per-user financial records.
  The intended rule is *horizontal segregation*: a user may read only their own transactions
  (§6.1.1). Administrators aside, no user should see another user's data.
- **§6.1.2 Identify fruitful targets.** From the Phase-0 map, the `/<user_id>/...` URLs are the
  obvious target for horizontal privilege-escalation testing.
- **§6.2.2 Test with multiple accounts.** Chapter 21 says horizontal access control is tested by
  using two accounts at the same privilege level and "replacing an identifier … within a request to
  specify a resource belonging to the other user." We have `alice` and `bob` for exactly this.
- **§6.3.4 Predictable identifiers.** Even with a single account, the identifiers here are
  sequential integers, so a victim's ID can simply be guessed by decrementing/incrementing — making
  the control trivially defeatable.
- **§6.4.1 Insecure access-control methods.** The decision is based purely on a request parameter
  (`user_id`) with no server-side authorization — exactly the unsafe pattern §6.4.1 warns about.

### 4.4 Step-by-step exploitation

1. Log in as the attacker **alice**. Note her own ID from the post-login redirect, e.g.
   `http://127.0.0.1:8000/5/home/` → alice is ID **5**. Her own (legitimate) history is at:
   ```
   http://127.0.0.1:8000/5/transactions/
   ```
2. Form the hypothesis (§6.2.2): "If the page keys off the URL, changing the ID should reveal
   someone else's data." Identify the victim's ID. Because IDs are sequential (§6.3.4), simply try
   the neighbouring value — **bob** is ID **6**.
3. While **still logged in as alice**, request the victim's resource by editing only the identifier:
   ```
   http://127.0.0.1:8000/6/transactions/
   ```
4. **Result:** alice sees **bob's** private transactions ("Freelance", "Groceries", "Gaming") and
   amounts, despite never authenticating as bob. Iterating `1,2,3,…` enumerates every user's
   finances.

**Evidence (live HTTP, logged in as alice, requesting bob's ID 6):**
```
IDOR sees Gaming/Freelance: True True
```

### 4.5 Impact

Complete disclosure of every user's financial records (categories, amounts, dates). Combined with
§6.3.4 (guessable IDs) it is fully automatable to harvest the entire user base's data.

---

## 5. Vulnerability #2 — SQL Injection

### 5.1 Description

The `q` search parameter is concatenated directly into a raw SQL string with no parameterisation or
escaping. An attacker can break out of the string literal and inject arbitrary SQL, including a
`UNION SELECT` that reads from `auth_user` to dump **every username and password hash**.

### 5.2 Where it exists

`budgy/home/views.py`, `transaction_history()`:

```python
q = request.GET.get("q", "")
sql = (
    "SELECT trans_id, trans_type, date, amount, category_trans "
    "FROM home_transaction "
    "WHERE user_id = " + str(user_id)
)
if q:
    sql += " AND category_trans LIKE '%" + q + "%'"   # <-- q injected verbatim
sql += " ORDER BY date DESC"

with connection.cursor() as cursor:
    cursor.execute(sql)          # raw execution, no parameters
```

Both `user_id` and `q` are attacker-controlled and concatenated. The `q` parameter sits inside a
single-quoted `LIKE` literal — a classic injection point.

### 5.3 Methodology (Chapter 21 §7.1 Fuzz, §7.2 SQL Injection)

- **§7.1.1 Identify parameters to fuzz.** From Phase 0, `q` is a query-string parameter the server
  processes — in scope for fuzzing.
- **§7.1.3 Submit the standard payload set.** Chapter 21's SQL payloads begin with a single quote
  `'` and `'--`. We submit `'` first.
- **§7.2.2 Investigate error messages.** With Django `DEBUG=True`, injecting `'` produces a
  **500 error page** containing the raw SQL and an `OperationalError` — a strong positive signal and
  also Information Leakage (§13).
- **§7.2.3 The two-single-quote test.** Submitting one quote breaks the query; submitting two quotes
  (`''`) restores normal behaviour. Per §7.2.3 this "probably vulnerable to SQL injection" heuristic
  confirms the bug.
- **§7.2.8 Choose an attack.** Chapter 21 lists feasible attacks: modify the `WHERE` clause
  (boolean injection) and "use the `UNION` operator to inject an arbitrary `SELECT` query." We use
  both — boolean to prove control of logic, then `UNION` to exfiltrate credentials.

### 5.4 Step-by-step exploitation

All requests are made while logged in (the view requires a session). The injection is in `q`.

**Step 1 — Detect (§7.2.3).** Submit a single quote:
```
/5/transactions/?q='
```
The page returns HTTP 500 with `OperationalError: unrecognized token` and the raw query — proof the
input reaches a SQL string. Submitting `q=''` (two quotes) returns a normal page → vulnerable.

**Step 2 — Confirm logic control (boolean, §7.2.8).** Inject an always-true condition and comment
out the rest of the query:
```
/5/transactions/?q=%' OR '1'='1' -- 
```
The resulting WHERE becomes `... LIKE '%%' OR '1'='1'`, which is always true, so the page returns
**all transactions for all users**, not just the matching category. Logic is now attacker-controlled.

**Step 3 — Exfiltrate credentials (UNION, §7.2.8).** The `SELECT` returns 5 columns
(`trans_id, trans_type, date, amount, category_trans`). We craft a 5-column `UNION` that pulls
`username` and `password` from `auth_user`, placing them in text columns that the template renders:
```
/5/transactions/?q=%' UNION SELECT NULL, username, NULL, NULL, password FROM auth_user -- 
```
URL-encoded (note the trailing space after `--`, per Chapter 21's "General Guidelines" on encoding):
```
/5/transactions/?q=%25%27%20UNION%20SELECT%20NULL%2C%20username%2C%20NULL%2C%20NULL%2C%20password%20FROM%20auth_user%20--%20
```

**Result:** the results table now lists every account's username and PBKDF2 hash.

**Evidence (rendered table cells):**
```
admin   pbkdf2_sha256$1000000$uSGpNeGNTLnHr6WzAvTRGB$PgV+BeNMkAmXf1aMps5pdsGk/FURsEKR6Wu...
alice   pbkdf2_sha256$1000000$tEledjm64QNMBRMo6GzBXt$9Z2rf5B4e3lDqE2RIDyXLwAsIRVkUb/vHNN...
bob     pbkdf2_sha256$1000000$AYTdTlpTAkIZUfvUH40QNb$F4H7dSbhs9dvRThTA4oLT1IPXZ1Co3H+EMR...
jeans   pbkdf2_sha256$1000000$NS7zVnxOPZv2DE4jOYk9PC$trXw3l2pnOCbpZU+93kckUqtYf6qnsHT/bL...
```

> **Tester's note (§7.2 in practice):** the third selected column is Django's `date` field. On
> SQLite the ORM applies a datetime converter to that column, so a hash placed there is parsed to
> `None`. Aligning the stolen `password` to the text column `category_trans` (the 5th column) renders
> it intact. This is exactly the kind of column-type reasoning §7.2.8 expects when building a UNION.

### 5.5 Impact

Full read access to the entire database (any table, e.g. `auth_user`). Harvested hashes can be
cracked offline; the boolean technique also exposes all users' financial data regardless of access
control.

---

## 6. Vulnerability #3 — Stored Cross-Site Scripting (XSS)

### 6.1 Description

Category names are stored verbatim and later rendered into the Transaction History page through
Django's `|safe` filter, which **disables auto-escaping**. A user who creates a category containing
`<script>…</script>` plants a payload that executes in the browser of **anyone** who later views a
transaction with that category — a *stored* (persistent) XSS.

### 6.2 Where it exists

`budgy/home/templates/home/transaction_history.html`:

```django
<td>{{ t.category|safe }}</td>      {# <-- |safe disables HTML escaping #}
```

The data path: a category name entered on the income/expense forms (`transaction_*_page` in
`home/views.py`) is saved to `Transaction.category_trans`, then echoed back here without escaping.
Every other field (`t.type`, `t.date`, `t.amount`) is auto-escaped — only the category is unsafe.

### 6.3 Methodology (Chapter 21 §7.1 Fuzz, §7.3 XSS)

- **§7.1.1 / §7.3.1 Identify reflected parameters.** The category value submitted by the user is
  reflected back into the HTML response body of the history page → candidate for response injection.
- **§7.3.1.2 Locate the input in the response.** The value appears as element text inside a
  `<td>…</td>` cell — the simplest XSS context (a `<script>` tag injected as element content will
  execute).
- **§7.3.2.1 Craft for the context.** Because the reflection is raw element text, no attribute/tag
  breakout is needed; Chapter 21's canonical payload `"><script>alert('xss')</script>` (here simply
  `<script>...</script>`) is sufficient.
- **§7.3.2.3 Verify conclusively in a browser.** Submit the payload and confirm an `alert` dialog
  fires — proving arbitrary JavaScript execution rather than mere reflection.
- This is the **stored** variant: the payload is persisted in the database and re-served to victims,
  which is higher impact than the reflected case discussed in §7.3.2.

### 6.4 Step-by-step exploitation

1. Log in (e.g. as alice). Map the input: the **Add expense** form posts a `category_name`.
2. Create a transaction whose **category name** is the payload:
   ```
   <script>alert(document.cookie)</script>
   ```
   (Use the Expense page: enter a date, an amount, an account, and the payload as the category.)
3. Navigate to the history page:
   ```
   /5/transactions/
   ```
4. **Result:** the category cell renders the raw `<script>` tag; the browser executes it and pops an
   `alert` showing the session cookie. The payload persists — it fires for *every* viewer of that
   row, including via the IDOR path (an admin browsing the victim's history would also be hit).

**Evidence (response body contains the unescaped tag):**
```
[XSS] raw <script> reflected unescaped:  True
      (escaped form &lt;script&gt; present: False)
```

A real attacker would replace `alert(...)` with a payload that exfiltrates `document.cookie` to an
attacker server, enabling **session hijacking**.

### 6.5 Impact

Arbitrary JavaScript in victims' sessions: session/cookie theft, CSRF-token theft, action-on-behalf
of the victim, UI defacement. Because it is stored and shown through an IDOR-exposed page, a single
payload can target many users including administrators.

---

## 7. Mitigation Strategies

### 7.1 Broken Access Control (IDOR)

**Fix — authorize on the server using the session identity, never the client-supplied ID.** Filter
by `request.user`, not the URL value:

```python
@login_required(login_url="/login/")
def transaction_history(request, user_id):
    if request.user.id != user_id:
        return HttpResponseForbidden("Not allowed")
    rows = Transaction.objects.filter(user=request.user)   # ORM, scoped to the owner
    ...
```

Better still, drop `user_id` from the URL entirely and derive the owner from the session.

**Best practices**

- Enforce access control server-side on **every** request (§6.4.1); never trust a path/query value.
- Deny by default; check ownership for each object (`get_object_or_404(Model, pk=..., user=request.user)`).
- Prefer unpredictable identifiers (UUIDs) so resources can't be enumerated (§6.3.4).
- Add automated tests that assert "user A cannot read user B's data."

### 7.2 SQL Injection

**Fix — never build SQL by string concatenation. Use the ORM, or parameterised queries** where the
driver binds values separately from the SQL text:

```python
# Best: the ORM parameterises automatically
rows = Transaction.objects.filter(user=request.user, category_trans__icontains=q)

# If raw SQL is truly required, bind parameters — do NOT concatenate:
cursor.execute(
    "SELECT trans_id, trans_type, date, amount, category_trans "
    "FROM home_transaction WHERE user_id = %s AND category_trans LIKE %s",
    [request.user.id, f"%{q}%"],
)
```

**Best practices**

- Parameterised queries / prepared statements everywhere (§7.2 — concatenation is the root cause).
- Least-privilege database account (no `DROP`, limited tables).
- Input validation / allow-listing as defence-in-depth (not a substitute for parameterisation).
- Disable detailed error pages in production (`DEBUG = False`) so SQL errors don't leak (§13).

### 7.3 Stored XSS

**Fix — never use `|safe` on user-controlled data.** Let Django auto-escape (the default):

```django
<td>{{ t.category }}</td>   {# auto-escaped: <script> becomes &lt;script&gt; #}
```

**Best practices**

- Rely on contextual output encoding (Django auto-escaping); reserve `|safe`/`mark_safe` for content
  you generate, never user input (§7.3.2).
- Sanitise rich text server-side with a vetted library (e.g. `bleach`) if HTML must be allowed.
- Add a `Content-Security-Policy` header to block inline scripts as defence-in-depth.
- Set `HttpOnly` and `Secure` on session cookies so script-based cookie theft is mitigated.

### 7.4 Hardening observed during the assessment (out of scope but noted)

While mapping the app (§2, §13) the following weaknesses were also observed and should be fixed in a
real deployment: CSRF middleware is disabled in `settings.py` and several views use `@csrf_exempt`;
`DEBUG=True` and `ALLOWED_HOSTS=['*']`; a hard-coded fallback `SECRET_KEY`; and the password-reset
view (`authorized/views.py → reset_password`) sets a new password without running Django's password
validators. These are not part of the three required vulnerabilities but are worth remediating.

---

## 8. Summary

| # | Vulnerability | Detection (Ch.21) | Exploit (Ch.21) | Fix |
|---|---------------|-------------------|-----------------|-----|
| 1 | IDOR | §6.2.2 multi-account test; §6.3.4 guessable IDs | Change `user_id` in URL → read others' data | Authorize via `request.user` |
| 2 | SQL Injection | §7.2.3 single-/double-quote test | §7.2.8 UNION dump of `auth_user` hashes | Parameterised queries / ORM |
| 3 | Stored XSS | §7.3.1 reflected param; §7.3.2.3 browser verify | `<script>` in category name fires on view | Remove `|safe`; auto-escape |

All three were discovered by following Chapter 21's flow — **map → analyse → identify entry points →
hypothesise → test → exploit** — and all three are reproducible against the seeded demo data.
