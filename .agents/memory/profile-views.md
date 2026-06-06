---
name: Profile view tracking
description: How "Were looking for: N" is tracked
---

## Table
`tg_profile_views(id, target_user_id, viewer_user_id, viewed_at)`

## Functions (in db/tg_users.py)
- `track_profile_view(viewer_id, target_id)` — inserts a row; ignores self-views
- `get_profile_view_count(user_id)` — COUNT(*) for target

## Where called
`_send_user_result` in `mirror/search.py` — called every time a profile card is sent

**Why:** FunStat shows "Were looking for: N". We track views in tg_profile_views to compute this.
