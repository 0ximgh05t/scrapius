import os
import json
from typing import List, Dict, Tuple
from openai import OpenAI


def get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")
    return OpenAI(api_key=api_key)


def generate_message_for_post(post: Dict, system_prompt: str, user_prompt: str, model: str = "gpt-4o-mini") -> str:
    client = get_openai_client()
    content = post.get('post_content_raw') or post.get('content_text') or ""
    url = post.get('post_url', '')
    author = post.get('post_author_name', '')

    messages = [
        {"role": "system", "content": system_prompt.strip()},
        {"role": "user", "content": (user_prompt.strip() + f"\n\nAuthor: {author}\nURL: {url}\nContent:\n{content}")[:6000]},
    ]

    resp = client.chat.completions.create(model=model, messages=messages, temperature=0)
    text = resp.choices[0].message.content if resp.choices else ""
    return text or ""


def decide_and_summarize_for_post(post: Dict, system_prompt: str, user_prompt: str, model: str = "gpt-4o-mini") -> Tuple[bool, str]:
    """Ask the model to decide if a post should be sent and provide a brief summary.
    Returns (send, summary).
    """
    client = get_openai_client()
    content = post.get('post_content_raw') or post.get('content_text') or ""
    url = post.get('post_url', '')
    author = post.get('post_author_name', '')

    sys = (
        (system_prompt or "You are a strict filter for Facebook posts.").strip()
        + "\n\nRespond ONLY with valid JSON: {\"send\": <true|false>, \"summary\": <string>}\n"
        + "If the post meets the criteria in the user's instructions, set send=true and write a short summary. Otherwise send=false and summary can be empty."
    )
    usr = (
        (user_prompt or "Decide if this is relevant.").strip()
        + f"\n\nAuthor: {author}\nURL: {url}\nContent:\n{content}"
    )[:6000]

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": usr},
        ],
        temperature=0,
    )
    text = resp.choices[0].message.content if resp.choices else ""
    try:
        data = json.loads(text)
        send = bool(data.get("send", False))
        summary = str(data.get("summary", ""))
        return send, summary
    except Exception:
        # Fallback: simple heuristic
        lowered = (text or "").lower()
        send = "\"send\": true" in lowered or "\"send\":true" in lowered or lowered.strip().startswith("send")
        summary = text if send else ""
        return send, summary 