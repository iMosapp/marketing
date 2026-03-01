import { Tabs, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { useEffect, useState, useCallback } from 'react';
import { View, Text } from 'react-native';
import api from '../../services/api';
import { useWebSocket } from '../../hooks/useWebSocket';

const getInitialTab = (role?: string): string => {
  switch (role) {
    case 'super_admin':
    case 'org_admin':
    case 'store_manager':
      return 'more';
    default:
      return 'inbox';
  }
};

export default function TabLayout() {
  const { user, isAuthenticated, isLoading, partnerBranding } = useAuthStore();
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  // WebSocket for real-time
  const { subscribe } = useWebSocket();

  // Tab badge counts
  const [teamUnreadCount, setTeamUnreadCount] = useState(0);
  const [inboxUnreadCount, setInboxUnreadCount] = useState(0);

  const fetchTeamUnreadCount = useCallback(async () => {
    if (!user?._id) return;
    try {
      const response = await api.get(`/team-chat/channels?user_id=${user._id}`);
      if (response.data.success) {
        const total = response.data.channels.reduce((sum: number, ch: any) => sum + (ch.unread_count || 0), 0);
        setTeamUnreadCount(total);
      }
    } catch { /* silent */ }
  }, [user?._id]);

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
      fetchTeamUnreadCount();
      fetchInboxUnreadCount();
      const interval = setInterval(() => {
        fetchTeamUnreadCount();
        fetchInboxUnreadCount();
      }, 15000);
      return () => clearInterval(interval);
    }
  }, [mounted, user?._id, fetchTeamUnreadCount, fetchInboxUnreadCount]);

  // WebSocket real-time updates
  useEffect(() => {
    if (!subscribe) return;
    return subscribe((msg: any) => {
      if (msg.type === 'team_chat_message' || (msg.type === 'notification_update' && msg.reason === 'team_chat')) {
        setTeamUnreadCount(prev => prev + 1);
      }
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
  const colors = useThemeStore((state) => state.colors);

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
          <Text style={{ fontSize: 10, fontWeight: '700', color: '#FFF' }}>
            {count > 99 ? '99+' : count}
          </Text>
        </View>
      )}
    </View>
  );

  return (
    <Tabs
      initialRouteName={getInitialTab(user?.role)}
      screenOptions={{
        headerShown: false,
        tabBarStyle: {
          backgroundColor: '#000',
          borderTopColor: '#2C2C2E',
          borderTopWidth: 1,
          height: 88,
          paddingBottom: 32,
          paddingTop: 8,
        },
        tabBarActiveTintColor: partnerBranding?.primary_color || '#007AFF',
        tabBarInactiveTintColor: '#8E8E93',
        tabBarLabelStyle: { fontSize: 10, fontWeight: '600' },
      }}
    >
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
        name="dialer"
        options={{
          title: 'Keypad',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="keypad" size={size} color={isPending ? '#3C3C3E' : color} />
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
        name="team"
        options={{
          title: 'Team',
          tabBarIcon: ({ color, size }) => (
            <BadgeIcon name="chatbox-ellipses" color={color} size={size} count={teamUnreadCount} />
          ),
        }}
        listeners={{
          tabPress: (e) => {
            if (isPending) e.preventDefault();
            else setTeamUnreadCount(0);
          },
        }}
      />
      <Tabs.Screen
        name="more"
        options={{
          title: 'More',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="menu" size={size} color={color} />
          ),
        }}
      />
    </Tabs>
  );
}
