"""OTP generation and sending utilities (Twilio-backed when configured)."""
import os
import hmac
import hashlib
import random
from datetime import datetime, timedelta
from typing import Tuple

try:
    from .db import create_otp_for_user, consume_otp
except ImportError:
    from db import create_otp_for_user, consume_otp

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.environ.get("TWILIO_WHATSAPP_NUMBER")


def _hash_code(code: str) -> str:
    # simple HMAC-ish hash for storage; use server-side secret if available
    secret = os.environ.get("OTP_SECRET", "otp-secret")
    return hmac.new(secret.encode("utf-8"), code.encode("utf-8"), hashlib.sha256).hexdigest()


def generate_code() -> str:
    return f"{random.randint(0, 999999):06d}"


def create_and_store_otp(chat_id: str, lifetime_seconds: int = 300) -> Tuple[str, int]:
    code = generate_code()
    code_hash = _hash_code(code)
    expires_at = (datetime.utcnow() + timedelta(seconds=lifetime_seconds)).isoformat()
    rowid = create_otp_for_user(chat_id, code_hash, expires_at)
    return code, rowid


def verify_otp(chat_id: str, code: str) -> bool:
    code_hash = _hash_code(code)
    return consume_otp(chat_id, code_hash)


def send_via_twilio(to_number: str, body: str) -> bool:
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN):
        return False
    try:
        from twilio.rest import Client

        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        # If sending WhatsApp, ensure to_number is in "whatsapp:+<number>" format and use TWILIO_WHATSAPP_NUMBER
        if to_number.startswith("whatsapp:") and TWILIO_WHATSAPP_NUMBER:
            from_num = f"whatsapp:{TWILIO_WHATSAPP_NUMBER}"
            client.messages.create(body=body, from_=from_num, to=to_number)
        else:
            # SMS
            client.messages.create(body=body, from_=os.environ.get("TWILIO_PHONE_NUMBER"), to=to_number)
        return True
    except Exception:
        return False
