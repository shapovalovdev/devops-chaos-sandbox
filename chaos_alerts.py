#!/usr/bin/env python3
# Alerting daemon for DevOps Chaos Sandbox
# Resolves #2.

import os
import sys
import time
import urllib.request
import urllib.parse
import json

# Load configurations from environment
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
TARGET_APP_URL = os.environ.get("TARGET_APP_URL")

POLL_INTERVAL = 10  # seconds
TIMEOUT = 5         # seconds

def validate_env():
    missing = []
    if not TELEGRAM_BOT_TOKEN: missing.append("TELEGRAM_BOT_TOKEN")
    if not TELEGRAM_CHAT_ID: missing.append("TELEGRAM_CHAT_ID")
    if not TARGET_APP_URL: missing.append("TARGET_APP_URL")
    if missing:
        print(f"CRITICAL: Missing environment variables: {', '.join(missing)}")
        sys.exit(1)

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            return response.read()
    except Exception as e:
        print(f"ERROR sending Telegram notification: {e}", file=sys.stderr)
        return None

def check_app_health():
    try:
        # Standard user agent to avoid basic blocking
        req = urllib.request.Request(
            TARGET_APP_URL, 
            headers={"User-Agent": "ChaosSandboxAlertMonitor/1.0"}
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            code = response.getcode()
            if code == 200:
                return True, f"Status: {code}"
            return False, f"Non-200 Status: {code}"
    except Exception as e:
        return False, f"Exception: {e}"

def main():
    validate_env()
    print("=" * 60)
    print("        CHAOS ALERTS DAEMON STARTED")
    print(f"Monitoring Target: {TARGET_APP_URL}")
    print(f"Poll Interval:     {POLL_INTERVAL}s")
    print("=" * 60)

    is_down = False

    while True:
        healthy, message = check_app_health()
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] Health check: {'OK' if healthy else 'FAIL'} ({message})")

        if not healthy and not is_down:
            # Transition from healthy -> down
            print(f"[{timestamp}] WebApp transition to DOWN. Sending Telegram alert...")
            alert_text = (
                f"🚨 *[DOWNTIME ALERT]*\n\n"
                f"**Target application is UNREACHABLE!**\n"
                f"• *URL:* `{TARGET_APP_URL}`\n"
                f"• *Reason:* `{message}`\n\n"
                f"🔧 Please log in to your sandbox node and begin triaging."
            )
            send_telegram_message(alert_text)
            is_down = True

        elif healthy and is_down:
            # Transition from down -> healthy
            print(f"[{timestamp}] WebApp transition to UP. Sending Telegram recovery...")
            recovery_text = (
                f"✅ *[RECOVERY ALERT]*\n\n"
                f"**Target application is healthy again!**\n"
                f"• *URL:* `{TARGET_APP_URL}`\n"
                f"• *Status:* Service Restored."
            )
            send_telegram_message(recovery_text)
            is_down = False

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
