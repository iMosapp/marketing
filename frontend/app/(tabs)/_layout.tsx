import { Tabs, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '../../store/authStore';
import { useEffect, useState, useCallback } from 'react';
import { View, Platform } from 'react-native';
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
  const { user } = useAuthStore();
  const router = useRouter();
  
  // Track if component is mounted (for hydration safety)
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  
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