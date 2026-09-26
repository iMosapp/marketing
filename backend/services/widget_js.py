"""The embeddable widget script. One vanilla-JS IIFE with the widget's public config baked in (served by GET /api/w/{key}.js)."""
import json

ICONS = {
    "chat": '<path d="M4 4h16a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H9l-5 4v-4H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>',
    "text": '<rect x="6" y="2" width="12" height="20" rx="2.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M10 18h4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M9 7h6M9 10h4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
    "phone": '<path d="M5 3h4l2 5-2.5 1.5a11 11 0 0 0 6 6L16 13l5 2v4a2 2 0 0 1-2 2A17 17 0 0 1 3 5a2 2 0 0 1 2-2z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>',
    "menu": '<path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>',
    "sparkles": '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3z" fill="currentColor"/><path d="M19 15l.9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9L19 15z" fill="currentColor"/>',
    "send": '<path d="M3 11.5 21 3l-8.5 18-2.5-7.5L3 11.5z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>',
}


def render(cfg: dict) -> str:
    payload = json.dumps(cfg, separators=(",", ":")).replace("</", "<\\/")
    icons = json.dumps(ICONS).replace("</", "<\\/")
    return TEMPLATE.replace("__CONFIG__", payload).replace("__ICONS__", icons)


def demo_html(store_name: str, js: str, path: str = "", door: str = "") -> str:
    """A stand-in dealership page so the widget can be seen exactly as visitors will see it. `path` fakes the page URL for page rules."""
    name = (store_name or "Your Dealership").replace("<", "&lt;")
    flags = f"window.IMOS_WIDGET_PREVIEW = true; window.IMOS_WIDGET_PATH = {json.dumps(path or '')}; window.IMOS_WIDGET_DOOR = {json.dumps(door or '')};"
    return DEMO.replace("__NAME__", name).replace("__FLAGS__", flags).replace("__JS__", js)


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
<script>__FLAGS__</script>
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

var PATH = String(window.IMOS_WIDGET_PATH || (location.pathname + location.search)).toLowerCase();
var rule = null; (A.page_rules || []).some(function(r){ if (r && r.match && PATH.indexOf(String(r.match).toLowerCase()) >= 0) { rule = r; return true; } return false; });
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
.imosw-greet{position:absolute;bottom:68px;' + side + ':0;width:max-content;max-width:min(300px,calc(100vw - 40px));background:' + panelBg + ';color:' + panelFg + ';border-radius:16px;padding:12px 14px 12px 12px;box-shadow:0 10px 30px rgba(0,0,0,.18);display:flex;gap:10px;align-items:flex-start;cursor:pointer;animation:imosw-in .25s ease}\
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
.imosw-chat{display:flex;flex-direction:column;height:440px;max-height:62vh}\
.imosw-msgs{flex:1;overflow-y:auto;padding:14px 14px 6px;display:flex;flex-direction:column;gap:8px}\
.imosw-m{max-width:84%;padding:9px 12px;border-radius:14px;font-size:14px;line-height:1.4;white-space:pre-wrap;word-wrap:break-word}\
.imosw-m.j{align-self:flex-start;background:rgba(0,0,0,.06);border-bottom-left-radius:4px}\
.imosw-m.v{align-self:flex-end;background:' + bubble + ';color:' + fg + ';border-bottom-right-radius:4px}\
.imosw-m.r{align-self:flex-start;background:rgba(0,0,0,.06);border-bottom-left-radius:4px;border-left:3px solid ' + bubble + '}\
.imosw-m .who{font-size:11px;font-weight:800;opacity:.7;margin-bottom:2px}\
.imosw-sys{align-self:center;font-size:12px;opacity:.6;text-align:center;padding:2px 10px}\
.imosw-booked{align-self:center;font-size:12.5px;font-weight:700;color:#1E8E3E;background:rgba(30,142,62,.1);border-radius:999px;padding:5px 12px}\
.imosw-chips{display:flex;flex-wrap:wrap;gap:6px}\
.imosw-chips.scroll{flex-wrap:nowrap;overflow-x:auto;padding-bottom:4px;-webkit-overflow-scrolling:touch}\
.imosw-chip{flex:none;height:32px;padding:0 12px;border-radius:16px;border:1.5px solid rgba(0,0,0,.12);background:transparent;color:inherit;font-family:inherit;font-size:13px;font-weight:600;cursor:pointer}\
.imosw-chip.on{background:' + bubble + ';color:' + fg + ';border-color:' + bubble + '}\
.imosw-human .sep{opacity:.5;font-size:12.5px}\
.imosw-typing{align-self:flex-start;opacity:.6;font-size:13px;padding:2px 12px}\
.imosw-compose{display:flex;gap:8px;padding:10px 12px 6px;border-top:1px solid rgba(0,0,0,.08)}\
.imosw-compose .imosw-in{height:42px}\
.imosw-send{width:42px;height:42px;border-radius:50%;background:' + bubble + ';color:' + fg + ';border:0;cursor:pointer;flex:none;display:flex;align-items:center;justify-content:center}\
.imosw-send[disabled]{opacity:.5}\
.imosw-human{text-align:center;padding:0 0 6px}\
.imosw-human button{background:none;border:0;color:inherit;opacity:.7;font-size:12.5px;cursor:pointer;font-family:inherit;text-decoration:underline}\
.imosw-cform{align-self:stretch;background:rgba(0,0,0,.04);border-radius:12px;padding:10px;display:flex;flex-direction:column;gap:6px}\
.imosw-cform .imosw-in{height:40px}\
.imosw-cform .imosw-btn{margin-top:4px;height:42px}\
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
var doors = []; if (D.text && D.text.on) doors.push('text'); if (D.call && D.call.on) doors.push('call'); if (D.chat && D.chat.on) doors.push('chat');
var ruleDoor = rule && rule.door && doors.indexOf(rule.door) >= 0 ? rule.door : null;
var greetingText = rule ? rule.greeting : (A.greeting_on ? A.greeting : '');
var avatarHtml = A.avatar_url ? '<img src="' + esc(A.avatar_url) + '" alt="">' : esc((C.store_name || 'Us').charAt(0).toUpperCase());

if (greetingText && doors.length && !saved.greet_dismissed) {
  setTimeout(function(){ if (opened) return;
    greet = h('div', { 'class': 'imosw-greet', onclick: function(e){ if (e.target.className === 'x') return; open(ruleDoor); } }, [
      h('div', { 'class': 'imosw-av', html: avatarHtml }),
      h('div', { style: 'font-size:14px' }, [fill(greetingText, { store: C.store_name })]),
      h('div', { 'class': 'x', html: '&times;', onclick: function(e){ e.stopPropagation(); remember('greet_dismissed', 1); if (greet) { root.removeChild(greet); greet = null; } } })
    ]);
    root.appendChild(greet); track('greeting');
  }, Math.max(0, (rule ? Math.min(A.greeting_delay_s == null ? 4 : A.greeting_delay_s, 3) : (A.greeting_delay_s == null ? 4 : A.greeting_delay_s)) * 1000));
}

function showDoor(d){ track('door', { door: d }); if (d === 'chat') showChat(); else showForm(d); }
function open(door){ if (opened) return; opened = true; if (greet) { root.removeChild(greet); greet = null; }
  panel = h('div', { 'class': 'imosw-panel', role: 'dialog' });
  root.appendChild(panel); launch.style.display = 'none'; track('open');
  if (!doors.length) { showDoors(); return; }
  var d = door && doors.indexOf(door) >= 0 ? door : (ruleDoor || (chat.sid && doors.indexOf('chat') >= 0 && chat.status !== 'closed' ? 'chat' : null));
  if (d) showDoor(d); else if (doors.length === 1) showDoor(doors[0]); else showDoors();
}
function close(){ if (!panel) return; stopPoll(); root.removeChild(panel); panel = null; opened = false; launch.style.display = ''; }
function header(title, sub){ return h('div', { 'class': 'imosw-head' }, [ h('div', { 'class': 'imosw-av', html: avatarHtml }), h('div', {}, [ h('h3', {}, [title]), sub ? h('p', {}, [sub]) : null ]), h('button', { 'class': 'imosw-close', type: 'button', 'aria-label': 'Close', html: '&times;', onclick: close }) ]); }
function foot(){ return h('div', { 'class': 'imosw-foot', html: 'Powered by <a href="https://www.imonsocial.com" target="_blank" rel="noopener">i\'M On Social</a>' }); }
function render(children){ panel.innerHTML = ''; children.forEach(function(c){ if (c) panel.appendChild(c); }); }

function showDoors(){
  var body = h('div', { 'class': 'imosw-body' });
  doors.forEach(function(d){ var cfg = D[d];
    body.appendChild(h('button', { 'class': 'imosw-door', type: 'button', onclick: function(){ showDoor(d); }, html: '<div class="ic">' + svg(d === 'call' ? 'phone' : d === 'chat' ? 'chat' : 'text') + '</div><div><b>' + esc(cfg.label) + '</b><span>' + esc(cfg.intro) + '</span></div>' }));
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

var chat = { sid: saved.chat_sid || null, msgs: [], busy: false, need: false, status: 'open', mode: 'jessi', agent: '', offer: false, booking: null, slots: null, showBook: false };
var pollTimerChat = null; function stopPoll(){ if (pollTimerChat) { clearInterval(pollTimerChat); pollTimerChat = null; } }
function previewReply(t){ if (/test.?drive|appointment|schedule|book|come in|stop by|visit|oil change/i.test(t)) { chat.offer = true; return 'I can set that up right here. Pick a day and time below and I\'ll get you booked.'; }
  if (/price|cost|payment|much|trade|finance|person|human/i.test(t)) { chat.need = true; return 'That one is a team member\'s call, and they\'re quick. What\'s your first name and mobile number? They\'ll text you right away.'; }
  return 'This is the preview, so I\'m not looking anything up. On your live site I answer from your hours, store facts, specials and live inventory, and I hand pricing to your team.'; }
function previewSlots(){ var d = new Date(), out = []; for (var i = 0; i < 4; i++) { var day = new Date(d.getTime() + i * 86400000); var iso = day.toISOString().slice(0, 10);
    out.push({ date: iso, label: i === 0 ? 'Today' : i === 1 ? 'Tomorrow' : day.toDateString().slice(0, 10), slots: ['09:00', '10:30', '13:00', '15:30', '17:00'].map(function(v){ var hh = +v.slice(0, 2); return { v: v, l: ((hh % 12) || 12) + (v.slice(3) === '00' ? '' : ':' + v.slice(3)) + (hh < 12 ? ' AM' : ' PM') }; }) }); }
  return { days: out, kinds: [{ v: 'test_drive', l: 'Test drive' }, { v: 'service', l: 'Service visit' }, { v: 'visit', l: 'Store visit' }] }; }
function showChat(){
  var cfg = D.chat; var ctx = { store: C.store_name };
  var wrap = h('div', { 'class': 'imosw-chat' });
  var list = h('div', { 'class': 'imosw-msgs' });
  var input = h('input', { 'class': 'imosw-in', type: 'text', placeholder: cfg.placeholder || 'Type your question', autocomplete: 'off', 'aria-label': 'Your message' });
  var send = h('button', { 'class': 'imosw-send', type: 'button', 'aria-label': 'Send', html: '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">' + ICONS.send + '</svg>' });
  var humanBtn = h('button', { type: 'button', onclick: function(){ askHuman(); } }, [cfg.human || 'Talk to a person']);
  var bookBtn = h('button', { type: 'button', onclick: function(){ chat.showBook = !chat.showBook; draw(); } }, [cfg.booking_label || 'Book a visit']);
  var sep = h('span', { 'class': 'sep' }, [' \u00b7 ']);
  var human = h('div', { 'class': 'imosw-human' }, [humanBtn, cfg.booking_on !== false ? sep : null, cfg.booking_on !== false ? bookBtn : null]);
  var head = header(cfg.label || 'Chat now', 'Jessi \u00b7 ' + (C.store_name || ''));
  function sub(){ var p = head.querySelector('p'); if (p) p.textContent = (chat.mode === 'human' && chat.agent ? chat.agent : 'Jessi') + ' \u00b7 ' + (C.store_name || ''); }
  function apply(r){ if (r.messages) chat.msgs = r.messages; chat.need = !!r.need_contact; chat.status = r.status || chat.status; chat.mode = r.mode || 'jessi'; chat.agent = r.agent || ''; chat.offer = !!r.offer_booking; chat.booking = r.booking || null; if (chat.booking) chat.showBook = false; sub(); }
  function contactForm(){
    var nm = h('input', { 'class': 'imosw-in', type: 'text', autocomplete: 'name', placeholder: T.name_label || 'First name', value: saved.name || '' });
    var ph = h('input', { 'class': 'imosw-in', type: 'tel', autocomplete: 'tel', inputmode: 'tel', placeholder: T.phone_label || 'Mobile number', value: saved.phone || '' });
    var hp = h('input', { 'class': 'imosw-hp', type: 'text', name: 'website', tabindex: '-1', autocomplete: 'off' });
    var err = h('div', { 'class': 'imosw-err' });
    var btn = h('button', { 'class': 'imosw-btn', type: 'button' }, ['Text me']);
    btn.addEventListener('click', function(){
      var n = nm.value.trim(), p = ph.value.replace(/\D/g, '');
      if (!n) { err.textContent = 'Please add your name.'; return; } if (p.length < 10) { err.textContent = 'Please enter a 10 digit mobile number.'; return; }
      remember('name', n); remember('phone', ph.value); btn.disabled = true; btn.textContent = 'Sending\u2026';
      if (PREVIEW) { chat.need = false; chat.status = 'handed_off'; chat.msgs.push({ role: 'jessi', text: 'Done, ' + n.split(' ')[0] + '. ' + (C.store_name || 'The store') + ' just texted you, reply there and a real person takes it from here.' }); draw(); return; }
      post('/chat/' + chat.sid + '/contact', { name: n, phone: ph.value, website: hp.value }).then(function(r){ apply(r); draw(); track('lead', { door: 'chat' }); })
        .catch(function(e){ btn.disabled = false; btn.textContent = 'Text me'; err.textContent = typeof e === 'string' ? e : 'Something went wrong. Please try again.'; });
    });
    return h('div', { 'class': 'imosw-cform' }, [nm, ph, hp, btn, err, h('div', { 'class': 'imosw-fine', style: 'margin-top:4px' }, [fill(T.optin, ctx)])]);
  }
  var bk = { kind: 'test_drive', date: '', time: '' };
  function bookForm(){
    var box = h('div', { 'class': 'imosw-cform imosw-book' });
    if (!chat.slots) { box.appendChild(h('div', { 'class': 'imosw-typing', style: 'align-self:center' }, ['Checking open times\u2026']));
      var got = function(s){ chat.slots = s; if (!bk.date && s.days[0]) bk.date = s.days[0].date; draw(); };
      if (PREVIEW) setTimeout(function(){ got(previewSlots()); }, 400); else fetch(API + '/chat/' + chat.sid + '/slots').then(function(x){ return x.json(); }).then(got).catch(function(){ chat.slots = { days: [], kinds: [] }; draw(); });
      return box; }
    var s = chat.slots;
    function chips(items, val, set, cls){ var row = h('div', { 'class': 'imosw-chips' + (cls ? ' ' + cls : '') }); items.forEach(function(it){ row.appendChild(h('button', { type: 'button', 'class': 'imosw-chip' + (it.v === val ? ' on' : ''), onclick: function(){ set(it.v); draw(); } }, [it.l])); }); return row; }
    box.appendChild(h('div', { 'class': 'imosw-lbl', style: 'margin-top:0' }, ['What for?']));
    box.appendChild(chips(s.kinds, bk.kind, function(v){ bk.kind = v; }));
    if (!s.days.length) { box.appendChild(h('div', { 'class': 'imosw-err' }, ['No open times in the next few days. Tap ' + (cfg.human || 'Talk to a person') + ' and the team will find one.'])); return box; }
    box.appendChild(h('div', { 'class': 'imosw-lbl' }, ['Which day?']));
    box.appendChild(chips(s.days.map(function(d){ return { v: d.date, l: d.label }; }), bk.date, function(v){ bk.date = v; bk.time = ''; }, 'scroll'));
    var day = s.days.filter(function(d){ return d.date === bk.date; })[0] || s.days[0];
    box.appendChild(h('div', { 'class': 'imosw-lbl' }, ['What time?']));
    box.appendChild(chips(day.slots, bk.time, function(v){ bk.time = v; }, 'scroll'));
    var veh = bk.kind === 'test_drive' ? h('input', { 'class': 'imosw-in', type: 'text', placeholder: 'Which vehicle? (optional)', value: bk.vehicle || '', oninput: function(e){ bk.vehicle = e.target.value; } }) : null;
    var nm = h('input', { 'class': 'imosw-in', type: 'text', autocomplete: 'name', placeholder: T.name_label || 'First name', value: bk.name || saved.name || '', oninput: function(e){ bk.name = e.target.value; } });
    var ph = h('input', { 'class': 'imosw-in', type: 'tel', autocomplete: 'tel', inputmode: 'tel', placeholder: T.phone_label || 'Mobile number', value: bk.phone || saved.phone || '', oninput: function(e){ bk.phone = e.target.value; } });
    var hp = h('input', { 'class': 'imosw-hp', type: 'text', name: 'website', tabindex: '-1', autocomplete: 'off' });
    var err = h('div', { 'class': 'imosw-err' });
    var btn = h('button', { 'class': 'imosw-btn', type: 'button', disabled: !bk.time ? 'disabled' : null }, ['Book it']);
    if (!bk.time) btn.setAttribute('disabled', 'disabled'); else btn.removeAttribute('disabled');
    btn.addEventListener('click', function(){
      var n = nm.value.trim(), p = ph.value.replace(/\D/g, '');
      if (!bk.time) { err.textContent = 'Pick a time first.'; return; } if (!n) { err.textContent = 'Please add your name.'; return; } if (p.length < 10) { err.textContent = 'Please enter a 10 digit mobile number.'; return; }
      remember('name', n); remember('phone', ph.value); btn.disabled = true; btn.textContent = 'Booking\u2026';
      var lab = (day.label + ' at ' + (day.slots.filter(function(x){ return x.v === bk.time; })[0] || {}).l);
      if (PREVIEW) { setTimeout(function(){ chat.booking = { kind: (s.kinds.filter(function(k){ return k.v === bk.kind; })[0] || {}).l, when: lab }; chat.showBook = false; chat.offer = false; chat.status = 'handed_off'; chat.msgs.push({ role: 'jessi', text: 'You\'re all set, ' + n.split(' ')[0] + '. ' + chat.booking.kind + ' on ' + lab + '. ' + (C.store_name || 'The store') + ' just texted you a confirmation.' }); draw(); }, 600); return; }
      post('/chat/' + chat.sid + '/book', { kind: bk.kind, date: bk.date, time: bk.time, vehicle: veh ? veh.value.trim() : '', name: n, phone: ph.value, website: hp.value })
        .then(function(r){ apply(r); chat.showBook = false; draw(); track('lead', { door: 'chat', booked: 1 }); })
        .catch(function(e){ btn.disabled = false; btn.textContent = 'Book it'; err.textContent = typeof e === 'string' ? e : 'Something went wrong. Please try again.'; if (/not open/i.test(String(e))) { chat.slots = null; bk.time = ''; draw(); } });
    });
    if (veh) box.appendChild(veh); box.appendChild(nm); box.appendChild(ph); box.appendChild(hp); box.appendChild(btn); box.appendChild(err);
    box.appendChild(h('div', { 'class': 'imosw-fine', style: 'margin-top:4px' }, [fill(T.optin, ctx)]));
    return box;
  }
  function draw(){ list.innerHTML = '';
    chat.msgs.forEach(function(m){
      if (m.role === 'system') { list.appendChild(h('div', { 'class': 'imosw-sys' }, [m.text])); return; }
      var el = h('div', { 'class': 'imosw-m ' + (m.role === 'visitor' ? 'v' : m.role === 'rep' ? 'r' : 'j') });
      if (m.role === 'rep' && m.who) el.appendChild(h('div', { 'class': 'who' }, [m.who]));
      el.appendChild(document.createTextNode(m.text)); list.appendChild(el); });
    if (chat.booking) list.appendChild(h('div', { 'class': 'imosw-booked' }, ['\u2713 ' + chat.booking.kind + ' \u00b7 ' + chat.booking.when]));
    if (chat.need && chat.status !== 'closed') list.appendChild(contactForm());
    if ((chat.offer || chat.showBook) && !chat.booking && chat.status !== 'closed' && chat.mode !== 'human') list.appendChild(bookForm());
    if (chat.busy && chat.mode !== 'human') list.appendChild(h('div', { 'class': 'imosw-typing' }, ['Jessi is typing\u2026']));
    if (chat.status === 'closed') list.appendChild(h('div', { style: 'text-align:center;padding:6px' }, [ h('button', { 'class': 'imosw-link', type: 'button', onclick: function(){ chat.sid = null; remember('chat_sid', null); chat.msgs = []; chat.status = 'open'; chat.mode = 'jessi'; chat.agent = ''; chat.booking = null; chat.offer = false; sub(); begin(); } }, ['Start a new chat']) ]));
    send.disabled = chat.busy || chat.status === 'closed'; input.disabled = chat.status === 'closed'; humanBtn.style.display = chat.status === 'closed' ? 'none' : ''; sep.style.display = bookBtn.style.display = (chat.status === 'closed' || chat.booking || chat.mode === 'human') ? 'none' : '';
    list.scrollTop = list.scrollHeight; }
  function fail(e){ chat.busy = false; chat.msgs.push({ role: 'jessi', text: typeof e === 'string' ? e : 'Hmm, something hiccuped on my end. Try that once more.' }); draw(); }
  function submit(){ var t = input.value.trim(); if (!t || chat.busy || chat.status === 'closed') return; input.value = ''; chat.msgs.push({ role: 'visitor', text: t }); chat.busy = true; draw();
    if (PREVIEW) { setTimeout(function(){ chat.busy = false; chat.msgs.push({ role: 'jessi', text: previewReply(t) }); draw(); }, 700); return; }
    post('/chat/' + chat.sid + '/message', { text: t }).then(function(r){ chat.busy = false; apply(r); draw(); }).catch(fail); }
  function askHuman(){ if (chat.busy) return; chat.busy = true; draw();
    if (PREVIEW) { setTimeout(function(){ chat.busy = false; chat.need = chat.status !== 'handed_off'; chat.msgs.push({ role: 'jessi', text: chat.status === 'handed_off' ? 'A team member already has your number and is texting you now.' : 'Happy to. What\'s your first name and mobile number? A team member will text you in a minute.' }); draw(); }, 500); return; }
    post('/chat/' + chat.sid + '/human', {}).then(function(r){ chat.busy = false; apply(r); draw(); }).catch(fail); }
  function begin(){ chat.busy = true; draw();
    post('/chat/start', { page: location.href, title: document.title, visitor: visitor }).then(function(r){ chat.busy = false; chat.sid = r.sid; chat.status = 'open'; remember('chat_sid', r.sid); chat.msgs = [{ role: 'jessi', text: r.greeting }]; draw(); poll(); }).catch(fail); }
  function poll(){ stopPoll(); if (PREVIEW) return;
    pollTimerChat = setInterval(function(){ if (!panel || !chat.sid || chat.busy || chat.status === 'closed') { if (!panel) stopPoll(); return; }
      fetch(API + '/chat/' + chat.sid).then(function(x){ if (!x.ok) throw 0; return x.json(); }).then(function(r){ var before = chat.msgs.length + '|' + chat.mode + '|' + chat.status + '|' + chat.offer + '|' + !!chat.booking; apply(r); var after = chat.msgs.length + '|' + chat.mode + '|' + chat.status + '|' + chat.offer + '|' + !!chat.booking; if (before !== after) draw(); }).catch(function(){}); }, 3000); }
  send.addEventListener('click', submit); input.addEventListener('keydown', function(e){ if (e.key === 'Enter') { e.preventDefault(); submit(); } });
  wrap.appendChild(list); wrap.appendChild(h('div', { 'class': 'imosw-compose' }, [input, send])); wrap.appendChild(human);
  if (doors.length > 1) wrap.appendChild(h('div', { style: 'text-align:center;padding:0 0 6px' }, [ h('button', { 'class': 'imosw-link', type: 'button', style: 'margin-top:0', onclick: function(){ stopPoll(); showDoors(); } }, ['\u2190 Other options']) ]));
  render([head, wrap, foot()]);
  if (PREVIEW) { if (!chat.msgs.length) chat.msgs = [{ role: 'jessi', text: C.chat_welcome || ('Hi! I\'m Jessi, ' + (C.store_name || 'the store') + '\'s assistant. Ask me about hours, what\'s in stock or anything about the store. Want a person? Just say so.') }]; draw(); }
  else if (chat.sid) { fetch(API + '/chat/' + chat.sid).then(function(x){ if (!x.ok) throw 0; return x.json(); }).then(function(r){ apply(r); draw(); poll(); }).catch(function(){ chat.sid = null; remember('chat_sid', null); begin(); }); }
  else begin();
  setTimeout(function(){ input.focus(); }, 80);
}

if (PREVIEW) { setTimeout(function(){ if (window.IMOS_WIDGET_PATH && !window.IMOS_WIDGET_DOOR) return; open(window.IMOS_WIDGET_DOOR || null); }, 250); }
window.IMOSWidget = { open: open, close: close };
})();
"""
