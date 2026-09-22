import React, { useEffect, useState } from 'react';
import { Modal, View, Text, TouchableOpacity, ScrollView, TextInput, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { showSimpleAlert } from '../../services/alert';
import { useThemeStore } from '../../store/themeStore';
import { PrimaryButton } from '../ui/PrimaryButton';
import { GOLD, GREEN, RADIUS, SPACE, TYPE, tid, tint } from '../ui/tokens';
import { prettyPhone } from './shared';
import { Chips, DigestCard, hourLabel } from './DigestCard';

type Cfg = { sender_user_id: string; reminders_hours: Record<string, number[]>; quiet_start: number; quiet_end: number; timezone: string; activation_ttl_hours: number; digest_enabled: boolean; digest_hour: number; digest_stuck_hours: number };
type Sender = { id: string; name: string; role: string; number: string };
const NUDGE_LABEL: Record<string, string> = { interview: 'Setup call', summary: 'Write-up (YEP)', photo: 'Photo', email: 'Login email', activation: 'Activation link' };
const TZS = [['America/New_York', 'Eastern'], ['America/Chicago', 'Central'], ['America/Denver', 'Mountain'], ['America/Phoenix', 'Arizona'], ['America/Los_Angeles', 'Pacific'], ['Europe/Amsterdam', 'Netherlands']];

const Label = ({ children }: { children: string }) => {
  const { colors } = useThemeStore();
  return <Text style={{ fontSize: TYPE.caption, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.6, marginTop: SPACE.sm }}>{children}</Text>;
};

const Block = ({ title, icon, children, testID }: { title: string; icon: string; children: React.ReactNode; testID: string }) => {
  const { colors } = useThemeStore();
  return (
    <View style={{ backgroundColor: colors.card, borderRadius: RADIUS.lg, borderWidth: 1, borderColor: colors.border, padding: SPACE.lg, gap: SPACE.sm }} {...tid(testID)}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}><Ionicons name={icon as any} size={16} color={GOLD} /><Text style={{ fontSize: TYPE.section, fontWeight: '800', color: colors.text }}>{title}</Text></View>
      {children}
    </View>
  );
};

/** Sender number, quiet hours, nudge timing and the morning digest, all without touching the API. Super admins edit; managers see the digest block. */
export const SettingsSheet = ({ visible, onClose, isSuper, onSaved }: { visible: boolean; onClose: () => void; isSuper: boolean; onSaved: () => void }) => {
  const { colors } = useThemeStore();
  const [cfg, setCfg] = useState<Cfg | null>(null);
  const [senders, setSenders] = useState<Sender[]>([]);
  const [currentSender, setCurrentSender] = useState<string | null>(null);
  const [nudges, setNudges] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!visible) return;
    api.get('/admin/onboarding-jessi/config').then(r => {
      const c = r.data.config as Cfg;
      setCfg(c);
      setNudges(Object.fromEntries(Object.keys(NUDGE_LABEL).map(k => [k, ((c.reminders_hours || {})[k] || []).join(', ')])));
    }).catch(() => {});
    if (isSuper) api.get('/admin/onboarding-jessi/senders').then(r => { setSenders(r.data.senders || []); setCurrentSender(r.data.current_id); }).catch(() => {});
  }, [visible]);

  const set = (patch: Partial<Cfg>) => setCfg(c => (c ? { ...c, ...patch } : c));
  const save = async () => {
    if (!cfg) return;
    const reminders_hours: Record<string, number[]> = {};
    for (const k of Object.keys(NUDGE_LABEL)) {
      const nums = (nudges[k] || '').split(/[,\s]+/).map(x => parseInt(x, 10)).filter(n => n > 0);
      reminders_hours[k] = nums;
    }
    setSaving(true);
    try {
      await api.put('/admin/onboarding-jessi/config', { sender_user_id: cfg.sender_user_id || undefined, quiet_start: cfg.quiet_start, quiet_end: cfg.quiet_end, timezone: cfg.timezone, reminders_hours, digest_enabled: cfg.digest_enabled, digest_hour: cfg.digest_hour, digest_stuck_hours: cfg.digest_stuck_hours });
      onSaved(); onClose();
    } catch (e: any) { showSimpleAlert('Could not save', e?.response?.data?.detail || 'Try again'); }
    finally { setSaving(false); }
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'flex-end' }}>
        <View style={{ maxHeight: '92%', backgroundColor: colors.bg, borderTopLeftRadius: 22, borderTopRightRadius: 22 }} {...tid('onb-settings-sheet')}>
          <View style={{ flexDirection: 'row', alignItems: 'center', padding: SPACE.lg, paddingBottom: SPACE.sm }}>
            <Text style={{ flex: 1, fontSize: 20, fontWeight: '800', color: colors.text }}>Onboarding settings</Text>
            <TouchableOpacity onPress={onClose} hitSlop={8} {...tid('onb-settings-close')}><Ionicons name="close" size={24} color={colors.textSecondary} /></TouchableOpacity>
          </View>
          {!cfg ? <ActivityIndicator color={GOLD} style={{ margin: 40 }} /> : (
            <ScrollView contentContainerStyle={{ paddingHorizontal: SPACE.lg, paddingBottom: 40, gap: SPACE.md }} keyboardShouldPersistTaps="handled">
              {isSuper && (
                <Block title="Jessi texts from" icon="call-outline" testID="onb-settings-sender">
                  {senders.length === 0 && <Text style={{ fontSize: TYPE.sub, color: colors.textTertiary }}>No accounts with a work number yet.</Text>}
                  {senders.map(s => {
                    const on = (cfg.sender_user_id || currentSender) === s.id;
                    return (
                      <TouchableOpacity key={s.id} onPress={() => set({ sender_user_id: s.id })} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 9 }} {...tid(`onb-settings-sender-${s.id}`)}>
                        <Ionicons name={on ? 'radio-button-on' : 'radio-button-off'} size={20} color={on ? GOLD : colors.textTertiary} />
                        <View style={{ flex: 1 }}><Text style={{ fontSize: TYPE.body, fontWeight: '600', color: colors.text }}>{s.name}</Text><Text style={{ fontSize: TYPE.caption, color: colors.textSecondary }}>{prettyPhone(s.number)} · {s.role.replace('_', ' ')}</Text></View>
                      </TouchableOpacity>
                    );
                  })}
                </Block>
              )}
              {isSuper && (
                <Block title="Quiet hours" icon="moon-outline" testID="onb-settings-quiet">
                  <Text style={{ fontSize: TYPE.sub, color: colors.textSecondary }}>No intro, nudge or digest goes out between {hourLabel(cfg.quiet_start)} and {hourLabel(cfg.quiet_end)} ({TZS.find(t => t[0] === cfg.timezone)?.[1] || cfg.timezone}). Held texts go out in the morning.</Text>
                  <Label>QUIET FROM</Label>
                  <Chips options={[19, 20, 21, 22, 23]} value={cfg.quiet_start} onPick={v => set({ quiet_start: v })} testID="onb-settings-quiet-start" fmt={hourLabel} />
                  <Label>UNTIL</Label>
                  <Chips options={[6, 7, 8, 9, 10]} value={cfg.quiet_end} onPick={v => set({ quiet_end: v })} testID="onb-settings-quiet-end" fmt={hourLabel} />
                  <Label>TIME ZONE</Label>
                  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
                    {TZS.map(([key, label]) => {
                      const on = cfg.timezone === key;
                      return <TouchableOpacity key={key} onPress={() => set({ timezone: key })} style={{ paddingHorizontal: 12, height: 30, borderRadius: 15, justifyContent: 'center', backgroundColor: on ? tint(GOLD, 0.18) : colors.surface, borderWidth: 1, borderColor: on ? GOLD : colors.border }} {...tid(`onb-settings-tz-${key.split('/')[1]}`)}><Text style={{ fontSize: 13, fontWeight: '700', color: on ? GOLD : colors.text }}>{label}</Text></TouchableOpacity>;
                    })}
                  </View>
                </Block>
              )}
              {isSuper && (
                <Block title="Nudges" icon="alarm-outline" testID="onb-settings-nudges">
                  <Text style={{ fontSize: TYPE.sub, color: colors.textSecondary }}>Hours after a step stalls, comma separated (24, 72, 168 = one day, three days, a week). Empty = no nudges for that step. Nudges stop the moment the step is done or they text back.</Text>
                  {Object.keys(NUDGE_LABEL).map(k => (
                    <View key={k} style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                      <Text style={{ width: 120, fontSize: TYPE.sub, fontWeight: '600', color: colors.text }}>{NUDGE_LABEL[k]}</Text>
                      <TextInput value={nudges[k] || ''} onChangeText={v => setNudges(n => ({ ...n, [k]: v }))} placeholder="24, 72" placeholderTextColor={colors.textTertiary} keyboardType="numbers-and-punctuation"
                        style={{ flex: 1, height: 36, paddingHorizontal: 12, borderRadius: 10, backgroundColor: colors.surface, color: colors.text, fontSize: TYPE.sub }} {...tid(`onb-settings-nudge-${k}`)} />
                    </View>
                  ))}
                </Block>
              )}
              <Block title="Morning digest" icon="sunny-outline" testID="onb-settings-digest-block">
                <DigestCard isSuper={isSuper} hour={cfg.digest_hour} stuckHours={cfg.digest_stuck_hours} enabled={cfg.digest_enabled !== false} onHour={v => set({ digest_hour: v })} onStuck={v => set({ digest_stuck_hours: v })} onEnabled={v => set({ digest_enabled: v })} />
              </Block>
              {isSuper && <PrimaryButton full size="lg" icon="checkmark" color={GREEN} label="Save settings" loading={saving} onPress={save} testID="onb-settings-save" />}
            </ScrollView>
          )}
        </View>
      </View>
    </Modal>
  );
};
