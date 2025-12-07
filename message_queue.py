"""
message_queue.py

Simple in-process queue and worker threads that process messages asynchronously.
Workers call `ai_core.Answerer` and send replies via Telegram or Twilio when credentials are available.

Usage:
 - call start_workers() at application startup to begin background processing
 - call enqueue_message(job_dict) to queue a message for processing

Job format (dict):
  {
    'platform': 'telegram' | 'whatsapp',
    'to': chat_id (int) for telegram or 'whatsapp:+123' for whatsapp,
    'text': 'user message'
  }

This is a lightweight example for small deployments. For production use, replace with Redis/RQ or Celery.
"""
import os
import threading
import time
import logging
from queue import Queue, Empty
from typing import Dict

logger = logging.getLogger(__name__)

_queue = Queue()
_workers_started = False


def enqueue_message(job: Dict):
    """Enqueue a job for background processing."""
    _queue.put(job)


def _process_job(job: Dict):
    from ai_core import Answerer
    answerer = Answerer()
    try:
        resp = answerer.answer(job.get('text', ''))
        reply = resp.get('answer')

        platform = job.get('platform')
        to = job.get('to')

        if platform == 'telegram':
            token = os.getenv('TELEGRAM_TOKEN')
            if token and to is not None:
                try:
                    from telegram import Bot
                    bot = Bot(token=token)
                    bot.send_message(chat_id=to, text=reply)
                    logger.info('Sent Telegram reply to %s', to)
                except Exception:
                    logger.exception('Failed sending telegram reply')
            else:
                logger.info('Telegram not configured or chat_id missing; reply: %s', reply)

        elif platform == 'whatsapp':
            sid = os.getenv('TWILIO_ACCOUNT_SID')
            token = os.getenv('TWILIO_AUTH_TOKEN')
            from_number = os.getenv('TWILIO_WHATSAPP_NUMBER')
            if sid and token and from_number and to:
                try:
                    from twilio.rest import Client
                    client = Client(sid, token)
                    client.messages.create(body=reply, from_=from_number, to=to)
                    logger.info('Sent WhatsApp reply to %s', to)
                except Exception:
                    logger.exception('Failed sending whatsapp reply')
            else:
                logger.info('Twilio not configured or destination missing; reply: %s', reply)

        else:
            logger.warning('Unknown platform for job: %s', job)

    except Exception:
        logger.exception('Error processing job')


def _worker_loop(stop_event: threading.Event):
    logger.info('Worker started')
    while not stop_event.is_set():
        try:
            job = _queue.get(timeout=1.0)
        except Empty:
            continue
        try:
            _process_job(job)
        finally:
            _queue.task_done()
    logger.info('Worker stopped')


def start_workers(num_workers: int = 1):
    global _workers_started
    if _workers_started:
        return
    _workers_started = True
    stop_event = threading.Event()
    for i in range(num_workers):
        t = threading.Thread(target=_worker_loop, args=(stop_event,), daemon=True)
        t.start()
    logger.info('Started %d background worker(s)', num_workers)


__all__ = ['enqueue_message', 'start_workers']
