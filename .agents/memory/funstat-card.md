---
name: FunStat profile card format
description: How SeekHub user profile cards should be structured — FunStat-style with crystal buttons
---

## Layout
```
This is *Name* (@username)
Message diversity X%
From YYYY-MM-DD to YYYY-MM-DD
N messages in N groups
X% replies  Y% media
Circles: N, voice: N
Favorite group: GroupName
Admin in N groups
Were looking for: N

ID: 123456789
usernames:
| @old1 | @old2 | @old3
first name / last name:
├ YYYY-MM-DD  ➜  Name1
```

## Button rows (crystal costs)
Row 1: stats(now) | track | Names 7💠
Row 2: groups 15💠 | 20💠 messages | analysis
Row 3: 15💠 channels | 👍 reputations | friends 8💠
Row 4: reactions 10💠 | 💠 prices | share 🔗
Row 5: words frequency | common groups

## Implementation
- `_send_user_result` in `mirror/search.py`
- Crystal costs in `CRYSTAL_COSTS` dict (keep in sync with `callbacks.py COSTS`)
- Stats from `tg_users.get_extended_stats()` — single DB round-trip

**Why:** User explicitly requested FunStat format. Crystals must be the primary monetization mechanic.
