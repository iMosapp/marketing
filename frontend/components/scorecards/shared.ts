export const GOLD = '#C9A962';
export const GREEN = '#34C759';
export const AMBER = '#FF9500';
export const RED = '#FF3B30';
export const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });

export type Criterion = { id: string; text: string; hint: string; weight: number; critical: boolean };
export type Scorecard = {
  id: string; name: string; department: string; description: string; criteria: Criterion[];
  applies_to: { user_ids: string[]; inbox_ids: string[]; source_ids: string[] };
  is_default: boolean; active: boolean; alert_on_critical: boolean; alert_below_pct: number | null; notify_rep: boolean;
  store_id?: string | null; template_key?: string | null; critical_count: number; calls_30d?: number; avg_30d?: number | null;
};
export type EvalResult = {
  criterion_id: string; text: string; critical: boolean; weight: number; passed: boolean | null; ai_passed: boolean | null;
  evidence: string; confidence: number; override: { by: string; by_name: string; at: string; note?: string } | null;
};
export type Evaluation = {
  id: string; call_sid: string; user_id: string; rep_name: string; contact_id?: string | null; contact_name: string; conversation_id?: string | null;
  scorecard_id: string; scorecard_name: string; department: string; duration_s: number; direction: string; call_at: string;
  results: EvalResult[]; score_pct: number | null; critical_misses: string[]; summary: string; wins: string[]; coaching: string[];
  customer_sentiment: 'positive' | 'neutral' | 'negative'; call_type: string; graded_by: 'ai' | 'manager'; created_at: string;
};
export type RepStats = {
  days: number; count: number; avg_score: number | null; prev_avg: number | null; critical_misses: number; clean_calls: number;
  trend: { week_start: string; label: string; avg: number | null; count: number }[];
  criteria: { id: string; text: string; critical: boolean; passed: number; graded: number; pass_rate: number | null }[];
};

export const scoreTone = (pct: number | null | undefined) => pct == null ? '#8E8E93' : pct >= 80 ? GREEN : pct >= 60 ? AMBER : RED;
export const fmtDur = (s: number) => (s >= 60 ? `${Math.floor(s / 60)}m ${s % 60 ? `${s % 60}s` : ''}`.trim() : `${s}s`);
export const fmtWhen = (iso: string) => {
  const d = new Date(iso);
  const diff = (Date.now() - d.getTime()) / 60000;
  if (diff < 60) return `${Math.max(1, Math.round(diff))}m ago`;
  if (diff < 60 * 24) return `${Math.round(diff / 60)}h ago`;
  if (diff < 60 * 24 * 7) return `${Math.round(diff / 1440)}d ago`;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
};
export const passedCount = (ev: Evaluation) => ({
  passed: ev.results.filter(r => r.passed === true).length,
  graded: ev.results.filter(r => r.passed !== null).length,
});
