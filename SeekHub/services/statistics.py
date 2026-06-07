from db import sh_users, tg_chats, tg_messages, sh_mirrors
from utils.fmt import fmt_count


def get_stats() -> dict:
    return {
        "users":    sh_users.count(),
        "mirrors":  sh_mirrors.count(),
        "chats":    tg_chats.count(),
        "messages": tg_messages.count(),
    }


def get_stats_fmt() -> dict:
    s = get_stats()
    return {k: fmt_count(v) for k, v in s.items()}
