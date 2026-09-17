"""Test Lab: new features land here first so the owner can try them on their own account before anyone else sees them.
A feature is `lab` (only visible inside the Test Lab, super admins) until it is flipped to `live` (everyone)."""
import asyncio
from datetime import datetime, timezone
from typing import Optional

FEATURES = [
    {"key": "voice_interview", "name": "Jessi Voice Interview", "icon": "mic",
     "tagline": "Jessi calls a rep, interviews them for about five minutes and writes their VA, bio and card from the call.",
     "description": "The rep taps Call me in My Profile (or My VA). Jessi rings their cell and asks about 10 things (what customers call them and their role, years and how they got in, "
                    "where they grew up and live, family, hobbies, why this work and why customers pick them, how they text, things they never say, a fun fact, plus one topic for the "
                    "store's industry such as what they drive), then GPT turns the transcript into their persona. The call records the rep's side only and enrolls their Voice ID so we know when it is them on recorded calls.",
     "how_to_test": ["Tap Call me and pick up. Talk like you would with a new hire, Jessi adapts to short and long answers.",
                     "Try interrupting her, asking what this is for, or saying you have to go: she should wrap up.",
                     "Hang up or let her finish. In about a minute the review opens with what she learned. In the lab NOTHING is saved to your profile until you tap Save to my profile.",
                     "Check the bio reads like you, the tone and phrases match, and the title is right. Redo as often as you like."],
     "added": "2026-09-16", "needs": "Voice ID needs PICOVOICE_ACCESS_KEY in the backend .env; until then the interview works and Voice ID shows as coming soon."},
    {"key": "industry_va", "name": "One VA for every industry", "icon": "layers",
     "tagline": "The VA stops assuming a car dealership: it speaks the store's industry and only answers specifics from a facts list the manager controls.",
     "description": "Every AI text (auto replies, follow-ups, campaign messages, suggested replies, the My VA preview) is built from four layers: the standard assistant rules, "
                    "the store's industry (words, tone, what the VA may handle itself and what always goes to the rep), who the rep is and how they text (the persona, mostly from the interview), "
                    "and FACTS: the only place the VA is allowed to get specifics like hours, what to bring, walk-ins, pricing rules or links. Managers keep the store's facts under "
                    "Things my VA may answer on the My VA screen; reps add their own. A question a fact answers gets answered (the rep gets an FYI); pricing or availability with no matching fact "
                    "still pauses the thread for the rep, using the industry's own hold words instead of car words.",
     "how_to_test": ["Open My VA. You should see Things my VA may answer with your industry at the top. Add a store fact like 'We take walk-ins weekdays until 6'.",
                     "Tap Generate Your VA's Reply on a scenario: the reply should stay in character, use your facts, and hand pricing to you.",
                     "Text your own work number from another phone: ask something a fact covers (answered, you get an FYI push) and something it does not (you get a You're Needed push).",
                     "Check nothing car-specific leaks into a non-automotive store: switch the store's industry on the admin store page and generate again."],
     "added": "2026-09-17", "default": "live"},
    {"key": "power_dialer", "name": "Power Dialer + GoHighLevel", "icon": "call",
     "tagline": "Call through a list of 1,000 leads fast: you press 1, we ring up to 3 at once, the first live answer is on your phone. Built inside TCPA and TSR limits, with GoHighLevel sync.",
     "description": "A manager builds a campaign (CSV, a GoHighLevel tag, or your own tagged contacts), sets B2B or consumer, lines (1-3), calling hours, attempts and whether calls record. "
                    "A rep starts a session: the dialer rings their cell once and they stay on for the whole session. Press 1 (or tap Dial next) = you launched the calls, so no call is ever placed without a human. "
                    "The first lead that answers is on your phone instantly; the other ringing lines are cancelled. If two people answer at the same time the second hears the required "
                    "'this was a call from <store> at <number>, press 9 to be removed' message and it counts against the campaign's 3% abandonment budget, which throttles you back to one line. "
                    "Every dial is logged (local time, state, outcome, disposition) and kept. Leads outside their state's legal calling hours, over the daily cap, on your Do Not Call list or on the "
                    "National Registry are skipped automatically. Interested / Call back turns the lead into a contact in your book and, when GoHighLevel is connected, adds a note, tags and a pipeline opportunity there.",
     "how_to_test": ["Tools > Power Dialer > New campaign. Import 3-5 leads by CSV using your own and a teammate's cells (never a stranger). Pick 2 lines and B2B.",
                     "Tap Start dialing. Your phone rings, pick up, then press 1 (or tap Dial next). Both test phones ring; answer one. The other stops ringing. Hang up and mark the outcome.",
                     "Answer BOTH phones at once: the second one hears the abandonment message; press 9 on it and check the number shows under Do Not Call.",
                     "Try a campaign with Press 1 to accept: when a lead answers your phone says the name, you press 1 to talk.",
                     "Tools > GoHighLevel: paste a Location ID + Private Integration Token, import a tag into a campaign, mark a lead Interested and check the note + tag in GHL."],
     "added": "2026-06-20", "needs": "Reps need their cell number on their profile and a work number (caller ID). Consumer (B2C) lists should have the National DNC Registry loaded under Do Not Call."},
    {"key": "jessi_live_voice", "name": "Talk to Jessi (live voice)", "icon": "radio",
     "tagline": "A real conversation with Jessi on the Home screen: full duplex, you can interrupt her, and she pulls your real people, sends texts and sets reminders while you talk.",
     "description": "Talk to Jessi runs on OpenAI GPT-Live-1: the model listens and speaks at the same time, so there is no record-and-wait. Jessi handles the talking; every fact comes from our backend. "
                    "When you name a person, ask who to talk to today, ask to text or remind someone, or ask how something works, GPT-Live hands the request to our brain, which reads the live transcript, "
                    "runs the real tool (your daily three, the contact record, a draft, a task) and hands back a short verified result she says out loud. Texts are always read back and only sent after you say yes. "
                    "The Voice Lab lets you pick her voice (13 options), energy, pacing, playfulness and brevity, and audition her in the browser before reps hear her. Web and PWA first: on the iPhone app "
                    "the button opens the current Ask Jessi until the next App Store build.",
     "how_to_test": ["Open the Voice Lab, pick a voice and energy, tap Audition and just talk: ask who you should talk to today, then ask about one of them by name.",
                     "Interrupt her mid-sentence. She should stop and listen.",
                     "Say 'text Sam and tell him the part came in'. She reads the text back; say yes and check the thread.",
                     "Say 'remind me to call Sam Friday at 2'. Check Touchpoints.",
                     "Save the config, then use the gold Talk to Jessi button on Home. Check the session shows up under Recent conversations with minutes and cost."],
     "added": "2026-06-21", "needs": "Needs OPENAI_API_KEY (your own OpenAI project key) in the backend environment. GPT-Live-1 is English only for now; Dutch keeps the current flow."},
    {"key": "live_shop_calls", "name": "Mystery shop calls on GPT-Live", "icon": "call",
     "tagline": "English shop calls (and lead-shop callbacks) get a full-duplex shopper who interrupts, hesitates and reacts in real time instead of the turn-by-turn relay.",
     "description": "When the rep presses 1, the call is bridged straight to OpenAI GPT-Live-1 over Twilio Media Streams (raw phone audio, no transcription hop). The shopper persona, "
                    "curveballs and the store's script go in as spoken instructions; the transcript comes back live and lands in the same place the grader reads, so scorecards, "
                    "reports and recordings work exactly as before. The shopper says goodbye and hangs up on her own; the 15-minute ceiling still applies. Dutch shops stay on "
                    "ConversationRelay. Before releasing, you can switch single clients on or off with the 'GPT-Live shopper' toggle in the client editor (that toggle also wins after release).",
     "how_to_test": ["Open a client, edit it and switch on GPT-Live shopper, then Quick shop yourself (500-555 numbers never connect, so use your own cell once).",
                     "Talk over the shopper mid-sentence: she should stop and listen. Ask a blind price question: she should push back.",
                     "Say goodbye: the line should drop within a couple of seconds and the shop grades like before (Shops tab, scorecard text).",
                     "Check the client report: recording, transcript and score all present; the shop row shows GPT-Live."],
     "added": "2026-06-21", "needs": "Needs OPENAI_API_KEY in the backend environment. English clients only."},
]
STATUSES = ("lab", "live")
SETTINGS_KEY = "lab_features"


def _now():
    return datetime.now(timezone.utc)


async def statuses(db) -> dict:
    doc = await db.settings.find_one({"key": SETTINGS_KEY}, {"value": 1})
    return (doc or {}).get("value") or {}


def _default(key: str) -> str:
    return next((f.get("default") or "lab" for f in FEATURES if f["key"] == key), "lab")


async def is_live(db, key: str) -> bool:
    return (((await statuses(db)).get(key) or {}).get("status") or _default(key)) == "live"


async def visible(db, user: Optional[dict], key: str) -> bool:
    """Everyone once live; nobody outside the Test Lab before that."""
    return await is_live(db, key)


async def list_features(db) -> list:
    from services import voice_id
    st = await statuses(db)
    out = []
    for f in FEATURES:
        s = st.get(f["key"]) or {}
        at = s.get("changed_at")
        row = {**f, "status": s.get("status") or _default(f["key"]), "changed_at": at.isoformat() if hasattr(at, "isoformat") else at, "changed_by": s.get("changed_by_name")}
        if f["key"] == "voice_interview":
            reason = await asyncio.to_thread(voice_id.available)
            row["needs"] = f"Voice ID is not running on this server: {reason}" if reason else None
        elif f["key"] in ("jessi_live_voice", "live_shop_calls"):
            from services import live_voice
            row["needs"] = live_voice.configured()
        out.append(row)
    return out


async def set_status(db, key: str, status: str, me: dict) -> dict:
    if key not in {f["key"] for f in FEATURES}:
        raise LookupError("Unknown feature")
    if status not in STATUSES:
        raise ValueError("status must be lab or live")
    await db.settings.update_one({"key": SETTINGS_KEY}, {"$set": {f"value.{key}": {"status": status, "changed_at": _now(), "changed_by": str(me["_id"]), "changed_by_name": me.get("name")}}}, upsert=True)
    return next(f for f in await list_features(db) if f["key"] == key)
