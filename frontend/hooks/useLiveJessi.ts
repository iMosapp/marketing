import { useCallback, useEffect, useRef, useState } from 'react';
import { Platform } from 'react-native';
import api from '../services/api';

export type LiveState = 'idle' | 'connecting' | 'live' | 'ending' | 'ended' | 'error';
export type CaptionRow = { id: string; role: 'rep' | 'assistant'; text: string; start_ms: number; end_ms: number };
export type LiveOptions = { mode: 'assistant' | 'lab'; overrides?: Record<string, any>; contactId?: string };
export type OpenTarget = { kind: 'contact' | 'thread' | 'task' | 'tasks' | 'home' | 'inbox'; id?: string; name?: string; first?: string; contact_id?: string };

const TOOL_LABELS: Record<string, string> = {
  who_today: 'Pulled up your people for today', find_person: 'Looked them up', recall_person: 'Read their history', send_text: 'Text ready to send',
  draft_message: 'Draft ready', set_reminder: 'Reminder set', confirm: 'Sent', cancel: 'Cancelled', answer: 'Answered', open_screen: 'Opened it',
};
const ROW_GAP_MS = 1500;

export const openLabel = (t: OpenTarget) => {
  const who = t.first || (t.name || '').split(' ')[0];
  if (t.kind === 'contact') return who ? `Opened ${who}` : 'Opened the contact';
  if (t.kind === 'thread') return who ? `Opened ${who}'s thread` : 'Opened the thread';
  if (t.kind === 'task') return 'Opened the reminder';
  if (t.kind === 'tasks') return 'Opened your tasks';
  if (t.kind === 'inbox') return 'Opened the inbox';
  return 'Opened Home';
};

export const liveSupported = () =>
  Platform.OS === 'web' && typeof window !== 'undefined' && !!(window as any).RTCPeerConnection && !!(navigator as any)?.mediaDevices?.getUserMedia;

// One live GPT-Live-1 conversation: browser WebRTC for audio, data channel for events, our backend for every fact.
// `onOpen` fires when the backend wants something on the rep's screen (a contact, a thread, a task).
export function useLiveJessi(handlers: { onOpen?: (target: OpenTarget) => void } = {}) {
  const [state, setState] = useState<LiveState>('idle');
  const [rows, setRows] = useState<CaptionRow[]>([]);
  const [error, setError] = useState('');
  const [seconds, setSeconds] = useState(0);
  const [working, setWorking] = useState('');
  const [capLeft, setCapLeft] = useState<number | null>(null);
  const [closeReason, setCloseReason] = useState('');
  const [voice, setVoice] = useState('');
  const onOpenRef = useRef(handlers.onOpen);
  onOpenRef.current = handlers.onOpen;

  const pc = useRef<RTCPeerConnection | null>(null);
  const dc = useRef<RTCDataChannel | null>(null);
  const mic = useRef<MediaStream | null>(null);
  const audioEl = useRef<HTMLAudioElement | null>(null);
  const liveId = useRef('');
  const rowsRef = useRef<CaptionRow[]>([]);
  const queue = useRef<any[]>([]);
  const flushTimer = useRef<any>(null);
  const idleTimer = useRef<any>(null);
  const idleCloseS = useRef(25);
  const secondsRef = useRef(0);
  const finalized = useRef(false);
  const greeting = useRef('');
  const startedAt = useRef(0);
  const tick = useRef<any>(null);
  const closeTimer = useRef<any>(null);
  const startTimer = useRef<any>(null);
  const capRef = useRef<number | null>(null);

  const send = (ev: any) => {
    if (dc.current && dc.current.readyState === 'open') dc.current.send(JSON.stringify(ev));
  };

  const flush = useCallback(async () => {
    if (!liveId.current || queue.current.length === 0) return;
    const batch = queue.current.splice(0, 400);
    try { await api.post(`/live-voice/${liveId.current}/events`, { events: batch }); } catch { /* best effort */ }
  }, []);

  const cleanup = useCallback(() => {
    [flushTimer, idleTimer, tick, closeTimer, startTimer].forEach(t => { if (t.current) { clearTimeout(t.current); clearInterval(t.current); t.current = null; } });
    mic.current?.getTracks().forEach(t => t.stop());
    mic.current = null;
    try { dc.current?.close(); } catch { /* noop */ }
    try { pc.current?.close(); } catch { /* noop */ }
    dc.current = null;
    pc.current = null;
    if (audioEl.current) { audioEl.current.srcObject = null; audioEl.current.remove(); audioEl.current = null; }
  }, []);

  const queueRow = (row: CaptionRow) => queue.current.push({ type: 'transcript', role: row.role, text: row.text, start_ms: row.start_ms, end_ms: row.end_ms });

  const finish = useCallback((reason: string, secs?: number) => {
    if (finalized.current) return;
    finalized.current = true;
    const last = rowsRef.current[rowsRef.current.length - 1];
    if (last) queueRow(last);
    const s = secs ?? secondsRef.current;
    queue.current.push({ type: 'closed', reason, seconds: s });
    setCloseReason(reason);
    setState('ended');
    flush();
    cleanup();
  }, [cleanup, flush]);

  const stop = useCallback((reason = 'close_requested') => {
    if (finalized.current) return;
    if (!dc.current || dc.current.readyState !== 'open') { finish(reason); return; }
    setState('ending');
    setCloseReason(reason);
    send({ type: 'session.close' });
    closeTimer.current = setTimeout(() => finish(reason), 8000);
  }, [finish]);

  const resetIdle = useCallback(() => {
    if (idleTimer.current) clearTimeout(idleTimer.current);
    idleTimer.current = setTimeout(() => stop('idle'), idleCloseS.current * 1000);
  }, [stop]);

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

  const handleDelegation = async (delegationId: string) => {
    setWorking('Working on it');
    send({ type: 'session.thinking.append', event_id: `ack_${delegationId}`, delegation_id: delegationId, content: 'The backend is on it. It takes a few seconds; keep it short while you wait, and never invent the result.' });
    let content = 'Something went wrong on my side pulling that up. Try me again in a second.';
    let opened: OpenTarget | null = null;
    try {
      const transcript = rowsRef.current.map(r => ({ role: r.role, text: r.text }));
      const r = await api.post(`/live-voice/${liveId.current}/delegate`, { delegation_id: delegationId, transcript }, { timeout: 60000 });
      content = r.data?.content || content;
      opened = r.data?.open?.kind ? (r.data.open as OpenTarget) : null;
      setWorking(opened ? openLabel(opened) : (TOOL_LABELS[r.data?.tool] || 'Done'));
    } catch (e: any) {
      if (e?.response?.status === 429 || e?.response?.status === 409) content = e.response.data?.detail || content;
    }
    send({ type: 'session.commentary.append', event_id: `res_${delegationId}`, delegation_id: delegationId, content });
    if (opened) {
      try { onOpenRef.current?.(opened); } catch { /* navigation is best effort */ }
      send({ type: 'session.thinking.append', event_id: `ui_${delegationId}`, delegation_id: null, content: `The app just ${openLabel(opened).toLowerCase()} on the rep's screen; they can see it now.` });
    }
    setTimeout(() => setWorking(''), 1200);
  };

  const onMessage = (raw: string) => {
    let ev: any;
    try { ev = JSON.parse(raw); } catch { return; }
    switch (ev.type) {
      case 'session.started':
        if (startTimer.current) { clearTimeout(startTimer.current); startTimer.current = null; }
        setState('live');
        startedAt.current = Date.now();
        send({ type: 'session.instructions.append', event_id: 'greet_1', delegation_id: null,
          content: `Greet the rep immediately in English without waiting for them to speak. Say, in your own words: "${greeting.current}". Then pause and listen.` });
        tick.current = setInterval(() => { if (!secondsRef.current) setSeconds(Math.round((Date.now() - startedAt.current) / 1000)); }, 1000);
        flushTimer.current = setInterval(flush, 6000);
        resetIdle();
        break;
      case 'session.input_transcript.delta':
        appendCaption('rep', ev.delta || '', ev.start_ms || 0, ev.end_ms || 0);
        break;
      case 'session.output_transcript.delta':
        appendCaption('assistant', ev.delta || '', ev.start_ms || 0, ev.end_ms || 0);
        break;
      case 'session.delegation.created':
        if (ev.delegation?.id && ev.delegation?.target !== 'responses') handleDelegation(ev.delegation.id);
        break;
      case 'session.usage.updated': {
        const s = Number(ev.usage?.seconds || 0);
        secondsRef.current = s;
        setSeconds(s);
        queue.current.push({ type: 'usage', seconds: s });
        if (capRef.current !== null && s >= capRef.current) stop('daily_cap');
        break;
      }
      case 'session.closed':
        if (closeTimer.current) { clearTimeout(closeTimer.current); closeTimer.current = null; }
        finish(ev.reason || 'close_requested', Number(ev.usage?.seconds ?? secondsRef.current));
        break;
      case 'error': {
        const msg = ev.error?.message || 'Live session error';
        queue.current.push({ type: 'error', message: msg });
        if (!/append|client_event/i.test(msg)) setError(msg);
        break;
      }
      default:
        break;
    }
  };

  const start = useCallback(async (opts: LiveOptions) => {
    if (!liveSupported()) { setError('Live Jessi needs a browser with a microphone (Chrome, Safari or Edge).'); setState('error'); return; }
    finalized.current = false;
    rowsRef.current = [];
    queue.current = [];
    secondsRef.current = 0;
    liveId.current = '';
    setRows([]); setError(''); setSeconds(0); setWorking(''); setCloseReason(''); setState('connecting');
    try {
      const connection = new RTCPeerConnection();
      pc.current = connection;
      const audio = document.createElement('audio');
      audio.autoplay = true;
      audio.style.display = 'none';
      document.body.appendChild(audio);
      audioEl.current = audio;
      connection.addEventListener('track', (e: any) => {
        audio.srcObject = e.streams?.[0] || new MediaStream([e.track]);
        audio.play().catch(() => { /* autoplay blocked: user already tapped, so this rarely fires */ });
      });
      mic.current = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } as any });
      mic.current.getAudioTracks().forEach(t => connection.addTrack(t, mic.current as MediaStream));
      const channel = connection.createDataChannel('oai-events');
      dc.current = channel;
      channel.addEventListener('message', (e: any) => onMessage(e.data));
      channel.addEventListener('close', () => { if (!finalized.current) finish('connection_lost'); });
      connection.addEventListener('connectionstatechange', () => {
        if (['failed', 'disconnected'].includes(connection.connectionState) && !finalized.current) finish('connection_lost');
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
      const r = await api.post('/live-voice/session', { mode: opts.mode, sdp, overrides: opts.overrides || null, contact_id: opts.contactId || null }, { timeout: 40000 });
      liveId.current = r.data.live_id;
      greeting.current = r.data.greeting || 'Hey, it is Jessi.';
      idleCloseS.current = Number(r.data.idle_close_s || 25);
      capRef.current = r.data.cap_left_s ?? null;
      setCapLeft(capRef.current);
      setVoice(r.data.voice || '');
      await connection.setRemoteDescription({ type: 'answer', sdp: r.data.sdp });
      startTimer.current = setTimeout(() => { if (!finalized.current) { setError('Jessi did not pick up. Try again.'); setState('error'); finish('no_start'); } }, 20000);
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.message || 'Could not start the conversation';
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail));
      setState('error');
      finalized.current = true;
      cleanup();
    }
  }, [cleanup, finish]);

  useEffect(() => () => { if (!finalized.current && liveId.current) finish('unmounted'); else cleanup(); }, [cleanup, finish]);

  return { state, rows, error, seconds, working, capLeft, closeReason, voice, start, stop, liveId: liveId.current };
}

export type LiveJessi = ReturnType<typeof useLiveJessi>;
