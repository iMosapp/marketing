import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, Switch, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { showSimpleAlert } from '../../services/alert';
import { useThemeStore } from '../../store/themeStore';
import { PrimaryButton } from '../ui/PrimaryButton';
import { GOLD, RADIUS, SPACE, TYPE, tid, tint } from '../ui/tokens';

type Preview = { count: number; rows: { user_id: string; first_name: string; hours: number; waiting_for: string }[]; text: string; opt_in: boolean; last?: { at: string; count: number; ok: boolean } | null; hour: number; stuck_hours: number; enabled: boolean };

export const Chips = ({ options, value, onPick, testID, fmt }: { options: number[]; value: number; onPick: (v: number) => void; testID: string; fmt?: (v: number) => string }) => {
  const { colors } = useThemeStore();
  return (
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
      {options.map(o => {
        const on = o === value;
        return (
          <TouchableOpacity key={o} onPress={() => onPick(o)} style={{ paddingHorizontal: 12, height: 30, borderRadius: 15, alignItems: 'center', justifyContent: 'center', backgroundColor: on ? tint(GOLD, 0.18) : colors.surface, borderWidth: 1, borderColor: on ? GOLD : colors.border }} {...tid(`${testID}-${o}`)}>
            <Text style={{ fontSize: 13, fontWeight: '700', color: on ? GOLD : colors.text }}>{fmt ? fmt(o) : String(o)}</Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
};

export const hourLabel = (h: number) => `${h % 12 || 12} ${h >= 12 && h < 24 ? 'PM' : 'AM'}`;

/** "Morning digest" block: what Jessi would text this manager right now, the per-manager opt-in, and a send-now button. */
export const DigestCard = ({ isSuper, hour, stuckHours, enabled, onHour, onStuck, onEnabled }: { isSuper: boolean; hour: number; stuckHours: number; enabled: boolean; onHour: (v: number) => void; onStuck: (v: number) => void; onEnabled: (v: boolean) => void }) => {
  const { colors } = useThemeStore();
  const [pv, setPv] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const load = () => api.get('/admin/onboarding-jessi/digest/preview').then(r => setPv(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const toggleMe = async (v: boolean) => {
    setPv(p => (p ? { ...p, opt_in: v } : p));
    try { await api.put('/admin/onboarding-jessi/digest/me', { opt_in: v }); } catch { load(); }
  };
  const sendNow = async () => {
    setBusy(true);
    try { const r = await api.post('/admin/onboarding-jessi/digest/send'); showSimpleAlert('Sent', `Jessi texted you today's digest (${r.data.count} stuck).`); load(); }
    catch (e: any) { showSimpleAlert('Could not send', e?.response?.data?.detail || 'Try again in a minute'); }
    finally { setBusy(false); }
  };

  return (
    <View style={{ gap: SPACE.md }} {...tid('onb-settings-digest')}>
      <Text style={{ fontSize: TYPE.sub, color: colors.textSecondary, lineHeight: 18 }}>
        Every morning Jessi texts each manager who is stuck in onboarding and what they are waiting on. Nothing goes out when nobody is stuck.
      </Text>
      {isSuper && (
        <>
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
            <Text style={{ fontSize: TYPE.body, fontWeight: '600', color: colors.text }}>Morning digest on</Text>
            <Switch value={enabled} onValueChange={onEnabled} trackColor={{ true: GOLD }} {...tid('onb-settings-digest-enabled')} />
          </View>
          <Text style={{ fontSize: TYPE.caption, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.6 }}>SENDS AT</Text>
          <Chips options={[6, 7, 8, 9, 10]} value={hour} onPick={onHour} testID="onb-settings-digest-hour" fmt={hourLabel} />
          <Text style={{ fontSize: TYPE.caption, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.6 }}>COUNTS AS STUCK AFTER</Text>
          <Chips options={[12, 24, 48, 72]} value={stuckHours} onPick={onStuck} testID="onb-settings-digest-stuck" fmt={v => (v >= 48 ? `${v / 24} days` : `${v} h`)} />
        </>
      )}
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
        <Text style={{ fontSize: TYPE.body, fontWeight: '600', color: colors.text }}>Text me the digest</Text>
        {pv ? <Switch value={pv.opt_in} onValueChange={toggleMe} trackColor={{ true: GOLD }} {...tid('onb-settings-digest-me')} /> : <ActivityIndicator size="small" color={GOLD} />}
      </View>
      {pv && (
        <View style={{ backgroundColor: colors.surface, borderRadius: RADIUS.md, padding: SPACE.md, gap: 6 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            <Ionicons name="chatbubble-ellipses-outline" size={14} color={GOLD} />
            <Text style={{ fontSize: TYPE.caption, fontWeight: '700', color: GOLD }}>TODAY'S DIGEST FOR YOU · {pv.count} stuck</Text>
          </View>
          <Text style={{ fontSize: TYPE.sub, color: colors.text, lineHeight: 19 }} {...tid('onb-settings-digest-preview')}>{pv.text}</Text>
          {!!pv.last?.at && <Text style={{ fontSize: TYPE.caption, color: colors.textTertiary }}>Last sent {new Date(pv.last.at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}{pv.last.ok ? '' : ' (failed)'}</Text>}
        </View>
      )}
      <PrimaryButton size="sm" variant="soft" icon="paper-plane-outline" label="Text me today's digest now" loading={busy} onPress={sendNow} testID="onb-settings-digest-send" />
    </View>
  );
};
