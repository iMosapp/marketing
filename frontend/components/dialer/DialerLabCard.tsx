import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useThemeStore } from '../../store/themeStore';
import { GOLD, RED, BLUE, tid, useDialerConfig } from './shared';

// Test Lab entry: the three doors into the feature + what the account still needs before a real test call.
export const DialerLabCard = () => {
  const router = useRouter();
  const { colors } = useThemeStore();
  const { config } = useDialerConfig();
  const Tile = ({ icon, color, title, sub, route, testID }: { icon: any; color: string; title: string; sub: string; route: string; testID: string }) => (
    <TouchableOpacity onPress={() => router.push(route as any)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: colors.bg, borderRadius: 12, padding: 12, borderWidth: 1, borderColor: colors.border }} {...tid(testID)}>
      <Ionicons name={icon} size={18} color={color} />
      <View style={{ flex: 1 }}><Text style={{ fontSize: 13.5, fontWeight: '800', color: colors.text }}>{title}</Text><Text style={{ fontSize: 11.5, color: colors.textSecondary }}>{sub}</Text></View>
      <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
    </TouchableOpacity>
  );
  return (
    <View style={{ gap: 8 }} {...tid('dialer-lab-card')}>
      <Tile icon="call" color={GOLD} title="Power Dialer" sub="Campaigns, lists, start a session" route="/dialer" testID="dialer-lab-open" />
      <Tile icon="ban" color={RED} title="Do Not Call" sub={config?.registry?.numbers ? `${config.registry.numbers.toLocaleString()} registry numbers loaded` : 'Registry not loaded yet'} route="/dialer/dnc" testID="dialer-lab-dnc" />
      <Tile icon="git-network" color={BLUE} title="GoHighLevel" sub="Connect a sub-account with a Private Integration Token" route="/admin/ghl" testID="dialer-lab-ghl" />
      {config && (!config.has_phone || !config.has_number) && <Text style={{ fontSize: 11.5, color: '#FF9500', lineHeight: 16 }}>{!config.has_phone ? 'Your profile has no cell number (the dialer rings you there). ' : ''}{!config.has_number ? 'You have no work number for caller ID.' : ''}</Text>}
    </View>
  );
};
