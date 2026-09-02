"""Manual probe: simulate Twilio voice webhooks against a preview lead-call job and print the timeline."""
import os, sys, asyncio, json, urllib.request, urllib.parse
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

API = 'http://localhost:8001'
TOK = open('/tmp/tok').read().strip()
CONV = sys.argv[1]


def post(path, form):
    data = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(API + path, data=data, method='POST')
    return urllib.request.urlopen(req).read().decode()[:160]


async def main():
    db = AsyncIOMotorClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]
    job = await db.lead_call_jobs.find_one({'conversation_id': CONV})
    jid, tok, uid = str(job['_id']), job['token'], job['attempts'][0]['user_ids'][0]
    sid = job['calls'][0].get('call_sid', 'CAtest')
    qs = f"?job={jid}&u={uid}&t={tok}"
    print('answer:', post(f"/api/webhooks/twilio/lead-call/answer{qs}", {'CallSid': sid}))
    print('pass  :', post(f"/api/webhooks/twilio/lead-call/claim{qs}", {'CallSid': sid, 'Digits': '2'}))
    print('status:', post(f"/api/webhooks/twilio/lead-call/status{qs}", {'CallSid': sid, 'CallStatus': 'completed'}))
    await asyncio.sleep(40)
    job = await db.lead_call_jobs.find_one({'_id': job['_id']})
    print('attempt_index', job['attempt_index'], 'calls', [(c.get('attempt'), c.get('status'), c.get('twilio_status')) for c in job['calls']])
    if len(job['calls']) > 1:
        sid2 = job['calls'][1].get('call_sid', 'CAtest2')
        print('answer2:', post(f"/api/webhooks/twilio/lead-call/answer{qs}", {'CallSid': sid2}))
        print('claim2 :', post(f"/api/webhooks/twilio/lead-call/claim{qs}", {'CallSid': sid2, 'Digits': '1'}))
        print('status2:', post(f"/api/webhooks/twilio/lead-call/status{qs}", {'CallSid': sid2, 'CallStatus': 'completed'}))
    req = urllib.request.Request(API + f"/api/lead-sources/call-timeline/{CONV}", headers={'Authorization': 'Bearer ' + TOK})
    t = json.loads(urllib.request.urlopen(req).read())
    print(json.dumps({k: t['job'][k] for k in ['status', 'claimed_by_name', 'claimed_via', 'time_to_claim_seconds', 'calls']}, indent=1))
    print('conv:', await db.conversations.find_one({'_id': ObjectId(CONV)}, {'claimed_by': 1, 'claim_source': 1, 'rep_phone': 1, 'ai_mode': 1, 'ai_enabled': 1}))


asyncio.run(main())
