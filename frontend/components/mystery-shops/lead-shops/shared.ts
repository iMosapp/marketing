import { GOLD, GREEN, RED, AMBER, PURPLE, BLUE } from '../shared';
import type { ShopCall } from '../shared';

export type LeadProcess = { first_call_min: number; first_text_min: number; first_email_min: number; channels: string[]; day1_calls: number; follow_up_days: number; must: string[] };
export type LeadSetup = { lead_email: string; lead_website: string; lead_process: LeadProcess; defaults: LeadProcess; windows: { hours: number; label: string }[]; email_ready: boolean; pool: Pool };
export type PoolNumber = { phone: string; status: string; lead_shop_id: string | null; cooling: boolean; cooldown_until: string | null; purchased_at: string | null; monthly_cost_usd: number | null };
export type Pool = { numbers: PoolNumber[]; available: number; in_use: number; cap: number; total: number };
export type LeadEvent = { at: string; since: string | null; channel: string; direction: string; kind: string; summary: string; from?: string; session_id?: string; automated?: boolean };
export type ChannelScore = { required: boolean; count: number; human_count: number; first_minutes: number | null; first_human_minutes: number | null; target_minutes: number; speed_pts: number | null; auto_reply_only: boolean };
export type LeadScore = {
  overall: number; process: number; quality: number | null; parts: Record<string, number>; weights: Record<string, number>; per_channel: Record<string, ChannelScore>;
  day1_calls: number; contact_days: number; want_days: number; no_contact: boolean; timeline: string[]; summary?: string; wins?: string[]; coaching?: string[];
  quality_rows: { session_id: string; channel: string; score_pct: number; summary: string; coaching: string[]; wins: string[] }[]; scored_at: string;
};
export type LeadShop = {
  id: string; client_id: string; status: 'pending_delivery' | 'live' | 'closing' | 'completed'; method: 'adf' | 'manual'; source_name: string; department: string; store_name: string;
  window_hours: number; window_label: string; process: LeadProcess; persona: { name: string; first: string; last: string; email: string; phone: string; offering: string; goals?: string; summary?: string };
  script_title: string; delivery: Record<string, any>; created_at: string; started_at: string | null; expires_at: string | null; closed_at: string | null; close_reason?: string | null;
  score: LeadScore | null; notes?: string; events: LeadEvent[]; counts: Record<string, number>; conversations?: ShopCall[];
  identity_card?: { name: string; first: string; last: string; email: string; phone: string; offering: string; message: string; note: string } | null; adf_preview?: string | null;
};

export const CHANNELS: { key: string; label: string; icon: any }[] = [{ key: 'call', label: 'Call', icon: 'call' }, { key: 'text', label: 'Text', icon: 'chatbubbles' }, { key: 'email', label: 'Email', icon: 'mail' }];
export const LEAD_STATUS: Record<string, { label: string; color: string; icon: any }> = {
  pending_delivery: { label: 'Submit the form', color: AMBER, icon: 'clipboard-outline' }, live: { label: 'Live', color: GREEN, icon: 'radio' },
  closing: { label: 'Grading', color: PURPLE, icon: 'hourglass' }, completed: { label: 'Done', color: BLUE, icon: 'checkmark-circle' },
};
export const isOpen = (s: LeadShop) => s.status === 'pending_delivery' || s.status === 'live' || s.status === 'closing';

export const untilText = (iso?: string | null) => {
  if (!iso) return '';
  const ms = new Date(iso).getTime() - Date.now();
  if (ms <= 0) return 'closing now';
  const h = Math.floor(ms / 3600000); const d = Math.floor(h / 24);
  return d >= 1 ? `${d}d ${h % 24}h left` : h >= 1 ? `${h}h ${Math.floor((ms % 3600000) / 60000)}m left` : `${Math.max(1, Math.floor(ms / 60000))}m left`;
};
export const minsText = (m?: number | null) => (m == null ? 'none' : m < 1 ? 'under 1 min' : m < 60 ? `${Math.round(m)} min` : m < 1440 ? `${Math.floor(m / 60)}h ${Math.round(m % 60)}m` : `${Math.floor(m / 1440)}d ${Math.floor((m % 1440) / 60)}h`);

// First human touch on a channel, minutes since the lead landed (live shops have no score yet, so read the timeline)
export const firstMinutes = (s: LeadShop, ch: string): number | null => {
  if (s.score?.per_channel?.[ch]) return s.score.per_channel[ch].first_human_minutes;
  if (!s.started_at) return null;
  const ev = s.events.find(e => e.channel === ch && (e.direction || 'in') === 'in' && !e.kind.startsWith('late') && !e.automated);
  return ev ? Math.round(((new Date(ev.at).getTime() - new Date(s.started_at).getTime()) / 60000) * 10) / 10 : null;
};
export const channelTone = (s: LeadShop, ch: string) => {
  const m = firstMinutes(s, ch); const target = (s.process as any)[`first_${ch}_min`] as number;
  if (m == null) return s.status === 'completed' ? RED : AMBER;
  return m <= target ? GREEN : m <= target * 4 ? GOLD : RED;
};
export const processText = (p: LeadProcess) => [...CHANNELS.filter(c => p.channels.includes(c.key)).map(c => `${c.label.toLowerCase()} in ${(p as any)[`first_${c.key}_min`]} min`), `${p.day1_calls} call${p.day1_calls === 1 ? '' : 's'} day one`, `follow up ${p.follow_up_days} day${p.follow_up_days === 1 ? '' : 's'}`].join(' · ');
export const PART_LABEL: Record<string, string> = { speed: 'Speed to lead', effort: 'Day-one effort', coverage: 'Channels used', persistence: 'Follow-up days' };
