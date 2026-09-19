import React from 'react';
import { ScrollView, TouchableOpacity, Text, View } from 'react-native';
import { useThemeStore } from '../../store/themeStore';
import { tid } from '../scripts/shared';
import { GOLD, addDays, shortDay } from './types';

type Props = {
  today: string;
  days: number;
  countsByDay: Record<string, { you: number; jessi: number }>;
  selected: string | null;
  onSelect: (iso: string | null) => void;
};

export const DayStrip = ({ today, days, countsByDay, selected, onSelect }: Props) => {
  const { colors } = useThemeStore();
  const dayList = Array.from({ length: days }, (_, i) => addDays(today, i + 1));
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: 16, gap: 6, paddingBottom: 12 }} {...tid('upcoming-day-strip')}>
      {dayList.map(iso => {
        const c = countsByDay[iso] || { you: 0, jessi: 0 };
        const active = selected === iso;
        const { dow, num } = shortDay(iso);
        const empty = c.you + c.jessi === 0;
        return (
          <TouchableOpacity
            key={iso}
            onPress={() => onSelect(active ? null : iso)}
            style={{
              width: 48, paddingVertical: 8, borderRadius: 12, alignItems: 'center', borderWidth: 1,
              backgroundColor: active ? 'rgba(201,169,98,0.14)' : colors.card,
              borderColor: active ? 'rgba(201,169,98,0.5)' : colors.border,
              opacity: empty && !active ? 0.55 : 1,
            }}
            {...tid(`upcoming-day-${iso}`)}
          >
            <Text style={{ fontSize: 11, fontWeight: '600', color: active ? GOLD : colors.textSecondary }}>{dow}</Text>
            <Text style={{ fontSize: 17, fontWeight: '700', color: colors.text, marginTop: 1 }}>{num}</Text>
            <View style={{ flexDirection: 'row', gap: 3, marginTop: 4, height: 5 }}>
              {c.you > 0 && <View style={{ width: 5, height: 5, borderRadius: 3, backgroundColor: '#5AC8FA' }} />}
              {c.jessi > 0 && <View style={{ width: 5, height: 5, borderRadius: 3, backgroundColor: GOLD }} />}
            </View>
          </TouchableOpacity>
        );
      })}
    </ScrollView>
  );
};
