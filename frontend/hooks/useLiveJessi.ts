import { useCallback, useEffect, useRef, useState } from 'react';
import { Platform } from 'react-native';
import * as Application from 'expo-application';
import api from '../services/api';
import { getRtc, attachRemoteAudio, startAudioSession, stopAudioSession, applyAudioRoute, nativeRtcMissing, nativeRtcReason } from './liveRtc';

export type LiveState = 'idle' | 'connecting' | 'live' | 'switching' | 'ending' | 'ended' | 'error';
export type CaptionRow = { id: string; role: 'rep' | 'assistant'; text: string; start_ms: number; end_ms: number };
export type LiveOptions = { mode: 'assistant' | 'lab' | 'shopper' | 'advisor'; overrides?: Record<string, any>; contactId?: string };
export type OpenTarget = { kind: 'contact' | 'thread' | 'task' | 'tasks' | 'home' | 'inbox' | 'duplicates' | 'mentions' | 'team_today'; id?: string; name?: string; first?: string; contact_id?: string; query?: string; days?: number | null; res?: any; rep?: string; draft?: string };
type Meter = { policy_mode?: 'controls' | 'legacy'; role?: 'premium' | 'backup' | null; fallback_reason?: string | null; left_s?: number | null };

const TOOL_LABELS: Record<string, string> = {
  who_today: 'Pulled up your people for today', find_person: 'Looked them up', recall_person: 'Read their history', send_text: 'Text ready to send',
  draft_message: 'Draft ready', set_reminder: 'Reminder set', confirm: 'Done', cancel: 'Cancelled', answer: 'Answered', open_screen: 'Opened it',
  find_duplicates: 'Checked for duplicates', merge_duplicates: 'Merge ready, say yes', hang_up: 'The shopper hung up', stay_in_character: 'Staying in character',
  next_stop: 'Next stop', find_mentions: 'Searched your conversations',
  call_person: 'Calling, your phone will ring', add_note: 'Note saved', tag_person: 'Tag updated', mark_sold: 'Sale ready, say yes', finish_task: 'Reminder updated',
  update_contact: 'Record updated', book_appointment: 'Appointment ready, say yes', enroll_campaign: 'Enrollment ready, say yes', send_card: 'Text ready to send', advise: 'Advisor answered',
};
const ROW_GAP_MS = 1500;
// Ending because every voice pool is spent: the sheet offers the typed Ask Jessi instead.
export const CAP_REASONS = ['voice_cap', 'backup_cap', 'daily_cap', 'killed'];
export const STANDARD_VOICE_NOTE = "Switched to Jessi's standard voice";

export const openLabel = (t: OpenTarget) => {
  const who = t.first || (t.name || '').split(' ')[0];
  if (t.kind === 'contact') return who ? `Opened ${who}` : 'Opened the contact';
  if (t.kind === 'thread') return who ? `Opened ${who}'s thread` : 'Opened the thread';
  if (t.kind === 'task') return 'Opened the reminder';
  if (t.kind === 'tasks') return 'Opened your tasks';
  if (t.kind === 'inbox') return 'Opened the inbox';
  if (t.kind === 'duplicates') return 'Opened your duplicates';
  if (t.kind === 'mentions') return 'Opened who mentioned it';
  if (t.kind === 'team_today') return t.rep ? `Opened ${t.rep}'s day` : 'Opened your team today';
  return 'Opened Home';
};

// Web: any browser with WebRTC + a mic. Native: only binaries built with react-native-webrtc (older App Store builds get false).
export const liveSupported = () => !!getRtc();
export const liveNeedsAppUpdate = () => Platform.OS !== 'web' && nativeRtcMissing;
export const LIVE_UNSUPPORTED_TITLE = Platform.OS === 'web' ? 'This browser cannot do live voice' : 'This build cannot talk to Jessi yet';
// Native: name the installed binary and the real reason, so "latest TestFlight" claims can be checked against the build number.
export const INSTALLED_BUILD = Platform.OS === 'web' ? '' : `${Application.nativeApplicationVersion || '?'} (${Application.nativeBuildVersion || '?'})`;
export const LIVE_UNSUPPORTED_BODY = Platform.OS === 'web'
  ? 'Live Jessi needs a browser with a microphone (Chrome, Safari or Edge).'
  : `The app build installed on this phone, ${INSTALLED_BUILD}, was compiled without live voice${nativeRtcReason ? ` (${String(nativeRtcReason).replace(/\.$/, '')})` : ''}. An eas update cannot add it: it needs a new App Store or TestFlight build made from the current code. Install that build, or open app.imonsocial.com in Safari to talk to her now.`;
// The server answered but the voice link never came up: nearly always a network that blocks WebRTC (UDP), not Jessi.
export const NO_PICKUP_BODY = 'Jessi did not pick up. The server answered, but the voice connection could not open on this network. Dealership and office Wi-Fi often block it: switch to cellular (or another Wi-Fi) and tap Talk again.';

// One live Jessi conversation: WebRTC for audio (browser or react-native-webrtc), data channel for events, our backend for every fact.
// A conversation can span several provider sessions: when the premium (GPT-Live) pool runs out the server says stop + fallback_engine and
// `handoff` closes the old session (settling its reservation), keeps the microphone, and reconnects to the backup engine seeded with the
// conversation so far. `onOpen` fires when the backend wants something on the rep's screen (a contact, a thread, a task).
export function useLiveJessi(handlers: { onOpen?: (target: OpenTarget) => void } = {}) {
  const [state, setState] = useState<LiveState>('idle');
  const [rows, setRows] = useState<CaptionRow[]>([]);
  const [error, setError] = useState('');
  const [seconds, setSeconds] = useState(0);          // whole conversation, across handoffs (the timer)
  const [segSeconds, setSegSeconds] = useState(0);    // the current provider session (what the cap applies to)
  const [working, setWorking] = useState('');
  const [capLeft, setCapLeft] = useState<number | null>(null);
  const [closeReason, setCloseReason] = useState('');
  const [voice, setVoice] = useState('');
  const [engine, setEngine] = useState<'live' | 'mini'>('live');
  const [note, setNote] = useState('');               // one-line notice in the sheet (the switch to the standard voice)
  const [offerText, setOfferText] = useState(false);  // every voice pool is spent: offer the typed Ask Jessi
  const [handoffs, setHandoffs] = useState(0);
  const onOpenRef = useRef(handlers.onOpen);
  onOpenRef.current = handlers.onOpen;

  const pc = useRef<any>(null);
  const dc = useRef<any>(null);
  const mic = useRef<any>(null);
  const detachAudio = useRef<(() => void) | null>(null);
  const liveId = useRef('');
  const rowsRef = useRef<CaptionRow[]>([]);
  const queuedRowId = useRef('');
  const queue = useRef<any[]>([]);
  const flushTimer = useRef<any>(null);
  const idleTimer = useRef<any>(null);
  const idleCloseS = useRef(25);
  const secondsRef = useRef(0);
  const carriedRef = useRef(0);
  const finalized = useRef(false);
  const handing = useRef(false);
  const greeting = useRef('');
  const greetInstruction = useRef('');
  const openAtStart = useRef<OpenTarget | null>(null);
  const optsRef = useRef<LiveOptions>({ mode: 'assistant' });
  const modeRef = useRef<LiveOptions['mode']>('assistant');
  const startedAt = useRef(0);
  const tick = useRef<any>(null);
  const closeTimer = useRef<any>(null);
  const startTimer = useRef<any>(null);
  const capRef = useRef<number | null>(null);
  const meterRef = useRef<Meter>({});
  const resumedRef = useRef(false);
  // Which voice engine the backend put this session on: GPT-Live (delegation events) or Realtime mini (function calling, token usage).
  const engineRef = useRef<'live' | 'mini'>('live');
  const tokensRef = useRef<Record<string, number>>({ audio_in: 0, audio_in_cached: 0, text_in: 0, text_in_cached: 0, audio_out: 0, text_out: 0 });
  const isMini = () => engineRef.current === 'mini';
  const controlled = () => meterRef.current.policy_mode === 'controls';

  const send = (ev: any) => {
    if (dc.current && dc.current.readyState === 'open') dc.current.send(JSON.stringify(ev));
  };
  // Side context for the model (never spoken as-is): a thinking note on GPT-Live, a system item on Realtime.
  const nudge = (text: string) => isMini()
    ? send({ type: 'conversation.item.create', item: { type: 'message', role: 'system', content: [{ type: 'input_text', text }] } })
    : send({ type: 'session.thinking.append', event_id: `n_${Date.now()}`, delegation_id: null, content: text });
  const sinceStart = () => (startedAt.current ? Date.now() - startedAt.current : 0);

  // Every batch is also the server's metering heartbeat; its answer can carry a stop directive (pool spent) with the engine to continue on.
  const post = async (id: string, batch: any[]) => {
    try {
      const r = await api.post(`/live-voice/${id}/events`, { events: batch });
      return r.data || {};
    } catch { return {}; }
  };
  const flush = useCallback(async () => {
    if (!liveId.current || queue.current.length === 0) return;
    const id = liveId.current;
    const batch = queue.current.splice(0, 400);
    const r = await post(id, batch);
    if (r.stop && id === liveId.current && !finalized.current && !handing.current) onServerStop(r.stop, r.fallback_engine || null);
  }, []);

  const clearTimers = () => {
    [flushTimer, idleTimer, tick, closeTimer, startTimer].forEach(t => { if (t.current) { clearTimeout(t.current); clearInterval(t.current); t.current = null; } });
  };
  // Drop the provider connection but keep the microphone (handoff); `cleanup` drops everything (end of the conversation).
  const dropTransport = () => {
    try { dc.current?.close(); } catch { /* noop */ }
    try { pc.current?.close(); } catch { /* noop */ }
    dc.current = null;
    pc.current = null;
    detachAudio.current?.();
    detachAudio.current = null;
  };
  const cleanup = useCallback(() => {
    clearTimers();
    mic.current?.getTracks().forEach((t: any) => t.stop());
    mic.current = null;
    dropTransport();
    stopAudioSession();
  }, []);

  const queueRow = (row: CaptionRow) => {
    if (queuedRowId.current === row.id) return;
    queuedRowId.current = row.id;
    queue.current.push({ type: 'transcript', role: row.role, text: row.text, start_ms: row.start_ms, end_ms: row.end_ms });
  };

  const finish = useCallback((reason: string, secs?: number) => {
    if (finalized.current) return;
    finalized.current = true;
    handing.current = false;
    const last = rowsRef.current[rowsRef.current.length - 1];
    if (last) queueRow(last);
    const s = secs ?? secondsRef.current;
    if (liveId.current) queue.current.push({ type: 'closed', reason, seconds: s, tokens: isMini() ? { ...tokensRef.current } : undefined });
    setCloseReason(reason);
    if (CAP_REASONS.includes(reason)) setOfferText(true);
    setState('ended');
    flush();
    cleanup();
  }, [cleanup, flush]);

  const stop = useCallback((reason = 'close_requested') => {
    if (finalized.current) return;
    if (handing.current) { finish(reason); return; }
    if (isMini() || !dc.current || dc.current.readyState !== 'open') { finish(reason); return; }
    setState('ending');
    setCloseReason(reason);
    send({ type: 'session.close' });
    closeTimer.current = setTimeout(() => finish(reason), 8000);
  }, [finish]);

  const resetIdle = useCallback(() => {
    if (idleTimer.current) clearTimeout(idleTimer.current);
    idleTimer.current = setTimeout(() => stop('idle'), idleCloseS.current * 1000);
  }, [stop]);

  // The pool for this engine is spent. Premium -> continue on the backup engine; backup (or nothing to fall back to) -> end and offer text.
  const onServerStop = (reason: string, fallback: string | null) => {
    if (finalized.current || handing.current) return;
    if (fallback) { handoff(reason); return; }
    stop(reason === 'premium_cap' ? 'voice_cap' : reason);
  };
  const capHit = () => {
    if (!controlled()) { stop('daily_cap'); return; }
    if (meterRef.current.role === 'premium') handoff('premium_cap');
    else stop('backup_cap');
  };

  const appendCaption = (role: 'rep' | 'assistant', delta: string, start_ms: number, end_ms: number) => {
    const list = rowsRef.current;
    const last = list[list.length - 1];
    if (last && last.role === role && start_ms - last.end_ms < ROW_GAP_MS) {
      last.text += delta;
      last.end_ms = Math.max(last.end_ms, end_ms);
    } else {
      if (last) queueRow(last);
      list.push({ id: `${role}-${start_ms}-${list.length}`, role, text: delta, start_ms, end_ms });
    }
    rowsRef.current = list.slice(-80);
    setRows([...rowsRef.current]);
    resetIdle();
  };

  // One backend round trip. GPT-Live hands us a delegation id; Realtime mini hands us a function call (call_id + what the rep asked for).
  const handleDelegation = async (delegationId: string, request?: string) => {
    const shopper = modeRef.current === 'shopper';
    const mini = isMini();
    setWorking(shopper ? 'Thinking' : 'Working on it');
    if (!shopper && !mini) send({ type: 'session.thinking.append', event_id: `ack_${delegationId}`, delegation_id: delegationId, content: 'The backend is on it. It takes a few seconds; keep it short while you wait, and never invent the result.' });
    let content = 'Something went wrong on my side pulling that up. Try me again in a second.';
    let opened: OpenTarget | null = null;
    let kind = 'commentary';
    let end = false;
    try {
      const transcript = rowsRef.current.map(r => ({ role: r.role, text: r.text }));
      // Realtime: the rep's words can still be in transcription when the call fires, so the model's own summary goes in as the latest line.
      const lastRep = [...transcript].reverse().find(t => t.role === 'rep');
      if (request && !(lastRep && lastRep.text.toLowerCase().includes(request.toLowerCase().slice(0, 40)))) transcript.push({ role: 'rep', text: request });
      const r = await api.post(`/live-voice/${liveId.current}/delegate`, { delegation_id: delegationId, transcript }, { timeout: 60000 });
      content = r.data?.content || content;
      kind = r.data?.kind === 'thinking' ? 'thinking' : 'commentary';
      end = !!r.data?.end;
      opened = r.data?.open?.kind ? (r.data.open as OpenTarget) : null;
      setWorking(opened ? openLabel(opened) : (TOOL_LABELS[r.data?.tool] || 'Done'));
    } catch (e: any) {
      if (e?.response?.status === 429 || e?.response?.status === 409) content = e.response.data?.detail || content;
    }
    if (mini) {
      const output = kind === 'thinking' ? `GUIDANCE for your next words (do not read this label aloud): ${content}` : `SAY THIS TO THE REP in your own voice, keep every name and number, add nothing: ${content}`;
      send({ type: 'conversation.item.create', item: { type: 'function_call_output', call_id: delegationId, output } });
      if (opened) nudge(`The app just ${openLabel(opened).toLowerCase()} on the rep's screen; they can see it now.`);
      send({ type: 'response.create' });
    } else {
      send({ type: kind === 'thinking' ? 'session.thinking.append' : 'session.commentary.append', event_id: `res_${delegationId}`, delegation_id: delegationId, content });
      if (opened) nudge(`The app just ${openLabel(opened).toLowerCase()} on the rep's screen; they can see it now.`);
    }
    if (opened) { try { onOpenRef.current?.(opened); } catch { /* navigation is best effort */ } }
    if (end) setTimeout(() => stop('close_requested'), 2500);
    setTimeout(() => setWorking(''), 1200);
  };

  const onStarted = () => {
    if (startTimer.current) { clearTimeout(startTimer.current); startTimer.current = null; }
    setState('live');
    startedAt.current = Date.now();
    applyAudioRoute();
    const greet = greetInstruction.current || `Greet the rep immediately in English without waiting for them to speak. Say, in your own words: "${greeting.current}". Then pause and listen.`;
    if (isMini()) send({ type: 'response.create', response: { instructions: greet } });
    else send({ type: 'session.instructions.append', event_id: 'greet_1', delegation_id: null, content: greet });
    if (resumedRef.current) { setNote(STANDARD_VOICE_NOTE); setWorking(''); }
    if (openAtStart.current) {
      const target = openAtStart.current; openAtStart.current = null;
      setTimeout(() => { try { onOpenRef.current?.(target); } catch { /* best effort */ } }, 1500);
    }
    tick.current = setInterval(() => {
      const s = Math.round(sinceStart() / 1000);
      if (isMini()) {
        secondsRef.current = s;
        setSegSeconds(s);
        setSeconds(carriedRef.current + s);
        if (capRef.current !== null && s >= capRef.current) capHit();
      } else if (!secondsRef.current) { setSegSeconds(s); setSeconds(carriedRef.current + s); }
    }, 1000);
    flushTimer.current = setInterval(() => {
      // mini: seconds + tokens; GPT-Live: the last provider seconds. Either way the server gets a heartbeat and can answer with a stop.
      queue.current.push({ type: 'usage', seconds: secondsRef.current, tokens: isMini() ? { ...tokensRef.current } : undefined });
      flush();
    }, 6000);
    resetIdle();
  };

  // Realtime mini bills tokens, not minutes: keep a running total from every response.done so the desk can price the session.
  const addUsage = (u: any) => {
    if (!u) return;
    const inD = u.input_token_details || {};
    const cached = inD.cached_tokens_details || {};
    const outD = u.output_token_details || {};
    const t = tokensRef.current;
    t.audio_in_cached += Number(cached.audio_tokens || 0);
    t.text_in_cached += Number(cached.text_tokens || 0);
    t.audio_in += Math.max(0, Number(inD.audio_tokens || 0) - Number(cached.audio_tokens || 0));
    t.text_in += Math.max(0, Number(inD.text_tokens || 0) - Number(cached.text_tokens || 0));
    t.audio_out += Number(outD.audio_tokens || 0);
    t.text_out += Number(outD.text_tokens || 0);
  };

  const onMessage = (raw: string) => {
    let ev: any;
    try { ev = JSON.parse(raw); } catch { return; }
    switch (ev.type) {
      case 'session.started':
      case 'session.created':
        onStarted();
        break;
      case 'session.input_transcript.delta':
        appendCaption('rep', ev.delta || '', ev.start_ms || 0, ev.end_ms || 0);
        break;
      case 'session.output_transcript.delta':
        appendCaption('assistant', ev.delta || '', ev.start_ms || 0, ev.end_ms || 0);
        break;
      case 'conversation.item.input_audio_transcription.completed':
        if (ev.transcript) appendCaption('rep', ev.transcript, sinceStart(), sinceStart());
        break;
      case 'response.output_audio_transcript.delta':
        appendCaption('assistant', ev.delta || '', sinceStart(), sinceStart());
        break;
      case 'input_audio_buffer.speech_started':
        setWorking('');
        resetIdle();
        break;
      case 'response.done': {
        addUsage(ev.response?.usage);
        for (const item of ev.response?.output || []) {
          if (item?.type !== 'function_call' || item.name !== 'delegate') continue;
          let request = '';
          try { request = String(JSON.parse(item.arguments || '{}').request || ''); } catch { /* keep empty */ }
          handleDelegation(item.call_id, request);
        }
        break;
      }
      case 'session.delegation.created':
        if (ev.delegation?.id && ev.delegation?.target !== 'responses') handleDelegation(ev.delegation.id);
        break;
      case 'session.usage.updated': {
        const s = Number(ev.usage?.seconds || 0);
        secondsRef.current = s;
        setSegSeconds(s);
        setSeconds(carriedRef.current + s);
        queue.current.push({ type: 'usage', seconds: s });
        if (capRef.current !== null && s >= capRef.current) capHit();
        break;
      }
      case 'session.closed':
        if (closeTimer.current) { clearTimeout(closeTimer.current); closeTimer.current = null; }
        if (handing.current) break; // we closed it ourselves to switch engines
        finish(ev.reason || 'close_requested', Number(ev.usage?.seconds ?? secondsRef.current));
        break;
      case 'error': {
        const msg = ev.error?.message || 'Live session error';
        queue.current.push({ type: 'error', message: msg });
        if (!/append|client_event|active_response|no active response|cancellation/i.test(msg)) setError(msg);
        break;
      }
      default:
        break;
    }
  };

  // Open one provider session over a fresh peer connection. The mic track is reused when it already exists (handoff).
  const connect = async (opts: LiveOptions, resume?: { from: string; reason: string }) => {
    const rtc = getRtc();
    if (!rtc) throw new Error(LIVE_UNSUPPORTED_BODY);
    const connection = new rtc.PeerConnection();
    pc.current = connection;
    detachAudio.current = attachRemoteAudio(connection);
    if (!mic.current) mic.current = await rtc.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } as any });
    mic.current.getAudioTracks().forEach((t: any) => connection.addTrack(t, mic.current));
    const channel = connection.createDataChannel('oai-events');
    dc.current = channel;
    channel.addEventListener('message', (e: any) => { if (dc.current === channel) onMessage(typeof e.data === 'string' ? e.data : String(e.data ?? '')); });
    channel.addEventListener('close', () => { if (dc.current === channel && !finalized.current && !handing.current) finish('connection_lost'); });
    connection.addEventListener('connectionstatechange', () => {
      if (pc.current !== connection || handing.current) return;
      if (!['failed', 'disconnected'].includes(connection.connectionState) || finalized.current) return;
      if (!startedAt.current) {
        queue.current.push({ type: 'error', message: `ICE ${connection.connectionState} before session.started (ice: ${connection.iceConnectionState}, gathering: ${connection.iceGatheringState})` });
        setError(NO_PICKUP_BODY); setState('error');
      }
      finish(startedAt.current ? 'connection_lost' : 'no_start');
    });
    const offer = await connection.createOffer();
    await connection.setLocalDescription(offer);
    if (connection.iceGatheringState !== 'complete') {
      await new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => { connection.removeEventListener('icegatheringstatechange', onState); reject(new Error('Timed out while gathering ICE candidates')); }, 10000);
        function onState() {
          if (connection.iceGatheringState !== 'complete') return;
          clearTimeout(timeout);
          connection.removeEventListener('icegatheringstatechange', onState);
          resolve();
        }
        connection.addEventListener('icegatheringstatechange', onState);
        onState();
      });
    }
    const sdp = connection.localDescription?.sdp;
    if (!sdp) throw new Error('Missing local SDP offer');
    const r = await api.post('/live-voice/session', { mode: opts.mode, sdp, overrides: opts.overrides || null, contact_id: opts.contactId || null, resume_from: resume?.from || null, reason: resume?.reason || null }, { timeout: 40000 });
    if (finalized.current || pc.current !== connection) {
      // the rep ended the conversation while this session was being set up: give its reservation straight back
      try { connection.close(); } catch { /* noop */ }
      post(r.data.live_id, [{ type: 'closed', reason: 'close_requested', seconds: 0 }]);
      return;
    }
    liveId.current = r.data.live_id;
    engineRef.current = r.data.engine === 'mini' ? 'mini' : 'live';
    meterRef.current = r.data.meter || {};
    resumedRef.current = !!resume;
    tokensRef.current = { audio_in: 0, audio_in_cached: 0, text_in: 0, text_in_cached: 0, audio_out: 0, text_out: 0 };
    secondsRef.current = 0;
    startedAt.current = 0;
    queuedRowId.current = '';
    greeting.current = r.data.greeting || 'Hey, it is Jessi.';
    greetInstruction.current = r.data.greet_instruction || '';
    openAtStart.current = r.data.open?.kind ? (r.data.open as OpenTarget) : null;
    idleCloseS.current = Number(r.data.idle_close_s || 25);
    capRef.current = r.data.cap_left_s ?? null;
    setCapLeft(capRef.current);
    setVoice(r.data.voice || '');
    setEngine(engineRef.current);
    await connection.setRemoteDescription(rtc.answer(r.data.sdp));
    startTimer.current = setTimeout(() => {
      if (finalized.current || pc.current !== connection) return;
      queue.current.push({ type: 'error', message: `no session.started after 20 s (engine: ${engineRef.current}, pc: ${connection.connectionState}, ice: ${connection.iceConnectionState}, dc: ${channel.readyState})` });
      setError(NO_PICKUP_BODY); setState('error'); finish('no_start');
    }, 20000);
  };

  // Server-driven engine switch: settle the old session first (its reservation is released before the new one is taken), keep the mic,
  // reconnect to the engine the server picks, seeded with the conversation so far. Nothing left anywhere -> end and offer text.
  const handoff = async (reason: string) => {
    if (handing.current || finalized.current || !liveId.current) return;
    handing.current = true;
    const oldId = liveId.current;
    setState('switching');
    setWorking('Switching voice line');
    clearTimers();
    const last = rowsRef.current[rowsRef.current.length - 1];
    if (last) queueRow(last);
    queue.current.push({ type: 'closed', reason, seconds: secondsRef.current, tokens: isMini() ? { ...tokensRef.current } : undefined });
    const batch = queue.current.splice(0, 400);
    dropTransport();
    await post(oldId, batch);
    carriedRef.current += Math.max(secondsRef.current, Math.round(sinceStart() / 1000));
    try {
      await connect(optsRef.current, { from: oldId, reason });
      setHandoffs(n => n + 1);
    } catch (e: any) {
      const status = e?.response?.status;
      const detail = e?.response?.data?.detail;
      handing.current = false;
      liveId.current = '';
      if (status === 429) { finish('voice_cap'); return; }
      setError(typeof detail === 'string' ? detail : (e?.message || 'Could not switch the voice line'));
      finish('handoff_failed');
      return;
    }
    handing.current = false;
  };

  const start = useCallback(async (opts: LiveOptions) => {
    const rtc = getRtc();
    if (!rtc) { setError(LIVE_UNSUPPORTED_BODY); setState('error'); return; }
    optsRef.current = opts;
    modeRef.current = opts.mode;
    finalized.current = false;
    handing.current = false;
    rowsRef.current = [];
    queue.current = [];
    secondsRef.current = 0;
    carriedRef.current = 0;
    startedAt.current = 0;
    liveId.current = '';
    meterRef.current = {};
    setRows([]); setError(''); setSeconds(0); setSegSeconds(0); setWorking(''); setCloseReason(''); setNote(''); setOfferText(false); setHandoffs(0); setState('connecting');
    try {
      startAudioSession();
      await connect(opts);
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.message || 'Could not start the conversation';
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail));
      if (e?.response?.status === 429) setOfferText(true);
      setState('error');
      finalized.current = true;
      cleanup();
    }
  }, [cleanup, finish]);

  useEffect(() => () => { if (!finalized.current && liveId.current) finish('unmounted'); else cleanup(); }, [cleanup, finish]);

  return { state, rows, error, seconds, segSeconds, working, capLeft, closeReason, voice, engine, note, offerText, handoffs, start, stop, liveId: liveId.current };
}

export type LiveJessi = ReturnType<typeof useLiveJessi>;
