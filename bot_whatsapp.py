"""
bot_whatsapp.py

Simple Flask app to respond to WhatsApp messages via Twilio webhook.
It uses ai_core.Answerer to generate replies.

Usage:
 - Copy `.env.example` to `.env` and fill TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER
 - Expose this app to the internet (ngrok or a VPS) and set the Twilio Messaging webhook to the /whatsapp route.
 - python bot_whatsapp.py
"""

import os
from dotenv import load_dotenv
from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
import logging
try:
    from .ai_core import Answerer
    from .zac_bot import ensure_db, handle_command, handle_text, has_active_session
except ImportError:
    from ai_core import Answerer
    from zac_bot import ensure_db, handle_command, handle_text, has_active_session
from logging_config import configure_logging
try:
    from .message_queue import enqueue_message, start_workers
except ImportError:
    from message_queue import enqueue_message, start_workers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")

configure_logging()
start_workers()
app = Flask(__name__)
answerer = Answerer()
ensure_db()


@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    # Twilio posts form-encoded data with the user's message in Body
    body = request.form.get("Body", "")
    from_number = request.form.get("From", "")
    logger.info("Message from %s: %s", from_number, body)

    resp = MessagingResponse()
    if not body:
        resp.message("I didn't receive your message. Please send a question.")
        return Response(str(resp), mimetype="application/xml")

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

    cmd_resp = handle_command(from_number, normalized)
    if cmd_resp is not None:
        resp.message(cmd_resp)
        return Response(str(resp), mimetype="application/xml")

    if has_active_session(from_number):
        resp.message(handle_text(from_number, body))
        return Response(str(resp), mimetype="application/xml")

    # enqueue for background processing; reply immediately to webhook
    job = {
        "platform": "whatsapp",
        "to": from_number,
        "text": body,
    }
    status = enqueue_message(job)
    job_id = status.get("job_id")
    eta = status.get("eta_seconds", 0)
    resp.message(
        f"Received (job {job_id}). " f"Estimated reply in ~{eta} seconds."
    )
    return Response(str(resp), mimetype="application/xml")


if __name__ == "__main__":
    host = os.getenv("SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("SERVER_PORT", 5000))
    logger.info("Starting Flask app on %s:%s", host, port)
    app.run(host=host, port=port)
