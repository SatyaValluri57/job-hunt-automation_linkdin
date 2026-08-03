"""
Phase 3 — Telegram integration.
One-way: sends daily summary + low-confidence alerts.
Two-way: sends field question, waits for your reply (approve/edit/skip).

Setup:
  1. Message @BotFather on Telegram → create bot → get TELEGRAM_BOT_TOKEN
  2. Message your bot once → get your TELEGRAM_CHAT_ID
  3. Add to .env:
       TELEGRAM_BOT_TOKEN=your_token
       TELEGRAM_CHAT_ID=your_chat_id

Requires: pip install requests
"""

import os
import time
from typing import Optional, Dict

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
POLL_INTERVAL = 5   # seconds between polling for reply
POLL_TIMEOUT = 120  # seconds to wait for your reply before giving up


def _is_configured() -> bool:
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID and REQUESTS_AVAILABLE)


def send_message(text: str) -> bool:
    """Send a plain text message to your Telegram chat."""
    if not _is_configured():
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "Markdown",
        }, timeout=10)
        return True
    except Exception:
        return False


def send_daily_summary(stats: Dict) -> None:
    """Send daily apply summary to Telegram."""
    if not _is_configured():
        return
    msg = (
        "📊 *Job Apply Daily Summary*\n"
        f"✅ Applied: {stats.get('applied', 0)}\n"
        f"🧪 Dry-run: {stats.get('dry_run', 0)}\n"
        f"🔗 External apply: {stats.get('external', 0)}\n"
        f"⛔ Below threshold: {stats.get('below_threshold', 0)}\n"
        f"⏳ Needs review: {stats.get('low_confidence', 0)}\n"
        f"⏱ Duration: {stats.get('duration_min', 0)} min\n"
        f"📁 Check data/ folder for review queue."
    )
    send_message(msg)


def _get_latest_update_id() -> int:
    """Get the latest processed update_id to avoid duplicate reads."""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates?limit=1&offset=-1"
        resp = requests.get(url, timeout=10)
        data = resp.json()
        results = data.get("result", [])
        if results:
            return results[-1]["update_id"]
    except Exception:
        pass
    return 0


def ask_for_approval(
    job_title: str,
    question: str,
    suggested_answer: str,
    confidence: str,
    offer_page: str,
) -> Dict:
    """
    Sends a Telegram message asking you to approve/edit/skip a field.
    Waits up to POLL_TIMEOUT seconds for your reply.

    Reply format expected from you:
      approve          → use suggested answer
      edit: your text  → use your custom answer
      skip             → skip this field

    Returns: {"action": "approve"|"edit"|"skip", "value": "answer text"}
    """
    if not _is_configured():
        # If telegram not configured, default to review queue (skip auto-fill)
        return {"action": "skip", "value": ""}

    msg = (
        f"⏳ *Field needs your input*\n\n"
        f"🏢 Job: {job_title}\n"
        f"❓ Question: `{question}`\n"
        f"🤖 AI suggestion: `{suggested_answer}`\n"
        f"📊 Confidence: {confidence}\n"
        f"🔗 {offer_page}\n\n"
        f"Reply:\n"
        f"  `approve` → use suggestion\n"
        f"  `edit: your answer` → use your text\n"
        f"  `skip` → leave blank"
    )
    send_message(msg)

    # Get current update_id baseline so we only read NEW messages
    baseline_id = _get_latest_update_id()
    waited = 0

    while waited < POLL_TIMEOUT:
        time.sleep(POLL_INTERVAL)
        waited += POLL_INTERVAL
        try:
            url = (
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
                f"?offset={baseline_id + 1}&limit=5&timeout=5"
            )
            resp = requests.get(url, timeout=15)
            data = resp.json()
            results = data.get("result", [])
            for update in results:
                baseline_id = update["update_id"]
                msg_data = update.get("message", {})
                chat_id = str(msg_data.get("chat", {}).get("id", ""))
                text = msg_data.get("text", "").strip().lower()
                if chat_id != str(TELEGRAM_CHAT_ID):
                    continue
                if text == "approve":
                    send_message(f"✅ Approved: `{suggested_answer}`")
                    return {"action": "approve", "value": suggested_answer}
                elif text.startswith("edit:"):
                    custom = msg_data.get("text", "").strip()[5:].strip()
                    send_message(f"✏️ Using your answer: `{custom}`")
                    return {"action": "edit", "value": custom}
                elif text == "skip":
                    send_message("⏭️ Skipped this field.")
                    return {"action": "skip", "value": ""}
        except Exception:
            continue

    # Timed out — default to skip and log
    send_message(f"⏰ Timed out waiting for reply. Field skipped: `{question}`")
    return {"action": "skip", "value": ""}
