(function(){
  // Jessi Chat Widget — i'M On Social
  var API_BASE = window.IMOS_API || '';
  var CLOSED_KEY = 'imos_chat_closed';
  var SESSION_KEY = 'imos_chat_session';

  if (sessionStorage.getItem(CLOSED_KEY) === '1') return;

  // === CSS ===
  var style = document.createElement('style');
  style.textContent = [
    // Bubble
    '#imos-chat-bubble{position:fixed;bottom:24px;right:24px;z-index:99999;width:56px;height:56px;border-radius:50%;background:#007AFF;color:#fff;border:none;cursor:pointer;box-shadow:0 4px 20px rgba(0,122,255,.35);display:flex;align-items:center;justify-content:center;transition:transform .25s,box-shadow .25s;font-size:0;-webkit-tap-highlight-color:transparent}',
    '#imos-chat-bubble:hover{transform:scale(1.08);box-shadow:0 6px 28px rgba(0,122,255,.45)}',
    '#imos-chat-bubble svg{width:26px;height:26px;fill:#fff}',
    '#imos-chat-bubble .pulse{position:absolute;top:-3px;right:-3px;width:14px;height:14px;background:#34C759;border:2.5px solid #fff;border-radius:50%}',

    // Panel — desktop
    '#imos-chat-panel{position:fixed;bottom:24px;right:24px;z-index:99999;width:380px;max-width:calc(100vw - 32px);height:520px;max-height:calc(100vh - 48px);border-radius:20px;background:#fff;box-shadow:0 20px 60px rgba(0,0,0,.18);display:none;flex-direction:column;overflow:hidden;font-family:Inter,-apple-system,BlinkMacSystemFont,sans-serif;animation:imos-up .3s ease}',
    '@keyframes imos-up{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}',

    // Header
    '#imos-chat-panel .ch-head{background:#007AFF;color:#fff;padding:14px 16px;display:flex;align-items:center;gap:12px;flex-shrink:0}',
    '#imos-chat-panel .ch-head .av{width:36px;height:36px;border-radius:50%;background:rgba(255,255,255,.2);display:flex;align-items:center;justify-content:center;font-size:15px;font-weight:700;flex-shrink:0}',
    '#imos-chat-panel .ch-head .info{flex:1;min-width:0}',
    '#imos-chat-panel .ch-head .info .name{font-size:15px;font-weight:700}',
    '#imos-chat-panel .ch-head .info .status{font-size:12px;opacity:.8}',
    '#imos-chat-panel .ch-close{background:none;border:none;color:#fff;cursor:pointer;width:44px;height:44px;border-radius:12px;display:flex;align-items:center;justify-content:center;transition:background .15s;flex-shrink:0;-webkit-tap-highlight-color:transparent}',
    '#imos-chat-panel .ch-close:hover{background:rgba(255,255,255,.2)}',
    '#imos-chat-panel .ch-close svg{width:20px;height:20px;fill:#fff}',

    // Body
    '#imos-chat-panel .ch-body{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:10px;background:#F8F9FB;-webkit-overflow-scrolling:touch}',
    '#imos-chat-panel .ch-body::-webkit-scrollbar{width:4px}',
    '#imos-chat-panel .ch-body::-webkit-scrollbar-thumb{background:rgba(0,0,0,.12);border-radius:4px}',

    // Messages
    '.ch-msg{max-width:82%;padding:10px 14px;border-radius:16px;font-size:14px;line-height:1.5;word-break:break-word}',
    '.ch-msg.jessi{background:#fff;color:#111;border:1px solid rgba(0,0,0,.06);align-self:flex-start;border-bottom-left-radius:4px}',
    '.ch-msg.visitor{background:#007AFF;color:#fff;align-self:flex-end;border-bottom-right-radius:4px}',
    '.ch-msg.typing{background:#fff;border:1px solid rgba(0,0,0,.06);align-self:flex-start;border-bottom-left-radius:4px;display:flex;gap:4px;padding:12px 18px}',
    '.ch-msg.typing span{width:7px;height:7px;border-radius:50%;background:rgba(0,0,0,.25);animation:imos-dot 1.2s infinite}',
    '.ch-msg.typing span:nth-child(2){animation-delay:.2s}',
    '.ch-msg.typing span:nth-child(3){animation-delay:.4s}',
    '@keyframes imos-dot{0%,60%,100%{transform:translateY(0)}30%{transform:translateY(-5px)}}',

    // Footer
    '#imos-chat-panel .ch-foot{padding:10px 12px;border-top:1px solid rgba(0,0,0,.06);display:flex;gap:8px;background:#fff;flex-shrink:0;align-items:center}',
    '#imos-chat-panel .ch-foot input{flex:1;padding:10px 14px;border:1px solid rgba(0,0,0,.1);border-radius:980px;font-size:16px;font-family:inherit;outline:none;transition:border .2s;min-width:0;-webkit-appearance:none}',
    '#imos-chat-panel .ch-foot input:focus{border-color:#007AFF}',
    '#imos-chat-panel .ch-foot button{width:44px;height:44px;min-width:44px;border-radius:50%;background:#007AFF;color:#fff;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:background .2s;flex-shrink:0;-webkit-tap-highlight-color:transparent}',
    '#imos-chat-panel .ch-foot button:hover{background:#0059CC}',
    '#imos-chat-panel .ch-foot button:disabled{background:#ccc;cursor:default}',
    '#imos-chat-panel .ch-foot button svg{width:18px;height:18px;fill:#fff}',

    // Lead capture form
    '.ch-lead-form{background:#fff;border:1px solid rgba(0,0,0,.08);border-radius:16px;padding:18px;align-self:stretch;animation:imos-up .3s ease}',
    '.ch-lead-form p{font-size:14px;color:#111;font-weight:600;margin-bottom:12px;line-height:1.4}',
    '.ch-lead-form input{display:block;width:100%;padding:11px 14px;border:1px solid rgba(0,0,0,.12);border-radius:12px;font-size:16px;font-family:inherit;margin-bottom:10px;outline:none;-webkit-appearance:none;box-sizing:border-box}',
    '.ch-lead-form input:focus{border-color:#007AFF}',
    '.ch-lead-form input::placeholder{color:#999}',
    '.ch-lead-form .ch-form-btn{width:100%;padding:12px;border:none;border-radius:12px;background:#007AFF;color:#fff;font-size:15px;font-weight:700;cursor:pointer;font-family:inherit;-webkit-tap-highlight-color:transparent;transition:background .2s}',
    '.ch-lead-form .ch-form-btn:hover{background:#0059CC}',
    '.ch-lead-form .ch-form-btn:disabled{background:#ccc;cursor:default}',
    '.ch-lead-form .ch-form-err{color:#FF3B30;font-size:12px;margin-bottom:8px;display:none}',

    // Mobile — full screen
    '@media(max-width:768px){',
      '#imos-chat-panel{width:100%!important;height:100%!important;max-width:100%!important;max-height:100%!important;bottom:0!important;right:0!important;border-radius:0!important;top:0!important;left:0!important}',
      '#imos-chat-panel .ch-head{padding:16px;padding-top:max(16px,env(safe-area-inset-top))}',
      '#imos-chat-panel .ch-foot{padding:10px 12px;padding-bottom:max(10px,env(safe-area-inset-bottom))}',
      '#imos-chat-panel .ch-foot input{font-size:16px}',
    '}',

    // Nudge
    '#imos-chat-nudge{position:fixed;bottom:90px;right:24px;z-index:99998;background:#fff;border:1px solid rgba(0,0,0,.1);border-radius:16px;padding:10px 14px;box-shadow:0 8px 32px rgba(0,0,0,.12);display:flex;align-items:center;gap:10px;font-family:Inter,-apple-system,BlinkMacSystemFont,sans-serif;animation:imos-up .4s ease;max-width:calc(100vw - 100px)}',
    '#imos-chat-nudge span{font-size:14px;font-weight:500;color:#111;cursor:pointer}',
    '#imos-chat-nudge button{background:none;border:none;font-size:18px;color:#888;cursor:pointer;padding:4px;line-height:1;-webkit-tap-highlight-color:transparent}'
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
      '<input type="text" placeholder="Type a message..." data-testid="chat-widget-input" autocomplete="off" />',
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
  var visitorMsgCount = 0;
  var formShown = false;
  var formCompleted = false;

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

  // === Lead capture form ===
  function showLeadForm() {
    if (formShown) return;
    formShown = true;

    // Disable main input while form is showing
    input.disabled = true;
    input.placeholder = 'Fill out the form above to continue...';

    addMsg("I'd love to keep helping! So we can follow up properly, could you share your info real quick?", 'jessi');

    var form = document.createElement('div');
    form.className = 'ch-lead-form';
    form.setAttribute('data-testid', 'chat-widget-lead-form');
    form.innerHTML = [
      '<p>So a team member can reach out:</p>',
      '<input type="text" placeholder="Your name" data-testid="lead-form-name" autocomplete="name" />',
      '<input type="tel" placeholder="Phone number" data-testid="lead-form-phone" autocomplete="tel" />',
      '<div class="ch-form-err" data-testid="lead-form-error">Please enter your name and phone number</div>',
      '<button class="ch-form-btn" data-testid="lead-form-submit">Continue Chatting</button>'
    ].join('');
    body.appendChild(form);
    body.scrollTop = body.scrollHeight;

    var nameIn = form.querySelector('[data-testid="lead-form-name"]');
    var phoneIn = form.querySelector('[data-testid="lead-form-phone"]');
    var errEl = form.querySelector('.ch-form-err');
    var submitBtn = form.querySelector('.ch-form-btn');

    nameIn.focus();

    submitBtn.addEventListener('click', async function() {
      var name = nameIn.value.trim();
      var phone = phoneIn.value.trim();

      if (!name || !phone) {
        errEl.style.display = 'block';
        return;
      }
      errEl.style.display = 'none';
      submitBtn.disabled = true;
      submitBtn.textContent = 'Saving...';

      // Send to capture endpoint
      try {
        await fetch(API_BASE + '/api/chat/capture', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: sessionId, name: name, phone: phone })
        });
      } catch (e) { /* still continue */ }

      formCompleted = true;
      form.remove();
      input.disabled = false;
      input.placeholder = 'Type a message...';
      input.focus();

      addMsg("Thanks, " + name.split(' ')[0] + "! A team member will follow up with you shortly. Anything else I can help with in the meantime?", 'jessi');
      body.scrollTop = body.scrollHeight;
    });

    // Allow Enter to submit from phone field
    phoneIn.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') submitBtn.click();
    });
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
      return true;
    } catch (e) {
      addMsg("Hi! I'm Jessi — I'll be right with you. Go ahead and type your question!", 'jessi');
      return false;
    }
  }

  async function sendMessage() {
    var text = input.value.trim();
    if (!text || sending) return;

    // Block sending if form is showing but not completed
    if (formShown && !formCompleted) return;

    // Retry session if needed
    if (!sessionId) {
      sending = true;
      sendBtn.disabled = true;
      var ok = await startSession();
      if (!ok) { sending = false; sendBtn.disabled = false; return; }
    }

    sending = true;
    sendBtn.disabled = true;
    input.value = '';
    addMsg(text, 'visitor');
    visitorMsgCount++;
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

      // Show lead form after 2 visitor messages if not yet captured
      if (visitorMsgCount >= 2 && !formShown && !data.lead_captured) {
        setTimeout(function() { showLeadForm(); }, 800);
      }
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
    dismissNudge();
    bubble.style.display = 'none';
    panel.style.display = 'flex';
    input.focus();
    if (!sessionId) startSession();
  });

  // Close
  closeBtn.addEventListener('click', function() {
    panel.style.display = 'none';
    sessionStorage.setItem(CLOSED_KEY, '1');
  });

  // Send
  sendBtn.addEventListener('click', sendMessage);
  input.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') sendMessage();
  });
  input.addEventListener('input', function() {
    sendBtn.disabled = !input.value.trim();
  });

  // === Proactive nudge after 30s ===
  var nudge = null;
  var NUDGE_KEY = 'imos_chat_nudged';

  function dismissNudge() {
    if (nudge) { nudge.remove(); nudge = null; }
  }

  if (!sessionStorage.getItem(NUDGE_KEY)) {
    setTimeout(function() {
      if (panel.style.display === 'flex') return;
      if (sessionStorage.getItem(CLOSED_KEY) === '1') return;

      sessionStorage.setItem(NUDGE_KEY, '1');
      nudge = document.createElement('div');
      nudge.id = 'imos-chat-nudge';
      nudge.setAttribute('data-testid', 'chat-widget-nudge');
      nudge.innerHTML = '<span>Have questions? I\'m here to help!</span><button data-testid="chat-widget-nudge-close">&times;</button>';
      document.body.appendChild(nudge);

      nudge.querySelector('span').addEventListener('click', function() {
        dismissNudge();
        bubble.click();
      });
      nudge.querySelector('button').addEventListener('click', function(e) {
        e.stopPropagation();
        dismissNudge();
      });
      setTimeout(function() { dismissNudge(); }, 8000);
    }, 30000);
  }

})();
