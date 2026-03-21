(function(){
  // Jessi Chat Widget — i'M On Social
  // Self-contained: injects its own CSS, HTML, and logic.
  // If closed via X, it stays closed for the session (sessionStorage).

  var API_BASE = window.IMOS_API || '';
  var CLOSED_KEY = 'imos_chat_closed';
  var SESSION_KEY = 'imos_chat_session';

  // Respect the user's close
  if (sessionStorage.getItem(CLOSED_KEY) === '1') return;

  // Inject CSS
  var style = document.createElement('style');
  style.textContent = [
    '#imos-chat-bubble{position:fixed;bottom:24px;right:24px;z-index:99999;width:56px;height:56px;border-radius:50%;background:#007AFF;color:#fff;border:none;cursor:pointer;box-shadow:0 4px 20px rgba(0,122,255,.35);display:flex;align-items:center;justify-content:center;transition:transform .25s,box-shadow .25s;font-size:0}',
    '#imos-chat-bubble:hover{transform:scale(1.08);box-shadow:0 6px 28px rgba(0,122,255,.45)}',
    '#imos-chat-bubble svg{width:26px;height:26px;fill:#fff}',
    '#imos-chat-bubble .pulse{position:absolute;top:-3px;right:-3px;width:14px;height:14px;background:#34C759;border:2.5px solid #fff;border-radius:50%}',

    '#imos-chat-panel{position:fixed;bottom:24px;right:24px;z-index:99999;width:380px;max-width:calc(100vw - 32px);height:520px;max-height:calc(100vh - 48px);border-radius:20px;background:#fff;box-shadow:0 20px 60px rgba(0,0,0,.18);display:none;flex-direction:column;overflow:hidden;font-family:Inter,-apple-system,BlinkMacSystemFont,sans-serif;animation:imos-slide-up .3s ease}',
    '@keyframes imos-slide-up{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}',

    '#imos-chat-panel .ch-head{background:#007AFF;color:#fff;padding:16px 18px;display:flex;align-items:center;gap:12px;flex-shrink:0}',
    '#imos-chat-panel .ch-head .av{width:36px;height:36px;border-radius:50%;background:rgba(255,255,255,.2);display:flex;align-items:center;justify-content:center;font-size:15px;font-weight:700;flex-shrink:0}',
    '#imos-chat-panel .ch-head .info{flex:1}',
    '#imos-chat-panel .ch-head .info .name{font-size:15px;font-weight:700}',
    '#imos-chat-panel .ch-head .info .status{font-size:12px;opacity:.8}',
    '#imos-chat-panel .ch-close{background:none;border:none;color:#fff;cursor:pointer;padding:6px;border-radius:8px;display:flex;align-items:center;justify-content:center;transition:background .15s}',
    '#imos-chat-panel .ch-close:hover{background:rgba(255,255,255,.2)}',
    '#imos-chat-panel .ch-close svg{width:18px;height:18px;fill:#fff}',

    '#imos-chat-panel .ch-body{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:10px;background:#F8F9FB}',
    '#imos-chat-panel .ch-body::-webkit-scrollbar{width:4px}',
    '#imos-chat-panel .ch-body::-webkit-scrollbar-thumb{background:rgba(0,0,0,.12);border-radius:4px}',

    '.ch-msg{max-width:82%;padding:10px 14px;border-radius:16px;font-size:14px;line-height:1.5;word-break:break-word}',
    '.ch-msg.jessi{background:#fff;color:#111;border:1px solid rgba(0,0,0,.06);align-self:flex-start;border-bottom-left-radius:4px}',
    '.ch-msg.visitor{background:#007AFF;color:#fff;align-self:flex-end;border-bottom-right-radius:4px}',
    '.ch-msg.typing{background:#fff;border:1px solid rgba(0,0,0,.06);align-self:flex-start;border-bottom-left-radius:4px;display:flex;gap:4px;padding:12px 18px}',
    '.ch-msg.typing span{width:7px;height:7px;border-radius:50%;background:rgba(0,0,0,.25);animation:imos-dot 1.2s infinite}',
    '.ch-msg.typing span:nth-child(2){animation-delay:.2s}',
    '.ch-msg.typing span:nth-child(3){animation-delay:.4s}',
    '@keyframes imos-dot{0%,60%,100%{transform:translateY(0)}30%{transform:translateY(-5px)}}',

    '#imos-chat-panel .ch-foot{padding:12px;border-top:1px solid rgba(0,0,0,.06);display:flex;gap:8px;background:#fff;flex-shrink:0}',
    '#imos-chat-panel .ch-foot input{flex:1;padding:10px 14px;border:1px solid rgba(0,0,0,.1);border-radius:980px;font-size:14px;font-family:inherit;outline:none;transition:border .2s}',
    '#imos-chat-panel .ch-foot input:focus{border-color:#007AFF}',
    '#imos-chat-panel .ch-foot button{width:38px;height:38px;border-radius:50%;background:#007AFF;color:#fff;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:background .2s;flex-shrink:0}',
    '#imos-chat-panel .ch-foot button:hover{background:#0059CC}',
    '#imos-chat-panel .ch-foot button:disabled{background:#ccc;cursor:default}',
    '#imos-chat-panel .ch-foot button svg{width:16px;height:16px;fill:#fff}',

    '@media(max-width:480px){#imos-chat-panel{width:100%;height:100%;max-width:100%;max-height:100%;bottom:0;right:0;border-radius:0}}'
  ].join('\n');
  document.head.appendChild(style);

  // SVG icons
  var chatIcon = '<svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.2L4 17.2V4h16v12z"/></svg>';
  var closeIcon = '<svg viewBox="0 0 24 24"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>';
  var sendIcon = '<svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>';

  // Detect page source
  var pagePath = location.pathname.replace(/^\/|\/$/g, '') || 'homepage';
  var pageSource = pagePath.replace(/\//g, '_') + '_page';

  // Build bubble
  var bubble = document.createElement('button');
  bubble.id = 'imos-chat-bubble';
  bubble.setAttribute('data-testid', 'chat-widget-bubble');
  bubble.innerHTML = chatIcon + '<span class="pulse"></span>';
  bubble.title = 'Chat with Jessi';
  document.body.appendChild(bubble);

  // Build panel
  var panel = document.createElement('div');
  panel.id = 'imos-chat-panel';
  panel.setAttribute('data-testid', 'chat-widget-panel');
  panel.innerHTML = [
    '<div class="ch-head">',
      '<div class="av">J</div>',
      '<div class="info"><div class="name">Jessi</div><div class="status">Online</div></div>',
      '<button class="ch-close" data-testid="chat-widget-close">' + closeIcon + '</button>',
    '</div>',
    '<div class="ch-body" data-testid="chat-widget-body"></div>',
    '<div class="ch-foot">',
      '<input type="text" placeholder="Type a message..." data-testid="chat-widget-input" />',
      '<button data-testid="chat-widget-send" disabled>' + sendIcon + '</button>',
    '</div>'
  ].join('');
  document.body.appendChild(panel);

  var body = panel.querySelector('.ch-body');
  var input = panel.querySelector('.ch-foot input');
  var sendBtn = panel.querySelector('.ch-foot button');
  var closeBtn = panel.querySelector('.ch-close');
  var sessionId = null;
  var sending = false;

  function addMsg(text, role) {
    var d = document.createElement('div');
    d.className = 'ch-msg ' + role;
    d.textContent = text;
    body.appendChild(d);
    body.scrollTop = body.scrollHeight;
  }

  function showTyping() {
    var d = document.createElement('div');
    d.className = 'ch-msg typing';
    d.id = 'imos-typing';
    d.innerHTML = '<span></span><span></span><span></span>';
    body.appendChild(d);
    body.scrollTop = body.scrollHeight;
  }

  function hideTyping() {
    var el = document.getElementById('imos-typing');
    if (el) el.remove();
  }

  async function startSession() {
    try {
      var res = await fetch(API_BASE + '/api/chat/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ page: pageSource })
      });
      var data = await res.json();
      sessionId = data.session_id;
      sessionStorage.setItem(SESSION_KEY, sessionId);
      addMsg(data.greeting, 'jessi');
    } catch (e) {
      addMsg("Hi! I'm Jessi. Having a small connection hiccup — try again in a moment!", 'jessi');
    }
  }

  async function sendMessage() {
    var text = input.value.trim();
    if (!text || sending || !sessionId) return;

    sending = true;
    sendBtn.disabled = true;
    input.value = '';
    addMsg(text, 'visitor');
    showTyping();

    try {
      var res = await fetch(API_BASE + '/api/chat/message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, message: text })
      });
      var data = await res.json();
      hideTyping();
      if (data.response) addMsg(data.response, 'jessi');
    } catch (e) {
      hideTyping();
      addMsg("Sorry, I had a hiccup. Could you try that again?", 'jessi');
    }
    sending = false;
    sendBtn.disabled = false;
    input.focus();
  }

  // Open panel
  bubble.addEventListener('click', function() {
    bubble.style.display = 'none';
    panel.style.display = 'flex';
    input.focus();
    if (!sessionId) startSession();
  });

  // Close — permanently for this browser session
  closeBtn.addEventListener('click', function() {
    panel.style.display = 'none';
    sessionStorage.setItem(CLOSED_KEY, '1');
    // Don't show bubble again
  });

  // Send on click or Enter
  sendBtn.addEventListener('click', sendMessage);
  input.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') sendMessage();
  });
  input.addEventListener('input', function() {
    sendBtn.disabled = !input.value.trim();
  });

})();
