import { GOLD, GREEN, RED, AMBER, PURPLE, BLUE, tid } from '../mystery-shops/shared';

export { GOLD, GREEN, RED, AMBER, PURPLE, BLUE, tid };

export type Who = { id: string; name: string };
export type Statement = { key: string; kind: string; data: { text: string }; status: 'draft' | 'approved'; versions: number; updated_at: string | null; approved_at: string | null };
export type Objective = { key: 'objective'; data: { title: string; why: string; target_date: string | null; progress_pct: number; status: string }; status: string; versions: number };
export type NextAction = { key: 'next_action'; data: { text: string; why: string; state: 'none' | 'set' } };
export type Pillar = { key: string; data: { key: string; name: string; promise: string; capabilities: string[]; outcome: string; purpose: string; status: string; target_customer: string; revenue_opportunity: string; kpis: string[]; enhancements: string[] } };
export type Product = { key: string; data: { key: string; name: string; target: string; promise: string; includes: string[]; problem: string; value_prop: string; readiness: Record<string, string>; pricing: { status: string; notes: string } } };
export type Priority = { id: string; title: string; status: 'proposed' | 'active' | 'paused' | 'completed' | 'replaced'; slot: number | null; pillar: string; product: string; purpose: string; next_action: string; due: string | null; owner: Who; progress_pct: number; definition_of_done: string; created_at: string };
export type Note = { id: string; kind: 'waiting' | 'win'; title: string; party: string; due: string | null; status: 'open' | 'done'; created_at: string };
export type Idea = { id: string; title: string; description: string; transcript: string; pillar: string; product: string; customer: string; value: string; complexity: string; urgency: string; status: 'captured' | 'evaluating' | 'parked' | 'approved' | 'active' | 'rejected'; source: string; created_at: string };
export type RoadmapItem = { id: string; phase: 'package' | 'validate' | 'replicate'; title: string; status: 'not_started' | 'in_progress' | 'done' | 'blocked'; owner: Who; due: string | null; note: string };
export type RoadmapPhase = { phase: string; label: string; items: RoadmapItem[]; done: number; total: number; pct: number };
export type Focus = { objective: Objective; next_action: NextAction; active: Priority[]; proposed: Priority[]; paused: Priority[]; slots: number; waiting: Note[]; wins: Note[]; ideas_new_week: number; pillars: { key: string; name: string }[]; products: { key: string; name: string }[] };

export const TABS = [['index', 'Focus'], ['strategy', 'Strategy'], ['roadmap', 'Roadmap'], ['ideas', 'Ideas']] as const;
export const PILLAR_COLOR: Record<string, string> = { capture: BLUE, understand: PURPLE, engage: GOLD, improve: GREEN };
export const PILLAR_ICON: Record<string, any> = { capture: 'radio-button-on', understand: 'eye', engage: 'chatbubbles', improve: 'trending-up' };
export const IDEA_STATUS: Record<string, { label: string; color: string }> = {
  captured: { label: 'Captured', color: AMBER }, evaluating: { label: 'Evaluating', color: BLUE }, parked: { label: 'Parked', color: PURPLE }, approved: { label: 'Approved', color: GREEN }, active: { label: 'Active', color: GOLD }, rejected: { label: 'Declined', color: RED },
};
export const ROADMAP_STATUS: Record<string, { label: string; color: string; icon: any }> = {
  not_started: { label: 'Not started', color: '#8E8E93', icon: 'ellipse-outline' }, in_progress: { label: 'In progress', color: BLUE, icon: 'time-outline' }, done: { label: 'Done', color: GREEN, icon: 'checkmark-circle' }, blocked: { label: 'Blocked', color: RED, icon: 'alert-circle' },
};
export const OBJECTIVE_STATUS: Record<string, { label: string; color: string }> = { proposed: { label: 'Proposed', color: AMBER }, on_track: { label: 'On track', color: GREEN }, at_risk: { label: 'At risk', color: AMBER }, behind: { label: 'Behind', color: RED }, done: { label: 'Done', color: PURPLE } };
export const STATEMENT_LABEL: Record<string, string> = { company: 'Company', category: 'Category', vision: 'Long-term vision', promise: 'Company promise', mission: 'Mission', philosophy: 'Core philosophy', positioning: 'Positioning' };
export const fmtDay = (d?: string | null) => (d ? new Date(d.length === 10 ? d + 'T12:00:00' : d).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : '');
export const detail = (e: any, fallback: string) => { const d = e?.response?.data?.detail; return typeof d === 'string' ? d : d?.message || fallback; };
