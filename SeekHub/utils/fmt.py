"""
utils/fmt.py
============
Shared formatting helpers for Telegram MarkdownV2 output.
"""
import re


def escape(text: str) -> str:
    """Escape special characters for MarkdownV2."""
    if not text:
        return ""
    return re.sub(r"([_\*\[\]\(\)~`>#+\-=|{}.!\\])", r"\\\1", str(text))


def user_line(u: dict) -> str:
    name = escape(" ".join(filter(None, [u.get("first_name"), u.get("last_name")])) or "Unknown")
    uname = f" @{escape(u['username'])}" if u.get("username") else ""
    badges = ""
    if u.get("is_verified"): badges += " ✅"
    if u.get("is_premium"):  badges += " 💎"
    return f"• [{name}](tg://user?id={u['id']}){uname}{badges} — `{u['id']}`"


def chat_line(c: dict) -> str:
    icon  = "📢" if c.get("type") == "channel" else "💬"
    title = escape(c.get("title") or "Untitled")
    uname = f" @{escape(c['username'])}" if c.get("username") else ""
    members = f" `{c['member_count']:,}` members" if c.get("member_count") else ""
    return f"{icon} {title}{uname}{members} — `{c['id']}`"


def fmt_count(n: int) -> str:
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000:     return f"{n/1_000:.1f}K"
    return str(n)
