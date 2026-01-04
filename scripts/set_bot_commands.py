"""Set Telegram bot commands and optional profile fields via HTTP API.

Usage:
  TELEGRAM_TOKEN=... python scripts/set_bot_commands.py --name "Display Name" --description "Short description"
"""
import os
import sys
import json
import urllib.request
import argparse


def call(method, data=None):
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        print("TELEGRAM_TOKEN not set in environment")
        sys.exit(1)
    url = f"https://api.telegram.org/bot{token}/{method}"
    headers = {"Content-Type": "application/json"}
    if data is None:
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.load(r)
    else:
        b = json.dumps(data).encode()
        req = urllib.request.Request(url, data=b, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.load(r)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", help="Bot display name to set", default=None)
    parser.add_argument("--description", help="Bot description to set", default=None)
    args = parser.parse_args()

    commands = [
        {"command": "start", "description": "Greet and explain how to use the bot"},
        {"command": "help", "description": "Show usage tips and examples"},
    ]
    print("Setting commands...")
    print(call("setMyCommands", {"commands": commands}))

    if args.name:
        print("Setting display name...")
        print(call("setMyName", {"name": args.name}))

    if args.description:
        print("Setting description...")
        print(call("setMyDescription", {"description": args.description}))


if __name__ == "__main__":
    main()
