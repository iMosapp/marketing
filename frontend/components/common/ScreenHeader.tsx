import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useThemeStore } from '../../store/themeStore';
import { FS } from '../../constants/typography';

const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });

interface Props {
  title: string;
  subtitle?: string;
  onBack?: () => void;
  right?: React.ReactNode;
  testID?: string;
  noBorder?: boolean;
}

// One nav bar for every Tools screen: gold back chevron, centered 17/700 title, optional right action.
export function ScreenHeader({ title, subtitle, onBack, right, testID = 'screen-header', noBorder }: Props) {
  const router = useRouter();
  const { colors } = useThemeStore();
  // Deep links and refreshes have no history; fall back to the Tools tab instead of doing nothing.
  const goBack = () => (router.canGoBack() ? router.back() : router.replace('/(tabs)/more' as any));
  return (
    <View style={[styles.wrap, !noBorder && { borderBottomWidth: 1, borderBottomColor: colors.border }]} {...tid(testID)}>
      <TouchableOpacity onPress={onBack || goBack} style={styles.side} hitSlop={8} {...tid(`${testID}-back`)}>
        <Ionicons name="chevron-back" size={26} color={colors.accent} />
      </TouchableOpacity>
      <View style={styles.center}>
        <Text style={[styles.title, { color: colors.text }]} numberOfLines={1} maxFontSizeMultiplier={1.2}>{title}</Text>
        {subtitle ? <Text style={[styles.subtitle, { color: colors.textSecondary }]} numberOfLines={1} maxFontSizeMultiplier={1.2}>{subtitle}</Text> : null}
      </View>
      <View style={[styles.side, { alignItems: 'flex-end' }]}>{right || null}</View>
    </View>
  );
}

export function HeaderIconButton({ icon, onPress, testID, color, disabled }: { icon: any; onPress: () => void; testID: string; color?: string; disabled?: boolean }) {
  const { colors } = useThemeStore();
  return (
    <TouchableOpacity onPress={onPress} disabled={disabled} style={[styles.iconBtn, disabled && { opacity: 0.4 }]} hitSlop={8} {...tid(testID)}>
      <Ionicons name={icon} size={24} color={color || colors.accent} />
    </TouchableOpacity>
  );
}

export function HeaderTextButton({ label, onPress, testID, disabled }: { label: string; onPress: () => void; testID: string; disabled?: boolean }) {
  const { colors } = useThemeStore();
  return (
    <TouchableOpacity onPress={onPress} disabled={disabled} style={[styles.textBtn, disabled && { opacity: 0.4 }]} hitSlop={8} {...tid(testID)}>
      <Text style={{ fontSize: FS.heading, fontWeight: '700', color: colors.accent }} maxFontSizeMultiplier={1.2}>{label}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  wrap: { flexDirection: 'row', alignItems: 'center', height: 52, paddingHorizontal: 8 },
  side: { minWidth: 44, height: 44, justifyContent: 'center' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: FS.nav, fontWeight: '700' },
  subtitle: { fontSize: FS.caption, marginTop: 1 },
  iconBtn: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  textBtn: { height: 44, paddingHorizontal: 8, alignItems: 'center', justifyContent: 'center' },
});
