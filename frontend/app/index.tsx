import { useEffect, useState } from 'react';
import { View, ActivityIndicator, StyleSheet, Platform } from 'react-native';
import { useRouter, useRootNavigationState, Redirect } from 'expo-router';
import { useAuthStore } from '../store/authStore';

// Helper to get the right landing page based on user role
const getDefaultRoute = (role?: string): string => {
  switch (role) {
    case 'super_admin':
    case 'org_admin':
    case 'store_manager':
      return '/(tabs)/more';
    default:
      return '/(tabs)/inbox';
  }
};

export default function Index() {
  const router = useRouter();
  const { isAuthenticated, isLoading, user, loadAuth } = useAuthStore();
  const [mounted, setMounted] = useState(false);
  const [redirectPath, setRedirectPath] = useState<string | null>(null);
  
  // Track mount state and load auth
  useEffect(() => {
    setMounted(true);
    loadAuth();
  }, []);
  
  // Determine redirect path once loading is complete
  useEffect(() => {
    if (!mounted || isLoading) return;
    
    if (!isAuthenticated) {
      setRedirectPath('/auth/login');
    } else if (user?.needs_onboarding || user?.status === 'pending' || !user?.onboarding_complete) {
      setRedirectPath('/onboarding/index');
    } else {
      setRedirectPath(getDefaultRoute(user?.role));
    }
  }, [mounted, isLoading, isAuthenticated, user]);
  
  // Fallback timeout — extended to 30s to allow cookie-based session restore
  useEffect(() => {
    if (!mounted || redirectPath) return;
    
    const timer = setTimeout(() => {
      if (!redirectPath && isLoading) {
        loadAuth().finally(() => {
          const { isAuthenticated: authNow } = useAuthStore.getState();
          if (!authNow) {
            setRedirectPath('/auth/login');
          }
        });
      }
    }, 30000);
    
    return () => clearTimeout(timer);
  }, [mounted, redirectPath]);
  
  // Use Redirect component for cleaner navigation
  if (redirectPath) {
    return <Redirect href={redirectPath as any} />;
  }
  
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