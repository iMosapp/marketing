// Mocked Realtime-mini sessions replayed through the REAL hooks/useLiveJessi.ts (no network, no provider, no cost).
// React, react-native, the API client and WebRTC are faked; timers run on a virtual clock. Run: node scripts/sim-mini-lifecycle.js
require('sucrase/register/ts');
const Module = require('module');
const path = require('path');
const fs = require('fs');

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
  Object.assign(sim, { pcs: [], channels: [], batches: [], state: {}, eventsReply: null, delegateMs: 2000, delegateStatus: 200, sessions: 0, log: [], effects: [],
    micStopped: 0, audioStopped: 0, appListeners: [], quietLog: [] });
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
const track = { stop() { sim.micStopped += 1; } };
const fakeRtc = {
  getRtc: () => ({ PeerConnection: FakePC, getUserMedia: async () => ({ getTracks: () => [track], getAudioTracks: () => [track] }), MediaStream: class {}, answer: sdp => ({ type: 'answer', sdp }) }),
  attachRemoteAudio: () => () => {}, startAudioSession: () => {}, stopAudioSession: () => { sim.audioStopped += 1; }, applyAudioRoute: async () => {}, nativeRtcMissing: false, nativeRtcReason: '',
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
const fakeRN = { Platform: { OS: 'ios' }, AppState: { currentState: 'active', addEventListener: (t, f) => { sim.appListeners.push(f); return { remove: () => { sim.appListeners = sim.appListeners.filter(x => x !== f); } }; } } };
const STATE_NAMES = ['state', 'rows', 'error', 'seconds', 'segSeconds', 'working', 'capLeft', 'closeReason', 'voice', 'engine', 'note', 'offerText', 'handoffs', 'quiet'];
let stateIdx = 0;
const fakeReact = {
  useState: (init) => {
    const name = STATE_NAMES[stateIdx++] || `s${stateIdx}`;
    sim.state[name] = init;
    return [init, v => {
      sim.state[name] = typeof v === 'function' ? v(sim.state[name]) : v;
      if (name === 'state') sim.log.push({ t: now, state: sim.state[name] });
      if (name === 'quiet') sim.quietLog.push({ t: now, ...sim.state.quiet });
    }];
  },
  useRef: (init) => ({ current: init }),
  useCallback: fn => fn,
  useEffect: fn => { sim.effects.push(fn); },
};
const origLoad = Module._load;
Module._load = function (req, parent, isMain) {
  if (parent && /hooks[\\/]useLiveJessi/.test(parent.filename || '')) {
    if (req === 'react') return fakeReact;
    if (req === 'react-native') return fakeRN;
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
const closedEvents = () => sim.batches.flatMap(b => b.events.filter(e => e.type === 'closed'));
const closedAt = () => { const e = sim.log.find(x => x.state === 'ended'); return e ? e.t : null; };
const greetingsSent = () => ch().sent.filter(e => e.type === 'response.create' && e.response?.instructions).length;

// Jessi answers: text is generated in genMs (transcript deltas + response.done), her audio plays in real time for audioMs, then
// output_audio_buffer.stopped (WebRTC). stopped=false: the stop event is lost.
const jessiSays = async (t0, rid, text, genMs, audioMs, output = null, stopped = true) => {
  await at(t0, { type: 'response.created', response: { id: rid } });
  emit({ type: 'output_audio_buffer.started', response_id: rid });
  const words = text.split(' ');
  for (let i = 0; i < words.length; i++) await at(t0 + Math.round((genMs * (i + 1)) / words.length), { type: 'response.output_audio_transcript.delta', item_id: `${rid}_item`, response_id: rid, delta: `${words[i]} ` });
  await at(t0 + genMs + 50, { type: 'response.done', response: { id: rid, output: output || [{ id: `${rid}_item`, type: 'message' }], usage: { input_token_details: { audio_tokens: 200, text_tokens: 2100 }, output_token_details: { audio_tokens: Math.round(audioMs / 50), text_tokens: words.length } } } });
  if (stopped) await at(t0 + audioMs, { type: 'output_audio_buffer.stopped', response_id: rid });
  return t0 + audioMs;
};
const repSays = async (t0, item, speakMs, text) => {
  await at(t0, { type: 'input_audio_buffer.speech_started', item_id: item });
  await at(t0 + speakMs, { type: 'input_audio_buffer.speech_stopped', item_id: item });
  await at(t0 + speakMs + 400, { type: 'conversation.item.input_audio_transcription.completed', item_id: item, transcript: text });
};

const begin = async (o = {}) => {
  reset(); stateIdx = 0; eid = 0;
  sim.sessionResponse = { engine: o.engine || 'mini', sdp: 'v=0 fake answer', idle_close_s: o.idle ?? 15, cap_left_s: o.cap ?? 86400, greeting: 'Hey Alex, who are we talking about today?', listening: null,
    meter: { policy_mode: o.controls ? 'controls' : 'legacy', role: o.controls ? 'backup' : null } };
  const hook = useLiveJessi({});
  sim.cleanups = sim.effects.map(fn => fn()).filter(Boolean);  // mount: run the effects once (AppState listener), keep their cleanups for unmount
  hook.start({ mode: 'assistant' });
  await flush();
  if ((o.engine || 'mini') === 'mini') {
    await at(300, { type: 'session.created' });
    await jessiSays(600, 'r_greet', 'Hey Alex, who are we talking about today?', 900, 3000);
  } else {
    await at(300, { type: 'session.started' });
  }
  return hook;
};
const live = () => sim.state.state === 'live';
const diag = () => (closedEvents()[0] || {}).diag || {};

const results = [];
let failures = 0;
const record = (id, title, facts, pass, verdict) => {
  results.push({ id, title, ...facts, pass, verdict });
  if (!pass) failures += 1;
  console.log(`\n[${id}] ${pass ? 'PASS' : 'FAIL'} ${title}\n  ${Object.entries(facts).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join('\n  ')}\n  => ${verdict}`);
};
const s = (ms) => (ms === null ? null : Math.round(ms / 100) / 10);

(async () => {
  // 1 Normal greeting: one greeting, one provider session.
  await begin();
  await advanceTo(10000);
  record('1', 'Normal greeting', { greetings_sent: greetingsSent(), sessions_created: sim.sessions, state: sim.state.state }, greetingsSent() === 1 && sim.sessions === 1 && live(), 'One greeting, one session');

  // 2 Silence past 15 s after an answer: stays live, calm hint only.
  await begin();
  await repSays(6000, 'u1', 3000, 'What did Sarah buy last time?');
  const endA = await jessiSays(9600, 'r1', 'Sarah Kincaid bought a 2024 Tahoe in May and her Equinox lease ends in March', 1500, 12000);
  await advanceTo(endA + 40000);
  record('2', 'Silence of 40 s after a 12 s answer (production setting 15 s)', { state: sim.state.state, quiet: sim.state.quiet, close_reason: sim.state.closeReason || null }, live() && sim.state.quiet.level === 'hint', 'Still connected; the sheet shows "Still here, take your time"');

  // 3 Longer natural pauses (60 s, then 110 s), with talk in between: never closes.
  await begin();
  await repSays(6000, 'u1', 2000, 'Give me a second to think');
  await jessiSays(8400, 'r1', 'Sure, take your time.', 400, 1500);
  await advanceTo(70000);
  const after60 = sim.state.state;
  await repSays(70000, 'u2', 2000, 'Okay, who is next?');
  await jessiSays(72400, 'r2', 'Mike Tran is next.', 300, 1200);
  await advanceTo(73600 + 110000);
  record('3', 'Natural pauses of 60 s and 110 s', { after_60s_pause: after60, after_110s_pause: sim.state.state, quiet: sim.state.quiet }, after60 === 'live' && live(), 'Both pauses survive (warning only starts at 120 s of true quiet)');

  // 4 Rep talks 30 s without a pause: no cut-off.
  await begin();
  await repSays(6000, 'u1', 30000, 'Long explanation about the Tahoe deal');
  await advanceTo(40000);
  record('4', 'Rep talks for 30 s without pausing', { state: sim.state.state }, live(), 'Not cut off while talking');

  // 5 Long 30 s answer generated in 2 s: not cut off; quiet starts when her audio ends.
  await begin();
  await repSays(6000, 'u1', 2500, 'Walk me through everybody today');
  const p5 = jessiSays(9100, 'r1', 'You have five today. Sarah Kincaid is waiting on the Tahoe, Bud Miller has an overdue follow up, Mike Tran is one of your three, Earl Jones asked about financing and Tanya Reed is a hot lead', 2000, 30000);
  const endB = await p5;
  const midAudio = sim.quietLog.filter(q => q.t > 11200 && q.t < endB && q.level).length;
  await advanceTo(endB + 1000);
  record('5', 'Long 30 s answer whose text arrives in 2 s', { jessi_audio_ends_s: s(endB), quiet_flags_while_she_spoke: midAudio, state_after_answer: sim.state.state, quiet_after_answer: sim.state.quiet.level || 'none' },
    live() && sim.state.quiet.level === '' && midAudio === 0, 'She finishes; no quiet hint while her audio plays; the quiet clock starts after it');

  // 6 Slow lookup (30 s): no cut-off; the result is spoken.
  await begin();
  sim.delegateMs = 30000;
  await repSays(6000, 'u1', 2500, 'Who asked about a Tesla last month?');
  await jessiSays(8900, 'r1', 'One sec.', 300, 900, [{ type: 'function_call', name: 'delegate', call_id: 'call_1', arguments: JSON.stringify({ request: 'who asked about a Tesla last month' }) }]);
  await advanceTo(45000);
  const out6 = ch().sent.find(e => e.item?.type === 'function_call_output');
  record('6', 'Backend lookup takes 30 s', { state: sim.state.state, result_sent_to_model: !!out6, wrapper: out6 ? out6.item.output.slice(0, 95) : null }, live() && !!out6, 'Still live, result handed to Jessi');

  // 7 Interruption: the rep talks over a long answer (audio buffer cleared), then pauses.
  await begin();
  await repSays(6000, 'u1', 2000, 'Tell me about Bud');
  await at(8400, { type: 'response.created', response: { id: 'r1' } });
  emit({ type: 'output_audio_buffer.started', response_id: 'r1' });
  await at(8900, { type: 'response.output_audio_transcript.delta', item_id: 'r1_item', response_id: 'r1', delta: 'Bud Miller came in ' });
  await at(12000, { type: 'input_audio_buffer.speech_started', item_id: 'u2' });
  emit({ type: 'output_audio_buffer.cleared', response_id: 'r1' });
  emit({ type: 'response.done', response: { id: 'r1', status: 'cancelled', output: [{ id: 'r1_item', type: 'message' }] } });
  await at(14000, { type: 'input_audio_buffer.speech_stopped', item_id: 'u2' });
  await at(14400, { type: 'conversation.item.input_audio_transcription.completed', item_id: 'u2', transcript: 'Actually, text him instead' });
  await advanceTo(40000);
  record('7', 'Rep interrupts Jessi, then pauses 25 s', { state: sim.state.state, quiet: sim.state.quiet.level || 'none' }, live(), 'Interruption handled, still connected');

  // 8 Forgotten session: warning at 120 s of quiet, Keep going resets, then a calm end at 150 s.
  const h8 = await begin();
  await advanceTo(3600 + 121000);
  const warn = { ...sim.state.quiet };
  h8.keepGoing(); await flush();
  const afterKeep = sim.state.quiet.level || 'none';
  const t0 = now;
  await advanceTo(t0 + 149000);
  const before = sim.state.state;
  await advanceTo(t0 + 152000);
  record('8', 'Forgotten session: warning, Keep going, then calm end', { warning_at_121s: warn, after_keep_going: afterKeep, live_at_149s: before, close_reason: sim.state.closeReason, closed_at_quiet_s: s(closedAt() - t0), quiet_after_end: sim.state.quiet.level || 'none', diag: diag() },
    warn.level === 'warning' && warn.closeIn > 0 && afterKeep === 'none' && before === 'live' && sim.state.closeReason === 'away' && diag().initiated_by === 'app' && diag().unexpected === false && sim.state.quiet.level === '',
    'Warns with a countdown, Keep going resets it, ends quietly as "away" after 150 s of true quiet');

  // 9 Explicit End: mic, peer connection and audio session released, one close, no new session.
  const h9 = await begin();
  await advanceTo(20000);
  h9.stop('close_requested'); h9.stop('close_requested');
  ch().close();
  sim.cleanups.forEach(f => f());
  await advanceTo(23000);
  record('9', 'Rep taps End (twice), then channel close + unmount', { state: sim.state.state, close_events: closedEvents().length, mic_tracks_stopped: sim.micStopped > 0, pc_state: pc().connectionState, audio_session_stopped: sim.audioStopped > 0, sessions_created: sim.sessions, diag: diag() },
    sim.state.state === 'ended' && closedEvents().length === 1 && sim.micStopped > 0 && pc().connectionState === 'closed' && sim.audioStopped > 0 && sim.sessions === 1 && diag().initiated_by === 'user' && diag().unexpected === false,
    'Everything released once; diagnostics say the rep ended it');

  // 10 Daily allowance still enforced (90 s left).
  await begin({ cap: 90, controls: true });
  for (let k = 0; k < 4; k++) { await repSays(6000 + k * 16000, `w${k}`, 2000, 'And who else?'); await jessiSays(8500 + k * 16000, `rw${k}`, 'Mike Tran is next, he is one of your three today.', 800, 4000); }
  await advanceTo(95000);
  record('10', 'Daily Mini allowance runs out (90 s left)', { close_reason: sim.state.closeReason, closed_at_s: s(closedAt()), diag_by: diag().initiated_by }, sim.state.closeReason === 'backup_cap' && Math.abs(closedAt() - 90300) <= 1000, 'Allowance enforced exactly as before');

  // 11 Server stop in the heartbeat answer still honoured.
  await begin({ controls: true });
  sim.eventsReply = (t) => (t >= 18000 ? { stop: 'backup_cap', fallback_engine: null } : null);
  await advanceTo(40000);
  record('11', 'Server says stop (allowance spent server-side)', { close_reason: sim.state.closeReason, diag_by: diag().initiated_by }, sim.state.closeReason === 'backup_cap' && diag().initiated_by === 'server', 'Stops; diagnostics say the server did it');

  // 12 Provider ends the call (events channel closes, peer still connected).
  await begin();
  await advanceTo(15000);
  ch().close();
  await advanceTo(16000);
  record('12', 'Provider ends the call', { close_reason: sim.state.closeReason, diag: diag() }, diag().initiated_by === 'provider' && diag().unexpected === true && diag().pc_state === 'connected', 'Told apart from a network drop');

  // 13 Network failure.
  await begin();
  await advanceTo(15000);
  pc().setState('failed');
  await advanceTo(16000);
  record('13', 'Network failure (ICE failed)', { close_reason: sim.state.closeReason, diag: diag() }, diag().initiated_by === 'network' && diag().unexpected === true, 'Recorded as network, unexpected');

  // 14 Lost "audio stopped" event: the busy flag expires after 90 s, so a forgotten session still ends.
  await begin();
  await repSays(6000, 'u1', 2000, 'Who is next?');
  await jessiSays(8400, 'r1', 'Mike Tran is next.', 300, 1500, null, false);
  await advanceTo(8400 + 90000 + 151000);
  record('14', 'Audio-stopped event never arrives', { close_reason: sim.state.closeReason, closed_at_s: s(closedAt()) }, sim.state.closeReason === 'away', 'Not stuck open: ends as "away" after the 90 s safety cap + 150 s');

  // 15 App backgrounded and back during a session.
  const h15 = await begin();
  await advanceTo(10000);
  sim.appListeners.forEach(f => f('background'));
  await advanceTo(40000);
  sim.appListeners.forEach(f => f('active'));
  await advanceTo(45000);
  const h15live = sim.state.state;
  h15.stop('close_requested');
  await advanceTo(47000);
  record('15', 'App backgrounded 30 s, then foreground (JS keeps running in the mock)', { state_after_foreground: h15live, diag_backgrounds: diag().backgrounds, diag_app_state: diag().app_state },
    h15live === 'live' && diag().backgrounds === 1 && diag().app_state === 'active', 'No change in behaviour; the background trip is counted in the close diagnostics');

  // 15b Long background (JS paused 200 s, e.g. iOS suspended it): coming back must not end the session on the first tick without a warning.
  const h15b = await begin();
  await advanceTo(10000);
  sim.appListeners.forEach(f => f('background'));
  const savedTimers = new Map(timers); timers.clear(); now = 210000;  // nothing ran for 200 s
  sim.appListeners.forEach(f => f('active'));
  savedTimers.forEach((x, id) => { if (x.every) x.at = now + 1; timers.set(id, x); });
  await advanceTo(215000);
  record('15b', 'Back from a 200 s background with JS paused', { state: sim.state.state, quiet: sim.state.quiet.level || 'none' }, live(), 'Returning to the app counts as activity: no instant away-end');
  h15b.stop('close_requested');

  // 16 Premium (GPT-Live) unchanged: 15 s without captions still closes as idle.
  await begin({ engine: 'live' });
  await advanceTo(14000);
  const live14 = sim.state.state;
  await advanceTo(17000);
  record('16', 'Premium idle behaviour unchanged', { live_at_14s: live14, close_reason: sim.state.closeReason, ending_at_s: s((sim.log.find(x => x.state === 'ending') || {}).t ?? null), quiet: sim.state.quiet.level || 'none' },
    live14 === 'live' && sim.state.closeReason === 'idle' && Math.abs((sim.log.find(x => x.state === 'ending') || {}).t - 15300) <= 1000 && sim.state.quiet.level === '', 'GPT-Live still closes 15 s after the last caption, as before');

  // 17 No unintended session recreation across a long quiet session.
  await begin();
  await advanceTo(3600 + 115000);
  record('17', 'No extra provider sessions during long quiet', { sessions_created: sim.sessions, state: sim.state.state }, sim.sessions === 1 && live(), 'One session only; no reconnects');

  // 18 A failed lookup (409) still clears the lookup flag: the quiet hint comes back, the session stays live.
  await begin();
  sim.delegateStatus = 409; sim.delegateMs = 1500;
  await repSays(6000, 'u1', 2000, 'Pull up Sarah');
  await jessiSays(8400, 'r1', 'One sec.', 300, 900, [{ type: 'function_call', name: 'delegate', call_id: 'call_9', arguments: JSON.stringify({ request: 'pull up Sarah' }) }]);
  await advanceTo(10300);
  await jessiSays(10400, 'r2', 'That did not work, try again.', 300, 2000);
  await advanceTo(12400 + 17000);
  record('18', 'Lookup fails (409) then quiet', { state: sim.state.state, quiet: sim.state.quiet.level || 'none' }, live() && sim.state.quiet.level === 'hint', 'Lookup flag cleared on failure; normal quiet handling resumes');

  fs.mkdirSync('/app/test_reports', { recursive: true });
  fs.writeFileSync('/app/test_reports/mini_lifecycle_sim_after.json', JSON.stringify({ note: 'virtual clock; real hooks/useLiveJessi.ts; fake provider events', passed: results.length - failures, failed: failures, results }, null, 2));
  console.log(`\n${results.length - failures}/${results.length} passed. Written /app/test_reports/mini_lifecycle_sim_after.json`);
  process.exit(failures ? 1 : 0);
})().catch(e => { console.error('SIM FAILED', e); process.exit(1); });
