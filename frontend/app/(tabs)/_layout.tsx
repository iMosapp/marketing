import { Tabs, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { useEffect, useState, useCallback } from 'react';
import { View, Text } from 'react-native';
import api from '../../services/api';
import { useWebSocket } from '../../hooks/useWebSocket';

export default function TabLayout() {
  const { colors } = useThemeStore();
  const { user, isAuthenticated, isLoading, partnerBranding } = useAuthStore();
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  // WebSocket for real-time
  const { subscribe } = useWebSocket();

  // Tab badge counts
  const [inboxUnreadCount, setInboxUnreadCount] = useState(0);

  const fetchInboxUnreadCount = useCallback(async () => {
    if (!user?._id) return;
    try {
      const response = await api.get(`/messages/conversations/${user._id}`);
      if (Array.isArray(response.data)) {
        const total = response.data.filter((c: any) => c.unread_count > 0).length;
        setInboxUnreadCount(total);
      }
    } catch { /* silent */ }
  }, [user?._id]);

  // Initial fetch + polling
  useEffect(() => {
    if (mounted && user?._id) {
      fetchInboxUnreadCount();
      const interval = setInterval(() => {
        fetchInboxUnreadCount();
      }, 15000);
      return () => clearInterval(interval);
    }
  }, [mounted, user?._id, fetchInboxUnreadCount]);

  // WebSocket real-time updates
  useEffect(() => {
    if (!subscribe) return;
    return subscribe((msg: any) => {
      if (msg.type === 'new_customer_message' || (msg.type === 'notification_update' && msg.reason === 'new_message')) {
        setInboxUnreadCount(prev => prev + 1);
      }
    });
  }, [subscribe]);

  // Auth redirect
  useEffect(() => {
    if (mounted && !isLoading && !isAuthenticated) {
      router.replace('/auth/login');
    }
  }, [mounted, isLoading, isAuthenticated]);

  useEffect(() => {
    if (mounted && !isLoading && isAuthenticated && user && !user.onboarding_complete) {
      router.replace('/onboarding');
    }
  }, [mounted, isLoading, isAuthenticated, user?.onboarding_complete]);

  const isPending = user?.status === 'pending';

  const BadgeIcon = ({ name, color, size, count }: { name: string; color: string; size: number; count: number }) => (
    <View>
      <Ionicons name={name as any} size={size} color={isPending ? '#3C3C3E' : color} />
      {mounted && count > 0 && (
        <View style={{
          position: 'absolute', top: -4, right: -10,
          backgroundColor: '#FF3B30', borderRadius: 10,
          minWidth: 18, height: 18,
          justifyContent: 'center', alignItems: 'center', paddingHorizontal: 4,
        }}>
          <Text style={{ fontSize: 10, fontWeight: '700', color: colors.text }}>
            {count > 99 ? '99+' : count}
          </Text>
        </View>
      )}
    </View>
  );

  return (
    <Tabs
      initialRouteName="home"
      screenOptions={{
        headerShown: false,
        tabBarStyle: {
          backgroundColor: colors.tabBar,
          borderTopColor: colors.tabBarBorder,
          borderTopWidth: 1,
          height: 88,
          paddingBottom: 32,
          paddingTop: 8,
        },
        tabBarActiveTintColor: partnerBranding?.primary_color || '#C9A962',
        tabBarInactiveTintColor: colors.textSecondary,
        tabBarLabelStyle: { fontSize: 10, fontWeight: '600' },
      }}
    >
      <Tabs.Screen
        name="home"
        options={{
          title: 'Home',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="home" size={size} color={isPending ? '#3C3C3E' : color} />
          ),
        }}
        listeners={{ tabPress: (e) => { if (isPending) e.preventDefault(); } }}
      />
      <Tabs.Screen
        name="contacts"
        options={{
          title: 'Contacts',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="people" size={size} color={isPending ? '#3C3C3E' : color} />
          ),
        }}
        listeners={{ tabPress: (e) => { if (isPending) e.preventDefault(); } }}
      />
      <Tabs.Screen
        name="activity"
        options={{
          title: 'Activity',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="pulse" size={size} color={isPending ? '#3C3C3E' : color} />
          ),
        }}
        listeners={{ tabPress: (e) => { if (isPending) e.preventDefault(); } }}
      />
      <Tabs.Screen
        name="inbox"
        options={{
          title: 'Inbox',
          tabBarIcon: ({ color, size }) => (
            <BadgeIcon name="chatbubbles" color={color} size={size} count={inboxUnreadCount} />
          ),
        }}
        listeners={{
          tabPress: (e) => {
            if (isPending) e.preventDefault();
            else setInboxUnreadCount(0);
          },
        }}
      />
      <Tabs.Screen
        name="more"
        options={{
          title: 'Hub',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="apps" size={size} color={color} />
          ),
        }}
      />
      {/* Hidden tabs - accessible via Menu but not shown in tab bar */}
      <Tabs.Screen name="dialer" options={{ href: null }} />
      <Tabs.Screen name="team" options={{ href: null }} />
      <Tabs.Screen name="touchpoints" options={{ href: null }} />
      <Tabs.Screen name="activity-feed" options={{ href: null }} />
      <Tabs.Screen name="ai-outreach" options={{ href: null }} />
      <Tabs.Screen name="notifications" options={{ href: null }} />
    </Tabs>
  );
}
