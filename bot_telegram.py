"""
bot_telegram.py

Simple Telegram bot using python-telegram-bot (polling). It delegates responses to ai_core.Answerer.

Usage:
  - Copy `.env.example` to `.env` and set TELEGRAM_TOKEN
  - python bot_telegram.py
"""

import os
import logging
from dotenv import load_dotenv
from logging_config import configure_logging
try:
    from .message_queue import enqueue_message, start_workers
except ImportError:
    from message_queue import enqueue_message, start_workers
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    configure_logging()
    start_workers()

    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN not set in environment")
        return

    try:
        from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
    except Exception:
        logger.exception("python-telegram-bot not installed or incompatible")
        raise

    # Zac sacco credit bot handlers (basic flows)
    try:
        try:
            from .zac_bot import (
                ensure_db,
                start_register,
                start_onboarding,
                profile_summary,
                handle_text,
                require_registered,
                handle_balance,
                start_apply_loan,
                get_loans,
                send_otp_cmd,
                verify_otp_cmd,
            )
        except ImportError:
            from zac_bot import (
                ensure_db,
                start_register,
                start_onboarding,
                profile_summary,
                handle_text,
                require_registered,
                handle_balance,
                start_apply_loan,
                get_loans,
                send_otp_cmd,
                verify_otp_cmd,
            )
    except Exception:
        logger.exception("zac_bot import failed; ensure module is available")

    ensure_db()

    def start(update, context):
        update.message.reply_text(
            "Hello. Send me a question and I will try to answer "
            "from my knowledge base. Use /register, /onboard, /profile, /balance, /apply_loan, /loans."
        )

    def help_cmd(update, context):
        update.message.reply_text(
            "Ask me detailed questions. I attempt to match questions "
            "to documented answers. Use /register, /onboard, /profile, /balance, /apply_loan, /loans, /send_otp, /verify_otp."
        )

    def register_cmd(update, context):
        chat_id = update.message.chat_id
        ensure_db()
        update.message.reply_text(start_register(str(chat_id)))

    def balance_cmd(update, context):
        chat_id = update.message.chat_id
        if not require_registered(str(chat_id)):
            update.message.reply_text("You are not registered. Use /register to create an account.")
            return
        update.message.reply_text(handle_balance(str(chat_id)))

    def apply_loan_cmd(update, context):
        chat_id = update.message.chat_id
        if not require_registered(str(chat_id)):
            update.message.reply_text("You are not registered. Use /register to create an account.")
            return
        update.message.reply_text(start_apply_loan(str(chat_id)))

    def loans_cmd(update, context):
        chat_id = update.message.chat_id
        update.message.reply_text(get_loans(str(chat_id)))

    def onboard_cmd(update, context):
        chat_id = update.message.chat_id
        if not require_registered(str(chat_id)):
            update.message.reply_text("You are not registered. Use /register to create an account.")
            return
        update.message.reply_text(start_onboarding(str(chat_id)))

    def profile_cmd(update, context):
        chat_id = update.message.chat_id
        update.message.reply_text(profile_summary(str(chat_id)))

    def send_otp(update, context):
        chat_id = update.message.chat_id
        update.message.reply_text(send_otp_cmd(str(chat_id)))

    def verify_otp(update, context):
        chat_id = update.message.chat_id
        args = context.args or []
        if not args:
            update.message.reply_text("Usage: /verify_otp 123456")
            return
        update.message.reply_text(verify_otp_cmd(str(chat_id), args[0]))

    def echo(update, context):
        # global conversation handler for simple flows
        chat_id = update.message.chat_id
        text = update.message.text or ""
        resp = handle_text(str(chat_id), text)
        update.message.reply_text(resp)

    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_cmd))
    dp.add_handler(CommandHandler("register", register_cmd))
    dp.add_handler(CommandHandler("onboard", onboard_cmd))
    dp.add_handler(CommandHandler("profile", profile_cmd))
    dp.add_handler(CommandHandler("balance", balance_cmd))
    dp.add_handler(CommandHandler("apply_loan", apply_loan_cmd))
    dp.add_handler(CommandHandler("loans", loans_cmd))
    dp.add_handler(CommandHandler("send_otp", send_otp))
    dp.add_handler(CommandHandler("verify_otp", verify_otp))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, echo))

    logger.info("Starting Telegram polling...")
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
