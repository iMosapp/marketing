#!/usr/bin/env python3
"""
MVPLine Backend API Test Suite
Comprehensive testing for all backend APIs
"""

import requests
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Configuration
BASE_URL = "https://sop-training.preview.emergentagent.com/api"
TIMEOUT = 30

# Test state storage
test_state = {
    'user_id': None,
    'token': None,
    'contact_ids': [],
    'conversation_id': None,
    'campaign_id': None,
    'task_id': None,
    'call_id': None
}

# Test results tracking
test_results = {
    'passed': [],
    'failed': [],
    'errors': []
}

def log_test(test_name: str, success: bool, details: str = ""):
    """Log test results"""
    status = "✅ PASSED" if success else "❌ FAILED"
    print(f"{status}: {test_name}")
    if details:
        print(f"   Details: {details}")
    
    if success:
        test_results['passed'].append(test_name)
    else:
        test_results['failed'].append({'test': test_name, 'details': details})

def make_request(method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
    """Make HTTP request with error handling"""
    url = f"{BASE_URL}{endpoint}"
    try:
        response = requests.request(method, url, timeout=TIMEOUT, **kwargs)
        return {
            'success': True,
            'status_code': response.status_code,
            'data': response.json() if response.content else {},
            'response': response
        }
    except requests.exceptions.RequestException as e:
        return {
            'success': False,
            'error': str(e),
            'status_code': 0
        }
    except Exception as e:
        return {
            'success': False,
            'error': f"Unexpected error: {str(e)}",
            'status_code': 0
        }

# ===== AUTHENTICATION TESTS =====

def test_user_signup():
    """Test user signup endpoint"""
    import time
    # Use timestamp to create unique email
    unique_email = f"john.doe.{int(time.time())}@mvpline.com"
    
    user_data = {
        "email": unique_email,
        "password": "securepass123",
        "name": "John Doe",
        "phone": "+15551234567",
        "mode": "rep"
    }
    
    result = make_request('POST', '/auth/signup', json=user_data)
    
    if not result['success']:
        log_test("User Signup", False, f"Request failed: {result.get('error')}")
        return False
    
    if result['status_code'] != 200:
        log_test("User Signup", False, f"Status: {result['status_code']}, Response: {result.get('data')}")
        return False
    
    # Check response structure
    data = result['data']
    if 'id' in data or '_id' in data:
        test_state['user_id'] = data.get('id') or data.get('_id')
        test_state['user_email'] = unique_email  # Store email for login
        log_test("User Signup", True, f"User created with ID: {test_state['user_id']}")
        return True
    else:
        log_test("User Signup", False, f"No user ID in response: {data}")
        return False

def test_user_login():
    """Test user login endpoint"""
    login_data = {
        "email": test_state.get('user_email', "john.doe@mvpline.com"),
        "password": "securepass123"
    }
    
    result = make_request('POST', '/auth/login', json=login_data)
    
    if not result['success']:
        log_test("User Login", False, f"Request failed: {result.get('error')}")
        return False
    
    if result['status_code'] != 200:
        log_test("User Login", False, f"Status: {result['status_code']}, Response: {result.get('data')}")
        return False
    
    data = result['data']
    if 'token' in data and 'user' in data:
        test_state['token'] = data['token']
        if not test_state['user_id']:
            test_state['user_id'] = data['user'].get('_id') or data['user'].get('id')
        log_test("User Login", True, f"Login successful, token received")
        return True
    else:
        log_test("User Login", False, f"Invalid login response: {data}")
        return False

# ===== ONBOARDING TESTS =====

def test_save_persona():
    """Test saving user persona"""
    if not test_state['user_id']:
        log_test("Save Persona", False, "No user_id available")
        return False
    
    persona_data = {
        "tone": "casual",
        "emoji_use": "moderate",
        "humor_level": "some",
        "brevity": "balanced",
        "professional_identity": "I'm straightforward and honest",
        "interests": ["sports", "cars"]
    }
    
    result = make_request('POST', f"/onboarding/profile/{test_state['user_id']}", json=persona_data)
    
    if not result['success']:
        log_test("Save Persona", False, f"Request failed: {result.get('error')}")
        return False
    
    if result['status_code'] != 200:
        log_test("Save Persona", False, f"Status: {result['status_code']}, Response: {result.get('data')}")
        return False
    
    log_test("Save Persona", True, "Persona saved successfully")
    return True

def test_get_persona():
    """Test retrieving user persona"""
    if not test_state['user_id']:
        log_test("Get Persona", False, "No user_id available")
        return False
    
    result = make_request('GET', f"/onboarding/profile/{test_state['user_id']}")
    
    if not result['success']:
        log_test("Get Persona", False, f"Request failed: {result.get('error')}")
        return False
    
    if result['status_code'] != 200:
        log_test("Get Persona", False, f"Status: {result['status_code']}, Response: {result.get('data')}")
        return False
    
    data = result['data']
    if 'tone' in data and 'interests' in data:
        log_test("Get Persona", True, f"Persona retrieved successfully")
        return True
    else:
        log_test("Get Persona", False, f"Invalid persona data: {data}")
        return False

# ===== CONTACT MANAGEMENT TESTS =====

def test_create_contacts():
    """Test creating contacts"""
    if not test_state['user_id']:
        log_test("Create Contacts", False, "No user_id available")
        return False
    
    contacts = [
        {
            "first_name": "Alice",
            "last_name": "Johnson",
            "phone": "+15559876543",
            "email": "alice@example.com",
            "tags": ["prospect", "car_buyer"],
            "notes": "Interested in SUV models"
        },
        {
            "first_name": "Bob",
            "last_name": "Smith",
            "phone": "+15558765432",
            "tags": ["customer"],
            "notes": "Previous buyer, good referral source"
        }
    ]
    
    success_count = 0
    for i, contact_data in enumerate(contacts):
        result = make_request('POST', f"/contacts/{test_state['user_id']}", json=contact_data)
        
        if result['success'] and result['status_code'] == 200:
            contact_id = result['data'].get('id') or result['data'].get('_id')
            if contact_id:
                test_state['contact_ids'].append(contact_id)
                success_count += 1
    
    if success_count == len(contacts):
        log_test("Create Contacts", True, f"Created {success_count} contacts")
        return True
    else:
        log_test("Create Contacts", False, f"Only created {success_count}/{len(contacts)} contacts")
        return False

def test_get_contacts():
    """Test retrieving contacts"""
    if not test_state['user_id']:
        log_test("Get Contacts", False, "No user_id available")
        return False
    
    result = make_request('GET', f"/contacts/{test_state['user_id']}")
    
    if not result['success']:
        log_test("Get Contacts", False, f"Request failed: {result.get('error')}")
        return False
    
    if result['status_code'] != 200:
        log_test("Get Contacts", False, f"Status: {result['status_code']}, Response: {result.get('data')}")
        return False
    
    contacts = result['data']
    if isinstance(contacts, list) and len(contacts) >= 2:
        log_test("Get Contacts", True, f"Retrieved {len(contacts)} contacts")
        return True
    else:
        log_test("Get Contacts", False, f"Expected list of contacts, got: {type(contacts)} with {len(contacts) if isinstance(contacts, list) else 0} items")
        return False

def test_import_contacts():
    """Test bulk contact import"""
    if not test_state['user_id']:
        log_test("Import Contacts", False, "No user_id available")
        return False
    
    import_data = [
        {
            "first_name": "Charlie",
            "last_name": "Wilson",
            "phone": "+15557654321",
            "tags": ["lead"]
        },
        {
            "first_name": "Diana",
            "last_name": "Brown",
            "phone": "+15556543210",
            "tags": ["prospect", "referral"]
        }
    ]
    
    result = make_request('POST', f"/contacts/{test_state['user_id']}/import", json=import_data)
    
    if not result['success']:
        log_test("Import Contacts", False, f"Request failed: {result.get('error')}")
        return False
    
    if result['status_code'] != 200:
        log_test("Import Contacts", False, f"Status: {result['status_code']}, Response: {result.get('data')}")
        return False
    
    data = result['data']
    if 'imported' in data and data['imported'] >= 2:
        log_test("Import Contacts", True, f"Imported {data['imported']} contacts")
        return True
    else:
        log_test("Import Contacts", False, f"Import failed: {data}")
        return False

def test_search_contacts():
    """Test contact search functionality"""
    if not test_state['user_id']:
        log_test("Search Contacts", False, "No user_id available")
        return False
    
    result = make_request('GET', f"/contacts/{test_state['user_id']}", params={'search': 'Alice'})
    
    if not result['success']:
        log_test("Search Contacts", False, f"Request failed: {result.get('error')}")
        return False
    
    if result['status_code'] != 200:
        log_test("Search Contacts", False, f"Status: {result['status_code']}, Response: {result.get('data')}")
        return False
    
    contacts = result['data']
    if isinstance(contacts, list):
        found_alice = any('alice' in contact.get('first_name', '').lower() for contact in contacts)
        if found_alice:
            log_test("Search Contacts", True, f"Search found {len(contacts)} matching contacts")
            return True
        else:
            log_test("Search Contacts", False, f"Search didn't find Alice in results: {contacts}")
            return False
    else:
        log_test("Search Contacts", False, f"Expected list, got: {type(contacts)}")
        return False

# ===== MESSAGING TESTS =====

def test_send_message():
    """Test sending a message"""
    if not test_state['user_id'] or not test_state['contact_ids']:
        log_test("Send Message", False, "Missing user_id or contact_ids")
        return False
    
    message_data = {
        "conversation_id": test_state['contact_ids'][0],  # Using contact_id as conversation_id
        "content": "Hi Alice! I wanted to follow up about the SUV you were interested in. Do you have time to chat today?",
        "media_url": None
    }
    
    result = make_request('POST', f"/messages/send/{test_state['user_id']}", json=message_data)
    
    if not result['success']:
        log_test("Send Message", False, f"Request failed: {result.get('error')}")
        return False
    
    if result['status_code'] != 200:
        log_test("Send Message", False, f"Status: {result['status_code']}, Response: {result.get('data')}")
        return False
    
    data = result['data']
    if 'message' in data and data['message'] == 'Message sent':
        log_test("Send Message", True, "Message sent successfully")
        return True
    else:
        log_test("Send Message", False, f"Unexpected response: {data}")
        return False

def test_get_conversations():
    """Test retrieving conversations"""
    if not test_state['user_id']:
        log_test("Get Conversations", False, "No user_id available")
        return False
    
    result = make_request('GET', f"/messages/conversations/{test_state['user_id']}")
    
    if not result['success']:
        log_test("Get Conversations", False, f"Request failed: {result.get('error')}")
        return False
    
    if result['status_code'] != 200:
        log_test("Get Conversations", False, f"Status: {result['status_code']}, Response: {result.get('data')}")
        return False
    
    conversations = result['data']
    if isinstance(conversations, list):
        if len(conversations) > 0:
            # Store first conversation ID for thread testing
            test_state['conversation_id'] = conversations[0].get('_id') or conversations[0].get('id')
        log_test("Get Conversations", True, f"Retrieved {len(conversations)} conversations")
        return True
    else:
        log_test("Get Conversations", False, f"Expected list, got: {type(conversations)}")
        return False

def test_get_message_thread():
    """Test retrieving message thread"""
    if not test_state['conversation_id']:
        log_test("Get Message Thread", False, "No conversation_id available")
        return False
    
    result = make_request('GET', f"/messages/thread/{test_state['conversation_id']}")
    
    if not result['success']:
        log_test("Get Message Thread", False, f"Request failed: {result.get('error')}")
        return False
    
    if result['status_code'] != 200:
        log_test("Get Message Thread", False, f"Status: {result['status_code']}, Response: {result.get('data')}")
        return False
    
    messages = result['data']
    if isinstance(messages, list):
        log_test("Get Message Thread", True, f"Retrieved {len(messages)} messages in thread")
        return True
    else:
        log_test("Get Message Thread", False, f"Expected list, got: {type(messages)}")
        return False

def test_ai_suggest_message():
    """Test AI message suggestion"""
    if not test_state['conversation_id']:
        log_test("AI Suggest Message", False, "No conversation_id available")
        return False
    
    result = make_request('POST', f"/messages/ai-suggest/{test_state['conversation_id']}")
    
    if not result['success']:
        log_test("AI Suggest Message", False, f"Request failed: {result.get('error')}")
        return False
    
    if result['status_code'] != 200:
        log_test("AI Suggest Message", False, f"Status: {result['status_code']}, Response: {result.get('data')}")
        return False
    
    data = result['data']
    if 'suggestion' in data and 'confidence' in data:
        log_test("AI Suggest Message", True, f"AI suggestion received: '{data['suggestion'][:50]}...'")
        return True
    else:
        log_test("AI Suggest Message", False, f"Invalid AI response: {data}")
        return False

# ===== CALL LOGGING TESTS =====

def test_create_call_logs():
    """Test creating call logs"""
    if not test_state['user_id'] or not test_state['contact_ids']:
        log_test("Create Call Logs", False, "Missing user_id or contact_ids")
        return False
    
    call_types = ["outbound", "inbound", "missed"]
    success_count = 0
    
    for call_type in call_types:
        call_data = {
            "contact_id": test_state['contact_ids'][0],
            "type": call_type,
            "duration": 120 if call_type != "missed" else 0
        }
        
        result = make_request('POST', f"/calls/{test_state['user_id']}", json=call_data)
        
        if result['success'] and result['status_code'] == 200:
            success_count += 1
            if call_type == "missed":
                test_state['call_id'] = result['data'].get('id') or result['data'].get('_id')
    
    if success_count == len(call_types):
        log_test("Create Call Logs", True, f"Created {success_count} call logs")
        return True
    else:
        log_test("Create Call Logs", False, f"Only created {success_count}/{len(call_types)} call logs")
        return False

def test_get_call_logs():
    """Test retrieving call logs"""
    if not test_state['user_id']:
        log_test("Get Call Logs", False, "No user_id available")
        return False
    
    result = make_request('GET', f"/calls/{test_state['user_id']}")
    
    if not result['success']:
        log_test("Get Call Logs", False, f"Request failed: {result.get('error')}")
        return False
    
    if result['status_code'] != 200:
        log_test("Get Call Logs", False, f"Status: {result['status_code']}, Response: {result.get('data')}")
        return False
    
    calls = result['data']
    if isinstance(calls, list) and len(calls) >= 3:
        log_test("Get Call Logs", True, f"Retrieved {len(calls)} call logs")
        return True
    else:
        log_test("Get Call Logs", False, f"Expected at least 3 calls, got: {len(calls) if isinstance(calls, list) else 0}")
        return False

def test_filter_call_logs():
    """Test filtering call logs by type"""
    if not test_state['user_id']:
        log_test("Filter Call Logs", False, "No user_id available")
        return False
    
    result = make_request('GET', f"/calls/{test_state['user_id']}", params={'call_type': 'missed'})
    
    if not result['success']:
        log_test("Filter Call Logs", False, f"Request failed: {result.get('error')}")
        return False
    
    if result['status_code'] != 200:
        log_test("Filter Call Logs", False, f"Status: {result['status_code']}, Response: {result.get('data')}")
        return False
    
    calls = result['data']
    if isinstance(calls, list):
        missed_calls = [call for call in calls if call.get('type') == 'missed']
        if len(missed_calls) >= 1:
            log_test("Filter Call Logs", True, f"Found {len(missed_calls)} missed calls")
            return True
        else:
            log_test("Filter Call Logs", False, f"No missed calls found in filtered results")
            return False
    else:
        log_test("Filter Call Logs", False, f"Expected list, got: {type(calls)}")
        return False

# ===== AI TESTS =====

def test_generate_ai_message():
    """Test AI message generation"""
    if not test_state['user_id']:
        log_test("Generate AI Message", False, "No user_id available")
        return False
    
    params = {
        "user_id": test_state['user_id'],
        "context": "Follow up with customer about car purchase",
        "intent": "follow_up"
    }
    
    result = make_request('POST', '/ai/generate-message', params=params)
    
    if not result['success']:
        log_test("Generate AI Message", False, f"Request failed: {result.get('error')}")
        return False
    
    if result['status_code'] != 200:
        log_test("Generate AI Message", False, f"Status: {result['status_code']}, Response: {result.get('data')}")
        return False
    
    data = result['data']
    if 'generated_message' in data and 'intent' in data:
        log_test("Generate AI Message", True, f"Generated message: '{data['generated_message'][:50]}...'")
        return True
    else:
        log_test("Generate AI Message", False, f"Invalid AI generation response: {data}")
        return False

def test_detect_intent():
    """Test AI intent detection"""
    test_data = {
        "message": "I want to buy a car and need to know the price"
    }
    
    result = make_request('POST', '/ai/detect-intent', json=test_data)
    
    if not result['success']:
        log_test("Detect Intent", False, f"Request failed: {result.get('error')}")
        return False
    
    if result['status_code'] != 200:
        log_test("Detect Intent", False, f"Status: {result['status_code']}, Response: {result.get('data')}")
        return False
    
    data = result['data']
    if 'intents' in data and isinstance(data['intents'], list):
        detected_intents = data['intents']
        expected_intents = ['buying_intent', 'price_question']
        found_expected = any(intent in detected_intents for intent in expected_intents)
        
        if found_expected:
            log_test("Detect Intent", True, f"Detected intents: {detected_intents}")
            return True
        else:
            log_test("Detect Intent", False, f"Expected buying/price intents, got: {detected_intents}")
            return False
    else:
        log_test("Detect Intent", False, f"Invalid intent detection response: {data}")
        return False

# ===== CAMPAIGN TESTS =====

def test_create_campaign():
    """Test creating a campaign"""
    if not test_state['user_id']:
        log_test("Create Campaign", False, "No user_id available")
        return False
    
    campaign_data = {
        "name": "SUV Buyers Follow-up",
        "segment_tags": ["prospect", "car_buyer"],
        "message_template": "Hi {first_name}! Just checking in about your SUV search. Any questions I can help with?",
        "schedule": {
            "frequency": "weekly",
            "day": "monday",
            "time": "09:00"
        }
    }
    
    result = make_request('POST', f"/campaigns/{test_state['user_id']}", json=campaign_data)
    
    if not result['success']:
        log_test("Create Campaign", False, f"Request failed: {result.get('error')}")
        return False
    
    if result['status_code'] != 200:
        log_test("Create Campaign", False, f"Status: {result['status_code']}, Response: {result.get('data')}")
        return False
    
    data = result['data']
    campaign_id = data.get('id') or data.get('_id')
    if campaign_id:
        test_state['campaign_id'] = campaign_id
        log_test("Create Campaign", True, f"Campaign created with ID: {campaign_id}")
        return True
    else:
        log_test("Create Campaign", False, f"No campaign ID in response: {data}")
        return False

def test_get_campaigns():
    """Test retrieving campaigns"""
    if not test_state['user_id']:
        log_test("Get Campaigns", False, "No user_id available")
        return False
    
    result = make_request('GET', f"/campaigns/{test_state['user_id']}")
    
    if not result['success']:
        log_test("Get Campaigns", False, f"Request failed: {result.get('error')}")
        return False
    
    if result['status_code'] != 200:
        log_test("Get Campaigns", False, f"Status: {result['status_code']}, Response: {result.get('data')}")
        return False
    
    campaigns = result['data']
    if isinstance(campaigns, list) and len(campaigns) >= 1:
        log_test("Get Campaigns", True, f"Retrieved {len(campaigns)} campaigns")
        return True
    else:
        log_test("Get Campaigns", False, f"Expected at least 1 campaign, got: {len(campaigns) if isinstance(campaigns, list) else 0}")
        return False

# ===== TASK TESTS =====

def test_create_task():
    """Test creating a task"""
    if not test_state['user_id'] or not test_state['contact_ids']:
        log_test("Create Task", False, "Missing user_id or contact_ids")
        return False
    
    task_data = {
        "contact_id": test_state['contact_ids'][0],
        "type": "follow_up",
        "title": "Follow up with Alice about SUV pricing",
        "description": "Alice showed interest in the new SUV models. Need to send pricing info and schedule test drive.",
        "due_date": (datetime.utcnow() + timedelta(days=2)).isoformat()
    }
    
    result = make_request('POST', f"/tasks/{test_state['user_id']}", json=task_data)
    
    if not result['success']:
        log_test("Create Task", False, f"Request failed: {result.get('error')}")
        return False
    
    if result['status_code'] != 200:
        log_test("Create Task", False, f"Status: {result['status_code']}, Response: {result.get('data')}")
        return False
    
    data = result['data']
    task_id = data.get('id') or data.get('_id')
    if task_id:
        test_state['task_id'] = task_id
        log_test("Create Task", True, f"Task created with ID: {task_id}")
        return True
    else:
        log_test("Create Task", False, f"No task ID in response: {data}")
        return False

def test_get_tasks():
    """Test retrieving tasks"""
    if not test_state['user_id']:
        log_test("Get Tasks", False, "No user_id available")
        return False
    
    result = make_request('GET', f"/tasks/{test_state['user_id']}")
    
    if not result['success']:
        log_test("Get Tasks", False, f"Request failed: {result.get('error')}")
        return False
    
    if result['status_code'] != 200:
        log_test("Get Tasks", False, f"Status: {result['status_code']}, Response: {result.get('data')}")
        return False
    
    tasks = result['data']
    if isinstance(tasks, list) and len(tasks) >= 1:
        log_test("Get Tasks", True, f"Retrieved {len(tasks)} tasks")
        return True
    else:
        log_test("Get Tasks", False, f"Expected at least 1 task, got: {len(tasks) if isinstance(tasks, list) else 0}")
        return False

# ===== UTILITY TESTS =====

def test_api_root():
    """Test API root endpoint"""
    result = make_request('GET', '/')
    
    if not result['success']:
        log_test("API Root", False, f"Request failed: {result.get('error')}")
        return False
    
    if result['status_code'] != 200:
        log_test("API Root", False, f"Status: {result['status_code']}, Response: {result.get('data')}")
        return False
    
    data = result['data']
    if 'message' in data and 'MVPLine' in data['message']:
        log_test("API Root", True, f"API responding: {data['message']}")
        return True
    else:
        log_test("API Root", False, f"Unexpected root response: {data}")
        return False

def test_get_user():
    """Test get user profile"""
    if not test_state['user_id']:
        log_test("Get User Profile", False, "No user_id available")
        return False
    
    result = make_request('GET', f"/user/{test_state['user_id']}")
    
    if not result['success']:
        log_test("Get User Profile", False, f"Request failed: {result.get('error')}")
        return False
    
    if result['status_code'] != 200:
        log_test("Get User Profile", False, f"Status: {result['status_code']}, Response: {result.get('data')}")
        return False
    
    data = result['data']
    if 'name' in data and 'email' in data:
        log_test("Get User Profile", True, f"User profile retrieved for: {data['name']}")
        return True
    else:
        log_test("Get User Profile", False, f"Invalid user profile response: {data}")
        return False

# ===== MAIN TEST RUNNER =====

def run_all_tests():
    """Run all backend API tests"""
    print("=" * 60)
    print("MVPLine Backend API Test Suite")
    print("=" * 60)
    print(f"Testing against: {BASE_URL}")
    print("=" * 60)
    
    # Test order matters due to dependencies
    test_functions = [
        # Basic connectivity
        test_api_root,
        
        # Authentication (required for everything else)
        test_user_signup,
        test_user_login,
        test_get_user,
        
        # Onboarding
        test_save_persona,
        test_get_persona,
        
        # Contact management (required for messaging/calls)
        test_create_contacts,
        test_get_contacts,
        test_import_contacts,
        test_search_contacts,
        
        # Messaging & conversations
        test_send_message,
        test_get_conversations,
        test_get_message_thread,
        test_ai_suggest_message,
        
        # Call logging
        test_create_call_logs,
        test_get_call_logs,
        test_filter_call_logs,
        
        # AI features
        test_generate_ai_message,
        test_detect_intent,
        
        # Campaign management
        test_create_campaign,
        test_get_campaigns,
        
        # Task management
        test_create_task,
        test_get_tasks,
    ]
    
    print(f"\nRunning {len(test_functions)} tests...\n")
    
    for test_func in test_functions:
        try:
            test_func()
        except Exception as e:
            test_name = test_func.__name__.replace('test_', '').replace('_', ' ').title()
            log_test(test_name, False, f"Test error: {str(e)}")
            test_results['errors'].append({'test': test_name, 'error': str(e)})
        print()  # Empty line for readability
    
    # Print summary
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    total_tests = len(test_results['passed']) + len(test_results['failed']) + len(test_results['errors'])
    passed_count = len(test_results['passed'])
    failed_count = len(test_results['failed'])
    error_count = len(test_results['errors'])
    
    print(f"Total Tests: {total_tests}")
    print(f"✅ Passed: {passed_count}")
    print(f"❌ Failed: {failed_count}")
    print(f"🚨 Errors: {error_count}")
    print(f"Success Rate: {(passed_count/total_tests)*100:.1f}%")
    
    if test_results['failed']:
        print("\n❌ FAILED TESTS:")
        for failure in test_results['failed']:
            print(f"   • {failure['test']}: {failure['details']}")
    
    if test_results['errors']:
        print("\n🚨 ERROR TESTS:")
        for error in test_results['errors']:
            print(f"   • {error['test']}: {error['error']}")
    
    print("\n" + "=" * 60)
    
    # Return results for programmatic use
    return {
        'total': total_tests,
        'passed': passed_count,
        'failed': failed_count,
        'errors': error_count,
        'success_rate': (passed_count/total_tests)*100 if total_tests > 0 else 0,
        'details': test_results
    }

if __name__ == "__main__":
    run_all_tests()