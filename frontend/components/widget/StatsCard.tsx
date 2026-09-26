import React from 'react';
import { View, Text } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, tid, timeAgo } from '../inbox/ownership';
import { Section, Label, Hint } from '../inbox/InboxEditorParts';

const Tile = ({ n, label, colors, hot }: { n: string | number; label: string; colors: any; hot?: boolean }) => (
  <View style={{ flexBasis: '30%', flexGrow: 1, alignItems: 'center', paddingVertical: 10, borderRadius: 12, backgroundColor: hot ? GOLD + '22' : colors.surface }}>
    <Text style={{ fontSize: 18, fontWeight: '800', color: hot ? GOLD : colors.text }}>{n}</Text>
    <Text style={{ fontSize: 11, color: colors.textSecondary, fontWeight: '600', textAlign: 'center' }}>{label}</Text>
  </View>
);

const STATUS: Record<string, { label: string; color: string; icon: string }> = {
  connected: { label: 'Connected', color: '#34C759', icon: 'checkmark-circle' }, connecting: { label: 'Connecting', color: GOLD, icon: 'sync' }, ringing: { label: 'Ringing', color: GOLD, icon: 'call' },
  missed: { label: 'Missed · texted', color: '#FF9500', icon: 'alert-circle' }, missed_customer: { label: 'Visitor did not pick up', color: '#FF9500', icon: 'alert-circle' }, after_hours: { label: 'After hours · texted', color: '#8E8E93', icon: 'moon' },
};

export const StatsCard = ({ stats, recent, colors }: { stats: any; recent: any[]; colors: any }) => (
  <>
    <Section colors={colors} testId="widget-section-stats">
      <Label colors={colors}>How it is doing</Label>
      <Hint colors={colors}>All time, since the code went live on your site.</Hint>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
        <Tile n={stats.loads || 0} label="Page loads" colors={colors} />
        <Tile n={stats.opens || 0} label={`Opened${stats.open_rate != null ? ` · ${stats.open_rate}%` : ''}`} colors={colors} />
        <Tile n={stats.leads_7d || 0} label="Leads this week" colors={colors} hot />
        <Tile n={stats.text_leads || 0} label="Texts" colors={colors} />
        <Tile n={stats.call_requests || 0} label="Call requests" colors={colors} />
        <Tile n={stats.avg_seconds_to_connect != null ? `${stats.avg_seconds_to_connect}s` : '–'} label="Avg. to connect" colors={colors} hot />
      </View>
    </Section>
    <Section colors={colors} testId="widget-section-recent">
      <Label colors={colors}>Recent "Call me now" requests</Label>
      {recent.length === 0 ? <Text style={{ fontSize: 13, color: colors.textSecondary }} {...tid('widget-recent-empty')}>None yet. Once the code is on your site, every request shows up here with who took it and how fast.</Text> : null}
      {recent.map(c => {
        const s = STATUS[c.status] || { label: c.status, color: colors.textSecondary, icon: 'ellipse' };
        return (
          <View key={c.id} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 8, borderTopWidth: 0.5, borderTopColor: colors.border }} {...tid(`widget-recent-${c.id}`)}>
            <Ionicons name={s.icon as any} size={18} color={s.color} />
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>{c.name} <Text style={{ fontWeight: '400', color: colors.textSecondary }}>· ···{c.phone_last4}</Text></Text>
              <Text style={{ fontSize: 12, color: colors.textSecondary }}>{s.label}{c.rep ? ` by ${c.rep}` : ''}{c.seconds != null ? ` in ${c.seconds}s` : ''}{c.host ? ` · ${c.host}` : ''}</Text>
            </View>
            <Text style={{ fontSize: 11, color: colors.textSecondary }}>{timeAgo(c.at)}</Text>
          </View>
        );
      })}
    </Section>
  </>
);
