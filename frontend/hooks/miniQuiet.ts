// Realtime mini: what counts as quiet. Mini's caption text runs ahead of her voice and nothing arrives while the rep talks, so quiet is
// measured from the provider's audio and turn events plus running lookups, not from captions. Quiet never hangs up early:
// after the Voice Lab idle_close_s a calm "take your time" hint (only when it is set below AWAY_S), after AWAY_S a visible "Still there?"
// countdown, after AWAY_WARN_S more a quiet end ('away'). Owner choice (Oct 16 2026): end after 20 s of true quiet, countdown from 12 s.
export type Busy = 'jessi' | 'rep' | 'reply' | 'lookup';
export type Quiet = { since: number; busy: Partial<Record<Busy, number>> };
export type QuietLevel = '' | 'hint' | 'warning';

export const AWAY_S = 12;
export const AWAY_WARN_S = 8;
// A busy flag whose stop event never came (lost event, model without output_audio_buffer events) stops counting after this long.
const MAX_BUSY_MS: Record<Busy, number> = { jessi: 90000, rep: 60000, reply: 90000, lookup: 70000 };

export const QUIET_EVENTS: Record<string, [Busy, boolean]> = {
  'output_audio_buffer.started': ['jessi', true], 'output_audio_buffer.stopped': ['jessi', false], 'output_audio_buffer.cleared': ['jessi', false],
  'input_audio_buffer.speech_started': ['rep', true], 'input_audio_buffer.speech_stopped': ['rep', false],
  'response.created': ['reply', true], 'response.done': ['reply', false],
};

export const newQuiet = (now: number): Quiet => ({ since: now, busy: {} });
export const touch = (q: Quiet, now: number) => { q.since = now; };
export const markBusy = (q: Quiet, what: Busy, on: boolean, now: number) => {
  if (on) q.busy[what] = now; else delete q.busy[what];
  q.since = now;
};

// Whole seconds of true quiet right now: 0 while Jessi speaks, the rep speaks, a reply is being made or a lookup runs.
export const quietSeconds = (q: Quiet, now: number): number => {
  let busy = false;
  (Object.keys(q.busy) as Busy[]).forEach(k => {
    if (now - (q.busy[k] as number) < MAX_BUSY_MS[k]) busy = true;
    else delete q.busy[k];
  });
  if (busy) { q.since = now; return 0; }
  return Math.max(0, Math.floor((now - q.since) / 1000));
};

export const quietLevel = (quietS: number, hintS: number): { level: QuietLevel; closeIn: number; end: boolean } => {
  if (quietS >= AWAY_S + AWAY_WARN_S) return { level: 'warning', closeIn: 0, end: true };
  if (quietS >= AWAY_S) return { level: 'warning', closeIn: AWAY_S + AWAY_WARN_S - quietS, end: false };
  if (quietS >= hintS) return { level: 'hint', closeIn: 0, end: false };
  return { level: '', closeIn: 0, end: false };
};
