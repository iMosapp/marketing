import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { GOLD, tid } from '../inbox/ownership';
import { Section, Label, Hint } from '../inbox/InboxEditorParts';

const WINDOWS: [number, string][] = [[7, '7 days'], [30, '30 days'], [0, 'All time']];
const DOORS: { key: 'chat' | 'text' | 'call'; icon: string; fallback: string }[] = [
  { key: 'chat', icon: 'chatbubbles', fallback: 'Chat now' }, { key: 'text', icon: 'chatbox-ellipses', fallback: 'Text us' }, { key: 'call', icon: 'call', fallback: 'Call me now' },
];

const Stat = ({ n, label, colors, hot }: { n: string | number; label: string; colors: any; hot?: boolean }) => (
  <View style={{ flexBasis: '22%', flexGrow: 1, paddingVertical: 8, paddingHorizontal: 6, borderRadius: 10, backgroundColor: hot ? GOLD + '22' : colors.surface, alignItems: 'center' }}>
    <Text style={{ fontSize: 16, fontWeight: '800', color: hot ? GOLD : colors.text }}>{n}</Text>
    <Text style={{ fontSize: 10.5, color: colors.textSecondary, fontWeight: '600', textAlign: 'center' }} numberOfLines={1}>{label}</Text>
  </View>
);

const doorStats = (key: string, d: any, colors: any) => {
  const rate = d.rate != null ? `${d.rate}%` : '–';
  if (key === 'call') return [
    <Stat key="v" n={d.views || 0} label="Opened" colors={colors} />, <Stat key="r" n={d.requests || 0} label="Requests" colors={colors} hot />,
    <Stat key="c" n={d.connected || 0} label={d.avg_seconds != null ? `Connected · ${d.avg_seconds}s` : 'Connected'} colors={colors} />, <Stat key="m" n={(d.missed || 0) + (d.after_hours || 0)} label="Missed / closed" colors={colors} />,
  ];
  if (key === 'chat') return [
    <Stat key="v" n={d.views || 0} label="Opened" colors={colors} />, <Stat key="c" n={d.chats || 0} label="Chats" colors={colors} />,
    <Stat key="h" n={d.handed_off || 0} label="To a person" colors={colors} hot />, <Stat key="b" n={d.bookings || 0} label="Booked" colors={colors} hot />,
  ];
  return [
    <Stat key="v" n={d.views || 0} label="Opened" colors={colors} />, <Stat key="l" n={d.leads || 0} label="Texts sent" colors={colors} hot />,
    <Stat key="r" n={rate} label="Opened → sent" colors={colors} />,
  ];
};

type Props = { widgetId: string; initial: any; form: any; colors: any };

export const DoorStatsCard = ({ widgetId, initial, form, colors }: Props) => {
  const [days, setDays] = useState<number>(initial?.days ?? 7);
  const [data, setData] = useState<any>(initial || null);
  const [loading, setLoading] = useState(false);
  useEffect(() => { if (initial && days === (initial.days ?? 7)) setData(initial); }, [initial]);
  const pick = async (n: number) => {
    setDays(n); setLoading(true);
    try { setData((await api.get(`/widgets/${widgetId}/door-stats`, { params: { days: n } })).data); } catch {} finally { setLoading(false); }
  };
  const doors = data?.doors || {};
  const busiest = data?.busiest;
  return (
    <Section colors={colors} testId="widget-section-door-stats">
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
        <Label colors={colors}>Which door gets used</Label>
        <View style={{ flexDirection: 'row', backgroundColor: colors.surface, borderRadius: 9, padding: 3, gap: 2 }}>
          {WINDOWS.map(([n, l]) => (
            <TouchableOpacity key={n} onPress={() => pick(n)} style={{ paddingVertical: 5, paddingHorizontal: 10, borderRadius: 7, backgroundColor: days === n ? GOLD : 'transparent' }} {...tid(`widget-door-stats-days-${n}`)}>
              <Text style={{ fontSize: 11.5, fontWeight: '800', color: days === n ? '#111' : colors.textSecondary }}>{l}</Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>
      <Hint colors={colors}>
        {data?.total_leads ? `${data.total_leads} lead${data.total_leads === 1 ? '' : 's'} came through the widget${busiest ? `, most through ${form.doors?.[busiest]?.label || busiest}` : ''}.` : 'Opened = a visitor picked that door. Leads, requests and chats show what came out of it.'}
      </Hint>
      <View style={{ gap: 10, opacity: loading ? 0.5 : 1 }} {...tid('widget-door-stats-body')}>
        {DOORS.map(({ key, icon, fallback }) => {
          const d = doors[key] || {}; const on = !!form.doors?.[key]?.on;
          return (
            <View key={key} style={{ gap: 6 }} {...tid(`widget-door-stats-${key}`)}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <Ionicons name={icon as any} size={15} color={on ? GOLD : colors.textSecondary} />
                <Text style={{ fontSize: 13, fontWeight: '700', color: on ? colors.text : colors.textSecondary, flex: 1 }}>{form.doors?.[key]?.label || fallback}{!on ? '  · off' : ''}</Text>
                {busiest === key && data?.total_leads ? <Text style={{ fontSize: 10, fontWeight: '800', color: GOLD }} {...tid('widget-door-stats-busiest')}>BUSIEST</Text> : null}
              </View>
              <View style={{ flexDirection: 'row', gap: 6 }}>{doorStats(key, d, colors)}</View>
              {d.pages?.length ? (
                <Text style={{ fontSize: 11.5, color: colors.textSecondary, lineHeight: 16 }} {...tid(`widget-door-stats-pages-${key}`)}>
                  From: {d.pages.map((p: any) => `${p.path} (${p.n})`).join(' · ')}
                </Text>
              ) : null}
            </View>
          );
        })}
      </View>
    </Section>
  );
};
