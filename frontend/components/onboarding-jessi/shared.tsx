import React from 'react';
import { View, Text } from 'react-native';
import { GOLD, GREEN, RED, tint, tid } from '../ui/tokens';

export const BLUE = '#0A84FF';
export const GREY = '#8E8E93';

export type OnbRow = {
  id: string; user_id: string; name: string; first_name: string; phone: string; from_number: string; email?: string; user_photo_url?: string | null;
  state: string; state_index: number; states: string[]; next: string; waiting_on: 'them' | 'jessi' | 'done' | 'paused'; paused: boolean;
  steps: Record<string, string>; facts?: Record<string, any>; summary_text?: string | null; summary_confirmed?: boolean; awaiting_email?: boolean;
  interview_session_id?: string | null; photo_url?: string | null; activation_url?: string | null; call_link: string;
  reminders: { count: number; last_at: string | null }; last_inbound_at?: string | null; last_outbound_at?: string | null; created_at: string; updated_at: string; completed_at?: string | null;
  thread?: ThreadLine[]; events?: OnbEvent[]; user?: any; interview?: any;
};
export type ThreadLine = { role: 'jessi' | 'user'; text: string; at: string; ok?: boolean; kind?: string; media?: string[]; error?: string | null };
export type OnbEvent = { type: string; at: string; note?: string; ref?: string };

/** Plain-English stage names, in machine order. */
export const STAGE_LABEL: Record<string, string> = {
  NOT_STARTED: 'Queued', JESSI_INTRODUCED: 'Intro sent', CONTACT_CARD_SENT: 'Card sent', INTERVIEW_INVITED: 'Invited to the call', INTERVIEW_STARTED: 'On the call',
  INTERVIEW_COMPLETE: 'Write-up sent', PHOTO_REQUESTED: 'Photo asked', PHOTO_RECEIVED: 'Photo in', PROFILE_COMPLETE: 'Profile built', ACTIVATION_SENT: 'Activation link sent',
  ACCOUNT_ACTIVATED: 'Activated', FIRST_LOGIN: 'Logged in', FIRST_SUCCESS: 'First win', ONBOARDING_COMPLETE: 'Done',
};

/** Funnel buckets for the dashboard strip. */
export const FUNNEL: { key: string; label: string; states: string[] }[] = [
  { key: 'texting', label: 'Texting', states: ['NOT_STARTED', 'JESSI_INTRODUCED', 'CONTACT_CARD_SENT'] },
  { key: 'interview', label: 'Interview', states: ['INTERVIEW_INVITED', 'INTERVIEW_STARTED'] },
  { key: 'writeup', label: 'Write-up', states: ['INTERVIEW_COMPLETE'] },
  { key: 'photo', label: 'Photo', states: ['PHOTO_REQUESTED', 'PHOTO_RECEIVED'] },
  { key: 'activation', label: 'Activation', states: ['PROFILE_COMPLETE', 'ACTIVATION_SENT', 'ACCOUNT_ACTIVATED'] },
  { key: 'done', label: 'In the app', states: ['FIRST_LOGIN', 'FIRST_SUCCESS', 'ONBOARDING_COMPLETE'] },
];

export const WAITING: Record<string, { label: string; color: string }> = {
  them: { label: 'Waiting on them', color: BLUE },
  jessi: { label: "Jessi's move", color: GOLD },
  done: { label: 'Done', color: GREEN },
  paused: { label: 'Paused', color: RED },
};

export const WaitingPill = ({ who, testID }: { who: string; testID?: string }) => {
  const w = WAITING[who] || WAITING.them;
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 9, height: 24, borderRadius: 12, backgroundColor: tint(w.color, 0.14) }} {...(testID ? tid(testID) : {})}>
      <View style={{ width: 7, height: 7, borderRadius: 4, backgroundColor: w.color }} />
      <Text style={{ fontSize: 12, fontWeight: '700', color: w.color }}>{w.label}</Text>
    </View>
  );
};

export const ago = (iso?: string | null) => {
  if (!iso) return '';
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
};

export const when = (iso?: string | null) => {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
};

export const prettyPhone = (p?: string) => {
  const d = (p || '').replace(/\D/g, '').slice(-10);
  return d.length === 10 ? `(${d.slice(0, 3)}) ${d.slice(3, 6)}-${d.slice(6)}` : p || '';
};

export const initials = (name?: string) => (name || '?').split(' ').map(x => x[0]).filter(Boolean).slice(0, 2).join('').toUpperCase();
