import requests
from typing import List, Dict, Optional
import html

TELEGRAM_API_BASE = "https://api.telegram.org"


def _truncate_text(text: str, max_len: int = 3500) -> str:
    if text is None:
        return ""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def send_telegram_message(bot_token: str, chat_id: str, text: str, parse_mode: Optional[str] = None, reply_markup: Optional[dict] = None) -> bool:
    url = f"{TELEGRAM_API_BASE}/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": _truncate_text(text),
        "disable_web_page_preview": True,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if not resp.ok:
            print(f"❌ Telegram API error: {resp.status_code} - {resp.text}")
        return resp.ok
    except Exception as e:
        print(f"❌ Telegram request exception: {e}")
        return False


def broadcast_message(bot_token: str, chat_ids: List[str], text: str, parse_mode: Optional[str] = None) -> None:
    for cid in chat_ids:
        send_telegram_message(bot_token, str(cid).strip(), text, parse_mode=parse_mode)


def get_updates(bot_token: str, offset: Optional[int] = None, timeout: int = 30) -> Dict:
    url = f"{TELEGRAM_API_BASE}/bot{bot_token}/getUpdates"
    params = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset
    
    try:
        resp = requests.get(url, params=params, timeout=timeout + 5)
        resp.raise_for_status()
        return resp.json()
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, 
            requests.exceptions.RequestException, OSError) as e:
        # Return empty result on network errors to prevent bot crashes
        print(f"⚠️ Telegram API connection error: {e}")
        return {"ok": False, "result": []}


def extract_commands(update: Dict) -> Optional[Dict]:
    if "message" not in update:
        return None
    msg = update["message"]
    chat_id = msg.get("chat", {}).get("id")
    text = msg.get("text", "") or ""
    if not chat_id or not text.startswith("/"):
        return None
    parts = text.strip().split(" ", 1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""
    return {"chat_id": str(chat_id), "cmd": cmd, "arg": arg}


def escape_html(text: str) -> str:
    return html.escape(text or "")


def format_post_message(title: str, short_text: str, url: str, author: Optional[str] = None, group_name: Optional[str] = None) -> str:
    """Format post message in beautiful Lithuanian format."""
    # Clean up group name - remove "Group from " prefix
    clean_group_name = group_name or "Unknown Group"
    if clean_group_name.startswith("Group from "):
        clean_group_name = clean_group_name.replace("Group from ", "")
    clean_group_name = clean_group_name.replace("https://www.facebook.com/groups/", "")
    
    # Use short_text as the main content
    content = escape_html(short_text or "")
    
    if url and url != "#":
        # Has URL - show group name + post link
        msg = f"""📩 <b>Naujas įrašas</b>

📍 <b>Grupė:</b> <i>{escape_html(clean_group_name)}</i>

{content}

<a href="{escape_html(url)}">📱 Peržiūrėti įrašą</a>"""
    else:
        # No URL - show group name only (no link since we don't have group_url here)
        msg = f"""📩 <b>Naujas įrašas</b>

📍 <b>Grupė:</b> <i>{escape_html(clean_group_name)}</i>

{content}"""
    
    return msg 