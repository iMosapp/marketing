"""Public, no-login customer trade page: /api/public/trade/{token}. Token = one appraisal, 7 days. Serves a self-contained mobile page and three JSON
endpoints (context, photo, submit). Photos are downscaled in the browser before upload so they stay small; every upload goes through core.save_media
with source customer_supplied, so VIN/odometer photos are read the same way rep photos are."""
import json
import logging
from html import escape as ea

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse

from routers.database import get_db
from services.appraisals import intake

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/public/trade", tags=["public-trade"])

_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="robots" content="noindex">
<title>{title}</title>
<style>
:root{{--gold:#C9A962;--bg:#0B0B0D;--card:#15161A;--line:#26272C;--text:#F4F1EA;--muted:#9A9AA2;--ok:#34C759;--bad:#FF3B30}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:16px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:480px;margin:0 auto;padding:28px 18px 80px}}
.eyebrow{{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--gold);margin:0 0 10px;font-weight:700}}
h1{{font-size:26px;line-height:1.15;margin:0 0 8px;font-weight:800}}p.lead{{color:var(--muted);margin:0 0 18px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:16px;margin:14px 0}}
.card h2{{font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin:0 0 10px;font-weight:800}}
label{{display:block;font-size:12px;color:var(--muted);margin:8px 0 4px;font-weight:700}}
input[type=text],input[type=number],input[type=tel],textarea{{width:100%;background:#0F1013;border:1.5px solid var(--line);border-radius:12px;color:var(--text);padding:13px 14px;font-size:17px;font-weight:700;letter-spacing:.5px}}
input:focus,textarea:focus{{outline:none;border-color:var(--gold)}}textarea{{font-weight:500;letter-spacing:0;min-height:84px;font-size:15px}}
.hint{{font-size:12px;color:var(--muted);margin:6px 0 0}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
.slot{{position:relative;border:1.5px dashed var(--line);border-radius:14px;aspect-ratio:4/3;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:6px;color:var(--muted);font-size:13px;font-weight:700;overflow:hidden;background:#0F1013}}
.slot.done{{border-style:solid;border-color:var(--ok)}}.slot img{{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}}
.slot .tag{{position:absolute;left:8px;bottom:8px;background:rgba(0,0,0,.65);padding:3px 8px;border-radius:999px;font-size:11px;color:#fff}}
.slot input{{position:absolute;inset:0;opacity:0;cursor:pointer}}.slot .busy{{position:absolute;inset:0;background:rgba(0,0,0,.55);display:flex;align-items:center;justify-content:center;color:#fff}}
.chips{{display:flex;flex-wrap:wrap;gap:8px}}.chip{{border:1.5px solid var(--line);border-radius:999px;padding:9px 14px;font-size:14px;font-weight:700;color:var(--text);background:#0F1013}}
.chip.on{{border-color:var(--gold);background:rgba(201,169,98,.18);color:var(--gold)}}
.btn{{display:flex;align-items:center;justify-content:center;width:100%;padding:16px;border-radius:999px;font-weight:800;font-size:16px;border:0;color:#000;background:var(--gold);margin-top:14px}}
.btn[disabled]{{opacity:.5}}.btn.ghost{{background:transparent;color:var(--text);border:1px solid var(--line)}}
.read{{font-size:12px;color:var(--ok);margin-top:6px;font-weight:700}}.err{{color:var(--bad);font-size:13px;margin-top:8px;font-weight:700}}
.foot{{margin-top:22px;font-size:12.5px;color:var(--muted)}}.done-wrap{{text-align:center;padding:40px 0}}.done-wrap .big{{font-size:52px}}
.hide{{display:none}}
.btn.rec{{border-color:var(--bad);color:var(--bad)}}.btn svg{{width:18px;height:18px;margin-right:8px;fill:currentColor}}
.clip{{display:flex;gap:10px;margin-top:10px;font-size:14px;line-height:1.4;color:var(--text);background:#0F1013;border:1px solid var(--line);border-radius:12px;padding:10px 12px}}
.clip .dur{{color:var(--gold);font-weight:800;white-space:nowrap}}.clip.quiet span:last-child{{color:var(--muted);font-style:italic}}
</style></head><body><div class="wrap" id="app">
<p class="eyebrow">{store}</p>
<h1 id="h1">{heading}</h1>
<p class="lead" id="lead">{lead}</p>
<div id="form" class="{form_class}">
 <div class="card"><h2>1 · The vehicle</h2>
  <label for="vin">VIN (17 characters)</label>
  <input type="text" id="vin" autocapitalize="characters" autocomplete="off" spellcheck="false" maxlength="17" placeholder="1FTFW1E50NFA12345" value="{vin}">
  <p class="hint">On the driver's door-jamb sticker or the bottom of the windshield. Or just photograph the sticker below and we read it.</p>
  <label for="mileage">Mileage</label>
  <input type="tel" id="mileage" inputmode="numeric" placeholder="61200" value="{mileage}">
  <label for="zip">ZIP where the vehicle is</label>
  <input type="tel" id="zip" inputmode="numeric" maxlength="5" placeholder="84070" value="{zip}">
 </div>
 <div class="card"><h2>2 · Photos</h2>
  <p class="hint" style="margin:0 0 10px">Tap a box to take or choose a photo. They upload right away.</p>
  <div class="grid" id="slots"></div>
  <p class="hint">Need to add more? Use "Other" as many times as you like.</p>
 </div>
 <div class="card"><h2>3 · Quick questions</h2><div id="questions"></div></div>
 <div class="card"><h2>4 · Anything else?</h2>
  <textarea id="notes" placeholder="Recent work, known issues, extras, anything the appraiser should know.">{notes}</textarea>
  <div id="voice" class="hide">
   <button type="button" class="btn ghost" id="rec" style="margin-top:10px"></button>
   <p class="hint" id="rec-hint">Tap, talk about the car, tap again to stop. We type it up for {rep}.</p>
   <div id="clips"></div>
  </div>
  <label for="wants">Do you have a number in mind? (optional)</label>
  <input type="tel" id="wants" inputmode="numeric" placeholder="$">
 </div>
 <button class="btn" id="submit">Send to {rep}</button>
 <p class="err hide" id="err"></p>
 <p class="foot">This link is private to you and expires in a few days. Photos and details go straight to {rep} at {store}, nowhere else.</p>
</div>
<div id="done" class="done-wrap {done_class}"><div class="big">✓</div><h1>Sent to {rep}</h1><p class="lead">Thanks, {customer}. {rep} will take it from here and reach out with your number. You can reopen this link to add photos.</p>
 <button class="btn ghost" id="again">Add more photos</button></div>
</div>
<script>
var T={token_json},CTX={ctx_json},API="/api/public/trade/"+T;
var ROLE_ORDER=["vin_photo","odometer_photo","exterior","exterior","exterior","exterior","interior","interior","photo"];
var ROLE_LABEL={{vin_photo:"VIN sticker",odometer_photo:"Odometer",exterior:"Outside",interior:"Inside",photo:"Other"}};
var answers=CTX.answers||{{}};
function el(h){{var d=document.createElement("div");d.innerHTML=h.trim();return d.firstChild}}
function slot(role,i,ph){{var s=el('<div class="slot" data-role="'+role+'"><span>'+(ph?'':'＋ ')+ROLE_LABEL[role]+(role==="exterior"?" "+(i+1):"")+'</span><input type="file" accept="image/*" capture="environment"></div>');
 if(ph){{s.classList.add("done");if(ph.thumb){{s.insertBefore(el('<img src="'+ph.thumb+'" alt="">'),s.firstChild)}}s.appendChild(el('<span class="tag">'+ROLE_LABEL[ph.role]+'</span>'))}}
 s.querySelector("input").addEventListener("change",function(e){{if(e.target.files[0])upload(s,role,e.target.files[0])}});return s}}
function renderSlots(){{var g=document.getElementById("slots");g.innerHTML="";var ph=(CTX.photos||[]).slice();var ext=0;
 ROLE_ORDER.forEach(function(r){{var idx=ph.findIndex(function(p){{return p.role===r}});var p=idx>=0?ph.splice(idx,1)[0]:null;g.appendChild(slot(r,r==="exterior"?ext++:0,p))}});
 ph.forEach(function(p){{g.appendChild(slot(p.role,0,p))}});g.appendChild(slot("photo",0,null))}}
function shrink(file){{return new Promise(function(res){{var img=new Image(),u=URL.createObjectURL(file);img.onload=function(){{var m=1600,w=img.width,h=img.height,s=Math.min(1,m/Math.max(w,h));
 var c=document.createElement("canvas");c.width=Math.round(w*s);c.height=Math.round(h*s);c.getContext("2d").drawImage(img,0,0,c.width,c.height);URL.revokeObjectURL(u);c.toBlob(function(b){{res(b||file)}},"image/jpeg",.86)}};img.onerror=function(){{res(file)}};img.src=u}})}}
function upload(s,role,file){{var b=el('<div class="busy">Uploading…</div>');s.appendChild(b);shrink(file).then(function(blob){{var fd=new FormData();fd.append("role",role);fd.append("file",blob,(file.name||"photo")+".jpg");
 return fetch(API+"/photo",{{method:"POST",body:fd}})}}).then(function(r){{return r.json().then(function(j){{if(!r.ok)throw new Error(j.detail||"Upload failed");return j}})}}).then(function(j){{
 CTX.photos=(CTX.photos||[]).concat([j]);if(j.reading&&j.reading.vin&&!document.getElementById("vin").value){{document.getElementById("vin").value=j.reading.vin}}
 if(j.reading&&j.reading.mileage&&!document.getElementById("mileage").value){{document.getElementById("mileage").value=j.reading.mileage}}renderSlots()}}).catch(function(e){{b.remove();showErr(e.message)}})}}
function renderQuestions(){{var q=document.getElementById("questions");q.innerHTML="";(CTX.questions||[]).forEach(function(qq){{var w=el('<div><label>'+qq.label+'</label><div class="chips"></div></div>');var ch=w.querySelector(".chips");
 qq.options.forEach(function(o){{var c=el('<span class="chip'+(answers[qq.key]===o.value?" on":"")+'">'+o.label+'</span>');c.onclick=function(){{answers[qq.key]=o.value;renderQuestions()}};ch.appendChild(c)}});q.appendChild(w)}})}}
function showErr(m){{var e=document.getElementById("err");e.textContent=m;e.classList.remove("hide");setTimeout(function(){{e.classList.add("hide")}},6000)}}
document.getElementById("vin").addEventListener("input",function(e){{e.target.value=e.target.value.toUpperCase().replace(/[^A-Z0-9]/g,"").replace(/I/g,"1").replace(/[OQ]/g,"0").slice(0,17)}});
document.getElementById("submit").onclick=function(){{var btn=this;btn.disabled=true;var body={{vin:document.getElementById("vin").value,mileage:document.getElementById("mileage").value.replace(/\\D/g,""),zip:document.getElementById("zip").value,
 condition:answers,notes:document.getElementById("notes").value,wants:document.getElementById("wants").value.replace(/\\D/g,"")}};
 fetch(API+"/submit",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify(body)}}).then(function(r){{return r.json().then(function(j){{if(!r.ok)throw new Error(j.detail||"Could not send");return j}})}})
 .then(function(){{document.getElementById("form").classList.add("hide");document.getElementById("done").classList.remove("hide");window.scrollTo(0,0)}}).catch(function(e){{btn.disabled=false;showErr(e.message)}})}};
document.getElementById("again").onclick=function(){{document.getElementById("done").classList.add("hide");document.getElementById("form").classList.remove("hide");document.getElementById("slots").scrollIntoView({{behavior:"smooth"}})}};
var MIC='<svg viewBox="0 0 24 24"><path d="M12 15a4 4 0 0 0 4-4V6a4 4 0 1 0-8 0v5a4 4 0 0 0 4 4zm6-4h-2a4 4 0 0 1-8 0H6a6 6 0 0 0 5 5.9V20H8v2h8v-2h-3v-3.1A6 6 0 0 0 18 11z"/></svg>';
var REC_LABEL=MIC+"Or just tell us about it",REC_MAX=180,rec=null,recChunks=[],recT=null,recS=0,recMime="";
function esc(s){{return String(s==null?"":s).replace(/[&<>"]/g,function(c){{return{{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}}[c]}})}}
function fmt(s){{s=Math.round(s||0);return Math.floor(s/60)+":"+("0"+(s%60)).slice(-2)}}
function pickMime(){{var c=["audio/webm;codecs=opus","audio/webm","audio/mp4","audio/ogg;codecs=opus"];for(var i=0;i<c.length;i++){{if(window.MediaRecorder&&MediaRecorder.isTypeSupported(c[i]))return c[i]}}return""}}
function renderClips(){{var w=document.getElementById("clips");w.innerHTML="";(CTX.voice_notes||[]).forEach(function(v){{w.appendChild(el('<div class="clip'+(v.transcript?"":" quiet")+'" data-testid="voice-clip"><span class="dur">'+fmt(v.duration)+'</span><span>'+(v.transcript?esc(v.transcript):"Saved. "+esc(CTX.rep)+" will listen to it.")+'</span></div>'))}});
 var full=(CTX.voice_notes||[]).length>=(CTX.max_voice_notes||5);document.getElementById("rec").classList.toggle("hide",full);document.getElementById("rec-hint").textContent=full?"That is plenty of recordings. Type anything else above.":"Tap, talk about the car, tap again to stop. We type it up for "+CTX.rep+"."}}
function setRec(){{var b=document.getElementById("rec");b.innerHTML=REC_LABEL;b.classList.remove("rec");b.disabled=false}}
if(navigator.mediaDevices&&navigator.mediaDevices.getUserMedia&&pickMime()){{document.getElementById("voice").classList.remove("hide");setRec();renderClips()}}
document.getElementById("rec").onclick=function(){{var btn=this;if(rec){{rec.stop();return}}
 navigator.mediaDevices.getUserMedia({{audio:true}}).then(function(stream){{recMime=pickMime();rec=new MediaRecorder(stream,{{mimeType:recMime}});recChunks=[];recS=0;
  rec.ondataavailable=function(e){{if(e.data&&e.data.size)recChunks.push(e.data)}};
  rec.onstop=function(){{clearInterval(recT);stream.getTracks().forEach(function(t){{t.stop()}});var dur=recS,base=recMime.split(";")[0],blob=new Blob(recChunks,{{type:base}});rec=null;setRec();
   if(dur<2){{showErr("Too short. Tap, talk, then tap again.");return}}
   btn.disabled=true;btn.innerHTML=MIC+"Typing it up\u2026";var fd=new FormData();fd.append("duration",dur);fd.append("file",blob,"note."+(base.indexOf("mp4")>=0?"m4a":base.indexOf("ogg")>=0?"ogg":"webm"));
   fetch(API+"/voice",{{method:"POST",body:fd}}).then(function(r){{return r.json().then(function(j){{if(!r.ok)throw new Error(j.detail||"Could not save that");return j}})}})
   .then(function(j){{CTX.voice_notes=(CTX.voice_notes||[]).concat([j]);renderClips()}}).catch(function(e){{showErr(e.message)}}).then(setRec)}};
  rec.start(1000);btn.classList.add("rec");btn.innerHTML=MIC+"Recording 0:00 \u00b7 tap to stop";
  recT=setInterval(function(){{recS++;btn.innerHTML=MIC+"Recording "+fmt(recS)+" \u00b7 tap to stop";if(recS>=REC_MAX&&rec)rec.stop()}},1000)}})
 .catch(function(){{showErr("Microphone access was blocked. Type your notes in the box instead.")}})}};
renderSlots();renderQuestions();
</script></body></html>"""

_GONE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>Trade link</title><style>body{margin:0;background:#0B0B0D;color:#F4F1EA;font:16px/1.5 -apple-system,Segoe UI,Helvetica,Arial,sans-serif}
.wrap{max-width:440px;margin:0 auto;padding:56px 20px}h1{font-size:26px;margin:0 0 10px}p{color:#9A9AA2}</style></head>
<body><div class="wrap"><h1>%s</h1><p>%s</p></div></body></html>"""


async def _appr(token: str):
    a = await intake.by_token(get_db(), token)
    if not a:
        raise HTTPException(status_code=404, detail="This link is not valid.")
    return a


@router.get("/{token}", response_class=HTMLResponse)
async def trade_page(token: str):
    db = get_db()
    a = await intake.by_token(db, token)
    if not a:
        return HTMLResponse(_GONE % ("This link is not valid", "Ask your salesperson to send a fresh one."), status_code=404)
    ctx = await intake.context(db, a, mark_opened=True)
    if ctx["state"] == "expired":
        return HTMLResponse(_GONE % ("This link has expired", "Ask your salesperson to text you a fresh one."), status_code=410)
    if ctx["state"] == "closed":
        return HTMLResponse(_GONE % ("This appraisal is already with the desk", f"{ea(ctx['rep'])} has what they need. Reach out to them for anything new."), status_code=410)
    done = ctx["submitted"]
    page = _PAGE.format(title=f"Your trade · {ea(ctx['store'])}", store=ea(ctx["store"]), rep=ea(ctx["rep"]), customer=ea(ctx["customer"]),
                        heading=ea(f"Hi {ctx['customer']}, let's value your {ctx['vehicle']}" if ctx.get("vehicle") else f"Hi {ctx['customer']}, let's value your trade"),
                        lead=ea(f"{ctx['rep']} asked for a few things so the number is real, not a guess. About 3 minutes."),
                        vin=ea(ctx.get("vin") or ""), mileage=ea(str(ctx.get("mileage") or "")), zip=ea(ctx.get("zip") or ""), notes=ea(ctx.get("notes") or ""),
                        form_class="hide" if done else "", done_class="" if done else "hide", token_json=json.dumps(token), ctx_json=json.dumps(ctx, default=str))
    return HTMLResponse(page, headers={"Cache-Control": "no-store"})


@router.get("/{token}/context")
async def trade_context(token: str):
    return await intake.context(get_db(), await _appr(token))


@router.post("/{token}/photo")
async def trade_photo(token: str, request: Request, role: str = Form("photo"), file: UploadFile = File(...)):
    db = get_db()
    a = await _appr(token)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="That photo came through empty. Try again.")
    try:
        return await intake.add_photo(db, a, role=role, data=data, content_type=file.content_type or "image/jpeg", name=file.filename or "photo.jpg")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{token}/voice")
async def trade_voice(token: str, file: UploadFile = File(...), duration: float = Form(0)):
    """The customer's spoken note (browser MediaRecorder). Stored on the appraisal as a customer voice note, typed by Whisper, words appended to the notes."""
    db = get_db()
    a = await _appr(token)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="That recording came through empty. Try again.")
    try:
        return await intake.add_voice(db, a, data=data, content_type=file.content_type or "audio/webm", duration=duration, name=file.filename or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        logger.error(f"[Intake] voice note failed: {e}")
        raise HTTPException(status_code=500, detail="Could not save that recording. Type it in the box instead.")


@router.post("/{token}/submit")
async def trade_submit(token: str, request: Request):
    db = get_db()
    a = await _appr(token)
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="Bad request")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Bad request")
    try:
        return await intake.submit(db, a, body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
