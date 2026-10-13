import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useThemeStore } from '../../store/themeStore';
import { GOLD, tid } from '../scripts/shared';
import { liveSupported } from '../../hooks/useLiveJessi';
import { useLiveJessiLauncher } from './LiveJessiProvider';
import { useLiveConfig } from './useLiveConfig';

const ORANGE = '#FF9500';
const resetLabel = (iso?: string) => {
  const d = iso ? new Date(iso) : null;
  if (!d || isNaN(d.getTime())) return 'midnight';
  const sameDay = d.toDateString() === new Date().toDateString();
  const t = d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
  return sameDay ? t : `midnight (${t})`;
};

// Home entry point for Jessi. Live voice when it is on for this rep and the build supports it, else the Jessi screen.
export const TalkToJessiButton = () => {
  const router = useRouter();
  const { colors } = useThemeStore();
  const { config, reload } = useLiveConfig();
  const jessi = useLiveJessiLauncher();
  const liveOn = !!config?.available && !!config.configured;
  const paused = liveOn && !!config!.controls?.killed;
  const capHit = liveOn && config!.usage.left_s <= 0;
  const liveReady = liveOn && !capHit && liveSupported();
  const needsKey = !!config?.available && !config.configured && config.is_super_admin;

  const press = () => {
    if (needsKey || (capHit && config?.is_super_admin && !paused)) { router.push('/admin/voice-lab' as any); return; }
    if (liveReady) { jessi.open({ options: { mode: 'assistant' }, onClose: reload }); return; }
    router.push('/(tabs)/jessi' as any);
  };
  const capMin = Math.round((config?.usage.cap_s || 0) / 60);
  const sub = needsKey ? 'Needs OPENAI_API_KEY on the server. Tap to open the Voice Lab.'
    : paused ? 'Live Jessi is paused for your account by the account owner. Ask me by text instead.'
    : capHit ? `All ${capMin} live minutes for today are used. Back at ${resetLabel(config?.usage.reset_at)}.${config?.is_super_admin ? ' Tap to raise the daily cap in the Voice Lab.' : ' Until then, ask me by text or voice note.'}`
    : liveReady ? 'Who to call today, text someone, pull up a contact. Just talk.'
    : 'Ask about a customer, who to follow up with, or what to send.';
  const title = paused ? 'Live Jessi is paused' : capHit ? 'Live Jessi is resting' : liveReady ? 'Talk to Jessi' : 'Ask Jessi';

  return (
    <TouchableOpacity onPress={press} activeOpacity={0.85} style={{ marginHorizontal: 16, marginBottom: 16, borderRadius: 18, padding: 14, backgroundColor: colors.card, borderWidth: 1.5, borderColor: capHit ? `${ORANGE}88` : `${GOLD}66`, flexDirection: 'row', alignItems: 'center', gap: 12 }} {...tid('talk-to-jessi-btn')}>
      <View style={{ width: 46, height: 46, borderRadius: 23, backgroundColor: capHit ? ORANGE : GOLD, alignItems: 'center', justifyContent: 'center' }}>
        <Ionicons name={capHit ? 'hourglass' : liveReady ? 'mic' : 'sparkles'} size={22} color="#0B0B0D" />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text }} {...tid('talk-to-jessi-title')}>{title}</Text>
        <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }} numberOfLines={3} {...tid('talk-to-jessi-sub')}>{sub}</Text>
      </View>
      {liveReady || capHit ? (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: capHit ? `${ORANGE}22` : `${GOLD}22`, borderRadius: 12, paddingHorizontal: 9, paddingVertical: 5 }} {...tid('talk-to-jessi-badge')}>
          <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: capHit ? ORANGE : GOLD }} />
          <Text style={{ fontSize: 11, fontWeight: '800', color: capHit ? ORANGE : GOLD, letterSpacing: 0.6 }}>{capHit ? 'CAP' : jessi.active ? 'ON' : 'LIVE'}</Text>
        </View>
      ) : (
        <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
      )}
    </TouchableOpacity>
  );
};
