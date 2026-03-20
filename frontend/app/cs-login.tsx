import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  Alert,
  Image,
  Animated,
} from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useAuthStore } from '../store/authStore';
import { WebSafeButton } from '../components/WebSafeButton';
import {
  checkBiometricSupport,
  authenticateWithBiometric,
  enableBiometricLogin,
  getBiometricIcon,
  BiometricStatus,
} from '../utils/biometrics';

const getDefaultRoute = (role?: string): string => {
  return '/(tabs)/home';
};

export default function CSLoginScreen() {
  const router = useRouter();
  const login = useAuthStore((state) => state.login);
  const fadeAnim = useRef(new Animated.Value(0)).current;

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loginError, setLoginError] = useState('');
  const [biometricLoading, setBiometricLoading] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [biometricStatus, setBiometricStatus] = useState<BiometricStatus | null>(null);

  useEffect(() => {
    Animated.timing(fadeAnim, {
      toValue: 1,
      duration: 400,
      useNativeDriver: true,
    }).start();

    // Swap manifest + PWA meta for Calendar Systems branding
    if (Platform.OS === 'web' && typeof document !== 'undefined') {
      // Swap manifest
      const manifestLink = document.querySelector('link[rel="manifest"]');
      if (manifestLink) manifestLink.setAttribute('href', '/cs-manifest.json');

      // Swap apple-touch-icon
      const appleIcon = document.querySelector('link[rel="apple-touch-icon"]');
      if (appleIcon) appleIcon.setAttribute('href', '/cs-apple-touch-icon.png');

      // Update PWA meta tags
      const setMeta = (name: string, content: string, attr = 'name') => {
        const el = document.querySelector(`meta[${attr}="${name}"]`);
        if (el) el.setAttribute('content', content);
      };
      setMeta('apple-mobile-web-app-title', 'Calendar Systems');
      setMeta('theme-color', '#102050');
      document.title = 'Calendar Systems';
    }

    checkBiometrics();
    loadRememberedEmail();
  }, []);

  const loadRememberedEmail = async () => {
    try {
      const savedEmail = await AsyncStorage.getItem('rememberedEmail');
      if (savedEmail) { setEmail(savedEmail); setRememberMe(true); }
    } catch {}
  };

  const checkBiometrics = async () => {
    const status = await checkBiometricSupport();
    setBiometricStatus(status);
    if (status.isAvailable && status.isEnabled) {
      setTimeout(() => handleBiometricLogin(), 500);
    }
  };

  const handleLogin = async () => {
    setLoginError('');
    if (!email || !password) {
      try { Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning); } catch {}
      setLoginError('Please fill in all fields');
      return;
    }
    try { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light); } catch {}
    setLoading(true);
    try {
      await login(email.trim().toLowerCase(), password);
      if (rememberMe && email) {
        await AsyncStorage.setItem('rememberedEmail', email);
      } else {
        await AsyncStorage.removeItem('rememberedEmail');
      }
      try { Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success); } catch {}
      const loggedInUser = useAuthStore.getState().user;
      if (loggedInUser?.needs_password_change) { router.replace('/auth/change-password'); return; }
      if (loggedInUser?.onboarding_complete === false && loggedInUser?.role !== 'super_admin') { router.replace('/auth/complete-profile' as any); return; }
      router.replace(getDefaultRoute(loggedInUser?.role) as any);
    } catch {
      try { Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error); } catch {}
      setLoginError('Invalid email or password');
    } finally {
      setLoading(false);
    }
  };

  const handleBiometricLogin = async () => {
    if (!biometricStatus?.isAvailable || !biometricStatus?.isEnabled) return;
    setBiometricLoading(true);
    try {
      const result = await authenticateWithBiometric(`Login with ${biometricStatus.biometricLabel}`);
      if (result.success && result.credentials) {
        await login(result.credentials.email, result.credentials.password);
        const loggedInUser = useAuthStore.getState().user;
        if (loggedInUser?.needs_password_change) { router.replace('/auth/change-password'); return; }
        if (loggedInUser?.onboarding_complete === false && loggedInUser?.role !== 'super_admin') { router.replace('/auth/complete-profile' as any); return; }
        router.replace(getDefaultRoute(loggedInUser?.role) as any);
      } else if (result.error && !result.error.includes('cancel') && !result.error.includes('Cancel')) {
        Alert.alert('Authentication Failed', result.error);
      }
    } catch {
      Alert.alert('Error', 'Biometric login failed. Please use your password.');
    } finally {
      setBiometricLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      <Animated.View style={[styles.inner, { opacity: fadeAnim }]}>
        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
          <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled" bounces={false}>
            {/* Logo Area */}
            <View style={styles.header}>
              <Image
                source={{ uri: '/calendar-systems/cs-logo.png' }}
                style={styles.csLogo}
                resizeMode="contain"
              />
              <View style={styles.poweredRow}>
                <Text style={styles.poweredText}>Powered by</Text>
                <Image
                  source={{ uri: '/marketing-logo.png' }}
                  style={styles.imosLogo}
                  resizeMode="contain"
                />
              </View>
            </View>

            {/* Form */}
            <View style={styles.form}>
              <TextInput
                style={styles.input}
                placeholder="Email"
                placeholderTextColor="rgba(255,255,255,0.35)"
                value={email}
                onChangeText={setEmail}
                keyboardType="email-address"
                autoCapitalize="none"
                autoCorrect={false}
                textContentType="emailAddress"
                returnKeyType="next"
                blurOnSubmit={false}
                data-testid="cs-login-email"
              />

              <View style={styles.passwordWrap}>
                <TextInput
                  style={styles.passwordInput}
                  placeholder="Password"
                  placeholderTextColor="rgba(255,255,255,0.35)"
                  value={password}
                  onChangeText={setPassword}
                  secureTextEntry={!showPassword}
                  autoCapitalize="none"
                  textContentType="password"
                  returnKeyType="done"
                  onSubmitEditing={handleLogin}
                  data-testid="cs-login-password"
                />
                <TouchableOpacity style={styles.eyeBtn} onPress={() => setShowPassword(!showPassword)}>
                  <Ionicons name={showPassword ? 'eye-off' : 'eye'} size={22} color="rgba(255,255,255,0.4)" />
                </TouchableOpacity>
              </View>

              <View style={styles.optionsRow}>
                <TouchableOpacity style={styles.rememberRow} onPress={() => setRememberMe(!rememberMe)} activeOpacity={0.7}>
                  <View style={[styles.checkbox, rememberMe && styles.checkboxOn]}>
                    {rememberMe && <Ionicons name="checkmark" size={14} color="#FFF" />}
                  </View>
                  <Text style={styles.rememberText}>Remember me</Text>
                </TouchableOpacity>
                <TouchableOpacity onPress={() => router.push('/auth/forgot-password')}>
                  <Text style={styles.forgotText}>Forgot Password?</Text>
                </TouchableOpacity>
              </View>

              <TouchableOpacity
                style={[styles.loginBtn, loading && { opacity: 0.6 }]}
                onPress={handleLogin}
                disabled={loading}
                activeOpacity={0.85}
                data-testid="cs-login-submit"
              >
                <Text style={styles.loginBtnText}>{loading ? 'Logging in...' : 'Log In'}</Text>
              </TouchableOpacity>

              {loginError ? (
                <View style={styles.errorBox}>
                  <Ionicons name="alert-circle" size={18} color="#FF6B6B" />
                  <Text style={styles.errorText}>{loginError}</Text>
                </View>
              ) : null}

              {biometricStatus?.isAvailable && biometricStatus?.isEnabled && (
                <TouchableOpacity
                  style={[styles.biometricBtn, biometricLoading && { opacity: 0.5 }]}
                  onPress={handleBiometricLogin}
                  disabled={biometricLoading}
                  data-testid="cs-biometric-login"
                >
                  <Ionicons name={getBiometricIcon(biometricStatus.biometricType) as any} size={24} color="#F08010" />
                  <Text style={styles.biometricText}>
                    {biometricLoading ? 'Authenticating...' : `Login with ${biometricStatus.biometricLabel}`}
                  </Text>
                </TouchableOpacity>
              )}

              {Platform.OS === 'web' && (
                <TouchableOpacity
                  style={styles.installBtn}
                  onPress={() => { if (typeof window !== 'undefined') window.location.href = '/install.html'; }}
                  data-testid="cs-install-app"
                >
                  <Ionicons name="download" size={18} color="rgba(255,255,255,0.4)" />
                  <Text style={styles.installText}>Add to Home Screen</Text>
                </TouchableOpacity>
              )}
            </View>
          </ScrollView>
        </KeyboardAvoidingView>
      </Animated.View>
    </View>
  );
}

const NAVY = '#102050';
const NAVY_LIGHT = '#1A3068';
const ORANGE = '#F08010';

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: NAVY,
  },
  inner: {
    flex: 1,
  },
  scroll: {
    flexGrow: 1,
    justifyContent: 'center',
    paddingHorizontal: 28,
    paddingVertical: 40,
    maxWidth: 420,
    width: '100%',
    alignSelf: 'center',
  },
  header: {
    alignItems: 'center',
    marginBottom: 40,
  },
  csLogo: {
    width: 280,
    height: 70,
    marginBottom: 16,
  },
  poweredRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  poweredText: {
    fontSize: 12,
    color: 'rgba(255,255,255,0.3)',
    fontWeight: '500',
  },
  imosLogo: {
    width: 80,
    height: 20,
    opacity: 0.4,
  },
  form: {
    gap: 16,
  },
  input: {
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderRadius: 12,
    padding: 16,
    fontSize: 16,
    color: '#FFFFFF',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.1)',
  },
  passwordWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.1)',
  },
  passwordInput: {
    flex: 1,
    padding: 16,
    fontSize: 16,
    color: '#FFFFFF',
  },
  eyeBtn: {
    padding: 16,
  },
  optionsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: -4,
  },
  rememberRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  checkbox: {
    width: 20,
    height: 20,
    borderRadius: 4,
    borderWidth: 2,
    borderColor: 'rgba(255,255,255,0.2)',
    backgroundColor: 'transparent',
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkboxOn: {
    backgroundColor: ORANGE,
    borderColor: ORANGE,
  },
  rememberText: {
    color: 'rgba(255,255,255,0.5)',
    fontSize: 14,
  },
  forgotText: {
    color: ORANGE,
    fontSize: 14,
    fontWeight: '500',
  },
  loginBtn: {
    backgroundColor: ORANGE,
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
    marginTop: 4,
    shadowColor: ORANGE,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 12,
  },
  loginBtnText: {
    color: '#FFFFFF',
    fontSize: 17,
    fontWeight: '700',
  },
  errorBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255,80,80,0.1)',
    borderRadius: 8,
    padding: 12,
    gap: 8,
  },
  errorText: {
    color: '#FF6B6B',
    fontSize: 14,
    fontWeight: '500',
    flex: 1,
  },
  biometricBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderRadius: 12,
    padding: 16,
    gap: 10,
    borderWidth: 1,
    borderColor: ORANGE,
  },
  biometricText: {
    color: ORANGE,
    fontSize: 17,
    fontWeight: '600',
  },
  installBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 16,
    paddingVertical: 12,
    gap: 8,
  },
  installText: {
    color: 'rgba(255,255,255,0.4)',
    fontSize: 14,
    fontWeight: '500',
  },
});
