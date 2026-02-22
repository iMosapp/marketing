import { Tabs, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '../../store/authStore';
import { useEffect, useState } from 'react';
import { View } from 'react-native';
import { useNotifications } from '../../hooks/useNotifications';
import { LeadNotificationModal } from '../../components/notifications/LeadNotificationModal';

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
  
  // Notification system
  const { 
    pendingNotification, 
    unreadCount, 
    clearPendingNotification 
  } = useNotifications(5000); // Poll every 5 seconds
  
  const [showNotificationModal, setShowNotificationModal] = useState(false);
  
  // Show modal when there's a pending notification
  useEffect(() => {
    if (pendingNotification) {
      setShowNotificationModal(true);
    }
  }, [pendingNotification]);
  
  const handleNotificationDismiss = () => {
    setShowNotificationModal(false);
    clearPendingNotification();
  };
  
  const handleNotificationAction = () => {
    setShowNotificationModal(false);
    clearPendingNotification();
  };
  
  // Check if user has restricted access (pending status)
  const isPending = user?.status === 'pending';
  const needsOnboarding = user?.needs_onboarding === true;
  
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
                {unreadCount > 0 && (
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
      
      {/* Lead Notification Modal */}
      <LeadNotificationModal
        visible={showNotificationModal}
        notification={pendingNotification}
        onDismiss={handleNotificationDismiss}
        onActionComplete={handleNotificationAction}
      />
    </>
  );
}