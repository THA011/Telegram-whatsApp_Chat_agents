"""Minimal Zac sacco credit bot handlers (PIN auth + onboarding + /balance + /apply_loan).

This is intentionally simple and uses in-process session state for conversation flows.
"""
from typing import Dict, Optional, Tuple
import logging

try:
    from .ai_core import AnswerEngine
    from .db import (
        init_db,
        get_user_by_chat,
        create_user,
        get_balance,
        create_loan,
        list_loans,
        upsert_profile,
        get_profile,
    )
    from .auth import make_pin_hash, verify_pin
except ImportError:
    from ai_core import AnswerEngine
    from db import (
        init_db,
        get_user_by_chat,
        create_user,
        get_balance,
        create_loan,
        list_loans,
        upsert_profile,
        get_profile,
    )
    from auth import make_pin_hash, verify_pin

logger = logging.getLogger(__name__)

# in-memory sessions: chat_id -> session dict
_sessions: Dict[str, Dict] = {}


def ensure_db():
    init_db()


def start_register(chat_id: str) -> str:
    _sessions[chat_id] = {"state": "awaiting_pin_or_phone"}
    return "To register, reply with either a 4-6 digit PIN or send your phone number to enable OTP login."


def handle_pin_submission(chat_id: str, text: str) -> str:
    s = _sessions.get(chat_id, {})
    if len(text.strip()) < 4 or len(text.strip()) > 6 or not text.strip().isdigit():
        return "Please send a 4-6 digit numeric PIN."
    salt, h = make_pin_hash(text.strip())
    # create user
    create_user(chat_id=str(chat_id), phone=None, pin_salt=salt, pin_hash=h)
    s.update({"state": "registered"})
    return "Registration successful. You can now use /balance and /apply_loan."


def handle_phone_submission(chat_id: str, text: str) -> str:
    # allow user to provide phone number; store it on user if exists
    try:
        from .db import _conn
    except ImportError:
        from db import _conn

    phone = text.strip()
    u = get_user_by_chat(str(chat_id))
    if not u:
        # create ephemeral user with phone - PIN still required for security
        salt, h = make_pin_hash("0000")
        user_id = create_user(chat_id=str(chat_id), phone=phone, pin_salt=salt, pin_hash=h)
        return "Phone saved. You can request an OTP with /send_otp. Please set a proper PIN later using /register."
    else:
        with _conn() as c:
            cur = c.cursor()
            cur.execute("UPDATE users SET phone = ? WHERE id = ?", (phone, u["id"]))
            c.commit()
        return "Phone updated. You can request an OTP with /send_otp."


def require_registered(chat_id: str) -> bool:
    return get_user_by_chat(str(chat_id)) is not None


def start_onboarding(chat_id: str) -> str:
    _sessions[chat_id] = {"state": "onboard_name"}
    return "Welcome to Zac SACCO onboarding. What is your full name?"


def _set_onboarding_value(chat_id: str, field: str, value: str):
    s = _sessions.get(chat_id, {})
    s[field] = value
    _sessions[chat_id] = s


def handle_onboarding(chat_id: str, text: str) -> str:
    s = _sessions.get(chat_id, {})
    state = s.get("state")

    if state == "onboard_name":
        name = text.strip()
        if len(name) < 3:
            return "Please enter your full name (at least 3 characters)."
        _set_onboarding_value(chat_id, "full_name", name)
        s["state"] = "onboard_national_id"
        return "Thanks. Please enter your national ID number."

    if state == "onboard_national_id":
        nid = text.strip()
        if len(nid) < 5:
            return "Please enter a valid national ID number."
        _set_onboarding_value(chat_id, "national_id", nid)
        s["state"] = "onboard_employer"
        return "Who is your employer (or 'self-employed')?"

    if state == "onboard_employer":
        employer = text.strip()
        if len(employer) < 2:
            return "Please enter your employer name."
        _set_onboarding_value(chat_id, "employer", employer)
        s["state"] = "onboard_income"
        return "What is your estimated monthly income in KES?"

    if state == "onboard_income":
        raw = text.strip().replace(",", "")
        try:
            income = float(raw)
            if income <= 0:
                return "Please enter a positive income amount."
        except Exception:
            return "Please enter a numeric income amount."
        _set_onboarding_value(chat_id, "monthly_income", income)
        s["state"] = "onboard_consent"
        return "Do you consent to storing this info for SACCO onboarding? Reply YES or NO."

    if state == "onboard_consent":
        consent = text.strip().lower()
        if consent not in ("yes", "no"):
            return "Please reply YES or NO."
        u = get_user_by_chat(str(chat_id))
        if not u:
            return "You are not registered yet. Use /register first."
        upsert_profile(
            user_id=u["id"],
            full_name=s.get("full_name"),
            national_id=s.get("national_id"),
            employer=s.get("employer"),
            monthly_income=float(s.get("monthly_income", 0)),
            consent=1 if consent == "yes" else 0,
        )
        _sessions.pop(chat_id, None)
        if consent == "yes":
            return "Onboarding complete. You can now apply for a loan with /apply_loan."
        return "Onboarding saved, but consent not granted. You can still use /balance and basic features."

    return "Onboarding state invalid. Please start with /onboard."


def handle_balance(chat_id: str) -> str:
    bal = get_balance(str(chat_id))
    if bal is None:
        return "You are not registered. Use /register to create an account."
    return f"Your balance is: KES {bal:.2f}"


def start_apply_loan(chat_id: str) -> str:
    _sessions[chat_id] = {"state": "awaiting_loan_amount"}
    return "How much would you like to borrow? (enter a number in KES)"


def handle_loan_amount(chat_id: str, text: str) -> str:
    try:
        amt = float(text.strip())
        if amt <= 0:
            return "Please enter a positive amount."
    except Exception:
        return "Please enter a numeric amount."
    _sessions[chat_id] = {"state": "awaiting_loan_reason", "amount": amt}
    return "Please briefly state the reason for the loan."


def handle_loan_reason(chat_id: str, text: str) -> str:
    s = _sessions.get(chat_id, {})
    amt = s.get("amount")
    if amt is None:
        return "Loan amount missing; please start with /apply_loan."
    loan_id = create_loan(str(chat_id), float(amt), text.strip())
    _sessions.pop(chat_id, None)
    if loan_id:
        profile = get_profile_by_chat(chat_id)
        limit_hint = ""
        if profile and profile.get("monthly_income", 0) > 0:
            limit = profile["monthly_income"] * 1.5
            limit_hint = f" Based on your income, a typical pre-approval limit is ~KES {limit:,.0f}."
        return f"Loan request submitted (id: {loan_id}) and is pending approval.{limit_hint}"
    else:
        return "Could not create loan. Are you registered? Use /register to create an account."


def handle_text(chat_id: str, text: str) -> str:
    s = _sessions.get(chat_id, {})
    state = s.get("state")
    if state and state.startswith("onboard_"):
        return handle_onboarding(chat_id, text)
    if state == "awaiting_pin_or_phone":
        # determine phone vs PIN
        if text.strip().isdigit() and 4 <= len(text.strip()) <= 6:
            return handle_pin_submission(chat_id, text)
        return handle_phone_submission(chat_id, text)
    if state == "awaiting_pin":
        return handle_pin_submission(chat_id, text)
    if state == "awaiting_loan_amount":
        return handle_loan_amount(chat_id, text)
    if state == "awaiting_loan_reason":
        return handle_loan_reason(chat_id, text)
    # default fallback
    ae = AnswerEngine()
    res = ae.answer(text)
    return res if isinstance(res, str) else res.get("answer")


def get_loans(chat_id: str) -> str:
    loans = list_loans(str(chat_id))
    if not loans:
        return "No loans found."
    lines = [f"#{l['id']}: KES {l['amount']} - {l['status']} ({l['created_at']})" for l in loans]
    return "\n".join(lines)

# OTP commands

def send_otp_cmd(chat_id: str) -> str:
    u = get_user_by_chat(str(chat_id))
    if not u or not u.get("phone"):
        return "No phone number on file; send your phone number first."
    # create OTP and attempt to send via Twilio; if not configured, return code (for dev)
    try:
        from .otp import create_and_store_otp, send_via_twilio
    except ImportError:
        from otp import create_and_store_otp, send_via_twilio

    code, _ = create_and_store_otp(str(chat_id))
    # try to send via Twilio (WhatsApp if configured)
    to = u.get("phone")
    sent = send_via_twilio(to, f"Your Zac OTP: {code}")
    if sent:
        return "OTP sent via configured Twilio channel."
    return f"OTP (dev): {code}"


def verify_otp_cmd(chat_id: str, code: str) -> str:
    try:
        from .otp import verify_otp
    except ImportError:
        from otp import verify_otp

    ok = verify_otp(str(chat_id), code)
    if ok:
        return "OTP verified. You are authenticated."
    return "Invalid or expired OTP."


def get_profile_by_chat(chat_id: str) -> Optional[dict]:
    u = get_user_by_chat(str(chat_id))
    if not u:
        return None
    return get_profile(u["id"])


def profile_summary(chat_id: str) -> str:
    profile = get_profile_by_chat(chat_id)
    if not profile:
        return "No profile on file. Start with /onboard."
    consent = "yes" if profile.get("consent") else "no"
    return (
        f"Name: {profile.get('full_name')}\n"
        f"National ID: {profile.get('national_id')}\n"
        f"Employer: {profile.get('employer')}\n"
        f"Monthly income: KES {profile.get('monthly_income', 0):,.0f}\n"
        f"Consent: {consent}"
    )


def has_active_session(chat_id: str) -> bool:
    return bool(_sessions.get(chat_id))


def parse_command(text: str) -> Tuple[Optional[str], Optional[str]]:
    if not text:
        return None, None
    if not text.startswith("/"):
        return None, None
    parts = text.strip().split(maxsplit=1)
    cmd = parts[0].lstrip("/").lower()
    arg = parts[1] if len(parts) > 1 else None
    return cmd, arg


def handle_command(chat_id: str, text: str) -> Optional[str]:
    ensure_db()
    cmd, arg = parse_command(text)
    if not cmd:
        return None
    if cmd in ("start", "help"):
        return (
            "Zac SACCO assistant: /register, /onboard, /profile, /balance, "
            "/apply_loan, /loans, /send_otp, /verify_otp <code>"
        )
    if cmd == "register":
        ensure_db()
        return start_register(chat_id)
    if cmd == "onboard":
        if not require_registered(chat_id):
            return "You are not registered. Use /register to create an account."
        return start_onboarding(chat_id)
    if cmd == "profile":
        return profile_summary(chat_id)
    if cmd == "balance":
        return handle_balance(chat_id)
    if cmd == "apply_loan":
        if not require_registered(chat_id):
            return "You are not registered. Use /register to create an account."
        profile = get_profile_by_chat(chat_id)
        if not profile or not profile.get("consent"):
            return "Please complete onboarding first: /onboard."
        return start_apply_loan(chat_id)
    if cmd == "loans":
        return get_loans(chat_id)
    if cmd == "send_otp":
        return send_otp_cmd(chat_id)
    if cmd == "verify_otp":
        if not arg:
            return "Usage: /verify_otp 123456"
        return verify_otp_cmd(chat_id, arg.strip())
    return "Unknown command. Try /help."
