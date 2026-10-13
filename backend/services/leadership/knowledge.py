"""Company Intelligence foundation: structured facts with status, source, freshness and access class; rule-based knowledge readiness per executive;
keyword passages from Company Docs. Facts are data for the executives, never instructions, and an AI recommendation never becomes a fact by itself."""
import re
from datetime import datetime, timedelta, timezone

from services import command_center as cc
from services import command_center_ai as ai
from services.doc_access import RESTRICTED_CATEGORIES

FACTS = "ck_facts"
DOMAINS = ("strategy", "products", "technology", "customers", "commercial", "financials", "operations", "departments", "decisions", "compliance")
STATUSES = ("proposed", "verified", "disputed", "retired")
KINDS = ("fact", "assumption", "projection", "policy", "decision", "historical")
VISIBILITY = ("founder", "exec", "company")
FRESH_DAYS = {"financials": 35, "technology": 90, "products": 90, "customers": 120, "commercial": 120, "operations": 180, "departments": 180, "strategy": 180, "compliance": 365, "decisions": 3650}
SOURCE_KINDS = ("command_center", "document", "platform", "human", "integration", "interview", "agent_proposal", "request_log")


def _now():
    return datetime.now(timezone.utc)


def _aware(dt):
    return dt.replace(tzinfo=timezone.utc) if isinstance(dt, datetime) and dt.tzinfo is None else dt


# Facts about the first company that can be read off the repository and its documentation. Anything commercial or financial that no paying customer
# or ledger has confirmed is seeded as `proposed` and labelled assumption; the founder verifies in the app.
IMOS_SEED = [
    ("technology.stack", "technology", "fact", "verified", "The platform is a FastAPI backend with MongoDB (Motor) and an Expo React Native app (web, iOS, Android); Twilio handles voice and SMS; OpenAI models run through the Emergent key; files live in Emergent object storage.", "platform", "docs/ARCHITECTURE.md; backend/server.py"),
    ("technology.integrations", "technology", "fact", "verified", "Integrations in production: Twilio (voice, SMS, A2P compliance), OpenAI (text, Whisper, TTS, GPT-Live voice), Stripe (proposals and invoices), Resend (email), Expo push, Emergent object storage. No CRM two-way sync is live.", "platform", "docs/INTEGRATIONS.md; backend/services"),
    ("technology.deploy", "technology", "fact", "verified", "Releases: backend goes live through the Emergent Deploy action; the mobile app updates over the air with an EAS update; native changes need an App Store build. Preview and production databases are separate.", "platform", "memory/PRD.md Environments; docs/DEPLOYMENT.md"),
    ("technology.limitations", "technology", "fact", "verified", "Known limitations: no central LLM wrapper (36+ call sites), no durable background-job runner, Twilio webhook signature validation in log-only mode, native live voice only in EAS builds, no vector search.", "platform", "memory/ARCH_PLAN.md; memory/PRD.md"),
    ("technology.ai_costs", "technology", "fact", "verified", "Unit prices on record: GPT-Live voice $0.05 per session minute; gpt-5.2 text $1.75 per 1M input tokens and $14 per 1M output tokens (approximate list prices).", "platform", "backend/services/live_voice.py:28; backend/services/command_center_ai.py:29"),
    ("products.release_status", "products", "fact", "verified", "Deployed in production: Relationship OS core (contacts, inbox, AI replies, campaigns, voice memos), Mystery Shops (shop clients, challenge library incl. an equipment/Kubota pack, phone/text/email shops, GPT-Live shopper, lead shops, journeys, scorecards, proposals with Stripe e-sign, public report pages, nl and en-GB locales), Trade Appraisal engine, Founder Command Center 1A. Built in preview only, not deployed: Founder Advisor (Phase 2) and the Leadership Team.", "platform", "memory/PRD.md; memory/CHANGELOG.md"),
    ("products.mystery_shops.architecture", "products", "fact", "verified", "Mystery Shops shares authentication, Twilio numbers, LLM access, object storage and Stripe with the rest of the platform; its public pages (report, proposal, kickoff) are token-based and can be skinned per client; the admin side is inside the main app.", "platform", "backend/routers/mystery_shops.py; backend/routers/public_*.py"),
    ("commercial.pricing", "commercial", "assumption", "proposed", "No paying Mystery Shops customer has validated a price. The only quote on record is a UK demo client at 450 GBP per month and a Dutch demo client; both are demo data.", "platform", "memory/test_credentials.md (demo clients)"),
    ("customers.target", "customers", "fact", "verified", "Primary go-to-market target per the Command Center: equipment dealerships, reached through a partner-led sales model. Automotive dealerships are the existing user base.", "command_center", "cc_blueprint objective; FOUNDER_COMMAND_CENTER_PLAN.md"),
    ("customers.partners", "customers", "assumption", "proposed", "TracTru is a prospective partner at stage 'exploring'; no terms, no signed agreement and no confirmed interest are on record.", "document", "memory/FOUNDER_COMMAND_CENTER_PLAN.md; memory/DNI_MARKETING_ATTRIBUTION_PLAN.md"),
    ("customers.pipeline", "customers", "fact", "verified", "No paying Mystery Shops customers and no sales pipeline are recorded in the system; shop clients in preview are demo data.", "platform", "shop_clients collection (preview demo seeds)"),
    ("financials.revenue", "financials", "fact", "verified", "No financial actuals (revenue, costs, cash) are recorded in the system. Stripe runs in test mode in preview; production billing results are not connected.", "platform", "backend/.env (Stripe test); no finance connector"),
    ("financials.assumptions", "financials", "assumption", "proposed", "Cost-to-serve assumption for a phone mystery shop: about 6 minutes of GPT-Live ($0.30) plus Twilio voice and one or two grading calls, roughly $0.50 per shop; text and email shops $0.10 to $0.20. Unvalidated.", "agent_proposal", "derived from technology.ai_costs"),
    ("operations.onboarding", "operations", "fact", "verified", "Rep onboarding runs through Jessi Onboarding (SMS-led interview, activation link, first-win nudges). No customer-level (dealership) onboarding procedure for Mystery Shops is documented beyond the proposal and kickoff pages.", "platform", "backend/services/jessi_onboarding.py; routers/public_trade.py"),
    ("operations.support", "operations", "fact", "verified", "No support procedure, SLA or escalation path is documented in the system. In-app bug reports exist (report-bug screen, weekly bug digest).", "platform", "memory/PRD.md"),
    ("operations.implementation", "operations", "fact", "verified", "Mystery Shops client setup today: create the shop client, add people with phone numbers, pick challenges and quotas, choose the shop number, optionally arm journey campaigns. Done by the owner in the admin app; no customer self-serve.", "platform", "backend/routers/mystery_shops.py"),
    ("compliance.texting", "compliance", "fact", "verified", "Texting Compliance (A2P 10DLC brand and campaign registration) is modelled per store with a dry-run mode; recorded shop calls and shopper identities have no written consent policy yet.", "platform", "backend/services/twilio_compliance.py; routers/compliance.py"),
    ("departments.owners", "departments", "fact", "verified", "The founder owns every department personally; there are no employees seated in the leadership structure yet.", "human", "founder (Oct 2026)"),
]


def _pub(f: dict) -> dict:
    out = {k: (cc._iso(v) if isinstance(v, datetime) else v) for k, v in f.items() if k not in ("_id", "company_id")}
    out["id"] = str(f["_id"])
    sa = f.get("stale_after")
    out["stale"] = bool(sa and _aware(sa) < _now())
    return out


async def seed(db, company_id: str):
    if company_id != "imos":
        return
    now = _now()
    for key, domain, kind, status, statement, src_kind, ref in IMOS_SEED:
        await db[FACTS].update_one({"company_id": company_id, "key": key}, {"$setOnInsert": {
            "company_id": company_id, "key": key, "domain": domain, "kind": kind, "status": status, "statement": statement, "source": {"kind": src_kind, "ref": ref, "excerpt": ""},
            "visibility": "exec", "as_of": now, "stale_after": now + timedelta(days=FRESH_DAYS[domain]), "verified_by": {"id": "system", "name": "repository audit"} if status == "verified" else None,
            "verified_at": now if status == "verified" else None, "supersedes": None, "superseded_by": None, "seed_key": "imos_phase1", "created_by": {"id": "system", "name": "seed"}, "created_at": now, "updated_at": now}}, upsert=True)


async def list_facts(db, company_id: str, domain: str | None = None, visibility_max: str = "founder") -> list:
    allowed = VISIBILITY[VISIBILITY.index(visibility_max):]
    q = {"company_id": company_id, "visibility": {"$in": list(allowed)}}
    if domain in DOMAINS:
        q["domain"] = domain
    return [_pub(f) async for f in db[FACTS].find(q).sort([("domain", 1), ("key", 1)])]


def _clean_fact(body: dict, create: bool) -> dict:
    out = {}
    if "statement" in body or create:
        s = ai.clean(body.get("statement"), 1200)
        if not s:
            raise ValueError("A statement is required")
        out["statement"] = s
    if "key" in body or create:
        k = re.sub(r"[^a-z0-9_.]", "", str(body.get("key") or "").lower().replace(" ", "_"))[:80]
        if not k or "." not in k:
            raise ValueError("Give the fact a dotted key such as commercial.pricing.floor")
        out["key"] = k
    for f, allowed in (("domain", DOMAINS), ("kind", KINDS), ("visibility", VISIBILITY)):
        if f in body or create:
            v = body.get(f) or ("exec" if f == "visibility" else None)
            if v not in allowed:
                raise ValueError(f"Unknown {f}")
            out[f] = v
    if "source" in body or create:
        src = body.get("source") if isinstance(body.get("source"), dict) else {}
        out["source"] = {"kind": src.get("kind") if src.get("kind") in SOURCE_KINDS else "human", "ref": ai.clean(src.get("ref"), 300), "excerpt": ai.clean(src.get("excerpt"), 600)}
    if "as_of" in body and body.get("as_of"):
        try:
            out["as_of"] = datetime.fromisoformat(str(body["as_of"])[:10]).replace(tzinfo=timezone.utc)
        except ValueError:
            raise ValueError("as_of must be YYYY-MM-DD")
    return out


async def create_fact(db, company_id: str, body: dict, me: dict) -> dict:
    f = _clean_fact(body, True)
    now = _now()
    status = body.get("status") if body.get("status") in ("proposed", "verified") else "proposed"
    as_of = f.get("as_of") or now
    doc = {**f, "company_id": company_id, "status": status, "as_of": as_of, "stale_after": as_of + timedelta(days=FRESH_DAYS[f["domain"]]), "verified_by": cc._who(me) if status == "verified" else None,
           "verified_at": now if status == "verified" else None, "supersedes": None, "superseded_by": None, "created_by": cc._who(me), "created_at": now, "updated_at": now}
    prior = await db[FACTS].find_one({"company_id": company_id, "key": f["key"], "status": {"$ne": "retired"}})
    if prior:
        # Same key again: the new statement supersedes the old one; both verified with different text would be a conflict, so the old one is retired explicitly.
        doc["supersedes"] = str(prior["_id"])
        await db[FACTS].update_one({"_id": prior["_id"]}, {"$set": {"status": "retired", "updated_at": now}})
    r = await db[FACTS].insert_one(doc)
    if prior:
        await db[FACTS].update_one({"_id": prior["_id"]}, {"$set": {"superseded_by": str(r.inserted_id)}})
    doc["_id"] = r.inserted_id
    return _pub(doc)


async def set_status(db, company_id: str, fid: str, status: str, me: dict, note: str = "") -> dict | None:
    oid = cc._oid(fid)
    if not oid or status not in STATUSES:
        return None
    now = _now()
    upd = {"status": status, "updated_at": now}
    if status == "verified":
        upd.update({"verified_by": cc._who(me), "verified_at": now, "as_of": now})
        f = await db[FACTS].find_one({"_id": oid, "company_id": company_id}, {"domain": 1})
        if f:
            upd["stale_after"] = now + timedelta(days=FRESH_DAYS.get(f["domain"], 90))
    if note:
        upd["note"] = ai.clean(note, 400)
    await db[FACTS].update_one({"_id": oid, "company_id": company_id}, {"$set": upd})
    f = await db[FACTS].find_one({"_id": oid, "company_id": company_id})
    return _pub(f) if f else None


async def block(db, company_id: str, domains: list, visibility_max: str = "exec") -> tuple:
    """Knowledge for one executive's prompt: verified first, then proposed/disputed with their labels; stale facts say so. Returns (text, index) where index maps F<n> to fact ids."""
    allowed = VISIBILITY[VISIBILITY.index(visibility_max):]
    rows = await db[FACTS].find({"company_id": company_id, "domain": {"$in": domains}, "visibility": {"$in": list(allowed)}, "status": {"$ne": "retired"}}).sort([("status", -1), ("domain", 1), ("key", 1)]).to_list(80)
    lines, index = [], {}
    for i, f in enumerate(rows, 1):
        stale = f.get("stale_after") and _aware(f["stale_after"]) < _now()
        tag = f["status"].upper() + ("" if f["kind"] == "fact" else f" · {f['kind'].upper()}") + (" · MAY BE OUTDATED" if stale else "")
        lines.append(f"F{i} [{tag}] {f['domain']}.{f['key'].split('.', 1)[-1]} (as of {cc._iso(f.get('as_of'))[:10]}; source {f.get('source', {}).get('kind')}): {ai.clean(f['statement'], 600)}")
        index[f"F{i}"] = str(f["_id"])
    guide = "Only VERIFIED facts may be cited as FACT. PROPOSED, DISPUTED, ASSUMPTION and PROJECTION entries may only be used as assumptions and must be labelled so."
    return ai._block("company_knowledge", [guide] + lines), index


# ───────────────────────── readiness: rule-based, documented ─────────────────────────
READINESS_RULE = ("Score = sum over the executive's required knowledge items of: 1.0 for a VERIFIED fact that is fresh, 0.5 for a VERIFIED fact past its freshness date, 0.25 for a PROPOSED or DISPUTED fact, 0 when missing; "
                  "divided by the number of required items, times 100. Command Center items (cc.*) count 1.0 when the item exists (objective set, at least one priority, roadmap items, products described) and 0 otherwise; cc.positioning needs the approved statement. No model is involved.")


async def readiness(db, company_id: str, agent: dict, cc_state: dict | None = None) -> dict:
    cc_state = cc_state or await cc_snapshot(db)
    facts = {f["key"]: f async for f in db[FACTS].find({"company_id": company_id, "status": {"$ne": "retired"}})}
    items, total = [], 0.0
    for req in agent.get("required_keys") or []:
        key = req["key"]
        if key.startswith("cc."):
            ok = bool(cc_state.get(key))
            score, status, detail = (1.0 if ok else 0.0), ("verified" if ok else "missing"), ("present in the Command Center" if ok else "not set in the Command Center yet")
        else:
            f = next((v for k, v in facts.items() if k == key or k.startswith(key + ".")), None)
            if not f:
                score, status, detail = 0.0, "missing", "no fact recorded"
            elif f["status"] == "verified":
                stale = f.get("stale_after") and _aware(f["stale_after"]) < _now()
                score, status, detail = (0.5 if stale else 1.0), ("stale" if stale else "verified"), ("verified but past its freshness date" if stale else f"verified {cc._iso(f.get('verified_at') or f.get('as_of'))[:10]}")
            else:
                score, status, detail = 0.25, f["status"], f"{f['status']} ({f['kind']}), not yet verified"
        total += score
        items.append({"key": key, "label": req["label"], "status": status, "score": score, "detail": detail})
    n = len(items) or 1
    pct = round(100 * total / n)
    missing = [i for i in items if i["status"] in ("missing", "proposed", "disputed", "stale")]
    level = "ready" if pct >= 75 else "partial" if pct >= 40 else "low"
    return {"score": pct, "level": level, "items": items, "missing": [{"key": i["key"], "label": i["label"], "next_step": ("Set it in the Command Center" if i["key"].startswith("cc.") else "Verify the proposed fact" if i["status"] in ("proposed", "disputed") else "Re-confirm the fact" if i["status"] == "stale" else "Add a verified fact")} for i in missing],
            "rule": READINESS_RULE}


async def cc_snapshot(db) -> dict:
    bp = await cc.blueprint(db)
    pri = await db[cc.PRIORITIES].count_documents({"status": {"$in": ["proposed", "active", "paused"]}})
    rm = await db[cc.ROADMAP].count_documents({})
    ob = (bp.get("objective") or {}).get("data") or {}
    pos = (bp.get("statements") or {}).get("positioning") or {}
    return {"cc.objective": bool(ob.get("title")), "cc.priorities": pri > 0, "cc.roadmap": rm > 0, "cc.products": len(bp.get("products") or []) >= 3, "cc.positioning": pos.get("status") == "approved"}


# ───────────────────────── Company Docs passages (keyword match, read-only) ─────────────────────────
_STOP = set("the a an and or of to in for on with is are be we our this that it as by at from what how should would could does do my me i".split())


def _terms(q: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]{3,}", (q or "").lower()) if w not in _STOP}


async def doc_passages(db, question: str, k: int = 4, cap: int = 600) -> tuple:
    """Top paragraphs from the synced Company Docs by keyword overlap. Deliberately simple: the corpus is a dozen documents; a chunk index comes when it is measured to be needed."""
    terms = _terms(question)
    if not terms:
        return "", {}
    scored = []
    # super-admin-only documents (engineering/operations) never enter an AI prompt
    async for d in db.company_docs.find({"is_published": {"$ne": False}, "required_role": {"$ne": "super_admin"}, "category": {"$nin": list(RESTRICTED_CATEGORIES)}}, {"title": 1, "slug": 1, "content": 1}):
        for para in re.split(r"\n\s*\n", d.get("content") or ""):
            p = para.strip()
            if len(p) < 80:
                continue
            words = _terms(p)
            hit = len(terms & words)
            if hit >= 2:
                scored.append((hit / (1 + len(words) / 400), d.get("title") or d.get("slug"), p))
    scored.sort(key=lambda x: -x[0])
    lines, index = [], {}
    for i, (_, title, p) in enumerate(scored[:k], 1):
        lines.append(f"D{i} ({ai.clean(title, 80)}): {ai.clean(p, cap)}")
        index[f"D{i}"] = title
    return (ai._block("company_documents", lines) if lines else ""), index
