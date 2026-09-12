import { Linking, Platform } from 'react-native';
import api from '../../services/api';
import { useAuthStore } from '../../store/authStore';

export const GOLD = '#C9A962';
export const GREEN = '#34C759';
export const AMBER = '#FF9500';
export const RED = '#FF3B30';
export const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });

export type Persona = { name: string; voice: string; summary: string; goals?: string; objections?: string[]; opening_line?: string };
export type Scene = { on_screen: string; voice_over: string; seconds: number };
export type Training = { title: string; runtime_seconds: number; hook: string; scenes: Scene[]; cta: string; notes?: string };
export type Script = {
  id: string; slug?: string; kind: 'phone' | 'training'; category: string; title: string; runtime: string; purpose: string; body: string;
  success_points: string[]; persona: Persona | null; store_id?: string | null; is_store_copy: boolean; customized: boolean; scorecard_id?: string | null;
  training?: Training | null; feature_id?: string; format?: string; created_by_name?: string; updated_at?: string; preview?: string;
};
export type Turn = { role: 'customer' | 'rep'; text: string; audio_url?: string | null; mood?: string | null; at: string };
export type Assignment = {
  id: string; script_id: string; script_title: string; rep_ids: string[]; rep_names: Record<string, string>; due_by: string | null; curveballs: string[]; note: string;
  created_by_name?: string; created_at: string; status: string; completed: Record<string, { session_id: string; evaluation_id: string; score_pct: number | null; adherence_pct: number | null; at: string }>; mine_done?: boolean | null;
};
export type Adherence = { score_pct: number | null; points?: { point: string; hit: boolean; evidence: string }[]; hits: string[]; misses: string[]; coaching: string[]; summary: string };
export type RoleplayResult = {
  evaluation_id: string; score_pct: number | null; scorecard_name: string | null; critical_misses: string[]; adherence: Adherence; summary: string; wins: string[];
  coaching: string[]; customer_sentiment: string; duration_s: number; results: any[];
};

export const VOICES = [{ key: 'female', label: 'Woman' }, { key: 'male', label: 'Man' }, { key: 'young', label: 'Younger' }, { key: 'older', label: 'Older' }];
export const initials = (name?: string) => (name || 'C').split(' ').map(p => p[0]).filter(Boolean).slice(0, 2).join('').toUpperCase();
export const fmtClock = (s: number) => `${Math.floor(s / 60)}:${String(Math.max(0, s) % 60).padStart(2, '0')}`;
export const fmtDate = (iso?: string | null) => {
  if (!iso) return '';
  const d = new Date(iso);
  const today = new Date(); const tmr = new Date(); tmr.setDate(today.getDate() + 1);
  if (d.toDateString() === today.toDateString()) return 'today';
  if (d.toDateString() === tmr.toDateString()) return 'tomorrow';
  return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
};
export const moodTone = (m?: string | null) => (m === 'warm' ? GREEN : m === 'guarded' ? AMBER : m === 'annoyed' ? RED : '#8E8E93');

// Print / save: web opens the PDF in a new tab (browser print), native downloads it and opens the share sheet (Print, Save to Files, AirDrop).
export async function openScriptPdf(script: { id: string; title: string }): Promise<'opened' | 'shared' | 'failed'> {
  const token = useAuthStore.getState().token;
  const url = `${api.defaults.baseURL}/scripts/${script.id}/pdf?t=${encodeURIComponent(token || '')}`;
  if (Platform.OS === 'web') {
    if (typeof window !== 'undefined') window.open(url, '_blank');
    return 'opened';
  }
  try {
    const res = await api.get(`/scripts/${script.id}/pdf`, { responseType: 'arraybuffer', timeout: 60000 });
    const { File, Paths } = await import('expo-file-system');
    const Sharing = await import('expo-sharing');
    const name = `${(script.title || 'script').replace(/[^a-z0-9 _-]/gi, '').trim().replace(/\s+/g, '_') || 'script'}.pdf`;
    const f = new File(Paths.cache, name);
    try { f.create({ overwrite: true } as any); } catch { /* exists */ }
    f.write(new Uint8Array(res.data));
    await Sharing.shareAsync(f.uri, { mimeType: 'application/pdf', UTI: 'com.adobe.pdf', dialogTitle: script.title });
    return 'shared';
  } catch (e) {
    try { await Linking.openURL(url); return 'opened'; } catch { return 'failed'; }
  }
}
