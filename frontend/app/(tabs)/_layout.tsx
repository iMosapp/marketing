import { Tabs, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '../../store/authStore';
import { useEffect, useState, useCallback } from 'react';
import { View, Platform, Text, TouchableOpacity, StyleSheet, ScrollView, Pressable, Animated } from 'react-native';
import api from '../../services/api';
import { useWebSocket } from '../../hooks/useWebSocket';
import { useNotifications } from '../../hooks/useNotifications';

const IS_WEB = Platform.OS === 'web';

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

// Notification bell + dropdown component
function NotificationBell({ unreadCount, notifications, onMarkAllRead, onNotificationPress, onRefresh }: any) {
  const [open, setOpen] = useState(false);

  return (
    <View style={bellStyles.wrapper}>
      <TouchableOpacity
        style={bellStyles.button}
        onPress={() => { setOpen(!open); if (!open) onRefresh(); }}
        data-testid="notification-bell"
      >
        <Ionicons name="notifications-outline" size={24} color="#FFF" />
        {unreadCount > 0 && (
          <View style={bellStyles.badge}>
            <Text style={bellStyles.badgeText}>{unreadCount > 99 ? '99+' : unreadCount}</Text>
          </View>
        )}
      </TouchableOpacity>
      
      {open && (
        <Pressable style={bellStyles.overlay} onPress={() => setOpen(false)}>
          <Pressable style={bellStyles.dropdown} onPress={(e) => e.stopPropagation()}>
            <View style={bellStyles.dropdownHeader}>
              <Text style={bellStyles.dropdownTitle}>Notifications</Text>
              {unreadCount > 0 && (
                <TouchableOpacity onPress={() => { onMarkAllRead(); }} data-testid="mark-all-read-btn">
                  <Text style={bellStyles.markAll}>Mark all read</Text>
                </TouchableOpacity>
              )}
            </View>
            <ScrollView style={bellStyles.list} contentContainerStyle={{ paddingBottom: 8 }}>
              {notifications.length === 0 ? (
                <Text style={bellStyles.empty}>No notifications</Text>
              ) : (
                notifications.slice(0, 20).map((n: any) => (
                  <TouchableOpacity
                    key={n.id}
                    style={[bellStyles.item, !n.read && bellStyles.itemUnread]}
                    onPress={() => { onNotificationPress(n); setOpen(false); }}
                    data-testid={`notification-item-${n.id}`}
                  >
                    <View style={bellStyles.itemDot}>
                      {!n.read && <View style={bellStyles.dot} />}
                    </View>
                    <View style={bellStyles.itemContent}>
                      <Text style={bellStyles.itemTitle} numberOfLines={1}>{n.title}</Text>
                      <Text style={bellStyles.itemBody} numberOfLines={2}>{n.message || n.body || ''}</Text>
                      <Text style={bellStyles.itemTime}>{formatTime(n.created_at)}</Text>
                    </View>
                    <Ionicons
                      name={getNotifIcon(n.type)}
                      size={18}
                      color={getNotifColor(n.type)}
                    />
                  </TouchableOpacity>
                ))
              )}
            </ScrollView>
          </Pressable>
        </Pressable>
      )}
    </View>
  );
}

function getNotifIcon(type: string) {
  switch (type) {
    case 'new_lead': case 'lead_assigned': return 'person-add';
    case 'jump_ball': return 'flash';
    case 'team_mention': return 'at';
    case 'team_broadcast': return 'megaphone';
    case 'team_chat': return 'chatbox';
    case 'new_message': return 'chatbubble';
    default: return 'notifications';
  }
}

function getNotifColor(type: string) {
  switch (type) {
    case 'new_lead': return '#007AFF';
    case 'jump_ball': return '#FF9500';
    case 'team_mention': return '#C9A962';
    case 'team_broadcast': return '#5856D6';
    case 'team_chat': return '#34C759';
    case 'new_message': return '#007AFF';
    default: return '#8E8E93';
  }
}

function formatTime(isoString: string) {
  try {
    const d = new Date(isoString);
    const now = new Date();
    const diff = now.getTime() - d.getTime();
    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    return d.toLocaleDateString();
  } catch { return ''; }
}

export default function TabLayout() {
  const { user, isAuthenticated, isLoading } = useAuthStore();
  const router = useRouter();
  
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  
  // WebSocket for real-time
  const { connected, subscribe } = useWebSocket();
  
  // Notifications
  const {
    notifications,
    unreadCount,
    refreshNotifications,
    markAsRead,
    markAllRead,
  } = useNotifications();
  
  // Team chat unread count
  const [teamUnreadCount, setTeamUnreadCount] = useState(0);
  
  const fetchTeamUnreadCount = useCallback(async () => {
    if (!user?._id) return;
    try {
      const response = await api.get(`/team-chat/channels?user_id=${user._id}`);
      if (response.data.success) {
        const total = response.data.channels.reduce((sum: number, ch: any) => sum + (ch.unread_count || 0), 0);
        setTeamUnreadCount(total);
      }
    } catch (error) {
      // Silently fail
    }
  }, [user?._id]);
  
  // Inbox unread count
  const [inboxUnreadCount, setInboxUnreadCount] = useState(0);
  
  const fetchInboxUnreadCount = useCallback(async () => {
    if (!user?._id) return;
    try {
      const response = await api.get(`/messages/conversations/${user._id}`);
      if (Array.isArray(response.data)) {
        const total = response.data.filter((c: any) => c.unread_count > 0).length;
        setInboxUnreadCount(total);
      }
    } catch (error) { /* silent */ }
  }, [user?._id]);
  
  // Initial data fetch
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

  // WebSocket event handler for real-time updates
  useEffect(() => {
    if (!subscribe) return;
    const unsub = subscribe((msg: any) => {
      if (msg.type === 'team_chat_message') {
        // Bump team unread count
        setTeamUnreadCount(prev => prev + 1);
      }
      if (msg.type === 'notification_update') {
        // Refresh notification count
        refreshNotifications();
        if (msg.reason === 'team_chat') {
          setTeamUnreadCount(prev => prev + 1);
        }
        if (msg.reason === 'new_message') {
          setInboxUnreadCount(prev => prev + 1);
        }
      }
      if (msg.type === 'new_customer_message') {
        setInboxUnreadCount(prev => prev + 1);
      }
    });
    return unsub;
  }, [subscribe, refreshNotifications]);
  
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

  const handleNotificationPress = useCallback((n: any) => {
    markAsRead(n.id);
    if (n.conversation_id) {
      router.push(`/inbox/${n.conversation_id}`);
    } else if (n.channel_id) {
      router.push('/team' as any);
    }
  }, [markAsRead, router]);
  
  const isPending = user?.status === 'pending';

  return (
    <>
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
          tabBarActiveTintColor: '#007AFF',
          tabBarInactiveTintColor: '#8E8E93',
          tabBarLabelStyle: {
            fontSize: 10,
            fontWeight: '600',
          },
        }}
      >
        <Tabs.Screen
          name="inbox"
          options={{
            title: 'Inbox',
            tabBarIcon: ({ color, size }) => (
              <View>
                <Ionicons name="chatbubbles" size={size} color={isPending ? '#3C3C3E' : color} />
                {mounted && inboxUnreadCount > 0 && (
                  <View style={{
                    position: 'absolute',
                    top: -4,
                    right: -10,
                    backgroundColor: '#FF3B30',
                    borderRadius: 10,
                    minWidth: 18,
                    height: 18,
                    justifyContent: 'center',
                    alignItems: 'center',
                    paddingHorizontal: 4,
                  }}>
                    <Text style={{ fontSize: 10, fontWeight: '700', color: '#FFF' }}>
                      {inboxUnreadCount > 99 ? '99+' : inboxUnreadCount}
                    </Text>
                  </View>
                )}
              </View>
            ),
            tabBarLabelStyle: {
              fontSize: 10,
              fontWeight: '600',
              color: isPending ? '#3C3C3E' : undefined,
            },
          }}
          listeners={{
            tabPress: (e) => {
              if (isPending) e.preventDefault();
              if (!isPending) setInboxUnreadCount(0);
            },
          }}
        />
      <Tabs.Screen
        name="dialer"
        options={{
          title: 'Keypad',
          headerTitle: '',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="keypad" size={size} color={isPending ? '#3C3C3E' : color} />
          ),
          tabBarLabelStyle: {
            fontSize: 10,
            fontWeight: '600',
            color: isPending ? '#3C3C3E' : undefined,
          },
        }}
        listeners={{
          tabPress: (e) => {
            if (isPending) e.preventDefault();
          },
        }}
      />
      <Tabs.Screen
        name="contacts"
        options={{
          title: 'Contacts',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="people" size={size} color={isPending ? '#3C3C3E' : color} />
          ),
          tabBarLabelStyle: {
            fontSize: 10,
            fontWeight: '600',
            color: isPending ? '#3C3C3E' : undefined,
          },
        }}
        listeners={{
          tabPress: (e) => {
            if (isPending) e.preventDefault();
          },
        }}
      />
      <Tabs.Screen
        name="team"
        options={{
          title: 'Team',
          tabBarIcon: ({ color, size }) => (
            <View>
              <Ionicons name="chatbox-ellipses" size={size} color={isPending ? '#3C3C3E' : color} />
              {mounted && teamUnreadCount > 0 && (
                <View style={{
                  position: 'absolute',
                  top: -4,
                  right: -10,
                  backgroundColor: '#FF3B30',
                  borderRadius: 10,
                  minWidth: 18,
                  height: 18,
                  justifyContent: 'center',
                  alignItems: 'center',
                  paddingHorizontal: 4,
                }}>
                  <Text style={{ fontSize: 10, fontWeight: '700', color: '#FFF' }}>
                    {teamUnreadCount > 99 ? '99+' : teamUnreadCount}
                  </Text>
                </View>
              )}
            </View>
          ),
          tabBarLabelStyle: {
            fontSize: 10,
            fontWeight: '600',
            color: isPending ? '#3C3C3E' : undefined,
          },
        }}
        listeners={{
          tabPress: (e) => {
            if (isPending) e.preventDefault();
            if (!isPending) setTeamUnreadCount(0);
          },
        }}
      />
      <Tabs.Screen
        name="more"
        options={{
          title: 'More',
          tabBarIcon: ({ color, size}) => (
            <Ionicons name="menu" size={size} color={color} />
          ),
        }}
      />
      </Tabs>
      
      {/* Notification bell - floating top right, rendered AFTER tabs for z-index */}
      {mounted && user && (
        <View style={bellStyles.container} pointerEvents="box-none">
          <NotificationBell
            unreadCount={unreadCount}
            notifications={notifications}
            onMarkAllRead={markAllRead}
            onNotificationPress={handleNotificationPress}
            onRefresh={refreshNotifications}
          />
        </View>
      )}
    </>
  );
}

const bellStyles = StyleSheet.create({
  container: {
    position: IS_WEB ? 'fixed' as any : 'absolute',
    top: IS_WEB ? 12 : 52,
    right: 16,
    zIndex: 99999,
    elevation: 99999,
  },
  wrapper: {
    position: 'relative',
  },
  button: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#1C1C1E',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: '#2C2C2E',
  },
  badge: {
    position: 'absolute',
    top: -2,
    right: -2,
    backgroundColor: '#FF3B30',
    borderRadius: 10,
    minWidth: 18,
    height: 18,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 4,
    borderWidth: 2,
    borderColor: '#000',
  },
  badgeText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#FFF',
  },
  overlay: {
    position: 'fixed' as any,
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    zIndex: 9998,
  },
  dropdown: {
    position: 'absolute',
    top: IS_WEB ? 62 : 102,
    right: 16,
    width: 340,
    maxHeight: 440,
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#2C2C2E',
    overflow: 'hidden',
    ...(IS_WEB ? {
      boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
    } : {
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 8 },
      shadowOpacity: 0.6,
      shadowRadius: 16,
      elevation: 20,
    }),
  },
  dropdownHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  dropdownTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#FFF',
  },
  markAll: {
    fontSize: 13,
    color: '#007AFF',
    fontWeight: '500',
  },
  list: {
    maxHeight: 380,
  },
  empty: {
    textAlign: 'center',
    color: '#6E6E73',
    fontSize: 14,
    paddingVertical: 40,
  },
  item: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
    gap: 10,
  },
  itemUnread: {
    backgroundColor: '#007AFF10',
  },
  itemDot: {
    width: 8,
    paddingTop: 6,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#007AFF',
  },
  itemContent: {
    flex: 1,
  },
  itemTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 2,
  },
  itemBody: {
    fontSize: 13,
    color: '#8E8E93',
    lineHeight: 18,
  },
  itemTime: {
    fontSize: 11,
    color: '#6E6E73',
    marginTop: 4,
  },
});
