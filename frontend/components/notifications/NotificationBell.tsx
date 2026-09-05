import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useNotifications } from '../../hooks/useNotifications';
import { useThemeStore } from '../../store/themeStore';

// Bell = badge + one tap straight into the Alerts screen (no dropdown to dig through).
export function NotificationBell() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { unreadCount } = useNotifications();

  return (
    <View style={styles.wrapper}>
      <TouchableOpacity
        style={styles.button}
        onPress={() => router.push('/notifications' as any)}
        testID="notification-bell-btn"
        {...({ dataSet: { testid: 'notification-bell-btn' } } as any)}
      >
        <Ionicons name="notifications-outline" size={22} color={colors.text} />
        {unreadCount > 0 && (
          <View style={styles.badge} testID="notification-bell-badge" {...({ dataSet: { testid: 'notification-bell-badge' } } as any)}>
            <Text maxFontSizeMultiplier={1} style={styles.badgeText}>{unreadCount > 99 ? '99+' : unreadCount}</Text>
          </View>
        )}
      </TouchableOpacity>
    </View>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  wrapper: { position: 'relative' },
  button: {
    width: 40, height: 40, borderRadius: 12,
    backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center',
    borderWidth: 1, borderColor: colors.surface,
  },
  badge: {
    position: 'absolute', top: -6, right: -6,
    backgroundColor: '#FF3B30', borderRadius: 10, minWidth: 20, height: 20,
    alignItems: 'center', justifyContent: 'center', paddingHorizontal: 5,
    borderWidth: 1.5, borderColor: '#fff',
  },
  badgeText: { color: '#fff', fontSize: 11, fontWeight: '700' },
});

export default NotificationBell;
