"""Call guides: the read-along script + KPI scorecard a person follows during a practice shop.
Kubota's four Customer Engagement Standards are seeded verbatim; every other industry/department gets one written by
Jessi on first open, in the same shape, from that department's success points and scorecard, then cached."""
import logging
from datetime import datetime, timezone
from typing import Optional

from services import industries as ind

logger = logging.getLogger(__name__)

SEED_VERSION = 1
BLOCK_KINDS = ("say", "ask", "label", "note", "warn", "list")


def _say(*t):
    return [{"kind": "say", "text": x} for x in t]


def _ask(*t):
    return [{"kind": "ask", "text": x} for x in t]


def _label(t):
    return [{"kind": "label", "text": t}]


def _note(*t):
    return [{"kind": "note", "text": x} for x in t]


def _warn(*t):
    return [{"kind": "warn", "text": x} for x in t]


def _list(*t):
    return [{"kind": "list", "text": x} for x in t]


KUBOTA_SALES = {
    "title": "Kubota Sales Customer Engagement Standard",
    "kpi_chain": ["DISCOVER", "RECOMMEND", "ADVANCE", "REMEMBER"],
    "kpi_note": "Every qualified sales conversation should accomplish four things. The salesperson should understand the customer's application before recommending equipment and create a specific next step before ending the conversation.",
    "sections": [
        {"title": "Open strong",
         "blocks": _say("Thanks for calling [DEALERSHIP], this is [NAME] in Sales. Who am I speaking with?", "Great to meet you, [CUSTOMER]. What can I help you accomplish?"),
         "kpi": ["Introduce yourself", "Get customer's name", "Use customer's name naturally", "Ask an open-ended question"]},
        {"title": "Discover the job",
         "blocks": _label("If the customer asks about a specific machine:") + _say("Absolutely. Tell me a little about what you're planning to use it for.")
                   + _label("Follow with the questions that fit:")
                   + _ask("What are the main jobs you want this machine doing?", "How much property are you working?", "What kind of terrain are you dealing with?",
                          "What are you moving, lifting, mowing, digging or pulling?", "How often will you use it?", "What attachments or implements do you anticipate using?",
                          "Do you currently own equipment?", "What are you running now?", "What do you like about it?", "What do you wish it did better?"),
         "kpi": ["Primary application", "Secondary application", "Operating environment", "Frequency / utilization", "Current equipment"]},
        {"title": "Find the pain",
         "blocks": _ask("What made you start looking now?", "What are you trying to accomplish that your current equipment isn't doing?", "If you could change one thing about what you're running now, what would it be?")
                   + _label("For commercial customers:") + _ask("When equipment is down, what does that do to your operation?"),
         "kpi": ["Identify WHY the customer is shopping", "Identify current pain / problem", "Understand urgency"]},
        {"title": "Understand the buying decision",
         "blocks": _ask("What other equipment have you looked at?", "Are there other brands you're considering?", "What matters most to you when you're making this decision?",
                        "When would you ideally like to have the machine?", "Will you be replacing or trading anything?")
                   + _label("When appropriate:") + _ask("Are you planning on financing it, or are you still figuring out how you want to structure the purchase?"),
         "kpi": ["Competition identified", "Timing identified", "Trade identified", "Decision criteria identified", "Financing / payment conversation when appropriate"]},
        {"title": "Recommend, don't recite",
         "blocks": _label("Transition:") + _say("Based on what you've told me, here's where I'd start.")
                   + _note("Connect the recommendation to Kubota's PRO framework.")
                   + _label("PRODUCTIVITY") + _say("This makes sense for you because…") + _note("Explain how the machine helps accomplish the customer's actual work.")
                   + _label("RELIABILITY") + _say("You mentioned downtime is a big concern…") + _note("Connect dealer support, maintenance, durability or uptime to the customer's situation.")
                   + _label("OPERATOR EXPERIENCE") + _say("You said you're spending six or seven hours at a time in the machine…") + _note("Connect comfort, controls, visibility or ease of operation to their needs."),
         "kpi": ["Recommendation tied directly to discovery", "Productivity addressed", "Reliability addressed when relevant", "Operator experience addressed when relevant", "No meaningless feature dump"]},
        {"title": "Check alignment",
         "blocks": _ask("How does that compare with what you had in mind?", "What questions or concerns do you have about that setup?") + _note("Listen.") + _warn("Do not immediately defend the recommendation."),
         "kpi": ["Asked how it compares", "Listened before answering"]},
        {"title": "Advance the customer",
         "blocks": _warn("Never finish with: \"Let us know if you have any questions.\"") + _label("Instead:")
                   + _say("The best next step is to actually put you on the machine. I can have one ready for you. Would today or tomorrow work better?",
                          "Let's get the trade information together and I'll build this around your actual numbers.",
                          "Let's schedule a demo so you can see whether this actually does what you need it to do."),
         "kpi": ["Specific next step requested", "Date / time attempted", "Appointment, demo, quote or trade action established"]},
        {"title": "Remember",
         "blocks": _label("Before ending:") + _ask("What's the best number to reach you?", "And what's the best email?")
                   + _label("Document:") + _list("Equipment discussed", "Equipment currently owned", "Property / business", "Acreage", "Applications", "Attachments", "Competitors", "Trade", "Timing", "Future equipment needs", "Personal / contextual information learned"),
         "kpi": ["Best number captured", "Best email captured", "Notes documented"]},
    ],
    "scorecard": [("Customer Name", 5), ("Contact Information", 5), ("Application Discovery", 15), ("Current Equipment", 5), ("Pain / Need", 10), ("Timing", 5), ("Competition", 5),
                  ("Trade / Financing", 5), ("Solution Alignment", 15), ("Value / PRO", 10), ("Specific Next Step", 15), ("Relationship Intelligence", 5)],
}

KUBOTA_SERVICE = {
    "title": "Kubota Service Customer Engagement Standard",
    "kpi_chain": ["UNDERSTAND", "OWN", "SET EXPECTATIONS", "FOLLOW THROUGH"],
    "kpi_note": "The customer should never wonder: \"Does this person understand my problem?\" or \"What happens next?\"",
    "sections": [
        {"title": "Open",
         "blocks": _say("Thanks for calling [DEALERSHIP] Service, this is [NAME]. Who am I speaking with?", "Thanks, [CUSTOMER]. Tell me what's going on with your Kubota."),
         "kpi": ["Name", "Rapport", "Open-ended question"]},
        {"title": "Identify equipment",
         "blocks": _ask("What model are we working with?", "Do you have the serial number available?", "About how many hours are on it?", "How are you primarily using the machine?"),
         "kpi": ["Model", "Serial number when necessary", "Hours", "Application"]},
        {"title": "Understand the concern",
         "blocks": _ask("Tell me exactly what it's doing.", "When did you first notice it?", "Does it happen every time or intermittently?", "Any warning lights or messages?",
                        "Did anything happen immediately before this started?", "Is the machine currently operational?") + _warn("Never guess at the diagnosis."),
         "kpi": ["Symptoms documented", "Timeline", "Warning information", "Operational status", "No unsupported diagnosis"]},
        {"title": "Understand urgency",
         "blocks": _ask("What do you have coming up that you need the machine for?") + _label("Commercial:") + _ask("Is this machine currently holding up a job or crew?", "When do you absolutely need to be operational?"),
         "kpi": ["Customer deadline", "Business impact", "Priority established"]},
        {"title": "Own the problem",
         "blocks": _label("Use language like:") + _say("I understand. Let's figure out the best way to get this moving.") + _warn("NOT: \"Yeah, we're pretty backed up.\"")
                   + _note("Even if scheduling is difficult, own the next action."),
         "kpi": ["Owned the next action"]},
        {"title": "Set expectations",
         "blocks": _label("Explain clearly:") + _list("What happens next", "Who takes action", "What information is needed", "Drop-off / pickup process", "When the customer should expect communication")
                   + _label("Example:") + _say("Here's what we're going to do. I'll get this documented for our service team. Once we've inspected the machine, we'll contact you before moving forward with repairs outside what we've discussed.")
                   + _warn("Never promise completion dates or diagnoses that cannot be verified."),
         "kpi": ["Next step explained", "Who does what", "When they hear from us"]},
        {"title": "Maintenance opportunity",
         "blocks": _label("When appropriate:") + _say("While we have it here, would you like us to check where you are on scheduled maintenance?") + _note("This should be helpful, not a forced upsell."),
         "kpi": ["Maintenance offered when it fits"]},
        {"title": "Close",
         "blocks": _say("So we're set for [ACTION]. The best number for updates is still [NUMBER], correct?", "You'll hear from us by [APPROPRIATE EXPECTATION]."),
         "kpi": ["Action recapped", "Number confirmed", "Follow-up time given"]},
    ],
    "scorecard": [("Customer Identification", 5), ("Equipment Identification", 10), ("Hours / Application", 5), ("Concern Discovery", 15), ("Diagnostic Questions", 10), ("Urgency / Business Impact", 10),
                  ("Empathy / Ownership", 10), ("Technical Discipline", 10), ("Expectations", 10), ("Specific Next Step", 10), ("Relationship Intelligence", 5)],
}

KUBOTA_PARTS = {
    "title": "Kubota Parts Customer Engagement Standard",
    "kpi_chain": ["IDENTIFY", "VERIFY", "COMPLETE THE JOB", "CREATE NEXT STEP"],
    "kpi_note": "Accuracy beats speed when guessing creates another trip to the dealership.",
    "sections": [
        {"title": "Open",
         "blocks": _say("Thanks for calling [DEALERSHIP] Parts, this is [NAME]. Who am I speaking with?", "What can I help you find today?"),
         "kpi": ["Name", "Open-ended question"]},
        {"title": "Identify",
         "blocks": _ask("What Kubota are we working on?", "What model?", "Do you have the serial number available?", "What are you working on or trying to accomplish?") + _warn("Never guess compatibility."),
         "kpi": ["Customer identified", "Machine identified", "Correct application verified"]},
        {"title": "Understand the job",
         "blocks": _label("For maintenance:") + _ask("Are you doing a complete service or replacing just that item?", "What service are you performing?")
                   + _label("For repair:") + _ask("Tell me what's being replaced.")
                   + _label("For a commercial customer:") + _ask("Is the machine currently down?", "Do you have a crew or job waiting on it?"),
         "kpi": ["Understand WHY the part is needed", "Understand urgency"]},
        {"title": "Verify",
         "blocks": _label("Verify the correct component before promising:") + _list("Fit / application", "Quantity", "Availability", "Required related components") + _warn("Never claim inventory without verification."),
         "kpi": ["Fit verified", "Quantity confirmed", "Availability checked", "Related components covered"]},
        {"title": "Complete the job",
         "blocks": _ask("What else do you need to finish the job?")
                   + _label("For scheduled maintenance:") + _ask("Do you already have your other filters, fluids and maintenance items?")
                   + _label("For attachments / repairs:") + _ask("Do you have everything else you'll need once you start the repair?")
                   + _note("This is not an upsell. It prevents the customer from making another trip because nobody bothered to ask."),
         "kpi": ["Asked what else finishes the job"]},
        {"title": "Value",
         "blocks": _label("If Genuine Kubota Parts pricing is challenged:")
                   + _say("I understand. My priority is making sure we're giving you the correct part for your machine. With Genuine Kubota Parts, we're matching the component to the equipment specifications rather than guessing based on something that looks compatible.")
                   + _warn("Never attack competitors or aftermarket suppliers."),
         "kpi": ["Value explained without bashing"]},
        {"title": "Close",
         "blocks": _say("So I've got [PART / ITEM] for your [MACHINE]. Here's the next step…") + _label("Confirm:") + _list("Availability / status", "Quantity", "Pickup / order process", "Contact information", "Expected next action"),
         "kpi": ["Availability / status", "Quantity", "Pickup / order process", "Contact information", "Expected next action"]},
    ],
    "scorecard": [("Customer Identification", 5), ("Equipment Identification", 15), ("Serial / Application Verification", 10), ("Job Discovery", 10), ("Accuracy", 15), ("Urgency", 10),
                  ("Complete-the-Job Questions", 10), ("Value Communication", 5), ("Availability / Expectation Accuracy", 5), ("Specific Next Step", 10), ("Relationship Intelligence", 5)],
}

KUBOTA_RENTAL = {
    "title": "Kubota Rental Customer Engagement Standard",
    "kpi_chain": ["QUALIFY THE JOB BEFORE QUOTING THE MACHINE"],
    "kpi_note": "The customer's opening request is not necessarily the equipment they actually need.",
    "sections": [
        {"title": "Open",
         "blocks": _say("Thanks for calling [DEALERSHIP] Rental, this is [NAME]. Who am I speaking with?", "What are you working on?")
                   + _warn("NOT immediately: \"What machine do you want?\"") + _note("Start with the job."),
         "kpi": ["Name", "Started with the job, not the machine"]},
        {"title": "Discover the project",
         "blocks": _ask("Tell me about the project.", "What exactly are you trying to accomplish?", "When does the job start?", "How long do you expect to need the equipment?", "Is this residential, agricultural or commercial?"),
         "kpi": ["Project", "Application", "Start date", "Duration"]},
        {"title": "Qualify equipment",
         "blocks": _label("Depending on the application:") + _ask("How deep are you digging?", "How much material are you moving?", "What are the ground conditions?", "Any width or access restrictions?",
                                                                    "What are you lifting?", "What attachments will you need?", "Have you operated this type of equipment before?"),
         "kpi": ["Size / capability", "Environment", "Access", "Attachment", "Operator considerations"]},
        {"title": "Logistics",
         "blocks": _ask("How are you planning on getting the machine to the job?", "Will you need us to deliver it?", "Where is the job located?", "When do you need it onsite?"),
         "kpi": ["Transportation", "Delivery", "Location", "Timing"]},
        {"title": "Recommend",
         "blocks": _say("Based on what you're doing, here's where I'd start…") + _note("Explain WHY.") + _warn("Do not simply say: \"You need a KX040.\"") + _note("Explain what requirement caused the recommendation."),
         "kpi": ["Recommendation explained by requirement"]},
        {"title": "Price",
         "blocks": _label("Once properly qualified:") + _say("Now that I understand the job, let's look at the rental options.")
                   + _warn("Never sacrifice proper qualification just because the customer begins with: \"How much?\""),
         "kpi": ["Qualified before quoting"]},
        {"title": "Repeat rental / purchase signal",
         "blocks": _label("If appropriate:") + _ask("How often are you renting this type of machine?") + _label("If frequently:") + _ask("How many days would you say you rented one over the last year?")
                   + _label("When utilization warrants it:")
                   + _say("You may be getting to the point where it's worth comparing what you're spending in rental with ownership. Would you like me to have someone run that comparison with you?")
                   + _note("This is a handoff opportunity, not a hard sell."),
         "kpi": ["Utilization asked", "Ownership comparison offered when it fits"]},
        {"title": "Close",
         "blocks": _label("Confirm:") + _list("Equipment", "Attachment", "Dates", "Duration", "Delivery / transportation", "Location", "Customer information", "Availability / status", "Next action"),
         "kpi": ["Equipment and attachment", "Dates and duration", "Delivery and location", "Customer information", "Availability and next action"]},
    ],
    "scorecard": [("Customer Identification", 5), ("Project Discovery", 15), ("Application", 10), ("Equipment Qualification", 15), ("Access / Ground Conditions", 5), ("Attachments", 5),
                  ("Duration / Timing", 10), ("Transportation / Delivery", 10), ("Recommendation Quality", 10), ("Specific Next Step", 10), ("Relationship / Buy Signal", 5)],
}

SEEDS = {("equipment", "eq_sales"): KUBOTA_SALES, ("equipment", "eq_service"): KUBOTA_SERVICE, ("equipment", "eq_parts"): KUBOTA_PARTS, ("equipment", "eq_rental"): KUBOTA_RENTAL}


def _now():
    return datetime.now(timezone.utc)


def _shape(g: dict) -> dict:
    """Normalise a guide (seed or model output) into the stored shape; drops anything malformed."""
    sections = []
    for s in g.get("sections") or []:
        blocks = [{"kind": b.get("kind") if b.get("kind") in BLOCK_KINDS else "note", "text": str(b.get("text") or "").strip()} for b in (s.get("blocks") or []) if isinstance(b, dict) and str(b.get("text") or "").strip()]
        kpi = [str(k).strip() for k in (s.get("kpi") or []) if str(k).strip()]
        if str(s.get("title") or "").strip() and (blocks or kpi):
            sections.append({"title": str(s["title"]).strip(), "blocks": blocks, "kpi": kpi})
    scorecard = []
    for row in g.get("scorecard") or []:
        label, pts = (row if isinstance(row, (list, tuple)) else (row.get("label"), row.get("points")))
        try:
            pts = int(pts)
        except (TypeError, ValueError):
            continue
        if str(label or "").strip() and pts > 0:
            scorecard.append({"label": str(label).strip(), "points": pts})
    return {"title": str(g.get("title") or "").strip(), "kpi_chain": [str(x).strip() for x in (g.get("kpi_chain") or []) if str(x).strip()][:5],
            "kpi_note": str(g.get("kpi_note") or "").strip(), "sections": sections, "scorecard": scorecard, "total": sum(r["points"] for r in scorecard)}


async def ensure_call_guides(db) -> int:
    """Seed / refresh the Kubota guides (never touches a guide an admin has customised)."""
    n = 0
    for (industry, department), g in SEEDS.items():
        cur = await db.call_guides.find_one({"industry": industry, "department": department}, {"source": 1, "seed_version": 1})
        if cur and (cur.get("source") == "custom" or (cur.get("seed_version") or 0) >= SEED_VERSION):
            continue
        await db.call_guides.update_one({"industry": industry, "department": department},
                                        {"$set": {**_shape(g), "source": "seed", "seed_version": SEED_VERSION, "updated_at": _now()}, "$setOnInsert": {"created_at": _now()}}, upsert=True)
        n += 1
    return n


def valid_keys(industry: Optional[str], department: Optional[str]) -> bool:
    return industry in ind.INDUSTRIES and department in ind.dept_keys(industry)


def guide_url(industry: str, department: str) -> str:
    from services.scripts import _app_url
    return f"{_app_url()}/guide/{industry}/{department}"


def serialize(g: dict) -> dict:
    d = ind.dept(g["department"], g["industry"])
    return {"industry": g["industry"], "industry_label": ind.get(g["industry"])["label"], "department": g["department"], "department_label": d.get("label") or g["department"],
            "title": g.get("title"), "kpi_chain": g.get("kpi_chain") or [], "kpi_note": g.get("kpi_note") or "", "sections": g.get("sections") or [], "scorecard": g.get("scorecard") or [],
            "total": g.get("total") or sum(r.get("points", 0) for r in g.get("scorecard") or []), "source": g.get("source"), "url": guide_url(g["industry"], g["department"]),
            "updated_at": g.get("updated_at").isoformat() if g.get("updated_at") else None}


async def get_guide(db, industry: str, department: str, build: bool = True) -> Optional[dict]:
    """Cached guide for an industry/department; Jessi writes it on first open when there is no seed."""
    g = await db.call_guides.find_one({"industry": industry, "department": department})
    if g or not build:
        return g
    written = await write_guide(industry, department)
    if not written:
        return None
    doc = {**written, "industry": industry, "department": department, "source": "ai", "created_at": _now(), "updated_at": _now()}
    await db.call_guides.update_one({"industry": industry, "department": department}, {"$setOnInsert": doc}, upsert=True)
    return await db.call_guides.find_one({"industry": industry, "department": department})


async def write_guide(industry: str, department: str) -> Optional[dict]:
    """Jessi drafts a Customer Engagement Standard for a department, modelled on the Kubota Sales one."""
    from services import scripts as scr
    pack, d = ind.get(industry), ind.dept(department, industry)
    criteria = [c.get("text") for c in (d.get("scorecard") or {}).get("criteria") or [] if c.get("text")]
    system = ("You write phone-call playbooks a frontline employee reads along with DURING a live call to score 100 on the mystery shop that follows. "
              "Match this exact JSON shape and this level of concreteness (this is the example for equipment sales):\n" + _example() +
              "\nRules: 6 to 8 sections in the order the call happens (open, discover, pain or urgency, decision or verification, recommend or set expectations, check or value, advance to a specific next step, remember/document). "
              "Block kinds: 'say' = a word-for-word line the employee says, 'ask' = a question to ask, 'label' = a short sub-heading like 'For commercial customers:', "
              "'note' = a one-line coaching note, 'warn' = something never to do (start with 'Never' or 'NOT:'), 'list' = an item to confirm or document. "
              "Use [BUSINESS], [NAME], [CUSTOMER] placeholders. Plain spoken English, no em dashes, no emoji. Each section has 2 to 6 kpi checklist items. "
              "The scorecard has 9 to 12 categories whose points sum to exactly 100, and it must cover every criterion below. Return ONLY the JSON object.")
    user = (f"Industry: {pack['label']}. Department: {d.get('label')}. The employee is {d.get('rep')}. The caller is {pack.get('customer', 'a customer')}. "
            f"What the call is: {d.get('brief') or d.get('call')}.\nScorecard criteria the guide must make easy to hit:\n- " + "\n- ".join(criteria) +
            f"\nTitle it '{pack['label']} {d.get('label')} Customer Engagement Standard'.")
    try:
        data = await scr._llm_json(system, user, timeout=90)
    except Exception as e:
        logger.warning(f"[CallGuides] {industry}/{department} draft failed: {e}")
        return None
    shaped = _shape(data or {})
    if len(shaped["sections"]) < 4 or not shaped["scorecard"]:
        logger.warning(f"[CallGuides] {industry}/{department} draft too thin: {len(shaped['sections'])} sections, {len(shaped['scorecard'])} scorecard rows")
        return None
    if shaped["total"] != 100 and shaped["total"] > 0:  # rescale so the self-score reads out of 100
        scale = 100 / shaped["total"]
        for r in shaped["scorecard"]:
            r["points"] = max(1, round(r["points"] * scale))
        diff = 100 - sum(r["points"] for r in shaped["scorecard"])
        shaped["scorecard"][0]["points"] += diff
        shaped["total"] = 100
    return shaped


def _example() -> str:
    import json
    g = _shape(KUBOTA_SALES)
    g["sections"] = g["sections"][:3]
    return json.dumps(g, ensure_ascii=False)


def guide_sms(client: dict, person: dict, guide: dict, sender_first: str) -> str:
    first = (person.get("name") or "there").split(" ")[0]
    brand = (client.get("brand") or "").strip()
    dept = (ind.dept(guide["department"], guide["industry"]).get("label") or "").lower()
    what = f"{brand} {dept}".strip() if brand else dept
    return (f"Hi {first}, it's {sender_first} with I'm On Social. Your {what} practice call is coming up. "
            f"Read along with the call guide and go for 100: {guide_url(guide['industry'], guide['department'])}")
