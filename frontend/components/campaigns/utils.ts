export const GOLD = '#C9A962';
export const GREEN = '#34C759';
export const RED = '#FF3B30';
export const AMBER = '#FF9500';
export const PURPLE = '#AF52DE';
export const tid = (id: string) => ({ testID: id, dataSet: { testid: id } } as any);

export type Touch = {
  id: string;
  actionType: 'message' | 'send_card';
  cardType: string;
  message: string;
  delayMinutes: number;
  delayHours: number;
  delayDays: number;
  delayMonths: number;
  media_urls: string[];
  channel: string;
  ai_generated?: boolean;
  step_context?: string;
};

export const CARD_TYPES = [
  { key: 'congrats', label: 'Congrats', icon: 'gift', color: GOLD },
  { key: 'birthday', label: 'Birthday', icon: 'balloon', color: '#FF2D55' },
  { key: 'anniversary', label: 'Anniversary', icon: 'heart', color: '#FF6B6B' },
  { key: 'thankyou', label: 'Thank You', icon: 'thumbs-up', color: GREEN },
  { key: 'welcome', label: 'Welcome', icon: 'hand-left', color: '#007AFF' },
  { key: 'holiday', label: 'Holiday', icon: 'snow', color: '#5AC8FA' },
];

export const REPLY_MODES = [
  { value: 'auto_reply', label: 'Jessi answers automatically', sub: 'Texts back in your voice, books, and escalates to you when a human is needed. Inbox shows Auto.' },
  { value: 'draft_only', label: 'Jessi drafts, I approve', sub: 'Nothing goes out until you tap send.' },
  { value: 'auto_with_approval', label: 'Auto, then hand to me', sub: 'Jessi warms them up for a few replies, then holds for your approval.' },
  { value: 'off', label: 'I handle replies', sub: 'Plan texts still go out; replies wait for you.' },
];
export const REPLY_SHORT: Record<string, string> = {
  auto_reply: 'Jessi answers replies', draft_only: 'Jessi drafts, you approve', auto_with_approval: 'Jessi answers, then hands to you', off: 'You handle replies',
};

export const DELIVERY_MODES = [
  { value: 'auto', label: 'Sends automatically', sub: 'Goes out from your tracking number on schedule. Never overnight.' },
  { value: 'manual', label: 'Asks me first', sub: 'Each touch becomes a task with the text ready to send.' },
];
export const isAutoDelivery = (mode?: string) => !mode || mode === 'auto' || mode === 'automated';

export const DATE_TYPES = [
  { id: 'birthday', name: 'Birthday', icon: 'gift', color: AMBER, phrase: 'On their birthday' },
  { id: 'anniversary', name: 'Purchase anniversary', icon: 'heart', color: RED, phrase: 'On their purchase anniversary' },
  { id: 'sold_date', name: 'Sold date', icon: 'calendar', color: GREEN, phrase: 'On their sold date' },
];

export const TAG_COLOR: Record<string, string> = { sold: GREEN, working: '#007AFF', met: '#5AC8FA', 'lost contact': AMBER, vip: GOLD, birthday: '#FF2D55', anniversary: PURPLE, hot: RED };
export const tagColor = (tag?: string) => TAG_COLOR[(tag || '').toLowerCase()] || PURPLE;

export type Preset = { label: string; mo: number; d: number; h: number; m: number; firstOnly?: boolean };
export const PRESETS: Preset[] = [
  { label: 'Right away', mo: 0, d: 0, h: 0, m: 0, firstOnly: true },
  { label: '15 min', mo: 0, d: 0, h: 0, m: 15 },
  { label: '1 hour', mo: 0, d: 0, h: 1, m: 0 },
  { label: '1 day', mo: 0, d: 1, h: 0, m: 0 },
  { label: '3 days', mo: 0, d: 3, h: 0, m: 0 },
  { label: '1 week', mo: 0, d: 7, h: 0, m: 0 },
  { label: '2 weeks', mo: 0, d: 14, h: 0, m: 0 },
  { label: '1 month', mo: 1, d: 0, h: 0, m: 0 },
  { label: '3 months', mo: 3, d: 0, h: 0, m: 0 },
  { label: '6 months', mo: 6, d: 0, h: 0, m: 0 },
  { label: '1 year', mo: 12, d: 0, h: 0, m: 0 },
];
export const MIN_FOLLOWUP_MINUTES = 15;

export const touchMinutes = (t: Partial<Touch>) =>
  (t.delayMonths || 0) * 30 * 24 * 60 + (t.delayDays || 0) * 24 * 60 + (t.delayHours || 0) * 60 + (t.delayMinutes || 0);

export const matchPreset = (t: Partial<Touch>) =>
  PRESETS.find(p => p.mo === (t.delayMonths || 0) && p.d === (t.delayDays || 0) && p.h === (t.delayHours || 0) && p.m === (t.delayMinutes || 0));

const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? '' : 's'}`;

// "1 day", "2 weeks", "3 months", "1 hour 30 min"
export const humanDelay = (t: Partial<Touch>) => {
  const mins = touchMinutes(t);
  if (mins === 0) return 'Right away';
  const mo = t.delayMonths || 0, d = t.delayDays || 0, h = t.delayHours || 0, m = t.delayMinutes || 0;
  if (mo && !d && !h && !m) return mo % 12 === 0 ? plural(mo / 12, 'year') : plural(mo, 'month');
  const days = mo * 30 + d;
  if (days && !h && !m) {
    if (days % 365 === 0) return plural(days / 365, 'year');
    if (days % 30 === 0 && days >= 30) return plural(days / 30, 'month');
    return days % 7 === 0 && days >= 7 ? plural(days / 7, 'week') : plural(days, 'day');
  }
  const parts: string[] = [];
  if (days) parts.push(plural(days, 'day'));
  if (h) parts.push(plural(h, 'hour'));
  if (m) parts.push(`${m} min`);
  return parts.join(' ');
};

// Short rail label: "Now", "Day 1", "2 wk", "1 mo", "1 yr", "15 min"
export const whenLabel = (t: Partial<Touch>) => {
  const mins = touchMinutes(t);
  if (mins === 0) return 'Now';
  const mo = t.delayMonths || 0, d = t.delayDays || 0, h = t.delayHours || 0, m = t.delayMinutes || 0;
  if (mo && !d && !h && !m) return mo % 12 === 0 ? `${mo / 12} yr` : `${mo} mo`;
  const days = mo * 30 + d;
  if (days && !h && !m) {
    if (days % 365 === 0) return `${days / 365} yr`;
    if (days % 30 === 0 && days >= 30) return `${days / 30} mo`;
    return days % 7 === 0 && days >= 14 ? `${days / 7} wk` : `Day ${days}`;
  }
  if (!days && h && !m) return `${h} hr`;
  if (!days && !h) return `${m} min`;
  return humanDelay(t);
};

export const whenSentence = (t: Partial<Touch>, trigger: string) =>
  touchMinutes(t) === 0 ? `Right after ${trigger}` : `${humanDelay(t)} after ${trigger}`;

export const planDuration = (touches: Partial<Touch>[]) => {
  if (!touches.length) return '';
  const last = touches.reduce((a, b) => (touchMinutes(b) > touchMinutes(a) ? b : a));
  return touchMinutes(last) === 0 ? 'right away' : humanDelay(last);
};

export const summarizeTouches = (touches: Partial<Touch>[]) => {
  if (!touches.length) return 'No touches yet';
  const dur = planDuration(touches);
  return `${plural(touches.length, 'touch').replace('touchs', 'touches')}${dur && dur !== 'right away' ? ` over ${dur}` : ''}`;
};

export const normalizeTouches = (sequences: any[] | undefined, legacyMessage?: string): Touch[] => {
  const seqs = (sequences || []).map((s: any, idx: number) => ({
    id: String(s.id || idx + 1),
    actionType: (s.action_type || 'message') as Touch['actionType'],
    cardType: s.card_type || '',
    message: s.message_template || s.message || '',
    delayMinutes: s.delay_minutes || 0,
    delayHours: s.delay_hours || 0,
    delayDays: s.delay_days || 0,
    delayMonths: s.delay_months || 0,
    media_urls: s.media_urls || [],
    channel: s.channel || 'sms',
    ai_generated: s.ai_generated,
    step_context: s.step_context,
  }));
  if (!seqs.length && legacyMessage) {
    seqs.push({ id: '1', actionType: 'message', cardType: '', message: legacyMessage, delayMinutes: 0, delayHours: 0, delayDays: 0, delayMonths: 0, media_urls: [], channel: 'sms', ai_generated: false, step_context: '' });
  }
  return seqs.sort((a, b) => touchMinutes(a) - touchMinutes(b));
};

export const touchesToSequences = (touches: Touch[]) =>
  [...touches].sort((a, b) => touchMinutes(a) - touchMinutes(b)).map((t, idx) => ({
    step: idx + 1,
    action_type: t.actionType,
    card_type: t.cardType,
    message_template: t.message,
    delay_hours: t.delayHours,
    delay_days: t.delayDays,
    delay_months: t.delayMonths,
    delay_minutes: t.delayMinutes || 0,
    media_urls: t.media_urls,
    channel: t.channel || 'sms',
    ai_generated: !!t.ai_generated,
    step_context: t.step_context || '',
  }));

export const newTouch = (after?: Touch): Touch => ({
  id: `t${Date.now()}`,
  actionType: 'message',
  cardType: '',
  message: '',
  delayMinutes: 0,
  delayHours: 0,
  delayDays: after ? (after.delayDays || 0) + (after.delayMonths ? 0 : 3) : 0,
  delayMonths: after ? (after.delayMonths || 0) + (after.delayMonths ? 1 : 0) : 0,
  media_urls: [],
  channel: 'sms',
});

export const isDateCampaign = (c: any) => ['birthday', 'anniversary', 'sold_date'].includes(c?.type) || !!c?.date_type;
export const dateTypeOf = (c: any) => c?.date_type || (isDateCampaign(c) ? c.type : '');

export const triggerPhrase = (c: any) => {
  if (isDateCampaign(c)) return DATE_TYPES.find(d => d.id === dateTypeOf(c))?.phrase || 'On a date';
  return c?.trigger_tag ? `When tagged ${c.trigger_tag}` : 'No trigger yet';
};

export const scopeLabel = (c: any) =>
  c?.scope === 'org' ? 'org-wide' : c?.scope === 'account' || c?.scope === 'store' || c?.ownership_level === 'store' ? 'store-wide' : 'personal';

export const planIssues = (c: any): string[] => {
  const out: string[] = [];
  if (!isDateCampaign(c) && !c?.trigger_tag) out.push('No trigger tag');
  const seqs = c?.sequences || [];
  if (!seqs.length) out.push('No touches yet');
  seqs.forEach((s: any, i: number) => {
    if ((s.action_type || 'message') === 'message' && !(s.message_template || s.message || '').trim()) out.push(`Touch ${i + 1} has no message`);
    if (s.action_type === 'send_card' && !s.card_type) out.push(`Touch ${i + 1} has no card picked`);
  });
  return out;
};

export type Sample = { first_name: string; last_name: string; vehicle: string; my_name: string; my_phone: string; company: string };
export const DEFAULT_SAMPLE: Sample = { first_name: 'Brent', last_name: 'Miller', vehicle: 'Tahoe', my_name: 'me', my_phone: '', company: 'the store' };

export const renderSample = (text: string, s: Sample) =>
  (text || '')
    .replace(/\{first_name\}|\{name\}/g, s.first_name)
    .replace(/\{last_name\}/g, s.last_name)
    .replace(/\{full_name\}/g, `${s.first_name} ${s.last_name}`.trim())
    .replace(/\{vehicle\}/g, s.vehicle)
    .replace(/\{my_name\}|\{salesperson_name\}/g, s.my_name)
    .replace(/\{my_phone\}/g, s.my_phone || '(435) 555-0100')
    .replace(/\{company\}/g, s.company)
    .replace(/\{phone\}/g, '(801) 555-0123')
    .replace(/\{email\}/g, `${s.first_name.toLowerCase()}@example.com`)
    .replace(/\{date_sold\}/g, 'last month')
    .replace(/\{review_link\}/g, 'g.page/r/review');

export const initials = (name?: string) => (name || '?').split(' ').filter(Boolean).slice(0, 2).map(w => w[0]?.toUpperCase()).join('') || '?';

export const shortDate = (iso?: string | null) => {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '';
  return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
};
