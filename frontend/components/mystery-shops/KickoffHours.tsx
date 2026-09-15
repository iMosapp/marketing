import React from 'react';
import { View, Text } from 'react-native';
import { Chip, Label, LIGHT, type Hours } from './shared';
import { makeT, daysOf, fmtHourL, type Lang } from './i18n';

const STARTS = ['07:00', '07:30', '08:00', '08:30', '09:00', '09:30', '10:00'];
const ENDS = ['17:00', '17:30', '18:00', '18:30', '19:00', '19:30', '20:00', '21:00'];
type TZ = { id: string; label: string };
type Props = { hours: Hours; timezone: string; timezones: TZ[]; onHours: (h: Hours) => void; onTimezone: (tz: string) => void; customer?: string; lang?: Lang };

// GM picks the window we may call in: days, open, close, time zone. Chips, no typing. Dutch shows a 24h clock.
export const KickoffHours = ({ hours, timezone, timezones, onHours, onTimezone, customer = 'shopper', lang = 'en' }: Props) => {
  const tr = makeT(lang);
  const DAYS = daysOf(lang);
  const starts = STARTS.includes(hours.start) ? STARTS : [hours.start, ...STARTS].sort();
  const ends = ENDS.includes(hours.end) ? ENDS : [hours.end, ...ENDS].sort();
  const toggleDay = (i: number) => onHours({ ...hours, days: hours.days.includes(i) ? hours.days.filter(d => d !== i) : [...hours.days, i].sort() });
  return (
    <View style={{ gap: 14 }}>
      <View style={{ gap: 8 }}>
        <Label t={tr('kick.days')} colors={LIGHT} />
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>{DAYS.map((d, i) => <Chip key={d} label={d} small active={hours.days.includes(i)} onPress={() => toggleDay(i)} colors={LIGHT} testID={`kickoff-day-${i}`} />)}</View>
      </View>
      <View style={{ gap: 8 }}>
        <Label t={tr('kick.earliest')} colors={LIGHT} />
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>{starts.map(s => <Chip key={s} label={fmtHourL(s, lang)} small active={hours.start === s} onPress={() => onHours({ ...hours, start: s })} colors={LIGHT} testID={`kickoff-start-${s.replace(':', '')}`} />)}</View>
      </View>
      <View style={{ gap: 8 }}>
        <Label t={tr('kick.latest')} colors={LIGHT} />
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>{ends.map(s => <Chip key={s} label={fmtHourL(s, lang)} small active={hours.end === s} onPress={() => onHours({ ...hours, end: s })} colors={LIGHT} testID={`kickoff-end-${s.replace(':', '')}`} />)}</View>
      </View>
      <View style={{ gap: 8 }}>
        <Label t={tr('kick.tz')} colors={LIGHT} />
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>{timezones.map(t => <Chip key={t.id} label={t.label} small active={timezone === t.id} onPress={() => onTimezone(t.id)} colors={LIGHT} testID={`kickoff-tz-${t.label.toLowerCase().replace(/[^a-z]/g, '')}`} />)}</View>
      </View>
      <Text style={{ fontSize: 13, color: LIGHT.textSecondary, lineHeight: 18 }} {...({ testID: 'kickoff-hours-summary' } as any)}>{tr('kick.hours_line', { customer, days: DAYS.filter((_, i) => hours.days.includes(i)).join(', ') || tr('kick.no_days'), start: fmtHourL(hours.start, lang), end: fmtHourL(hours.end, lang), tz: timezones.find(t => t.id === timezone)?.label || '' })}</Text>
    </View>
  );
};
