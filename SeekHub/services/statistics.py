from db import users, mirrors, groups


def get_stats() -> dict:
    return {
        "users": users.count_users(),
        "mirrors": mirrors.count_mirrors(),
        "groups": groups.count_groups(),
    }


def format_count(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)
