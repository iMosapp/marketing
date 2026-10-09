"""Virtual customer identities: 1 to 10 fully reachable buyers per journey campaign, each one a Lead Shop.

An identity is a `lead_shops` row in status `draft` until its campaign is armed: persona and scenario are filled, but no
phone number is reserved yet, so drafts never burn a pool number. The LLM enriches the base persona (name, story, goal,
objections from the challenge library) with a buying timeline, a personality, channel preferences, the questions a real
buyer still needs answered and extra instructions; the admin can edit every field before launch."""
import logging
import random
import re
import uuid
from typing import Optional

from services import lead_shops as ls
from utils.text_sanitize import no_em_dash

logger = logging.getLogger(__name__)

MAX_IDENTITIES = 10
CHANNELS = ("text", "email", "call")
TIMELINES = ["this week", "within two weeks", "this month", "in the next 60 days", "just starting to look, 2 to 3 months out"]
PERSONALITIES = ["direct and busy, short answers, wants numbers", "friendly and chatty, asks a lot of questions", "cautious, has been burned before, double-checks everything",
                 "analytical, compares options, wants it in writing", "easygoing, decides fast when treated well"]
FIRST_NAMES = ["Avery", "Jordan", "Morgan", "Casey", "Riley", "Taylor", "Quinn", "Dakota", "Reese", "Parker", "Elena", "Marcus", "Priya", "Devon", "Nadia", "Luis", "Hannah", "Omar", "Grace", "Theo"]
LAST_NAMES = ["Rivera", "Bennett", "Okafor", "Lindqvist", "Marsh", "Patel", "Nguyen", "Carter", "Delgado", "Foster", "Hughes", "Kim", "Moreno", "Walsh", "Sato", "Brennan"]
NO_COMMIT_RULE = ("HARD RULE: never confirm a firm appointment and never commit to buy, sign or put money down. When they offer times, say you need to check your schedule "
                  "(or talk it over at home) and will get back to them; stay interested and keep asking your questions. This overrides anything above about agreeing to an appointment.")


def _clean_list(raw, n: int, width: int) -> list:
    if isinstance(raw, str):
        raw = [x for x in re.split(r"\r?\n|;", raw)]
    return [no_em_dash(str(x)).strip()[:width] for x in (raw or []) if str(x).strip()][:n]


def clean_fields(raw: Optional[dict]) -> dict:
    """Validate the editable identity fields; unknown keys are dropped."""
    raw = raw or {}
    out = {}
    if "timeline" in raw:
        out["timeline"] = no_em_dash(str(raw.get("timeline") or "")).strip()[:80]
    if "personality" in raw:
        out["personality"] = no_em_dash(str(raw.get("personality") or "")).strip()[:160]
    if "channel_prefs" in raw and isinstance(raw["channel_prefs"], list):
        seen = []
        for c in raw["channel_prefs"]:
            c = {"sms": "text", "phone": "call"}.get(str(c).lower(), str(c).lower())
            if c in CHANNELS and c not in seen:
                seen.append(c)
        out["channel_prefs"] = seen
    if "questions" in raw:
        out["questions"] = _clean_list(raw.get("questions"), 5, 160)
    if "objections" in raw:
        out["objections"] = _clean_list(raw.get("objections"), 3, 160)
    if "ai_instructions" in raw:
        out["ai_instructions"] = no_em_dash(str(raw.get("ai_instructions") or "")).strip()[:400]
    if "goals" in raw:
        out["goals"] = no_em_dash(str(raw.get("goals") or "")).strip()[:400]
    if "interest" in raw:
        v = str(raw.get("interest") or "").strip()[:80]
        if v:
            out["offering"] = v
            out["vehicle"] = v
    return out


def identity_fields(persona: dict) -> dict:
    p = persona or {}
    return {"timeline": p.get("timeline") or "", "personality": p.get("personality") or "", "channel_prefs": p.get("channel_prefs") or [], "questions": p.get("questions") or [],
            "objections": p.get("objections") or [], "ai_instructions": p.get("ai_instructions") or "", "no_commit": bool(p.get("no_commit"))}


def prompt_rules(persona: dict) -> str:
    """What a journey identity adds to the shopper's system prompt (empty for ordinary shop personas)."""
    p = persona or {}
    bits = []
    if p.get("timeline"):
        bits.append(f"YOUR TIMELINE: you plan to decide {p['timeline']}.")
    if p.get("personality"):
        bits.append(f"YOUR PERSONALITY: {p['personality']}.")
    if p.get("questions"):
        bits.append(f"QUESTIONS YOU STILL NEED ANSWERED (one at a time, when it fits, and notice when one is dodged): {'; '.join(p['questions'])}.")
    if p.get("channel_prefs"):
        bits.append(f"You would rather be reached by {p['channel_prefs'][0]}; if they use a channel you like less you may say so once, mildly.")
    if p.get("ai_instructions"):
        bits.append(f"EXTRA INSTRUCTIONS FROM THE SHOP DIRECTOR: {p['ai_instructions']}")
    if p.get("no_commit"):
        bits.append(NO_COMMIT_RULE)
    return (" ".join(bits) + " ") if bits else ""


def _fallback(i: int) -> dict:
    return {"timeline": TIMELINES[i % len(TIMELINES)], "personality": PERSONALITIES[i % len(PERSONALITIES)], "channel_prefs": list(random.choice([["text", "email", "call"], ["email", "text", "call"], ["call", "text", "email"]])),
            "questions": ["Is it still available?", "What is the out-the-door price?", "Can I see it this weekend?"][: 2 + (i % 2)], "objections": [], "ai_instructions": ""}


async def _enrich(client: dict, campaign: dict, bases: list) -> list:
    """One LLM call fills timeline / personality / channel prefs / questions / objections for the whole batch; falls back to defaults per row."""
    from services import scripts as scr
    scenario = campaign.get("scenario") or {}
    system = ("You design realistic virtual customers for a covert mystery shop of a business. Each customer sent the business an online inquiry and will now be contacted by its staff "
              "by phone, text and email over several days. For EVERY customer listed, invent: a buying timeline (short phrase), a one-line personality, the order of channels they prefer "
              "(subset of text, email, call), 2 to 4 specific questions a real buyer in that situation still needs answered, 0 to 2 objections they may raise, and one short extra "
              "instruction for the AI playing them (quirk, constraint or detail). Make the customers clearly different from each other. Plain words, no em dashes. "
              "Return ONLY JSON: {\"identities\": [{\"i\": 0, \"timeline\": \"\", \"personality\": \"\", \"channel_prefs\": [\"text\"], \"questions\": [\"\"], \"objections\": [\"\"], \"ai_instructions\": \"\"}]}")
    rows = "\n".join(f"{i}. {b.get('name')}: {b.get('summary') or ''} Wants: {b.get('goals') or ''} Asking about: {b.get('offering') or b.get('vehicle') or ''}" for i, b in enumerate(bases))
    user = (f"BUSINESS: {client.get('name')} ({client.get('industry') or 'automotive'}, {campaign.get('department')} department)\nSCENARIO: {scenario.get('offering') or 'whatever they have listed'}. "
            f"{scenario.get('notes') or ''}\nCUSTOMERS:\n{rows}")
    out = [_fallback(i) for i in range(len(bases))]
    try:
        data = await scr._llm_json(system, user, timeout=60)
        for row in data.get("identities") or []:
            try:
                i = int(row.get("i"))
            except (TypeError, ValueError):
                continue
            if 0 <= i < len(out):
                out[i] = {**out[i], **clean_fields({k: row.get(k) for k in ("timeline", "personality", "channel_prefs", "questions", "objections", "ai_instructions")})}
    except Exception as e:
        logger.warning(f"[Journey] identity enrichment failed, using defaults: {e}")
    return out


async def _unique_name(db, campaign_id: str, persona: dict, used: set):
    """No two identities in a campaign share a name or an email, and no identity reuses an email that exists anywhere."""
    tries = 0
    while (persona["name"].lower() in used or await db[ls.COLL].count_documents({"persona.email": persona["email"]})) and tries < 20:
        persona["first"] = random.choice(FIRST_NAMES)
        persona["last"] = random.choice(LAST_NAMES)
        persona["name"] = f"{persona['first']} {persona['last']}"
        persona["email"] = ls._email_for(persona)
        tries += 1
    used.add(persona["name"].lower())


async def generate(db, campaign: dict, client: dict, me: Optional[dict], count: int) -> list:
    """Add `count` draft identities to the campaign (cap 10 in total). Each draws a fresh challenge persona, then the batch is enriched by the LLM."""
    if not ls.inbound_domain():
        raise ValueError("Email receiving is not configured (INBOUND_EMAIL_DOMAIN)")
    count = max(1, min(int(count or 1), MAX_IDENTITIES))
    existing = await db[ls.COLL].count_documents({"campaign_id": str(campaign["_id"])})
    limit = min(MAX_IDENTITIES, int(campaign.get("submission_limit") or MAX_IDENTITIES))
    if existing + count > limit:
        raise ValueError(f"A campaign holds at most {limit} identities (this one has {existing})")
    used = {(s.get("persona") or {}).get("name", "").lower() async for s in db[ls.COLL].find({"campaign_id": str(campaign["_id"])}, {"persona.name": 1})}
    scenario = campaign.get("scenario") or {}
    script = None
    if scenario.get("script_id") and ls._oid(scenario["script_id"]):
        script = await db.scripts.find_one({"_id": ls._oid(scenario["script_id"])})
    bases, scripts = [], []
    for _ in range(count):
        persona, sc = await ls.build_persona(db, client, campaign.get("department") or "sales", (scenario.get("offering") or "").strip()[:80] or None, script)
        await _unique_name(db, str(campaign["_id"]), persona, used)
        bases.append(persona)
        scripts.append(sc)
    extras = await _enrich(client, campaign, bases)
    now = ls._now()
    docs = []
    for persona, sc, extra in zip(bases, scripts, extras):
        persona.update({**extra, "no_commit": True})
        if extra.get("objections"):
            persona["objections"] = extra["objections"]
        docs.append({"client_id": str(client["_id"]), "campaign_id": str(campaign["_id"]), "department": campaign.get("department") or "sales", "industry": client.get("industry") or "automotive",
                     "store_name": client.get("name"), "locale": client.get("locale"), "status": "draft", "method": campaign.get("method") or "manual", "source_name": campaign.get("source_name") or "Website",
                     "persona": persona, "script_id": str(sc["_id"]), "script_title": sc.get("title"), "window_hours": int(campaign.get("window_hours") or 72), "process": ls.clean_process(client.get("lead_process")),
                     "events": [], "sessions": {"phone": [], "text": None, "email": None}, "delivery": {"method": campaign.get("method") or "manual", "to_email": (client.get("lead_email") or "").strip().lower() if campaign.get("method") == "adf" else None},
                     "started_at": None, "expires_at": None, "closed_at": None, "score": None, "score_token": uuid.uuid4().hex, "notes": "", "created_by": str(me["_id"]) if me else campaign.get("created_by"),
                     "created_at": now, "updated_at": now})
    if docs:
        res = await db[ls.COLL].insert_many(docs)
        for d, oid in zip(docs, res.inserted_ids):
            d["_id"] = oid
    await db["journey_campaigns"].update_one({"_id": campaign["_id"]}, {"$set": {"updated_at": now}})
    return docs


async def update(db, shop: dict, body: dict) -> dict:
    """Edit an identity. Name and email change only while it is a draft (the store may already hold them afterwards); the AI fields any time before it completes."""
    if shop.get("status") == "completed":
        raise ValueError("This identity has finished; it cannot be edited")
    upd = {f"persona.{k}": v for k, v in clean_fields(body).items()}
    first = str(body.get("first") or "").strip()[:40]
    last = str(body.get("last") or "").strip()[:40]
    if first or last:
        if shop.get("status") != "draft":
            raise ValueError("The name is locked once the campaign is armed")
        p = shop["persona"]
        first, last = first or p.get("first"), last or p.get("last")
        persona = {**p, "first": first, "last": last, "name": f"{first} {last}"}
        if await db[ls.COLL].count_documents({"campaign_id": shop.get("campaign_id"), "_id": {"$ne": shop["_id"]}, "persona.name": persona["name"]}):
            raise ValueError("Another identity in this campaign already has that name")
        persona["email"] = ls._email_for(persona)
        upd.update({"persona.first": first, "persona.last": last, "persona.name": persona["name"], "persona.email": persona["email"]})
    if not upd:
        raise ValueError("Nothing to change")
    await db[ls.COLL].update_one({"_id": shop["_id"]}, {"$set": {**upd, "updated_at": ls._now()}})
    return await db[ls.COLL].find_one({"_id": shop["_id"]})


async def remove(db, shop: dict):
    if shop.get("status") != "draft":
        raise ValueError("Only a draft identity can be removed; close or stop the campaign instead")
    await db[ls.COLL].delete_one({"_id": shop["_id"]})
