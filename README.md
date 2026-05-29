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
# Create victim & attacker test accounts
npm run setup

# Then run any exploit:
npm run vul1    # CSRF Email Takeover
npm run vul2    # Stored XSS Data Theft
npm run vul3    # Host Header Injection
npm run vul4    # Full Chain Attack (all combined)
```

---

## Exploits

### `npm run vul1` — CSRF Email Takeover

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

### `npm run vul2` — Stored XSS → Data Theft

| | |
|---|---|
| **Vulnerability** | CWE-79 (Stored XSS) + CWE-352 (CSRF) |
| **Servers** | `http://127.0.0.1:8001` (inject) + `http://127.0.0.1:9001` (receive) |
| **Impact** | Complete financial data exfiltration |

**How it works:**
1. Victim visits the "Feature Survey" phishing page → CSRF creates a malicious account in their profile (the account name IS an XSS payload)
2. Next time victim opens Dashboard → `innerHTML` renders the payload → script loads from attacker's server
3. Script fetches all APIs (accounts, spending, stats) and scrapes the settings page
4. Everything is sent to the attacker's real-time dashboard

**Demo steps:**
1. Log in as `victim` in browser
2. Open `http://127.0.0.1:8001` → survey page (XSS injected)
3. Open Dashboard → XSS fires
4. View stolen data at `http://127.0.0.1:9001/` (attacker dashboard)

---

### `npm run vul3` — Host Header Injection

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
1. Start the capture server: `npm run vul3`
2. In another terminal: `python vul3-poison.py`
3. Check the dashboard at `http://127.0.0.1:8002/`

> **Note:** Email delivery requires MailerSend API key. The PoC demonstrates that the forged Host is accepted and shows what the poisoned link looks like.

---

### `npm run vul4` — Full Chain Attack ☠️

| | |
|---|---|
| **Vulnerability** | CWE-352 + CWE-79 (chained) |
| **Servers** | `http://127.0.0.1:8001` (inject) + `http://127.0.0.1:9001` (receive) |
| **Impact** | **TOTAL ACCOUNT COMPROMISE** |

**How it works — three phases execute simultaneously:**

| Phase | Action | Effect |
|---|---|---|
| 📧 Email Takeover | XSS POSTs to `/settings/` | Email changed to `chain-attacker@evil.com` |
| 💸 Money Drain | XSS POSTs to `/transaction/expense/` | ฿999,999 expense from Cash |
| 🗃️ Data Theft | XSS fetches all APIs | Accounts, transactions, stats stolen |

**Demo steps:**
1. Log in as `victim` in browser
2. Open `http://127.0.0.1:8001` → "Security Update" page
3. Open Dashboard → all three phases execute
4. View results at `http://127.0.0.1:9001/` (chain attack dashboard)

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
| CSRF middleware disabled | `budgy/settings.py` | 50 |
| `@csrf_exempt` on views | `home/views.py` | 156, 194, 283, 367 |
| `innerHTML` with user data | `dashboard.html` | 142, 175 |
| `innerHTML` with user data | `stats.html` | 222 |
| `ALLOWED_HOSTS = ["*"]` | `budgy/settings.py` | 29 |
| `build_absolute_uri()` | `authorized/views.py` | 121 |
