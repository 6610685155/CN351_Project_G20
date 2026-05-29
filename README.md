# 🔴 Budgy Exploit Toolkit
## Members
1.Athichart Penwong 6610685015\
2.Krittin Dansai 6610685031\
3.Natthasit Thitithammakun 6610685155\
4.Supawich Boonpraseart 6610685346

**Authorized security testing for CN351 course project.**

Four PoC exploit servers demonstrating critical vulnerabilities in the Budgy Django web app. Each exploit is a self-contained Node.js + Express server with a realistic phishing page.

## Prerequisites

```bash
# Budgy must be running (follows the instruction inside budgy/README.md)
cd budgy && python manage.py runserver     # → http://127.0.0.1:8000

# Install exploit dependencies (one time)
cd exploits && npm install
```

## Quick Start

```bash
# Seed demo users (alice, bob, admin) with sample transactions
cd budgy
python manage.py shell -c "exec(open('seed_demo.py').read())"

# Then run any exploit:
npm run vul1    # SQL Injection (Credential Dump)
npm run vul2    # Stored XSS Data Theft
npm run vul3    # CSRF Email Takeover
npm run vul4    # Host Header Injection
```

---

## Exploits

### `npm run vul1` — SQL Injection (§2.1)

| | |
|---|---|
| **Vulnerability** | CWE-89 — SQL Injection |
| **Server** | `http://127.0.0.1:8003` (auto-runs attack + dashboard) |
| **Impact** | Full database read — all credentials, emails, tables dumped |

**How it works:**
1. The `transaction_history()` view concatenates the `q` parameter directly into raw SQL
2. The exploit sends payloads through `/<id>/transactions/?q=<payload>`
3. Six phases execute automatically:

| Phase | Payload | Result |
|---|---|---|
| Detection | `?q='` | HTTP 500 OperationalError |
| Boolean bypass | `?q=%' OR '1'='1' --` | All users' transactions returned |
| Credential dump | `UNION SELECT ... FROM auth_user` | Usernames + PBKDF2 hashes |
| Table enumeration | `UNION SELECT ... FROM sqlite_master` | All database tables listed |
| Email dump | `UNION SELECT ... email FROM auth_user` | All user emails |
| IDOR | Access `/<other_id>/transactions/` | Other users' data without authz |

**Demo steps:**
1. Make sure Budgy is running with seeded data
2. Run `npm run vul1` — attack auto-executes and results print to terminal
3. View dashboard at `http://127.0.0.1:8003`

---

### `npm run vul2` — Stored XSS → Data Theft (§2.2)

| | |
|---|---|
| **Vulnerability** | CWE-79 (Stored XSS) + CWE-352 (CSRF) |
| **Servers** | `http://127.0.0.1:8001` (inject) + `http://127.0.0.1:9001` (receive) |
| **Impact** | Complete financial data exfiltration |

**How it works:**
1. Victim visits the "Feature Survey" phishing page → CSRF creates a malicious account in their profile (the account name IS an XSS payload: `<img src=x onerror="...">`)
2. Next time victim opens Dashboard → `innerHTML` renders the payload → script loads from attacker's server
3. Script fetches all APIs (accounts, spending, stats) and scrapes the settings page
4. Everything is sent to the attacker's real-time dashboard

**Demo steps:**
1. Log in as `victim` in browser
2. Open `http://127.0.0.1:8001` → survey page (XSS injected)
3. Open Dashboard → XSS fires
4. View stolen data at `http://127.0.0.1:9001/` (attacker dashboard)

---

### `npm run vul3` — CSRF Email Takeover (§2.3)

| | |
|---|---|
| **Vulnerability** | CWE-352 — Cross-Site Request Forgery |
| **Server** | `http://127.0.0.1:8001` |
| **Impact** | Full account takeover |

**How it works:**
1. Victim visits the "Budgy Rewards" phishing page
2. A hidden form auto-submits to `/settings/` — changing the victim's email to `attacker-csrf@evil.com`
3. Attacker uses "Forgot Password" → receives reset link → takeover

**Demo steps:**
1. Log in as `victim` in your browser
2. Open `http://127.0.0.1:8001` in the same browser
3. Check Settings → email is now the attacker's

---

### `npm run vul4` — Host Header Injection (§2.4)

| | |
|---|---|
| **Vulnerability** | CWE-640 — Host Header Injection |
| **Server** | `http://127.0.0.1:8002` (token capture) |
| **Impact** | Account takeover via password reset poisoning |

**How it works:**
1. Attacker sends a forgot-password request with `Host: 127.0.0.1:8002`
2. Budgy builds the reset link using the forged Host → `http://127.0.0.1:8002/reset/<uid>/<token>/`
3. Victim receives email with the poisoned link
4. Victim clicks → token arrives at attacker's server
5. Attacker replays the token on the real Budgy server

**Demo steps:**
1. Start the capture server: `npm run vul4`
2. In another terminal: `python vul4-poison.py`
3. Check the dashboard at `http://127.0.0.1:8002/`

> **Note:** Email delivery requires MailerSend API key. The PoC demonstrates that the forged Host is accepted and shows what the poisoned link looks like.

---

## Architecture

```
┌─────────────────────┐     CSRF (same-site)     ┌──────────────────┐
│  Phishing Server    │ ─────────────────────────▶│  Budgy App       │
│  127.0.0.1:8001     │  Hidden form auto-submit  │  127.0.0.1:8000  │
│  (attacker-hosted)  │                           │  (victim's app)  │
└─────────────────────┘                           └────────┬─────────┘
                                                           │ XSS fires
                                                           │ on Dashboard
                                                           ▼
┌─────────────────────┐     Exfiltrate data       ┌──────────────────┐
│  Attacker Dashboard │ ◀─────────────────────────│  XSS Payload     │
│  127.0.0.1:9001     │  fetch() from victim's    │  (runs in victim │
│  (data receiver)    │  authenticated session    │   browser context)│
└─────────────────────┘                           └──────────────────┘
```

## Why These Attacks Work

| Root Cause | File | Line |
|---|---|---|
| Raw SQL concatenation | `home/views.py` | 498–504 |
| `{{ t.category\|safe }}` | `transaction_history.html` | 65 |
| `innerHTML` with user data | `dashboard.html` | 142, 175 |
| `innerHTML` with user data | `stats.html` | 222 |
| CSRF middleware disabled | `budgy/settings.py` | 50 |
| `@csrf_exempt` on views | `home/views.py` | 157, 195, 284, 368 |
| `ALLOWED_HOSTS = ["*"]` | `budgy/settings.py` | 29 |
| `build_absolute_uri()` | `authorized/views.py` | 121 |
