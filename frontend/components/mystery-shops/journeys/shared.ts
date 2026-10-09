import { GOLD, GREEN, RED, AMBER, PURPLE, BLUE } from '../shared';
import type { LeadShop } from '../lead-shops/shared';

export type Mode = 'observe' | 'approve' | 'auto';
export type VoiceMode = 'voicemail' | 'live';
export type Modes = { email: Mode; sms: Mode; voice: VoiceMode };
export type IdentityFields = { timeline: string; personality: string; channel_prefs: string[]; questions: string[]; objections: string[]; ai_instructions: string; no_commit: boolean };
export type Identity = Omit<LeadShop, 'persona' | 'status'> & { status: LeadShop['status'] | 'draft'; campaign_id?: string | null; persona: LeadShop['persona'] & IdentityFields };
export type CampaignStatus = 'draft' | 'armed' | 'live' | 'stopped' | 'closed';
export type Campaign = {
  id: string; client_id: string; name: string; department: string; store_name: string; status: CampaignStatus; method: 'adf' | 'manual'; source_name: string;
  window_hours: number; window_label: string; modes: Modes; live_voice_enabled: boolean; submission_limit: number;
  scenario: { offering?: string; script_id?: string | null; script_title?: string | null; notes?: string };
  authorization: { by: string; by_name?: string; at: string; website_url?: string; note?: string } | null;
  emergency_stop: { at: string; by: string; by_name?: string; reason?: string } | null; arm_errors: string[];
  created_at: string; armed_at: string | null; stopped_at: string | null; closed_at: string | null;
  counts: { draft: number; pending_delivery: number; live: number; closing: number; completed: number; total: number; open: number }; avg_score: number | null;
  identities: Identity[] | { id: string; name: string; status: string; score: number | null }[];
};
export type JourneyOptions = { windows: { hours: number; label: string }[]; modes: Mode[]; voice_modes: VoiceMode[]; default_modes: Modes; max_identities: number; timelines: string[]; personalities: string[]; email_ready: boolean; pool: { available: number; in_use: number; cap: number; total: number } };

export const CAMPAIGN_STATUS: Record<CampaignStatus, { label: string; color: string; icon: any }> = {
  draft: { label: 'Draft', color: AMBER, icon: 'create-outline' }, armed: { label: 'Armed', color: BLUE, icon: 'shield-checkmark' }, live: { label: 'Live', color: GREEN, icon: 'radio' },
  stopped: { label: 'Stopped', color: RED, icon: 'hand-left' }, closed: { label: 'Closed', color: PURPLE, icon: 'checkmark-circle' },
};
export const MODE_LABEL: Record<Mode, string> = { observe: 'Observe only', approve: 'Approve each reply', auto: 'Auto reply' };
export const MODE_HINT: Record<Mode, string> = { observe: 'Every touch is logged and timed; the shopper never answers.', approve: 'Jessi drafts the reply, you approve or edit it before it goes out.', auto: 'The shopper answers on its own, like a Lead Shop today.' };
export const VOICE_LABEL: Record<VoiceMode, string> = { voicemail: 'Voicemail + transcript', live: 'Live AI voice' };
export const WINDOW_OPTS = [{ hours: 24, label: '24 hours' }, { hours: 72, label: '3 days' }, { hours: 168, label: '7 days' }, { hours: 720, label: '30 days' }];
export const CHANNEL_WORD: Record<string, string> = { text: 'Text', email: 'Email', call: 'Call' };
export const isRunning = (c: Campaign) => c.status === 'armed' || c.status === 'live';
export const modesText = (m: Modes) => `Email ${MODE_LABEL[m.email].toLowerCase()} · Text ${MODE_LABEL[m.sms].toLowerCase()} · ${VOICE_LABEL[m.voice]}`;
export { GOLD, GREEN, RED, AMBER, PURPLE, BLUE };
