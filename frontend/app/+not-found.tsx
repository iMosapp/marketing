import { useEffect } from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import { useAuthStore } from '../store/authStore';

/**
 * Catches any unmatched route — including imos:/// (empty deep link after failed login).
 * Redirects to login if not authenticated, home if authenticated.
 */
export default function NotFoundScreen() {
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();

  useEffect(() => {
    // Redirect automatically after a short delay
    const t = setTimeout(() => {
      if (isAuthenticated) {
        router.replace('/(tabs)/home' as any);
      } else {
        router.replace('/auth/login' as any);
      }
    }, 100);
    return () => clearTimeout(t);
  }, [isAuthenticated]);

  // Fallback UI in case redirect takes a moment
  return (
    <View style={styles.container}>
      <Text style={styles.text}>Redirecting...</Text>
      <TouchableOpacity
        onPress={() => router.replace(isAuthenticated ? '/(tabs)/home' as any : '/auth/login' as any)}
        style={styles.button}
      >
        <Text style={styles.buttonText}>Go to App</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000', alignItems: 'center', justifyContent: 'center', gap: 16 },
  text: { color: '#888', fontSize: 16 },
  button: { backgroundColor: '#007AFF', borderRadius: 12, paddingHorizontal: 24, paddingVertical: 12 },
  buttonText: { color: '#fff', fontWeight: '700', fontSize: 16 },
});
