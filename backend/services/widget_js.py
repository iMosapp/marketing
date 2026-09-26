"""The embeddable widget script. One vanilla-JS IIFE with the widget's public config baked in (served by GET /api/w/{key}.js)."""
import json

ICONS = {
    "chat": '<path d="M4 4h16a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H9l-5 4v-4H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>',
    "text": '<rect x="6" y="2" width="12" height="20" rx="2.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M10 18h4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M9 7h6M9 10h4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
    "phone": '<path d="M5 3h4l2 5-2.5 1.5a11 11 0 0 0 6 6L16 13l5 2v4a2 2 0 0 1-2 2A17 17 0 0 1 3 5a2 2 0 0 1 2-2z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>',
    "menu": '<path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>',
    "sparkles": '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3z" fill="currentColor"/><path d="M19 15l.9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9L19 15z" fill="currentColor"/>',
}


def render(cfg: dict) -> str:
    payload = json.dumps(cfg, separators=(",", ":")).replace("</", "<\\/")
    icons = json.dumps(ICONS).replace("</", "<\\/")
    return TEMPLATE.replace("__CONFIG__", payload).replace("__ICONS__", icons)


def demo_html(store_name: str, js: str) -> str:
    """A stand-in dealership page so the widget can be seen exactly as visitors will see it."""
    name = (store_name or "Your Dealership").replace("<", "&lt;")
    return DEMO.replace("__NAME__", name).replace("__JS__", js)


DEMO = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__NAME__ · widget preview</title>
<style>
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;background:#f4f5f7;color:#1c1c1e}
.nav{display:flex;align-items:center;justify-content:space-between;padding:14px 24px;background:#fff;border-bottom:1px solid #e5e5ea}
.nav b{font-size:18px}.nav span{font-size:13px;color:#8e8e93;margin-left:14px}
.hero{padding:44px 24px 28px;background:linear-gradient(180deg,#fff,#f4f5f7)}
.hero h1{font-size:30px;margin:0 0 8px}.hero p{color:#636366;margin:0;max-width:520px;line-height:1.5}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:14px;padding:0 24px 120px}
.card{background:#fff;border-radius:14px;overflow:hidden;border:1px solid #e5e5ea}
.card .img{height:110px;background:linear-gradient(135deg,#d1d1d6,#e5e5ea)}
.card div.t{padding:12px 14px}.card b{display:block;font-size:14px}.card small{color:#8e8e93}
.tag{position:fixed;left:14px;bottom:12px;font-size:11px;color:#8e8e93;background:#fff;border:1px solid #e5e5ea;border-radius:8px;padding:4px 8px}
</style></head><body>
<div class="nav"><div><b>__NAME__</b><span>New</span><span>Pre-Owned</span><span>Service</span><span>About</span></div><span>Mon-Sat 9-7</span></div>
<div class="hero"><h1>Find your next ride at __NAME__</h1><p>This is a stand-in page. Your widget sits in the corner exactly like it will on your real website. Tap it to see the doors and forms your visitors get.</p></div>
<div class="grid">
<div class="card"><div class="img"></div><div class="t"><b>2025 Crew Cab 4x4</b><small>$48,990 · 12 mi</small></div></div>
<div class="card"><div class="img"></div><div class="t"><b>2024 Mid-size SUV</b><small>$36,450 · 8,210 mi</small></div></div>
<div class="card"><div class="img"></div><div class="t"><b>2023 Compact Sedan</b><small>$21,900 · 19,480 mi</small></div></div>
<div class="card"><div class="img"></div><div class="t"><b>2022 Sports Coupe</b><small>$39,200 · 24,300 mi</small></div></div>
<div class="card"><div class="img"></div><div class="t"><b>2025 Electric Crossover</b><small>$44,700 · 5 mi</small></div></div>
<div class="card"><div class="img"></div><div class="t"><b>2021 Minivan</b><small>$27,300 · 41,000 mi</small></div></div>
</div>
<div class="tag">Preview: nothing here sends a real text or call</div>
<script>window.IMOS_WIDGET_PREVIEW = true;</script>
<script>__JS__</script>
</body></html>"""


TEMPLATE = r"""(function(){
if (window.__imosWidgetLoaded) return; window.__imosWidgetLoaded = true;
var C = __CONFIG__; var ICONS = __ICONS__;
var A = C.appearance, D = C.doors, T = C.copy, PREVIEW = !!(window.IMOS_WIDGET_PREVIEW || C.preview);
var API = (function(){ try { var s = document.currentScript && document.currentScript.src; if (s && /\/api\/w\/[^\/?]+\.js/.test(s)) return s.replace(/\.js(\?.*)?$/, ''); } catch (e) {} return C.api; })();
var isMobile = function(){ return window.innerWidth < 520; };
if (A.hide_mobile && isMobile() && !PREVIEW) return;
var visitor = null; try { visitor = localStorage.getItem('imos_vid'); if (!visitor) { visitor = 'v' + Math.random().toString(36).slice(2) + Date.now().toString(36); localStorage.setItem('imos_vid', visitor); } } catch (e) { visitor = 'v' + Date.now(); }
var saved = {}; try { saved = JSON.parse(sessionStorage.getItem('imos_w') || '{}'); } catch (e) {}
function remember(k, v) { saved[k] = v; try { sessionStorage.setItem('imos_w', JSON.stringify(saved)); } catch (e) {} }
function post(path, body) {
  return fetch(API + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) }).then(function(r){ return r.json().then(function(j){ if (!r.ok) throw (j && (j.detail || j.message)) || 'Something went wrong'; return j; }); });
}
function track(kind, extra) { if (PREVIEW) return; try { post('/event', Object.assign({ kind: kind, page: location.href, title: document.title, visitor: visitor }, extra || {})).catch(function(){}); } catch (e) {} }
function h(tag, attrs, children) {
  var el = document.createElement(tag);
  for (var k in (attrs || {})) { if (k === 'style') el.style.cssText = attrs[k]; else if (k === 'html') el.innerHTML = attrs[k]; else if (k.indexOf('on') === 0) el.addEventListener(k.slice(2), attrs[k]); else el.setAttribute(k, attrs[k]); }
  (children || []).forEach(function(c){ if (c) el.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
  return el;
}
function svg(name) { return '<svg viewBox="0 0 24 24" width="26" height="26" aria-hidden="true">' + (ICONS[name] || ICONS.chat) + '</svg>'; }
function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function(c){ return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
function fill(s, ctx) { return String(s || '').replace(/\{(\w+)\}/g, function(_, k){ return ctx[k] != null ? ctx[k] : ''; }); }

var side = A.position === 'left' ? 'left' : 'right';
var bubble = A.bubble_color || '#2196F3', fg = A.text_color || '#FFFFFF', panelBg = A.panel_color || '#FFFFFF', panelFg = A.panel_text || '#111111';
var font = A.font === 'inherit' ? 'inherit' : '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif';
var css = '\
.imosw-root{position:fixed;z-index:2147483000;bottom:' + (A.offset_y || 20) + 'px;' + side + ':' + (A.offset_x || 20) + 'px;font-family:' + font + ';font-size:15px;line-height:1.4;color:' + panelFg + ';-webkit-font-smoothing:antialiased}\
.imosw-root *{box-sizing:border-box;margin:0;padding:0}\
.imosw-launch{display:flex;align-items:center;gap:10px;height:56px;padding:0 ' + (A.label_on && A.label ? '20px 0 16px' : '15px') + ';border:0;border-radius:999px;background:' + bubble + ';color:' + fg + ';cursor:pointer;box-shadow:0 8px 24px rgba(0,0,0,.22);font-weight:700;font-size:16px;font-family:inherit;transition:transform .15s ease,box-shadow .15s ease}\
.imosw-launch:hover{transform:translateY(-2px);box-shadow:0 12px 28px rgba(0,0,0,.26)}\
.imosw-launch svg{display:block}\
.imosw-launch img{width:28px;height:28px;border-radius:50%;object-fit:cover;display:block}\
.imosw-greet{position:absolute;bottom:68px;' + side + ':0;max-width:300px;background:' + panelBg + ';color:' + panelFg + ';border-radius:16px;padding:12px 14px 12px 12px;box-shadow:0 10px 30px rgba(0,0,0,.18);display:flex;gap:10px;align-items:flex-start;cursor:pointer;animation:imosw-in .25s ease}\
.imosw-greet:after{content:"";position:absolute;bottom:-7px;' + side + ':22px;border:7px solid transparent;border-top-color:' + panelBg + ';border-bottom:0}\
.imosw-greet .x{position:absolute;top:-8px;' + (side === 'right' ? 'left' : 'right') + ':-8px;width:22px;height:22px;border-radius:50%;background:#fff;color:#555;border:1px solid #ddd;font-size:13px;line-height:20px;text-align:center;cursor:pointer}\
.imosw-av{width:34px;height:34px;border-radius:50%;background:' + bubble + ';color:' + fg + ';display:flex;align-items:center;justify-content:center;flex:none;font-weight:800;overflow:hidden}\
.imosw-av img{width:100%;height:100%;object-fit:cover}\
.imosw-panel{position:absolute;bottom:68px;' + side + ':0;width:360px;max-width:calc(100vw - 24px);background:' + panelBg + ';color:' + panelFg + ';border-radius:' + (A.radius || 20) + 'px;box-shadow:0 18px 50px rgba(0,0,0,.28);overflow:hidden;animation:imosw-in .22s ease}\
.imosw-head{background:' + bubble + ';color:' + fg + ';padding:16px 16px 14px;display:flex;align-items:center;gap:12px}\
.imosw-head .imosw-av{background:rgba(255,255,255,.22);color:' + fg + ';width:40px;height:40px}\
.imosw-head h3{font-size:16px;font-weight:800;line-height:1.2}\
.imosw-head p{font-size:12.5px;opacity:.9;margin-top:2px}\
.imosw-close{margin-left:auto;background:rgba(0,0,0,.18);color:' + fg + ';border:0;width:30px;height:30px;border-radius:50%;cursor:pointer;font-size:18px;line-height:30px}\
.imosw-body{padding:16px}\
.imosw-door{display:flex;align-items:center;gap:12px;width:100%;text-align:left;padding:14px;border-radius:14px;border:1.5px solid rgba(0,0,0,.08);background:transparent;color:inherit;cursor:pointer;font-family:inherit;margin-bottom:10px;transition:border-color .15s,background .15s}\
.imosw-door:hover{border-color:' + bubble + ';background:rgba(0,0,0,.02)}\
.imosw-door .ic{width:40px;height:40px;border-radius:12px;background:' + bubble + ';color:' + fg + ';display:flex;align-items:center;justify-content:center;flex:none}\
.imosw-door b{display:block;font-size:15px}\
.imosw-door span{display:block;font-size:12.5px;opacity:.7;margin-top:2px}\
.imosw-lbl{display:block;font-size:12px;font-weight:700;opacity:.75;margin:10px 0 5px}\
.imosw-in{width:100%;height:44px;border:1.5px solid rgba(0,0,0,.14);border-radius:10px;padding:0 12px;font-size:15px;font-family:inherit;color:inherit;background:transparent;outline:none}\
.imosw-in:focus{border-color:' + bubble + '}\
textarea.imosw-in{height:74px;padding:10px 12px;resize:none}\
.imosw-btn{width:100%;height:48px;border:0;border-radius:12px;background:' + bubble + ';color:' + fg + ';font-weight:800;font-size:15px;cursor:pointer;margin-top:14px;font-family:inherit}\
.imosw-btn[disabled]{opacity:.6;cursor:default}\
.imosw-link{background:none;border:0;color:inherit;opacity:.7;font-size:13px;cursor:pointer;margin-top:10px;font-family:inherit;text-decoration:underline}\
.imosw-fine{font-size:11px;opacity:.6;margin-top:10px;line-height:1.35}\
.imosw-err{color:#D0342C;font-size:13px;margin-top:8px}\
.imosw-status{text-align:center;padding:14px 6px 6px}\
.imosw-status .big{font-size:17px;font-weight:800;margin:12px 0 6px}\
.imosw-status p{font-size:14px;opacity:.8}\
.imosw-ring{width:64px;height:64px;border-radius:50%;background:' + bubble + ';color:' + fg + ';display:flex;align-items:center;justify-content:center;margin:0 auto;animation:imosw-pulse 1.2s ease-in-out infinite}\
.imosw-ring.ok{animation:none;background:#2FB35B;color:#fff}\
.imosw-ring.no{animation:none;background:#8E8E93;color:#fff}\
.imosw-foot{text-align:center;font-size:10.5px;opacity:.5;padding:0 0 10px}\
.imosw-foot a{color:inherit;text-decoration:none}\
.imosw-hp{position:absolute;left:-9999px;opacity:0;height:0;width:0}\
@keyframes imosw-in{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}\
@keyframes imosw-pulse{0%,100%{transform:scale(1);box-shadow:0 0 0 0 rgba(0,0,0,.15)}50%{transform:scale(1.06);box-shadow:0 0 0 14px rgba(0,0,0,0)}}\
@media (max-width:520px){.imosw-panel{position:fixed;left:8px;right:8px;bottom:8px;width:auto;max-width:none;max-height:calc(100vh - 16px);overflow:auto}}';
document.head.appendChild(h('style', { html: css }));

var root = h('div', { 'class': 'imosw-root', 'data-imos-widget': C.key });
var launchInner = A.icon === 'image' && A.icon_url ? '<img src="' + esc(A.icon_url) + '" alt="">' : svg(A.icon || 'chat');
var launch = h('button', { 'class': 'imosw-launch', type: 'button', 'aria-label': A.label || 'Chat with us', html: launchInner + (A.label_on && A.label ? '<span>' + esc(A.label) + '</span>' : ''), onclick: function(){ open(); } });
root.appendChild(launch);
document.body.appendChild(root);
track('load');

var panel = null, greet = null, opened = false;
var doors = []; if (D.text && D.text.on) doors.push('text'); if (D.call && D.call.on) doors.push('call');
var avatarHtml = A.avatar_url ? '<img src="' + esc(A.avatar_url) + '" alt="">' : esc((C.store_name || 'Us').charAt(0).toUpperCase());

if (A.greeting_on && A.greeting && !saved.greet_dismissed) {
  setTimeout(function(){ if (opened) return;
    greet = h('div', { 'class': 'imosw-greet', onclick: function(e){ if (e.target.className === 'x') return; open(); } }, [
      h('div', { 'class': 'imosw-av', html: avatarHtml }),
      h('div', { style: 'font-size:14px' }, [fill(A.greeting, { store: C.store_name })]),
      h('div', { 'class': 'x', html: '&times;', onclick: function(e){ e.stopPropagation(); remember('greet_dismissed', 1); if (greet) { root.removeChild(greet); greet = null; } } })
    ]);
    root.appendChild(greet); track('greeting');
  }, Math.max(0, (A.greeting_delay_s == null ? 4 : A.greeting_delay_s) * 1000));
}

function open(){ if (opened) return; opened = true; if (greet) { root.removeChild(greet); greet = null; }
  panel = h('div', { 'class': 'imosw-panel', role: 'dialog' });
  root.appendChild(panel); launch.style.display = 'none'; track('open');
  if (doors.length === 1) showForm(doors[0]); else showDoors();
}
function close(){ if (!panel) return; root.removeChild(panel); panel = null; opened = false; launch.style.display = ''; }
function header(title, sub){ return h('div', { 'class': 'imosw-head' }, [ h('div', { 'class': 'imosw-av', html: avatarHtml }), h('div', {}, [ h('h3', {}, [title]), sub ? h('p', {}, [sub]) : null ]), h('button', { 'class': 'imosw-close', type: 'button', 'aria-label': 'Close', html: '&times;', onclick: close }) ]); }
function foot(){ return h('div', { 'class': 'imosw-foot', html: 'Powered by <a href="https://www.imonsocial.com" target="_blank" rel="noopener">i\'M On Social</a>' }); }
function render(children){ panel.innerHTML = ''; children.forEach(function(c){ if (c) panel.appendChild(c); }); }

function showDoors(){
  var body = h('div', { 'class': 'imosw-body' });
  doors.forEach(function(d){ var cfg = D[d];
    body.appendChild(h('button', { 'class': 'imosw-door', type: 'button', onclick: function(){ showForm(d); }, html: '<div class="ic">' + svg(d === 'call' ? 'phone' : 'text') + '</div><div><b>' + esc(cfg.label) + '</b><span>' + esc(cfg.intro) + '</span></div>' }));
  });
  render([header(T.title || 'How can we help?', C.store_name), body, foot()]);
}

function showForm(door){
  var cfg = D[door]; var ctx = { store: C.store_name };
  var body = h('div', { 'class': 'imosw-body' });
  var name = h('input', { 'class': 'imosw-in', type: 'text', autocomplete: 'name', placeholder: T.name_label || 'Your name', value: saved.name || '' });
  var phone = h('input', { 'class': 'imosw-in', type: 'tel', autocomplete: 'tel', inputmode: 'tel', placeholder: T.phone_label || 'Mobile number', value: saved.phone || '' });
  var msg = door === 'text' && cfg.ask_message !== false ? h('textarea', { 'class': 'imosw-in', placeholder: T.message_label || 'What can we help with?' }) : null;
  var hp = h('input', { 'class': 'imosw-hp', type: 'text', name: 'website', tabindex: '-1', autocomplete: 'off' });
  var err = h('div', { 'class': 'imosw-err' });
  var btn = h('button', { 'class': 'imosw-btn', type: 'button' }, [cfg.button || (door === 'call' ? 'Call me now' : 'Send text')]);
  btn.addEventListener('click', function(){
    err.textContent = '';
    var n = name.value.trim(), p = phone.value.replace(/\D/g, '');
    if (!n) { err.textContent = 'Please add your name.'; name.focus(); return; }
    if (p.length < 10) { err.textContent = 'Please enter a 10 digit mobile number.'; phone.focus(); return; }
    remember('name', n); remember('phone', phone.value);
    btn.disabled = true; btn.textContent = door === 'call' ? 'Calling…' : 'Sending…';
    if (PREVIEW) { setTimeout(function(){ door === 'call' ? showCallStatus({ status: 'ringing', request_id: 'preview' }, n) : showDone(cfg.success, ctx); }, 500); return; }
    post('/' + door, { name: n, phone: phone.value, message: msg ? msg.value.trim() : '', page: location.href, title: document.title, visitor: visitor, website: hp.value })
      .then(function(r){ track('lead', { door: door }); door === 'call' ? showCallStatus(r, n) : showDone(r.message || cfg.success, ctx); })
      .catch(function(e){ btn.disabled = false; btn.textContent = cfg.button || (door === 'call' ? 'Call me now' : 'Send text'); err.textContent = typeof e === 'string' ? e : 'Something went wrong. Please try again.'; });
  });
  body.appendChild(h('p', { style: 'font-size:14px;opacity:.85;margin-bottom:6px' }, [fill(cfg.intro, ctx)]));
  body.appendChild(h('label', { 'class': 'imosw-lbl' }, [T.name_label || 'Name'])); body.appendChild(name);
  body.appendChild(h('label', { 'class': 'imosw-lbl' }, [T.phone_label || 'Mobile number'])); body.appendChild(phone);
  if (msg) { body.appendChild(h('label', { 'class': 'imosw-lbl' }, [T.message_label || 'Message (optional)'])); body.appendChild(msg); }
  body.appendChild(hp); body.appendChild(btn); body.appendChild(err);
  body.appendChild(h('div', { 'class': 'imosw-fine' }, [fill(T.optin, ctx)]));
  if (doors.length > 1) body.appendChild(h('button', { 'class': 'imosw-link', type: 'button', onclick: showDoors }, ['\u2190 Other options']));
  render([header(cfg.label, C.store_name), body, foot()]);
  setTimeout(function(){ (saved.name ? phone : name).focus(); }, 60);
}

function showDone(text, ctx){
  render([header(C.store_name || 'Thanks!'), h('div', { 'class': 'imosw-body' }, [ h('div', { 'class': 'imosw-status' }, [ h('div', { 'class': 'imosw-ring ok', html: svg('text') }), h('div', { 'class': 'big' }, [fill(text, ctx)]), h('p', {}, ['Keep your phone handy.']) ]), h('button', { 'class': 'imosw-btn', type: 'button', onclick: close }, ['Done']) ]), foot()]);
}

var pollTimer = null;
function showCallStatus(r, n){
  var cfg = D.call; var ctx = { store: C.store_name, rep: r.rep_first || 'a team member', number: r.from_display || '', opens_at: r.opens_at_display || '' };
  var st = r.status;
  var icon = h('div', { 'class': 'imosw-ring' + (st === 'connected' || st === 'connecting' ? ' ok' : (st === 'missed' || st === 'after_hours' ? ' no' : '')), html: svg('phone') });
  var big = st === 'ringing' ? (cfg.success_ringing || 'Ringing the team…') : st === 'connecting' ? fill(cfg.success_connected || 'Connecting you to {rep}…', ctx) : st === 'connected' ? fill('You\'re on with {rep}.', ctx) : st === 'after_hours' ? (r.message || fill(cfg.after_hours || 'We\'re closed right now. We just texted you.', ctx)) : (r.message || fill(cfg.missed || 'Everyone is tied up. We just texted you instead.', ctx));
  var small = st === 'ringing' ? 'Your phone will ring from ' + (ctx.number || 'our number') + ' in a moment.' : st === 'connecting' ? 'Pick up, that\'s us calling from ' + (ctx.number || 'our number') + '.' : st === 'connected' ? 'Talk soon.' : st === 'after_hours' ? 'Reply to that text any time.' : 'Reply to that text and we\'ll get right back to you.';
  render([header(cfg.label, C.store_name), h('div', { 'class': 'imosw-body' }, [ h('div', { 'class': 'imosw-status' }, [icon, h('div', { 'class': 'big' }, [big]), h('p', {}, [small])]), (st === 'ringing' || st === 'connecting') ? null : h('button', { 'class': 'imosw-btn', type: 'button', onclick: close }, ['Done']) ]), foot()]);
  if (pollTimer) clearTimeout(pollTimer);
  if ((st === 'ringing' || st === 'connecting') && r.request_id && r.request_id !== 'preview') {
    pollTimer = setTimeout(function(){ fetch(API + '/call/' + r.request_id).then(function(x){ return x.json(); }).then(function(j){ if (panel) showCallStatus(Object.assign({}, r, j), n); }).catch(function(){ if (panel) showCallStatus(r, n); }); }, 2500);
  } else if (st === 'ringing' && r.request_id === 'preview') { pollTimer = setTimeout(function(){ if (panel) showCallStatus({ status: 'connecting', rep_first: 'Chuck', from_display: '(555) 010-2030', request_id: 'preview' }, n); }, 2500); }
}

if (PREVIEW) { setTimeout(open, 250); }
window.IMOSWidget = { open: open, close: close };
})();
"""
