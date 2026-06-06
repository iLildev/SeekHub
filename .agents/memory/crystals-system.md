---
name: Crystals system — how it works
description: How crystals are earned, spent, and enforced in SeekHub
---

## Earning
- +10 per referral (/link)
- +8 per group submission (/submit)
- +4 per referred user's first week activity

## Spending
1. **Daily query bypass** — `mirror/quota.py:charge_query()` — 1 crystal per extra search beyond plan limit
2. **Profile detail sections** — `mirror/callbacks.py` crystal_* handlers — fixed cost per feature:
   - names: 7💠 | groups: 15💠 | messages: 20💠 | channels: 15💠 | friends: 8💠 | reactions: 10💠

## Enforcement flow
charge_query() in quota.py:
  1. track_mirror_user() + increment_query_count() + log_query(user_id=...)
  2. Check get_user_daily_count() vs plan daily_queries limit
  3. If over: deduct 1 crystal or block with earn-more message

**Why:** Before this, crystals were earned but never spent. Now every search over limit costs 1 crystal,
and every profile detail section has a crystal price — making the economy real.

**How to apply:** All search entry points MUST go through charge_query(). Do NOT call
track_mirror_user/increment_query_count directly in handlers.
