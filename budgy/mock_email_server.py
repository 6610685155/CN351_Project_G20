"""
Mock Email Server for Local Testing (vul4 – Host Header Injection)
──────────────────────────────────────────────────────────────────
Runs two services:
  • SMTP server on 127.0.0.1:1025  — receives emails from Django
  • Web UI    on 127.0.0.1:8025   — browse captured emails in a browser

Usage:
    pip install aiosmtpd
    python mock_email_server.py

Then configure Django settings.py:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = "127.0.0.1"
    EMAIL_PORT = 1025
    EMAIL_USE_TLS = False
"""

import sys
import os

# Fix Windows terminal encoding
if sys.platform == "win32":
    os.system("")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import asyncio
import json
import threading
import email
from email.policy import default as default_policy
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from aiosmtpd.controller import Controller
from aiosmtpd.handlers import Message

# ── Storage ──────────────────────────────────────────────────────
captured_emails = []

# ── ANSI Colors ──────────────────────────────────────────────────
C, G, R, Y, B, X = "\033[96m", "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[0m"


# ── SMTP Handler ─────────────────────────────────────────────────
class EmailHandler(Message):
    def handle_message(self, message):
        mail = {
            "id": len(captured_emails) + 1,
            "time": datetime.now().isoformat(),
            "from": message.get("From", "unknown"),
            "to": message.get("To", "unknown"),
            "subject": message.get("Subject", "(no subject)"),
            "body": "",
        }

        # Extract body
        if message.is_multipart():
            for part in message.walk():
                ctype = part.get_content_type()
                if ctype == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        mail["body"] = payload.decode("utf-8", errors="replace")
                    break
        else:
            payload = message.get_payload(decode=True)
            if payload:
                mail["body"] = payload.decode("utf-8", errors="replace")

        captured_emails.append(mail)

        # Pretty-print to terminal
        print(f"""
{G}{"="*60}
  NEW EMAIL RECEIVED  (#{mail['id']})
{"="*60}{X}

  {B}From:{X}    {C}{mail['from']}{X}
  {B}To:{X}      {C}{mail['to']}{X}
  {B}Subject:{X} {Y}{mail['subject']}{X}
  {B}Time:{X}    {mail['time']}

  {B}Body:{X}
  {"-"*40}
  {mail['body']}
  {"-"*40}
{G}{"="*60}{X}
""")


# ── Web UI Handler ───────────────────────────────────────────────
class WebHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress HTTP request logs

    def do_GET(self):
        if self.path == "/api/emails":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(captured_emails).encode())
            return

        if self.path.startswith("/api/emails/"):
            try:
                eid = int(self.path.split("/")[-1])
                mail = next((m for m in captured_emails if m["id"] == eid), None)
                if mail:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(mail).encode())
                    return
            except ValueError:
                pass
            self.send_response(404)
            self.end_headers()
            return

        # Main page
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(DASHBOARD_HTML.encode())

    def do_DELETE(self):
        if self.path == "/api/emails":
            captured_emails.clear()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"cleared"}')
            return
        self.send_response(404)
        self.end_headers()


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>📧 Mock Email Server — Budgy</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: 'Inter', sans-serif;
      background: #0a0a12;
      color: #e0e0e0;
      min-height: 100vh;
    }

    /* Header */
    .header {
      background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
      border-bottom: 1px solid #2a2a4a;
      padding: 20px 32px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .header h1 {
      font-family: 'JetBrains Mono', monospace;
      font-size: 20px;
      background: linear-gradient(135deg, #6366f1, #8b5cf6, #a855f7);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .header .badge {
      background: #22c55e20;
      color: #22c55e;
      padding: 6px 14px;
      border-radius: 20px;
      font-size: 12px;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .header .badge::before {
      content: '';
      width: 8px; height: 8px;
      background: #22c55e;
      border-radius: 50%;
      animation: pulse 2s ease-in-out infinite;
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.4; }
    }

    /* Toolbar */
    .toolbar {
      padding: 16px 32px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid #1a1a2e;
    }
    .toolbar .info {
      font-size: 13px;
      color: #666;
      font-family: 'JetBrains Mono', monospace;
    }
    .toolbar .info span { color: #8b5cf6; }
    .clear-btn {
      background: #ef444420;
      color: #ef4444;
      border: 1px solid #ef444440;
      padding: 8px 16px;
      border-radius: 8px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
    }
    .clear-btn:hover {
      background: #ef444440;
      transform: scale(1.02);
    }

    /* Layout */
    .container {
      display: flex;
      height: calc(100vh - 120px);
    }

    /* Email List */
    .email-list {
      width: 380px;
      border-right: 1px solid #1a1a2e;
      overflow-y: auto;
    }
    .email-item {
      padding: 16px 24px;
      border-bottom: 1px solid #111118;
      cursor: pointer;
      transition: all 0.15s;
    }
    .email-item:hover { background: #111118; }
    .email-item.active {
      background: #1a1a2e;
      border-left: 3px solid #6366f1;
    }
    .email-item .subject {
      font-weight: 600;
      font-size: 14px;
      margin-bottom: 4px;
      color: #f0f0f0;
    }
    .email-item .meta {
      font-size: 12px;
      color: #555;
      display: flex;
      justify-content: space-between;
    }
    .email-item .to { color: #8b5cf6; }

    /* Email Detail */
    .email-detail {
      flex: 1;
      overflow-y: auto;
      padding: 32px;
    }
    .detail-header {
      margin-bottom: 24px;
      padding-bottom: 20px;
      border-bottom: 1px solid #1a1a2e;
    }
    .detail-header h2 {
      font-size: 22px;
      margin-bottom: 16px;
      color: #f0f0f0;
    }
    .detail-field {
      display: flex;
      gap: 12px;
      margin-bottom: 8px;
      font-size: 13px;
    }
    .detail-field .label {
      color: #555;
      min-width: 60px;
      font-weight: 600;
    }
    .detail-field .value {
      color: #a0a0a0;
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
    }
    .detail-body {
      background: #111118;
      border: 1px solid #1a1a2e;
      border-radius: 12px;
      padding: 24px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 13px;
      line-height: 1.7;
      white-space: pre-wrap;
      word-break: break-all;
      color: #d0d0d0;
    }
    /* Highlight URLs in the body */
    .detail-body a {
      color: #ef4444;
      text-decoration: underline;
      font-weight: 700;
    }

    /* Empty state */
    .empty {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 100%;
      color: #333;
      text-align: center;
      gap: 12px;
    }
    .empty .icon { font-size: 48px; opacity: 0.3; }
    .empty h3 { font-size: 18px; color: #444; }
    .empty p { font-size: 13px; color: #333; max-width: 400px; line-height: 1.6; }
    .empty code {
      background: #111118;
      padding: 4px 10px;
      border-radius: 6px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
      color: #8b5cf6;
    }

    /* Scrollbar */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: #2a2a4a; border-radius: 3px; }
  </style>
</head>
<body>
  <div class="header">
    <h1>📧 Mock Email Server</h1>
    <div class="badge">SMTP :1025 — Listening</div>
  </div>

  <div class="toolbar">
    <div class="info">SMTP: <span>127.0.0.1:1025</span> &nbsp;|&nbsp; Web UI: <span>127.0.0.1:8025</span></div>
    <button class="clear-btn" onclick="clearAll()">🗑 Clear All</button>
  </div>

  <div class="container">
    <div class="email-list" id="emailList"></div>
    <div class="email-detail" id="emailDetail">
      <div class="empty">
        <div class="icon">📭</div>
        <h3>No emails yet</h3>
        <p>Waiting for emails on SMTP port 1025...<br><br>
        Configure Django to send here:<br>
        <code>EMAIL_HOST = "127.0.0.1"</code><br>
        <code>EMAIL_PORT = 1025</code></p>
      </div>
    </div>
  </div>

  <script>
    let emails = [];
    let selectedId = null;

    function linkify(text) {
      return text.replace(/(https?:\\/\\/[^\\s]+)/g, '<a href="$1" target="_blank">$1</a>');
    }

    function timeAgo(iso) {
      const d = new Date(iso);
      return d.toLocaleTimeString();
    }

    function renderList() {
      const el = document.getElementById('emailList');
      if (!emails.length) {
        el.innerHTML = '<div class="empty"><div class="icon">📭</div><h3>Inbox empty</h3></div>';
        return;
      }
      el.innerHTML = emails.slice().reverse().map(m =>
        `<div class="email-item ${selectedId === m.id ? 'active' : ''}" onclick="selectEmail(${m.id})">
          <div class="subject">${m.subject}</div>
          <div class="meta">
            <span class="to">${m.to}</span>
            <span>${timeAgo(m.time)}</span>
          </div>
        </div>`
      ).join('');
    }

    function renderDetail() {
      const el = document.getElementById('emailDetail');
      const m = emails.find(e => e.id === selectedId);
      if (!m) {
        el.innerHTML = `<div class="empty"><div class="icon">👈</div><h3>Select an email</h3></div>`;
        return;
      }
      el.innerHTML = `
        <div class="detail-header">
          <h2>${m.subject}</h2>
          <div class="detail-field"><span class="label">From</span><span class="value">${m.from}</span></div>
          <div class="detail-field"><span class="label">To</span><span class="value">${m.to}</span></div>
          <div class="detail-field"><span class="label">Time</span><span class="value">${m.time}</span></div>
        </div>
        <div class="detail-body">${linkify(m.body)}</div>
      `;
    }

    function selectEmail(id) {
      selectedId = id;
      renderList();
      renderDetail();
    }

    async function poll() {
      try {
        const r = await fetch('/api/emails');
        const data = await r.json();
        const changed = data.length !== emails.length;
        emails = data;
        if (changed) {
          if (!selectedId && emails.length) selectedId = emails[emails.length - 1].id;
          renderList();
          renderDetail();
        }
      } catch(e) {}
    }

    async function clearAll() {
      await fetch('/api/emails', { method: 'DELETE' });
      emails = [];
      selectedId = null;
      renderList();
      renderDetail();
    }

    poll();
    setInterval(poll, 2000);
  </script>
</body>
</html>
"""


def run_web_ui(port=8025):
    """Run the web UI in a separate thread."""
    server = HTTPServer(("127.0.0.1", port), WebHandler)
    server.serve_forever()


def main():
    smtp_port = 1025
    web_port = 8025

    print(f"""
{R}{"="*60}
  Mock Email Server for Budgy (vul4 testing)
{"="*60}{X}

  {B}SMTP Server:{X}  {C}127.0.0.1:{smtp_port}{X}   (receives emails)
  {B}Web UI:{X}       {C}http://127.0.0.1:{web_port}{X}  (view in browser)

  {Y}{B}DJANGO SETTINGS:{X}
  Add this to {C}settings.py{X}:

    {G}EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = "127.0.0.1"
    EMAIL_PORT = {smtp_port}
    EMAIL_USE_TLS = False
    EMAIL_HOST_USER = ""
    EMAIL_HOST_PASSWORD = ""{X}

  {Y}{B}HOW TO TEST VUL4:{X}
  {Y}1.{X} Keep this server running
  {Y}2.{X} Start Budgy:  {C}python manage.py runserver{X}
  {Y}3.{X} Start capture: {C}node vul4-host-header.js{X}
  {Y}4.{X} Run exploit:   {C}python vul4-poison.py{X}
  {Y}5.{X} Check this web UI -- the email will contain a poisoned link
     pointing to the attacker's server ({R}127.0.0.1:8002{X})

{R}{"="*60}{X}

  {Y}Listening for emails...{X}
""")

    # Start web UI in background thread
    web_thread = threading.Thread(target=run_web_ui, args=(web_port,), daemon=True)
    web_thread.start()

    # Start SMTP server (blocking)
    controller = Controller(
        EmailHandler(),
        hostname="127.0.0.1",
        port=smtp_port,
    )
    controller.start()

    try:
        # Keep the main thread alive
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_forever()
    except KeyboardInterrupt:
        print(f"\n  {Y}Shutting down...{X}")
        controller.stop()


if __name__ == "__main__":
    main()
