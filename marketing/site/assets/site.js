/* i'M On Social marketing site behaviour: nav, mobile sheet, footer accordions, reveal, product tour, demo/contact forms, video lightbox. */
(function () {
  var doc = document.documentElement;
  doc.classList.add('js');
  var API = doc.getAttribute('data-api') || '';
  var PAGE = doc.getAttribute('data-page') || 'site';
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  /* Attribution: keep the first-touch UTMs / click ids / landing page for the whole visit */
  var ATTR_KEY = 'imos_attr';
  var attr = {};
  try { attr = JSON.parse(sessionStorage.getItem(ATTR_KEY) || '{}'); } catch (e) {}
  var qs = new URLSearchParams(location.search);
  var keys = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'gclid', 'fbclid', 'ttclid', 'ref'];
  if (!attr.landing_page) {
    attr.landing_page = location.pathname + location.search;
    attr.referrer = document.referrer || '';
  }
  keys.forEach(function (k) { if (qs.get(k) && !attr[k]) attr[k] = qs.get(k); });
  try { sessionStorage.setItem(ATTR_KEY, JSON.stringify(attr)); } catch (e) {}

  /* Header shadow on scroll */
  var header = $('.site-header');
  var onScroll = function () { if (header) header.classList.toggle('scrolled', window.scrollY > 8); };
  window.addEventListener('scroll', onScroll, { passive: true }); onScroll();

  /* Desktop dropdowns: hover + click + keyboard */
  var items = $$('.nav-item');
  var closeAll = function (except) {
    items.forEach(function (it) {
      if (it === except) return;
      it.classList.remove('open');
      var t = $('.nav-trigger', it); if (t) t.setAttribute('aria-expanded', 'false');
    });
  };
  items.forEach(function (it) {
    var t = $('.nav-trigger', it);
    var timer;
    var open = function () { clearTimeout(timer); closeAll(it); it.classList.add('open'); t.setAttribute('aria-expanded', 'true'); };
    var close = function () { timer = setTimeout(function () { it.classList.remove('open'); t.setAttribute('aria-expanded', 'false'); }, 120); };
    it.addEventListener('mouseenter', function () { if (window.matchMedia('(hover: hover)').matches) open(); });
    it.addEventListener('mouseleave', function () { if (window.matchMedia('(hover: hover)').matches) close(); });
    t.addEventListener('click', function () { it.classList.contains('open') ? (it.classList.remove('open'), t.setAttribute('aria-expanded', 'false')) : open(); });
    it.addEventListener('focusout', function (e) { if (!it.contains(e.relatedTarget)) { it.classList.remove('open'); t.setAttribute('aria-expanded', 'false'); } });
  });
  document.addEventListener('click', function (e) { if (!e.target.closest('.nav-item')) closeAll(); });

  /* Mobile sheet */
  var sheet = $('#mobile-sheet');
  var menuBtn = $('[data-testid="nav-mobile-toggle"]');
  var setSheet = function (on) {
    if (!sheet) return;
    sheet.classList.toggle('open', on);
    sheet.setAttribute('aria-hidden', on ? 'false' : 'true');
    if (menuBtn) menuBtn.setAttribute('aria-expanded', on ? 'true' : 'false');
    document.body.style.overflow = on ? 'hidden' : '';
    if (on) { var c = $('[data-sheet-close]', sheet); if (c) c.focus(); } else if (menuBtn) menuBtn.focus();
  };
  if (menuBtn) menuBtn.addEventListener('click', function () { setSheet(true); });
  $$('[data-sheet-close]').forEach(function (b) { b.addEventListener('click', function () { setSheet(false); }); });
  $$('.sheet a').forEach(function (a) { a.addEventListener('click', function () { setSheet(false); }); });

  /* Smooth scroll to sections on this page */
  $$('[data-scroll]').forEach(function (a) {
    a.addEventListener('click', function (e) {
      var el = document.getElementById(a.getAttribute('data-scroll'));
      if (!el) return;
      e.preventDefault();
      setSheet(false);
      el.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
      history.replaceState(null, '', '#' + el.id);
    });
  });

  /* Footer accordions: closed on phones, open (and locked) on larger screens */
  var mq = window.matchMedia('(max-width: 720px)');
  var syncFooter = function () { $$('.f-col').forEach(function (d) { d.open = !mq.matches; }); };
  syncFooter();
  if (mq.addEventListener) mq.addEventListener('change', syncFooter);

  /* Reveal on scroll */
  var reveals = $$('.reveal');
  if (reduce || !('IntersectionObserver' in window)) {
    reveals.forEach(function (el) { el.classList.add('in'); });
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); } });
    }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
    reveals.forEach(function (el) { io.observe(el); });
  }

  /* Product tour: tabs swap the real screenshot; auto-advance, pause on hover/focus, stop after a manual pick */
  $$('[data-tour]').forEach(function (tour) {
    var tabs = $$('.tour-tab', tour), shots = $$('.tour-shot', tour), cap = $('.tour-caption', tour);
    var MS = 6000, idx = 0, timer = null, started = 0, left = MS, paused = false, inView = false;
    tour.style.setProperty('--tour-ms', MS + 'ms');
    var show = function (i, focus) {
      idx = (i + tabs.length) % tabs.length;
      tabs.forEach(function (t, j) {
        var on = j === idx;
        t.classList.toggle('is-active', on);
        t.setAttribute('aria-selected', on ? 'true' : 'false');
        t.tabIndex = on ? 0 : -1;
        var bar = $('.tt-bar i', t);
        if (bar && on) { bar.style.animation = 'none'; void bar.offsetWidth; bar.style.animation = ''; }
      });
      shots.forEach(function (s, j) { s.classList.toggle('is-active', j === idx); });
      if (cap) cap.textContent = $('.tt-cap', tabs[idx]).textContent;
      var strip = tabs[idx].parentNode;
      if (strip.scrollWidth > strip.clientWidth) strip.scrollTo({ left: tabs[idx].offsetLeft - 24, behavior: reduce ? 'auto' : 'smooth' });
      if (focus) tabs[idx].focus();
    };
    var stop = function () { clearTimeout(timer); timer = null; };
    var run = function (ms) {
      stop();
      if (reduce || tour.classList.contains('manual') || paused || !inView) return;
      started = Date.now(); left = ms;
      timer = setTimeout(function () { show(idx + 1); run(MS); }, ms);
    };
    var pause = function () { if (paused) return; paused = true; tour.classList.add('paused'); if (timer) { left = Math.max(0, left - (Date.now() - started)); stop(); } };
    var resume = function () { if (!paused) return; paused = false; tour.classList.remove('paused'); run(left); };
    tabs.forEach(function (t, j) {
      t.addEventListener('click', function () { tour.classList.add('manual'); stop(); show(j); });
      t.addEventListener('keydown', function (e) {
        if (e.key === 'ArrowDown' || e.key === 'ArrowRight') { e.preventDefault(); tour.classList.add('manual'); stop(); show(idx + 1, true); }
        if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') { e.preventDefault(); tour.classList.add('manual'); stop(); show(idx - 1, true); }
      });
    });
    tour.addEventListener('mouseenter', pause);
    tour.addEventListener('mouseleave', resume);
    tour.addEventListener('focusin', pause);
    tour.addEventListener('focusout', function (e) { if (!tour.contains(e.relatedTarget)) resume(); });
    if (reduce) tour.classList.add('manual');
    show(0);
    if ('IntersectionObserver' in window) {
      new IntersectionObserver(function (en) {
        inView = en[0].isIntersecting;
        if (inView) { show(idx); run(MS); } else stop();
      }, { threshold: 0.35 }).observe(tour);
    }
  });

  /* Modals */
  var lastFocus = null, openModal = null;
  var focusables = function (m) { return $$('a[href],button:not([disabled]),input,select,textarea,video[controls]', m).filter(function (el) { return el.offsetParent !== null; }); };
  var show = function (m) {
    lastFocus = document.activeElement; openModal = m;
    m.classList.add('open'); m.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    setTimeout(function () { var f = focusables(m); var first = f.filter(function (el) { return el.tagName === 'INPUT'; })[0] || f[0]; if (first) first.focus(); }, 60);
  };
  var hide = function (m) {
    m = m || openModal; if (!m) return;
    m.classList.remove('open'); m.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
    var v = $('video', m); if (v) v.pause();
    openModal = null;
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  };
  $$('.modal').forEach(function (m) {
    m.addEventListener('click', function (e) { if (e.target === m) hide(m); });
    $$('[data-modal-close]', m).forEach(function (b) { b.addEventListener('click', function () { hide(m); }); });
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { if (openModal) hide(); else if (sheet && sheet.classList.contains('open')) setSheet(false); else closeAll(); }
    if (e.key === 'Tab' && openModal) {
      var f = focusables(openModal); if (!f.length) return;
      if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
      else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
    }
  });

  var demoModal = $('#demo-modal'), contactModal = $('#contact-modal'), videoModal = $('#video-modal');
  var resetForm = function (m) {
    var form = $('form', m), ok = $('.form-success', m);
    if (form) { form.hidden = false; form.classList.remove('was-validated'); var er = $('.form-error', form); if (er) er.hidden = true; }
    if (ok) ok.hidden = true;
  };
  var demoSource = PAGE + '_direct';
  $$('[data-demo]').forEach(function (b) {
    b.addEventListener('click', function (e) {
      e.preventDefault();
      var src = b.getAttribute('data-demo');
      demoSource = src.indexOf(PAGE) === 0 ? src : PAGE + '_' + src;
      setSheet(false); resetForm(demoModal); show(demoModal);
    });
  });
  $$('[data-contact]').forEach(function (b) { b.addEventListener('click', function (e) { e.preventDefault(); resetForm(contactModal); show(contactModal); }); });
  $$('[data-video]').forEach(function (b) {
    b.addEventListener('click', function () { show(videoModal); var v = $('video', videoModal); if (v) { var p = v.play(); if (p && p.catch) p.catch(function () {}); } });
  });
  if (location.hash === '#demo' && demoModal) show(demoModal);

  var post = function (body) {
    var payload = Object.assign({}, body, {
      utm_source: attr.utm_source || '', utm_medium: attr.utm_medium || '', utm_campaign: attr.utm_campaign || '',
      utm_content: attr.utm_content || '', utm_term: attr.utm_term || '', ref: attr.ref || '',
      referrer: attr.referrer || '', landing_page: attr.landing_page || '', page: location.pathname,
      gclid: attr.gclid || '', fbclid: attr.fbclid || '', ttclid: attr.ttclid || ''
    });
    return fetch(API + '/api/demo-requests', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { if (!r.ok || j.status === 'error') throw new Error(j.message || 'failed'); return j; }); });
  };
  var wire = function (form, build) {
    if (!form) return;
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var err = $('.form-error', form);
      form.classList.add('was-validated');
      if (!form.checkValidity()) {
        err.textContent = 'Please fill in the highlighted fields.'; err.hidden = false;
        var bad = $(':invalid', form); if (bad) bad.focus();
        return;
      }
      err.hidden = true;
      var btn = $('button[type="submit"]', form), txt = btn.textContent;
      btn.disabled = true; btn.textContent = 'Sending...';
      var v = function (n) { var el = form.elements[n]; return el ? (el.type === 'checkbox' ? el.checked : el.value.trim()) : ''; };
      post(build(v)).then(function () {
        var box = form.parentNode.querySelector('.form-success');
        $('[data-first]', box).textContent = v('first_name') || 'there';
        form.hidden = true; box.hidden = false; form.reset();
        var done = $('button', box); if (done) done.focus();
      }).catch(function () {
        err.textContent = "We couldn't reach our server just now. Please try again in a moment, or email sales@imonsocial.com and we'll get you set up.";
        err.hidden = false;
      }).then(function () { btn.disabled = false; btn.textContent = txt; });
    });
  };
  wire($('#demo-form'), function (v) {
    return { name: (v('first_name') + ' ' + v('last_name')).trim(), first_name: v('first_name'), last_name: v('last_name'), email: v('email'), phone: v('phone'),
      company: v('company'), business_type: v('business_type'), team_size: v('team_size'), sms_opt_in: v('sms_opt_in'), source: demoSource, lead_source: demoSource };
  });
  wire($('#contact-form'), function (v) {
    return { name: (v('first_name') + ' ' + v('last_name')).trim(), email: v('email'), phone: v('phone'), message: v('message'),
      sms_opt_in: v('sms_opt_in'), source: PAGE + '_contact_footer', lead_source: 'contact_us' };
  });
})();
