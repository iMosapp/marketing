import { useEffect, useState } from 'react';
import { View, ActivityIndicator, StyleSheet, Platform } from 'react-native';
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
  const { isAuthenticated, isLoading, user, loadAuth } = useAuthStore();
  const rootNavigationState = useRootNavigationState();
  const [hasNavigated, setHasNavigated] = useState(false);
  const [mounted, setMounted] = useState(false);
  
  // Track mount state
  useEffect(() => {
    setMounted(true);
    // Ensure auth is loaded
    loadAuth();
  }, []);
  
  useEffect(() => {
    // For web: don't wait for rootNavigationState
    // For native: wait for navigation to be ready
    const isNavReady = Platform.OS === 'web' || rootNavigationState?.key;
    
    if (!mounted) return;
    if (!isNavReady) return;
    if (hasNavigated) return;
    
    // Add a small delay on web to allow state to settle
    const delay = Platform.OS === 'web' ? 100 : 0;
    
    const doNavigation = () => {
      // Only navigate if loading is complete
      if (isLoading) return;
      
      setHasNavigated(true);
      
      if (!isAuthenticated) {
        router.replace('/auth/login');
      } else if (user?.needs_onboarding || user?.status === 'pending') {
        router.replace('/onboarding/index');
      } else if (!user?.onboarding_complete) {
        router.replace('/onboarding/index');
      } else {
        router.replace(getDefaultRoute(user?.role) as any);
      }
    };
    
    if (delay > 0) {
      const timer = setTimeout(doNavigation, delay);
      return () => clearTimeout(timer);
    } else {
      doNavigation();
    }
  }, [isAuthenticated, isLoading, user, rootNavigationState?.key, hasNavigated, mounted]);
  
  // Fallback: if still stuck after 3 seconds, force redirect to login
  useEffect(() => {
    if (!mounted) return;
    
    const fallbackTimer = setTimeout(() => {
      if (!hasNavigated) {
        console.log('Fallback redirect to login');
        setHasNavigated(true);
        router.replace('/auth/login');
      }
    }, 3000);
    
    return () => clearTimeout(fallbackTimer);
  }, [mounted, hasNavigated]);
  
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