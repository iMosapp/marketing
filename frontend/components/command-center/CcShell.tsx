import React from 'react';
import { View, Text, ScrollView, TouchableOpacity, useWindowDimensions, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, usePathname } from 'expo-router';
import { useThemeStore } from '../../store/themeStore';
import { ScreenHeader } from '../common/ScreenHeader';
import { GOLD, TABS, tid } from './shared';

type ShellProps = { title: string; subtitle?: string; children: React.ReactNode; loading?: boolean; right?: React.ReactNode; footer?: React.ReactNode };

// The one frame every Command Center screen sits in: header, four calm tabs, scrolling body. Wide screens get a centered column.
export const CcShell = ({ title, subtitle, children, loading, right, footer }: ShellProps) => {
  const { colors } = useThemeStore();
  const router = useRouter();
  const pathname = usePathname();
  const { width } = useWindowDimensions();
  const wide = width >= 1024;
  const current = TABS.find(([k]) => (k === 'index' ? /command-center\/?$/.test(pathname) : pathname.endsWith(`/${k}`)))?.[0] || 'index';
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title={title} subtitle={subtitle} right={right} testID="cc-header" onBack={() => router.push('/(tabs)/more' as any)} />
      <View style={{ flexDirection: 'row', gap: 6, paddingHorizontal: 16, paddingVertical: 8, alignSelf: wide ? 'center' : 'stretch', width: wide ? 1100 : undefined }} {...tid('cc-nav')}>
        {TABS.map(([k, label]) => {
          const active = current === k;
          return (
            <TouchableOpacity key={k} onPress={() => router.push(`/admin/command-center${k === 'index' ? '' : '/' + k}` as any)} style={{ paddingHorizontal: 14, height: 34, borderRadius: 17, alignItems: 'center', justifyContent: 'center', backgroundColor: active ? GOLD : 'transparent', borderWidth: 1, borderColor: active ? GOLD : colors.border }} {...tid(`cc-tab-${k === 'index' ? 'focus' : k}`)}>
              <Text style={{ fontSize: 13, fontWeight: '800', color: active ? '#1C1C1E' : colors.textSecondary, letterSpacing: 0.2 }}>{label}</Text>
            </TouchableOpacity>
          );
        })}
      </View>
      {loading ? <ActivityIndicator color={GOLD} style={{ marginTop: 60 }} /> : (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: footer ? 120 : 60, gap: 20, alignSelf: wide ? 'center' : 'stretch', width: wide ? 1100 : undefined }} keyboardShouldPersistTaps="handled">
          {children}
        </ScrollView>
      )}
      {footer}
    </SafeAreaView>
  );
};

export const Card = ({ children, colors, accent, testID, onPress, style }: { children: React.ReactNode; colors: any; accent?: string; testID?: string; onPress?: () => void; style?: any }) => {
  const body = (
    <View style={[{ backgroundColor: colors.card, borderRadius: 18, borderWidth: 1, borderColor: colors.border, padding: 18, gap: 10, borderLeftWidth: accent ? 4 : 1, borderLeftColor: accent || colors.border }, style]} {...(onPress ? {} : tid(testID || 'cc-card'))}>
      {children}
    </View>
  );
  return onPress ? <TouchableOpacity onPress={onPress} activeOpacity={0.85} {...tid(testID || 'cc-card')}>{body}</TouchableOpacity> : body;
};

export const Eyebrow = ({ t, colors, right }: { t: string; colors: any; right?: React.ReactNode }) => (
  <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
    <Text style={{ fontSize: 11.5, fontWeight: '800', letterSpacing: 1.2, color: colors.textSecondary }}>{t}</Text>
    {right}
  </View>
);

export const Progress = ({ pct, color, colors, testID }: { pct: number; color?: string; colors: any; testID?: string }) => (
  <View style={{ height: 6, borderRadius: 3, backgroundColor: colors.border, overflow: 'hidden' }} {...tid(testID || 'cc-progress')}>
    <View style={{ width: `${Math.max(0, Math.min(100, pct))}%`, height: 6, backgroundColor: color || GOLD }} />
  </View>
);

export const Pill = ({ text, color, icon, testID }: { text: string; color: string; icon?: any; testID?: string }) => (
  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 9, height: 24, borderRadius: 12, backgroundColor: color + '22', alignSelf: 'flex-start' }} {...tid(testID || 'cc-pill')}>
    {icon && <Ionicons name={icon} size={12} color={color} />}
    <Text style={{ fontSize: 11.5, fontWeight: '800', color }}>{text}</Text>
  </View>
);

export const Empty = ({ t, colors, testID }: { t: string; colors: any; testID?: string }) => (
  <Text style={{ fontSize: 13.5, color: colors.textSecondary, lineHeight: 19 }} {...tid(testID || 'cc-empty')}>{t}</Text>
);
