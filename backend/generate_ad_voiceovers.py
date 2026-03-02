"""Generate voiceovers for 4 ad videos using OpenAI TTS via emergentintegrations"""
import os
import asyncio
from dotenv import load_dotenv
from emergentintegrations.llm.openai import OpenAITextToSpeech

load_dotenv()

EMERGENT_KEY = os.getenv("EMERGENT_LLM_KEY")
OUTPUT_DIR = "/app/frontend/public"

ADS = [
    {
        "filename": "ad1-digital-card.mp3",
        "voice": "onyx",
        "script": (
            "Your business card is outdated. Crumpled up in someone's pocket, forgotten in a drawer. "
            "What if every card you shared was digital, trackable, and unforgettable? "
            "With i'M On Social, share your digital business card via text, QR code, or a single tap. "
            "Know exactly who opened it, when they saved your contact, and when they shared it with a friend. "
            "Every interaction tracked. Every connection counted. "
            "Stop handing out paper. Start building relationships that stick. "
            "Get started at i'm on social dot com."
        ),
    },
    {
        "filename": "ad2-showcase.mp3",
        "voice": "nova",
        "script": (
            "Your happy customers are your best salespeople. So why aren't you showing them off? "
            "With i'M On Social, every team member gets a beautiful, shareable showcase page. "
            "Congrats cards, five-star reviews, happy customer photos, all in one place. "
            "Send it to a prospect and let your results speak for themselves. "
            "No website needed. No design skills required. Just real results, beautifully displayed. "
            "Your reputation, amplified. "
            "See it in action at i'm on social dot com."
        ),
    },
    {
        "filename": "ad3-reviews.mp3",
        "voice": "echo",
        "script": (
            "Getting five-star reviews shouldn't be hard. But most businesses forget to ask. "
            "With i'M On Social, any employee can send a Google or Facebook review request in one tap. "
            "Pick a customer, hit send, and a branded review link goes out instantly via text or email. "
            "No copying links. No awkward asks. Just a simple, professional request that gets results. "
            "Our users have tripled their Google reviews in ninety days. "
            "Your turn. Try it at i'm on social dot com."
        ),
    },
    {
        "filename": "ad4-autopilot.mp3",
        "voice": "shimmer",
        "script": (
            "What if your business stayed connected with every customer, automatically? "
            "Birthday messages that feel personal. Follow-ups that never fall through the cracks. "
            "Campaigns that run twenty-four seven while you focus on selling. "
            "i'M On Social makes it effortless. Set it up once, and watch your relationships grow on autopilot. "
            "AI-powered messaging. Automated campaigns. Real-time tracking. "
            "All from an app your whole team will actually use. "
            "Book a demo at i'm on social dot com."
        ),
    },
]


async def generate_all():
    tts = OpenAITextToSpeech(api_key=EMERGENT_KEY)
    for ad in ADS:
        output_path = os.path.join(OUTPUT_DIR, ad["filename"])
        print(f"Generating {ad['filename']} with voice '{ad['voice']}'...")
        try:
            audio_bytes = await tts.generate_speech(
                text=ad["script"],
                model="tts-1-hd",
                voice=ad["voice"],
                response_format="mp3",
            )
            with open(output_path, "wb") as f:
                f.write(audio_bytes)
            size = os.path.getsize(output_path)
            print(f"  -> Saved {ad['filename']} ({size:,} bytes)")
        except Exception as e:
            print(f"  -> ERROR generating {ad['filename']}: {e}")


if __name__ == "__main__":
    asyncio.run(generate_all())
