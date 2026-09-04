import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';

const GOLD = '#C9A962';
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });

type Row = {
  source_id: string; source_name: string; status: 'quiet' | 'slow' | 'healthy' | 'new';
  leads_28d: number; last_lead_at: string | null; quiet_hours: number | null; expected_gap_hours: number | null; alert_after_hours: number | null;
};

const COLOR: Record<Row['status'], string> = { quiet: '#FF3B30', slow: '#FF9F0A', healthy: '#34C759', new: '#8E8E93' };
const LABEL: Record<Row['status'], string> = { quiet: 'Quiet', slow: 'Low volume', healthy: 'Healthy', new: 'No leads yet' };

const hrs = (h: number | null) => h == null ? '' : h < 1 ? `${Math.max(1, Math.round(h * 60))} min` : h < 48 ? `${Math.round(h)}h` : `${(h / 24).toFixed(h / 24 >= 10 ? 0 : 1).replace(/\.0$/, '')} days`;

export const SourceHealthCard = ({ colors, onPick }: { colors: any; onPick?: (sourceId: string) => void }) => {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [rule, setRule] = useState<{ floor_hours: number; gap_multiplier: number; min_leads_28d: number } | null>(null);
  const load = useCallback(() => {
    api.get('/leads/sources/health').then(r => { setRows(r.data.sources || []); setRule(r.data.rule); }).catch(() => setRows([]));
  }, []);
  useEffect(load, [load]);
  if (!rows || rows.length === 0) return null;
  const quiet = rows.filter(r => r.status === 'quiet').length;
  const sub = { fontSize: 12, color: colors.textSecondary, lineHeight: 17 } as const;
  return (
    <View style={{ backgroundColor: colors.card, borderRadius: 14, padding: 16, gap: 10, borderWidth: quiet ? 1 : 0, borderColor: '#FF3B3066' }} {...tid('source-health-card')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
        <View style={{ width: 30, height: 30, borderRadius: 8, backgroundColor: `${quiet ? '#FF3B30' : '#34C759'}22`, alignItems: 'center', justifyContent: 'center' }}>
          <Ionicons name="pulse" size={16} color={quiet ? '#FF3B30' : '#34C759'} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text }}>Source health</Text>
          <Text style={sub} {...tid('source-health-summary')}>{quiet ? `${quiet} source${quiet === 1 ? ' has' : 's have'} gone quiet. Managers were pushed.` : 'Every producing source is still producing.'}</Text>
        </View>
      </View>
      {rows.filter(r => r.status !== 'new').map(r => (
        <TouchableOpacity key={r.source_id} onPress={() => onPick && onPick(r.source_id)} disabled={!onPick} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 6, borderTopWidth: 1, borderTopColor: colors.border }} {...tid(`source-health-${r.source_id}`)}>
          <View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: COLOR[r.status] }} />
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 14, fontWeight: '600', color: colors.text }} numberOfLines={1}>{r.source_name}</Text>
            <Text style={sub} numberOfLines={2}>
              {`${r.leads_28d} in 28 days · last ${hrs(r.quiet_hours)} ago${r.expected_gap_hours ? ` · usually every ${hrs(r.expected_gap_hours)}` : ''}${r.alert_after_hours ? ` · alert after ${hrs(r.alert_after_hours)}` : r.status === 'slow' ? ' · needs 4+ a month to be watched' : ''}`}
            </Text>
          </View>
          <Text style={{ fontSize: 12, fontWeight: '700', color: COLOR[r.status] }}>{LABEL[r.status]}</Text>
        </TouchableOpacity>
      ))}
      {rows.some(r => r.status === 'new') && <Text style={[sub, { borderTopWidth: 1, borderTopColor: colors.border, paddingTop: 8 }]} {...tid('source-health-new-count')}>{`${rows.filter(r => r.status === 'new').length} source${rows.filter(r => r.status === 'new').length === 1 ? ' has' : 's have'} never received a lead: ${rows.filter(r => r.status === 'new').map(r => r.source_name).join(', ')}.`}</Text>}
      {rule && <Text style={sub}>{`Rule: a source with ${rule.min_leads_28d}+ leads in 28 days is quiet after ${rule.floor_hours} hours, or ${rule.gap_multiplier}x its usual gap if it is slower than daily. Toggle the push in Notification Preferences.`}</Text>}
      <Text style={{ fontSize: 11, color: GOLD, fontWeight: '700' }} onPress={load} {...tid('source-health-refresh')}>Refresh</Text>
    </View>
  );
};
