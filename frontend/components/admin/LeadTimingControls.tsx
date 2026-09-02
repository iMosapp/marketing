import React, { useState } from 'react';
import { View, Text, TouchableOpacity, TextInput, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';

export type StoreHours = {
  store_name?: string; timezone: string; configured: boolean; open_now: boolean; opens_at: string | null;
  hours: Record<string, { open: string; close: string } | null>;
};

const GOLD = '#C9A962';
const DAYS = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'];
const PRESETS = [
  { key: 'strict', label: 'Strict states 9 AM to 8 PM', start: '09:00', end: '20:00' },
  { key: 'federal', label: 'Federal 8 AM to 9 PM', start: '08:00', end: '21:00' },
];

export const clock12 = (hhmm?: string) => {
  if (!hhmm || !/^\d{2}:\d{2}$/.test(hhmm)) return hhmm || '';
  const [h, m] = hhmm.split(':').map(Number);
  const ampm = h >= 12 ? 'PM' : 'AM';
  const hr = h % 12 === 0 ? 12 : h % 12;
  return m ? `${hr}:${String(m).padStart(2, '0')} ${ampm}` : `${hr} ${ampm}`;
};

export const whenLabel = (iso?: string | null) => {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '';
  const time = d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  return d.toDateString() === new Date().toDateString() ? time : `${d.toLocaleDateString([], { weekday: 'short' })} ${time}`;
};

export const AfterHoursRule = ({ mode, windowStart, windowEnd, storeHours, onChange, onEditHours, colors }: {
  mode: 'text_and_ai' | 'ring_anyway'; windowStart: string; windowEnd: string; storeHours: StoreHours | null;
  onChange: (patch: { after_hours_mode?: 'text_and_ai' | 'ring_anyway'; text_window_start?: string; text_window_end?: string }) => void;
  onEditHours: () => void; colors: any;
}) => {
  const preset = PRESETS.find(p => p.start === windowStart && p.end === windowEnd)?.key || 'custom';
  const today = storeHours?.hours?.[DAYS[new Date().getDay()]];
  const storeLine = !storeHours ? '' : !storeHours.configured
    ? 'No store hours set yet, so every lead counts as during hours.'
    : `${today ? `Today ${clock12(today.open)} to ${clock12(today.close)}` : 'Closed today'} · ${storeHours.timezone}${storeHours.open_now ? ' · Open now' : storeHours.opens_at ? ` · Closed, opens ${whenLabel(storeHours.opens_at)}` : ''}`;

  return (
    <View testID="after-hours-rule" dataSet={{ testid: 'after-hours-rule' } as any}>
      <Text style={{ fontSize: 13, fontWeight: '600', color: colors.textSecondary, marginBottom: 8 }}>After Store Hours</Text>
      <View style={{ flexDirection: 'row', backgroundColor: colors.surface, borderRadius: 12, padding: 4, gap: 4 }}>
        {([['text_and_ai', 'moon-outline', 'Text + Jessi, ring at opening'], ['ring_anyway', 'call-outline', 'Ring reps anyway']] as const).map(([v, icon, label]) => {
          const on = mode === v;
          return (
            <TouchableOpacity key={v} onPress={() => onChange({ after_hours_mode: v })}
              style={{ flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 10, paddingHorizontal: 6, borderRadius: 9, backgroundColor: on ? colors.card : 'transparent', borderWidth: on ? 1 : 0, borderColor: GOLD }}
              testID={`after-hours-${v}`} dataSet={{ testid: `after-hours-${v}` } as any}>
              <Ionicons name={icon as any} size={15} color={on ? GOLD : colors.textSecondary} />
              <Text style={{ fontWeight: '700', color: on ? colors.text : colors.textSecondary, fontSize: 12, flexShrink: 1 }}>{label}</Text>
            </TouchableOpacity>
          );
        })}
      </View>
      <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 6, lineHeight: 17 }}>
        {mode === 'text_and_ai'
          ? 'When the store is closed the customer still gets the intake text and Jessi answers their replies. The call ladder waits and rings your reps a few minutes after opening, unless someone already claimed or texted the lead.'
          : 'Reps get rung the moment a lead lands, even at 2 AM.'}
      </Text>
      {storeLine ? (
        <TouchableOpacity onPress={onEditHours} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 8 }} testID="edit-store-hours-link" dataSet={{ testid: 'edit-store-hours-link' } as any}>
          <Ionicons name="storefront-outline" size={14} color={GOLD} />
          <Text style={{ fontSize: 12, color: colors.text, flex: 1 }} numberOfLines={2}>{storeLine}</Text>
          <Text style={{ fontSize: 12, color: GOLD, fontWeight: '700' }}>Edit</Text>
        </TouchableOpacity>
      ) : null}

      <Text style={{ fontSize: 13, fontWeight: '600', color: colors.textSecondary, marginTop: 18, marginBottom: 4 }}>Texting Window (TCPA)</Text>
      <Text style={{ fontSize: 12, color: colors.textSecondary, marginBottom: 8, lineHeight: 17 }}>
        Business-initiated texts and rep calls wait for this window in the customer's local time. Leads that land outside it are released the next morning, one per minute per store, so 40 overnight leads never hit the team at once. Jessi always answers a customer's own text, any hour.
      </Text>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
        {PRESETS.map(p => {
          const on = preset === p.key;
          return (
            <TouchableOpacity key={p.key} onPress={() => onChange({ text_window_start: p.start, text_window_end: p.end })}
              style={{ paddingHorizontal: 10, paddingVertical: 6, borderRadius: 16, backgroundColor: on ? GOLD : colors.card, borderWidth: 1, borderColor: on ? GOLD : colors.border }}
              testID={`window-preset-${p.key}`} dataSet={{ testid: `window-preset-${p.key}` } as any}>
              <Text style={{ fontSize: 12, fontWeight: on ? '700' : '500', color: on ? '#000' : colors.text }}>{p.label}</Text>
            </TouchableOpacity>
          );
        })}
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 10, paddingVertical: 4, borderRadius: 16, backgroundColor: preset === 'custom' ? GOLD + '22' : colors.card, borderWidth: 1, borderColor: preset === 'custom' ? GOLD : colors.border }}>
          <Text style={{ fontSize: 12, color: colors.text }}>Custom</Text>
          <TextInput value={windowStart} onChangeText={v => onChange({ text_window_start: v })} placeholder="09:00" placeholderTextColor={colors.textSecondary} maxLength={5}
            style={{ width: 52, color: colors.text, fontSize: 12, textAlign: 'center', paddingVertical: 2 }} testID="window-start-input" dataSet={{ testid: 'window-start-input' } as any} />
          <Text style={{ fontSize: 12, color: colors.textSecondary }}>to</Text>
          <TextInput value={windowEnd} onChangeText={v => onChange({ text_window_end: v })} placeholder="20:00" placeholderTextColor={colors.textSecondary} maxLength={5}
            style={{ width: 52, color: colors.text, fontSize: 12, textAlign: 'center', paddingVertical: 2 }} testID="window-end-input" dataSet={{ testid: 'window-end-input' } as any} />
        </View>
      </View>
      <Text style={{ fontSize: 11, color: colors.textSecondary, marginTop: 6 }}>Currently {clock12(windowStart)} to {clock12(windowEnd)}, customer local time (24h HH:MM for custom).</Text>
    </View>
  );
};

export const TestLeadCard = ({ sourceId, defaultPhone, contactMode, hasIntakeText, colors, onOpenThread }: {
  sourceId: string; defaultPhone?: string; contactMode: 'text_only' | 'text_and_call'; hasIntakeText: boolean; colors: any; onOpenThread: (conversationId: string) => void;
}) => {
  const [phone, setPhone] = useState(defaultPhone || '');
  const [name, setName] = useState('Test Lead');
  const [includeLadder, setIncludeLadder] = useState(contactMode === 'text_and_call');
  const [sending, setSending] = useState(false);
  const [armed, setArmed] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState('');
  const digits = phone.replace(/\D/g, '');
  const ringing = includeLadder && contactMode === 'text_and_call';

  const send = async () => {
    if (!armed) {
      setArmed(true);
      setTimeout(() => setArmed(false), 5000);
      return;
    }
    setArmed(false);
    setSending(true); setError(''); setResult(null);
    try {
      const [first, ...rest] = name.trim().split(' ');
      const res = await api.post(`/lead-sources/${sourceId}/test-lead`, { phone, first_name: first || 'Test', last_name: rest.join(' ') || 'Lead', include_ladder: ringing });
      setResult(res.data);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Could not send the test lead');
    } finally { setSending(false); }
  };

  const plan = result?.plan;
  const lines: { icon: string; text: string; color?: string }[] = [];
  if (plan) {
    lines.push({ icon: 'chatbubble-ellipses-outline', text: !result.intake_text_configured ? 'Intake text: none configured on this source' : plan.intake_deferred ? `Intake text held until ${whenLabel(plan.intake_at)} (outside ${clock12(plan.window.start)} to ${clock12(plan.window.end)} for the customer)` : 'Intake text sent now', color: plan.intake_deferred ? '#FF9500' : '#34C759' });
    lines.push({ icon: 'sparkles-outline', text: plan.jessi_on ? 'Jessi is answering this lead\'s replies' : 'Jessi is off for this lead (reps answer)', color: plan.jessi_on ? GOLD : colors.textSecondary });
    if (result.ladder_configured) {
      const why = (plan.ladder_reasons || []).map((r: string) => r === 'store_closed' ? 'store closed' : 'texting window').join(' + ');
      lines.push({ icon: 'call-outline', text: plan.ladder_deferred ? `Call ladder rings ${whenLabel(plan.ladder_at)} (${why})` : 'Call ladder ringing reps now', color: plan.ladder_deferred ? '#FF9500' : '#34C759' });
    } else {
      lines.push({ icon: 'call-outline', text: includeLadder && contactMode === 'text_and_call' ? 'Call ladder: no reps configured' : 'Call ladder skipped for this test', color: colors.textSecondary });
    }
    lines.push({ icon: 'storefront-outline', text: `Store ${plan.store.configured ? (plan.store.open ? 'open' : `closed, opens ${whenLabel(plan.store.opens_at)}`) : 'hours not set'} · customer time zone ${plan.customer_tz}`, color: colors.textSecondary });
    lines.push({ icon: 'notifications-outline', text: `${result.reps_notified} rep${result.reps_notified === 1 ? '' : 's'} pushed`, color: colors.textSecondary });
  }

  return (
    <View style={{ borderWidth: 1, borderColor: GOLD + '66', borderRadius: 14, padding: 14, backgroundColor: GOLD + '0D' }} testID="test-lead-card" dataSet={{ testid: 'test-lead-card' } as any}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <Ionicons name="flask-outline" size={18} color={GOLD} />
        <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text }}>Send a test lead</Text>
      </View>
      <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 17, marginBottom: 10 }}>
        Runs a fake website lead through this exact workflow: intake text, rep push, Jessi, after-hours rule and the call ladder. Use your own cell. The contact is tagged "Test Lead".
      </Text>
      <View style={{ flexDirection: 'row', gap: 8, marginBottom: 8 }}>
        <TextInput value={phone} onChangeText={setPhone} placeholder="Customer phone (yours)" placeholderTextColor={colors.textSecondary} keyboardType="phone-pad"
          style={{ flex: 1, borderWidth: 1, borderColor: colors.border, borderRadius: 10, paddingHorizontal: 10, paddingVertical: 9, color: colors.text, backgroundColor: colors.card, fontSize: 14 }}
          testID="test-lead-phone" dataSet={{ testid: 'test-lead-phone' } as any} />
        <TextInput value={name} onChangeText={setName} placeholder="Name" placeholderTextColor={colors.textSecondary}
          style={{ width: 120, borderWidth: 1, borderColor: colors.border, borderRadius: 10, paddingHorizontal: 10, paddingVertical: 9, color: colors.text, backgroundColor: colors.card, fontSize: 14 }}
          testID="test-lead-name" dataSet={{ testid: 'test-lead-name' } as any} />
      </View>
      {contactMode === 'text_and_call' && (
        <TouchableOpacity onPress={() => setIncludeLadder(v => !v)} style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 }} testID="test-lead-ladder-toggle" dataSet={{ testid: 'test-lead-ladder-toggle' } as any}>
          <Ionicons name={includeLadder ? 'checkbox' : 'square-outline'} size={20} color={includeLadder ? GOLD : colors.textSecondary} />
          <Text style={{ fontSize: 13, color: colors.text }}>Ring the call ladder too (your reps' phones will ring)</Text>
        </TouchableOpacity>
      )}
      {!hasIntakeText && <Text style={{ fontSize: 12, color: '#FF9500', marginBottom: 8 }}>No intake text set: the customer gets no text, only the rep push{contactMode === 'text_and_call' ? ' and calls' : ''}.</Text>}
      <TouchableOpacity onPress={send} disabled={sending || digits.length < 10}
        style={{ backgroundColor: armed ? '#FF9500' : GOLD, borderRadius: 10, paddingVertical: 11, alignItems: 'center', opacity: sending || digits.length < 10 ? 0.5 : 1 }}
        testID="test-lead-send-btn" dataSet={{ testid: 'test-lead-send-btn' } as any}>
        {sending ? <ActivityIndicator size="small" color="#000" /> : (
          <Text style={{ color: '#000', fontWeight: '700', fontSize: 14 }}>
            {armed ? `Tap again to text ${digits.slice(-4).padStart(digits.length, '•')}${ringing ? ' and ring reps' : ''}` : 'Send test lead'}
          </Text>
        )}
      </TouchableOpacity>
      {error ? <Text style={{ color: '#FF3B30', fontSize: 12, marginTop: 8 }} testID="test-lead-error" dataSet={{ testid: 'test-lead-error' } as any}>{error}</Text> : null}
      {result ? (
        <View style={{ marginTop: 12, gap: 6 }} testID="test-lead-result" dataSet={{ testid: 'test-lead-result' } as any}>
          {lines.map((l, i) => (
            <View key={i} style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 8 }}>
              <Ionicons name={l.icon as any} size={15} color={l.color || colors.text} style={{ marginTop: 1 }} />
              <Text style={{ fontSize: 13, color: colors.text, flex: 1, lineHeight: 18 }}>{l.text}</Text>
            </View>
          ))}
          <TouchableOpacity onPress={() => onOpenThread(result.conversation_id)} style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, marginTop: 6, paddingVertical: 9, borderRadius: 10, borderWidth: 1, borderColor: GOLD }}
            testID="test-lead-open-thread" dataSet={{ testid: 'test-lead-open-thread' } as any}>
            <Ionicons name="chatbubbles-outline" size={15} color={GOLD} />
            <Text style={{ color: GOLD, fontWeight: '700', fontSize: 13 }}>Open the lead's thread</Text>
          </TouchableOpacity>
        </View>
      ) : null}
    </View>
  );
};
