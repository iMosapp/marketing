// Replays provider event sequences through the live-voice guards (hooks/miniSession.ts) and checks that the greeting, every event and
// every tool call are acted on once. Run: cp scripts/check-mini-opening.ts + hooks/miniSession.ts to a temp dir, sucrase, node (same
// recipe as check-mini-captions).
import { newGuards, routeEvent, traceSend } from '../hooks/miniSession';

let failed = 0;
const check = (name: string, ok: boolean) => { console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}`); if (!ok) failed += 1; };

const replay = (events: any[]) => {
  const g = newGuards();
  const out = events.map((e, i) => routeEvent(g, e, i * 10));
  return { g, out, starts: out.filter(o => o.kind === 'start').length };
};
const call = (id: string, request = 'who should I call today') => ({ type: 'function_call', name: 'delegate', call_id: id, arguments: JSON.stringify({ request }) });

{
  const r = replay([{ type: 'session.created', event_id: 'e1' }, { type: 'session.created', event_id: 'e2' }]);
  check('two session.created with different ids -> one greeting', r.starts === 1 && r.g.dups === 1);
}
{
  const r = replay([{ type: 'session.created', event_id: 'e1' }, { type: 'session.started', event_id: 'e2' }]);
  check('session.created + session.started -> one greeting', r.starts === 1);
}
{
  const r = replay([{ type: 'session.created', event_id: 'e1' }, { type: 'session.created', event_id: 'e1' }]);
  check('same event delivered twice -> handled once, counted', r.starts === 1 && r.out[1].kind === 'skip' && (r.out[1] as any).why === 'dup_event');
}
{
  const r = replay([{ type: 'session.created' }]);
  check('start without event_id still starts once', r.starts === 1);
}
{
  const done = { type: 'response.done', event_id: 'd1', response: { id: 'r1', output: [call('c1')] } };
  const r = replay([{ type: 'session.created', event_id: 'e1' }, done, { ...done, event_id: 'd2' }]);
  const calls = r.out.filter(o => o.kind === 'calls').flatMap((o: any) => o.calls);
  check('response.done with a tool call delivered twice -> one tool result', calls.length === 1 && calls[0].callId === 'c1' && calls[0].request === 'who should I call today');
}
{
  const done = { type: 'response.done', event_id: 'd1', response: { id: 'r1', output: [call('c1'), call('c1')] } };
  const r = replay([done]);
  check('same call_id twice in one response -> one tool result', (r.out[0] as any).calls.length === 1);
}
{
  const r = replay([
    { type: 'response.done', event_id: 'd1', response: { id: 'r1', output: [call('c1')] } },
    { type: 'response.done', event_id: 'd2', response: { id: 'r2', output: [call('c2', 'text Mike')] } },
  ]);
  const calls = r.out.flatMap((o: any) => o.calls || []);
  check('two different tool calls are both answered', calls.length === 2);
}
{
  const r = replay([{ type: 'response.done', event_id: 'd1', response: { id: 'r1', output: [{ type: 'message', id: 'i1' }] } }]);
  check('plain answer passes through', r.out[0].kind === 'pass');
}
{
  const d = { type: 'session.delegation.created', delegation: { id: 'g1', target: 'backend' } };
  const r = replay([{ ...d, event_id: 'x1' }, { ...d, event_id: 'x2' }]);
  check('GPT-Live delegation delivered twice -> handled once', r.out[0].kind === 'delegation' && r.out[1].kind === 'skip');
}
{
  const r = replay([{ type: 'session.delegation.created', event_id: 'x1', delegation: { id: 'g1', target: 'responses' } }]);
  check('GPT-Live responses-target delegation untouched', r.out[0].kind === 'pass');
}
{
  const r = replay([{ type: 'input_audio_buffer.speech_started', event_id: 'a' }, { type: 'response.created', event_id: 'b', response: { id: 'r9' } }]);
  check('interruption events pass through untouched', r.out.every(o => o.kind === 'pass'));
}
{
  const g = newGuards();
  for (let i = 0; i < 100; i += 1) routeEvent(g, { type: 'response.output_audio_transcript.delta', event_id: `t${i}` }, i);
  traceSend(g, 'response.create', 101);
  check('trace is capped at 60 rows', g.trace.length === 60 && g.trace[0].type === 'response.output_audio_transcript.delta');
}
{
  const g = newGuards();
  for (let i = 0; i < 700; i += 1) routeEvent(g, { type: 'x', event_id: `e${i}` }, i);
  const again = routeEvent(g, { type: 'x', event_id: 'e699' }, 800);
  check('dedupe memory is bounded and still catches recent repeats', g.seen.size === 500 && again.kind === 'skip');
}
{
  const g = newGuards();
  routeEvent(g, { type: 'session.created', event_id: 'e1', response: undefined }, 5);
  routeEvent(g, { type: 'response.done', event_id: 'e2', response: { id: 'r1', output: [] } }, 9);
  check('trace keeps type, event id and response id', g.trace[1].type === 'response.done' && g.trace[1].id === 'e2' && g.trace[1].rid === 'r1');
}

console.log(failed ? `\n${failed} mini opening check(s) FAILED` : '\nall mini opening checks passed');
if (failed) process.exit(1);
