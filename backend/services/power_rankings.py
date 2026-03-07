"""
Weekly Power Rankings Email — Sends competitive leaderboard emails to all team members.
Shows rank movement, streaks, levels, and who's closest to leveling up.
"""
import logging
import os
import asyncio
from datetime import datetime, timezone, timedelta
from bson import ObjectId

logger = logging.getLogger(__name__)


LEVELS = [
    {"min": 0, "title": "Rookie", "color": "#8E8E93"},
    {"min": 51, "title": "Hustler", "color": "#007AFF"},
    {"min": 201, "title": "Closer", "color": "#AF52DE"},
    {"min": 501, "title": "All-Star", "color": "#FF9500"},
    {"min": 1001, "title": "Legend", "color": "#C9A962"},
]


def _get_level(score):
    level = LEVELS[0]
    for l in LEVELS:
        if score >= l["min"]:
            level = l
    next_lvl = None
    for l in LEVELS:
        if l["min"] > score:
            next_lvl = l
            break
    pts_to_next = (next_lvl["min"] - score) if next_lvl else 0
    return {**level, "next_title": next_lvl["title"] if next_lvl else None, "pts_to_next": pts_to_next}


async def send_weekly_power_rankings(db):
    """Send Power Rankings email to every active user, grouped by store."""
    logger.info("[PowerRankings] Starting weekly power rankings email...")

    RESEND_KEY = os.environ.get("RESEND_API_KEY")
    if not RESEND_KEY:
        logger.error("[PowerRankings] RESEND_API_KEY not set, skipping")
        return

    import resend as resend_mod
    resend_mod.api_key = RESEND_KEY

    PUBLIC_URL = os.environ.get("PUBLIC_FACING_URL", "https://app.imonsocial.com")

    # Get all active users with email
    users = await db.users.find(
        {"status": {"$ne": "deactivated"}, "email": {"$exists": True, "$ne": ""}},
        {"password": 0}
    ).to_list(2000)

    if not users:
        logger.info("[PowerRankings] No active users found")
        return

    # Group users by store
    stores: dict = {}
    for u in users:
        sid = u.get("store_id", "independent")
        if sid not in stores:
            stores[sid] = []
        stores[sid].append(u)

    # Date ranges
    now = datetime.now(timezone.utc)
    week_start = now - timedelta(days=7)
    prev_week_start = week_start - timedelta(days=7)

    sent_count = 0
    for store_id, store_users in stores.items():
        if len(store_users) < 1:
            continue

        user_ids = [str(u["_id"]) for u in store_users]

        # This week's scores
        this_week = await _score_users(db, user_ids, week_start, now)
        # Last week's scores (for rank movement)
        last_week = await _score_users(db, user_ids, prev_week_start, week_start)

        # Rank this week
        ranked = sorted(user_ids, key=lambda uid: this_week.get(uid, 0), reverse=True)
        last_ranked = sorted(user_ids, key=lambda uid: last_week.get(uid, 0), reverse=True)

        rank_map = {uid: i + 1 for i, uid in enumerate(ranked)}
        last_rank_map = {uid: i + 1 for i, uid in enumerate(last_ranked)}

        # Build entries
        entries = []
        for uid in ranked:
            u = next((x for x in store_users if str(x["_id"]) == uid), None)
            if not u:
                continue
            score = this_week.get(uid, 0)
            rank = rank_map.get(uid, 0)
            prev_rank = last_rank_map.get(uid, rank)
            movement = prev_rank - rank  # positive = moved up
            level = _get_level(score)
            streak = await _get_streak(db, uid)
            entries.append({
                "user_id": uid,
                "name": u.get("name", "Unknown"),
                "email": u.get("email", ""),
                "score": score,
                "rank": rank,
                "movement": movement,
                "level": level,
                "streak": streak,
            })

        # Get store name
        store_name = "Your Team"
        if store_id and store_id != "independent":
            try:
                store = await db.stores.find_one({"_id": ObjectId(store_id)}, {"name": 1})
                if store:
                    store_name = store.get("name", store_name)
            except Exception:
                pass

        # Send to each user
        for entry in entries:
            if not entry["email"]:
                continue
            try:
                html = _build_power_rankings_html(entry, entries, store_name, PUBLIC_URL)
                await asyncio.to_thread(resend_mod.Emails.send, {
                    "from": f"i'M On Social <noreply@imosapp.com>",
                    "to": [entry["email"]],
                    "subject": f"Weekly Power Rankings — You're #{entry['rank']}!",
                    "html": html,
                })
                sent_count += 1
            except Exception as e:
                logger.error(f"[PowerRankings] Failed to send to {entry['email']}: {e}")

    logger.info(f"[PowerRankings] Sent {sent_count} emails")
    return sent_count


async def _score_users(db, user_ids, start, end):
    """Sum total contact_events + completed tasks for each user in a date range."""
    pipeline = [
        {"$match": {"user_id": {"$in": user_ids}, "timestamp": {"$gte": start, "$lt": end}}},
        {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
    ]
    event_scores = {}
    async for r in db.contact_events.aggregate(pipeline):
        event_scores[r["_id"]] = r["count"]

    task_pipeline = [
        {"$match": {"user_id": {"$in": user_ids}, "status": "completed", "completed_at": {"$gte": start, "$lt": end}}},
        {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
    ]
    async for r in db.tasks.aggregate(task_pipeline):
        event_scores[r["_id"]] = event_scores.get(r["_id"], 0) + r["count"]

    return event_scores


async def _get_streak(db, user_id):
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    streak = 0
    for i in range(60):
        day_start = today - timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        count = await db.tasks.count_documents({
            "user_id": user_id, "status": "completed",
            "completed_at": {"$gte": day_start, "$lt": day_end},
        })
        if count > 0:
            streak += 1
        elif i > 0:
            break
    return streak


def _build_power_rankings_html(you, all_entries, store_name, public_url):
    """Build the Power Rankings HTML email."""
    top3 = all_entries[:3]
    your_rank = you["rank"]
    your_score = you["score"]
    movement = you["movement"]
    level = you["level"]
    streak = you["streak"]

    # Movement arrow
    if movement > 0:
        move_html = f'<span style="color:#34C759;font-weight:700">&#9650; {movement}</span>'
    elif movement < 0:
        move_html = f'<span style="color:#FF3B30;font-weight:700">&#9660; {abs(movement)}</span>'
    else:
        move_html = '<span style="color:#8E8E93">&#8212;</span>'

    # Streak badge
    streak_html = f'<span style="background:rgba(255,150,0,0.15);color:#FF9500;padding:2px 8px;border-radius:8px;font-size:12px;font-weight:700">&#128293; {streak}d streak</span>' if streak > 0 else ''

    # Podium
    podium_html = ''
    medal = ['&#129351;', '&#129352;', '&#129353;']  # gold, silver, bronze
    for i, e in enumerate(top3):
        is_you_class = 'border:2px solid #C9A962;' if e["user_id"] == you["user_id"] else ''
        name_label = "You" if e["user_id"] == you["user_id"] else e["name"].split()[0]
        podium_html += f'''
        <td style="text-align:center;padding:8px;width:33%">
          <div style="font-size:28px">{medal[i]}</div>
          <div style="width:48px;height:48px;border-radius:14px;background:{["#FFD70030","#C0C0C030","#CD7F3230"][i]};{is_you_class}margin:0 auto;line-height:48px;font-weight:800;font-size:16px;color:{["#FFD700","#C0C0C0","#CD7F32"][i]}">{e["name"][:2].upper()}</div>
          <div style="font-size:13px;font-weight:700;color:#fff;margin-top:4px">{name_label}</div>
          <div style="font-size:16px;font-weight:800;color:{["#FFD700","#C0C0C0","#CD7F32"][i]}">{e["score"]} pts</div>
        </td>'''

    # Full rankings list
    rankings_html = ''
    for e in all_entries:
        is_you = e["user_id"] == you["user_id"]
        bg = 'rgba(201,169,98,0.08)' if is_you else '#1C1C1E'
        border = '1px solid rgba(201,169,98,0.3)' if is_you else '1px solid #2C2C2E'
        name_display = f'{e["name"]} (You)' if is_you else e["name"]
        e_level = e["level"]

        if e["movement"] > 0:
            e_move = f'<span style="color:#34C759;font-size:11px">&#9650;{e["movement"]}</span>'
        elif e["movement"] < 0:
            e_move = f'<span style="color:#FF3B30;font-size:11px">&#9660;{abs(e["movement"])}</span>'
        else:
            e_move = ''

        streak_dot = f'<span style="color:#FF9500;font-size:10px">&#128293;{e["streak"]}d</span>' if e["streak"] > 0 else ''

        rankings_html += f'''
        <tr>
          <td style="padding:10px 14px;background:{bg};border:{border};border-radius:10px">
            <table width="100%" cellpadding="0" cellspacing="0"><tr>
              <td style="width:36px;font-size:14px;font-weight:700;color:#8E8E93;text-align:center">#{e["rank"]}</td>
              <td style="padding-left:10px">
                <span style="font-size:14px;font-weight:600;color:{'#C9A962' if is_you else '#fff'}">{name_display}</span>
                <span style="margin-left:6px;font-size:11px;color:{e_level['color']}">{e_level['title']}</span>
                {' ' + e_move if e_move else ''}
                {' ' + streak_dot if streak_dot else ''}
              </td>
              <td style="text-align:right;font-size:16px;font-weight:700;color:#fff">{e["score"]}</td>
            </tr></table>
          </td>
        </tr>
        <tr><td style="height:4px"></td></tr>'''

    # "Almost there" — users closest to leveling up
    almost_html = ''
    leveling_up = sorted(
        [e for e in all_entries if e["level"]["next_title"] and e["level"]["pts_to_next"] <= 50],
        key=lambda x: x["level"]["pts_to_next"]
    )[:3]
    if leveling_up:
        rows = ''
        for e in leveling_up:
            name = "You" if e["user_id"] == you["user_id"] else e["name"].split()[0]
            rows += f'<div style="padding:6px 0;font-size:13px;color:#ccc">{name} — <span style="color:{e["level"]["color"]}">{e["level"]["pts_to_next"]} pts</span> to <span style="font-weight:700;color:{e["level"]["color"]}">{e["level"]["next_title"]}</span></div>'
        almost_html = f'''
        <div style="background:#1C1C1E;border-radius:12px;padding:14px 16px;margin-top:16px;border:1px solid #2C2C2E">
          <div style="font-size:11px;font-weight:700;color:#48484A;letter-spacing:1.5px;margin-bottom:8px">ALMOST THERE</div>
          {rows}
        </div>'''

    return f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#000;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#000;padding:20px 0">
<tr><td align="center">
<table width="100%" style="max-width:440px;background:#000" cellpadding="0" cellspacing="0">

  <!-- Header -->
  <tr><td style="padding:20px 16px 12px;text-align:center">
    <div style="font-size:13px;font-weight:700;color:#C9A962;letter-spacing:2px;text-transform:uppercase;margin-bottom:4px">WEEKLY POWER RANKINGS</div>
    <div style="font-size:22px;font-weight:800;color:#fff">{store_name}</div>
  </td></tr>

  <!-- Your Rank Banner -->
  <tr><td style="padding:0 16px 16px">
    <div style="background:#1C1C1E;border-radius:14px;padding:18px;border:1px solid rgba(201,169,98,0.3)">
      <table width="100%" cellpadding="0" cellspacing="0"><tr>
        <td>
          <div style="font-size:36px;font-weight:800;color:#C9A962;line-height:1">#{your_rank}</div>
          <div style="font-size:14px;color:#8E8E93;margin-top:2px">Your Rank {move_html}</div>
          <div style="margin-top:4px">
            <span style="font-size:13px;font-weight:700;color:{level['color']}">{level['title']}</span>
            {' ' + streak_html}
          </div>
        </td>
        <td style="text-align:right;vertical-align:top">
          <div style="font-size:28px;font-weight:800;color:#fff">{your_score}</div>
          <div style="font-size:12px;color:#8E8E93">points this week</div>
        </td>
      </tr></table>
      {f'<div style="margin-top:10px;font-size:12px;color:#636366;text-align:center">{level["pts_to_next"]} pts to <span style="color:{level["color"]};font-weight:700">{level["next_title"]}</span></div>' if level.get("next_title") else ''}
    </div>
  </td></tr>

  <!-- Podium -->
  <tr><td style="padding:0 16px 16px">
    <table width="100%" cellpadding="0" cellspacing="0"><tr>
      {podium_html}
    </tr></table>
  </td></tr>

  <!-- Full Rankings -->
  <tr><td style="padding:0 16px">
    <div style="font-size:11px;font-weight:700;color:#48484A;letter-spacing:1.5px;margin-bottom:8px">FULL RANKINGS</div>
    <table width="100%" cellpadding="0" cellspacing="0">
      {rankings_html}
    </table>
    {almost_html}
  </td></tr>

  <!-- CTA -->
  <tr><td style="padding:24px 16px;text-align:center">
    <a href="{public_url}/admin/leaderboard" style="display:inline-block;background:#C9A962;color:#000;font-size:16px;font-weight:700;padding:14px 32px;border-radius:12px;text-decoration:none">View Full Leaderboard</a>
  </td></tr>

  <!-- Footer -->
  <tr><td style="padding:16px;text-align:center;border-top:1px solid #2C2C2E">
    <div style="font-size:11px;color:#48484A">Powered by <a href="https://app.imonsocial.com/imos" style="color:#C9A962;text-decoration:none">i'M On Social</a></div>
    <div style="font-size:10px;color:#3A3A3C;margin-top:4px">You received this because you're part of {store_name}</div>
  </td></tr>

</table>
</td></tr></table>
</body></html>'''
