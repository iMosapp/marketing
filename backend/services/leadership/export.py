"""Roundtable export: the decision record as Markdown or PDF, rendered from the stored document exactly as it stands. Nothing is generated here."""
import re
from datetime import datetime, timezone

STATUS = {"selected": "Not started", "running": "In session", "awaiting_decision": "Awaiting the founder's decision", "decided": "Decided", "cancelled": "Cancelled", "failed": "Failed", "paused": "Paused", "interrupted": "Interrupted"}
DECISION = {"approved": "Approved", "rejected": "Rejected", "deferred": "Deferred", "pending": "Pending", "modify_requested": "Changes requested"}
FIXED = {"chief_of_staff": "Chief of Staff", "strategic_advisor": "Strategic Advisor", "founder": "Founder"}


def _when(v) -> str:
    return v.strftime("%b %d, %Y, %H:%M UTC") if isinstance(v, datetime) else (str(v)[:16] if v else "")


def filename(rtd: dict, ext: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (rtd.get("title") or "roundtable").lower()).strip("-")[:48] or "roundtable"
    return f"roundtable-{slug}-{str(rtd['_id'])[-6:]}.{ext}"


def _bul(L: list, items, fmt=lambda x: x):
    L += [f"- {fmt(x)}" for x in items or [] if fmt(x)]


def _para(L: list, head: str, text: str):
    if text:
        L += [f"### {head}", text, ""]


def markdown(rtd: dict, decision: dict | None, company: str = "I'm On Social") -> str:
    parts = rtd.get("participants") or []
    names = {**FIXED, **{p["key"]: p["title"] for p in parts}}
    def nm(k):
        return names.get(k, k)
    b = rtd.get("brief") or {}
    L = [f"# {rtd.get('title') or 'Leadership Roundtable'}", "", f"Leadership Roundtable · {company} · convened {_when(rtd.get('created_at'))} · {STATUS.get(rtd['status'], rtd['status'])}", "",
         "## The question", rtd.get("restated") or rtd.get("question") or "", "", f"Founder's words: {rtd.get('question')}", ""]
    if decision:
        f = decision.get("founder") or {}
        line = f"**{DECISION.get(decision['status'], decision['status'])}**"
        if f:
            line += f" by {(f.get('by') or {}).get('name') or 'the founder'} on {_when(f.get('at'))}"
        L += ["## Decision", line]
        if f.get("reason"):
            L.append(f"Founder's note: {f['reason']}")
        L += [f"The team recommended: {decision.get('recommendation') or b.get('recommended_decision') or ''}", ""]
    L.append("## The room")
    for p in parts:
        L.append(f"- {p['title']} ({p['short']})" + (" · devil's advocate" if p.get("devil_advocate") else "") + (f" · {p['why']}" if p.get("why") else ""))
    L.append("")
    if b:
        L += ["## Executive brief", ""]
        _para(L, "Opportunity", b.get("opportunity"))
        _para(L, "Strategic alignment", b.get("alignment"))
        if b.get("department_recommendations"):
            L.append("### Department recommendations")
            _bul(L, b["department_recommendations"], lambda x: f"**{nm(x['key'])}:** {x['summary']}")
            L.append("")
        if b.get("agreements"):
            L.append("### Where they agree")
            _bul(L, b["agreements"])
            L.append("")
        _para(L, "Where they disagree", b.get("disagreements"))
        _para(L, "Technical", b.get("technical"))
        _para(L, "Financial", b.get("financial"))
        _para(L, "Operational", b.get("operational"))
        _para(L, "Commercial", b.get("commercial"))
        for head, k in (("Dependencies", "dependencies"), ("Risks", "risks"), ("What the company still lacks", "missing")):
            if b.get(k):
                L.append(f"### {head}")
                _bul(L, b[k])
                L.append("")
        _para(L, "Recommended decision", b.get("recommended_decision"))
        if b.get("decisions_required"):
            L.append("### Decisions required from the founder")
            _bul(L, b["decisions_required"], lambda x: f"**{x['title']}**" + (f": {x['detail']}" if x.get("detail") else ""))
            L.append("")
        if b.get("next_actions"):
            L.append("### Next actions")
            _bul(L, b["next_actions"], lambda x: f"{x['action']} · owner: {nm(x.get('owner_key'))}" + (f" · {x['why']}" if x.get("why") else ""))
            L.append("")
        if b.get("unassessed"):
            L.append("### Unassessed")
            _bul(L, b["unassessed"])
            L.append("")
    L.append("## Dissent register")
    dis = rtd.get("dissent") or []
    if not dis:
        L += ["No material disagreement was recorded.", ""]
    for d in dis:
        L.append(f"### {d['id'].upper()}: {d['issue']}")
        _bul(L, d.get("positions") or [], lambda x: f"**{nm(x['key'])}:** {x['position']}")
        if d.get("evidence"):
            L.append(f"Evidence: {d['evidence']}")
        if d.get("consequences"):
            L.append(f"Consequence if wrong: {d['consequences']}")
        L.append(("Resolved" + (f": {d['how']}" if d.get("how") else "")) if d.get("resolved") else ("Unresolved, needs the founder" + (f": {d['how']}" if d.get("how") else "")))
        if d.get("raised_by_devil_advocate"):
            L.append("Raised by the devil's advocate.")
        L.append("")
    L.append("## Independent assessments")
    for p in parts:
        a = (rtd.get("assessments") or {}).get(p["key"]) or {}
        L.append(f"### {p['title']}")
        if a.get("status") != "ok":
            L += [f"Did not answer: {a.get('error') or 'no response'}", ""]
            continue
        d = a["data"]
        L += [f"**Recommendation:** {d.get('recommendation')} (confidence {d.get('confidence')})", "", d.get("perspective") or ""]
        for head, k in (("Evidence", "evidence"), ("Assumptions", "assumptions"), ("Risks", "risks"), ("Dependencies", "dependencies"), ("Limitations", "limitations")):
            if d.get(k):
                L.append(f"{head}:")
                _bul(L, d[k])
        L.append("")
    chal = {k: v for k, v in (rtd.get("challenges") or {}).items() if v.get("status") == "ok"}
    if chal:
        L.append("## Challenge round")
        for p in parts:
            c = (chal.get(p["key"]) or {}).get("data")
            if not c:
                continue
            L.append(f"### {p['title']}" + (" (devil's advocate)" if p.get("devil_advocate") else ""))
            if c.get("position_change"):
                L.append(f"Position change: {c['position_change']}")
            _bul(L, c.get("challenges") or [], lambda x: f"To {nm(x['to'])}: \"{x['claim']}\" -> {x['objection']} ({x['severity']}" + (f"; {x['consequence']}" if x.get("consequence") else "") + ")")
            _bul(L, c.get("agreements") or [], lambda x: f"Agrees with {nm(x['with'])} on {x['on']}")
            L.append("")
    if rtd.get("unsupported"):
        L.append("## Claims labelled FACT without a citation")
        _bul(L, rtd["unsupported"], lambda x: f"{nm(x['agent_key'])}: {x['claim']}")
        L.append("")
    L += ["## Record", f"- Measured model cost: ${float(rtd.get('cost_usd') or 0):.3f} (from provider token counts)", f"- Brief generated: {_when(b.get('generated_at')) or 'not yet'}", f"- Exported: {_when(datetime.now(timezone.utc))}",
          "- Advisory only: nothing in the Command Center changed because of this roundtable.", ""]
    return "\n".join(L)


def _safe(s: str) -> str:
    return (s or "").replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"').replace("\u2026", "...").replace("\u00b7", "-").replace("\u2192", "->").encode("latin-1", "replace").decode("latin-1")


def _plain(s: str) -> str:
    return s.replace("**", "")


def pdf(md: str) -> bytes:
    from fpdf import FPDF
    p = FPDF()
    p.set_auto_page_break(auto=True, margin=16)
    p.add_page()

    def w(h, text, style="", size=10.5, color=(20, 20, 20), indent=0):
        p.set_font("Helvetica", style, size)
        p.set_text_color(*color)
        if indent:
            p.set_x(p.l_margin + indent)
        p.multi_cell(0, h, _safe(text), new_x="LMARGIN", new_y="NEXT")

    for line in md.split("\n"):
        if line.startswith("# "):
            w(9, line[2:], "B", 18)
        elif line.startswith("Leadership Roundtable · "):
            w(5.5, line, "I", 9.5, (110, 110, 110))
        elif line.startswith("## "):
            p.ln(3)
            w(7.5, line[3:], "B", 14, (120, 92, 30))
        elif line.startswith("### "):
            p.ln(1)
            w(6.5, line[4:], "B", 11.5)
        elif line.startswith("- "):
            w(5.6, "- " + _plain(line[2:]), "", 10.5, indent=4)
        elif not line.strip():
            p.ln(2)
        else:
            w(5.6, _plain(line))
    return bytes(p.output())
