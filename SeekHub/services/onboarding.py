from db import sh_users, sh_referrals, sh_crystals

REFERRAL_CRYSTALS  = 50   # earned by referrer
NEW_USER_CRYSTALS  = 10   # bonus for new user


def handle_new_user(user_id: int, username: str, first_name: str, referrer_id: int = None):
    sh_users.upsert(user_id, username, first_name)

    if referrer_id and referrer_id != user_id:
        sh_referrals.add(referrer_id, user_id)
        sh_crystals.add(referrer_id, REFERRAL_CRYSTALS, "referral")
        sh_crystals.add(user_id,     NEW_USER_CRYSTALS,  "welcome_bonus")
