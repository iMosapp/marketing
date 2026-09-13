import React from 'react';
import { View, Text, TouchableOpacity, TextInput, Modal, ScrollView, Platform, KeyboardAvoidingView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, GREEN, RED, AMBER, tid } from '../scripts/shared';

export { GOLD, GREEN, RED, AMBER, tid };
export const PURPLE = '#AF52DE';
export const BLUE = '#0A84FF';
// Fixed light palette for the no-login pages a client GM opens (proposal, report, kickoff form).
export const LIGHT = { bg: '#F6F4EE', card: '#FFFFFF', border: '#E4DFD2', text: '#161616', textSecondary: '#6B6B6B', surface: '#F1EEE6' };
export const fmtHour = (hm: string) => { const [h, m] = (hm || '09:00').split(':').map(Number); const ap = h >= 12 ? 'PM' : 'AM'; const hh = h % 12 || 12; return m ? `${hh}:${String(m).padStart(2, '0')} ${ap}` : `${hh} ${ap}`; };

export type Plan = { sales_per_month: number; service_per_month: number; price_monthly: number };
export type Hours = { start: string; end: string; days: number[] };
export type DeptStat = { planned: number; scheduled: number; completed: number; unreachable: number; avg_score: number | null };
export type Client = {
  id: string; name: string; brand: string; city: string; state: string; timezone: string; contact_name: string; contact_email: string; contact_phone: string; contact_title: string;
  plan: Plan; hours: Hours; vehicles: string[]; active: boolean; record_calls: boolean; notes: string; from_number: string; report_token?: string; scorecards: Record<string, string | null>;
  billing?: { status?: string; last_invoice?: any }; progress?: Record<string, DeptStat>; avg_score?: number | null; completed?: number; planned?: number; needs_training?: number; people?: number;
  demo?: boolean; text_scorecards?: boolean;
};
export type Person = { id: string; client_id: string; name: string; phone: string; department: string; title: string; notes: string; active: boolean; challenge_history: string[] };
export type ShopCall = {
  id: string; target_id: string; target_name: string; department: string; status: string; outcome?: string | null; fail_reason?: string | null; script_id: string; script_title: string; persona_name?: string;
  curveballs: string[]; scheduled_for: string | null; attempts: number; started_at: string | null; ended_at: string | null; score_pct: number | null; adherence_pct: number | null; evaluation_id?: string | null;
  recording_url?: string | null; recording_seconds?: number | null; turns: number; manual: boolean; demo?: boolean; score_url?: string | null; score_sms_status?: string | null; score_views?: number;
};
export type Challenge = { id: string; title: string; department: string; direction?: 'inbound' | 'outbound'; category: string; purpose: string; body: string; success_points: string[]; persona: any; client_specific: boolean; shop_client_id?: string | null; runtime: string; curveballs?: string[]; generated?: boolean };
export type ChallengeDraft = { title: string; department: string; runtime?: string; purpose?: string; body: string; success_points?: string[]; curveballs?: string[]; persona?: any; generated_from?: string };
export type Proposal = {
  id: string; token: string; status: string; terms: { sales_per_month: number; service_per_month: number; price_monthly: number; term_months: number; notes?: string }; client_name: string; contact_name: string; contact_email: string;
  created_at: string; sent_at?: string | null; viewed_at?: string | null; signed_at?: string | null; signer?: { name?: string; title?: string; email?: string; signed_at?: string }; invoice?: { hosted_invoice_url?: string; status?: string; amount?: number; paid_at?: string; error?: string }; url?: string;
};

export const DEPTS = [{ key: 'sales', label: 'Sales' }, { key: 'service', label: 'Service' }, { key: 'parts', label: 'Parts' }, { key: 'rental', label: 'Rental' }];
export const deptLabel = (d?: string) => DEPTS.find(x => x.key === d)?.label || 'Sales';
export const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
export const fmtPhone = (p?: string) => { const d = (p || '').replace(/\D/g, '').slice(-10); return d.length === 10 ? `(${d.slice(0, 3)}) ${d.slice(3, 6)}-${d.slice(6)}` : p || ''; };
export const fmtWhen = (iso?: string | null) => (iso ? new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '');
export const fmtDay = (iso?: string | null) => (iso ? new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : '');
export const money = (n?: number | null) => `$${Math.round(n || 0).toLocaleString()}`;
export const monthKey = (d = new Date()) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
export const shiftMonth = (key: string, by: number) => { const [y, m] = key.split('-').map(Number); return monthKey(new Date(y, m - 1 + by, 1)); };
export const monthLabel = (key: string) => { const [y, m] = key.split('-').map(Number); return new Date(y, m - 1, 1).toLocaleDateString(undefined, { month: 'long', year: 'numeric' }); };
export const scoreColor = (pct?: number | null) => (pct == null ? '#8E8E93' : pct >= 85 ? GREEN : pct >= 70 ? AMBER : RED);

export const STATUS: Record<string, { label: string; color: string; icon: any }> = {
  scheduled: { label: 'Scheduled', color: BLUE, icon: 'time-outline' }, dialing: { label: 'Calling now', color: GOLD, icon: 'call' }, live: { label: 'On the call', color: GREEN, icon: 'radio' },
  grading: { label: 'Grading', color: PURPLE, icon: 'hourglass' }, completed: { label: 'Done', color: GREEN, icon: 'checkmark-circle' }, unreachable: { label: 'Unreachable', color: RED, icon: 'call-outline' },
  failed: { label: 'Failed', color: RED, icon: 'alert-circle' }, canceled: { label: 'Canceled', color: '#8E8E93', icon: 'close-circle' }, abandoned: { label: 'Hung up', color: RED, icon: 'call-outline' },
};

export const Label = ({ t, colors }: { t: string; colors: any }) => <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1 }}>{t}</Text>;

export const Field = ({ label, value, onChange, colors, placeholder, multiline, keyboardType, testID, autoCapitalize }: any) => (
  <View style={{ gap: 6 }}>
    {!!label && <Label t={label} colors={colors} />}
    <TextInput value={value} onChangeText={onChange} placeholder={placeholder} placeholderTextColor={colors.textSecondary} multiline={multiline} keyboardType={keyboardType} autoCapitalize={autoCapitalize}
      style={{ backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 12, paddingVertical: 10, color: colors.text, fontSize: 15, minHeight: multiline ? 90 : 44, textAlignVertical: 'top' }} {...tid(testID)} />
  </View>
);

export const Chip = ({ label, active, onPress, colors, testID, color = GOLD, small }: { label: string; active: boolean; onPress: () => void; colors: any; testID: string; color?: string; small?: boolean }) => (
  <TouchableOpacity onPress={onPress} style={{ paddingHorizontal: small ? 10 : 12, height: small ? 28 : 34, borderRadius: 17, backgroundColor: active ? color : colors.card, borderWidth: 1, borderColor: active ? color : colors.border, justifyContent: 'center' }} {...tid(testID)}>
    <Text style={{ fontSize: small ? 12 : 13, fontWeight: '800', color: active ? '#111' : colors.text }}>{label}</Text>
  </TouchableOpacity>
);

export const StatusChip = ({ status, colors }: { status: string; colors: any }) => {
  const s = STATUS[status] || { label: status, color: colors.textSecondary, icon: 'ellipse' };
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, height: 24, borderRadius: 12, backgroundColor: s.color + '22' }} {...tid(`shop-status-${status}`)}>
      <Ionicons name={s.icon} size={12} color={s.color} /><Text style={{ fontSize: 11, fontWeight: '800', color: s.color }}>{s.label}</Text>
    </View>
  );
};

export const Sheet = ({ visible, onClose, title, colors, children, testID, footer }: { visible: boolean; onClose: () => void; title: string; colors: any; children: React.ReactNode; testID: string; footer?: React.ReactNode }) => (
  <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <View style={{ flex: 1, backgroundColor: '#00000088', justifyContent: 'flex-end' }}>
        <TouchableOpacity style={{ flex: 1 }} activeOpacity={1} onPress={onClose} />
        <View style={{ backgroundColor: colors.bg, borderTopLeftRadius: 24, borderTopRightRadius: 24, maxHeight: '92%' }} {...tid(testID)}>
          <View style={{ flexDirection: 'row', alignItems: 'center', padding: 16, gap: 12 }}>
            <Text style={{ flex: 1, fontSize: 18, fontWeight: '800', color: colors.text }}>{title}</Text>
            <TouchableOpacity onPress={onClose} hitSlop={10} {...tid(`${testID}-close`)}><Ionicons name="close" size={24} color={colors.text} /></TouchableOpacity>
          </View>
          <ScrollView contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 20, gap: 16 }} keyboardShouldPersistTaps="handled">{children}</ScrollView>
          {footer && <View style={{ padding: 16, paddingBottom: Platform.OS === 'ios' ? 30 : 16, borderTopWidth: 1, borderTopColor: colors.border }}>{footer}</View>}
        </View>
      </View>
    </KeyboardAvoidingView>
  </Modal>
);

export const GoldButton = ({ label, onPress, disabled, busy, testID, icon, outline, color = GOLD }: { label: string; onPress: () => void; disabled?: boolean; busy?: boolean; testID: string; icon?: any; outline?: boolean; color?: string }) => (
  <TouchableOpacity onPress={onPress} disabled={disabled || busy} style={{ height: 46, borderRadius: 14, backgroundColor: outline ? 'transparent' : disabled ? color + '55' : color, borderWidth: outline ? 1 : 0, borderColor: color, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8, opacity: busy ? 0.7 : 1 }} {...tid(testID)}>
    {icon && <Ionicons name={icon} size={16} color={outline ? color : '#111'} />}
    <Text style={{ fontSize: 15, fontWeight: '800', color: outline ? color : '#111' }}>{busy ? 'Working…' : label}</Text>
  </TouchableOpacity>
);

export const Stat = ({ label, value, colors, tone, testID }: { label: string; value: string; colors: any; tone?: string; testID?: string }) => (
  <View style={{ flex: 1, minWidth: 130, backgroundColor: colors.card, borderRadius: 14, padding: 12, borderWidth: 1, borderColor: colors.border, gap: 2 }} {...tid(testID || `stat-${label.toLowerCase().replace(/\s+/g, '-')}`)}>
    <Text style={{ fontSize: 20, fontWeight: '800', color: tone || colors.text }}>{value}</Text>
    <Text style={{ fontSize: 11, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.5 }}>{label.toUpperCase()}</Text>
  </View>
);

export const Bar = ({ pct, color, colors }: { pct: number; color: string; colors: any }) => (
  <View style={{ height: 6, borderRadius: 3, backgroundColor: colors.border, overflow: 'hidden', flex: 1 }}><View style={{ width: `${Math.max(2, Math.min(100, pct))}%`, height: 6, backgroundColor: color }} /></View>
);
