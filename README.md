# chat_agents

This project contains two small messaging agents (Telegram and WhatsApp) that reply to user messages using a lightweight local answer engine.

Goals
- Build a pragmatic, privacy-friendly local responder that can be extended to use external LLMs if desired.
- Provide a simple, production-friendly template for Telegram (polling) and WhatsApp (Twilio webhook).

What is included
- `ai_core.py` — a TF-IDF based answerer that searches `kb.txt` for matching sentences.
- `kb.txt` — sample knowledge base (plain sentences); edit this file to add domain-specific answers.
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

5) Run the WhatsApp webhook (Flask)

```powershell
python bot_whatsapp.py
```

Tip: To receive Twilio webhooks locally, use `ngrok` to expose the Flask server and configure the Twilio webhook URL to `https://<your-ngrok>.ngrok.io/whatsapp`.

Design notes
- The `Answerer` is intentionally simple (TF-IDF + nearest match). It is deterministic, fast, and runs offline.

Security and privacy
- This implementation does not forward user messages to third-party language services. If you later integrate an external API, document that change and obtain any required permissions from users.

Final recommendations
- Populate `kb.txt` with concise question-and-answer pairs. Short, precise sentences improve match quality.
- Keep secrets out of source control. Copy `.env.example` to `.env` locally and never commit the `.env` file.
- Run the services first on a development host and verify behaviour using test phone numbers or a Telegram test chat.
- Add lightweight logging to a local file (rotating daily) so you can audit incoming messages and responses.
- Add a small test suite for `ai_core.Answerer` (unit tests that assert expected answers for representative queries).
- If you need higher throughput later, introduce a message queue and worker pool so webhooks return quickly and workers process answers asynchronously.

These steps are practical next actions to make the project reliable and maintainable in a small team or solo environment.
