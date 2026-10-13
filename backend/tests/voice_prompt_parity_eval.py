"""SIMULATED prompt-parity evaluation for Jessi's two voice engines. NOT a real OpenAI audio test.
A small text model (stand-in for the realtime-mini model; same model for every variant so only the PROMPT differs) plays Jessi with the
exact instruction strings the backend sends: GPT-Live packaging and Realtime-mini packaging, before (git HEAD) and after this change.
Ten salesperson scenarios, scripted rep turns, scripted backend results. Measures words / sentences / questions / re-greets / filler per
reply, a gpt-5.2 judge scores each transcript, and the cost is ESTIMATED from the PRICING table (speech seconds -> tokens).
    python tests/voice_prompt_parity_eval.py [stand_in_model]      (writes /app/memory/VOICE_MINI_PARITY_EVAL.json + .md)"""
import asyncio
import importlib.util
import json
import os
import re
import statistics
import subprocess
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
from emergentintegrations.llm.chat import LlmChat, UserMessage  # noqa: E402

from services import live_voice as AFTER  # noqa: E402

STAND_IN = ("openai", sys.argv[1] if len(sys.argv) > 1 else "gpt-4.1-mini")
JUDGE = ("openai", "gpt-5.2")
USER = {"name": "Forest Ward", "role": "super_admin", "organization_name": "I'm On Social"}
CONTEXT = "Right now it is Monday October 13, 2026, 12:01 PM for the rep. Their app is open on the Home screen."
OUT_JSON, OUT_MD = "/app/memory/VOICE_MINI_PARITY_EVAL.json", "/app/memory/VOICE_MINI_PARITY_EVAL.md"
WORDS_PER_S, PAUSE_S, OUT_TOK_PER_S, IN_TOK_PER_S, PROMPT_TOKENS = 2.6, 1.5, 20, 10, 2600


def load_before():
    """The live_voice module as committed before this change (first commit without CORE_RULES)."""
    rev = "HEAD"
    src = subprocess.run(["git", "show", f"{rev}:backend/services/live_voice.py"], cwd="/app", capture_output=True, text=True).stdout
    if "CORE_RULES" in src:
        first = subprocess.run(["git", "log", "--format=%H", "-S", "CORE_RULES", "--", "backend/services/live_voice.py"], cwd="/app", capture_output=True, text=True).stdout.split()[-1]
        src = subprocess.run(["git", "show", f"{first}^:backend/services/live_voice.py"], cwd="/app", capture_output=True, text=True).stdout
    path = "/tmp/live_voice_before.py"
    open(path, "w").write(src)
    spec = importlib.util.spec_from_file_location("live_voice_before", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


BEFORE = load_before()
GREET_OLD = 'Greet the rep immediately in English without waiting for them to speak. Say, in your own words: "{g}". Then pause and listen.'
GREET_MINI = 'Greet the rep now, before they speak. Say exactly this and nothing more: "{g}" Then stop and listen.'

# rep turns; "backend" = what delegate() would return for that turn (scripted, identical for every variant)
SCENARIOS = [
    ("1 voice memo", [{"rep": "Save a note on Bud Carter: he's looking at the Silverado High Country, wants to trade his 2019 F-150, wife's name is Deb, and call him after the fifteenth when his bonus hits.",
                       "backend": "Saved on Bud Carter's record: Silverado High Country, trading a 2019 F-150, wife Deb, call after the 15th when his bonus hits."}]),
    ("2 remember details", [{"rep": "What do I know about Sarah Mitchell?",
                             "backend": "Sarah Mitchell: bought a 2024 Tahoe from you in March, two kids, daughter starts college in the fall, last talked September 30 about a service appointment, open task: send her the referral card."},
                            {"rep": "When did I last talk to her?"}]),
    ("3 find a contact", [{"rep": "Pull up Tod Berry.", "backend": "Which one: Tod Berry with the Tahoe, or Todd Berry with the Silverado?"},
                          {"rep": "The Tahoe one.", "backend": "Tod Berry is up on your screen: 2022 Tahoe, last text October 2."}]),
    ("4 follow-up task", [{"rep": "Remind me to call Sarah Friday afternoon about the referral card.", "backend": "Reminder set: call Sarah Mitchell Friday 2 PM about the referral card."}]),
    ("5 prepare for a call", [{"rep": "I'm about to call Bud, give me the quick rundown.",
                               "backend": "Bud Carter: looking at the Silverado High Country, trading a 2019 F-150, wife Deb, bonus lands after the 15th, last text October 9 asking about lease options."},
                              {"rep": "What should I open with?"}]),
    ("6 relationship history", [{"rep": "What's my history with the Mitchells?",
                                 "backend": "Sarah Mitchell: Tahoe in March 2024; her husband Dan came in on her referral and bought a Colorado in June; two service visits; you sent a birthday text in August; she asked about trading Dan's truck next year."}]),
    ("7 campaign idea", [{"rep": "Give me a quick idea for a text campaign to my Harley riders before Sturgis."}]),
    ("8 short factual", [{"rep": "What day is it today?"}, {"rep": "And what time?"}]),
    ("9 extended brainstorm", [{"rep": "Let's brainstorm. I want to double my referral rate this quarter. Walk me through some ideas."}, {"rep": "Go deeper on the second one."}]),
    ("10 continue after handoff", [{"rep": "So like I was saying, text her about the referral card.",
                                    "backend": "Read back: 'Hi Sarah, it's Forest. Wanted to get you that referral card I promised, is this still the best number?' Send it?"},
                                   {"rep": "Yes, send it.", "backend": "Sent to Sarah Mitchell."}]),
]
HANDOFF_PREV = {"transcript": [{"role": "assistant", "text": "Hey Forest, who are we talking about today?"}, {"role": "user", "text": "Sarah Mitchell."},
                               {"role": "assistant", "text": "Sarah bought a 2024 Tahoe in March, two kids, daughter starts college in the fall. You last talked September 30 about service, and the referral card is still open."},
                               {"role": "user", "text": "Right, I promised her that card."}], "pending": None}

FILLER = re.compile(r"\b(great question|absolutely|of course|happy to help|certainly|sure thing|no problem|i'?d be happy|let me know if)\b", re.I)
GREET = re.compile(r"\b(hey|hi|hello)\b[^.!?]{0,20}\bforest\b|\bit'?s jessi\b|\bi'?m jessi\b|\bthis is jessi\b", re.I)
ANYTHING_ELSE = re.compile(r"anything else|what else can i|is there anything", re.I)


def variants():
    cfg_a, cfg_b = AFTER.clean_config({}), BEFORE.clean_config({})
    greeting = AFTER.greeting_text(cfg_a, USER)
    ins_a, ins_b = AFTER.assistant_instructions(cfg_a, USER), BEFORE.assistant_instructions(cfg_b, USER)
    return {
        "live_before": {"system": ins_b + "\n\n" + CONTEXT, "greet": GREET_OLD.format(g=greeting), "handoff_ctx": BEFORE._handoff_context, "handoff_greet": BEFORE._handoff_greet},
        "live_after": {"system": ins_a + "\n\n" + CONTEXT, "greet": GREET_OLD.format(g=greeting), "handoff_ctx": AFTER._handoff_context, "handoff_greet": AFTER._handoff_greet},
        "mini_before": {"system": ins_b + BEFORE.REALTIME_RULES + "\n\n" + CONTEXT, "greet": GREET_OLD.format(g=greeting), "handoff_ctx": BEFORE._handoff_context, "handoff_greet": BEFORE._handoff_greet},
        "mini_after": {"system": AFTER.mini_instructions(ins_a, CONTEXT), "greet": GREET_MINI.format(g=greeting), "handoff_ctx": AFTER._handoff_context, "handoff_greet": AFTER._handoff_greet},
    }


def measure(text: str, turn_no: int) -> dict:
    words = len(text.split())
    sentences = len([s for s in re.split(r"[.!?]+", text) if s.strip()])
    return {"words": words, "sentences": sentences, "questions": text.count("?"), "filler": len(FILLER.findall(text)),
            "regreet": len(GREET.findall(text)) if turn_no > 0 else 0, "anything_else": len(ANYTHING_ELSE.findall(text))}


async def run_variant(name: str, v: dict) -> dict:
    out = {"name": name, "scenarios": []}
    for title, steps in SCENARIOS:
        handoff = title.startswith("10")
        system = v["system"] + ("\n\n" + v["handoff_ctx"](HANDOFF_PREV) if handoff else "")
        chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"eval-{uuid.uuid4().hex[:8]}", system_message=system).with_model(*STAND_IN)
        turns = []
        opener = v["handoff_greet"](HANDOFF_PREV) if handoff else v["greet"]
        reply = await chat.send_message(UserMessage(text=f"[instruction for your first words, not spoken by the rep] {opener}"))
        turns.append({"rep": "(session start)", "jessi": reply.strip(), **measure(reply, 0)})
        for i, step in enumerate(steps, start=1):
            msg = f"[rep says] {step['rep']}"
            if step.get("backend"):
                msg += f"\n[backend result, say it to the rep in your own voice, keep every name and number, add nothing] {step['backend']}"
            reply = await chat.send_message(UserMessage(text=msg))
            turns.append({"rep": step["rep"], "backend": step.get("backend"), "jessi": reply.strip(), **measure(reply, i)})
        out["scenarios"].append({"title": title, "turns": turns, **cost(turns, name)})
    return out


def cost(turns: list, variant: str) -> dict:
    jessi_s = sum(t["words"] for t in turns) / WORDS_PER_S
    rep_s = sum(len((t.get("rep") or "").split()) for t in turns if t["rep"] != "(session start)") / WORDS_PER_S
    total_s = jessi_s + rep_s + PAUSE_S * len(turns)
    if variant.startswith("live"):
        usd = max(total_s, 15) / 60 * AFTER.PRICE_PER_MIN
    else:
        p = AFTER.MINI_PRICES
        usd = (jessi_s * OUT_TOK_PER_S * p["audio_out"] + rep_s * IN_TOK_PER_S * p["audio_in"] + PROMPT_TOKENS * p["text_in"] + PROMPT_TOKENS * (len(turns) - 1) * p["text_in_cached"]
               + sum(t["words"] for t in turns) * 1.3 * p["text_out"]) / 1_000_000
    return {"est_jessi_speech_s": round(jessi_s, 1), "est_total_s": round(total_s, 1), "est_cost_usd": round(usd, 4)}


RUBRIC = ("You grade a voice assistant transcript. Jessi is a sales rep's voice assistant. Rules she must follow: answer first, one or two spoken sentences for simple asks, "
          "no filler, no repeated greetings or self-introductions after the first turn, follow-up questions only when needed, open up only when the rep asks for detail or brainstorming, "
          "keep every name and number from backend results, stay warm and natural, never robotic. Score 1-5 (5 best) for: quality, conciseness, adherence, flow, context_retention. "
          "Return strict JSON: {\"quality\":n,\"conciseness\":n,\"adherence\":n,\"flow\":n,\"context_retention\":n,\"note\":\"one short sentence\"}")


async def judge(scn: dict) -> dict:
    convo = "\n".join(f"REP: {t['rep']}\n" + (f"BACKEND: {t['backend']}\n" if t.get("backend") else "") + f"JESSI: {t['jessi']}" for t in scn["turns"])
    chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"judge-{uuid.uuid4().hex[:8]}", system_message=RUBRIC).with_model(*JUDGE)
    raw = await chat.send_message(UserMessage(text=f"Scenario: {scn['title']}\n\n{convo}"))
    m = re.search(r"\{.*\}", raw, re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except ValueError:
        return {}


def summarize(v: dict) -> dict:
    turns = [t for s in v["scenarios"] for t in s["turns"]]
    simple = [t for s in v["scenarios"] for t in s["turns"] if not s["title"].startswith(("9", "7", "5")) and t["rep"] != "(session start)"]
    scores = [s["judge"] for s in v["scenarios"] if s.get("judge")]
    avg = lambda k: round(statistics.mean(float(s.get(k, 0)) for s in scores), 2) if scores else None  # noqa: E731
    return {"replies": len(turns), "avg_words": round(statistics.mean(t["words"] for t in turns), 1), "opener_words": round(statistics.mean(s["turns"][0]["words"] for s in v["scenarios"]), 1),
            "simple_replies_le_2_sentences_pct": round(100 * sum(t["sentences"] <= 2 for t in simple) / max(1, len(simple))),
            "questions_per_reply": round(sum(t["questions"] for t in turns) / len(turns), 2), "regreets": sum(t["regreet"] for t in turns), "filler": sum(t["filler"] for t in turns),
            "anything_else": sum(t["anything_else"] for t in turns), "est_cost_10_scenarios_usd": round(sum(s["est_cost_usd"] for s in v["scenarios"]), 4),
            "judge": {k: avg(k) for k in ("quality", "conciseness", "adherence", "flow", "context_retention")}}


async def main():
    V = variants()
    results = {}
    for name, v in V.items():
        results[name] = await run_variant(name, v)
        for scn in results[name]["scenarios"]:
            scn["judge"] = await judge(scn)
        results[name]["summary"] = summarize(results[name])
        print(name, json.dumps(results[name]["summary"]))
    meta = {"kind": "SIMULATED (text model stand-in), not a real OpenAI audio test", "stand_in_model": STAND_IN, "judge_model": JUDGE,
            "prompt_chars": {k: len(v["system"]) for k, v in V.items()}, "cost_assumptions": {"words_per_s": WORDS_PER_S, "pause_s_per_turn": PAUSE_S, "audio_out_tok_per_s": OUT_TOK_PER_S, "audio_in_tok_per_s": IN_TOK_PER_S, "prompt_tokens": PROMPT_TOKENS, "pricing": AFTER.MINI_PRICES, "live_per_min": AFTER.PRICE_PER_MIN}}
    json.dump({"meta": meta, "results": results}, open(OUT_JSON, "w"), indent=1)
    rows = ["| variant | avg words/reply | opener words | simple replies <= 2 sentences | questions/reply | re-greets | filler | 'anything else' | est $ / 10 scenarios | judge quality | concise | adherence | flow | context |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, r in results.items():
        s = r["summary"]
        j = s["judge"]
        rows.append(f"| {name} | {s['avg_words']} | {s['opener_words']} | {s['simple_replies_le_2_sentences_pct']}% | {s['questions_per_reply']} | {s['regreets']} | {s['filler']} | {s['anything_else']} | ${s['est_cost_10_scenarios_usd']} | {j['quality']} | {j['conciseness']} | {j['adherence']} | {j['flow']} | {j['context_retention']} |")
    md = [f"# Jessi prompt parity: SIMULATED evaluation ({meta['kind']})", f"Stand-in model {STAND_IN[1]} for every variant (only the prompt differs); judge {JUDGE[1]}. Costs are ESTIMATES from the PRICING table and speech-seconds assumptions, not measured OpenAI usage.", ""] + rows + [""]
    for name, r in results.items():
        md.append(f"## {name}  (prompt {meta['prompt_chars'][name]} chars)")
        for scn in r["scenarios"]:
            md.append(f"**{scn['title']}** est ${scn['est_cost_usd']} / {scn['est_total_s']} s; judge: {scn.get('judge', {}).get('note', '')}")
            for t in scn["turns"]:
                md.append(f"- REP: {t['rep']}" + (f"  \n  BACKEND: {t['backend']}" if t.get("backend") else "") + f"  \n  JESSI ({t['words']} w, {t['sentences']} s): {t['jessi']}")
            md.append("")
    open(OUT_MD, "w").write("\n".join(md))
    print("wrote", OUT_JSON, OUT_MD)


if __name__ == "__main__":
    asyncio.run(main())
