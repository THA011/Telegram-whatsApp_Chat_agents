"""quick_poll_bot.py

Minimal Telegram polling bot that avoids third-party Telegram libraries so it
can run quickly. Uses the local `ai_core.AnswerEngine` to generate replies.
"""

import os
import time
import json
import urllib.parse
import urllib.request
try:
    from .ai_core import AnswerEngine
except ImportError:
    from ai_core import AnswerEngine

TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    print("TELEGRAM_TOKEN not set in environment")
    raise SystemExit(1)

BASE = f"https://api.telegram.org/bot{TOKEN}"


def get_updates(offset=None, timeout=20):
    url = f"{BASE}/getUpdates?timeout={timeout}"
    if offset:
        url += f"&offset={offset}"
    with urllib.request.urlopen(url, timeout=timeout + 5) as r:
        data = json.load(r)
    return data


def send_message(chat_id, text):
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    req = urllib.request.Request(f"{BASE}/sendMessage", data=data)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


def main():
    engine = AnswerEngine()  # uses faq.yml and optional LLM if configured
    offset = None
    print("Starting quick polling bot. Press CTRL+C to stop.")
    while True:
        try:
            res = get_updates(offset=offset)
            if not res.get("ok"):
                time.sleep(1)
                continue
            for upd in res.get("result", []):
                offset = upd["update_id"] + 1
                if "message" not in upd:
                    continue
                msg = upd["message"]
                chat = msg.get("chat", {})
                chat_id = chat.get("id")
                text = msg.get("text", "").strip()
                if not text:
                    continue
                print(f"Received from {chat_id}: {text}")
                mem = []
                reply = engine.answer(text, memory=mem)
                if isinstance(reply, dict):
                    reply_text = reply.get("answer")
                else:
                    reply_text = str(reply)
                send_message(chat_id, reply_text)
                print(f"Replied to {chat_id}")
        except KeyboardInterrupt:
            print("Stopping polling bot.")
            break
        except Exception as e:
            print("Error in poll loop:", e)
            time.sleep(2)


if __name__ == "__main__":
    main()
