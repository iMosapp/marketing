import React, { useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useThemeStore } from '../../store/themeStore';
import { GOLD, GREEN, tid } from '../scripts/shared';
import { liveSupported } from '../../hooks/useLiveJessi';
import { LiveJessiSheet } from './LiveJessiSheet';
import { useLiveConfig } from './useLiveConfig';

// Test Lab entry: open the Voice Lab or talk to Jessi right here with the saved config.
export const VoiceLabCard = () => {
  const router = useRouter();
  const { colors } = useThemeStore();
  const { config, reload } = useLiveConfig();
  const [open, setOpen] = useState(false);
  const Tile = ({ icon, color, title, sub, onPress, testID, disabled }: { icon: any; color: string; title: string; sub: string; onPress: () => void; testID: string; disabled?: boolean }) => (
    <TouchableOpacity onPress={onPress} disabled={disabled} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: colors.bg, borderRadius: 12, padding: 12, borderWidth: 1, borderColor: colors.border, opacity: disabled ? 0.55 : 1 }} {...tid(testID)}>
      <Ionicons name={icon} size={18} color={color} />
      <View style={{ flex: 1 }}><Text style={{ fontSize: 13.5, fontWeight: '800', color: colors.text }}>{title}</Text><Text style={{ fontSize: 11.5, color: colors.textSecondary }}>{sub}</Text></View>
      <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
    </TouchableOpacity>
  );
  const ready = !!config?.configured;
  return (
    <View style={{ gap: 8 }} {...tid('voice-lab-card')}>
      <Tile icon="options" color={GOLD} title="Jessi Voice Lab" sub={config ? `Voice: ${config.voice}. Pick her voice, energy and pacing, audition her` : 'Pick her voice, energy and pacing'} onPress={() => router.push('/admin/voice-lab' as any)} testID="voice-lab-open" />
      <Tile icon="mic" color={GREEN} title="Talk to Jessi now" sub={ready ? (liveSupported() ? 'Live conversation with the saved settings' : 'Web browser only for now') : 'Waiting for OPENAI_API_KEY on the server'} onPress={() => setOpen(true)} testID="voice-lab-talk" disabled={!ready || !liveSupported()} />
      <LiveJessiSheet visible={open} onClose={() => { setOpen(false); reload(); }} options={{ mode: 'assistant' }} />
    </View>
  );
};
