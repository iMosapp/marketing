import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import api from '../../services/api';
import { GOLD, tid } from '../inbox/ownership';
import { money, miles } from './shared';

const GROUP_ICON: Record<string, any> = { needs_attention: 'alert-circle', waiting_on_manager: 'hourglass', approved_to_present: 'hand-left', presented_follow_up: 'chatbubble-ellipses', reappraisal_opportunities: 'sparkles', recently_closed: 'flag' };
const GROUP_COLOR: Record<string, string> = { needs_attention: '#FF3B30', waiting_on_manager: '#FF9500', approved_to_present: '#34C759', presented_follow_up: GOLD, reappraisal_opportunities: '#30B0C7', recently_closed: '#8E8E93' };
const ago = (s?: number | null) => (s == null ? '' : s < 3600 ? `${Math.max(1, Math.round(s / 60))}m` : s < 86400 ? `${Math.round(s / 3600)}h` : `${Math.round(s / 86400)}d`);

// MY TRADE PIPELINE: what to do next, in order. Managers can flip to the team's pipeline.
export const PipelineSection = ({ colors }: { colors: any }) => {
  const router = useRouter();
  const [data, setData] = useState<any | null>(null);
  const [team, setTeam] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const load = useCallback(() => { api.get('/appraisals/pipeline', { params: { team: team ? 1 : undefined } }).then(r => setData(r.data)).catch(() => setData(null)); }, [team]);
  useEffect(() => { load(); }, [load]);
  useFocusEffect(useCallback(() => { load(); }, [load]));
  if (!data) return null;
  const groups = data.groups.filter((g: any) => g.items.length);
  return (
    <View style={{ borderRadius: 16, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, padding: 14, gap: 10 }} {...tid('pipeline-section')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <Ionicons name="git-branch" size={16} color={GOLD} />
        <Text style={{ flex: 1, fontSize: 12, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8 }}>{team ? 'TEAM TRADE PIPELINE' : 'MY TRADE PIPELINE'} · {data.actionable} to act on</Text>
        {data.can_team ? <TouchableOpacity onPress={() => setTeam(t => !t)} style={{ height: 28, paddingHorizontal: 10, borderRadius: 14, borderWidth: 1, borderColor: GOLD, backgroundColor: team ? GOLD + '22' : 'transparent' }} {...tid('pipeline-team-toggle')}><Text style={{ fontSize: 11.5, fontWeight: '800', color: GOLD, lineHeight: 26 }}>{team ? 'Just mine' : 'Whole team'}</Text></TouchableOpacity> : null}
      </View>
      {groups.length === 0 ? <Text style={{ fontSize: 12.5, color: colors.textSecondary }} {...tid('pipeline-empty')}>Nothing waiting on you. Start an appraisal or check back after the desk answers.</Text> : groups.map((g: any) => {
        const c = GROUP_COLOR[g.key] || GOLD;
        const isOpen = open === g.key || (open === null && g.key === groups[0].key);
        return (
          <View key={g.key} style={{ borderTopWidth: 1, borderTopColor: colors.border, paddingTop: 8, gap: 6 }} {...tid(`pipeline-group-${g.key}`)}>
            <TouchableOpacity onPress={() => setOpen(isOpen ? '' : g.key)} style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }} {...tid(`pipeline-toggle-${g.key}`)}>
              <Ionicons name={GROUP_ICON[g.key]} size={15} color={c} />
              <Text style={{ flex: 1, fontSize: 14, fontWeight: '800', color: colors.text }}>{g.label}</Text>
              <View style={{ minWidth: 24, height: 22, borderRadius: 11, backgroundColor: c + '22', alignItems: 'center', justifyContent: 'center', paddingHorizontal: 6 }}><Text style={{ fontSize: 11.5, fontWeight: '800', color: c }}>{g.items.length}</Text></View>
              <Ionicons name={isOpen ? 'chevron-up' : 'chevron-down'} size={15} color={colors.textSecondary} />
            </TouchableOpacity>
            {isOpen ? g.items.slice(0, 8).map((it: any) => (
              <TouchableOpacity key={it.id || it.vehicle_id} onPress={() => router.push((g.key === 'reappraisal_opportunities' ? `/vehicle/${it.vehicle_id}` : `/appraisal/${it.id}`) as any)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 6, paddingLeft: 23 }} {...tid(`pipeline-item-${it.id || it.vehicle_id}`)}>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 13.5, fontWeight: '700', color: colors.text }} numberOfLines={1}>{it.contact_name || 'Customer'} · {it.vehicle_label || 'Vehicle'}</Text>
                  <Text style={{ fontSize: 12, color: colors.textSecondary }} numberOfLines={2}>
                    {g.key === 'reappraisal_opportunities' ? it.title
                      : g.key === 'needs_attention' && it.needs_info_request?.reason ? `Desk asked: ${it.needs_info_request.reason}`
                      : [it.status_label, it.approved_value ? `offered ${money(it.approved_value)}` : it.suggested_acv ? `suggested ${money(it.suggested_acv)}` : null, it.customer_expected_value ? `wants ${money(it.customer_expected_value)}` : null, it.gap ? `gap ${money(it.gap)}` : null, it.mileage_confirmed != null ? miles(it.mileage_confirmed) : null, it.outcome_label].filter(Boolean).join(' · ')}
                  </Text>
                </View>
                <Text style={{ fontSize: 11, color: colors.textSecondary }}>{g.key === 'waiting_on_manager' ? `${ago(it.waiting_s)} waiting` : ago(it.age_s)}</Text>
                <Ionicons name="chevron-forward" size={14} color={colors.textSecondary} />
              </TouchableOpacity>
            )) : null}
            {isOpen && g.items.length > 8 ? <Text style={{ fontSize: 12, color: colors.textSecondary, paddingLeft: 23 }}>and {g.items.length - 8} more</Text> : null}
          </View>
        );
      })}
    </View>
  );
};
