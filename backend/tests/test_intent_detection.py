"""
Tests for intent_detection.py — detect_buying_intent and process_inbound_intent.
Runs async functions synchronously via asyncio.run().
"""
import pytest
import asyncio
import sys
import os

# Load backend .env so EMERGENT_LLM_KEY and MONGO_URL are available
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

sys.path.insert(0, "/app/backend")

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")


def run(coro):
    return asyncio.run(coro)


# ─────────────────────────────────────────────
# Skip-phrase / pre-filter tests (no GPT needed)
# ─────────────────────────────────────────────

def test_skip_phrase_ok():
    from services.intent_detection import detect_buying_intent
    result = run(detect_buying_intent("ok", "User", [], "u1", "c1", "cv1"))
    assert result["score"] == 0
    print("PASS: 'ok' -> score=0")


def test_skip_phrase_thanks():
    from services.intent_detection import detect_buying_intent
    result = run(detect_buying_intent("thanks", "User", [], "u1", "c1", "cv1"))
    assert result["score"] == 0
    print("PASS: 'thanks' -> score=0")


def test_skip_phrase_thank_you():
    from services.intent_detection import detect_buying_intent
    result = run(detect_buying_intent("thank you", "User", [], "u1", "c1", "cv1"))
    assert result["score"] == 0
    print("PASS: 'thank you' -> score=0")


def test_empty_message_returns_default():
    from services.intent_detection import detect_buying_intent
    result = run(detect_buying_intent("", "User", [], "u1", "c1", "cv1"))
    assert result == {"score": 0, "signals": [], "category": "none", "hot_summary": ""}
    print("PASS: empty message -> full default")


def test_short_message_under_8_chars():
    from services.intent_detection import detect_buying_intent
    result = run(detect_buying_intent("hi", "User", [], "u1", "c1", "cv1"))
    assert result["score"] == 0
    print("PASS: 'hi' (<8 chars) -> score=0")


def test_skip_phrase_yes():
    from services.intent_detection import detect_buying_intent
    result = run(detect_buying_intent("yes", "User", [], "u1", "c1", "cv1"))
    assert result["score"] == 0
    print("PASS: 'yes' -> score=0")


def test_skip_phrase_cool():
    from services.intent_detection import detect_buying_intent
    result = run(detect_buying_intent("cool", "User", [], "u1", "c1", "cv1"))
    assert result["score"] == 0
    print("PASS: 'cool' -> score=0")


# ─────────────────────────────────────────────
# GPT-based tests (need EMERGENT_LLM_KEY)
# ─────────────────────────────────────────────

def test_result_always_has_required_fields():
    """All 4 fields must be present regardless of message content."""
    from services.intent_detection import detect_buying_intent
    result = run(detect_buying_intent(
        "What are my monthly payments on the 2024 F-150?",
        "John Smith", [], "u1", "c1", "cv_fields"
    ))
    assert "score" in result
    assert "signals" in result
    assert "category" in result
    assert "hot_summary" in result
    assert isinstance(result["score"], int)
    assert isinstance(result["signals"], list)
    assert 0 <= result["score"] <= 10
    print(f"PASS: all fields valid, score={result['score']}")


def test_payment_question_scores_high():
    """Monthly payment question should score >= 5 (signals buying interest)."""
    from services.intent_detection import detect_buying_intent
    result = run(detect_buying_intent(
        "What are my monthly payments on the 2024 F-150?",
        "John Smith", [], "u1", "c1", "cv_pay"
    ))
    assert result["score"] >= 5, f"Expected >= 5 for payment question, got {result['score']}"
    print(f"PASS: payment question score={result['score']}")


def test_ready_to_buy_scores_nine_or_ten():
    """'Ready to buy, where do I sign?' should score >= 9."""
    from services.intent_detection import detect_buying_intent
    result = run(detect_buying_intent(
        "I'm ready to buy, where do I sign?",
        "Jane Doe", [], "u1", "c1", "cv_buy"
    ))
    assert result["score"] >= 9, f"Expected >= 9 for ready-to-buy, got {result['score']}"
    print(f"PASS: ready-to-buy score={result['score']}")


def test_hot_summary_non_empty_when_score_high():
    """hot_summary must be non-empty string when score >= 7."""
    from services.intent_detection import detect_buying_intent
    result = run(detect_buying_intent(
        "Can I come in today to sign? I got approved yesterday.",
        "Sarah Connor", [], "u1", "c1", "cv_sum"
    ))
    if result["score"] >= 7:
        assert result["hot_summary"] != "", f"hot_summary empty for score={result['score']}"
        print(f"PASS: hot_summary='{result['hot_summary']}'")
    else:
        pytest.skip(f"GPT returned score={result['score']} < 7")


# ─────────────────────────────────────────────
# process_inbound_intent DB integration tests
# ─────────────────────────────────────────────

def get_real_conversation_id():
    """Get a real conversation _id string directly from MongoDB."""
    import motor.motor_asyncio

    async def _fetch():
        client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]
        conv = await db.conversations.find_one({}, {"_id": 1})
        client.close()
        if conv:
            return str(conv["_id"])
        return None

    return run(_fetch())


def test_process_inbound_intent_high_score_sets_hot_opportunity():
    """Mocked score=8 -> hot_opportunity=True written to DB."""
    import motor.motor_asyncio
    import bson
    from unittest.mock import patch, AsyncMock

    conv_id = get_real_conversation_id()
    if not conv_id:
        pytest.skip("No conversation in DB")

    async def _run():
        from services.intent_detection import process_inbound_intent
        client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]

        high_intent = {
            "score": 8,
            "signals": ["payment_discussion"],
            "category": "payment_discussion",
            "hot_summary": "Customer asking about payments",
        }

        with patch("services.intent_detection.detect_buying_intent", return_value=high_intent):
            # Patch push; it may or may not import correctly
            with patch("services.intent_detection.send_push_to_user", new_callable=AsyncMock, create=True):
                await process_inbound_intent(
                    db=db,
                    message="What are my monthly payments?",
                    contact_name="Test Contact",
                    contact_id="c1",
                    conversation_id=conv_id,
                    user_id="69a0b7095fddcede09591667",
                )

        updated = await db.conversations.find_one({"_id": bson.ObjectId(conv_id)})
        client.close()
        return updated

    updated = run(_run())
    assert updated is not None
    assert updated.get("intent_score") == 8, f"Expected intent_score=8, got {updated.get('intent_score')}"
    assert updated.get("hot_opportunity") == True, f"Expected hot_opportunity=True, got {updated.get('hot_opportunity')}"
    assert "intent_signals" in updated
    print(f"PASS: score=8 -> hot_opportunity=True, intent_score=8")


def test_process_inbound_intent_low_score_no_db_write():
    """Mocked score=2 -> nothing written to DB (early return)."""
    import motor.motor_asyncio
    import bson
    from unittest.mock import patch

    conv_id = get_real_conversation_id()
    if not conv_id:
        pytest.skip("No conversation in DB")

    async def _run():
        from services.intent_detection import process_inbound_intent
        client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]

        # Reset intent fields
        await db.conversations.update_one(
            {"_id": bson.ObjectId(conv_id)},
            {"$unset": {"intent_score": "", "hot_opportunity": "", "intent_signals": ""}}
        )

        low_intent = {"score": 2, "signals": [], "category": "none", "hot_summary": ""}

        with patch("services.intent_detection.detect_buying_intent", return_value=low_intent):
            await process_inbound_intent(
                db=db,
                message="ok",
                contact_name="Test Contact",
                contact_id="c1",
                conversation_id=conv_id,
                user_id="69a0b7095fddcede09591667",
            )

        updated = await db.conversations.find_one({"_id": bson.ObjectId(conv_id)})
        client.close()
        return updated

    updated = run(_run())
    assert updated is not None
    assert updated.get("intent_score") is None, f"Expected no intent_score, got {updated.get('intent_score')}"
    print("PASS: low score (<4) does not write to DB")


def test_process_inbound_intent_moderate_score_not_hot():
    """Mocked score=5 -> intent_score=5, hot_opportunity=False."""
    import motor.motor_asyncio
    import bson
    from unittest.mock import patch

    conv_id = get_real_conversation_id()
    if not conv_id:
        pytest.skip("No conversation in DB")

    async def _run():
        from services.intent_detection import process_inbound_intent
        client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]

        mod_intent = {"score": 5, "signals": ["interest"], "category": "none", "hot_summary": ""}

        with patch("services.intent_detection.detect_buying_intent", return_value=mod_intent):
            await process_inbound_intent(
                db=db,
                message="I'm kind of interested in your SUVs",
                contact_name="Test Contact",
                contact_id="c1",
                conversation_id=conv_id,
                user_id="69a0b7095fddcede09591667",
            )

        updated = await db.conversations.find_one({"_id": bson.ObjectId(conv_id)})
        client.close()
        return updated

    updated = run(_run())
    assert updated is not None
    assert updated.get("intent_score") == 5, f"Expected intent_score=5, got {updated.get('intent_score')}"
    assert updated.get("hot_opportunity") == False, f"Expected hot_opportunity=False, got {updated.get('hot_opportunity')}"
    print("PASS: score=5 -> intent_score=5, hot_opportunity=False")
