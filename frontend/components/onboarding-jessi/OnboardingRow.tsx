import React from 'react';
import { View, Text, Image, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useThemeStore } from '../../store/themeStore';
import { resolvePhotoUrl } from '../../utils/photoUrl';
import { GOLD, RADIUS, SPACE, TYPE, tid, tint } from '../ui/tokens';
import { OnbRow, STAGE_LABEL, WaitingPill, ago, initials, prettyPhone } from './shared';

/** One person in the onboarding list: who, where they are, whose move it is, how long it has been quiet. */
export const OnboardingRow = ({ row, onPress, first }: { row: OnbRow; onPress: () => void; first?: boolean }) => {
  const { colors } = useThemeStore();
  const uri = resolvePhotoUrl(row.user_photo_url || row.photo_url || null);
  const total = (row.states?.length || 14) - 1;
  const pct = Math.min(1, Math.max(0.04, row.state_index / total));
  const quiet = row.last_inbound_at || row.last_outbound_at || row.updated_at;
  return (
    <TouchableOpacity onPress={onPress} activeOpacity={0.75}
      style={{ flexDirection: 'row', alignItems: 'center', gap: SPACE.md, paddingHorizontal: SPACE.lg, paddingVertical: SPACE.md, borderTopWidth: first ? 0 : 0.5, borderTopColor: colors.border }}
      {...tid(`jessi-onb-row-${row.user_id}`)}>
      {uri ? <Image source={{ uri }} style={{ width: 44, height: 44, borderRadius: 22 }} /> : (
        <View style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: tint(GOLD, 0.16), alignItems: 'center', justifyContent: 'center' }}>
          <Text style={{ fontSize: 15, fontWeight: '800', color: GOLD }}>{initials(row.name)}</Text>
        </View>
      )}
      <View style={{ flex: 1, minWidth: 0 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <Text style={{ flex: 1, fontSize: TYPE.body, fontWeight: '700', color: colors.text }} numberOfLines={1}>{row.name || row.first_name}</Text>
          <Text style={{ fontSize: TYPE.caption, color: colors.textTertiary }}>{ago(quiet)}</Text>
        </View>
        <Text style={{ fontSize: TYPE.caption, color: colors.textSecondary, marginTop: 1 }} numberOfLines={1}>
          {prettyPhone(row.phone)} · {STAGE_LABEL[row.state] || row.state}{row.reminders?.count ? ` · ${row.reminders.count} nudge${row.reminders.count > 1 ? 's' : ''}` : ''}
        </Text>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: SPACE.sm, marginTop: 6 }}>
          <View style={{ flex: 1, height: 4, borderRadius: 2, backgroundColor: tint(colors.text, 0.08), overflow: 'hidden' }}>
            <View style={{ width: `${pct * 100}%`, height: 4, backgroundColor: row.waiting_on === 'done' ? '#34C759' : GOLD, borderRadius: 2 }} />
          </View>
          <WaitingPill who={row.waiting_on} testID={`jessi-onb-waiting-${row.user_id}`} />
        </View>
      </View>
      <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />
    </TouchableOpacity>
  );
};

/** Six little tiles across the top: how many people sit in each part of the funnel. */
export const FunnelStrip = ({ counts, buckets, active, onPick }: { counts: Record<string, number>; buckets: { key: string; label: string; states: string[] }[]; active: string | null; onPick: (k: string | null) => void }) => {
  const { colors } = useThemeStore();
  return (
    <View style={{ flexDirection: 'row', gap: 6, paddingHorizontal: SPACE.lg, marginBottom: SPACE.lg }} {...tid('jessi-onb-funnel')}>
      {buckets.map(b => {
        const n = b.states.reduce((a, s) => a + (counts[s] || 0), 0);
        const on = active === b.key;
        return (
          <TouchableOpacity key={b.key} onPress={() => onPick(on ? null : b.key)} activeOpacity={0.8}
            style={{ flex: 1, alignItems: 'center', paddingVertical: 10, borderRadius: RADIUS.md, backgroundColor: on ? tint(GOLD, 0.18) : colors.card, borderWidth: 1, borderColor: on ? GOLD : colors.border }}
            {...tid(`jessi-onb-funnel-${b.key}`)}>
            <Text style={{ fontSize: 18, fontWeight: '800', color: n ? colors.text : colors.textTertiary }}>{n}</Text>
            <Text style={{ fontSize: 10, fontWeight: '700', color: on ? GOLD : colors.textSecondary, letterSpacing: 0.3 }} numberOfLines={1}>{b.label}</Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
};
