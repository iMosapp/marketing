#!/bin/bash
# End-to-end check of the Sold tag workflow on preview
set -e
cd /app
API=$(grep REACT_APP_BACKEND_URL frontend/.env | cut -d '=' -f2)
TOKEN=$(curl -s -X POST "$API/api/auth/login" -H "Content-Type: application/json" -d '{"email":"forest@imosapp.com","password":"Admin123!"}' | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('token') or d.get('access_token'))")
U=69a0b7095fddcede09591667
echo "--- workflows list ---"
curl -s "$API/api/workflows/$U" -H "Authorization: Bearer $TOKEN" | python3 -c "
import sys,json;d=json.load(sys.stdin);print('editable',d['editable'],'scope',d['scope'])
for w in d['workflows']: print(' ',w['tag'],'| jessi',w['jessi_mode'],'| stop',w['stop_tags'],'| camps',[(c['name'],c['steps'],c['scope']) for c in w['campaigns']],'| timeline',len(w['timeline']))
sold=[w for w in d['workflows'] if w['tag']=='sold'][0]; print('sold timeline:', [(t['when'],t['what']) for t in sold['timeline'][:7]])"
echo "--- create Working contact (tag path enrolls Working campaign) ---"
CID=$(curl -s -X POST "$API/api/contacts/$U" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"first_name":"Wf","last_name":"SoldTest","phone":"+15005550061","tags":["Working"]}' | python3 -c "import sys,json;print(json.load(sys.stdin)['_id'])")
echo "contact $CID"; sleep 1
cd backend; export $(grep -v '^#' .env | grep -E "^(MONGO_URL|DB_NAME)=" | xargs)
python - <<EOF
import asyncio, os
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
async def main():
    db=AsyncIOMotorClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]
    await db.contacts.update_one({"_id":ObjectId("$CID")},{"\$set":{"hot_opportunity":True},"\$addToSet":{"tags":"hot"}})
    await db.conversations.insert_one({"user_id":"$U","contact_id":"$CID","contact_phone":"+15005550061","contact_name":"Wf SoldTest","status":"active","ai_enabled":False,"ai_mode":"suggest","hot_opportunity":True})
    print('after Working tag -> enrollments:', [(x['campaign_name'],x['status'],x.get('ai_assist_mode')) async for x in db.campaign_enrollments.find({"contact_id":"$CID"})])
    c=await db.contacts.find_one({"_id":ObjectId("$CID")},{"tags":1,"ai_default_mode":1}); print('contact tags', c.get('tags'), 'ai_default_mode', c.get('ai_default_mode'))
    conv=await db.conversations.find_one({"user_id":"$U","contact_id":"$CID"}); print('conversation before sold: ai_mode', conv.get('ai_mode'))
asyncio.run(main())
EOF
cd /app
echo "--- mark sold via date-sold ---"
curl -s -X PATCH "$API/api/contacts/$U/$CID/date-sold" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"date":"2026-09-09"}' | python3 -c "import sys,json;d=json.load(sys.stdin);print('sale',d.get('sale'),'| workflow',json.dumps(d.get('workflow'))[:500])"
cd backend
python - <<EOF
import asyncio, os, sys
sys.path.insert(0,'.')
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
async def main():
    db=AsyncIOMotorClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]
    c=await db.contacts.find_one({"_id":ObjectId("$CID")},{"tags":1,"hot_opportunity":1,"ai_default_mode":1,"sold_count":1})
    print('contact tags', c.get('tags'), '| hot', c.get('hot_opportunity'), '| ai_default_mode', c.get('ai_default_mode'), '| sold_count', c.get('sold_count'))
    async for x in db.campaign_enrollments.find({"contact_id":"$CID"}): print('  enrollment', x['campaign_name'], x['status'], x.get('cancelled_reason'), 'jessi', x.get('ai_assist_mode'))
    print('  pending sends:', {s: await db.campaign_pending_sends.count_documents({"contact_id":"$CID","status":s}) for s in ('pending','cancelled')})
    conv=await db.conversations.find_one({"user_id":"$U","contact_id":"$CID"}); print('conversation after sold: ai_mode', conv.get('ai_mode'), 'ai_enabled', conv.get('ai_enabled'), 'hot', conv.get('hot_opportunity'))
    print('activity:', [e['description'] async for e in db.contact_events.find({"contact_id":"$CID","event_type":"workflow"})])
    from services.tag_workflows import initial_ai_state
    print('initial_ai_state for a future conversation:', await initial_ai_state(db, "$CID"))
    await db.campaign_pending_sends.delete_many({"contact_id":"$CID"}); await db.campaign_enrollments.delete_many({"contact_id":"$CID"}); await db.conversations.delete_many({"contact_id":"$CID"}); await db.contact_events.delete_many({"contact_id":"$CID"}); await db.contacts.delete_one({"_id":ObjectId("$CID")}); print('cleaned')
asyncio.run(main())
EOF
