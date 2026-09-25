import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useThemeStore } from '../../store/themeStore';
import { GOLD, tid } from '../scripts/shared';
import { liveSupported } from '../../hooks/useLiveJessi';
import { useLiveJessiLauncher } from './LiveJessiProvider';
import { useLiveConfig } from './useLiveConfig';

// Home entry point for Jessi. Live voice when it is on for this rep and the build supports it, else the Jessi screen.
export const TalkToJessiButton = () => {
  const router = useRouter();
  const { colors } = useThemeStore();
  const { config, reload } = useLiveConfig();
  const jessi = useLiveJessiLauncher();
  const liveReady = !!config?.available && !!config.configured && config.usage.left_s > 0 && liveSupported();
  const needsKey = !!config?.available && !config.configured && config.is_super_admin;

  const press = () => {
    if (needsKey) { router.push('/admin/voice-lab' as any); return; }
    if (liveReady) { jessi.open({ options: { mode: 'assistant' }, onClose: reload }); return; }
    router.push('/(tabs)/jessi' as any);
  };
  const sub = needsKey ? 'Needs OPENAI_API_KEY on the server. Tap to open the Voice Lab.'
    : liveReady ? 'Who to call today, text someone, pull up a contact. Just talk.'
    : config?.available && config.configured && config.usage.left_s <= 0 ? "Today's live minutes are used up. Ask me by text or voice note."
    : 'Ask about a customer, who to follow up with, or what to send.';

  return (
    <TouchableOpacity onPress={press} activeOpacity={0.85} style={{ marginHorizontal: 16, marginBottom: 16, borderRadius: 18, padding: 14, backgroundColor: colors.card, borderWidth: 1.5, borderColor: `${GOLD}66`, flexDirection: 'row', alignItems: 'center', gap: 12 }} {...tid('talk-to-jessi-btn')}>
      <View style={{ width: 46, height: 46, borderRadius: 23, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center' }}>
        <Ionicons name={liveReady ? 'mic' : 'sparkles'} size={22} color="#0B0B0D" />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text }}>{liveReady ? 'Talk to Jessi' : 'Ask Jessi'}</Text>
        <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }} numberOfLines={2}>{sub}</Text>
      </View>
      {liveReady ? (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: `${GOLD}22`, borderRadius: 12, paddingHorizontal: 9, paddingVertical: 5 }}>
          <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: GOLD }} />
          <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 0.6 }}>{jessi.active ? 'ON' : 'LIVE'}</Text>
        </View>
      ) : (
        <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
      )}
    </TouchableOpacity>
  );
};
