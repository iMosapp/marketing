"""Scripts & Practice: phone-script library (store-editable), training-video script generator, and voice roleplay
("mystery shop") against an AI customer, graded with the store's scorecard + script adherence."""
import asyncio
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId

from routers.database import get_db
from services import locales as loc
from services.speech import numbers_rule, speakable
from utils.text_sanitize import no_em_dash

logger = logging.getLogger(__name__)

MODEL = ("openai", "gpt-5.2")
MERGE_FIELDS = ["first_name", "vehicle", "store", "rep_name", "appointment_time", "trade"]
MAX_TURNS = 24
PHONE_MAX_MINUTES = 15
PHONE_MAX_TURNS = 60
CALL_TIME_LIMIT_S = (PHONE_MAX_MINUTES + 3) * 60  # Twilio-side ceiling: announcement + the call itself can never run past this

# ---------------------------------------------------------------- starter phone scripts (global library, stores override by copying)
STARTER_SCRIPTS = [
    {"slug": "inbound_sales_call", "category": "Sales calls", "title": "Inbound sales call", "runtime": "3 to 5 min", "direction": "inbound",
     "purpose": "A customer calls in about a vehicle they saw online. Goal: build rapport, confirm the car, set a firm appointment.",
     "body": "Thanks for calling {store}, this is {rep_name}. Who do I have the pleasure of speaking with?\n\n"
             "Great to meet you, {first_name}. Which vehicle caught your eye? ... The {vehicle}, good choice. Let me pull it up while we talk.\n\n"
             "[Confirm availability, never quote a payment on the phone]\nGood news, it's here on the lot. What is it about the {vehicle} that made you reach out today?\n\n"
             "[Discovery: 2 questions max]\nWill anyone be joining you when you come see it? Are you replacing something you'll be trading in?\n\n"
             "[Set the appointment with two options]\nI'd love to have it pulled up front and washed for you. I have an opening today at 4:30 or tomorrow at 10. Which works better?\n\n"
             "[Lock it in]\nPerfect, {appointment_time} it is. What's the best cell to text you a confirmation and my direct line? ... You'll have a text from me in about a minute. Ask for me, {rep_name}, when you arrive.",
     "success_points": ["Introduces self and the store", "Gets and uses the customer's name", "Confirms the vehicle and availability without quoting a payment",
                        "Asks about a trade-in", "Offers two appointment times", "Confirms the appointment time and gets the cell number"],
     "persona": {"name": "Maria Lopez", "voice": "female", "summary": "38, busy nurse, saw a 2022 Tahoe Z71 online. Friendly but short on time. Wants the price and monthly payment before driving over.",
                 "goals": "Find out if the Tahoe is still available and what the payment would be. Come in only if it feels worth the drive.",
                 "objections": ["Can you just tell me the payment over the phone?", "I'm 40 minutes away, I don't want to waste a trip", "Is that price negotiable?"],
                 "opening_line": "Hi, I'm calling about the white Tahoe Z71 you have listed online, is it still available?"}},
    {"slug": "internet_lead_followup", "category": "Sales calls", "title": "Internet lead follow-up call", "runtime": "2 to 4 min",
     "purpose": "Calling a lead who filled out a form minutes ago. Goal: reach them while it's hot, answer the question, set the visit.",
     "body": "Hi {first_name}, this is {rep_name} at {store}. You just sent us a note about the {vehicle}, I wanted to get right back to you. Did I catch you at an okay time?\n\n"
             "[Answer their exact question first]\nYou asked about ... Here's the honest answer: ...\n\n"
             "[One discovery question]\nWhat's most important to you on this one: the price, the payment, or getting the right one?\n\n"
             "[Trade]\nWill you have anything to trade? I can have a real number ready when you get here.\n\n"
             "[Appointment, two options]\nI can have the {vehicle} pulled up and ready. Does this evening or tomorrow morning work better? ... {appointment_time}, done.\n\n"
             "[Confirm + text]\nI'll text you a confirmation with my direct line right now. If anything changes just text me back.",
     "success_points": ["Calls back fast and references the form", "Answers the customer's actual question", "Asks one discovery question", "Asks about a trade",
                        "Offers two appointment times", "Confirms and sends a text"],
     "persona": {"name": "Derek Nguyen", "voice": "male", "summary": "29, software tester, submitted a form asking if the 2021 Tacoma TRD has a clean title and the out-the-door price. Analytical, hates pressure.",
                 "goals": "Get straight answers. Will set an appointment if the rep is honest and not pushy.",
                 "objections": ["What's the out-the-door price, all in?", "I've been burned by dealer fees before", "I'm still looking at two other trucks"],
                 "opening_line": "Hello? Oh hey, yeah I just sent something in about the Tacoma."}},
    {"slug": "appointment_confirmation", "category": "Appointments", "title": "Appointment confirmation call", "runtime": "1 to 2 min",
     "purpose": "The day before or morning of. Goal: confirm they're coming, remind them what to bring, reduce no-shows.",
     "body": "Hi {first_name}, it's {rep_name} at {store}. Quick call to confirm we're still on for {appointment_time} to see the {vehicle}.\n\n"
             "[Build anticipation]\nI've got it pulled up front and detailed. It looks even better in person.\n\n"
             "[What to bring]\nBring your license and, if you're trading, the title or payoff info and both keys so we can get you a real number on the spot.\n\n"
             "[Confirm]\nSo I'll see you at {appointment_time}? Perfect. Text me if you're running late, no problem at all.",
     "success_points": ["Confirms the day and time", "Builds anticipation about the vehicle", "Tells them what to bring", "Invites them to text if late"],
     "persona": {"name": "Janet Kowalski", "voice": "older", "summary": "61, retired teacher, appointment tomorrow at 10 for a Buick Enclave. Polite, a little hesitant, her son wants to come too.",
                 "goals": "Confirm, but she's wavering because her son can't come until Saturday.",
                 "objections": ["My son wanted to come with me and he's not free until Saturday", "Will the car still be there Saturday?"],
                 "opening_line": "Hello, this is Janet."}},
    {"slug": "missed_appointment", "category": "Appointments", "title": "Missed appointment call", "runtime": "1 to 2 min",
     "purpose": "They didn't show. Goal: no guilt, rebook with two options.",
     "body": "Hi {first_name}, {rep_name} at {store}. I had the {vehicle} up front for you at {appointment_time} and wanted to make sure everything's okay on your end.\n\n"
             "[No guilt]\nNo worries at all, life happens.\n\n"
             "[Rebook, two options]\nIt's still here. Would later today or tomorrow around the same time be easier? ... Great, I'll have it ready and text you a confirmation.",
     "success_points": ["No guilt or blame", "Confirms the vehicle is still available", "Offers two new times", "Confirms and texts"],
     "persona": {"name": "Tyler Brooks", "voice": "young", "summary": "24, missed his 2 PM appointment for a Civic Si because work ran late. Slightly embarrassed.",
                 "goals": "Rebook if the rep is cool about it.",
                 "objections": ["Sorry, work went long, I couldn't leave", "I might just wait until next weekend"],
                 "opening_line": "Hey, yeah, sorry about today."}},
    {"slug": "unsold_followup", "category": "Follow-up", "title": "Unsold follow-up call (visited, didn't buy)", "runtime": "2 to 3 min",
     "purpose": "They came in and left without buying. Goal: find the real objection, bring them back with a reason.",
     "body": "Hi {first_name}, it's {rep_name} from {store}. Thanks again for coming in to see the {vehicle}. I wanted to follow up personally.\n\n"
             "[Find the real reason]\nWhen you left, what was the one thing that kept you from moving forward? ... Got it, that makes sense.\n\n"
             "[Bring news, not pressure]\nHere's why I called: ... [new arrival, price change, manager approval, trade number]\n\n"
             "[Invite back]\nWould it be worth 15 minutes to take another look with that in mind? I can do today after 5 or tomorrow at 11.",
     "success_points": ["Thanks them for the visit", "Asks for the real objection and listens", "Brings a reason to return (news)", "Offers two times"],
     "persona": {"name": "Priya Raman", "voice": "female", "summary": "45, came in Saturday, drove a Highlander Hybrid, left because the payment was $80 over budget and her husband wasn't there.",
                 "goals": "Only comes back if the number moves or there's a real reason.",
                 "objections": ["The payment was just too high", "My husband thinks we should wait until the end of the year", "Are you calling to pressure me?"],
                 "opening_line": "Hi, yes, I remember you."}},
    {"slug": "trade_appraisal", "category": "Sales calls", "title": "Trade appraisal call", "runtime": "2 to 3 min",
     "purpose": "Customer wants a number on their trade. Goal: gather the facts, never guess a number, get the car on the lot.",
     "body": "Hi {first_name}, {rep_name} at {store}. You asked about a number on your {trade}. Happy to help. A couple quick questions so my used-car manager can be accurate.\n\n"
             "[Facts]\nMileage? Any accidents or warning lights? Is it paid off or is there a payoff? Two keys?\n\n"
             "[Never guess]\nI won't throw a number at you over the phone because I'd rather be right than fast. My manager will put eyes on it and you'll have a firm number in about 15 minutes.\n\n"
             "[Appointment]\nCan you bring it by today after 3 or tomorrow morning? Bring the title or payoff letter and I'll have the {vehicle} pulled up so you can drive it while we appraise yours.",
     "success_points": ["Gathers mileage, condition, payoff, keys", "Does not guess a number", "Explains the appraisal process", "Sets a time to bring the trade in"],
     "persona": {"name": "Carlos Mendez", "voice": "male", "summary": "52, contractor, wants a number on his 2018 F-150 XLT with 88k miles, one fender bender, owes about $9,000. Impatient.",
                 "goals": "Get a ballpark number on the phone. Reluctant to drive in without one.",
                 "objections": ["Just give me a ballpark", "KBB says it's worth 22", "I don't have time to sit at a dealership"],
                 "opening_line": "Yeah, I want to know what you'd give me for my F-150."}},
    {"slug": "service_to_sales", "category": "Follow-up", "title": "Service-to-sales call", "runtime": "2 min",
     "purpose": "Customer is in service with a big repair estimate or aging car. Goal: offer an upgrade conversation without being sleazy.",
     "body": "Hi {first_name}, this is {rep_name} in sales at {store}. Service mentioned your {trade} is in for ... I wanted to give you an option before you decide.\n\n"
             "[The option]\nWe're actively looking for vehicles like yours. There's a chance the trade value covers more than you'd expect, and the payment on something newer might be close to that repair bill.\n\n"
             "[Low pressure]\nNo obligation. While it's in the shop, would you like me to run the numbers and show you a couple of options? Takes 10 minutes.",
     "success_points": ["References the service visit specifically", "Frames the upgrade as an option, not a pitch", "Low pressure, offers to run numbers"],
     "persona": {"name": "Angela Foster", "voice": "female", "summary": "57, her 2015 Equinox needs a $2,400 transmission repair. Wary of being upsold.",
                 "goals": "Fix the car unless the numbers really make sense.",
                 "objections": ["I just want my car fixed", "I can't afford a new car payment", "Is this a sales trick?"],
                 "opening_line": "Hello? Who is this?"}},
    {"slug": "objection_handling", "category": "Objections", "title": "Common objections and responses", "runtime": "Reference",
     "purpose": "Quick responses to the objections you hear every day. Acknowledge, isolate, answer, ask.",
     "body": "\"Can you give me the payment over the phone?\"\nI can get close, but I'd be guessing without your trade and credit tier and I don't want to be wrong with your money. Come in for 20 minutes and I'll give you exact numbers. This afternoon or tomorrow?\n\n"
             "\"I'm just looking.\"\nSmart. Most people start there. What are you comparing the {vehicle} against? I can save you a trip if it's not the right fit.\n\n"
             "\"Your price is higher than the other dealer.\"\nThat may be true on the sticker. Is their number out the door with fees? Send me what they quoted and I'll tell you honestly if I can match it or why I can't.\n\n"
             "\"I need to talk to my spouse.\"\nOf course. Would it help if you both came in together? I have {appointment_time} open, and the {vehicle} will be ready.\n\n"
             "\"I'm 40 minutes away.\"\nTotally get it. If it were me I'd want to know it's worth the drive. Here's what I'll do: I'll send you a walkaround video and my direct line right now, and hold it until you arrive.",
     "success_points": ["Acknowledges before answering", "Isolates the real objection", "Answers honestly", "Ends with a question or appointment"],
     "persona": {"name": "Sam Whitaker", "voice": "male", "summary": "41, calling about a Silverado. Throws one objection after another to see how the rep handles pressure.",
                 "goals": "Test the rep. Sets an appointment only if every objection gets a straight answer.",
                 "objections": ["Give me the payment over the phone", "The other dealer is cheaper", "I need to talk to my wife", "I'm 40 minutes away"],
                 "opening_line": "Hey, I saw your Silverado online. What's the payment going to be on that?"}},
]

# ---------------------------------------------------------------- features the training-video generator knows about
FEATURES = [
    {"id": "inbox_thread", "name": "Inbox & threads", "audience": "reps", "summary": "One thread per customer with texts, emails, calls and voice memos; Ask, Search, Call and Record pills; Jessi banner; quick templates and media."},
    {"id": "ask_jessi", "name": "Ask Jessi about a customer", "audience": "reps", "summary": "Chat with Jessi about any customer's full history (texts, calls, recordings, tasks) with tappable citations; turn an answer into a text in one tap."},
    {"id": "record_conversation", "name": "Record a conversation", "audience": "reps", "summary": "Record a walk-around or desk talk up to 45 minutes from the thread or profile; Jessi transcribes, summarizes, names it, and turns every promise into a task with reminders."},
    {"id": "do_this_next", "name": "Home: Do This Next & My 3", "audience": "reps", "summary": "Home screen tells the rep the single best next move and today's three touches; pull to refresh; marks itself done when the rep reaches out."},
    {"id": "internet_leads", "name": "Internet leads: claim, ring, press 1", "audience": "both", "summary": "Lead lands, customer gets a text, reps' phones ring, first to press 1 claims and is bridged to the customer; Leads segment in Inbox; timeline shows every ring."},
    {"id": "lead_flows", "name": "Lead Flows (managers)", "audience": "managers", "summary": "Reusable playbooks: steps of who rings when, text-first delay, after-hours rule, returning-customer rule, automations on claim / no answer; attach to lead sources."},
    {"id": "shared_inboxes", "name": "Shared inboxes", "audience": "both", "summary": "Department numbers worked by a team: up for grabs, claim, assign, hand off, graduate to a rep's line; Jessi first reply."},
    {"id": "scorecards", "name": "Call scorecards", "audience": "managers", "summary": "Build a checklist per department; every recorded call is graded by AI with evidence quotes; critical-miss alerts; leaderboard and heatmap."},
    {"id": "team_ask", "name": "Ask Jessi about the team (managers)", "audience": "managers", "summary": "Ask across every rep's threads and calls: who is waiting, who mentioned a trade, what calls missed steps; citations open the thread."},
    {"id": "digital_card", "name": "Digital business card & QR", "audience": "reps", "summary": "Personal card with photo, links and reviews; QR to share; taps and views tracked on the profile."},
    {"id": "campaigns", "name": "Campaigns & birthday/anniversary cards", "audience": "reps", "summary": "Automated touches: birthdays, purchase anniversaries, holidays, review requests; personalized cards the customer opens."},
    {"id": "tasks_touchpoints", "name": "Touchpoints & tasks", "audience": "reps", "summary": "Every follow-up as a task with reminders 15 minutes before and at time; call tasks deep-link to the dialer; complete from the thread."},
    {"id": "voice_memos", "name": "Voice memos & relationship intel", "audience": "reps", "summary": "Talk a memo after any interaction; Jessi extracts family, hobbies, timing into the customer's intel card."},
    {"id": "scripts_practice", "name": "Scripts & practice (mystery shop)", "audience": "both", "summary": "Phone scripts library, editable per store; reps practice by voice against an AI customer and get scored with the store's scorecard."},
]


def _now():
    return datetime.now(timezone.utc)


def _json(raw: str) -> dict:
    t = (raw or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    m = re.search(r"\{.*\}", t, re.S)
    if m:
        t = m.group(0)
    # models sometimes escape the quotes that delimit a value (`: \"text\",`); unescape only at value boundaries
    lenient = re.sub(r'\\"(\s*[,}\]\n])', r'"\1', re.sub(r'(:\s*)\\"', r'\1"', t))
    for cand in (t, lenient):
        try:
            d = json.loads(cand)
            if isinstance(d, dict):
                return d
        except json.JSONDecodeError:
            continue
    return {}


async def _llm(system: str, user: str, timeout: int = 75, model: tuple = MODEL) -> str:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"scripts-{uuid.uuid4().hex[:8]}", system_message=system).with_model(*model)
    resp = await asyncio.wait_for(chat.send_message(UserMessage(text=user)), timeout=timeout)
    return resp if isinstance(resp, str) else getattr(resp, "text", "") or ""


JSON_RULES = " Strict JSON only: double quotes, no trailing commas, and never put quotation marks or backslashes inside string values (paraphrase quotes instead)."


async def _llm_json(system: str, user: str, timeout: int = 75) -> dict:
    """LLM call that must come back as a JSON object; one retry when the model breaks the format."""
    raw = await _llm(system + JSON_RULES, user, timeout)
    data = _json(raw)
    if data:
        return data
    logger.warning(f"[Scripts] bad JSON from model, retrying once: {raw[:160]!r}")
    return _json(await _llm(system + JSON_RULES + " Your previous reply was not valid JSON.", user, timeout))


def merge(body: str, values: dict) -> str:
    out = body
    for k in MERGE_FIELDS:
        out = out.replace("{" + k + "}", str(values.get(k) or "{" + k + "}"))
    return out


IMPORT_CATEGORIES = ["Sales calls", "Appointments", "Follow-up", "Objections", "Service", "Custom"]


async def import_script_text(text: str, industry: Optional[str] = None, department: Optional[str] = None) -> dict:
    """Turn a pasted phone script (any format: notes, Word dump, bullets) into a structured draft for the editor. Nothing is saved here.
    industry/department (industry packs) make Jessi talk like that business: an insurance agency never hears 'dealership' or 'vehicle'."""
    from services import industries as ind
    industry = industry if industry in ind.INDUSTRIES else (ind.industry_of_dept(department) if department else ind.DEFAULT_INDUSTRY)
    pack = ind.get(industry)
    d = ind.dept(department, industry) if department else None
    off = pack["offering"]
    who = f"{d['rep']}" if d else f"a {pack['label'].lower()} team member"
    context = f" The script is for {who} handling {d['call']}s: {d['brief']}." if d else ""
    system = (f"You are Jessi, a {pack['trainer']} for {pack['label'].lower()} teams. A manager pasted a phone script they already use.{context} Re-shape it into our script format WITHOUT rewriting their words: "
              "keep every line of dialogue they wrote (fix only obvious typos), keep their order, drop page numbers and headers. "
              f"Put stage directions in [brackets]. Replace the customer's name with {{first_name}}, the specific {off['label']} with {{offering}}, the {pack['business']} name with {{store}}, the employee's name with {{rep_name}} and "
              "appointment times with {appointment_time}, but only where the pasted text clearly refers to those things and ONLY inside body; write success_points and persona in plain words (no curly braces). "
              f"Use this business's own words: the business is a {pack['business']} (never call it a dealership or store unless it is one), the caller is a {pack['customer']}, what they ask about is a {off['label']}. "
              f"Pick category from {IMPORT_CATEGORIES}. success_points = 4 to 8 short graded behaviours the script asks the employee to do (start with a verb). "
              f"persona = the {pack['customer']} this script is talking to, so an employee can practice against it: name (first and last), voice one of female/male/young/older, summary (age, situation, what they saw or need), goals as ONE sentence string, 2 to 4 objections they would raise, and an opening_line they would say to start the call. "
              f"runtime like '2 to 4 min'. purpose = one line on when to use it. direction = inbound when the {pack['customer']} is calling the {pack['business']} (the employee answers the phone), outbound when the employee places the call. Never use em dashes. "
              "Return JSON: {title, category, direction, runtime, purpose, body, success_points:[...], persona:{name, voice, summary, goals, objections:[...], opening_line}}.")
    data = await _llm_json(system, f"PASTED SCRIPT ({pack['label']}{' / ' + d['label'] if d else ''}):\n\n{text[:12000]}", timeout=90)
    if industry == ind.DEFAULT_INDUSTRY and isinstance(data.get("body"), str):
        data["body"] = data["body"].replace("{offering}", "{vehicle}")  # automotive practice scripts keep their historical merge field
    body = data.get("body")
    if isinstance(body, list):  # the model sometimes returns the script as a list of lines / turns
        body = "\n".join(str(x.get("text") or x.get("line") or " ".join(str(v) for v in x.values())) if isinstance(x, dict) else str(x) for x in body)
        data["body"] = body
    if not str(body or "").strip():
        raise ValueError("Jessi could not read a script in that text")
    persona = data.get("persona") if isinstance(data.get("persona"), dict) else {}
    voice = persona.get("voice") if persona.get("voice") in ("female", "male", "young", "older") else "female"
    plain = lambda v, n: no_em_dash("; ".join(str(x) for x in v) if isinstance(v, list) else str(v or "")).replace("{", "").replace("}", "")[:n]
    return {
        "title": no_em_dash(str(data.get("title") or "Imported script"))[:120],
        "category": data.get("category") if data.get("category") in IMPORT_CATEGORIES else "Custom",
        "direction": "inbound" if str(data.get("direction") or "").lower() == "inbound" else "outbound",
        "runtime": no_em_dash(str(data.get("runtime") or ""))[:40],
        "purpose": no_em_dash(str(data.get("purpose") or ""))[:400],
        "body": no_em_dash(str(data.get("body")))[:8000],
        "success_points": [plain(p, 160).strip() for p in (data.get("success_points") or []) if str(p).strip()][:12],
        "persona": {"name": plain(persona.get("name"), 60), "voice": voice, "summary": plain(persona.get("summary"), 400),
                    "goals": plain(persona.get("goals"), 200), "opening_line": plain(persona.get("opening_line"), 240),
                    "objections": [plain(o, 160).strip() for o in (persona.get("objections") or []) if str(o).strip()][:6]},
    }


# ---------------------------------------------------------------- library
def serialize_script(s: dict, store_id: Optional[str] = None) -> dict:
    return {
        "id": str(s["_id"]), "slug": s.get("slug"), "kind": s.get("kind", "phone"), "category": s.get("category", ""), "title": s.get("title", ""), "direction": script_direction(s),
        "runtime": s.get("runtime", ""), "purpose": s.get("purpose", ""), "body": s.get("body", ""), "success_points": s.get("success_points") or [],
        "persona": s.get("persona") or None, "store_id": s.get("store_id"), "is_store_copy": bool(s.get("store_id")),
        "customized": bool(s.get("store_id")) and s.get("store_id") == store_id, "scorecard_id": s.get("scorecard_id"),
        "training": s.get("training") or None, "feature_id": s.get("feature_id"), "format": s.get("format"),
        "created_by_name": s.get("created_by_name"), "updated_at": (s.get("updated_at") or s.get("created_at") or _now()).isoformat() if hasattr(s.get("updated_at") or s.get("created_at") or _now(), "isoformat") else None,
    }


async def ensure_starters(db) -> int:
    """Global library rows (store_id None) exist once; text updates in code refresh untouched rows."""
    n = 0
    for tpl in STARTER_SCRIPTS:
        res = await db.scripts.update_one(
            {"slug": tpl["slug"], "store_id": None, "kind": "phone"},
            {"$setOnInsert": {**{k: v for k, v in tpl.items() if k != "direction"}, "kind": "phone", "store_id": None, "active": True, "created_at": _now(), "updated_at": _now()},
             "$set": {"direction": tpl.get("direction", "outbound")}}, upsert=True)
        n += 1 if res.upserted_id else 0
    return n


STARTER_DIRECTIONS = {t["slug"]: t.get("direction", "outbound") for t in STARTER_SCRIPTS}


def script_direction(s: dict) -> str:
    """inbound = the customer is calling the store, so the rep answers first; outbound = the rep places the call and the customer picks up."""
    d = (s or {}).get("direction")
    return d if d in ("inbound", "outbound") else STARTER_DIRECTIONS.get((s or {}).get("slug") or "", "outbound")


async def phone_library(db, store_id: Optional[str]) -> list:
    """Global starters with the store's customized copies swapped in, plus store-created scripts."""
    await ensure_starters(db)
    rows = await db.scripts.find({"kind": "phone", "active": {"$ne": False}, "pool": {"$exists": False}, "$or": [{"store_id": None}, {"store_id": store_id}]}).sort([("category", 1), ("title", 1)]).to_list(200)
    by_slug = {}
    for r in rows:
        key = r.get("slug") or str(r["_id"])
        cur = by_slug.get(key)
        if cur is None or (r.get("store_id") and not cur.get("store_id")):
            by_slug[key] = r
    return [serialize_script(r, store_id) for r in by_slug.values()]


async def save_store_copy(db, script_id: str, store_id: str, me: dict, patch: dict) -> dict:
    """Editing a global script creates the store's own copy; editing a store copy updates it in place."""
    src = await db.scripts.find_one({"_id": ObjectId(script_id)})
    if not src:
        raise LookupError("Script not found")
    fields = {k: patch[k] for k in ("title", "category", "runtime", "purpose", "body", "success_points", "persona", "scorecard_id", "direction") if k in patch and patch[k] is not None}
    if fields.get("direction") not in (None, "inbound", "outbound"):
        fields.pop("direction")
    if "body" in fields:
        fields["body"] = no_em_dash(str(fields["body"]))[:8000]
    if "title" in fields:
        fields["title"] = str(fields["title"]).strip()[:120]
    if "success_points" in fields:
        fields["success_points"] = [str(p).strip()[:160] for p in fields["success_points"] if str(p).strip()][:12]
    now = _now()
    if src.get("store_id") == store_id:
        await db.scripts.update_one({"_id": src["_id"]}, {"$set": {**fields, "updated_at": now, "updated_by": str(me["_id"]), "created_by_name": me.get("name")}})
        return serialize_script(await db.scripts.find_one({"_id": src["_id"]}), store_id)
    copy = {k: v for k, v in src.items() if k not in ("_id", "created_at", "updated_at", "store_id")}
    copy.update({**fields, "store_id": store_id, "copied_from": str(src["_id"]), "created_by": str(me["_id"]), "created_by_name": me.get("name"), "created_at": now, "updated_at": now, "active": True})
    res = await db.scripts.insert_one(copy)
    return serialize_script(await db.scripts.find_one({"_id": res.inserted_id}), store_id)


# ---------------------------------------------------------------- training video scripts
async def generate_training_script(feature: dict, fmt: str, audience: str, extra: str = "") -> dict:
    long = fmt == "long"
    system = ("You write scripts for short product training videos for a dealership CRM app called i'M On Social (assistant named Jessi). "
              "Screen-recorded walkthroughs with a friendly human narrator. Plain dealership language, no hype, no em dashes. Return ONLY JSON: "
              "{\"title\": str, \"runtime_seconds\": int, \"hook\": \"first 5 seconds, the problem in one line\", "
              "\"scenes\": [{\"on_screen\": \"what to show or tap, concrete\", \"voice_over\": \"exact words to say\", \"seconds\": int}], "
              "\"cta\": \"last line\", \"notes\": \"recording tips, one line\"}. "
              + ("Runtime 180 to 300 seconds, 8 to 12 scenes, cover setup, the everyday flow and one pro tip." if long else "Runtime 60 to 90 seconds, 4 to 6 scenes, one job done start to finish."))
    user = (f"FEATURE: {feature['name']}\nWHAT IT DOES: {feature['summary']}\nAUDIENCE: {audience or feature.get('audience') or 'reps'}"
            + (f"\nEXTRA DIRECTION: {extra}" if extra else ""))
    data = await _llm_json(system, user)
    scenes = [{"on_screen": no_em_dash(str(s.get("on_screen") or "")).strip(), "voice_over": no_em_dash(str(s.get("voice_over") or "")).strip(), "seconds": int(s.get("seconds") or 10)}
              for s in (data.get("scenes") or []) if s.get("voice_over")]
    return {"title": no_em_dash(str(data.get("title") or feature["name"])).strip()[:120], "runtime_seconds": int(data.get("runtime_seconds") or sum(s["seconds"] for s in scenes) or 75),
            "hook": no_em_dash(str(data.get("hook") or "")).strip(), "scenes": scenes, "cta": no_em_dash(str(data.get("cta") or "")).strip(), "notes": no_em_dash(str(data.get("notes") or "")).strip()}


def training_to_text(t: dict) -> str:
    lines = [t.get("title", ""), f"Runtime: about {t.get('runtime_seconds', 0)} seconds", "", f"HOOK: {t.get('hook', '')}", ""]
    for i, s in enumerate(t.get("scenes") or [], 1):
        lines += [f"SCENE {i} ({s.get('seconds', 0)}s)", f"On screen: {s.get('on_screen', '')}", f"Voice-over: {s.get('voice_over', '')}", ""]
    lines += [f"CTA: {t.get('cta', '')}"]
    if t.get("notes"):
        lines += ["", f"Notes: {t['notes']}"]
    return "\n".join(lines)


# ---------------------------------------------------------------- PDF
def script_pdf(script: dict, store_name: str = "") -> bytes:
    from fpdf import FPDF
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    def line(h: float, text: str):
        pdf.multi_cell(0, h, _pdf_safe(text), new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "B", 18)
    line(9, script.get("title", "Script"))
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(110, 110, 110)
    line(6, " - ".join(filter(None, [script.get("category"), script.get("runtime"), store_name or "i'M On Social"])))
    pdf.ln(2)
    pdf.set_text_color(0, 0, 0)
    if script.get("purpose"):
        pdf.set_font("Helvetica", "I", 11)
        line(6, script["purpose"])
        pdf.ln(2)
    text = training_to_text(script["training"]) if script.get("training") else script.get("body", "")
    pdf.set_font("Helvetica", "", 12)
    for para in text.split("\n"):
        if para.startswith("[") and para.endswith("]") or para.isupper() or para.startswith(("SCENE", "HOOK", "CTA", "On screen", "Voice-over")):
            pdf.set_font("Helvetica", "B", 11)
            line(6.5, para)
            pdf.set_font("Helvetica", "", 12)
        elif para.strip():
            line(6.5, para)
        else:
            pdf.ln(3)
    if script.get("success_points"):
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 12)
        line(7, "What a great call hits")
        pdf.set_font("Helvetica", "", 11)
        for p in script["success_points"]:
            line(6, f"  [ ] {p}")
    return bytes(pdf.output())


def _pdf_safe(s: str) -> str:
    return (s or "").replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"').replace("\u2026", "...").replace("\u00b7", "-").encode("latin-1", "replace").decode("latin-1")


# ---------------------------------------------------------------- roleplay (mystery shop)
RELAY_VOICES = {"female": "en-US-Journey-F", "male": "en-US-Journey-D", "young": "en-US-Journey-O", "older": "en-US-Journey-F"}
FAIL_REASONS = {"busy": "Your phone was busy", "no-answer": "No answer, we let it ring for 25 seconds", "failed": "The call could not be placed", "canceled": "The call was cancelled",
                "carrier_declined": "Carrier spam filter declined the call before your phone rang", "declined": "Declined before it rang, by a carrier spam filter or by the phone itself"}
SPAM_SIP = {"607": "carrier_declined", "608": "carrier_declined", "603": "declined"}  # RFC 8197/8688 unwanted + generic decline
TOLL_FREE_RE = re.compile(r"^\+?1?8(00|33|44|55|66|77|88)\d{7}$")


def failure_key(status: str, sip_code=None) -> str:
    """Twilio's final CallStatus plus the callee carrier's SIP code -> our outcome key. 603/607/608 mean the network refused the call (usually a spam filter), not a real busy signal."""
    return SPAM_SIP.get(str(sip_code or "").strip(), status)


def toll_free(phone) -> bool:
    return bool(TOLL_FREE_RE.match(re.sub(r"[^\d+]", "", str(phone or ""))))


def fail_label(key: str, from_number=None, fix: str = "ask your admin to switch you to a local number") -> str:
    label = FAIL_REASONS.get(key, key)
    if key in SPAM_SIP.values() and toll_free(from_number):
        label += f". We called from a toll-free number, cell carriers flag those as spam often, {fix}"
    return label


def _app_url() -> str:
    return os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com")).rstrip("/")


def _xml(v: str) -> str:
    return (v or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def relay_twiml(session: dict, prelude: str = "") -> str:
    """TwiML that hands the answered call to ConversationRelay, which streams the rep's speech to our websocket and speaks Jessi's customer lines."""
    sid, token = str(session["_id"]), session["token"]
    base = _app_url()
    persona = session.get("persona") or {}
    ws = base.replace("https://", "wss://").replace("http://", "ws://") + f"/api/scripts/roleplay/relay/{sid}/{token}"
    opening = persona.get("opening_line") or "Hi, I'm calling about a car I saw online."
    hints = ",".join(h for h in [session.get("store_name"), persona.get("name")] if h)
    # inbound = the customer is calling in, so the AI stays quiet until the rep answers the phone
    locale = session.get("locale")
    greeting = "" if session.get("direction") == "inbound" else f'welcomeGreeting="{_xml(speakable(opening, locale))}" '
    provider, voice = loc.relay_voice(locale, persona.get("voice"))
    return (f'<?xml version="1.0" encoding="UTF-8"?><Response>{prelude}<Connect action="{_xml(base)}/api/scripts/roleplay/after/{sid}?t={token}">'
            f'<ConversationRelay url="{_xml(ws)}" {greeting}ttsProvider="{provider}" voice="{_xml(voice)}" language="{loc.get(locale)["relay_language"]}" '
            f'transcriptionProvider="Deepgram" speechModel="nova-3-general" interruptible="any" interruptSensitivity="medium" ignoreBackchannel="true" hints="{_xml(hints)}" />'
            f'</Connect></Response>')


ANNOUNCE_VOICE = "Polly.Joanna-Neural"
GATE_SECONDS = 12
READY_WORDS = ("ready", "yes", "yeah", "yep", "go", "okay", "ok", "sure", "let's", "lets", "bring it", "hit me", "klaar", "ja", "start", "kom maar", "prima", "oké", "oke")
LATER_WORDS = ("not now", "bad time", "later", "busy", "call back", "can't right now", "cant right now", "no", "niet nu", "nee", "later", "geen tijd", "bel later", "druk")
GATE_HINTS = {"en": "ready, yes, go, not now, later", "nl": "klaar, ja, start, niet nu, later, nee"}
GO_LINES = {"en": ("Here it comes.", "Here we go, it's ringing."), "nl": ("Daar komt hij.", "Daar gaan we, hij gaat over.")}


def shop_announcement(session: dict) -> str:
    """What the rep hears the moment they pick up: who this is, which way the call runs, how to start it."""
    from services import industries as ind
    first = (session.get("rep_name") or "").split(" ")[0]
    industry = session.get("industry") or ind.industry_of_dept(session.get("department"))
    pack, d = ind.get(industry), ind.dept(session.get("department"), industry)
    dept = d.get("call") or "call"
    persona = session.get("persona") or {}
    if loc.language(session.get("locale")) == "nl":
        return _shop_announcement_nl(session, first, dept, persona)
    hi = f"Hi {first}, " if first else "Hi, "
    if session.get("direction") == "outbound":
        who = persona.get("name", "").split(" ")[0] or "a customer"
        about = f" about {persona['offering'] if persona.get('offering') else persona.get('vehicle')}" if (persona.get("offering") or persona.get("vehicle")) else ""
        setup = f"Coming up: an outbound {dept}. You're calling {who} back{about}. When you're ready, press 1 or say ready, you'll hear it ring, and they'll pick up."
    else:
        setup = f"Coming up: an inbound {dept}. A {pack['customer'] if pack['customer'] != 'shopper' else 'customer'} is calling the {pack['business']}, so answer it exactly like a real call. Press 1 or say ready when you're set."
    return f"{hi}this is your practice call from I'm On Social. {setup} If now's a bad time, press 2 and we'll {'try another time' if session.get('demo') or session.get('manual') else 'call back in a couple of hours'}."


def _shop_announcement_nl(session: dict, first: str, dept: str, persona: dict) -> str:
    """Dutch version of what the rep hears when they pick up."""
    hi = f"Hoi {first}, " if first else "Hoi, "
    dept_nl = {"sales call": "verkoopgesprek", "service call": "servicegesprek", "parts call": "onderdelengesprek", "rental call": "verhuurgesprek", "body shop call": "schadeherstelgesprek"}.get(dept, "gesprek")
    if session.get("direction") == "outbound":
        who = persona.get("name", "").split(" ")[0] or "een klant"
        about = f" over {persona['offering'] if persona.get('offering') else persona.get('vehicle')}" if (persona.get("offering") or persona.get("vehicle")) else ""
        setup = f"Zo meteen: een uitgaand {dept_nl}. Je belt {who} terug{about}. Druk op 1 of zeg klaar als je er klaar voor bent, je hoort hem overgaan en dan wordt er opgenomen."
    else:
        setup = f"Zo meteen: een inkomend {dept_nl}. Een klant belt het bedrijf, dus neem op zoals je een echt gesprek zou opnemen. Druk op 1 of zeg klaar als je zover bent."
    later = "proberen we het een andere keer" if session.get("demo") or session.get("manual") else "bellen we over een paar uur terug"
    return f"{hi}dit is je oefengesprek van I'm On Social. {setup} Komt het nu niet uit, druk dan op 2 en {later}."


def shop_gate_twiml(session: dict) -> str:
    sid, token = str(session["_id"]), session["token"]
    action = f"{_xml(_app_url())}/api/scripts/roleplay/gate/{sid}?t={token}"
    lang = loc.language(session.get("locale"))
    return (f'<?xml version="1.0" encoding="UTF-8"?><Response>'
            f'<Gather input="dtmf speech" numDigits="1" timeout="{GATE_SECONDS}" speechTimeout="auto" actionOnEmptyResult="true" action="{action}" method="POST" language="{loc.get(session.get("locale"))["relay_language"]}" hints="{GATE_HINTS.get(lang, GATE_HINTS["en"])}">'
            f'<Say voice="{loc.say_voice(session.get("locale"))}">{_xml(speakable(shop_announcement(session), session.get("locale")))}</Say></Gather></Response>')


def gate_choice(digits: str, speech: str) -> str:
    """'go' (press 1 / ready), 'later' (press 2 / not now) or 'none' (silence, voicemail greeting, anything else)."""
    d = (digits or "").strip()
    low = " ".join((speech or "").lower().split())
    if d == "1" or any(w in low for w in READY_WORDS if w != "no"):
        return "go"
    if d == "2" or any(w == low or f" {w}" in f" {low}" for w in LATER_WORDS):
        return "later"
    return "none"


def shop_go_twiml(session: dict) -> str:
    """Rep is ready: a heads-up, a ring, then the live customer."""
    lines = GO_LINES.get(loc.language(session.get("locale")), GO_LINES["en"])
    line = lines[0] if session.get("direction") == "inbound" else lines[1]
    ring = f"{_xml(_app_url())}/api/scripts/roleplay/audio/ring.wav"
    return relay_twiml(session, prelude=f'<Say voice="{loc.say_voice(session.get("locale"))}">{_xml(speakable(line, session.get("locale")))}</Say><Play>{ring}</Play>')


def say_hangup_twiml(text: str, locale: Optional[str] = None) -> str:
    return f'<?xml version="1.0" encoding="UTF-8"?><Response><Say voice="{loc.say_voice(locale)}">{_xml(speakable(text, locale))}</Say><Hangup/></Response>'


_RING_WAV: Optional[bytes] = None


def ring_wav() -> bytes:
    """US ringback (440 + 480 Hz, 2 s on / 1.2 s off, two rings), 8 kHz mono PCM, built once."""
    global _RING_WAV
    if _RING_WAV is None:
        import io
        import math
        import struct
        import wave
        rate = 8000
        frames = bytearray()
        for on, off in ((2.0, 1.2), (2.0, 0.6)):
            for i in range(int(rate * on)):
                t = i / rate
                v = 0.35 * (math.sin(2 * math.pi * 440 * t) + math.sin(2 * math.pi * 480 * t)) / 2
                frames += struct.pack("<h", int(v * 32767))
            frames += b"\x00\x00" * int(rate * off)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(bytes(frames))
        _RING_WAV = buf.getvalue()
    return _RING_WAV


def hangup_twiml(text: str, locale: Optional[str] = None) -> str:
    return f'<?xml version="1.0" encoding="UTF-8"?><Response><Say voice="{loc.say_voice(locale)}">{_xml(speakable(text, locale))}</Say><Hangup/></Response>'


async def start_phone_session(db, me: dict, script: dict, assignment: Optional[dict] = None) -> dict:
    """Create the session and ring the rep's cell; Twilio then fetches relay_twiml when they answer."""
    from routers.twilio_webhooks import normalize_phone
    from services.lead_call_engine import _twilio_client
    rep_phone = normalize_phone(me.get("phone") or "")
    if not rep_phone or len(rep_phone) < 11:
        raise ValueError("Add your cell number to your profile first, that is the phone we call")
    client = _twilio_client()
    if client is None:
        raise RuntimeError("Calling is not set up on this account yet")
    from_number = me.get("twilio_number") or me.get("mvpline_number") or os.environ.get("TWILIO_PHONE_NUMBER", "")
    if not from_number:
        raise RuntimeError("No number to call you from yet, ask your admin to assign one")
    store = await db.stores.find_one({"_id": ObjectId(me["store_id"])}, {"name": 1, "locale": 1}) if ObjectId.is_valid(str(me.get("store_id") or "")) else None
    persona = (assignment or {}).get("persona") or script.get("persona") or {"name": "Customer", "voice": "female", "summary": "A shopper calling about a vehicle.", "goals": "Learn more", "objections": [], "opening_line": "Hi, I'm calling about a car I saw online."}
    now = _now()
    token = uuid.uuid4().hex
    doc = {"user_id": str(me["_id"]), "rep_name": me.get("name") or "", "rep_phone": rep_phone, "from_number": from_number, "store_id": me.get("store_id"), "store_name": (store or {}).get("name") or "the store", "locale": loc.key_of(store),
           "script_id": str(script["_id"]), "script_title": script.get("title"), "script_slug": script.get("slug"), "direction": script_direction(script), "persona": persona, "curveballs": (assignment or {}).get("curveballs") or [],
           "assignment_id": str(assignment["_id"]) if assignment else None, "mode": "phone", "status": "dialing", "token": token, "turns": [], "started_at": now, "updated_at": now}
    res = await db.roleplay_sessions.insert_one(doc)
    sid = str(res.inserted_id)
    base = f"{_app_url()}/api/scripts/roleplay"
    try:
        call = await asyncio.to_thread(
            client.calls.create, to=rep_phone, from_=from_number, url=f"{base}/twiml/{sid}?t={token}", method="POST",
            status_callback=f"{base}/status/{sid}?t={token}", status_callback_event=["answered", "completed"], status_callback_method="POST",
            record=True, recording_status_callback=f"{base}/recording/{sid}?t={token}", recording_status_callback_event=["completed"], timeout=25, time_limit=CALL_TIME_LIMIT_S)
    except Exception as e:
        logger.warning(f"[Roleplay] could not place practice call: {e}")
        await db.roleplay_sessions.update_one({"_id": res.inserted_id}, {"$set": {"status": "failed", "fail_reason": "The call could not be placed", "updated_at": _now()}})
        raise RuntimeError("The call could not be placed, try again in a minute")
    await db.roleplay_sessions.update_one({"_id": res.inserted_id}, {"$set": {"call_sid": call.sid, "call_status": "queued"}})
    return {"session_id": sid, "status": "dialing", "direction": script_direction(script), "persona": {k: persona.get(k) for k in ("name", "summary", "voice")}, "script_title": script.get("title"), "rep_phone": rep_phone}


async def reconcile_dialing(db, s: dict) -> dict:
    """Status callbacks can be lost; after 30s of dialing ask Twilio directly so the app never spins forever."""
    started = s.get("started_at")
    if started and started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    if s.get("mode") != "phone" or s.get("status") != "dialing" or not s.get("call_sid") or not started or (_now() - started).total_seconds() < 30:
        return s
    from services.lead_call_engine import _twilio_client
    client = _twilio_client()
    if client is None:
        return s
    try:
        call = await asyncio.to_thread(client.calls(s["call_sid"]).fetch)
    except Exception as e:
        logger.debug(f"[Roleplay] reconcile fetch failed: {e}")
        return s
    sets = {"call_status": call.status, "updated_at": _now()}
    if call.status in FAIL_REASONS and s.get("kind") == "mystery_shop":
        from services.mystery_shops import record_outcome
        await record_outcome(db, {**s, "call_status": call.status}, call.status)
        return await db.roleplay_sessions.find_one({"_id": s["_id"]})
    if call.status in FAIL_REASONS:
        sets.update(status="failed", fail_reason=fail_label(call.status, s.get("from_number")))
    elif call.status == "in-progress":
        sets["status"] = "live"
    elif call.status == "completed":
        await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$set": sets})
        await finalize_session(db, str(s["_id"]), "reconciled_completed")
        return await db.roleplay_sessions.find_one({"_id": s["_id"]})
    await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$set": sets})
    return {**s, **sets}


async def relay_setup(db, sid: str, msg: dict):
    """ConversationRelay connected: the greeting is about to play, so the clock starts here."""
    s = await db.roleplay_sessions.find_one({"_id": ObjectId(sid)}, {"persona": 1, "turns": 1, "direction": 1, "kind": 1, "rep_name": 1})
    if not s:
        return
    now = _now()
    sets = {"status": "live", "call_status": "in-progress", "started_at": now, "updated_at": now}
    if msg.get("callSid"):
        sets["call_sid"] = msg["callSid"]
    update = {"$set": sets}
    if not s.get("turns") and s.get("direction") != "inbound":
        opening = (s.get("persona") or {}).get("opening_line") or "Hi, I'm calling about a car I saw online."
        update["$push"] = {"turns": {"role": "customer", "text": opening, "audio_url": None, "at": now, "mood": "neutral"}}
    await db.roleplay_sessions.update_one({"_id": s["_id"]}, update)


async def relay_turn(db, sid: str, heard: str) -> dict:
    s = await db.roleplay_sessions.find_one({"_id": ObjectId(sid)})
    if not s or s.get("status") not in ("live", "ending", "dialing"):
        return {"say": "", "ended": True}
    out = await customer_turn(db, s, heard[:1200])
    return {"say": speakable(out["customer"]["text"], s.get("locale")), "ended": out["ended"]}


INBOUND_NUDGE_S = 8


async def relay_nudge(db, sid: str) -> str:
    """Inbound call, ring played, rep still silent: the customer speaks first anyway so the call never sits dead."""
    s = await db.roleplay_sessions.find_one({"_id": ObjectId(sid)}, {"turns": 1, "direction": 1, "persona": 1, "status": 1, "locale": 1})
    if not s or s.get("status") not in ("live", "dialing") or s.get("turns") or s.get("direction") != "inbound":
        return ""
    opening = (s.get("persona") or {}).get("opening_line") or "Hi, I'm calling about a car I saw online."
    await db.roleplay_sessions.update_one({"_id": s["_id"], "turns": {"$size": 0}}, {"$push": {"turns": {"role": "customer", "text": opening, "audio_url": None, "at": _now(), "mood": "neutral"}}, "$set": {"updated_at": _now()}})
    return speakable(opening, s.get("locale"))


async def relay_interrupt(db, sid: str, spoken: Optional[str]):
    """Rep talked over the customer: keep only what was actually heard so grading matches the real call."""
    s = await db.roleplay_sessions.find_one({"_id": ObjectId(sid)}, {"turns": 1})
    turns = (s or {}).get("turns") or []
    if not turns or turns[-1].get("role") != "customer":
        return
    idx = len(turns) - 1
    sets = {f"turns.{idx}.interrupted": True}
    if spoken and spoken.strip():
        sets[f"turns.{idx}.text"] = spoken.strip()
    await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$set": sets})


async def finalize_session(db, sid: str, reason: str) -> Optional[dict]:
    """Call over (hang-up, customer ended, websocket closed): grade once, whoever gets here first."""
    claimed = await db.roleplay_sessions.find_one_and_update(
        {"_id": ObjectId(sid), "mode": "phone", "status": {"$in": ["live", "ending", "dialing"]}},
        {"$set": {"status": "grading", "ended_at": _now(), "end_reason": reason, "updated_at": _now()}})
    if not claimed:
        return None
    s = await db.roleplay_sessions.find_one({"_id": ObjectId(sid)})
    if not any(t.get("role") == "rep" for t in s.get("turns", [])):
        if s.get("kind") == "mystery_shop":
            from services.mystery_shops import record_outcome
            await record_outcome(db, s, "hung_up")
            return None
        await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$set": {"status": "abandoned", "fail_reason": "The call ended before you said anything", "updated_at": _now()}})
        return None
    try:
        return await grade_session(db, s)
    except Exception as e:
        logger.warning(f"[Roleplay] grading after phone call failed: {e}")
        await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$set": {"status": "failed", "fail_reason": "Grading failed, the call is saved", "updated_at": _now()}})
        return None


async def save_recording(db, sid: str, recording_url: str, duration: Optional[str]):
    """Pull the mp3 from Twilio into our storage so playback needs no Twilio auth. Attempts that never got past the announcement keep no recording."""
    import httpx
    from utils.image_storage import put_object
    s = await db.roleplay_sessions.find_one({"_id": ObjectId(sid)}, {"status": 1})
    if not s or s.get("status") in ("scheduled", "unreachable", "canceled"):
        return
    tw_sid, tw_tok = os.environ.get("TWILIO_ACCOUNT_SID", ""), os.environ.get("TWILIO_AUTH_TOKEN", "")
    mp3 = recording_url if recording_url.endswith(".mp3") else f"{recording_url}.mp3"
    for attempt in range(3):
        async with httpx.AsyncClient() as client:
            resp = await client.get(mp3, auth=(tw_sid, tw_tok), follow_redirects=True, timeout=60.0)
        if resp.status_code == 200 and resp.content:
            break
        await asyncio.sleep(2 + attempt * 2)
    else:
        logger.warning(f"[Roleplay] recording fetch failed for {sid}: HTTP {resp.status_code}")
        return
    path = f"roleplay/{sid}/call.mp3"
    stored = (await asyncio.to_thread(put_object, path, resp.content, "audio/mpeg")).get("path") or path
    sets = {"recording_url": f"/api/images/{stored}", "recording_twilio_url": recording_url, "updated_at": _now()}
    try:
        sets["recording_seconds"] = int(float(duration)) if duration else None
    except ValueError:
        pass
    await db.roleplay_sessions.update_one({"_id": ObjectId(sid)}, {"$set": sets})
    await db.call_evaluations.update_one({"roleplay_session_id": sid}, {"$set": {"recording_url": sets["recording_url"]}})


def _customer_system(script: dict, persona: dict, store_name: str, rep_first: str, curveballs: list, live: bool = False, direction: str = "outbound", mystery: bool = False, industry: Optional[str] = None, department: Optional[str] = None, locale: Optional[str] = None, channel: str = "call", covert: bool = False) -> str:
    from services import industries as ind
    industry = industry or (ind.industry_of_dept(department) if department else ind.DEFAULT_INDUSTRY)
    pack = ind.get(industry)
    rep_role = ind.dept(department, industry)["rep"] if department else ("a salesperson" if industry == "automotive" else "an employee")
    who = "a real car shopper" if industry == "automotive" else f"a real {pack['customer']} of a {pack['label'].lower()} business"
    # covert = a lead shop: you sent an inquiry online, the business is following up, and nobody there knows it is a shop
    lead_ctx = (f"You sent the {pack['business']} an inquiry online (an internet lead) and now THEY are following up with you, so they lead and you react like a real, interested but busy person. "
                "Nobody at the business knows this is a shop: stay fully in character as a real customer; never admit you are an AI, a bot or a shopper, even if asked directly. ")
    if channel == "email":
        return (f"You are {persona.get('name', 'a customer')}, {who} emailing {rep_first}, {rep_role} at {store_name}. "
                + (lead_ctx if covert else f"YOU emailed the {pack['business']} first, like a real internet lead who found them online, so you drive what you want. ")
                + "Stay fully in character as a real customer: never admit you are an AI, a bot or a shopper, even if asked directly; a real customer would just sound confused and keep going. "
                "This is an EMAIL thread: write like a real person emails a business from their phone. A one-line greeting, 2 to 5 short sentences, plain words, contractions, then sign off with just your first name. "
                "No subject line inside the body (the first email's subject goes in the separate subject field), no letter formality, no bullet lists, no emojis. "
                "Answer what they asked and add at most one or two things. A real email lead takes a few exchanges: price, availability, what is included, a time to come in, your trade, financing. "
                "If a reply took the rep a long time (noted like [replied after 3 h 10 min]) you may mention it once, mildly, the way a real person would. "
                + loc.language_rule(locale)
                + f"WHO YOU ARE: {persona.get('summary', '')} WHAT YOU WANT: {persona.get('goals', '')} "
                f"OBJECTIONS YOU RAISE (one at a time, only when it fits): {'; '.join(persona.get('objections') or [])}. "
                + (f"CURVEBALLS TO WORK IN: {'; '.join(curveballs)}. " if curveballs else "")
                + "RULES: Never narrate, never break character, never coach. Volunteer a little, not everything. If the rep earns it (clear answers, specific times), agree to come in and end warmly with a short final email. "
                  "If the rep is pushy, vague, sends a wall of boilerplate or throws out a blind number, push back; if they keep it up, lose interest and end politely. "
                  "Set ended to true on your closing email only: after the appointment or next step is set, after you decline for good, or when the rep clearly ends the conversation. Never end before exchange 3 unless the rep is rude. "
                  "No em dashes. Return ONLY JSON: {\"subject\": \"short subject, first email only, else empty\", \"say\": \"the email body with line breaks\", \"ended\": true|false, \"mood\": \"warm|neutral|guarded|annoyed\"}. "
                + f"The employee's script (they may or may not follow it): {script.get('title', '')}: {script.get('purpose', '')}")
    if channel == "text":
        return (f"You are {persona.get('name', 'a customer')}, {who} texting (SMS) with {rep_first}, {rep_role} at {store_name}. "
                + (lead_ctx if covert else f"YOU texted the {pack['business']} first, like a real lead who found them online, so you drive what you want. ")
                + "Stay fully in character as a real customer: never admit you are an AI, a bot or a shopper, even if asked directly; a real customer would just sound confused and keep going. "
                "This is an SMS thread: write like a real person texts. 1 or 2 short sentences, under 240 characters, casual, contractions, no sign-off, no lists, no emojis unless the rep used one first. "
                "Answer what they asked and add at most one thing. A real text lead takes several exchanges: price, availability, a time to come in, your trade, hours. "
                "If a reply took the rep a long time (noted like [replied after 40 min]) you may mention it once, mildly, the way a real person would. "
                + loc.language_rule(locale)
                + f"WHO YOU ARE: {persona.get('summary', '')} WHAT YOU WANT: {persona.get('goals', '')} "
                f"OBJECTIONS YOU RAISE (one at a time, only when it fits): {'; '.join(persona.get('objections') or [])}. "
                + (f"CURVEBALLS TO WORK IN: {'; '.join(curveballs)}. " if curveballs else "")
                + "RULES: Never narrate, never break character, never coach. Volunteer a little, not everything. If the rep earns it (clear answers, offers specific times), agree to come in and end warmly with a short final text. "
                  "If the rep is pushy, vague or throws out a blind number, push back; if they keep it up, lose interest and end politely. "
                  "Set ended to true on your closing text only: after the appointment or next step is set, after you decline for good, or when the rep clearly ends the conversation. Never end before exchange 4 unless the rep is rude. "
                  "No em dashes. Return ONLY JSON: {\"say\": \"your text message\", \"ended\": true|false, \"mood\": \"warm|neutral|guarded|annoyed\"}. "
                + f"The employee's script (they may or may not follow it): {script.get('title', '')}: {script.get('purpose', '')}")
    return (f"You are {persona.get('name', 'a customer')}, {who} on a phone call with {rep_first}, {rep_role} at {store_name}. "
            + (lead_ctx if covert else (f"YOU placed this call to the {pack['business']}, so you drive the reason for calling. " if direction == "inbound" else "The employee called YOU, so they drive the conversation and you react. "))
            + ("The rep was told this is a practice call, but you stay fully in character as a real customer: never admit you are an AI, a recording or a shopper, even if asked directly; a real customer would just sound confused and keep going. " if mystery and not covert else "")
            + ("This is a LIVE voice call: your words are read aloud the moment you answer, so keep every reply to 1 or 2 short spoken sentences, no lists, spell nothing out. "
               "The transcript of what the rep said may contain speech-to-text mistakes; interpret generously. " + numbers_rule(locale) if live else "")
            + loc.language_rule(locale)
            + f"WHO YOU ARE: {persona.get('summary', '')} WHAT YOU WANT: {persona.get('goals', '')} "
            f"OBJECTIONS YOU RAISE (one at a time, only when it fits): {'; '.join(persona.get('objections') or [])}. "
            + (f"CURVEBALLS TO WORK IN: {'; '.join(curveballs)}. " if curveballs else "")
            + "RULES: Speak like a real person on the phone: short, 1 to 3 sentences, contractions, occasional hesitation. Never narrate, never break character, never coach. "
              "Answer what the rep asks; volunteer a little, not everything. If the rep earns it (answers honestly, offers specific times), agree to an appointment and end warmly. "
              "If the rep is pushy, dodges, or throws out a blind number, push back. Say goodbye and end the call naturally after the appointment or next step is set, after you decline for good, "
            + ("or when the rep says goodbye. A real call runs as long as it needs to, often 5 to 10 minutes, so never rush to end it or count exchanges. "
               if live else "or if the call drags past 12 exchanges. ")
            + "No em dashes. Return ONLY JSON: {\"say\": \"your spoken words\", \"ended\": true|false, \"mood\": \"warm|neutral|guarded|annoyed\"}. "
              f"The employee's script (they may or may not follow it): {script.get('title', '')}: {script.get('purpose', '')}")


async def start_session(db, me: dict, script: dict, assignment: Optional[dict] = None) -> dict:
    store = await db.stores.find_one({"_id": ObjectId(me["store_id"])}, {"name": 1, "locale": 1}) if ObjectId.is_valid(str(me.get("store_id") or "")) else None
    persona = (assignment or {}).get("persona") or script.get("persona") or {"name": "Customer", "voice": "female", "summary": "A shopper calling about a vehicle.", "goals": "Learn more", "objections": [], "opening_line": "Hi, I'm calling about a car I saw online."}
    curveballs = (assignment or {}).get("curveballs") or []
    now = _now()
    direction = script_direction(script)
    doc = {"user_id": str(me["_id"]), "rep_name": me.get("name") or "", "store_id": me.get("store_id"), "store_name": (store or {}).get("name") or "the store", "locale": loc.key_of(store),
           "script_id": str(script["_id"]), "script_title": script.get("title"), "script_slug": script.get("slug"), "direction": direction, "persona": persona, "curveballs": curveballs,
           "assignment_id": str(assignment["_id"]) if assignment else None, "mode": "text", "status": "active", "turns": [], "started_at": now, "updated_at": now}
    res = await db.roleplay_sessions.insert_one(doc)
    sid = str(res.inserted_id)
    out = {"session_id": sid, "direction": direction, "persona": {k: persona.get(k) for k in ("name", "summary", "voice")}, "script_title": script.get("title"), "customer": None, "ended": False}
    if direction == "inbound":
        return out  # the customer is calling in: the rep answers first, the opening line comes back after their greeting
    opening = persona.get("opening_line") or "Hi, I'm calling about a car I saw online."
    turn = {"role": "customer", "text": opening, "audio_url": None, "at": now, "mood": "neutral"}
    await db.roleplay_sessions.update_one({"_id": res.inserted_id}, {"$push": {"turns": turn}})
    return {**out, "customer": _turn_out(turn)}


def _turn_out(t: dict) -> dict:
    return {"role": t["role"], "text": t["text"], "audio_url": t.get("audio_url"), "mood": t.get("mood"), "at": t["at"].isoformat() if hasattr(t["at"], "isoformat") else t["at"]}


async def customer_turn(db, session: dict, rep_text: str) -> dict:
    """Rep spoke -> the AI customer answers (text + audio)."""
    now = _now()
    if session.get("direction") == "inbound" and not session.get("turns"):
        # the rep just answered the phone: the customer opens with their scripted line, no model call needed
        persona = session.get("persona") or {}
        rep_turn = {"role": "rep", "text": rep_text, "at": now}
        cust_turn = {"role": "customer", "text": persona.get("opening_line") or "Hi, I'm calling about a car I saw online.", "audio_url": None, "at": now, "mood": "neutral"}
        await db.roleplay_sessions.update_one({"_id": session["_id"]}, {"$push": {"turns": {"$each": [rep_turn, cust_turn]}}, "$set": {"updated_at": now}})
        return {"rep": _turn_out(rep_turn), "customer": _turn_out(cust_turn), "ended": False}
    script = await db.scripts.find_one({"_id": ObjectId(session["script_id"])}) or {}
    persona = session.get("persona") or {}
    rep_first = (session.get("rep_name") or "the salesperson").split(" ")[0]
    history = "\n".join(f"{'CUSTOMER' if t['role'] == 'customer' else 'REP'}: {t['text']}" for t in session.get("turns", []))
    exchanges = sum(1 for t in session.get("turns", []) if t["role"] == "rep") + 1
    live = session.get("mode") == "phone"
    started = session.get("started_at")
    minutes = ((_now() - (started.replace(tzinfo=timezone.utc) if started and started.tzinfo is None else started)).total_seconds() / 60) if started else 0
    out_of_time = live and (minutes >= PHONE_MAX_MINUTES or exchanges >= PHONE_MAX_TURNS)
    user = f"CALL SO FAR:\n{history}\nREP: {rep_text}\n\n(This is exchange {exchanges}. Reply as the customer." + (" You are out of time: wrap up in one sentence, say goodbye and set ended to true.)" if out_of_time else ")")
    try:
        data = await _llm_json(_customer_system(script, persona, session.get("store_name") or "the business", rep_first, session.get("curveballs") or [], live, session.get("direction") or "outbound", session.get("kind") == "mystery_shop",
                                                session.get("industry"), session.get("department") if session.get("kind") == "mystery_shop" else None, session.get("locale"), covert=bool(session.get("lead_shop_id"))), user, timeout=45)
    except Exception as e:
        logger.warning(f"[Roleplay] customer turn failed: {e}")
        data = {}
    say = no_em_dash(str(data.get("say") or "Sorry, could you say that again?")).strip()[:600]
    ended = bool(data.get("ended")) or out_of_time or (not live and exchanges >= MAX_TURNS)
    rep_turn = {"role": "rep", "text": rep_text, "at": now}
    cust_turn = {"role": "customer", "text": say, "audio_url": None, "at": now, "mood": data.get("mood") or "neutral"}
    await db.roleplay_sessions.update_one({"_id": session["_id"]}, {"$push": {"turns": {"$each": [rep_turn, cust_turn]}}, "$set": {"updated_at": now, **({"status": "ending"} if ended else {})}})
    return {"rep": _turn_out(rep_turn), "customer": _turn_out(cust_turn), "ended": ended}


def transcript_text(session: dict) -> str:
    return "\n".join(f"{'CUSTOMER' if t['role'] == 'customer' else 'REP'}: {t['text']}" for t in session.get("turns", []))


async def grade_session(db, session: dict) -> dict:
    """Score with the store's scorecard (same grader as real calls) + script adherence + coaching, stored as a call_evaluation."""
    from services import scorecards as sc
    script = await db.scripts.find_one({"_id": ObjectId(session["script_id"])}) or {}
    from services import text_shops as tx
    shop = session.get("kind") == "mystery_shop"
    rep = ({"name": session.get("rep_name") or "Rep"} if shop else await db.users.find_one({"_id": ObjectId(session["user_id"])})) or {}
    rep_first = (rep.get("first_name") or (rep.get("name") or "Rep").split(" ")[0])
    transcript = transcript_text(session)
    rep_turns = [t for t in session.get("turns", []) if t["role"] == "rep"]
    started = session.get("started_at")
    if started and started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    ended = session.get("ended_at") or _now()
    if ended.tzinfo is None:
        ended = ended.replace(tzinfo=timezone.utc)
    duration_s = int((ended - started).total_seconds()) if started else 0
    persona = session.get("persona") or {}
    text = shop and session.get("mode") == "text"
    email = shop and session.get("mode") == "email"
    from services import email_shops as ems
    thread = tx if text else ems if email else None
    card = None
    if shop:
        from services.mystery_shops import scorecard_for
        card = await scorecard_for(db, session)
        if thread and card:
            card = thread.speed_card(card, session.get("locale"))
    elif script.get("scorecard_id") and ObjectId.is_valid(str(script["scorecard_id"])):
        card = await db.scorecards.find_one({"_id": ObjectId(script["scorecard_id"]), "active": {"$ne": False}})
    elif script.get("pool") == "mystery_shop" and script.get("department"):
        from services.mystery_shops import template_card
        card = template_card(script["department"])
    if not card and not shop:
        card = await sc.pick_scorecard(db, rep, None)
    graded = None
    if card and card.get("criteria") and len(rep_turns) >= (1 if thread else 2):
        try:
            graded = await sc.grade_with_ai(card, (thread.grader_transcript(session) if thread else transcript).replace("REP:", f"{rep_first}:"), rep_first, persona.get("name") or "the customer", session.get("direction") or "inbound", max(duration_s, 60),
                                            industry=session.get("industry"), language=loc.dialect(session.get("locale")), channel="text" if text else "email" if email else "call")
            if thread and graded:
                thread.apply_speed(session, graded)
        except Exception as e:
            logger.warning(f"[Roleplay] scorecard grading failed: {e}")
    adherence = await _grade_adherence(script, transcript, rep_first) if len(rep_turns) >= 1 else {"score_pct": None, "hits": [], "misses": [], "coaching": [], "summary": "Too short to grade."}
    pct, misses = (sc.compute_score(graded["results"], card["criteria"]) if graded else (None, []))
    now = _now()
    ev = {
        "call_sid": f"RP_{session['_id']}", "is_roleplay": not shop, "is_mystery_shop": shop, "roleplay_session_id": str(session["_id"]), "assignment_id": session.get("assignment_id"),
        "shop_client_id": session.get("client_id"), "shop_target_id": session.get("target_id"),
        "user_id": session.get("user_id"), "rep_name": rep.get("name") or rep_first, "store_id": session.get("store_id"),
        "contact_id": None, "contact_name": f"{persona.get('name', 'AI customer')} ({'mystery shopper' if shop else 'practice'})", "conversation_id": None, "inbox_id": None,
        "scorecard_id": str(card["_id"]) if card and card.get("_id") else None, "scorecard_name": card.get("name") if card else None, "department": (card or {}).get("department") or "",
        "duration_s": duration_s, "direction": session.get("direction") or "inbound", "call_at": session.get("started_at") or now,
        "results": (graded or {}).get("results") or [], "score_pct": pct, "critical_misses": misses,
        "summary": (graded or {}).get("summary") or adherence.get("summary") or "", "wins": (graded or {}).get("wins") or adherence.get("hits") or [],
        "coaching": ((graded or {}).get("coaching") or []) + adherence.get("coaching", []), "customer_sentiment": (graded or {}).get("customer_sentiment") or "",
        "call_type": "mystery_shop" if shop else "roleplay", "script_id": session["script_id"], "script_title": session.get("script_title"),
        "channel": "text" if text else "email" if email else "call", **({"text_stats": tx.stats(session)} if thread else {}),
        "adherence": adherence, "transcript": transcript, "model": MODEL[1], "graded_by": "ai", "created_at": now, "updated_at": now, "alerts_sent_at": None, "alerted_user_ids": [],
    }
    res = await db.call_evaluations.update_one({"call_sid": ev["call_sid"]}, {"$set": ev}, upsert=True)
    ev_doc = await db.call_evaluations.find_one({"call_sid": ev["call_sid"]}, {"_id": 1})
    ev_id = str(ev_doc["_id"])
    await db.roleplay_sessions.update_one({"_id": session["_id"]}, {"$set": {"status": "completed", "ended_at": now, "evaluation_id": ev_id, "score_pct": pct, "adherence_pct": adherence.get("score_pct"), "updated_at": now}})
    if session.get("enrollment_id"):
        from services.courses import record_result
        try:
            await record_result(db, session, pct)
        except Exception as e:
            logger.warning(f"[Roleplay] course progress update failed: {e}")
    if shop:
        from services.mystery_shops import after_graded
        try:
            await after_graded(db, str(session["_id"]))
        except Exception as e:
            logger.warning(f"[Roleplay] mystery shop follow-up failed: {e}")
    if not shop and session.get("assignment_id") and ObjectId.is_valid(str(session["assignment_id"])):
        await db.mystery_shops.update_one({"_id": ObjectId(session["assignment_id"])}, {"$set": {f"completed.{session['user_id']}": {"session_id": str(session["_id"]), "evaluation_id": ev_id, "score_pct": pct, "adherence_pct": adherence.get("score_pct"), "at": now}}})
    return {"evaluation_id": ev_id, "score_pct": pct, "scorecard_name": ev["scorecard_name"], "critical_misses": sc.miss_labels(ev), "adherence": adherence,
            "summary": ev["summary"], "wins": ev["wins"], "coaching": ev["coaching"], "customer_sentiment": ev["customer_sentiment"], "duration_s": duration_s, "results": ev["results"]}


async def _grade_adherence(script: dict, transcript: str, rep_first: str) -> dict:
    points = script.get("success_points") or []
    if not points:
        return {"score_pct": None, "hits": [], "misses": [], "coaching": [], "summary": ""}
    system = ("You grade whether an employee followed their phone script on a practice call. Return ONLY JSON: "
              "{\"points\": [{\"point\": str, \"hit\": true|false, \"evidence\": \"short quote or empty\"}], \"summary\": \"2 sentences, plain\", "
              "\"coaching\": [\"up to 3 specific, kind, actionable tips\"]}. Judge intent, not exact wording. No em dashes.")
    user = f"SCRIPT: {script.get('title')}\nPOINTS A GREAT CALL HITS:\n" + "\n".join(f"- {p}" for p in points) + f"\n\nCALL TRANSCRIPT ({rep_first} is REP):\n{transcript}"
    try:
        data = await _llm_json(system, user, timeout=60)
    except Exception as e:
        logger.warning(f"[Roleplay] adherence grading failed: {e}")
        data = {}
    rows = [{"point": str(p.get("point") or ""), "hit": bool(p.get("hit")), "evidence": no_em_dash(str(p.get("evidence") or ""))[:200]} for p in (data.get("points") or []) if p.get("point")]
    if not rows:
        return {"score_pct": None, "points": [], "hits": [], "misses": [], "coaching": [], "summary": "Script points could not be graded this time."}
    hits = [r["point"] for r in rows if r["hit"]]
    return {"score_pct": int(round(100 * len(hits) / len(rows))) if rows else None, "points": rows, "hits": hits, "misses": [r["point"] for r in rows if not r["hit"]],
            "coaching": [no_em_dash(str(c)) for c in (data.get("coaching") or [])][:3], "summary": no_em_dash(str(data.get("summary") or ""))}
