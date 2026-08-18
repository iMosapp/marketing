"""
Intent Detection Service — real-time buying signal analysis.

Runs on every inbound customer message. Uses GPT to score buying intent
and identify which signals are present. Non-blocking — fires as asyncio task.

Score guide:
  0-3  : No intent / casual conversation
  4-6  : Moderate interest — worth watching
  7-8  : High intent — notify rep immediately
  9-10 : Extremely hot — customer is ready to buy NOW

Categories (can have multiple):
  payment_discussion    — Monthly payments, financing, down payment, rates
  visit_readiness       — Wants to come in, asking about hours/directions
  urgency               — Needs it soon, deadline, life event driving purchase
  specific_availability — "Do you have a [specific vehicle]?" 
  price_negotiation     — Best deal, OTD price, "can you do"
  strong_buy_signal     — "Ready to buy", "where do I sign", "let's do it"
  trade_in              — Asking about trade-in value
"""
import os
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


INTENT_PROMPT = """You are a sales intelligence assistant for an automotive dealership CRM.

Analyze this customer message and recent conversation for buying intent signals.

Return ONLY valid JSON, no explanation:
{{
  "score": <0-10 integer>,
  "signals": ["signal1", "signal2"],
  "category": "payment_discussion|visit_readiness|urgency|specific_availability|price_negotiation|strong_buy_signal|trade_in|none",
  "hot_summary": "<15 word max description for rep notification, or empty string if score < 7>"
}}

Score guide:
- 0-3: No buying signals / just chatting
- 4-6: Mild interest (asking general questions)
- 7-8: Strong intent (payment talk, wants to visit, specific vehicle ask)
- 9-10: Ready to buy NOW ("let's do it", "can I come in today to sign")

Buying signal keywords to watch for:
- Payments: "monthly payment", "per month", "down payment", "finance", "interest rate", "out the door"
- Visit: "come in", "stop by", "today", "this week", "your hours", "still open"
- Urgency: "need it by", "this weekend", "wife is pregnant", "just got approved", "have to decide"
- Availability: "do you have", "in stock", "available", "still have the"
- Negotiation: "best price", "can you do", "meet me at", "what's your best"
- Strong: "ready to buy", "want to purchase", "let's do this", "where do I sign"
- Trade: "trade in", "worth for my", "what would you give me"

Customer name: {contact_name}
Recent conversation (last 3 messages):
{conversation_context}

Latest customer message:
{message}"""


async def detect_buying_intent(
    message: str,
    contact_name: str,
    recent_messages: list,
    user_id: str,
    contact_id: str,
    conversation_id: str,
) -> dict:
    """
    Classify buying intent in a customer message.
    Returns dict with score, signals, category, hot_summary.
    Never raises — returns safe default on any error.
    """
    default = {"score": 0, "signals": [], "category": "none", "hot_summary": ""}

    if not message or not message.strip():
        return default

    # Quick pre-filter — skip obvious non-intent messages to save API calls
    msg_lower = message.lower().strip()
    skip_phrases = ["ok", "okay", "thanks", "thank you", "got it", "sounds good",
                    "lol", "haha", "😂", "👍", "yes", "no", "sure", "cool", "great"]
    if msg_lower in skip_phrases or len(message.strip()) < 8:
        return default

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            return default

        # Build conversation context (last 3 messages)
        ctx_parts = []
        for m in recent_messages[-3:]:
            direction = "Customer" if m.get("direction") == "inbound" else "Rep"
            ctx_parts.append(f"{direction}: {(m.get('content') or '')[:150]}")
        conversation_context = "\n".join(ctx_parts) if ctx_parts else "No prior context"

        prompt = INTENT_PROMPT.format(
            contact_name=contact_name,
            conversation_context=conversation_context,
            message=message[:500],
        )

        chat = LlmChat(
            api_key=api_key,
            session_id=f"intent-{conversation_id}",
            system_message="You are a buying intent classifier. Return only valid JSON.",
        ).with_model("openai", "gpt-4.1-mini")

        response = await chat.send_message(UserMessage(text=prompt))
        raw = response.strip() if isinstance(response, str) else (
            response.text.strip() if hasattr(response, "text") else str(response)
        )

        # Strip markdown code blocks if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        import json
        result = json.loads(raw)
        score = int(result.get("score", 0))
        result["score"] = min(max(score, 0), 10)
        return result

    except Exception as e:
        logger.debug(f"[IntentDetect] Failed for conv {conversation_id}: {e}")
        return default


async def process_inbound_intent(
    db,
    message: str,
    contact_name: str,
    contact_id: str,
    conversation_id: str,
    user_id: str,
):
    """
    Full pipeline: detect intent → store result → fire push if hot.
    Called as fire-and-forget asyncio.create_task from twilio_webhooks.
    """
    try:
        # Get recent messages for context
        recent_messages = await db.messages.find(
            {"conversation_id": conversation_id},
            {"content": 1, "direction": 1}
        ).sort("timestamp", -1).limit(4).to_list(4)
        recent_messages.reverse()  # oldest first

        result = await detect_buying_intent(
            message=message,
            contact_name=contact_name,
            recent_messages=recent_messages,
            user_id=user_id,
            contact_id=contact_id,
            conversation_id=conversation_id,
        )

        score = result.get("score", 0)
        signals = result.get("signals", [])
        hot_summary = result.get("hot_summary", "")

        if score < 4:
            return  # Not interesting — skip DB write

        now = datetime.now(timezone.utc)

        # Store intent on the conversation
        await db.conversations.update_one(
            {"_id": __import__("bson").ObjectId(conversation_id)},
            {"$set": {
                "intent_score": score,
                "intent_signals": signals,
                "intent_category": result.get("category", ""),
                "intent_detected_at": now,
                "hot_opportunity": score >= 7,
            }}
        )

        logger.info(f"[Intent] Conv {conversation_id[:8]} | score={score} | signals={signals}")

        # Fire Hot Opportunity push when score >= 7
        if score >= 7 and user_id:
            summary = hot_summary or f"{contact_name} is showing strong buying intent"
            try:
                from routers.push_notifications import send_push_to_user
                await send_push_to_user(
                    user_id=user_id,
                    title=f"🔥 Hot Opportunity — {contact_name}",
                    body=summary,
                    url=f"/thread/{conversation_id}",
                    icon="flame",
                )
                # Mark as hot in conversation so inbox shows it
                await db.conversations.update_one(
                    {"_id": __import__("bson").ObjectId(conversation_id)},
                    {"$set": {"hot_opportunity": True, "hot_notified_at": now}}
                )
                logger.info(f"[Intent] 🔥 HOT push fired for {contact_name} (score={score})")
            except Exception as push_err:
                logger.warning(f"[Intent] Push failed: {push_err}")

    except Exception as e:
        logger.warning(f"[Intent] process_inbound_intent failed: {e}")
