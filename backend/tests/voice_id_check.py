"""Real Eagle round trip on this server: enroll a synthetic voice (OpenAI TTS 'nova'), then score a new 'nova' clip against an 'onyx' clip.
Run: cd /app/backend && set -a && . ./.env && set +a && python tests/voice_id_check.py"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import voice_id  # noqa: E402

ENROLL = ("Hey, it's Alex over at QA Motors. I have been selling trucks and SUVs for about twelve years now. I grew up in Ogden and I still live about ten minutes "
          "from where I was raised. My wife Jen and I have two boys and a very loud husky named Blue. Weekends we are usually camping up in the Uintas or at a little "
          "league game, and I fly fish whenever I can sneak away. I text pretty casual, short messages, maybe a thumbs up now and then. I never say what is it going to "
          "take to get you in a car today, I hate that line, and I never bad mouth another store. Fun fact, I was a college wrestler and I still coach the middle school team.")
TEST = "Thanks for reaching out about the Tahoe. Let me pull the exact numbers on that and get right back to you. Does Tuesday afternoon work to swing by?"


async def tts(text: str, voice: str) -> bytes:
    from emergentintegrations.llm.openai import OpenAITextToSpeech
    return await OpenAITextToSpeech(api_key=os.environ["EMERGENT_LLM_KEY"]).generate_speech(text=text, model="tts-1", voice=voice, speed=1.0, response_format="mp3")


async def main():
    print("available:", voice_id.available() or "yes", "| lib override:", bool(voice_id._lib_kwargs()))
    assert voice_id.available() is None
    t = time.time()
    nova_enroll, nova_test, onyx_test = await asyncio.gather(tts(ENROLL, "nova"), tts(TEST, "nova"), tts(TEST, "onyx"))
    print(f"tts {time.time() - t:.1f}s")
    pcm = voice_id.to_pcm16k(nova_enroll)
    print(f"enroll clip {voice_id.pcm_seconds(pcm):.1f}s")
    t = time.time()
    out = voice_id.enroll(pcm)
    print(f"enroll {time.time() - t:.1f}s -> percent {out['percent']} profile {len(out['profile'] or b'')} bytes")
    assert out["profile"], "enrollment did not reach 100%"
    same = voice_id.score(voice_id.to_pcm16k(nova_test), [out["profile"]])[0]
    other = voice_id.score(voice_id.to_pcm16k(onyx_test), [out["profile"]])[0]
    print(f"same voice {same} | other voice {other} | threshold {voice_id.THRESHOLD}")
    assert same is not None and other is not None and same > other, "scores do not separate the voices"
    print("ALL OK")


if __name__ == "__main__":
    asyncio.run(main())
