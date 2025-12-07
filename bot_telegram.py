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

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from ai_core import Answerer

def main():
    if not TELEGRAM_TOKEN:
        logger.error('TELEGRAM_TOKEN not set in environment')
        return

    try:
        from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
    except Exception as e:
        logger.exception('python-telegram-bot not installed or incompatible')
        raise

    answerer = Answerer()

    def start(update, context):
        update.message.reply_text('Hello. Send me a question and I will try to answer from my knowledge base.')

    def help_cmd(update, context):
        update.message.reply_text('Ask me detailed questions. I attempt to match questions to documented answers.')

    def echo(update, context):
        text = update.message.text
        resp = answerer.answer(text)
        update.message.reply_text(resp['answer'])

    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(CommandHandler('help', help_cmd))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, echo))

    logger.info('Starting Telegram polling...')
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
