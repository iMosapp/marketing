// Mocked Realtime-mini sessions replayed through the REAL hooks/useLiveJessi.ts (no network, no provider, no cost).
// React, react-native, the API client and WebRTC are faked; timers run on a virtual clock. Run: node scripts/sim-mini-lifecycle.js
require('sucrase/register/ts');
const Module = require('module');
const path = require('path');

let now = 0;
let seq = 0;
const BASE = 1_800_000_000_000;
const timers = new Map();
global.setTimeout = (fn, ms = 0) => { const id = ++seq; timers.set(id, { at: now + ms, fn, every: 0 }); return id; };
global.setInterval = (fn, ms) => { const id = ++seq; timers.set(id, { at: now + ms, fn, every: ms }); return id; };
global.clearTimeout = global.clearInterval = id => { timers.delete(id); };
Date.now = () => BASE + now;
const tick = () => new Promise(r => setImmediate(r));
const flush = async () => { for (let i = 0; i < 8; i++) await tick(); };
const advanceTo = async (t) => {
  for (;;) {
    let next = null;
    for (const [id, x] of timers) if (x.at <= t && (!next || x.at < next[1].at)) next = [id, x];
    if (!next) break;
    const [id, x] = next;
    now = x.at;
    if (x.every) x.at += x.every; else timers.delete(id);
    x.fn();
    await flush();
  }
  now = t;
  await flush();
};

const sim = {};
const reset = () => {
  timers.clear(); now = 0;
  Object.assign(sim, { pcs: [], channels: [], batches: [], state: {}, eventsReply: null, delegateMs: 2000, delegateStatus: 200, sessions: 0, log: [], effects: [] });
};

class Emitter {
  constructor() { this.l = {}; }
  addEventListener(t, f) { (this.l[t] = this.l[t] || []).push(f); }
  removeEventListener(t, f) { this.l[t] = (this.l[t] || []).filter(x => x !== f); }
  emit(t, e) { (this.l[t] || []).slice().forEach(f => f(e)); }
}
class FakeChannel extends Emitter {
  constructor() { super(); this.readyState = 'open'; this.sent = []; }
  send(s) { const ev = JSON.parse(s); ev._t = now; this.sent.push(ev); }
  close() { if (this.readyState === 'closed') return; this.readyState = 'closed'; setImmediate(() => this.emit('close', {})); }
}
class FakePC extends Emitter {
  constructor() { super(); this.connectionState = 'new'; this.iceConnectionState = 'new'; this.iceGatheringState = 'complete'; this.localDescription = null; sim.pcs.push(this); }
  addTrack() {}
  createDataChannel() { const c = new FakeChannel(); sim.channels.push(c); return c; }
  async createOffer() { return { type: 'offer', sdp: 'v=0 fake offer' }; }
  async setLocalDescription(d) { this.localDescription = d; }
  async setRemoteDescription() { this.connectionState = 'connected'; this.iceConnectionState = 'connected'; }
  close() { this.connectionState = 'closed'; }
  setState(s) { this.connectionState = s; this.iceConnectionState = s; this.emit('connectionstatechange', {}); }
}
const track = { stop() {} };
const fakeRtc = {
  getRtc: () => ({ PeerConnection: FakePC, getUserMedia: async () => ({ getTracks: () => [track], getAudioTracks: () => [track] }), MediaStream: class {}, answer: sdp => ({ type: 'answer', sdp }) }),
  attachRemoteAudio: () => () => {}, startAudioSession: () => {}, stopAudioSession: () => {}, applyAudioRoute: async () => {}, nativeRtcMissing: false, nativeRtcReason: '',
};
const fakeApi = {
  post: async (url, body) => {
    if (url === '/live-voice/session') { sim.sessions += 1; return { data: { ...sim.sessionResponse, live_id: `L${sim.sessions}` } }; }
    if (url.endsWith('/events')) { sim.batches.push({ t: now, events: body.events }); return { data: (sim.eventsReply && sim.eventsReply(now)) || {} }; }
    if (url.endsWith('/delegate')) {
      return new Promise((res, rej) => setTimeout(() => {
        if (sim.delegateStatus === 409) rej({ response: { status: 409, data: { detail: 'That session is closed' } } });
        else res({ data: { content: 'Sarah Kincaid bought a 2024 Tahoe in May.', tool: 'recall_person' } });
      }, sim.delegateMs));
    }
    return { data: {} };
  },
};
const STATE_NAMES = ['state', 'rows', 'error', 'seconds', 'segSeconds', 'working', 'capLeft', 'closeReason', 'voice', 'engine', 'note', 'offerText', 'handoffs'];
let stateIdx = 0;
const fakeReact = {
  useState: (init) => { const name = STATE_NAMES[stateIdx++] || `s${stateIdx}`; sim.state[name] = init; return [init, v => { sim.state[name] = typeof v === 'function' ? v(sim.state[name]) : v; if (name === 'state') sim.log.push({ t: now, state: sim.state[name] }); }]; },
  useRef: (init) => ({ current: init }),
  useCallback: fn => fn,
  useEffect: fn => { sim.effects.push(fn); },
};
const origLoad = Module._load;
Module._load = function (req, parent, isMain) {
  if (parent && /hooks[\\/]useLiveJessi/.test(parent.filename || '')) {
    if (req === 'react') return fakeReact;
    if (req === 'react-native') return { Platform: { OS: 'ios' } };
    if (req === 'expo-application') return { nativeApplicationVersion: '1.0.4', nativeBuildVersion: 'sim' };
    if (req === '../services/api') return { __esModule: true, default: fakeApi };
    if (req === './liveRtc') return fakeRtc;
  }
  return origLoad.apply(this, arguments);
};
const { useLiveJessi } = require(path.join(__dirname, '..', 'hooks', 'useLiveJessi.ts'));

let eid = 0;
const ch = () => sim.channels[sim.channels.length - 1];
const pc = () => sim.pcs[sim.pcs.length - 1];
const emit = (ev) => { const c = ch(); if (c && c.readyState === 'open') c.emit('message', { data: JSON.stringify({ event_id: `ev_${++eid}`, ...ev }) }); };
const at = async (t, ev) => { await advanceTo(t); if (ev) emit(ev); await flush(); };
const closedEvents = () => sim.batches.flatMap(b => b.events.filter(e => e.type === 'closed').map(e => ({ ...e, posted_at: b.t })));
const closedAt = () => { const e = sim.log.find(x => x.state === 'ended'); return e ? e.t : null; };

// Jessi answers: text is generated in genMs (transcript deltas + response.done), the audio plays in real time for audioMs.
const jessiSays = async (t0, rid, text, genMs, audioMs, output = null) => {
  await at(t0, { type: 'response.created', response: { id: rid } });
  emit({ type: 'output_audio_buffer.started', response_id: rid });
  const words = text.split(' ');
  for (let i = 0; i < words.length; i++) await at(t0 + Math.round((genMs * (i + 1)) / words.length), { type: 'response.output_audio_transcript.delta', item_id: `${rid}_item`, response_id: rid, delta: `${words[i]} ` });
  await at(t0 + genMs + 50, { type: 'response.done', response: { id: rid, output: output || [{ id: `${rid}_item`, type: 'message' }], usage: { input_token_details: { audio_tokens: 200, text_tokens: 2100 }, output_token_details: { audio_tokens: Math.round(audioMs / 50), text_tokens: words.length } } } });
  return t0 + audioMs;  // when the rep actually stops hearing her (output_audio_buffer.stopped, which the hook ignores)
};
const repSays = async (t0, item, speakMs, text) => {
  await at(t0, { type: 'input_audio_buffer.speech_started', item_id: item });
  await at(t0 + speakMs, { type: 'input_audio_buffer.speech_stopped', item_id: item });
  await at(t0 + speakMs + 400, { type: 'conversation.item.input_audio_transcription.completed', item_id: item, transcript: text });
};

const begin = async (o = {}) => {
  reset(); stateIdx = 0; eid = 0;
  sim.sessionResponse = { engine: 'mini', sdp: 'v=0 fake answer', idle_close_s: o.idle ?? 25, cap_left_s: o.cap ?? 86400, greeting: 'Hey Alex, it is Jessi. Who are we talking about today?', listening: null,
    meter: { policy_mode: o.controls ? 'controls' : 'legacy', role: o.controls ? 'backup' : null } };
  const hook = useLiveJessi({});
  hook.start({ mode: 'assistant' });
  await flush();
  await at(300, { type: 'session.created' });
  await jessiSays(600, 'r_greet', 'Hey Alex, it is Jessi. Who are we talking about today?', 900, 3600);
  return hook;
};

const results = [];
const record = (id, title, facts, verdict) => { results.push({ id, title, ...facts, verdict }); console.log(`\n[${id}] ${title}\n  ${Object.entries(facts).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join('\n  ')}\n  => ${verdict}`); };
const s = (ms) => ms === null ? null : Math.round(ms / 100) / 10;

(async () => {
  // A: a normal 12 s answer, then the rep thinks. Idle counts from her last transcript delta, not from when her audio ends.
  await begin();
  await repSays(6000, 'u1', 3000, 'What did Sarah buy last time?');
  const audioEndA = await jessiSays(9600, 'r1', 'Sarah Kincaid bought a 2024 Tahoe in May and she mentioned her lease on the Equinox ends in March so she might want a second vehicle soon', 1500, 12000);
  await advanceTo(120000);
  record('A', 'Normal 12 s answer, then the rep pauses to think', { jessi_audio_ends_s: s(audioEndA), session_closed_s: s(closedAt()), close_reason: sim.state.closeReason, quiet_time_rep_actually_got_s: s(closedAt() - audioEndA) },
    sim.state.closeReason === 'idle' ? `Closed as idle only ${s(closedAt() - audioEndA)} s after Jessi stopped talking (setting says 25 s)` : 'not idle');

  // B: a long 30 s answer (read-back, list of people): the idle timer fires while she is still talking.
  await begin();
  await repSays(6000, 'u1', 2500, 'Walk me through everybody I should call today');
  const audioEndB = await jessiSays(9100, 'r1', 'You have five today. Sarah Kincaid is waiting on a reply about the Tahoe, Bud Miller has an overdue follow up, Mike Tran is one of your three, Earl Jones asked about financing and Tanya Reed is a hot lead from the website form this morning', 2000, 30000);
  await advanceTo(60000);
  record('B', 'Long 30 s answer generated in 2 s', { jessi_audio_ends_s: s(audioEndB), session_closed_s: s(closedAt()), close_reason: sim.state.closeReason, cut_while_jessi_speaking: closedAt() !== null && closedAt() < audioEndB },
    closedAt() < audioEndB ? `Cut off WHILE JESSI WAS SPEAKING, ${s(audioEndB - closedAt())} s before her answer ended` : 'not cut');

  // C: the rep talks for 28 s without a 0.7 s pause: speech_started reset the timer once, nothing else arrives until they stop.
  await begin();
  await at(6000, { type: 'input_audio_buffer.speech_started', item_id: 'u1' });
  await advanceTo(34000);
  const closedC = closedAt();
  emit({ type: 'input_audio_buffer.speech_stopped', item_id: 'u1' });
  await advanceTo(40000);
  record('C', 'Rep explains something for 28 s without pausing', { rep_started_s: 6, rep_would_stop_s: 34, session_closed_s: s(closedC), close_reason: sim.state.closeReason },
    closedC !== null && closedC < 34000 ? `Cut off WHILE THE REP WAS SPEAKING at ${s(closedC)} s` : 'not cut');

  // D: a backend lookup that takes 30 s (brain + tools; the client allows 60 s): no caption event in between, so idle fires first.
  await begin();
  sim.delegateMs = 30000;
  await repSays(6000, 'u1', 2500, 'Who asked about a Tesla last month?');
  await jessiSays(8900, 'r1', 'One sec.', 300, 900, [{ type: 'function_call', name: 'delegate', call_id: 'call_1', arguments: JSON.stringify({ request: 'who asked about a Tesla last month' }) }]);
  await advanceTo(60000);
  const outD = ch().sent.filter(e => e.type === 'conversation.item.create' && e.item?.type === 'function_call_output');
  record('D', 'Backend lookup takes 30 s', { delegation_started_s: 9.3, session_closed_s: s(closedAt()), close_reason: sim.state.closeReason, result_delivered_to_model: outD.length > 0 },
    sim.state.closeReason === 'idle' ? `Closed as idle at ${s(closedAt())} s while Jessi was "Working on it"; the result was never spoken` : 'ok');

  // E: a 2 s ICE blip ("disconnected" then back to "connected"), e.g. walking between Wi-Fi access points or a cellular hiccup.
  await begin();
  await repSays(6000, 'u1', 2000, 'Text Bud that I am running late');
  await advanceTo(20000);
  pc().setState('disconnected');
  await flush();
  const closedE = closedAt();
  await advanceTo(22000);
  pc().setState('connected');
  await advanceTo(25000);
  record('E', 'Network blip: ICE disconnected for 2 s, then recovers', { blip_s: 20, session_closed_s: s(closedE), close_reason: sim.state.closeReason },
    closedE === 20000 ? 'Ended immediately as connection_lost; WebRTC would have recovered on its own 2 s later' : 'survived');

  // F: the provider (or the server kill switch) closes the call: the data channel closes. Same label as a network failure.
  await begin();
  await advanceTo(15000);
  emit({ type: 'error', error: { message: 'Session ended by server' } });
  ch().close();
  await advanceTo(16000);
  record('F', 'Provider / server ends the call (data channel closes)', { session_closed_s: s(closedAt()), close_reason: sim.state.closeReason, ui_text: 'The connection dropped' },
    sim.state.closeReason === 'connection_lost' ? 'Indistinguishable from a network failure: both are connection_lost' : 'distinct');

  // G: allowance boundary: 90 s left. The client timer ends the session at 90 s, mid-sentence, with no warning before.
  await begin({ cap: 90, controls: true });
  for (let k = 0; k < 4; k++) { await repSays(6000 + k * 16000, `w${k}`, 2000, 'And who else?'); await jessiSays(8500 + k * 16000, `rw${k}`, 'Mike Tran is next, he is one of your three today.', 800, 4000); }
  await repSays(70000, 'u1', 3000, 'Tell me about Earl');
  const audioEndG = await jessiSays(73600, 'r1', 'Earl Jones came in twice for the Silverado and asked about financing on the second visit and his wife Amy wants a third row', 1500, 18000);
  await advanceTo(100000);
  const warnings = ch() ? ch().sent.filter(e => e._t > 30000 && e._t < 90000 && /minute|time|left|wrap/i.test(JSON.stringify(e))) : [];
  record('G', 'Daily allowance runs out mid-answer (90 s left at start)', { cap_left_s: 90, session_closed_s: s(closedAt()), close_reason: sim.state.closeReason, jessi_audio_would_end_s: s(audioEndG), warnings_before_cutoff: warnings.length },
    `Ended as ${sim.state.closeReason} at ${s(closedAt())} s, ${s(audioEndG - closedAt())} s before her answer ended; ${warnings.length} warnings to the rep or the model before`);

  // H: the server's heartbeat answer says stop (pool spent on the server side, e.g. another device used the minutes).
  await begin({ controls: true });
  sim.eventsReply = (t) => (t >= 18000 ? { stop: 'backup_cap', fallback_engine: null } : null);
  await advanceTo(40000);
  record('H', 'Server heartbeat answer: stop (allowance spent server-side)', { session_closed_s: s(closedAt()), close_reason: sim.state.closeReason, offer_text: sim.state.offerText },
    `Ended at the first heartbeat after the server said stop (${s(closedAt())} s)`);

  // I (real): stop twice + late channel close + unmount -> one closed event.
  reset(); stateIdx = 0; eid = 0;
  sim.sessionResponse = { engine: 'mini', sdp: 'x', idle_close_s: 25, cap_left_s: 86400, greeting: 'Hi', listening: null, meter: { policy_mode: 'legacy' } };
  const h = useLiveJessi({});
  h.start({ mode: 'assistant' }); await flush();
  await at(300, { type: 'session.created' });
  await advanceTo(10000);
  h.stop('close_requested'); h.stop('close_requested');
  ch().close();
  const cleanupFns = sim.effects.map(fn => fn()).filter(Boolean); cleanupFns.forEach(f => f());
  await advanceTo(12000);
  record('I', 'Competing cleanups (End twice, channel close, unmount)', { closed_events_posted: closedEvents().length, close_reason: sim.state.closeReason }, closedEvents().length === 1 ? 'Guarded: one close, first reason wins' : 'DUPLICATE close');

  // J: the server watchdog already closed the session (no heartbeat for 150 s, e.g. JS paused); the call is still up and the next lookup gets 409.
  await begin();
  sim.delegateStatus = 409; sim.delegateMs = 500;
  await repSays(6000, 'u1', 2000, 'Pull up Sarah');
  await jessiSays(8400, 'r1', 'One sec.', 300, 900, [{ type: 'function_call', name: 'delegate', call_id: 'call_9', arguments: JSON.stringify({ request: 'pull up Sarah' }) }]);
  await advanceTo(12000);
  const outJ = ch().sent.find(e => e.type === 'conversation.item.create' && e.item?.type === 'function_call_output');
  record('J', 'Server closed the session (watchdog) but the call is still up', { function_output_sent_to_model: outJ ? outJ.item.output : null, state: sim.state.state },
    'Jessi is told to say "That session is closed" and the call stays open: the rep hears a confusing line, then idle closes it');

  // A15 / D15: the same as A and D with the PRODUCTION setting (jessi_voice.idle_close_s = 15).
  await begin({ idle: 15 });
  await repSays(6000, 'u1', 3000, 'What did Sarah buy last time?');
  const audioEndA15 = await jessiSays(9600, 'r1', 'Sarah Kincaid bought a 2024 Tahoe in May and she mentioned her lease on the Equinox ends in March so she might want a second vehicle soon', 1500, 12000);
  await advanceTo(120000);
  record('A15', 'Normal 12 s answer, production idle_close_s = 15', { jessi_audio_ends_s: s(audioEndA15), session_closed_s: s(closedAt()), close_reason: sim.state.closeReason, quiet_time_rep_actually_got_s: s(closedAt() - audioEndA15) },
    `Closed as idle ${s(closedAt() - audioEndA15)} s after Jessi stopped talking`);
  await begin({ idle: 15 });
  await repSays(6000, 'u1', 2500, 'Who should I call today?');
  const audioEndB15 = await jessiSays(9100, 'r1', 'You have three today. Sarah Kincaid is waiting on a reply about the Tahoe, Bud Miller has an overdue follow up and Mike Tran is one of your three', 1500, 18000);
  await advanceTo(60000);
  record('B15', '18 s answer, production idle_close_s = 15', { jessi_audio_ends_s: s(audioEndB15), session_closed_s: s(closedAt()), close_reason: sim.state.closeReason, cut_while_jessi_speaking: closedAt() < audioEndB15 },
    closedAt() < audioEndB15 ? `Cut off WHILE JESSI WAS SPEAKING, ${s(audioEndB15 - closedAt())} s before her answer ended` : `closed ${s(closedAt() - audioEndB15)} s after she finished`);
  await begin({ idle: 15 });
  sim.delegateMs = 20200;
  await repSays(6000, 'u1', 2500, 'Who asked about a Tesla last month?');
  await jessiSays(8900, 'r1', 'One sec.', 300, 900, [{ type: 'function_call', name: 'delegate', call_id: 'call_1', arguments: JSON.stringify({ request: 'who asked about a Tesla last month' }) }]);
  await advanceTo(60000);
  record('D15', 'Backend lookup takes 20.2 s (seen in production), idle_close_s = 15', { session_closed_s: s(closedAt()), close_reason: sim.state.closeReason, result_delivered_to_model: ch().sent.some(e => e.item?.type === 'function_call_output') },
    sim.state.closeReason === 'idle' ? `Closed as idle at ${s(closedAt())} s, before the 20.2 s lookup returned` : 'ok');
  await begin({ idle: 15 });
  await at(6000, { type: 'input_audio_buffer.speech_started', item_id: 'u1' });
  await advanceTo(40000);
  record('C15', 'Rep talks 18 s without a pause, idle_close_s = 15', { rep_started_s: 6, session_closed_s: s(closedAt()), close_reason: sim.state.closeReason }, `Cut off while the rep was speaking at ${s(closedAt())} s`);

  const fs = require('fs');
  fs.mkdirSync('/app/test_reports', { recursive: true });
  fs.writeFileSync('/app/test_reports/mini_lifecycle_sim.json', JSON.stringify({ ran_at: new Date(BASE).toISOString(), note: 'virtual clock; real hooks/useLiveJessi.ts; fake provider events', results }, null, 2));
  console.log('\nwritten /app/test_reports/mini_lifecycle_sim.json');
})().catch(e => { console.error('SIM FAILED', e); process.exit(1); });
