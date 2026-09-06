"""Help Center AI - An intelligent assistant that knows I'm On Social inside and out."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
import logging

router = APIRouter(prefix="/help-center", tags=["Help Center"])
logger = logging.getLogger(__name__)

HELP_KNOWLEDGE_HEADER = """
You are the i'M On Social Help Center assistant. You know the app exactly as it is today and answer in two to five short sentences. Always tell the user exactly where to tap using the current names (for example "Tools > Set Up > Phone Numbers"). Salespeople see a simplified app (Home with three cards, Tools with Today / My Brand / Inventory / Learning / Settings); managers and admins see everything. If a question is about a manager-only screen, say so. Plain text only: no markdown, no asterisks, no bullet symbols. Never use em dashes. If you are not sure, say what you do know and suggest Tools > Learning > Training Hub or Report a Bug.

"""


def _knowledge() -> str:
    from content.training_2026 import knowledge_text
    return HELP_KNOWLEDGE_HEADER + knowledge_text()

class HelpQuery(BaseModel):
    question: str
    user_id: str = ""

@router.post("/ask")
async def ask_help_ai(data: HelpQuery):
    """Ask the Help Center AI a question about I'm On Social."""
    try:
        api_key = os.getenv("EMERGENT_LLM_KEY")
        if not api_key:
            return {"answer": "AI assistant is not configured. Please check your EMERGENT_LLM_KEY.", "source": "error"}

        from emergentintegrations.llm.chat import LlmChat, UserMessage

        chat = LlmChat(
            api_key=api_key,
            session_id=f"help_{data.user_id or 'anon'}",
            system_message=_knowledge()
        ).with_model("openai", "gpt-5.2")

        response = await chat.send_message(UserMessage(text=data.question))
        from utils.text_sanitize import no_em_dash
        answer = (response if isinstance(response, str) else str(response)).replace("**", "")
        return {"answer": no_em_dash(answer), "source": "ai"}

    except Exception as e:
        logger.error(f"Help AI error: {e}")
        return {"answer": "Sorry, I couldn't process your question right now. Try browsing the articles below.", "source": "error"}
