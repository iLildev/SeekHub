from db import sh_users, sh_referrals, sh_crystals

REFERRAL_CRYSTALS = 10
NEW_USER_CRYSTALS = 4


def handle_new_user(user_id: int, username: str, first_name: str, referrer_id: int = None):
    is_new = not sh_users.get(user_id)
    sh_users.upsert(user_id, username, first_name)

    if not is_new:
        return

    if referrer_id and referrer_id != user_id:
        if not sh_referrals.exists(user_id):
            sh_referrals.add(referrer_id, user_id)
            sh_crystals.add(referrer_id, REFERRAL_CRYSTALS, "referral")
            sh_crystals.add(user_id, NEW_USER_CRYSTALS, "welcome_bonus")
