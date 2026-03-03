"""
i'M On Social Demo Data Seeder
Populates the database with realistic demo data for testing all features.
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta
import os
import random
from bson import ObjectId

# Demo data
DEMO_CONTACTS = [
    {"first_name": "Sarah", "last_name": "Mitchell", "phone": "+18015551001", "email": "sarah.mitchell@gmail.com", "notes": "Looking for a family SUV. Has 2 kids. Budget around $45k.", "tags": ["hot_lead", "suv"], "vehicle": "2024 Honda Pilot"},
    {"first_name": "James", "last_name": "Rodriguez", "phone": "+18015551002", "email": "jrodriguez@outlook.com", "notes": "Interested in trucks. Works in construction.", "tags": ["prospect", "truck"], "vehicle": None},
    {"first_name": "Emily", "last_name": "Chen", "phone": "+18015551003", "email": "emily.chen@yahoo.com", "notes": "First-time buyer. Needs financing help.", "tags": ["new_buyer", "financing"], "vehicle": None},
    {"first_name": "Michael", "last_name": "Thompson", "phone": "+18015551004", "email": "mthompson@gmail.com", "notes": "Trading in 2019 Accord. Wants hybrid.", "tags": ["trade_in", "hybrid"], "vehicle": "2019 Honda Accord"},
    {"first_name": "Jessica", "last_name": "Williams", "phone": "+18015551005", "email": "jwilliams@icloud.com", "notes": "Referred by Sarah Mitchell. Looking for compact SUV.", "tags": ["referral", "suv"], "vehicle": None},
    {"first_name": "David", "last_name": "Kim", "phone": "+18015551006", "email": "david.kim@gmail.com", "notes": "Business owner. Interested in fleet pricing.", "tags": ["fleet", "business"], "vehicle": None},
    {"first_name": "Amanda", "last_name": "Brown", "phone": "+18015551007", "email": "amanda.b@hotmail.com", "notes": "Previous customer. Bought Civic in 2022. Ready for upgrade.", "tags": ["repeat_customer", "loyalty"], "vehicle": "2022 Honda Civic"},
    {"first_name": "Robert", "last_name": "Garcia", "phone": "+18015551008", "email": "rgarcia@gmail.com", "notes": "Comparing with Toyota. Need competitive pricing.", "tags": ["comparison", "negotiating"], "vehicle": None},
    {"first_name": "Lisa", "last_name": "Martinez", "phone": "+18015551009", "email": "lisa.martinez@gmail.com", "notes": "Needs car for college student. Budget conscious.", "tags": ["budget", "student"], "vehicle": None},
    {"first_name": "Chris", "last_name": "Anderson", "phone": "+18015551010", "email": "canderson@yahoo.com", "notes": "Looking for electric/hybrid options.", "tags": ["ev", "eco_friendly"], "vehicle": None},
    {"first_name": "Rachel", "last_name": "Taylor", "phone": "+18015551011", "email": "rachel.t@gmail.com", "notes": "Wants test drive this weekend.", "tags": ["hot_lead", "test_drive"], "vehicle": None},
    {"first_name": "Kevin", "last_name": "Lee", "phone": "+18015551012", "email": "kevin.lee@outlook.com", "notes": "Relocating from CA. Needs vehicle ASAP.", "tags": ["urgent", "relocation"], "vehicle": None},
]

DEMO_CONVERSATIONS = [
    {
        "contact_idx": 0,  # Sarah Mitchell
        "status": "active",
        "unread": True,
        "unread_count": 2,
        "ai_handled": True,
        "ai_outcome": "appointment_set",
        "ai_outcome_priority": 1,
        "ai_outcome_acknowledged": False,
        "messages": [
            {"sender": "contact", "content": "Hi, I saw your ad for the Honda Pilot. Is it still available?", "hours_ago": 5},
            {"sender": "ai", "content": "Hi Sarah! Yes, we have several 2024 Honda Pilots in stock. Would you like to come in for a test drive? I have availability tomorrow at 2pm or Saturday morning.", "hours_ago": 4.5},
            {"sender": "contact", "content": "Saturday at 10am works great!", "hours_ago": 3},
            {"sender": "ai", "content": "Perfect! I've scheduled you for Saturday at 10am. I'll send a reminder the day before. Looking forward to meeting you!", "hours_ago": 2.5},
        ]
    },
    {
        "contact_idx": 1,  # James Rodriguez
        "status": "active",
        "unread": True,
        "unread_count": 1,
        "ai_handled": True,
        "ai_outcome": "callback_requested",
        "ai_outcome_priority": 2,
        "ai_outcome_acknowledged": False,
        "messages": [
            {"sender": "contact", "content": "What trucks do you have under 50k?", "hours_ago": 8},
            {"sender": "ai", "content": "Hi James! We have great options under $50k including the Honda Ridgeline. Would you like me to send you some details?", "hours_ago": 7.5},
            {"sender": "contact", "content": "Yeah send me info. Also can someone call me tomorrow to discuss financing?", "hours_ago": 2},
        ]
    },
    {
        "contact_idx": 2,  # Emily Chen
        "status": "active",
        "unread": False,
        "unread_count": 0,
        "ai_handled": True,
        "ai_outcome": "question_asked",
        "ai_outcome_priority": 4,
        "ai_outcome_acknowledged": False,
        "messages": [
            {"sender": "contact", "content": "What credit score do I need to get approved?", "hours_ago": 24},
            {"sender": "ai", "content": "Hi Emily! We work with multiple lenders and can help with various credit situations. Would you like to come in for a free credit consultation?", "hours_ago": 23},
            {"sender": "contact", "content": "What documents do I need to bring?", "hours_ago": 12},
        ]
    },
    {
        "contact_idx": 3,  # Michael Thompson
        "status": "active",
        "unread": True,
        "unread_count": 1,
        "ai_handled": True,
        "ai_outcome": "hot_lead",
        "ai_outcome_priority": 2,
        "ai_outcome_acknowledged": False,
        "messages": [
            {"sender": "contact", "content": "How much would you give me for my 2019 Accord trade-in?", "hours_ago": 6},
            {"sender": "ai", "content": "Hi Michael! We'd love to appraise your Accord. Based on current market values, 2019 Accords in good condition are trading around $18-22k. Can you tell me the mileage and condition?", "hours_ago": 5.5},
            {"sender": "contact", "content": "72k miles, excellent condition. I'm ready to buy today if the numbers work.", "hours_ago": 1},
        ]
    },
    {
        "contact_idx": 4,  # Jessica Williams
        "status": "active",
        "unread": False,
        "unread_count": 0,
        "ai_handled": False,
        "ai_outcome": None,
        "messages": [
            {"sender": "contact", "content": "Sarah Mitchell referred me. Looking for a CR-V.", "hours_ago": 48},
            {"sender": "user", "content": "Hi Jessica! Thanks for reaching out - Sarah is great! We have several CR-Vs available. What color and features are you looking for?", "hours_ago": 47},
        ]
    },
    {
        "contact_idx": 5,  # David Kim
        "status": "active",
        "unread": True,
        "unread_count": 3,
        "ai_handled": True,
        "ai_outcome": "needs_assistance",
        "ai_outcome_priority": 3,
        "ai_outcome_acknowledged": False,
        "messages": [
            {"sender": "contact", "content": "I need to buy 5 vehicles for my company. Do you offer fleet discounts?", "hours_ago": 10},
            {"sender": "ai", "content": "Hi David! Yes, we absolutely offer fleet pricing. For 5+ vehicles, we can provide significant discounts. Let me connect you with our fleet manager.", "hours_ago": 9.5},
            {"sender": "contact", "content": "I need them within 2 weeks. Is that possible?", "hours_ago": 4},
            {"sender": "contact", "content": "Also need commercial insurance quote", "hours_ago": 3},
            {"sender": "contact", "content": "Hello? Anyone there?", "hours_ago": 1},
        ]
    },
    {
        "contact_idx": 6,  # Amanda Brown
        "status": "closed",
        "unread": False,
        "unread_count": 0,
        "ai_handled": False,
        "ai_outcome": None,
        "messages": [
            {"sender": "contact", "content": "Thanks for the great service! Love my new Accord!", "hours_ago": 72},
            {"sender": "user", "content": "So glad you love it Amanda! Don't forget to leave us a review if you have a moment. Enjoy your new car! 🎉", "hours_ago": 71},
        ]
    },
    {
        "contact_idx": 10,  # Rachel Taylor
        "status": "active",
        "unread": True,
        "unread_count": 1,
        "ai_handled": True,
        "ai_outcome": "appointment_set",
        "ai_outcome_priority": 1,
        "ai_outcome_acknowledged": True,  # Already acknowledged
        "messages": [
            {"sender": "contact", "content": "Can I test drive the new Civic this Saturday?", "hours_ago": 26},
            {"sender": "ai", "content": "Hi Rachel! Absolutely! I have openings at 11am and 3pm on Saturday. Which works better?", "hours_ago": 25},
            {"sender": "contact", "content": "3pm please", "hours_ago": 24},
            {"sender": "ai", "content": "You're all set for Saturday at 3pm! See you then!", "hours_ago": 23.5},
            {"sender": "contact", "content": "Can I bring my husband too?", "hours_ago": 1},
        ]
    },
]

DEMO_CAMPAIGNS = [
    {
        "name": "Birthday Special",
        "type": "birthday",
        "segment_tags": ["repeat_customer"],
        "message_template": "Happy Birthday {first_name}! 🎂 As a valued customer, enjoy $500 off your next service visit. Valid this month only!",
        "active": True,
        "messages_sent": 23,
    },
    {
        "name": "Service Reminder",
        "type": "check_in",
        "segment_tags": ["loyalty"],
        "message_template": "Hi {first_name}! It's been 6 months since your last service. Schedule your maintenance today and get 10% off!",
        "active": True,
        "messages_sent": 156,
    },
    {
        "name": "Hot Lead Follow-up",
        "type": "check_in",
        "segment_tags": ["hot_lead"],
        "message_template": "Hi {first_name}! Just following up on your recent inquiry. Ready to take the next step? I'm here to help!",
        "active": True,
        "messages_sent": 45,
    },
    {
        "name": "Trade-In Promo",
        "type": "custom",
        "segment_tags": ["trade_in"],
        "message_template": "Hi {first_name}! We're offering top dollar for trade-ins this month. Get a free appraisal today!",
        "active": False,
        "messages_sent": 89,
    },
]

DEMO_TASKS = [
    {"title": "Call Sarah Mitchell", "description": "Confirm Saturday test drive appointment", "type": "call", "priority": "high", "days_until_due": 1, "completed": False, "contact_idx": 0},
    {"title": "Send James truck specs", "description": "Email Ridgeline brochure and pricing", "type": "follow_up", "priority": "high", "days_until_due": 0, "completed": False, "contact_idx": 1},
    {"title": "Process David's fleet quote", "description": "5 vehicle fleet pricing for Kim Construction", "type": "task", "priority": "high", "days_until_due": 0, "completed": False, "contact_idx": 5},
    {"title": "Follow up with Emily", "description": "Check if she scheduled credit consultation", "type": "follow_up", "priority": "medium", "days_until_due": 2, "completed": False, "contact_idx": 2},
    {"title": "Send Michael trade-in offer", "description": "Formal offer for 2019 Accord trade", "type": "follow_up", "priority": "high", "days_until_due": 0, "completed": False, "contact_idx": 3},
    {"title": "Thank Amanda for review", "description": "She left a 5-star Google review", "type": "follow_up", "priority": "low", "days_until_due": 3, "completed": False, "contact_idx": 6},
    {"title": "Update RMS notes", "description": "Weekly contact note updates", "type": "task", "priority": "low", "days_until_due": 5, "completed": True, "contact_idx": None},
    {"title": "Call Rachel about Civic", "description": "Confirm she can bring husband to test drive", "type": "call", "priority": "medium", "days_until_due": -1, "completed": True, "contact_idx": 10},
]

DEMO_TAGS = [
    {"name": "Hot Lead", "color": "#FF3B30", "icon": "flame"},
    {"name": "SUV Buyer", "color": "#007AFF", "icon": "car"},
    {"name": "Financing", "color": "#34C759", "icon": "card"},
    {"name": "Trade-In", "color": "#FF9500", "icon": "swap-horizontal"},
    {"name": "Referral", "color": "#AF52DE", "icon": "people"},
    {"name": "VIP", "color": "#D4AF37", "icon": "star"},
    {"name": "Fleet", "color": "#5856D6", "icon": "business"},
    {"name": "Test Drive", "color": "#30D158", "icon": "speedometer"},
]


async def seed_data():
    client = AsyncIOMotorClient(os.environ.get('MONGO_URL'))
    db = client['mvpline_db']
    
    # Get superadmin user
    superadmin = await db.users.find_one({"email": "superadmin@mvpline.com"})
    if not superadmin:
        print("Superadmin not found! Creating...")
        superadmin = {
            "_id": ObjectId(),
            "email": "superadmin@mvpline.com",
            "name": "Super Admin",
            "password": "admin123",
            "role": "super_admin",
            "mode": "rep",
            "phone": "+18015550000",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        await db.users.insert_one(superadmin)
    
    user_id = str(superadmin["_id"])
    print(f"Seeding data for user: {superadmin.get('name', superadmin['email'])} ({user_id})")
    
    # Clear existing data for this user
    await db.contacts.delete_many({"user_id": user_id})
    await db.conversations.delete_many({"user_id": user_id})
    await db.messages.delete_many({"user_id": user_id})
    await db.campaigns.delete_many({"user_id": user_id})
    await db.tasks.delete_many({"user_id": user_id})
    await db.tags.delete_many({"user_id": user_id})
    print("Cleared existing data")
    
    # Create tags
    tag_ids = {}
    for tag_data in DEMO_TAGS:
        tag = {
            "_id": ObjectId(),
            "user_id": user_id,
            "name": tag_data["name"],
            "color": tag_data["color"],
            "icon": tag_data["icon"],
            "contact_count": 0,
            "created_at": datetime.utcnow(),
        }
        await db.tags.insert_one(tag)
        tag_ids[tag_data["name"].lower().replace(" ", "_")] = str(tag["_id"])
    print(f"Created {len(DEMO_TAGS)} tags")
    
    # Create contacts
    contact_ids = []
    for contact_data in DEMO_CONTACTS:
        contact = {
            "_id": ObjectId(),
            "user_id": user_id,
            "first_name": contact_data["first_name"],
            "last_name": contact_data["last_name"],
            "phone": contact_data["phone"],
            "email": contact_data["email"],
            "notes": contact_data["notes"],
            "tags": contact_data["tags"],
            "vehicle": contact_data.get("vehicle"),
            "source": random.choice(["website", "referral", "walk_in", "phone"]),
            "created_at": datetime.utcnow() - timedelta(days=random.randint(1, 30)),
            "updated_at": datetime.utcnow(),
        }
        await db.contacts.insert_one(contact)
        contact_ids.append(contact)
    print(f"Created {len(DEMO_CONTACTS)} contacts")
    
    # Create conversations with messages
    for conv_data in DEMO_CONVERSATIONS:
        contact = contact_ids[conv_data["contact_idx"]]
        contact_name = f"{contact['first_name']} {contact['last_name']}"
        
        conversation = {
            "_id": ObjectId(),
            "user_id": user_id,
            "contact_id": str(contact["_id"]),
            "contact": {
                "name": contact_name,
                "phone": contact["phone"],
            },
            "status": conv_data["status"],
            "unread": conv_data["unread"],
            "unread_count": conv_data["unread_count"],
            "ai_enabled": True,
            "ai_mode": "auto_reply",
            "ai_handled": conv_data["ai_handled"],
            "ai_outcome": conv_data["ai_outcome"],
            "ai_outcome_priority": conv_data.get("ai_outcome_priority"),
            "ai_outcome_acknowledged": conv_data.get("ai_outcome_acknowledged", False),
            "created_at": datetime.utcnow() - timedelta(days=3),
            "updated_at": datetime.utcnow(),
        }
        
        # Add messages
        last_message = None
        for msg_data in conv_data["messages"]:
            message = {
                "_id": ObjectId(),
                "conversation_id": str(conversation["_id"]),
                "user_id": user_id,
                "sender": msg_data["sender"],
                "content": msg_data["content"],
                "timestamp": datetime.utcnow() - timedelta(hours=msg_data["hours_ago"]),
                "read": msg_data["sender"] != "contact" or not conv_data["unread"],
            }
            await db.messages.insert_one(message)
            last_message = message
        
        if last_message:
            conversation["last_message"] = {
                "content": last_message["content"],
                "sender": last_message["sender"],
                "timestamp": last_message["timestamp"],
            }
            conversation["last_message_at"] = last_message["timestamp"]
        
        await db.conversations.insert_one(conversation)
    print(f"Created {len(DEMO_CONVERSATIONS)} conversations with messages")
    
    # Create campaigns
    for camp_data in DEMO_CAMPAIGNS:
        campaign = {
            "_id": ObjectId(),
            "user_id": user_id,
            "name": camp_data["name"],
            "type": camp_data["type"],
            "segment_tags": camp_data["segment_tags"],
            "message_template": camp_data["message_template"],
            "active": camp_data["active"],
            "messages_sent": camp_data["messages_sent"],
            "schedule": {"frequency": "daily", "time": "09:00"},
            "created_at": datetime.utcnow() - timedelta(days=random.randint(7, 30)),
            "updated_at": datetime.utcnow(),
        }
        await db.campaigns.insert_one(campaign)
    print(f"Created {len(DEMO_CAMPAIGNS)} campaigns")
    
    # Create tasks with contact links
    for task_data in DEMO_TASKS:
        contact_idx = task_data.get("contact_idx")
        contact_ref = None
        contact_id = None
        
        if contact_idx is not None and contact_idx < len(contact_ids):
            contact = contact_ids[contact_idx]
            contact_id = str(contact["_id"])
            contact_ref = {
                "_id": contact_id,
                "name": f"{contact['first_name']} {contact['last_name'] or ''}".strip(),
                "phone": contact["phone"],
            }
        
        task = {
            "_id": ObjectId(),
            "user_id": user_id,
            "title": task_data["title"],
            "description": task_data["description"],
            "type": task_data["type"],
            "priority": task_data["priority"],
            "due_date": datetime.utcnow() + timedelta(days=task_data["days_until_due"]),
            "completed": task_data["completed"],
            "contact_id": contact_id,
            "contact": contact_ref,
            "created_at": datetime.utcnow() - timedelta(days=random.randint(1, 7)),
            "updated_at": datetime.utcnow(),
        }
        await db.tasks.insert_one(task)
    print(f"Created {len(DEMO_TASKS)} tasks")
    
    # Create activity feed entries
    activities = [
        {"type": "contact_added", "description": "Added new contact: Sarah Mitchell", "hours_ago": 5},
        {"type": "message_sent", "description": "Sent message to James Rodriguez", "hours_ago": 8},
        {"type": "deal_closed", "description": "Closed deal with Amanda Brown - 2024 Accord", "hours_ago": 72},
        {"type": "campaign_started", "description": "Started 'Hot Lead Follow-up' campaign", "hours_ago": 24},
        {"type": "appointment_set", "description": "Appointment scheduled with Rachel Taylor", "hours_ago": 23},
        {"type": "contact_added", "description": "Added new contact: David Kim (Fleet)", "hours_ago": 10},
    ]
    
    for activity in activities:
        act = {
            "_id": ObjectId(),
            "user_id": user_id,
            "user_name": superadmin.get("name", "Super Admin"),
            "type": activity["type"],
            "description": activity["description"],
            "created_at": datetime.utcnow() - timedelta(hours=activity["hours_ago"]),
        }
        await db.activity.insert_one(act)
    print(f"Created {len(activities)} activity entries")
    
    print("\n✅ Demo data seeded successfully!")
    print(f"   - {len(DEMO_CONTACTS)} contacts")
    print(f"   - {len(DEMO_CONVERSATIONS)} conversations")
    print(f"   - {len(DEMO_CAMPAIGNS)} campaigns")
    print(f"   - {len(DEMO_TASKS)} tasks")
    print(f"   - {len(DEMO_TAGS)} tags")
    print(f"\nLogin as: superadmin@mvpline.com / admin123")


if __name__ == "__main__":
    asyncio.run(seed_data())
