// Realtime mini captions, keyed by conversation item (pure, no React: see scripts/check-mini-captions.ts).
// The rep's transcript (`conversation.item.input_audio_transcription.completed`) lands AFTER Jessi has started answering; ordering between
// items is not guaranteed. Grouping bubbles by time put the rep's line in the middle of her answer, so her reply looked cut in two
// ("…Focus on your hot" / " leads, clear next steps…") and like two answers. Here the rep row is reserved when speech is detected and
// every bubble is found by item id.
export type CaptionRow = { id: string; role: 'rep' | 'assistant'; text: string; start_ms: number; end_ms: number; rid?: string };

// No letters or digits at all: room noise or the speaker's echo that the transcriber turned into something ("再見"). Not a turn.
export const isNoiseTranscript = (t: string) => !/[A-Za-z0-9\u00C0-\u024F]/.test(t || '');

export const reserveRep = (rows: CaptionRow[], itemId: string, now: number) => {
  if (!itemId || rows.some(r => r.id === itemId)) return;
  rows.push({ id: itemId, role: 'rep', text: '', start_ms: now, end_ms: now });
};

export type RepResult = { final?: CaptionRow; noise?: boolean; sends: any[]; cancelled?: string };
// Noise: the turn is deleted on the server and the answer it started is cancelled, so Jessi never replies to noise.
export const applyRepTranscript = (rows: CaptionRow[], itemId: string, transcript: string, now: number, activeResponse: string): RepResult => {
  const i = rows.findIndex(r => r.id === itemId);
  if (isNoiseTranscript(transcript)) {
    if (i >= 0) rows.splice(i, 1);
    const sends: any[] = itemId ? [{ type: 'conversation.item.delete', item_id: itemId }] : [];
    if (activeResponse) sends.push({ type: 'response.cancel' });
    return { noise: true, sends, cancelled: activeResponse || undefined };
  }
  const text = transcript.trim();
  let row = rows[i];
  if (row) { row.text = text; row.end_ms = now; }
  else { row = { id: itemId || `rep-${now}`, role: 'rep', text, start_ms: now, end_ms: now }; rows.push(row); }
  return { final: row, sends: [] };
};

export const applyAssistantDelta = (rows: CaptionRow[], itemId: string, responseId: string, delta: string, now: number) => {
  const row = itemId ? rows.find(r => r.id === itemId) : undefined;
  if (row) { row.text += delta; row.end_ms = now; return; }
  rows.push({ id: itemId || `assistant-${now}-${rows.length}`, role: 'assistant', text: delta, start_ms: now, end_ms: now, rid: responseId || undefined });
};

// response.done: whatever she started saying to a noise turn vanishes; every other message row of the response is final.
export const finishResponse = (rows: CaptionRow[], response: any, noiseCancelled: string): { rows: CaptionRow[]; final: CaptionRow[]; dropped: boolean } => {
  const id = response?.id || '';
  if (id && noiseCancelled === id) return { rows: rows.filter(r => r.rid !== id), final: [], dropped: true };
  const final = (response?.output || []).map((it: any) => rows.find(r => r.id === it?.id)).filter(Boolean) as CaptionRow[];
  return { rows, final, dropped: false };
};

export const dropUnheard = (rows: CaptionRow[], itemId: string) => {
  const i = rows.findIndex(r => r.id === itemId);
  if (i >= 0 && !rows[i].text) rows.splice(i, 1);
};
