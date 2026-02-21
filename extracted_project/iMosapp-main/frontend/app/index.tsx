import { useEffect, useState } from 'react';
import { View, ActivityIndicator, StyleSheet } from 'react-native';
import { useRouter, useRootNavigationState } from 'expo-router';
import { useAuthStore } from '../store/authStore';

// Helper to get the right landing page based on user role
const getDefaultRoute = (role?: string): string => {
  switch (role) {
    case 'super_admin':
    case 'org_admin':
    case 'store_manager':
      return '/(tabs)/more';  // Admins and managers go to More tab
    default:
      return '/(tabs)/inbox'; // Regular users go to Inbox
  }
};

export default function Index() {
  const router = useRouter();
  const { isAuthenticated, isLoading, user } = useAuthStore();
  const rootNavigationState = useRootNavigationState();
  const [hasNavigated, setHasNavigated] = useState(false);
  
  useEffect(() => {
    // Wait until navigation is ready before attempting to navigate
    if (!rootNavigationState?.key) return;
    if (hasNavigated) return;
    
    if (!isLoading) {
      setHasNavigated(true);
      if (!isAuthenticated) {
        router.replace('/auth/login');
      } else if (user?.needs_onboarding || user?.status === 'pending') {
        // New users (independent or pending) go to onboarding
        router.replace('/onboarding');
      } else if (!user?.onboarding_complete) {
        // Legacy check for onboarding
        router.replace('/onboarding');
      } else {
        // Navigate based on user role
        router.replace(getDefaultRoute(user?.role) as any);
      }
    }
  }, [isAuthenticated, isLoading, user, rootNavigationState?.key, hasNavigated]);
  
  return (
    <View style={styles.container}>
      <ActivityIndicator size="large" color="#007AFF" />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
    alignItems: 'center',
    justifyContent: 'center',
  },
});