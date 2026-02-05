import os
import json
from datetime import datetime
from flask import Flask, request, jsonify, abort
import requests
import logging
from logging.config import dictConfig
try:
    from .ai_core import AnswerEngine
except ImportError:
    from ai_core import AnswerEngine
from redis import Redis
from twilio.request_validator import RequestValidator
from twilio.rest import Client as TwilioClient
try:
    from .zac_bot import ensure_db, handle_command, handle_text, has_active_session
except ImportError:
    from zac_bot import ensure_db, handle_command, handle_text, has_active_session

# -------------------------
# Basic logging configuration
# -------------------------
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
dictConfig(
    {
        "version": 1,
        "formatters": {
            "default": {"format": "%(asctime)s - %(levelname)s - %(message)s"}
        },
        "handlers": {"w": {"class": "logging.StreamHandler", "formatter": "default"}},
        "root": {"level": LOG_LEVEL, "handlers": ["w"]},
    }
)
logger = logging.getLogger(__name__)

# -------------------------
# Environment & clients
# -------------------------
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN") or os.environ.get(
    "TELEGRAM_BOT_TOKEN"
)
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = os.environ.get("TWILIO_WHATSAPP_FROM") or os.environ.get(
    "TWILIO_WHATSAPP_NUMBER"
)
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

twilio_client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

try:
    redis_client = Redis.from_url(REDIS_URL, decode_responses=True)
    redis_client.ping()
    logger.info("Connected to Redis.")
except Exception as e:
    redis_client = None
    logger.warning(f"Redis not available: {e}")

app = Flask(__name__)
answer_engine = AnswerEngine(redis_client=redis_client)  # uses ai_core.py
ensure_db()

# -------------------------
# Helpers: conversation memory
# -------------------------
MAX_MEMORY_TURNS = int(os.environ.get("MAX_MEMORY_TURNS", 6))


def mem_key(channel, chat_id):
    return f"conv:{channel}:{chat_id}"


def push_memory(channel, chat_id, role, text):
    if not redis_client:
        return
    key = mem_key(channel, chat_id)
    entry = json.dumps(
        {"role": role, "text": text, "ts": datetime.utcnow().isoformat()}
    )
    redis_client.rpush(key, entry)
    redis_client.ltrim(key, -MAX_MEMORY_TURNS * 2, -1)


def get_memory(channel, chat_id):
    if not redis_client:
        return []
    key = mem_key(channel, chat_id)
    items = redis_client.lrange(key, 0, -1)
    return [json.loads(i) for i in items]


# -------------------------
# Telegram webhook
# -------------------------
@app.route("/webhook/telegram", methods=["POST"])
def telegram_webhook():
    payload = request.get_json(force=True)
    logger.debug(f"Telegram payload: {payload}")
    if "message" not in payload:
        logger.debug("No message in payload.")
        return ("", 204)

    msg = payload["message"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "").strip()

    if not text:
        reply_text = "Only text messages are supported."
    else:
        cmd_resp = handle_command(str(chat_id), text)
        if cmd_resp is not None:
            reply_text = cmd_resp
        elif has_active_session(str(chat_id)):
            reply_text = handle_text(str(chat_id), text)
        else:
            mem = get_memory("telegram", chat_id)
            reply_text = answer_engine.answer(user_text=text, memory=mem)
            push_memory("telegram", chat_id, "user", text)
            push_memory("telegram", chat_id, "assistant", reply_text)

    send_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(send_url, json={"chat_id": chat_id, "text": reply_text})
        logger.debug(f"Telegram sendMessage status: {resp.status_code}")
    except Exception:
        logger.exception("Failed to send message to Telegram.")
    return ("", 200)


# -------------------------
# Twilio (WhatsApp) webhook with validation
# -------------------------
@app.route("/webhook/whatsapp", methods=["POST"])
def whatsapp_webhook():
    # validate request signature if credentials present
    if TWILIO_AUTH_TOKEN and TWILIO_ACCOUNT_SID:
        validator = RequestValidator(TWILIO_AUTH_TOKEN)
        signature = request.headers.get("X-Twilio-Signature", "")
        url = request.url
        post_vars = request.form.to_dict()
        if not validator.validate(url, post_vars, signature):
            logger.warning("Twilio signature validation failed.")
            return abort(403)

    from_number = request.form.get("From")
    body = request.form.get("Body", "").strip()
    chat_id = from_number

    if not body:
        reply_text = "Only text messages are supported on WhatsApp."
    else:
        normalized = body
        lowered = body.lower()
        if not body.startswith("/"):
            if lowered in ("register", "onboard", "profile", "balance", "loans"):
                normalized = f"/{lowered}"
            elif lowered in ("apply loan", "loan"):
                normalized = "/apply_loan"
            elif lowered == "send otp":
                normalized = "/send_otp"
            elif lowered.startswith("verify otp"):
                code = lowered.replace("verify otp", "").strip()
                normalized = f"/verify_otp {code}" if code else "/verify_otp"

        cmd_resp = handle_command(str(chat_id), normalized)
        if cmd_resp is not None:
            reply_text = cmd_resp
        elif has_active_session(str(chat_id)):
            reply_text = handle_text(str(chat_id), body)
        else:
            mem = get_memory("whatsapp", chat_id)
            reply_text = answer_engine.answer(user_text=body, memory=mem)
            push_memory("whatsapp", chat_id, "user", body)
            push_memory("whatsapp", chat_id, "assistant", reply_text)

    if twilio_client:
        try:
            twilio_client.messages.create(
                body=reply_text, from_=TWILIO_WHATSAPP_FROM, to=from_number
            )
        except Exception:
            logger.exception("Failed to send Twilio WhatsApp message.")
            return ("", 500)
    else:
        logger.info("Twilio client not configured; skipping send.")
    return ("", 204)


# -------------------------
# Health + Ready endpoints
# -------------------------
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
