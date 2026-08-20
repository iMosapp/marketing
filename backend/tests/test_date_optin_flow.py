import asyncio, os, sys
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
load_dotenv('/app/backend/.env')
sys.path.insert(0, '/app/backend')

from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

async def main():
    client = AsyncIOMotorClient(os.environ['MONGO_URL'])
    db = client[os.environ['DB_NAME']]
    import routers.database as dbmod
    dbmod.db = db

    forest = await db.users.find_one({'email': 'forest@imosapp.com'})
    uid = str(forest['_id'])
    now = datetime.utcnow()

    # cleanup from previous runs
    await db.contacts.delete_many({'last_name': 'OptinTest'})
    await db.campaign_enrollments.delete_many({'contact_name': {'$regex': 'OptinTest'}})
    await db.campaign_pending_sends.delete_many({'contact_name': {'$regex': 'OptinTest'}})
    await db.date_send_guard.delete_many({})
    await db.tasks.delete_many({'title': {'$regex': 'OptinTest'}})
    await db.date_trigger_log.delete_many({'contact_name': {'$regex': 'OptinTest'}})

    # forest's active birthday campaign?
    bday_camp = await db.campaigns.find_one({'user_id': uid, 'active': True, '$or': [{'type': 'birthday'}, {'date_type': 'birthday'}]})
    print('forest birthday campaign:', bday_camp['name'] if bday_camp else 'NONE — creating one')
    if not bday_camp:
        r = await db.campaigns.insert_one({'user_id': uid, 'name': 'Birthday Test', 'type': 'birthday', 'trigger_tag': 'Birthday', 'active': True, 'delivery_mode': 'manual', 'ai_enabled': False, 'sequences': [{'message_template': 'Happy birthday {first_name}!', 'delay_days': 0}], 'created_at': now})

    # TEST 1: create contact with birthday TODAY via raw insert simulating API create logic isn't enough —
    # call the actual API endpoint
    import requests
    API = os.environ.get('TEST_API', 'http://localhost:8001')
    login = requests.post(f'{API}/api/auth/login', json={'email': 'forest@imosapp.com', 'password': 'Admin123!'}).json()
    tok = {'Authorization': f"Bearer {login['token']}"}
    bday_this_year = now.replace(year=1990).isoformat()
    r = requests.post(f'{API}/api/contacts/{uid}', json={
        'first_name': 'Alice', 'last_name': 'OptinTest', 'phone': '+15557770001',
        'birthday': bday_this_year,
    }, headers=tok)
    alice_id = r.json().get('_id') or r.json().get('id')
    alice = await db.contacts.find_one({'_id': ObjectId(alice_id)})
    tags = alice.get('tags', [])
    enr = await db.campaign_enrollments.count_documents({'contact_id': alice_id})
    pend = await db.campaign_pending_sends.count_documents({'contact_id': alice_id})
    print(f"TEST1 save-birthday: auto-tag applied={'Birthday' in tags} (want False), enrollments={enr} (want 0), pending_sends={pend} (want 0)")

    # TEST 2: bulk opt-in
    r = requests.post(f'{API}/api/contacts/{uid}/date-optins/bulk', json={'contact_ids': [alice_id], 'occasion': 'birthday', 'enable': True}, headers=tok)
    print('TEST2 bulk opt-in:', r.json())
    alice = await db.contacts.find_one({'_id': ObjectId(alice_id)})
    print('  tags now:', alice.get('tags'))
    # bulk opt-in must NOT create enrollments
    enr = await db.campaign_enrollments.count_documents({'contact_id': alice_id})
    print(f"  enrollments after tag applied={enr} (want 0 — tag application never fires)")

    # TEST 3: second contact, birthday today, NOT opted in
    r = requests.post(f'{API}/api/contacts/{uid}', json={
        'first_name': 'Bob', 'last_name': 'OptinTest', 'phone': '+15557770002',
        'birthday': now.replace(year=1985).isoformat(),
    }, headers=tok)
    bob_id = r.json().get('_id') or r.json().get('id')

    # TEST 4: run the day-of sweep
    from scheduler import _enroll_date_campaigns_for_user, _run_date_triggers_for_user
    n1 = await _enroll_date_campaigns_for_user(db, uid)
    alice_enr = await db.campaign_enrollments.count_documents({'contact_id': alice_id, 'status': 'active'})
    bob_enr = await db.campaign_enrollments.count_documents({'contact_id': bob_id})
    alice_pend = await db.campaign_pending_sends.count_documents({'contact_id': alice_id, 'status': 'pending'})
    print(f"TEST4 day-of sweep: enrolled={n1}, alice_enrollments={alice_enr} (want 1), alice_pending={alice_pend} (want >=1), bob_enrollments={bob_enr} (want 0)")

    # TEST 5: run sweep AGAIN — guard must prevent doubles
    n2 = await _enroll_date_campaigns_for_user(db, uid)
    alice_enr2 = await db.campaign_enrollments.count_documents({'contact_id': alice_id, 'status': 'active'})
    print(f"TEST5 re-run guard: enrolled={n2} (want 0), alice_enrollments={alice_enr2} (want still 1)")

    # TEST 6: sold-date anniversary — contact sold 2 yrs ago today, Anniversary tag, date-trigger config
    r = requests.post(f'{API}/api/contacts/{uid}', json={
        'first_name': 'Cara', 'last_name': 'OptinTest', 'phone': '+15557770003',
        'date_sold': now.replace(year=now.year - 2).isoformat(), 'vehicle': '2024 Chevy Tahoe',
    }, headers=tok)
    cara_id = r.json().get('_id') or r.json().get('id')
    requests.post(f'{API}/api/contacts/{uid}/date-optins/bulk', json={'contact_ids': [cara_id], 'occasion': 'anniversary', 'enable': True}, headers=tok)
    # ensure sold_date config has a template
    await db.date_trigger_configs.update_one(
        {'user_id': uid, 'trigger_type': 'sold_date'},
        {'$set': {'enabled': True, 'delivery_method': 'sms', 'message_template': 'Hey {first_name}, {years} years since your purchase — hope you love it!'}},
        upsert=True)
    sent = await _run_date_triggers_for_user(db, uid)
    task = await db.tasks.find_one({'contact_id': cara_id, 'source': 'date_trigger'})
    log = await db.date_trigger_log.find_one({'contact_id': cara_id})
    print(f"TEST6 sold anniversary: tasks_created={task is not None} (want True)")
    if task:
        d = task.get('description', '')
        print(f"  years resolved: {'2 years' in d}, card link included: {'anniversary card' in d.lower()}")
        print('  msg:', d[:160].replace(chr(10), ' | '))

    # TEST 7: untagged contact with sold date today-2yrs gets NOTHING
    r = requests.post(f'{API}/api/contacts/{uid}', json={
        'first_name': 'Dan', 'last_name': 'OptinTest', 'phone': '+15557770004',
        'date_sold': now.replace(year=now.year - 3).isoformat(),
    }, headers=tok)
    dan_id = r.json().get('_id') or r.json().get('id')
    await _run_date_triggers_for_user(db, uid)
    dan_task = await db.tasks.find_one({'contact_id': dan_id, 'source': 'date_trigger'})
    print(f"TEST7 untagged sold-anniv: task_created={dan_task is not None} (want False)")

    # cleanup
    for cid in [alice_id, bob_id, cara_id, dan_id]:
        if cid:
            await db.contacts.delete_one({'_id': ObjectId(cid)})
    await db.campaign_enrollments.delete_many({'contact_name': {'$regex': 'OptinTest'}})
    await db.campaign_pending_sends.delete_many({'contact_name': {'$regex': 'OptinTest'}})
    await db.tasks.delete_many({'contact_id': {'$in': [alice_id, bob_id, cara_id, dan_id]}})
    await db.date_trigger_log.delete_many({'contact_id': {'$in': [alice_id, bob_id, cara_id, dan_id]}})
    await db.date_send_guard.delete_many({})
    await db.campaigns.delete_many({'name': 'Birthday Test'})
    print('cleanup done')

asyncio.run(main())
