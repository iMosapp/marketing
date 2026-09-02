"""Manual probe part 2: morning release + deferred ladder handling on convs created by part 1."""
import os, sys, asyncio, json, urllib.request
from datetime import datetime, timezone, timedelta
sys.path.insert(0, '/app/backend')
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from bson import ObjectId
from routers.database import get_db

API = 'http://localhost:8001'
TOK = open('/tmp/tok').read().strip()
A1, A2, B1 = sys.argv[1], sys.argv[2], sys.argv[3]


def api(method, path, body=None):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body else None, method=method,
                                 headers={'Authorization': 'Bearer ' + TOK, 'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req).read())


async def main():
    db = get_db()
    from routers.lead_intake import process_lead_deferred_actions
    from services.lead_call_engine import process_lead_call_jobs
    print("C) morning release: deferred intake action runs")
    await db.lead_deferred_actions.update_one({'conversation_id': A1}, {'$set': {'run_at': datetime.now(timezone.utc) - timedelta(seconds=5)}})
    await process_lead_deferred_actions()
    act = await db.lead_deferred_actions.find_one({'conversation_id': A1})
    print('  a1 action ->', act['status'], act.get('error'))
    print('  a1 intake message logged:', bool(await db.messages.find_one({'conversation_id': A1, 'is_intake_text': True})))
    print("C2) rep already texted -> deferred intake cancelled")
    await db.messages.insert_one({'conversation_id': A2, 'sender': 'user', 'direction': 'outbound', 'content': 'hi from rep', 'timestamp': datetime.now(timezone.utc), 'is_probe': True})
    await db.lead_deferred_actions.update_one({'conversation_id': A2}, {'$set': {'run_at': datetime.now(timezone.utc) - timedelta(seconds=5)}})
    await process_lead_deferred_actions()
    act = await db.lead_deferred_actions.find_one({'conversation_id': A2})
    print('  a2 action ->', act['status'], act.get('reason'))

    print("D) deferred ladder at opening: engaged lead skipped, fresh lead rings")
    await db.lead_call_jobs.update_many({'conversation_id': {'$in': [A2, B1]}}, {'$set': {'next_attempt_at': datetime.now(timezone.utc) - timedelta(seconds=5)}})
    await process_lead_call_jobs()
    for cid, label in ((A2, 'a2 (rep texted)'), (B1, 'b1 (fresh)')):
        j = await db.lead_call_jobs.find_one({'conversation_id': cid})
        print(f"  {label}: status={j['status']} handled_reason={j.get('handled_reason')} calls={[c['status'] for c in j['calls']]}")
    t = api('GET', f"/api/lead-sources/call-timeline/{B1}")
    print('  timeline b1: deferred', t['job']['deferred'], t['job']['deferred_reasons'], 'intake sent', bool(t['intake']['sent_at']), 'jessi', t['jessi_on'])
    t = api('GET', f"/api/lead-sources/call-timeline/{A1}")
    print('  timeline a1: intake', t['intake'], 'job', t['job']['status'], t['job']['deferred_until'][:16])
    # overnight wording on answer
    j = await db.lead_call_jobs.find_one({'conversation_id': B1})
    if j['calls']:
        import urllib.parse
        qs = f"?job={j['_id']}&u={j['calls'][0]['user_id']}&t={j['token']}"
        req = urllib.request.Request(API + f"/api/webhooks/twilio/lead-call/answer{qs}", data=urllib.parse.urlencode({'CallSid': j['calls'][0].get('call_sid', 'x')}).encode(), method='POST')
        print('  answer TwiML:', urllib.request.urlopen(req).read().decode()[120:200])

asyncio.run(main())
