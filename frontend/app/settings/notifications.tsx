import React, { useState, useEffect } from 'react';
import {
  View, Text, Switch, TouchableOpacity, StyleSheet,
  ScrollView, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useThemeStore } from '../../store/themeStore';
import { useAuthStore } from '../../store/authStore';
import { useToast } from '../../components/common/Toast';
import api from '../../services/api';

const THROTTLE_OPTIONS = [
  { label: '5 min',  value: 5 },
  { label: '15 min', value: 15 },
  { label: '30 min', value: 30 },
  { label: '1 hour', value: 60 },
];

const THRESHOLD_OPTIONS = [
  { label: '1st reply',  value: 1 },
  { label: '2nd reply',  value: 2 },
  { label: '3rd reply',  value: 3 },
];

export default function NotificationSettings() {
  const router    = useRouter();
  const colors    = useThemeStore(s => s.colors);
  const { user, updateUser } = useAuthStore();
  const { showToast } = useToast();
  const s = getStyles(colors);

  // Load from user.notification_settings
  const saved = (user as any)?.notification_settings || {};
  const [smsActive,    setSmsActive]    = useState<boolean>(saved.sms_active_conversation   ?? true);
  const [throttleMin,  setThrottleMin]  = useState<number>(saved.sms_active_throttle_minutes ?? 30);
  const [smsUrgent,    setSmsUrgent]    = useState<boolean>(saved.sms_you_are_needed         ?? true);
  const [urnThreshold, setUrnThreshold] = useState<number>(saved.you_are_needed_threshold    ?? 2);
  const [alertMode,    setAlertMode]    = useState<'both'|'push'|'sms'>((user as any)?.notification_mode || 'both');
  const [saving, setSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

  const mark = () => setHasChanges(true);

  const save = async () => {
    if (!user?._id) return;
    setSaving(true);
    try {
      const prefs = {
        sms_active_conversation:       smsActive,
        sms_active_throttle_minutes:   throttleMin,
        sms_you_are_needed:            smsUrgent,
        you_are_needed_threshold:      urnThreshold,
      };
      await api.patch(`/users/${user._id}`, { notification_settings: prefs });
      // Save alert delivery mode separately
      await api.patch(`/push/preferences/${user._id}`, { notification_mode: alertMode });
      // Update auth store so the value persists across screens
      updateUser({ notification_settings: prefs, notification_mode: alertMode } as any);
      setHasChanges(false);
      showToast('Notification preferences saved', 'success');
    } catch (e: any) {
      showToast(e?.response?.data?.detail || 'Failed to save', 'error');
    } finally {
      setSaving(false);
    }
  };

  const hasPersonalPhone = !!(user as any)?.phone;
  const hasTwilioNumber  = !!((user as any)?.twilio_number || (user as any)?.mvpline_number);

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      {/* Header */}
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
          <Ionicons name="arrow-back" size={22} color={colors.text} />
        </TouchableOpacity>
        <Text style={s.title}>SMS Notifications</Text>
        {hasChanges ? (
          <TouchableOpacity style={s.saveBtn} onPress={save} disabled={saving}>
            {saving
              ? <ActivityIndicator size="small" color="#000" />
              : <Text style={s.saveBtnText}>Save</Text>
            }
          </TouchableOpacity>
        ) : <View style={{ width: 64 }} />}
      </View>

      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60 }}>
        {/* Info card */}
        <View style={[s.infoCard, { borderColor: colors.accent + '40' }]}>
          <Ionicons name="phone-portrait-outline" size={20} color={colors.accent} />
          <View style={{ flex: 1 }}>
            <Text style={[s.infoTitle, { color: colors.text }]}>Text notifications to your phone</Text>
            <Text style={[s.infoBody, { color: colors.textSecondary }]}>
              When a customer texts you, I'm On Social sends a notification to your personal cell with a link that opens the conversation directly.
            </Text>
          </View>
        </View>

        {/* Warning if setup incomplete */}
        {(!hasPersonalPhone || !hasTwilioNumber) && (
          <View style={[s.warnCard, { borderColor: '#FF950040' }]}>
            <Ionicons name="warning-outline" size={18} color="#FF9500" />
            <View style={{ flex: 1, gap: 4 }}>
              {!hasPersonalPhone && (
                <Text style={{ fontSize: 13, color: '#FF9500' }}>
                  Add your personal phone number in Profile to receive SMS notifications.
                </Text>
              )}
              {!hasTwilioNumber && (
                <Text style={{ fontSize: 13, color: '#FF9500' }}>
                  Assign a dedicated Twilio number from Admin → Phone Numbers to enable sending.
                </Text>
              )}
            </View>
          </View>
        )}

        {/* ── Alert Delivery Mode ─────────────────────────────────────────── */}
        <Text style={[s.sectionLabel, { color: colors.textSecondary }]}>ALERT DELIVERY</Text>
        <View style={[s.card, { backgroundColor: colors.card, padding: 0, overflow: 'hidden' }]}>
          {([
            { value: 'both' as const,  label: 'SMS + Push',  sub: 'Text to personal phone + in-app badge',  icon: 'notifications',   color: '#007AFF' },
            { value: 'push' as const,  label: 'Push only',   sub: 'In-app badge only, no SMS texts',        icon: 'phone-portrait',  color: '#34C759' },
            { value: 'sms'  as const,  label: 'SMS only',    sub: 'Text to personal phone only',            icon: 'chatbubble',      color: '#FF9500' },
          ] as const).map((opt, i, arr) => (
            <TouchableOpacity
              key={opt.value}
              onPress={() => { setAlertMode(opt.value); mark(); }}
              style={{ flexDirection: 'row', alignItems: 'center', padding: 14, borderBottomWidth: i < arr.length - 1 ? 1 : 0, borderBottomColor: colors.border, gap: 12 }}
              data-testid={`alert-mode-${opt.value}`}
            >
              <View style={{ width: 36, height: 36, borderRadius: 9, backgroundColor: alertMode === opt.value ? opt.color + '25' : colors.surface, alignItems: 'center', justifyContent: 'center' }}>
                <Ionicons name={opt.icon as any} size={18} color={alertMode === opt.value ? opt.color : colors.textSecondary} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 16, fontWeight: '600', color: colors.text }}>{opt.label}</Text>
                <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 1 }}>{opt.sub}</Text>
              </View>
              {alertMode === opt.value && <Ionicons name="checkmark-circle" size={22} color={opt.color} />}
            </TouchableOpacity>
          ))}
        </View>

        {/* ── Active Conversation ────────────────────────────────────────── */}
        <Text style={[s.sectionLabel, { color: colors.textSecondary }]}>ACTIVE CONVERSATIONS</Text>

        <View style={[s.card, { backgroundColor: colors.card }]}>
          <View style={s.row}>
            <View style={[s.iconWrap, { backgroundColor: '#007AFF20' }]}>
              <Ionicons name="chatbubble" size={18} color="#007AFF" />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={[s.rowTitle, { color: colors.text }]}>Customer replied</Text>
              <Text style={[s.rowSub, { color: colors.textSecondary }]}>
                Text me when a customer sends a message
              </Text>
            </View>
            <Switch
              value={smsActive}
              onValueChange={v => { setSmsActive(v); mark(); }}
              trackColor={{ false: colors.border, true: '#007AFF80' }}
              thumbColor={smsActive ? '#007AFF' : colors.textSecondary}
            />
          </View>

          {smsActive && (
            <>
              <View style={[s.divider, { backgroundColor: colors.border }]} />
              <Text style={[s.subLabel, { color: colors.textSecondary }]}>
                How often (per conversation)
              </Text>
              <View style={s.chipRow}>
                {THROTTLE_OPTIONS.map(opt => (
                  <TouchableOpacity
                    key={opt.value}
                    onPress={() => { setThrottleMin(opt.value); mark(); }}
                    style={[
                      s.chip,
                      { backgroundColor: colors.surface, borderColor: colors.border },
                      throttleMin === opt.value && s.chipActive,
                    ]}
                    data-testid={`throttle-${opt.value}`}
                  >
                    <Text style={[s.chipText, { color: throttleMin === opt.value ? '#fff' : colors.textSecondary }]}>
                      {opt.label}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
              <Text style={[s.hint, { color: colors.textTertiary }]}>
                After receiving a notification for a conversation, you won't be texted again for this window — prevents spam during active exchanges.
              </Text>
            </>
          )}
        </View>

        {/* ── You're Needed ──────────────────────────────────────────────── */}
        <Text style={[s.sectionLabel, { color: colors.textSecondary, marginTop: 24 }]}>YOU'RE NEEDED</Text>

        <View style={[s.card, { backgroundColor: colors.card }]}>
          <View style={s.row}>
            <View style={[s.iconWrap, { backgroundColor: '#FF3B3020' }]}>
              <Ionicons name="alert-circle" size={18} color="#FF3B30" />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={[s.rowTitle, { color: colors.text }]}>Urgent — customer waiting</Text>
              <Text style={[s.rowSub, { color: colors.textSecondary }]}>
                Text me when a customer replies multiple times without a response
              </Text>
            </View>
            <Switch
              value={smsUrgent}
              onValueChange={v => { setSmsUrgent(v); mark(); }}
              trackColor={{ false: colors.border, true: '#FF3B3080' }}
              thumbColor={smsUrgent ? '#FF3B30' : colors.textSecondary}
            />
          </View>

          {smsUrgent && (
            <>
              <View style={[s.divider, { backgroundColor: colors.border }]} />
              <Text style={[s.subLabel, { color: colors.textSecondary }]}>
                Trigger after this many unanswered replies
              </Text>
              <View style={s.chipRow}>
                {THRESHOLD_OPTIONS.map(opt => (
                  <TouchableOpacity
                    key={opt.value}
                    onPress={() => { setUrnThreshold(opt.value); mark(); }}
                    style={[
                      s.chip,
                      { backgroundColor: colors.surface, borderColor: colors.border },
                      urnThreshold === opt.value && s.chipUrgent,
                    ]}
                    data-testid={`threshold-${opt.value}`}
                  >
                    <Text style={[s.chipText, { color: urnThreshold === opt.value ? '#fff' : colors.textSecondary }]}>
                      {opt.label}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
              <Text style={[s.hint, { color: colors.textTertiary }]}>
                The urgent notification fires every time the threshold is hit — no rate limit. This always gets through.
              </Text>
            </>
          )}
        </View>

        {/* Message preview */}
        <Text style={[s.sectionLabel, { color: colors.textSecondary, marginTop: 24 }]}>WHAT YOU'LL RECEIVE</Text>
        <View style={[s.previewCard, { backgroundColor: colors.card }]}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <Ionicons name="phone-portrait" size={16} color={colors.textSecondary} />
            <Text style={{ fontSize: 13, fontWeight: '700', color: colors.textSecondary, textTransform: 'uppercase', letterSpacing: 0.5 }}>
              Active Conversation
            </Text>
          </View>
          <View style={[s.smsBox, { backgroundColor: colors.surface }]}>
            <Text style={{ fontSize: 13, color: colors.text, lineHeight: 18 }}>
              {`I'm On Social: Sarah replied to you.\n"Hey are those available in blue?"\n\nOpen conversation:\nhttps://app.imonsocial.com/thread/abc123`}
            </Text>
          </View>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 20, marginBottom: 12 }}>
            <Ionicons name="alert-circle" size={16} color="#FF3B30" />
            <Text style={{ fontSize: 13, fontWeight: '700', color: '#FF3B30', textTransform: 'uppercase', letterSpacing: 0.5 }}>
              You're Needed
            </Text>
          </View>
          <View style={[s.smsBox, { backgroundColor: colors.surface, borderColor: '#FF3B3030', borderWidth: 1 }]}>
            <Text style={{ fontSize: 13, color: colors.text, lineHeight: 18 }}>
              {`⚠️ I'm On Social: YOU'RE NEEDED\nSarah has texted 2 times without a reply.\n\nOpen now:\nhttps://app.imonsocial.com/thread/abc123`}
            </Text>
          </View>
        </View>

        {hasChanges && (
          <TouchableOpacity style={s.saveFab} onPress={save} disabled={saving}>
            {saving
              ? <ActivityIndicator size="small" color="#000" />
              : <Text style={s.saveFabText}>Save Preferences</Text>
            }
          </TouchableOpacity>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container:   { flex: 1, backgroundColor: colors.bg },
  header:      { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.border },
  backBtn:     { width: 36, height: 36, borderRadius: 18, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center' },
  title:       { fontSize: 18, fontWeight: '700', color: colors.text },
  saveBtn:     { backgroundColor: colors.accent, borderRadius: 18, paddingHorizontal: 16, paddingVertical: 7, minWidth: 64, alignItems: 'center' },
  saveBtnText: { fontSize: 14, fontWeight: '700', color: '#000' },
  infoCard:    { flexDirection: 'row', gap: 12, backgroundColor: colors.card, borderRadius: 14, padding: 14, marginBottom: 16, borderWidth: 1, alignItems: 'flex-start' },
  infoTitle:   { fontSize: 14, fontWeight: '700', marginBottom: 4 },
  infoBody:    { fontSize: 13, lineHeight: 18 },
  warnCard:    { flexDirection: 'row', gap: 10, backgroundColor: '#FF950010', borderRadius: 12, padding: 12, marginBottom: 16, borderWidth: 1, alignItems: 'flex-start' },
  sectionLabel:{ fontSize: 12, fontWeight: '700', letterSpacing: 0.8, textTransform: 'uppercase', marginBottom: 10 },
  card:        { borderRadius: 16, padding: 14, marginBottom: 12 },
  row:         { flexDirection: 'row', alignItems: 'center', gap: 12 },
  iconWrap:    { width: 38, height: 38, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  rowTitle:    { fontSize: 15, fontWeight: '600', marginBottom: 2 },
  rowSub:      { fontSize: 13, lineHeight: 17 },
  divider:     { height: 1, marginVertical: 14 },
  subLabel:    { fontSize: 13, fontWeight: '600', marginBottom: 10 },
  chipRow:     { flexDirection: 'row', gap: 8, flexWrap: 'wrap', marginBottom: 10 },
  chip:        { borderRadius: 20, paddingHorizontal: 14, paddingVertical: 7, borderWidth: 1 },
  chipActive:  { backgroundColor: '#007AFF', borderColor: '#007AFF' },
  chipUrgent:  { backgroundColor: '#FF3B30', borderColor: '#FF3B30' },
  chipText:    { fontSize: 13, fontWeight: '600' },
  hint:        { fontSize: 12, lineHeight: 16 },
  previewCard: { borderRadius: 16, padding: 16, marginBottom: 20 },
  smsBox:      { borderRadius: 12, padding: 12 },
  saveFab:     { backgroundColor: colors.accent, borderRadius: 16, padding: 16, alignItems: 'center', marginTop: 8 },
  saveFabText: { fontSize: 16, fontWeight: '700', color: '#000' },
});
