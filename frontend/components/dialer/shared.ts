import { useCallback, useEffect, useState } from 'react';
import api from '../../services/api';

export { GOLD, GREEN, RED, AMBER, tid, fmtPhone, Sheet, Field, Label, Chip, GoldButton, Stat } from '../mystery-shops/shared';
export const BLUE = '#0A84FF';
export const PURPLE = '#AF52DE';
export const GREY = '#8E8E93';

export type Disposition = { key: string; label: string; outcome: string; promote?: boolean; icon: string; color: string };
export type Counts = Record<string, number> & { total: number; remaining: number };
export type Stats = { dials: number; answered_live: number; abandoned: number; connected: number; voicemail: number; talk_s: number; abandon_rate: number; abandon_limit: number; lines_effective: number; throttled: boolean; dispositions: Record<string, number> };
export type Queue = { ready: number; waiting_window: number; next_open: string | null };
export type Rep = { id: string; name: string; has_phone: boolean; has_number: boolean };
export type Campaign = {
  id: string; name: string; store_id?: string | null; status: 'active' | 'paused' | 'done'; created_by: string; created_at: string;
  audience: 'b2b' | 'b2c'; lines: number; connect_mode: 'instant' | 'press1'; recording: 'off' | 'on'; voicemail: 'skip' | 'rep';
  hours: { start: string; end: string }; max_attempts: number; retry_hours: number; max_per_day: number; allow_registry_b2b: boolean; script: string;
  rep_ids: string[]; caller_id: string; seller_name: string; ghl: { tag: string; push: boolean; pipeline_id: string; stage_id: string };
  counts: Counts; stats?: Stats; queue?: Queue; reps?: Rep[];
};
export type Lead = {
  id: string; phone: string; name: string; first_name: string; last_name: string; company: string; email: string; title: string; city: string; state: string | null; tz: string | null;
  notes: string; source: string; status: string; attempts: number; disposition: string | null; last_outcome: string | null; last_attempt_at: string | null; next_attempt_at: string | null;
  dnc: string | null; contact_id: string | null; ghl_contact_id: string | null; ghl_sync_error?: string | null; local_time: string | null;
};
export type Attempt = {
  id: string; lead_name: string; lead_state: string | null; local_time: string | null; phone: string; status: string; call_status?: string; answered_by?: string | null; answered_live: boolean; abandoned: boolean;
  disposition: string | null; notes?: string; duration_s?: number; talk_s?: number; recording_url?: string | null; started_at: string; connected_at?: string | null; ended_at?: string | null; rep_name?: string; voicemail_detected?: boolean;
};
export type Leg = { attempt_id: string; lead_name: string; state: string | null; status: string; answered_by: string | null; local_time: string | null };
export type SessionView = {
  id: string; status: 'starting' | 'idle' | 'dialing' | 'connected' | 'wrapup' | 'ended'; line: string; message: string | null; end_reason: string | null;
  campaign: { id: string; name: string; connect_mode: string; lines: number; script: string; seller_name: string; voicemail: string; status: string } | null;
  caller_id: string; rep_phone: string; started_at: string; ended_at: string | null;
  stats: { bursts: number; dials: number; connects: number; voicemails: number; abandoned: number; dispositions: number; lines_effective?: number; abandon_rate?: number; throttled?: boolean };
  burst: { id: string; state: string; lines: number; record: boolean; started_at: string; legs: Leg[] } | null;
  current: { attempt: Attempt; lead: Lead | null; needs_disposition: boolean } | null;
  queue: Queue | null; dispositions: Disposition[];
};
export type Rule = { state: string; label: string; hours: string; note: string };
export type Registry = { numbers: number; areas: string[]; last_import_at: string | null; stale: boolean };
export type DialerConfig = {
  available: boolean; is_manager: boolean; live: boolean; dispositions: Disposition[]; max_lines: number; has_phone: boolean; has_number: boolean;
  rules: Rule[]; all_party_states: string[]; active_session_id?: string | null; registry?: Registry;
};

export const LEAD_STATUS: Record<string, { label: string; color: string }> = {
  new: { label: 'Ready', color: '#0A84FF' }, queued: { label: 'Retry later', color: '#8E8E93' }, callback: { label: 'Call back', color: '#C9A962' },
  calling: { label: 'Dialing', color: '#FF9500' }, wrapup: { label: 'Needs outcome', color: '#FF9500' }, done: { label: 'Done', color: '#34C759' }, dnc: { label: 'Do not call', color: '#FF3B30' },
};
export const DNC_LABEL: Record<string, string> = { internal: 'On your Do Not Call list', registry: 'On the National Registry', clear: 'Clear', unscrubbed: 'Not scrubbed (registry not loaded)' };
export const SOURCE_LABEL: Record<string, string> = { csv: 'CSV', ghl: 'GoHighLevel', contacts: 'My contacts' };

export const fmtDur = (s?: number | null) => { const n = Math.max(0, Math.round(s || 0)); return n >= 60 ? `${Math.floor(n / 60)}m ${n % 60}s` : `${n}s`; };
export const fmtWhen = (iso?: string | null) => { if (!iso) return ''; const d = new Date(iso); return d.toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }); };
export const fmtTime = (iso?: string | null) => { if (!iso) return ''; return new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }); };
export const pct = (v?: number | null) => `${((v || 0) * 100).toFixed(1)}%`;

export const useDialerConfig = () => {
  const [config, setConfig] = useState<DialerConfig | null>(null);
  const [error, setError] = useState('');
  const reload = useCallback(async () => {
    try { const r = await api.get('/dialer/config'); setConfig(r.data); setError(''); }
    catch (e: any) { setError(e?.response?.data?.detail || 'Could not load the dialer'); setConfig(null); }
  }, []);
  useEffect(() => { reload(); }, [reload]);
  return { config, error, reload };
};
