"""
Jessi AI Assistant Service
A friendly voice-enabled AI assistant that helps users learn about MVPLine features
"""
import os
from datetime import datetime
from typing import Optional
from bson import ObjectId
from dotenv import load_dotenv

load_dotenv()

from emergentintegrations.llm.chat import LlmChat, UserMessage
from emergentintegrations.llm.openai import OpenAITextToSpeech

from routers.database import get_db

# Jessi's system prompt - defines her personality and knowledge
JESSIE_SYSTEM_PROMPT = """You are Jessi, a friendly and helpful AI assistant for iMOs - a relationship management system (RMS) and communication platform for sales professionals. Your personality is warm, encouraging, and patient.

## Your Role:
- Help users understand and use MVPLine features
- Answer questions about the app in a conversational, friendly way
- Guide users through tasks step-by-step when needed
- Celebrate their successes and encourage them

## About MVPLine:
MVPLine helps automotive sales professionals manage customer relationships and communications. Key features include:

### Communication
- **Inbox**: Unified messaging with customers via SMS/MMS
- **Calls**: Make and receive calls through the app
- **Digital Business Cards**: Share contact info with a beautiful landing page
- **Congrats Cards**: Send celebratory messages when customers buy vehicles

### Sales Tools
- **Contacts**: Manage customer information and history
- **Tasks**: Track follow-ups and to-dos
- **Campaigns**: Automated message sequences for lead nurturing
- **Leaderboard**: Track sales performance and compete with teammates

### Profile & Branding
- **My Profile**: Set up your bio, photo, fun facts, and social links
- **AI Persona**: Let AI help craft your messaging style
- **Templates**: Save and reuse common messages

### Admin Features (for managers)
- **Team Management**: Add/remove team members
- **Activity Feed**: Monitor team activity
- **Reports**: View performance metrics

## Guidelines:
- Keep responses concise but helpful (2-3 sentences when possible)
- Use a warm, encouraging tone
- If you don't know something, say so honestly
- Offer to help with related topics
- Remember context from earlier in the conversation

## Example Responses:
- "Great question! The Inbox is where all your customer messages live. You can send texts, photos, and even voice messages right from there!"
- "I'd love to help you set up your digital business card! First, go to Settings, then tap 'My Profile'. From there, you can add your photo and all your contact details."
- "That's awesome that you closed a deal! You can send a Congrats Card by opening the conversation with your customer and tapping the gift icon."

Remember: You're Jessi - friendly, helpful, and always here to make their MVPLine experience better!"""


async def get_or_create_chat_session(user_id: str) -> dict:
    """Get existing chat session or create a new one for the user"""
    db = get_db()
    
    # Look for existing session
    session = await db.jessie_sessions.find_one({
        "user_id": user_id,
        "is_active": True
    })
    
    if session:
        return {
            "_id": str(session["_id"]),
            "session_id": session["session_id"],
            "messages": session.get("messages", []),
            "created_at": session.get("created_at"),
        }
    
    # Create new session
    import secrets
    session_id = f"jessie_{user_id}_{secrets.token_hex(8)}"
    
    new_session = {
        "user_id": user_id,
        "session_id": session_id,
        "messages": [],
        "is_active": True,
        "created_at": datetime.utcnow(),
    }
    
    result = await db.jessie_sessions.insert_one(new_session)
    new_session["_id"] = str(result.inserted_id)
    
    return new_session


async def save_message(user_id: str, role: str, content: str, audio_url: Optional[str] = None):
    """Save a message to the user's chat history"""
    db = get_db()
    
    message = {
        "role": role,  # "user" or "assistant"
        "content": content,
        "audio_url": audio_url,
        "timestamp": datetime.utcnow(),
    }
    
    await db.jessie_sessions.update_one(
        {"user_id": user_id, "is_active": True},
        {
            "$push": {"messages": message},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    
    return message


async def get_chat_history(user_id: str, limit: int = 20) -> list:
    """Get recent chat history for context"""
    db = get_db()
    
    session = await db.jessie_sessions.find_one({
        "user_id": user_id,
        "is_active": True
    })
    
    if not session:
        return []
    
    messages = session.get("messages", [])
    return messages[-limit:] if len(messages) > limit else messages


async def chat_with_jessie(user_id: str, user_message: str) -> dict:
    """
    Send a message to Jessi and get a response.
    Maintains conversation history for context.
    """
    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        raise ValueError("EMERGENT_LLM_KEY not configured")
    
    # Get or create session
    session = await get_or_create_chat_session(user_id)
    
    # Get user info for personalization
    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    user_name = user.get("name", "").split()[0] if user else ""
    
    # Build personalized system prompt
    personalized_prompt = JESSIE_SYSTEM_PROMPT
    if user_name:
        personalized_prompt += f"\n\nYou're currently helping {user_name}. Use their name occasionally to be personal."
    
    # Initialize chat with history
    chat = LlmChat(
        api_key=api_key,
        session_id=session["session_id"],
        system_message=personalized_prompt
    ).with_model("openai", "gpt-5.2")
    
    # Load previous messages into context
    history = await get_chat_history(user_id, limit=10)
    for msg in history:
        if msg["role"] == "user":
            await chat.send_message(UserMessage(text=msg["content"]))
        # Assistant messages are included automatically by the chat object
    
    # Save user message
    await save_message(user_id, "user", user_message)
    
    # Get Jessi's response
    message = UserMessage(text=user_message)
    response_text = await chat.send_message(message)
    
    # Save assistant message
    await save_message(user_id, "assistant", response_text)
    
    return {
        "text": response_text,
        "session_id": session["session_id"],
    }


async def generate_voice_response(text: str) -> bytes:
    """
    Generate voice audio from Jessi's text response.
    Uses OpenAI TTS with the 'nova' voice (energetic, upbeat female voice).
    """
    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        raise ValueError("EMERGENT_LLM_KEY not configured")
    
    tts = OpenAITextToSpeech(api_key=api_key)
    
    # Use nova voice - energetic and upbeat, with faster speed
    audio_bytes = await tts.generate_speech(
        text=text,
        model="tts-1",  # Use standard for faster response
        voice="nova",  # Energetic, upbeat female voice
        speed=1.15,  # Slightly faster for peppier delivery
        response_format="mp3"
    )
    
    return audio_bytes


async def generate_voice_response_base64(text: str) -> str:
    """Generate voice as base64 for direct embedding in responses"""
    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        raise ValueError("EMERGENT_LLM_KEY not configured")
    
    tts = OpenAITextToSpeech(api_key=api_key)
    
    audio_base64 = await tts.generate_speech_base64(
        text=text,
        model="tts-1",
        voice="nova",  # Energetic, upbeat female voice
        speed=1.15,  # Slightly faster for peppier delivery
        response_format="mp3"
    )
    
    return audio_base64


async def clear_chat_history(user_id: str):
    """Clear chat history for a user (start fresh conversation)"""
    db = get_db()
    
    # Mark current session as inactive
    await db.jessie_sessions.update_one(
        {"user_id": user_id, "is_active": True},
        {"$set": {"is_active": False, "ended_at": datetime.utcnow()}}
    )
    
    return {"message": "Chat history cleared"}


async def extract_profile_info(text: str, context: str = "intro") -> dict:
    """
    Extract structured profile information from natural speech.
    Uses AI to parse what the user said into profile fields.
    """
    import json
    
    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        raise ValueError("EMERGENT_LLM_KEY not configured")
    
    # Context-specific extraction prompts
    extraction_prompts = {
        "intro": """Extract the following from this self-introduction:
- bio: A 1-2 sentence professional bio
- years_experience: How many years of experience (just the number or phrase)
- specialties: List of professional specialties or skills mentioned
- personal_motto: Any motto or philosophy mentioned""",
        
        "hobbies": """Extract the following from this description of hobbies/interests:
- hobbies: List of hobbies mentioned
- interests: List of interests or passions mentioned""",
        
        "family": """Extract the following from this personal/family description:
- family_info: A brief summary of family situation
- fun_facts: List of fun or interesting facts about them""",
        
        "expertise": """Extract the following from this expertise description:
- specialties: List of areas of expertise
- fun_facts: List of achievements or interesting facts
- personal_motto: Any philosophy or approach mentioned"""
    }
    
    prompt = extraction_prompts.get(context, extraction_prompts["intro"])
    
    system_prompt = f"""You are a profile data extractor. Extract structured information from the user's speech.

{prompt}

IMPORTANT:
- Only extract information that was actually mentioned
- Return empty arrays [] for lists with no items
- Return null for fields not mentioned
- Keep text natural and conversational
- For bio, write in third person ("Forest is..." not "I am...")

Return ONLY valid JSON, no markdown or explanation."""

    chat = LlmChat(
        api_key=api_key,
        model="gpt-5.2",
        system=system_prompt
    )
    
    user_msg = UserMessage(f"Here's what they said:\n\n\"{text}\"")
    response = await chat.send_async(user_msg)
    
    # Parse the JSON response
    try:
        # Clean up response - remove markdown code blocks if present
        response_text = response.strip()
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        
        extracted = json.loads(response_text)
        
        # Clean up null values
        return {k: v for k, v in extracted.items() if v is not None and v != [] and v != ""}
    except json.JSONDecodeError:
        # If JSON parsing fails, return minimal extraction
        return {"bio": text[:200] if len(text) > 200 else text}
