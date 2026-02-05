# chat_agents

[![CI](https://github.com/THA011/Telegram-whatsApp_Chat_agents/actions/workflows/ci.yml/badge.svg)](https://github.com/THA011/Telegram-whatsApp_Chat_agents/actions/workflows/ci.yml)

This project contains two small messaging agents (Telegram and WhatsApp) that reply to user messages using a lightweight local answer engine.

Goals
- Build a pragmatic, privacy-friendly local responder that can be extended to use external LLMs if desired.
- Provide a simple, production-friendly template for Telegram (polling) and WhatsApp (Twilio webhook).
- Provide a SACCO onboarding + loan intake assistant MVP with OTP, profile capture, and basic pre-approval hints.

What is included
- `ai_core.py` — a TF-IDF based answerer that searches `kb.txt` for matching sentences.
- `faq.md` — FAQ-style knowledge base using simple Q/A markdown; edit this file to add domain-specific questions and answers.
- `bot_telegram.py` — telegram polling bot; replies using `ai_core.Answerer`.
- `bot_whatsapp.py` — Flask webhook for Twilio (WhatsApp); replies using `ai_core.Answerer`.
- `zac_bot.py` — SACCO flows (registration, onboarding, OTP, balance, loans).
- `db.py` — local SQLite storage for users, loans, OTPs, and onboarding profiles.
- `.env.example` — example environment variables for tokens and Twilio configuration.
- `requirements.txt` — Python packages required to run the project.

Quick start

1) Create and activate a virtual environment, then install dependencies

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt
```

2) Configure credentials

- Copy `.env.example` to `.env` and set `TELEGRAM_TOKEN` and the Twilio values if you want WhatsApp support.

3) Edit `kb.txt` to include common questions and short answers you want the responder to give.

4) Run the Telegram bot (local polling)

```powershell
python bot_telegram.py
```

Quick polling alternative (no external deps)

```powershell
# Uses the lightweight quick_poll_bot.py (no python-telegram-bot required)
$env:TELEGRAM_TOKEN = "<YOUR_TOKEN>"
python quick_poll_bot.py
```

5) Run the WhatsApp webhook (Flask)

```powershell
python bot_whatsapp.py
- `zac_bot.py` — SACCO flows (registration, onboarding, OTP, balance, loans).
- `db.py` — local SQLite storage for users, loans, OTPs, and onboarding profiles.
```

Tip: To receive Twilio webhooks locally, use `ngrok` to expose the Flask server and configure the Twilio webhook URL to `https://<your-ngrok>.ngrok.io/whatsapp`.

Production (Docker)
-------------------

1. Copy `.env.example` to `.env` and fill your secrets (do NOT commit `.env`).
2. Build & run:

```powershell
docker-compose up --build -d
```

3. Confirm the service is healthy:

```powershell
docker-compose ps
docker-compose logs web --tail=50
```

Set bot commands and profile (optional)
-------------------------------------

Use the helper script to register `/start` and `/help` and to set a display name/description:

```powershell
$env:TELEGRAM_TOKEN = "<YOUR_TOKEN>"
python scripts/set_bot_commands.py --name "Zac Support" --description "Support and quick FAQs — contact +254758577236"
```

Design notes
- The `Answerer` is intentionally simple (TF-IDF + nearest match). It is deterministic, fast, and runs offline.

Security and privacy
- This implementation does not forward user messages to third-party language services. If you later integrate an external API, document that change and obtain any required permissions from users.

---

## Usage examples 🧭

### OTP (one-time password) flow
- Register a user (PIN or phone):

```python
from chat_agents import db, zac_bot, auth
# create user programmatically for testing
salt, h = auth.make_pin_hash("1234")
uid = db.create_user(chat_id="dev-user", phone="whatsapp:+1234567890", pin_salt=salt, pin_hash=h)
```

- Generate and send an OTP (dev: returns code when Twilio is not configured):

```python
from chat_agents import zac_bot
zac_bot.send_otp_cmd("dev-user")  # returns "OTP (dev): 123456" when Twilio not configured
```

- Verify OTP:

```python
zac_bot.verify_otp_cmd("dev-user", "123456")

### SACCO onboarding flow
- Start onboarding and capture profile details:

```python
  from chat_agents import zac_bot
  zac_bot.start_onboarding("dev-user")
  # then send messages in sequence: name, national ID, employer, income, consent
  ```
  
  ### Running the worker
- Run the in-process worker locally (recommended for development):

```powershell
python -m chat_agents.worker
```

- Or with Docker Compose (starts `web`, `worker`, and `redis`):

```powershell
docker-compose up --build -d
```

### Running system smoke tests
- Run the dedicated smoke test to verify OTP worker/send integration (uses mocked Twilio):

```powershell
python -m pytest chat_agents/tests/test_system_smoke.py -q
```

- Run the full test-suite:

```powershell
python -m pytest -q
```

---

## Security review 🔒

**What we already do:**
- OTPs are stored as server-side HMAC-hashes (uses `OTP_SECRET`, defaults to `otp-secret` in dev) rather than plaintext.
- OTPs have a configurable expiry (default 5 minutes).
- Twilio sending is a no-op when credentials are not present to avoid accidental external messages during development.

**Risks & recommended mitigations:**
- Secrets management: never commit `.env`. Use CI secrets (GitHub Actions Secrets) and environment management for production.
- Rate limiting: add per-user rate limits (e.g., 3 OTPs per hour) and short lockouts to prevent abuse and brute-force attempts.
- OTP verification hardening: enforce attempt limits and exponential backoff, log suspicious activity, and notify admins for repeated failures.
- Storage & encryption: consider encrypting the database at rest or using a managed DB with encryption for production.
- Logging hygiene: avoid writing secrets (OTPs, full tokens) into logs or error messages; mask any partial identifiers.
- Transport security: ensure webhook endpoints (WhatsApp/Twilio) are served over TLS in production and validate Twilio signatures for incoming webhooks.
- Rotation & monitoring: rotate `TWILIO_*` and `OTP_SECRET` periodically and monitor sending failures and error rates.

**Dev behavior note:** In development, OTP codes are returned when Twilio is not configured (for convenience). In production, you must set Twilio env vars and disable dev fallbacks.

---

## Final system test & wrap-up ✅

- I added a **system smoke test** `chat_agents/tests/test_system_smoke.py` that creates a user, generates an OTP, and verifies end-to-end message delivery via the worker using a mocked Twilio client.
- Run the smoke test locally (see "Running system smoke tests" above). If it passes, the codebase is functionally integrated for the OTP + worker flow.

If you'd like, I can now push these changes to GitHub and open a PR to run CI (black/flake8/mypy/pytest/pip-audit/CodeQL/Trivy) — please confirm and grant permission to push, or tell me which branch name to use.


