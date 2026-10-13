// Replays Realtime mini event sequences through hooks/miniCaptions.ts (no React, no audio).
//   cd frontend && mkdir -p /tmp/mcsrc/hooks /tmp/mcsrc/scripts && cp hooks/miniCaptions.ts /tmp/mcsrc/hooks/ && cp scripts/check-mini-captions.ts /tmp/mcsrc/scripts/ \
//     && npx sucrase /tmp/mcsrc -d /tmp/mc --transforms typescript,imports -q && node /tmp/mc/scripts/check-mini-captions.js
import { CaptionRow, reserveRep, applyRepTranscript, applyAssistantDelta, finishResponse, dropUnheard, isNoiseTranscript } from '../hooks/miniCaptions';

let failures = 0;
const check = (name: string, ok: boolean, detail?: any) => {
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${ok ? '' : '  ' + JSON.stringify(detail)}`);
  if (!ok) failures += 1;
};
const visible = (rows: CaptionRow[]) => rows.filter(r => r.text).map(r => `${r.role}: ${r.text}`);

// 1. The screenshot case: the rep's transcript lands after Jessi has started answering.
{
  const rows: CaptionRow[] = [];
  reserveRep(rows, 'item_rep1', 1000);                                  // input_audio_buffer.speech_started
  applyAssistantDelta(rows, 'item_a1', 'resp_1', 'Focus on your hot', 2500);   // response started before the transcript
  applyAssistantDelta(rows, 'item_a1', 'resp_1', ' leads, clear next steps', 2700);
  const r = applyRepTranscript(rows, 'item_rep1', 'Yeah, tell me what I should do to move some deals forward.', 2800, 'resp_1');
  applyAssistantDelta(rows, 'item_a1', 'resp_1', ', and a fresh angle if they dodge you.', 3000);
  const done = finishResponse(rows, { id: 'resp_1', output: [{ id: 'item_a1', type: 'message' }] }, '');
  check('rep line stays above the whole answer', JSON.stringify(visible(rows)) === JSON.stringify([
    'rep: Yeah, tell me what I should do to move some deals forward.',
    'assistant: Focus on your hot leads, clear next steps, and a fresh angle if they dodge you.',
  ]), visible(rows));
  check('one assistant bubble, not two', rows.filter(r => r.role === 'assistant').length === 1, rows);
  check('rep row is final once the transcript lands', r.final?.id === 'item_rep1' && r.sends.length === 0, r);
  check('assistant row final at response.done', done.final.length === 1 && done.final[0].id === 'item_a1' && !done.dropped, done);
}

// 2. Noise turn ("再見"): the turn is deleted, the answer it started is cancelled and its words vanish.
{
  const rows: CaptionRow[] = [];
  reserveRep(rows, 'item_q', 1000);
  applyRepTranscript(rows, 'item_q', 'Tell me about Sarah.', 1800, '');
  applyAssistantDelta(rows, 'item_a1', 'resp_1', 'Sarah bought a Tahoe in March.', 2500);
  finishResponse(rows, { id: 'resp_1', output: [{ id: 'item_a1', type: 'message' }] }, '');
  reserveRep(rows, 'item_noise', 4000);                                 // echo / room noise detected as speech
  applyAssistantDelta(rows, 'item_a2', 'resp_2', 'First, qualify fast. Who is', 4600);   // model already answering the noise
  const r = applyRepTranscript(rows, 'item_noise', '再見', 4700, 'resp_2');
  check('noise detected', r.noise === true && isNoiseTranscript('再見') && isNoiseTranscript('') && isNoiseTranscript('...'), r);
  check('turn deleted + answer cancelled on the server', JSON.stringify(r.sends) === JSON.stringify([{ type: 'conversation.item.delete', item_id: 'item_noise' }, { type: 'response.cancel' }]) && r.cancelled === 'resp_2', r.sends);
  const done = finishResponse(rows, { id: 'resp_2', status: 'cancelled', output: [{ id: 'item_a2', type: 'message' }] }, r.cancelled || '');
  check('her half-sentence to the noise is gone, the real exchange stays', done.dropped && JSON.stringify(visible(done.rows)) === JSON.stringify(['rep: Tell me about Sarah.', 'assistant: Sarah bought a Tahoe in March.']), visible(done.rows));
  check('real words are never noise', !isNoiseTranscript('Yes') && !isNoiseTranscript('ok') && !isNoiseTranscript('2') && !isNoiseTranscript('José, bel hem') && !isNoiseTranscript('Cutting to'));
}

// 3. Noise with nothing in flight: only the item is deleted (no cancel), nothing on screen.
{
  const rows: CaptionRow[] = [];
  reserveRep(rows, 'item_n', 1000);
  const r = applyRepTranscript(rows, 'item_n', ' … ', 1500, '');
  check('no response to cancel', r.noise === true && r.sends.length === 1 && !r.cancelled && rows.length === 0, r);
}

// 4. Reserved row never reaches the screen before its words; failed transcription removes it; duplicates ignored.
{
  const rows: CaptionRow[] = [];
  reserveRep(rows, 'item_x', 1000);
  reserveRep(rows, 'item_x', 1001);
  check('reserved row invisible and not duplicated', rows.length === 1 && visible(rows).length === 0, rows);
  dropUnheard(rows, 'item_x');
  check('failed transcription drops the reserved row', rows.length === 0, rows);
  reserveRep(rows, 'item_y', 2000);
  applyRepTranscript(rows, 'item_y', 'Hello', 2500, '');
  dropUnheard(rows, 'item_y');
  check('a row with words is never dropped as unheard', rows.length === 1 && rows[0].text === 'Hello', rows);
}

// 5. Transcript without a reserved row (VAD was off) and deltas without item ids still show up, in order.
{
  const rows: CaptionRow[] = [];
  applyAssistantDelta(rows, '', 'resp_g', 'Hey Forest, it is Jessi.', 500);   // greeting, no item id known
  applyRepTranscript(rows, 'item_late', 'Who should I call?', 3000, '');
  applyAssistantDelta(rows, 'item_a9', 'resp_9', 'Start with Sarah.', 3500);
  check('fallback rows keep conversation order', JSON.stringify(visible(rows)) === JSON.stringify(['assistant: Hey Forest, it is Jessi.', 'rep: Who should I call?', 'assistant: Start with Sarah.']), visible(rows));
}

// 6. Barge-in by the rep mid-answer: her answer keeps what was said, the rep's line follows, the next answer is its own bubble.
{
  const rows: CaptionRow[] = [];
  reserveRep(rows, 'item_r1', 1000);
  applyRepTranscript(rows, 'item_r1', 'Give me my day.', 1500, '');
  applyAssistantDelta(rows, 'item_a1', 'resp_1', 'Three stops today. First', 2000);
  reserveRep(rows, 'item_r2', 2400);                                    // rep interrupts
  finishResponse(rows, { id: 'resp_1', status: 'cancelled', output: [{ id: 'item_a1', type: 'message' }] }, '');
  applyAssistantDelta(rows, 'item_a2', 'resp_2', 'Sure, Sarah first.', 3200);
  applyRepTranscript(rows, 'item_r2', 'Skip to Sarah.', 3300, 'resp_2');
  check('interruption keeps order: answer, rep, new answer', JSON.stringify(visible(rows)) === JSON.stringify(['rep: Give me my day.', 'assistant: Three stops today. First', 'rep: Skip to Sarah.', 'assistant: Sure, Sarah first.']), visible(rows));
}

console.log(failures ? `\n${failures} FAILED` : '\nall mini caption checks passed');
process.exit(failures ? 1 : 0);
