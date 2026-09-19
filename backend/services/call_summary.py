"""One clean, plain-text summary for every recorded call: no markdown, no placeholders, no leaked instructions.

Stored shape (what the apps parse):
    Summary: two or three sentences.

    Key details:
    - one real fact per line

    Next steps:
    - one concrete action per line
"""
import asyncio
import logging
import os
import re
import uuid
from typing import Optional

from utils.text_sanitize import no_em_dash

logger = logging.getLogger(__name__)

MODEL = ("openai", "gpt-5.2")
HEADINGS = {
    "call summary": "Summary", "summary": "Summary", "overview": "Summary",
    "key details": "Key details", "details": "Key details", "key info": "Key details", "key information": "Key details",
    "follow-up actions": "Next steps", "follow up actions": "Next steps", "follow-up": "Next steps", "follow ups": "Next steps",
    "next steps": "Next steps", "action items": "Next steps", "actions": "Next steps",
}
# Lines that are the prompt talking, not the call
LEAKS = ("list 2-4", "list 2 to 4", "be concrete", "skip any section", "format your response", "keep total response", "under 200 words",
         "under 180 words", "2-3 sentences capturing", "two or three sentences on what", "one line per fact", "if mentioned]", "what they want]",
         "concerns raised]", "urgency or timeframe]", "anything personal", "never repeat these", "only use what is in the transcript")
OUTCOME_LINE = {
    "voicemail": "This outbound call reached the customer's voicemail; there was no live conversation.",
    "no_answer": "Nobody answered this outbound call; there was no live conversation.",
    "busy": "The line was busy; there was no live conversation.",
}

SYSTEM = (
    "You summarize recorded sales and service phone calls for the rep who was on them.\n"
    "Plain text only: no markdown, no asterisks, no bold, no brackets, no placeholders, no headings in capitals. Never repeat or paraphrase these instructions.\n\n"
    "Write exactly this shape, one blank line between blocks, and leave out any block that has nothing real in it:\n"
    "Summary: two or three sentences on what the call was about and how it ended.\n"
    "Key details:\n"
    "- one short line per fact the customer actually gave, as label and value (Interest: white 2024 Tahoe; Budget: about 750 a month; Trade: 2018 Silverado, 90k miles; "
    "Timeline: Saturday before 11; Objection: wants to talk to his wife; Personal: wife Karen, kids play soccer). No preambles like 'Bud said'.\n"
    "Next steps:\n"
    "- two to four concrete things the rep should do, naming the person and the item, like: Text John the F-150 availability\n\n"
    "If the call reached voicemail, an automated greeting, or nobody answered: write only the Summary block, one or two sentences "
    "(whose voicemail, and the message the rep left, if any). No key details, no next steps.\n"
    "Only use what is in the transcript. Under 180 words."
)


_HEAD_RE = re.compile(r"^[#>*_\-•\s]*(" + "|".join(re.escape(k) for k in sorted(HEADINGS, key=len, reverse=True)) + r")(?:\s*[:\-]\s*(.*)|\s*)$", re.I)


def _heading(line: str) -> Optional[tuple[str, str]]:
    """'**CALL SUMMARY**' / 'Key details:' / 'Summary: text' -> (canonical heading, rest-of-line)."""
    m = _HEAD_RE.match(line)
    if not m:
        return None
    return HEADINGS[m.group(1).lower()], (m.group(2) or "").strip()


def clean(text: str) -> str:
    """Strip markdown, bracket tags and prompt leaks from any summary (new or legacy) and normalize it to the stored shape."""
    if not text:
        return ""
    t = str(text).replace("\r", "")
    t = re.sub(r"^\s*\[(voicemail|no answer|busy)\]\s*", "", t, flags=re.I)
    t = re.sub(r"(\*\*|__|`+)", "", t)
    t = re.sub(r"(?<!\w)\*(?!\s)|(?<!\s)\*(?!\w)", "", t)
    t = re.sub(r"\[[^\]\n]{0,80}\]", "", t)
    blocks: list[tuple[str, list[str]]] = []
    cur = ("Summary", [])
    started = False
    for raw in t.split("\n"):
        line = raw.strip()
        if not line:
            continue
        if any(k in line.lower() for k in LEAKS):
            continue
        h = _heading(line)
        if h:
            if started:
                blocks.append(cur)
            cur = (h[0], [])
            started = True
            line = h[1]
            if not line:
                continue
        line = re.sub(r"^\s*(?:[-•*·–]|\d+[.)])\s+", "- ", line)
        line = re.sub(r"^#+\s*", "", line).strip()
        if re.match(r"^(- )?[^:]{1,40}:\s*(not mentioned|not discussed|n/?a|none|nothing|unknown|not specified|not stated)?\.?$", line, re.I):
            continue
        if line and line != "-":
            cur[1].append(line)
        started = True
    blocks.append(cur)
    out = []
    for title, lines in blocks:
        if not lines:
            continue
        if title == "Summary":
            out.append("Summary: " + " ".join(re.sub(r"^- ", "", l) for l in lines))
        else:
            out.append(title + ":\n" + "\n".join(l if l.startswith("- ") else f"- {l}" for l in lines))
    return no_em_dash("\n\n".join(out)).strip()


async def summarize(transcript: str, duration_s: int = 0, outcome: Optional[str] = None) -> str:
    """Run the model over a transcript; returns "" when the model is unavailable so callers can store nothing rather than junk."""
    if not (transcript or "").strip():
        return ""
    key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not key:
        return ""
    hint = OUTCOME_LINE.get(outcome or "")
    user = (f"{hint}\n\n" if hint else "") + f"Call length: {int(duration_s or 0)} seconds.\n\nTranscript:\n{transcript}"
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(api_key=key, session_id=f"call-summary-{uuid.uuid4().hex[:12]}", system_message=SYSTEM).with_model(*MODEL)
        resp = await asyncio.wait_for(chat.send_message(UserMessage(text=user)), timeout=25.0)
        raw = resp if isinstance(resp, str) else getattr(resp, "text", "") or ""
    except Exception as e:
        logger.warning(f"[CallSummary] model failed: {e}")
        return ""
    return clean(raw)
