// Per-connection guards for the live voice data channel (pure, no React: see scripts/check-mini-opening.ts).
// Production showed the Realtime mini greeting requested twice in one session (two start events reached onStarted, which had no
// once-guard). These guards make the start, every provider event and every tool call happen at most once, and keep a short trace.
export type TraceRow = { t: number; type: string; id?: string; rid?: string; item?: string };
export type SessionGuards = { started: boolean; seen: Set<string>; seenOrder: string[]; calls: Set<string>; trace: TraceRow[]; dups: number };
export type Routed =
  | { kind: 'start' }
  | { kind: 'skip'; why: 'dup_event' | 'dup_start' | 'dup_call' }
  | { kind: 'calls'; calls: { callId: string; request: string }[] }
  | { kind: 'delegation'; id: string }
  | { kind: 'pass' };

const SEEN_LIMIT = 500;
const TRACE_LIMIT = 60;
const START_EVENTS = ['session.started', 'session.created'];

export const newGuards = (): SessionGuards => ({ started: false, seen: new Set(), seenOrder: [], calls: new Set(), trace: [], dups: 0 });

export const traceSend = (g: SessionGuards, type: string, t: number) => {
  if (g.trace.length < TRACE_LIMIT) g.trace.push({ t, type: `>${type}` });
};

const seenBefore = (g: SessionGuards, id: string) => {
  if (!id) return false;
  if (g.seen.has(id)) return true;
  g.seen.add(id);
  g.seenOrder.push(id);
  if (g.seenOrder.length > SEEN_LIMIT) g.seen.delete(g.seenOrder.shift() as string);
  return false;
};

const firstCall = (g: SessionGuards, callId: string) => {
  if (!callId || g.calls.has(callId)) return false;
  g.calls.add(callId);
  return true;
};

// One provider event in: what the hook should do with it. Duplicates are counted, never acted on.
export const routeEvent = (g: SessionGuards, ev: any, t: number): Routed => {
  const id = String(ev?.event_id || '');
  if (seenBefore(g, id)) { g.dups += 1; return { kind: 'skip', why: 'dup_event' }; }
  if (g.trace.length < TRACE_LIMIT) g.trace.push({ t, type: String(ev?.type || ''), id: id || undefined, rid: ev?.response?.id || ev?.response_id || undefined, item: ev?.item_id || ev?.item?.id || undefined });
  const type = ev?.type;
  if (START_EVENTS.includes(type)) {
    if (g.started) { g.dups += 1; return { kind: 'skip', why: 'dup_start' }; }
    g.started = true;
    return { kind: 'start' };
  }
  if (type === 'response.done') {
    const calls: { callId: string; request: string }[] = [];
    for (const item of ev?.response?.output || []) {
      if (item?.type !== 'function_call' || item.name !== 'delegate') continue;
      if (!firstCall(g, item.call_id)) { g.dups += 1; continue; }
      let request = '';
      try { request = String(JSON.parse(item.arguments || '{}').request || ''); } catch { /* keep empty */ }
      calls.push({ callId: item.call_id, request });
    }
    return calls.length ? { kind: 'calls', calls } : { kind: 'pass' };
  }
  if (type === 'session.delegation.created') {
    const did = ev?.delegation?.id;
    if (!did || ev?.delegation?.target === 'responses') return { kind: 'pass' };
    if (!firstCall(g, did)) { g.dups += 1; return { kind: 'skip', why: 'dup_call' }; }
    return { kind: 'delegation', id: did };
  }
  return { kind: 'pass' };
};
