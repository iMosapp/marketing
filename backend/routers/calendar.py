"""
Calendar router - handles Google Calendar OAuth and event management
Also provides endpoints for native device calendar integration
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from bson import ObjectId
from datetime import datetime, timedelta, timezone
from typing import Optional
import logging
import os
import requests  # only used for google-auth library compatibility
import httpx  # async HTTP — never blocks the event loop

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build

from routers.database import get_db

router = APIRouter(prefix="/calendar", tags=["Calendar"])
logger = logging.getLogger(__name__)

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
REDIRECT_URI = os.environ.get('GOOGLE_CALENDAR_REDIRECT_URI', 
    f"{os.environ.get('REACT_APP_BACKEND_URL', '')}/api/calendar/oauth/callback")

SCOPES = ['https://www.googleapis.com/auth/calendar']


@router.get("/oauth/login/{user_id}")
async def google_calendar_login(user_id: str):
    """Start Google Calendar OAuth flow"""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=503, 
            detail="Google Calendar integration not configured. Please provide GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
        )
    
    # Build authorization URL
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={GOOGLE_CLIENT_ID}&"
        f"redirect_uri={REDIRECT_URI}&"
        "response_type=code&"
        f"scope={'%20'.join(SCOPES)}&"
        "access_type=offline&"
        "prompt=consent&"
        f"state={user_id}"
    )
    
    return {"authorization_url": auth_url}


@router.get("/oauth/callback")
async def google_calendar_callback(code: str, state: str):
    """Handle Google OAuth callback"""
    user_id = state
    
    try:
        # Exchange code for tokens — use async httpx so we don't block the event loop
        async with httpx.AsyncClient(timeout=10.0) as client:
            token_resp = await client.post(
                'https://oauth2.googleapis.com/token',
                data={
                    'code': code,
                    'client_id': GOOGLE_CLIENT_ID,
                    'client_secret': GOOGLE_CLIENT_SECRET,
                    'redirect_uri': REDIRECT_URI,
                    'grant_type': 'authorization_code'
                }
            )
            token_response = token_resp.json()
        
        if 'error' in token_response:
            logger.error(f"Token exchange error: {token_response}")
            raise HTTPException(status_code=400, detail=token_response.get('error_description', 'OAuth failed'))
        
        # Get user email — async
        async with httpx.AsyncClient(timeout=10.0) as client:
            user_resp = await client.get(
                'https://www.googleapis.com/oauth2/v2/userinfo',
                headers={'Authorization': f'Bearer {token_response["access_token"]}'}
            )
            user_info = user_resp.json()
        
        # Save tokens to user record
        await get_db().users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {
                "google_calendar_tokens": {
                    "access_token": token_response['access_token'],
                    "refresh_token": token_response.get('refresh_token'),
                    "expires_at": datetime.now(timezone.utc) + timedelta(seconds=token_response.get('expires_in', 3600)),
                    "google_email": user_info.get('email')
                },
                "google_calendar_connected": True
            }}
        )
        
        # Redirect back to app with success
        frontend_url = os.environ.get('EXPO_PUBLIC_BACKEND_URL')
        if not frontend_url:
            frontend_url = os.environ.get('REACT_APP_BACKEND_URL', '')
        return RedirectResponse(f"{frontend_url}/settings/calendar?connected=true")
        
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{user_id}")
async def get_calendar_status(user_id: str):
    """Check if user has connected Google Calendar"""
    user = await get_db().users.find_one({"_id": ObjectId(user_id)}, {"google_calendar_connected": 1, "google_calendar_tokens": 1})
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "connected": user.get("google_calendar_connected", False),
        "google_email": user.get("google_calendar_tokens", {}).get("google_email")
    }


@router.delete("/disconnect/{user_id}")
async def disconnect_calendar(user_id: str):
    """Disconnect Google Calendar"""
    await get_db().users.update_one(
        {"_id": ObjectId(user_id)},
        {"$unset": {"google_calendar_tokens": 1}, "$set": {"google_calendar_connected": False}}
    )
    return {"message": "Calendar disconnected"}


async def get_google_credentials(user_id: str):
    """Get valid Google credentials for a user, refreshing if needed"""
    user = await get_db().users.find_one({"_id": ObjectId(user_id)})
    
    if not user or not user.get("google_calendar_tokens"):
        return None
    
    tokens = user["google_calendar_tokens"]
    
    creds = Credentials(
        token=tokens['access_token'],
        refresh_token=tokens.get('refresh_token'),
        token_uri='https://oauth2.googleapis.com/token',
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET
    )
    
    # Refresh if expired
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(GoogleRequest())
            # Update stored token
            await get_db().users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {
                    "google_calendar_tokens.access_token": creds.token,
                    "google_calendar_tokens.expires_at": datetime.now(timezone.utc) + timedelta(hours=1)
                }}
            )
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            return None
    
    return creds


@router.post("/events/{user_id}")
async def create_calendar_event(user_id: str, event_data: dict):
    """Create a calendar event for the user"""
    creds = await get_google_credentials(user_id)
    
    if not creds:
        raise HTTPException(status_code=401, detail="Google Calendar not connected")
    
    try:
        service = build('calendar', 'v3', credentials=creds)
        
        # Build event body
        event = {
            'summary': event_data.get('title', 'Appointment'),
            'description': event_data.get('description', ''),
            'start': {
                'dateTime': event_data['start_time'],
                'timeZone': event_data.get('timezone', 'America/New_York'),
            },
            'end': {
                'dateTime': event_data['end_time'],
                'timeZone': event_data.get('timezone', 'America/New_York'),
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'popup', 'minutes': 15},
                    {'method': 'popup', 'minutes': 60},
                ],
            },
        }
        
        # Add attendees if phone number provided (as description since can't add phone)
        if event_data.get('contact_phone'):
            event['description'] += f"\n\nContact: {event_data.get('contact_name', 'Unknown')}\nPhone: {event_data['contact_phone']}"
        
        # Add location if provided
        if event_data.get('location'):
            event['location'] = event_data['location']
        
        created_event = service.events().insert(
            calendarId='primary',
            body=event
        ).execute()
        
        logger.info(f"Created calendar event: {created_event.get('id')}")
        
        return {
            "success": True,
            "event_id": created_event.get('id'),
            "html_link": created_event.get('htmlLink')
        }
        
    except Exception as e:
        logger.error(f"Failed to create calendar event: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/appointments/{user_id}")
async def create_appointment_from_ai(user_id: str, appointment_data: dict):
    """
    Create an appointment when MVP (AI) sets one.
    This is called when AI detects an appointment was set in a conversation.
    """
    # Save appointment to database
    appointment = {
        "user_id": user_id,
        "conversation_id": appointment_data.get("conversation_id"),
        "contact_id": appointment_data.get("contact_id"),
        "contact_name": appointment_data.get("contact_name"),
        "contact_phone": appointment_data.get("contact_phone"),
        "title": appointment_data.get("title", f"Appointment with {appointment_data.get('contact_name', 'Contact')}"),
        "start_time": appointment_data.get("start_time"),
        "end_time": appointment_data.get("end_time"),
        "notes": appointment_data.get("notes", ""),
        "location": appointment_data.get("location", ""),
        "google_event_id": None,
        "synced_to_google": False,
        "created_at": datetime.now(timezone.utc),
        "created_by": "ai"
    }
    
    result = await get_db().appointments.insert_one(appointment)
    appointment_id = str(result.inserted_id)
    
    # Try to sync to Google Calendar if connected
    google_result = None
    try:
        creds = await get_google_credentials(user_id)
        if creds:
            event_data = {
                "title": appointment["title"],
                "description": f"Set by MVP (AI Assistant)\n\n{appointment.get('notes', '')}",
                "start_time": appointment["start_time"],
                "end_time": appointment["end_time"],
                "contact_name": appointment["contact_name"],
                "contact_phone": appointment["contact_phone"],
                "location": appointment.get("location")
            }
            
            service = build('calendar', 'v3', credentials=creds)
            
            event = {
                'summary': event_data['title'],
                'description': event_data['description'] + f"\n\nContact: {event_data.get('contact_name', 'Unknown')}\nPhone: {event_data.get('contact_phone', 'N/A')}",
                'start': {
                    'dateTime': event_data['start_time'],
                    'timeZone': 'America/New_York',
                },
                'end': {
                    'dateTime': event_data['end_time'],
                    'timeZone': 'America/New_York',
                },
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'popup', 'minutes': 15},
                        {'method': 'popup', 'minutes': 60},
                    ],
                },
            }
            
            if event_data.get('location'):
                event['location'] = event_data['location']
            
            created_event = service.events().insert(
                calendarId='primary',
                body=event
            ).execute()
            
            # Update appointment with Google event ID
            await get_db().appointments.update_one(
                {"_id": ObjectId(appointment_id)},
                {"$set": {
                    "google_event_id": created_event.get('id'),
                    "synced_to_google": True
                }}
            )
            
            google_result = {
                "synced": True,
                "event_id": created_event.get('id'),
                "html_link": created_event.get('htmlLink')
            }
            
    except Exception as e:
        logger.error(f"Failed to sync appointment to Google Calendar: {e}")
        google_result = {"synced": False, "error": str(e)}
    
    return {
        "success": True,
        "appointment_id": appointment_id,
        "google_calendar": google_result
    }


@router.get("/appointments/{user_id}")
async def get_user_appointments(user_id: str, upcoming_only: bool = True):
    """Get appointments for a user"""
    query = {"user_id": user_id}
    
    if upcoming_only:
        query["start_time"] = {"$gte": datetime.now(timezone.utc).isoformat()}
    
    appointments = await get_db().appointments.find(query).sort("start_time", 1).to_list(100)
    
    # Convert ObjectId to string
    for apt in appointments:
        apt["_id"] = str(apt["_id"])
    
    return appointments


@router.get("/native-event-data/{user_id}/{conversation_id}")
async def get_native_calendar_event_data(user_id: str, conversation_id: str):
    """
    Get event data formatted for native device calendar (expo-calendar).
    Frontend will use this to create events on iOS/Android native calendars.
    """
    # Get conversation and contact details
    conv = await get_db().conversations.find_one({"_id": ObjectId(conversation_id)})
    
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    contact = await get_db().contacts.find_one({"_id": ObjectId(conv.get("contact_id"))}) if conv.get("contact_id") else None
    
    contact_name = contact.get("name") if contact else conv.get("contact_phone", "Unknown")
    contact_phone = contact.get("phone") if contact else conv.get("contact_phone", "")
    
    # Default to 1 hour appointment starting in 1 day
    default_start = datetime.now(timezone.utc) + timedelta(days=1)
    default_end = default_start + timedelta(hours=1)
    
    return {
        "title": f"Appointment with {contact_name}",
        "notes": f"Contact: {contact_name}\nPhone: {contact_phone}\n\nSet by MVP (AI Assistant)",
        "startDate": default_start.isoformat(),
        "endDate": default_end.isoformat(),
        "alarms": [
            {"relativeOffset": -15},  # 15 minutes before
            {"relativeOffset": -60},  # 1 hour before
        ],
        "contact": {
            "name": contact_name,
            "phone": contact_phone
        }
    }
