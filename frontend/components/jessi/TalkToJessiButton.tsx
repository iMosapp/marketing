import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useThemeStore } from '../../store/themeStore';
import { showAlert } from '../../services/alert';
import { GOLD, tid } from '../scripts/shared';
import { liveSupported } from '../../hooks/useLiveJessi';
import { useLiveJessiLauncher } from './LiveJessiProvider';
import { useLiveConfig } from './useLiveConfig';

// Home entry point. Hidden until the Test Lab flag is live for this rep (super admins always see it).
export const TalkToJessiButton = () => {
  const router = useRouter();
  const { colors } = useThemeStore();
  const { config, reload } = useLiveConfig();
  const jessi = useLiveJessiLauncher();
  if (!config?.available) return null;
  if (!config.configured && !config.is_super_admin) return null;

  const press = () => {
    if (!config.configured) { router.push('/admin/voice-lab' as any); return; }
    if (!liveSupported()) {
      showAlert('Live Jessi is on the web app for now', 'Open app.imonsocial.com in Safari or Chrome to talk to her live. Opening the current Ask Jessi instead.', [{ text: 'OK', onPress: () => router.push('/jessie' as any) }]);
      return;
    }
    jessi.open({ options: { mode: 'assistant' }, onClose: reload });
  };
  const sub = !config.configured ? 'Needs OPENAI_API_KEY on the server. Tap to open the Voice Lab.' : config.usage.left_s <= 0 ? "Today's minutes are used up, back at midnight" : 'Who to call today, text someone, pull up a contact. Just talk.';

  return (
    <TouchableOpacity onPress={press} activeOpacity={0.85} style={{ marginHorizontal: 16, marginBottom: 16, borderRadius: 18, padding: 14, backgroundColor: colors.card, borderWidth: 1.5, borderColor: `${GOLD}66`, flexDirection: 'row', alignItems: 'center', gap: 12 }} {...tid('talk-to-jessi-btn')}>
      <View style={{ width: 46, height: 46, borderRadius: 23, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center' }}>
        <Ionicons name="mic" size={22} color="#0B0B0D" />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text }}>Talk to Jessi</Text>
        <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }} numberOfLines={2}>{sub}</Text>
      </View>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: `${GOLD}22`, borderRadius: 12, paddingHorizontal: 9, paddingVertical: 5 }}>
        <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: GOLD }} />
        <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 0.6 }}>{jessi.active ? 'ON' : 'LIVE'}</Text>
      </View>
    </TouchableOpacity>
  );
};
