// Grouping and searching for the Voice Memos list. Days are the rep's local days (the server only stores the label per day key).
const pad = (n: number) => String(n).padStart(2, '0');

export const dayKey = (iso: string) => {
  const d = new Date(iso);
  return isNaN(d.getTime()) ? 'unknown' : `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
};

export const dayTitle = (key: string) => {
  if (key === 'unknown') return 'Undated';
  const now = new Date();
  const today = dayKey(now.toISOString());
  const y = new Date(now); y.setDate(now.getDate() - 1);
  if (key === today) return 'Today';
  if (key === dayKey(y.toISOString())) return 'Yesterday';
  const [yy, mm, dd] = key.split('-').map(Number);
  const d = new Date(yy, mm - 1, dd);
  return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric', ...(yy !== now.getFullYear() ? { year: 'numeric' } : {}) });
};

export type DayGroup = { key: string; title: string; memos: any[] };

export const groupByDay = (memos: any[]): DayGroup[] => {
  const out: DayGroup[] = [];
  for (const m of memos) {
    const key = dayKey(m.created_at);
    const g = out.find(x => x.key === key);
    if (g) g.memos.push(m); else out.push({ key, title: dayTitle(key), memos: [m] });
  }
  return out;
};

export const memoMatches = (m: any, q: string) => {
  const s = q.trim().toLowerCase();
  if (!s) return true;
  const hay = [m.title, m.summary, m.transcript, m.contact_name, ...(m.tags || []), ...(m.people || []).map((p: any) => `${p.name} ${p.company || ''}`)]
    .filter(Boolean).join(' \n ').toLowerCase();
  return s.split(/\s+/).every(w => hay.includes(w));
};

export const tagsInUse = (memos: any[]) => {
  const seen = new Map<string, string>();
  for (const m of memos) for (const t of m.tags || []) { const k = String(t).toLowerCase(); if (!seen.has(k)) seen.set(k, t); }
  return [...seen.values()].sort((a, b) => a.localeCompare(b));
};
