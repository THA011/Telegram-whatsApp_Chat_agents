# chat_agents

[![CI](https://github.com/THA011/Telegram-whatsApp_Chat_agents/actions/workflows/ci.yml/badge.svg)](https://github.com/THA011/Telegram-whatsApp_Chat_agents/actions/workflows/ci.yml)

This project contains two small messaging agents (Telegram and WhatsApp) that reply to user messages using a lightweight local answer engine.

Goals
- Build a pragmatic, privacy-friendly local responder that can be extended to use external LLMs if desired.
- Provide a simple, production-friendly template for Telegram (polling) and WhatsApp (Twilio webhook).

What is included
- `ai_core.py` — a TF-IDF based answerer that searches `kb.txt` for matching sentences.
- `faq.md` — FAQ-style knowledge base using simple Q/A markdown; edit this file to add domain-specific questions and answers.
- `bot_telegram.py` — telegram polling bot; replies using `ai_core.Answerer`.
- `bot_whatsapp.py` — Flask webhook for Twilio (WhatsApp); replies using `ai_core.Answerer`.
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


