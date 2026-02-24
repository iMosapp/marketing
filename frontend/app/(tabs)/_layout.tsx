import { Tabs, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '../../store/authStore';
import { useEffect, useState, useCallback } from 'react';
import { View, Platform, Text } from 'react-native';
import api from '../../services/api';
// Temporarily disabled notification modal due to module resolution issue
// import { useNotifications } from '../../hooks/useNotifications';
// import { LeadNotificationModal } from '../../components/notifications/LeadNotificationModal';

const IS_WEB = Platform.OS === 'web';

// Get the initial tab based on user role
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
  const { user, isAuthenticated, isLoading } = useAuthStore();
  const router = useRouter();
  
  // Track if component is mounted (for hydration safety)
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  
  // Team chat unread count
  const [teamUnreadCount, setTeamUnreadCount] = useState(0);
  
  // Fetch team unread count periodically
  const fetchTeamUnreadCount = useCallback(async () => {
    if (!user?._id) return;
    
    try {
      const response = await api.get(`/team-chat/channels?user_id=${user._id}`);
      if (response.data.success) {
        const total = response.data.channels.reduce((sum: number, ch: any) => sum + (ch.unread_count || 0), 0);
        setTeamUnreadCount(total);
      }
    } catch (error) {
      // Silently fail - just don't show badge
    }
  }, [user?._id]);
  
  useEffect(() => {
    if (mounted && user?._id) {
      fetchTeamUnreadCount();
      const interval = setInterval(fetchTeamUnreadCount, 10000); // Poll every 10 seconds
      return () => clearInterval(interval);
    }
  }, [mounted, user?._id, fetchTeamUnreadCount]);
  
  // Protect tabs - redirect to login if not authenticated
  useEffect(() => {
    if (mounted && !isLoading && !isAuthenticated) {
      router.replace('/auth/login');
    }
  }, [mounted, isLoading, isAuthenticated]);
  
  // Check if user needs to complete onboarding (first login verification)
  useEffect(() => {
    if (mounted && !isLoading && isAuthenticated && user && !user.onboarding_complete) {
      // Redirect to onboarding for profile verification
      router.replace('/onboarding');
    }
  }, [mounted, isLoading, isAuthenticated, user?.onboarding_complete]);
  
  // Notification system temporarily disabled
  const pendingNotification = null;
  const unreadCount = 0;
  const clearPendingNotification = () => {};
  
  const [showNotificationModal, setShowNotificationModal] = useState(false);
  
  // Show modal when there's a pending notification
  useEffect(() => {
    if (pendingNotification && mounted) {
      setShowNotificationModal(true);
    }
  }, [pendingNotification, mounted]);
  
  const handleNotificationDismiss = useCallback(() => {
    setShowNotificationModal(false);
    clearPendingNotification();
  }, [clearPendingNotification]);
  
  const handleNotificationAction = useCallback(() => {
    setShowNotificationModal(false);
    clearPendingNotification();
  }, [clearPendingNotification]);
  
  // Check if user has restricted access (pending status)
  const isPending = user?.status === 'pending';
  const needsOnboarding = user?.needs_onboarding === true;
  
  // Badge should only show after mount to prevent hydration mismatch
  const showBadge = mounted && unreadCount > 0;
  
  // Redirect pending users trying to access restricted tabs
  useEffect(() => {
    if (isPending || needsOnboarding) {
      // Will be handled by individual screens
    }
  }, [isPending, needsOnboarding]);
  
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
                {showBadge && (
                  <View style={{
                    position: 'absolute',
                    top: -4,
                    right: -8,
                    backgroundColor: '#FF3B30',
                    borderRadius: 10,
                    minWidth: 18,
                    height: 18,
                    justifyContent: 'center',
                    alignItems: 'center',
                    paddingHorizontal: 4,
                  }}>
                    <Ionicons name="flash" size={10} color="#FFF" />
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
              if (isPending) {
                e.preventDefault();
                // Could show alert here
              }
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
            if (isPending) {
              e.preventDefault();
            }
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
            if (isPending) {
              e.preventDefault();
            }
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
            if (isPending) {
              e.preventDefault();
            }
            // Reset unread count when navigating to Team tab
            if (!isPending) {
              setTeamUnreadCount(0);
            }
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
      
      {/* Lead Notification Modal - temporarily disabled */}
      {/* <LeadNotificationModal
        visible={showNotificationModal}
        notification={pendingNotification}
        onDismiss={handleNotificationDismiss}
        onActionComplete={handleNotificationAction}
      /> */}
    </>
  );
}