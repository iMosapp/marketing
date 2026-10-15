"""SIMULATED name-use evaluation for Jessi on Realtime mini. NOT a real OpenAI audio test: a small text model stands in for the realtime-mini
model (same model for both variants, so only the PROMPT differs). It plays Jessi with the exact mini instruction strings the backend sends,
before and after the name-policy change, with the production Voice Lab sliders and greeting. Scripted rep turns and backend results.
Counts, per reply after the greeting: the rep's first name used to address them (quoted draft texts excluded), replies starting with it,
stock acknowledgment openers, and whether customer names from backend results are kept.
    python tests/voice_name_use_eval.py [stand_in_model] [runs]      (writes /app/memory/VOICE_MINI_NAME_EVAL.json)"""
import asyncio
import json
import os
import re
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
from emergentintegrations.llm.chat import LlmChat, UserMessage  # noqa: E402

from services import live_voice as lv  # noqa: E402

STAND_IN = ("openai", sys.argv[1] if len(sys.argv) > 1 else "gpt-4.1-mini")
RUNS = int(sys.argv[2]) if len(sys.argv) > 2 else 2
USER = {"name": "Forest Ward", "role": "super_admin", "organization_name": "I'm On Social"}
NAME = "Forest"
# production Voice Lab (read-only, Oct 15): energy 4, pacing 5, playful 4, brevity 5, custom greeting
CFG = lv.clean_config({"energy": 4, "pacing": 5, "playful": 4, "brevity": 5, "greeting": "Hey {first}, Who are we talking about today?"})
CONTEXT = "Right now it is Thursday October 15, 2026, 9:05 AM for the rep. Their app is open on the Home screen."
OUT = "/app/memory/VOICE_MINI_NAME_EVAL.json"
GREET_MINI = 'Greet the rep now, before they speak. Say exactly this and nothing more: "{g}" Then stop and listen.'
WRAP_OLD = "SAY THIS TO THE REP in your own voice, keep every name and number, add nothing: "
WRAP_NEW = "SAY THIS TO THE REP in your own voice, keep every customer name and number, don't add the rep's name, add nothing: "

# (rep says, backend result or None, customer name that must survive)
CONVERSATIONS = [
    [("What do I know about Sarah Mitchell?", "Sarah Mitchell: bought a 2024 Tahoe in March, two kids, daughter starts college in the fall, open task: send her the referral card.", "Sarah"),
     ("When did I last talk to her?", "Last text with Sarah Mitchell was September 30, about a service appointment.", "Sarah"),
     ("Okay, remind me to call her Friday afternoon.", "Reminder set: call Sarah Mitchell Friday 2 PM.", "Sarah"),
     ("Thanks.", None, None),
     ("Who else should I reach out to today?", "Today's three: Bud Carter (overdue follow-up), Mike Tran (birthday), Tanya Reed (new web lead).", "Bud"),
     ("Tell me about Bud.", "Bud Carter: looking at the Silverado High Country, trading a 2019 F-150, wife Deb, bonus after the 15th.", "Bud"),
     ("What should I open with when I call him?", None, None),
     ("Good idea. Draft him a text.", "Draft for Bud Carter: 'Hey Bud, it's Forest. Got a minute this week to look at the High Country numbers?' Send it?", "Bud"),
     ("Yes, send it.", "Sent to Bud Carter.", "Bud")],
    [("Pull up Tod Berry.", "Which one: Tod Berry with the Tahoe, or Todd Berry with the Silverado?", "Tod"),
     ("The Tahoe one.", "Tod Berry is up on your screen: 2022 Tahoe, last text October 2.", "Tod"),
     ("Any open tasks for him?", "One open task for Tod Berry: send the trade-in appraisal.", "Tod"),
     ("I'm swamped today, honestly.", None, None),
     ("What's my numbers this month?", "This month: 11 sold, 4 reviews, 62 texts sent, 3 hot leads waiting.", None),
     ("Is that good?", None, None),
     ("Who mentioned a Tesla last month?", "Earl Jones mentioned a Tesla on September 18: 'thinking about a Model Y for my wife'.", "Earl"),
     ("Tag him as EV interested.", "Tagged Earl Jones: EV interested.", "Earl"),
     ("Perfect, that's it for now.", None, None)],
    [("Let's brainstorm. How do I get more referrals this quarter?", None, None),
     ("Go deeper on the first idea.", None, None),
     ("How would I say that in a text?", None, None),
     ("Who are my last five sold customers?", "Last five sold: Sarah Mitchell (Tahoe), Dan Mitchell (Colorado), Amy Jones (Equinox), Bud Carter (Silverado), Kim Park (Traverse).", "Kim"),
     ("Send the referral card to Kim.", "Draft for Kim Park: 'Hi Kim, it's Forest. Thanks again for choosing us, here's my card if anyone you know is shopping.' Send it?", "Kim"),
     ("Yes.", "Sent to Kim Park.", "Kim"),
     ("What time is it?", None, None),
     ("Remind me tomorrow at 9 to check on Amy.", "Reminder set: check on Amy Jones tomorrow 9 AM.", "Amy"),
     ("Great, thanks Jessi.", None, None)],
]
OPENER = re.compile(r"^\W*(absolutely|great question|you got it|perfect|got it|sure thing|of course|okay so|alright|sounds good)\b", re.I)
QUOTED = re.compile(r"'[^']{12,}'|\"[^\"]{12,}\"|“[^”]{12,}”|‘[^’]{12,}’")


def name_uses(text: str) -> int:
    return len(re.findall(rf"\b{NAME}\b", QUOTED.sub(" ", text)))


def variants() -> dict:
    ins = lv.assistant_instructions(CFG, USER)
    old = ins + lv.REALTIME_RULES.replace("keep every customer name and number", "keep every name and number") + lv.MINI_RULES + "\n\n" + CONTEXT
    return {"mini_before": {"system": old, "wrap": WRAP_OLD}, "mini_after": {"system": lv.mini_instructions(ins, CONTEXT), "wrap": WRAP_NEW}}


async def run_conversation(v: dict, convo: list) -> list:
    chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"name-{uuid.uuid4().hex[:8]}", system_message=v["system"]).with_model(*STAND_IN)
    greet = await chat.send_message(UserMessage(text=f"[instruction for your first words, not spoken by the rep] {GREET_MINI.format(g=lv.greeting_text(CFG, USER))}"))
    turns = [{"rep": "(session start)", "jessi": greet.strip(), "greeting": True}]
    for rep, backend, customer in convo:
        msg = f"[rep says] {rep}" + (f"\n[function result] {v['wrap']}{backend}" if backend else "")
        reply = (await chat.send_message(UserMessage(text=msg))).strip()
        turns.append({"rep": rep, "backend": backend, "jessi": reply, "name_uses": name_uses(reply), "starts_with_name": bool(re.match(rf"^\W*{NAME}\b", reply)),
                      "stock_opener": bool(OPENER.match(reply)), "customer_kept": (customer in reply) if customer else None})
    return turns


def summary(turns: list) -> dict:
    later = [t for t in turns if not t.get("greeting")]
    kept = [t["customer_kept"] for t in later if t["customer_kept"] is not None]
    greet_named = sum(bool(re.search(rf"\b{NAME}\b", t["jessi"])) for t in turns if t.get("greeting"))
    return {"post_greeting_replies": len(later), "replies_with_name": sum(t["name_uses"] > 0 for t in later),
            "replies_with_name_pct": round(100 * sum(t["name_uses"] > 0 for t in later) / max(1, len(later)), 1),
            "replies_starting_with_name": sum(t["starts_with_name"] for t in later), "stock_openers": sum(t["stock_opener"] for t in later),
            "customer_names_kept_pct": round(100 * sum(kept) / max(1, len(kept)), 1), "greetings_with_name": f"{greet_named}/{sum(1 for t in turns if t.get('greeting'))}",
            "avg_words": round(sum(len(t["jessi"].split()) for t in later) / max(1, len(later)), 1)}


async def main():
    out = {"meta": {"kind": "SIMULATED (text model stand-in), not a real OpenAI audio test", "stand_in_model": STAND_IN[1], "runs": RUNS, "sliders": {k: CFG[k] for k in ("energy", "pacing", "playful", "brevity")}}, "results": {}}
    for name, v in variants().items():
        turns = []
        for _ in range(RUNS):
            for convo in CONVERSATIONS:
                turns += await run_conversation(v, convo)
        out["results"][name] = {"summary": summary(turns), "turns": turns}
        print(name, json.dumps(out["results"][name]["summary"]))
    json.dump(out, open(OUT, "w"), indent=1)
    print("wrote", OUT)


if __name__ == "__main__":
    asyncio.run(main())
