import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { normalizeTouches, whenLabel, summarizeTouches, isDateCampaign, dateTypeOf, DATE_TYPES, tagColor, scopeLabel, planIssues, GOLD, GREEN, RED, AMBER, tid } from './utils';

type Props = { campaign: any; colors: any; onPress: () => void; onToggleActive?: () => void };

export function PlanCard({ campaign: c, colors, onPress, onToggleActive }: Props) {
  const touches = normalizeTouches(c.sequences, c.message_template);
  const dateBased = isDateCampaign(c);
  const dt = DATE_TYPES.find(d => d.id === dateTypeOf(c));
  const color = dateBased ? (dt?.color || AMBER) : tagColor(c.trigger_tag);
  const issues = planIssues(c);
  const live = !!c.active;
  const jessi = c.ai_assist_mode === 'auto_reply' || c.ai_assist_mode === 'auto_with_approval' || (!c.ai_assist_mode && c.ai_enabled);
  const shown = touches.slice(0, 6);
  const id = c._id || c.id;

  return (
    <TouchableOpacity onPress={onPress} activeOpacity={0.85} style={{ backgroundColor: colors.card, borderRadius: 18, borderWidth: 1, borderColor: issues.length && live ? RED + '66' : colors.border, padding: 14, gap: 12 }} {...tid(`plan-card-${id}`)}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
        <View style={{ width: 40, height: 40, borderRadius: 12, backgroundColor: color + '22', alignItems: 'center', justifyContent: 'center' }}>
          <Ionicons name={dateBased ? ((dt?.icon as any) || 'calendar') : 'pricetag'} size={18} color={color} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text }} numberOfLines={1}>{c.name}</Text>
          <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }} numberOfLines={1}>
            {dateBased ? dt?.phrase || 'On a date' : c.trigger_tag ? <>When tagged <Text style={{ color, fontWeight: '700' }}>{c.trigger_tag}</Text></> : 'No trigger yet'}
            {` · ${scopeLabel(c)}`}
          </Text>
        </View>
        <TouchableOpacity onPress={onToggleActive} disabled={!onToggleActive} hitSlop={8} style={{ flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 9, paddingVertical: 5, borderRadius: 9, backgroundColor: live ? GREEN + '22' : colors.surface }} {...tid(`plan-toggle-${id}`)}>
          <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: live ? GREEN : colors.textTertiary }} />
          <Text style={{ fontSize: 10, fontWeight: '800', letterSpacing: 0.6, color: live ? GREEN : colors.textSecondary }}>{live ? 'LIVE' : 'PAUSED'}</Text>
        </TouchableOpacity>
      </View>

      {shown.length > 0 ? (
        <View style={{ paddingHorizontal: 4 }}>
          <View style={{ height: 2, backgroundColor: colors.border, position: 'absolute', left: 8, right: 8, top: 4 }} />
          <View style={{ flexDirection: 'row', justifyContent: shown.length === 1 ? 'flex-start' : 'space-between' }}>
            {shown.map((t, i) => (
              <View key={t.id} style={{ alignItems: 'center', minWidth: 36 }}>
                <View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: t.actionType === 'send_card' ? '#AF52DE' : GOLD, borderWidth: 2, borderColor: colors.card }} />
                <Text style={{ fontSize: 10, color: colors.textSecondary, marginTop: 4, fontWeight: '600' }}>{whenLabel(t)}</Text>
              </View>
            ))}
            {touches.length > 6 ? <Text style={{ fontSize: 10, color: colors.textTertiary, marginTop: 14 }}>+{touches.length - 6}</Text> : null}
          </View>
        </View>
      ) : null}

      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
        <Pill text={summarizeTouches(touches)} colors={colors} />
        {jessi ? <Pill text="Jessi answers" icon="sparkles" color={GOLD} colors={colors} /> : null}
        {c.ai_enabled ? <Pill text="Jessi writes" icon="create-outline" color={GOLD} colors={colors} /> : null}
        <Pill text={`${c.enrollments_active || 0} in plan`} colors={colors} />
        {c.sent_this_week ? <Pill text={`${c.sent_this_week} sent this week`} colors={colors} /> : null}
        {issues.length ? <Pill text={issues[0]} icon="alert-circle" color={RED} colors={colors} /> : null}
      </View>
    </TouchableOpacity>
  );
}

const Pill = ({ text, icon, color, colors }: { text: string; icon?: any; color?: string; colors: any }) => (
  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 9, paddingVertical: 4, borderRadius: 8, backgroundColor: color ? color + '1A' : colors.surface }}>
    {icon ? <Ionicons name={icon} size={11} color={color || colors.textSecondary} /> : null}
    <Text style={{ fontSize: 11, fontWeight: '700', color: color || colors.textSecondary }}>{text}</Text>
  </View>
);
