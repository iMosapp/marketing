import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useThemeStore } from '../../store/themeStore';
import { GOLD, tid } from '../scripts/shared';

export type Voice = { id: string; name: string; accent: string; tone: string; natural: boolean };

export const VoicePicker = ({ voices, value, onChange }: { voices: Voice[]; value: string; onChange: (id: string) => void }) => {
  const { colors } = useThemeStore();
  return (
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }} {...tid('voice-picker')}>
      {voices.map(v => {
        const on = v.id === value;
        return (
          <TouchableOpacity key={v.id} onPress={() => onChange(v.id)} style={{ width: '48%', flexGrow: 1, borderRadius: 12, padding: 10, borderWidth: 1.5, borderColor: on ? GOLD : colors.border, backgroundColor: on ? `${GOLD}1A` : colors.bg }} {...tid(`voice-${v.id}`)}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
              <Ionicons name={v.tone === 'feminine' ? 'female' : 'male'} size={13} color={on ? GOLD : colors.textSecondary} />
              <Text style={{ fontSize: 14, fontWeight: '800', color: on ? GOLD : colors.text, flex: 1 }}>{v.name}</Text>
              {on && <Ionicons name="checkmark-circle" size={16} color={GOLD} />}
            </View>
            <Text style={{ fontSize: 11, color: colors.textSecondary, marginTop: 3 }}>{v.accent}{v.natural ? '' : ' · generated'}</Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
};

export const LevelRow = ({ label, value, onChange, hint, testID }: { label: string; value: number; onChange: (n: number) => void; hint: string; testID: string }) => {
  const { colors } = useThemeStore();
  return (
    <View style={{ marginBottom: 14 }} {...tid(testID)}>
      <View style={{ flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <Text style={{ fontSize: 13, fontWeight: '800', color: colors.text }}>{label}</Text>
        <Text style={{ fontSize: 12, color: GOLD, fontWeight: '700' }} {...tid(`${testID}-hint`)}>{hint}</Text>
      </View>
      <View style={{ flexDirection: 'row', gap: 6, marginTop: 8 }}>
        {[1, 2, 3, 4, 5].map(n => (
          <TouchableOpacity key={n} onPress={() => onChange(n)} style={{ flex: 1, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center', backgroundColor: n <= value ? GOLD : colors.bg, borderWidth: 1, borderColor: n <= value ? GOLD : colors.border }} {...tid(`${testID}-${n}`)}>
            <Text style={{ fontSize: 13, fontWeight: '800', color: n <= value ? '#0B0B0D' : colors.textSecondary }}>{n}</Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );
};
