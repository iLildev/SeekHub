from db import users, referrals, points


REFERRAL_REWARD = 50


def handle_new_user(user_id: int, username: str, first_name: str, referrer_id: int = None):
    users.upsert_user(user_id, username, first_name)

    if referrer_id and referrer_id != user_id:
        referrals.add_referral(referrer_id, user_id)
        points.add_crystals(referrer_id, REFERRAL_REWARD)
        points.add_crystals(user_id, 10)
