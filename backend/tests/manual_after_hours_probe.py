"""Manual probe: after-hours + texting-window deferrals, stagger, morning release. Preview only, 500-555 numbers."""
import os, asyncio, json, urllib.request
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

API = 'http://localhost:8001'
TOK = open('/tmp/tok').read().strip()
SRC = ObjectId('69a787ca70ae63ea0ac69251')
STORE = ObjectId('69a0b7095fddcede09591668')


def api(method, path, body=None):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body else None, method=method,
                                 headers={'Authorization': 'Bearer ' + TOK, 'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req).read())


def test_lead(phone, ladder=True):
    r = api('POST', f'/api/lead-sources/{SRC}/test-lead', {'phone': phone, 'first_name': 'Night', 'last_name': 'Owl', 'include_ladder': ladder})
    p = r['plan']
    print(f"  conv={r['conversation_id']} intake_deferred={p['intake_deferred']} intake_at={p['intake_at'][:16]} ladder_deferred={p['ladder_deferred']} ladder_at={(p['ladder_at'] or '')[:16]} reasons={p['ladder_reasons']} jessi={p['jessi_on']} after_hours={p['after_hours']}")
    return r


async def main():
    db = AsyncIOMotorClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]
    src0 = await db.lead_sources.find_one({'_id': SRC}, {'text_window_start': 1, 'text_window_end': 1, 'after_hours_mode': 1})
    store0 = await db.stores.find_one({'_id': STORE}, {'business_hours': 1})
    try:
        print("A) window closed, store open -> intake + ladder wait for 9 AM, staggered")
        await db.lead_sources.update_one({'_id': SRC}, {'$set': {'text_window_end': '12:00'}})
        a1 = test_lead('5005550171'); a2 = test_lead('5005550172')
        await asyncio.sleep(1)
        acts = await db.lead_deferred_actions.find({'conversation_id': {'$in': [a1['conversation_id'], a2['conversation_id']]}}).to_list(5)
        print('  deferred actions:', [(a['status'], a['run_at'].strftime('%H:%M')) for a in acts])
        jobs = await db.lead_call_jobs.find({'conversation_id': {'$in': [a1['conversation_id'], a2['conversation_id']]}}).to_list(5)
        print('  jobs:', [(j['status'], j['deferred'], j['next_attempt_at'].strftime('%H:%M'), j['deferred_reasons']) for j in jobs])
        await db.lead_sources.update_one({'_id': SRC}, {'$set': {'text_window_end': src0.get('text_window_end', '20:00')}})

        print("B) store closed, window open -> intake now, Jessi on, ladder at opening")
        bh = dict(store0['business_hours']); today = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'][datetime.now().weekday()]
        bh[today] = {'open': '06:00', 'close': '07:00'}
        await db.stores.update_one({'_id': STORE}, {'$set': {'business_hours': bh}})
        b1 = test_lead('5005550173')
        await asyncio.sleep(1)
        conv = await db.conversations.find_one({'_id': ObjectId(b1['conversation_id'])}, {'ai_mode': 1, 'ai_enabled': 1, 'after_hours_lead': 1, 'rep_phone': 1})
        print('  conv:', {k: conv.get(k) for k in ['ai_mode', 'ai_enabled', 'after_hours_lead', 'rep_phone']})
        msg = await db.messages.find_one({'conversation_id': b1['conversation_id'], 'is_intake_text': True})
        print('  intake sent now:', bool(msg))
        job = await db.lead_call_jobs.find_one({'conversation_id': b1['conversation_id']})
        print('  job:', job['status'], 'deferred', job['deferred'], job['next_attempt_at'].strftime('%a %H:%M UTC'), job['deferred_reasons'])
        await db.stores.update_one({'_id': STORE}, {'$set': {'business_hours': store0['business_hours']}})

        print("C) morning release: deferred intake action runs")
        from routers.lead_intake import process_lead_deferred_actions
        await db.lead_deferred_actions.update_one({'conversation_id': a1['conversation_id']}, {'$set': {'run_at': datetime.now(timezone.utc) - timedelta(seconds=5)}})
        await process_lead_deferred_actions()
        act = await db.lead_deferred_actions.find_one({'conversation_id': a1['conversation_id']})
        print('  a1 action ->', act['status'], act.get('error'))
        print("C2) rep already texted -> deferred intake cancelled")
        await db.messages.insert_one({'conversation_id': a2['conversation_id'], 'sender': 'user', 'direction': 'outbound', 'content': 'hi from rep', 'timestamp': datetime.now(timezone.utc)})
        await db.lead_deferred_actions.update_one({'conversation_id': a2['conversation_id']}, {'$set': {'run_at': datetime.now(timezone.utc) - timedelta(seconds=5)}})
        await process_lead_deferred_actions()
        act = await db.lead_deferred_actions.find_one({'conversation_id': a2['conversation_id']})
        print('  a2 action ->', act['status'], act.get('reason'))

        print("D) deferred ladder at opening: engaged lead skipped, fresh lead rings")
        from services.lead_call_engine import process_lead_call_jobs
        await db.lead_call_jobs.update_many({'conversation_id': {'$in': [a2['conversation_id'], b1['conversation_id']]}}, {'$set': {'next_attempt_at': datetime.now(timezone.utc) - timedelta(seconds=5)}})
        await process_lead_call_jobs()
        for cid, label in ((a2['conversation_id'], 'a2 (rep texted)'), (b1['conversation_id'], 'b1 (fresh)')):
            j = await db.lead_call_jobs.find_one({'conversation_id': cid})
            print(f"  {label}: status={j['status']} handled_reason={j.get('handled_reason')} calls={[c['status'] for c in j['calls']]}")
        t = api('GET', f"/api/lead-sources/call-timeline/{b1['conversation_id']}")
        print('  timeline b1: deferred', t['job']['deferred'], t['job']['deferred_reasons'], 'intake sent', bool(t['intake']['sent_at']))
        t = api('GET', f"/api/lead-sources/call-timeline/{a1['conversation_id']}")
        print('  timeline a1: intake', t['intake'], 'job', t['job']['status'], t['job']['deferred_until'][:16])
    finally:
        await db.lead_sources.update_one({'_id': SRC}, {'$set': {'text_window_end': src0.get('text_window_end', '20:00')}})
        await db.stores.update_one({'_id': STORE}, {'$set': {'business_hours': store0['business_hours']}})
        print('restored source window + store hours')

asyncio.run(main())
