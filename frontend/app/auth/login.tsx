import React, { useState, useEffect, useRef } from 'react';
import { showAlert } from '../../services/alert';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  Pressable,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  Alert,
  Modal,
  Image,
  Animated,
} from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useAuthStore } from '../../store/authStore';
import { WebSafeButton } from '../../components/WebSafeButton';
import { useThemeStore } from '../../store/themeStore';
import {
  checkBiometricSupport,
  authenticateWithBiometric,
  enableBiometricLogin,
  getBiometricIcon,
  BiometricStatus,
} from '../../utils/biometrics';

// Helper to get the right landing page based on user role
const getDefaultRoute = (role?: string): string => {
  return '/(tabs)/home';  // Everyone starts at Home  - the daily command center
};

/** Gate: first-time / incomplete profiles land on My Presence to set up their profile.
 *  Once they have photo + bio (or onboarding_complete === true), go to home. */
const getProfileGatedRoute = (user: any): string => {
  const hasPhoto = !!(user?.photo_url || user?.photo_path);
  const hasBio   = !!(user?.persona?.bio || user?.bio);
  const complete  = user?.onboarding_complete === true || (hasPhoto && hasBio);
  return complete ? getDefaultRoute(user?.role) : '/my-account';
};

export default function LoginScreen() {
  const { colors: themeColors, loadTheme } = useThemeStore();
  // Force light theme for public login page
  const colors = {
    ...themeColors,
    bg: '#FFFFFF',
    card: '#FFFFFF',
    surface: '#F0F0F5',
    text: '#111111',
    textSecondary: '#6E6E73',
    textTertiary: '#AEAEB2',
    border: 'rgba(0,0,0,0.1)',
  };
  const [themeReady, setThemeReady] = useState(false);
  const styles = getStyles(colors);
  const router = useRouter();
  const login = useAuthStore((state) => state.login);
  const user = useAuthStore((state) => state.user);

  // Fade-in animation to prevent flash
  const fadeAnim = useRef(new Animated.Value(0)).current;
  
  useEffect(() => {
    loadTheme().finally(() => {
      setThemeReady(true);
      Animated.timing(fadeAnim, {
        toValue: 1,
        duration: 300,
        useNativeDriver: true,
      }).start();
    });

    // Login page is ALWAYS light — force data-theme="light" so autofill CSS
    // uses the light-mode rules (white bg, dark text) regardless of app theme.
    // Restore the real theme on unmount so the rest of the app still works.
    if (Platform.OS === 'web' && typeof document !== 'undefined') {
      const prev = document.documentElement.getAttribute('data-theme') || 'dark';
      document.documentElement.setAttribute('data-theme', 'light');
      return () => {
        document.documentElement.setAttribute('data-theme', prev);
      };
    }
  }, []);

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loginError, setLoginError] = useState('');
  const [biometricLoading, setBiometricLoading] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  
  // Biometric state
  const [biometricStatus, setBiometricStatus] = useState<BiometricStatus | null>(null);
  const [showBiometricPrompt, setShowBiometricPrompt] = useState(false);
  const [pendingCredentials, setPendingCredentials] = useState<{email: string; password: string} | null>(null);
  
  useEffect(() => {
    // Check biometric support on mount
    checkBiometrics();
    // Load remembered email
    loadRememberedEmail();
    
    // Auto-refresh if cached code is stale (fixes Cloudflare caching dead JS bundles)
    if (Platform.OS === 'web' && typeof window !== 'undefined') {
      fetch('/api/build-version')
        .then(r => r.json())
        .then(data => {
          const stored = localStorage.getItem('imos_build_version');
          if (stored && stored !== data.version) {
            localStorage.setItem('imos_build_version', data.version);
            window.location.reload();
          } else {
            localStorage.setItem('imos_build_version', data.version);
          }
        })
        .catch(() => {});
      
      const params = new URLSearchParams(window.location.search);
      const urlEmail = params.get('email');
      const urlPassword = params.get('password');
      if (urlEmail) setEmail(decodeURIComponent(urlEmail));
      if (urlPassword) setPassword(decodeURIComponent(urlPassword));
      // Clean URL params after reading
      if (urlEmail || urlPassword) {
        window.history.replaceState({}, '', window.location.pathname);
      }
    }
  }, []);
  
  const loadRememberedEmail = async () => {
    try {
      const savedEmail = await AsyncStorage.getItem('rememberedEmail');
      if (savedEmail) {
        setEmail(savedEmail);
        setRememberMe(true);
      }
    } catch (error) {
      console.log('Error loading remembered email:', error);
    }
  };
  
  const saveRememberedEmail = async (emailToSave: string) => {
    try {
      if (rememberMe && emailToSave) {
        await AsyncStorage.setItem('rememberedEmail', emailToSave);
      } else {
        await AsyncStorage.removeItem('rememberedEmail');
      }
    } catch (error) {
      console.log('Error saving remembered email:', error);
    }
  };
  
  const checkBiometrics = async () => {
    const status = await checkBiometricSupport();
    setBiometricStatus(status);
    
    // If biometrics are enabled, automatically try to authenticate
    if (status.isAvailable && status.isEnabled) {
      // Small delay for better UX
      setTimeout(() => {
        handleBiometricLogin();
      }, 500);
    }
  };
  
  const handleForgotPassword = () => {
    router.push('/auth/forgot-password');
  };
  
  const handleLogin = async () => {
    setLoginError('');
    
    if (!email || !password) {
      try { Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning); } catch {}
      setLoginError('Please fill in all fields');
      return;
    }
    
    // Light haptic on login button press
    try { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light); } catch {}
    
    setLoading(true);
    let retries = 0;
    const maxRetries = 1; // Auto-retry once for PWA network hiccups
    
    while (retries <= maxRetries) {
      try {
        await login(email.trim().toLowerCase(), password);
        
        // Save or clear remembered email based on checkbox
        await saveRememberedEmail(email);
        
        // Success haptic on successful login
        try { Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success); } catch {}
        
        // Get the user from store after login
        const loggedInUser = useAuthStore.getState().user;
        
        // Check if user needs to change password (first-time login with temp password)
        if (loggedInUser?.needs_password_change) {
          router.replace('/auth/change-password');
          return;
        }
        
        const defaultRoute = getDefaultRoute(loggedInUser?.role);
        
        // First-login / incomplete profile gate:
        // If the user hasn't completed their profile (no photo + no bio),
        // send them to Hub to set up. Once complete, future logins go to home.
        const hasPhoto = !!(loggedInUser?.photo_url || (loggedInUser as any)?.photo_path);
        const hasBio = !!((loggedInUser as any)?.persona?.bio || (loggedInUser as any)?.bio);
        const profileComplete = loggedInUser?.onboarding_complete === true || (hasPhoto && hasBio);
        const landingRoute = getProfileGatedRoute(loggedInUser);
        
        // After successful login, check if we should offer biometric setup
        if (biometricStatus?.isAvailable && !biometricStatus?.isEnabled) {
          setPendingCredentials({ email, password });
          setShowBiometricPrompt(true);
        } else {
          router.replace(landingRoute as any);
        }
        return; // Success — exit the retry loop
      } catch (error: any) {
        // Always log the raw error so we can diagnose unexpected post-login crashes
        console.error('[Login] catch error:', {
          message: error?.message,
          name: error?.name,
          status: error?.response?.status,
          data: error?.response?.data,
          code: error?.code,
          stack: error?.stack?.slice?.(0, 500),
        });
        // Report to backend error log for visibility in admin dashboard
        try {
          import('../services/errorReporter').then(({ reportError }) => {
            reportError({
              error_message: `Login error on mobile: ${error?.name || 'unknown'} — ${error?.message || 'no message'} | code: ${error?.code || 'none'} | status: ${error?.response?.status || 'none'}`,
              error_type: 'js_error',
              extra: { code: error?.code, name: error?.name, status: error?.response?.status },
            });
          }).catch(() => {});
        } catch {}

        const status = error?.response?.status;
        // Only retry on network/connection errors, not on 401 (wrong password)
        if (status === 401 || retries >= maxRetries) {
          try { Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error); } catch {}
          if (status === 401) {
            setLoginError('Invalid email or password');
          } else if (status === 402) {
            setLoginError(error?.response?.data?.detail || 'Account access issue. Please contact support.');
          } else if (status === 403) {
            setLoginError('Your account is not active. Please contact your administrator.');
          } else if (status === 429) {
            // Cloudflare or server rate-limiting — common on iOS/mobile
            setLoginError('Too many login attempts. Please wait a moment and try again.');
          } else if (status === 500 || status === 501) {
            // Server-side error — could be temporary DB connection issue
            setLoginError('Server error. This usually clears in 1-2 minutes — please try again shortly.');
          } else if (status === 502 || status === 503 || status === 504) {
            setLoginError('Server is temporarily restarting. Please try again in 30 seconds.');
          } else if (error?.message?.includes('Network') || error?.message?.includes('network') || error?.message?.includes('timeout') || error?.code === 'ERR_NETWORK' || error?.code === 'ECONNABORTED') {
            setLoginError('Connection issue. Please check your internet and try again.');
          } else if (error?.name === 'SecurityError' || error?.message?.includes('SecurityError') || error?.message?.includes('insecure') || error?.message?.includes('storage')) {
            setLoginError('Storage access blocked. Please check your browser privacy settings or try a different browser.');
          } else if (!status) {
            setLoginError(`Something went wrong (${error?.name || error?.code || 'unknown'}). Please try again or contact support.`);
          } else {
            setLoginError(`Something went wrong (${status}). Please try again.`);
          }
          break;
        }
        // Wait briefly then retry
        await new Promise(resolve => setTimeout(resolve, 1500));
        retries++;
      }
    }
    setLoading(false);
  };
  
  const handleBiometricLogin = async () => {
    if (!biometricStatus?.isAvailable || !biometricStatus?.isEnabled) {
      return;
    }
    
    setBiometricLoading(true);
    try {
      const result = await authenticateWithBiometric(
        `Login with ${biometricStatus.biometricLabel}`
      );
      
      if (result.success && result.credentials) {
        // Login with stored credentials
        await login(result.credentials.email, result.credentials.password);
        const loggedInUser = useAuthStore.getState().user;
        
        // Check if user needs to change password
        if (loggedInUser?.needs_password_change) {
          router.replace('/auth/change-password');
          return;
        }
        
        router.replace(getProfileGatedRoute(loggedInUser) as any);
        // Only show error if user didn't cancel
        if (!result.error.includes('cancel') && !result.error.includes('Cancel')) {
          showAlert('Authentication Failed', result.error);
        }
      }
    } catch (error: any) {
      console.error('Biometric login error:', error);
      showAlert('Error', 'Biometric login failed. Please use your password.');
    } finally {
      setBiometricLoading(false);
    }
  };
  
  const handleEnableBiometric = async () => {
    if (!pendingCredentials) return;
    
    const success = await enableBiometricLogin(pendingCredentials);
    const loggedInUser = useAuthStore.getState().user;
    const defaultRoute = getDefaultRoute(loggedInUser?.role);
    
    if (success) {
      showAlert(
        'Success',
        `${biometricStatus?.biometricLabel} login enabled! You can now login faster.`,
        [{ text: 'OK', onPress: () => router.replace(getProfileGatedRoute(loggedInUser) as any) }]
      );
    } else {
      router.replace(getProfileGatedRoute(loggedInUser) as any);
    }
    
    setShowBiometricPrompt(false);
    setPendingCredentials(null);
  };
  
  const handleSkipBiometric = () => {
    setShowBiometricPrompt(false);
    setPendingCredentials(null);
    const loggedInUser = useAuthStore.getState().user;
    router.replace(getProfileGatedRoute(loggedInUser) as any);
  };
  
  return (
    <View style={styles.container}>
      <Animated.View style={[styles.innerContainer, { opacity: fadeAnim }]}>
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          style={styles.keyboardView}
        >
          <ScrollView 
            contentContainerStyle={styles.scrollContent}
            keyboardShouldPersistTaps="handled"
            bounces={false}
          >
            <View style={styles.header}>
              <View style={styles.logoContainer}>
                <Image 
                  source={{ uri: '/new-logo-512-transparent.png' }}
                  style={styles.logoImage}
                  resizeMode="contain"
                />
              </View>
              <Text style={styles.tagline}>The Social Relationship OS</Text>
            </View>
            
            <View style={styles.form}>
              <TextInput
                ref={(ref) => {
                  // iOS PWA standalone mode: first tap doesn't trigger keyboard
                  // Force the input to be interactive with web attributes
                  if (Platform.OS === 'web' && ref) {
                    const el = ref as unknown as HTMLInputElement;
                    if (el.setAttribute) {
                      el.setAttribute('inputmode', 'email');
                      el.setAttribute('autocomplete', 'email');
                      el.setAttribute('name', 'email');
                      el.setAttribute('id', 'email-input');
                    }
                  }
                }}
                style={styles.input}
                placeholder="Email"
                placeholderTextColor={colors.textSecondary}
                value={email}
                onChangeText={setEmail}
                keyboardType="email-address"
                autoCapitalize="none"
                autoCorrect={false}
                textContentType="emailAddress"
                returnKeyType="next"
                blurOnSubmit={false}
                data-testid="login-email-input"
              />
              
              <View style={styles.passwordContainer}>
                <TextInput
                  ref={(ref) => {
                    if (Platform.OS === 'web' && ref) {
                      const el = ref as unknown as HTMLInputElement;
                      if (el.setAttribute) {
                        el.setAttribute('inputmode', 'text');
                        el.setAttribute('autocomplete', 'current-password');
                        el.setAttribute('name', 'password');
                        el.setAttribute('id', 'password-input');
                      }
                    }
                  }}
                  style={styles.passwordInput}
                  placeholder="Password"
                  placeholderTextColor={colors.textSecondary}
                  value={password}
                  onChangeText={setPassword}
                  secureTextEntry={!showPassword}
                  autoCapitalize="none"
                  textContentType="password"
                  returnKeyType="done"
                  onSubmitEditing={handleLogin}
                  data-testid="login-password-input"
                />
                <TouchableOpacity
                  style={styles.eyeButton}
                  onPress={() => setShowPassword(!showPassword)}
                >
                  <Ionicons
                    name={showPassword ? 'eye-off' : 'eye'}
                    size={22}
                    color={colors.textSecondary}
                  />
                </TouchableOpacity>
              </View>
              
              <View style={styles.optionsRow}>
                <TouchableOpacity
                  style={styles.rememberMeContainer}
                  onPress={() => setRememberMe(!rememberMe)}
                  activeOpacity={0.7}
                >
                  <View style={[styles.checkbox, rememberMe && styles.checkboxChecked]}>
                    {rememberMe && (
                      <Ionicons name="checkmark" size={14} color={colors.text} />
                    )}
                  </View>
                  <Text style={styles.rememberMeText}>Remember me</Text>
                </TouchableOpacity>
                
                <TouchableOpacity
                  style={styles.forgotButton}
                  onPress={handleForgotPassword}
                >
                  <Text style={styles.forgotText}>Forgot Password?</Text>
                </TouchableOpacity>
              </View>
              
              <WebSafeButton
                onPress={handleLogin}
                title={loading ? 'Logging in...' : 'Log In'}
                loading={loading}
                disabled={loading}
                variant="primary"
                size="large"
                fullWidth
                testID="login-button"
                style={{ marginTop: 8 }}
              />
              
              {loginError ? (
                <View style={styles.errorContainer}>
                  <Ionicons name="alert-circle" size={18} color="#FF3B30" />
                  <Text style={styles.errorText}>{loginError}</Text>
                </View>
              ) : null}
              
              {biometricStatus?.isAvailable && biometricStatus?.isEnabled && (
                <TouchableOpacity
                  style={[styles.biometricButton, biometricLoading && styles.buttonDisabled]}
                  onPress={handleBiometricLogin}
                  disabled={biometricLoading}
                  data-testid="biometric-login-button"
                >
                  <Ionicons
                    name={getBiometricIcon(biometricStatus.biometricType) as any}
                    size={24}
                    color="#007AFF"
                  />
                  <Text style={styles.biometricButtonText}>
                    {biometricLoading ? 'Authenticating...' : `Login with ${biometricStatus.biometricLabel}`}
                  </Text>
                </TouchableOpacity>
              )}
              
              <View style={styles.signupContainer}>
                <Text style={styles.signupText}>Don't have an account?</Text>
                <WebSafeButton
                  onPress={() => router.push('/auth/signup')}
                  title="Sign Up"
                  variant="outline"
                  size="large"
                  fullWidth
                  testID="signup-button"
                  style={{ marginTop: 12 }}
                />
              </View>
              
              {Platform.OS === 'web' && (
                <View style={{ alignItems: 'center', gap: 8 }}>
                  <TouchableOpacity
                    style={styles.refreshButton}
                    onPress={() => {
                      if (typeof window !== 'undefined') {
                        window.location.href = '/install.html';
                      }
                    }}
                    data-testid="install-app-btn"
                  >
                    <Ionicons name="download" size={18} color="#007AFF" />
                    <Text style={[styles.refreshButtonText, { color: '#007AFF' }]}>Install App on Your Phone</Text>
                  </TouchableOpacity>
                </View>
              )}
            </View>
          </ScrollView>
        </KeyboardAvoidingView>
      </Animated.View>
      
      {/* Biometric Enable Prompt Modal */}
      <Modal
        visible={showBiometricPrompt}
        animationType="fade"
        transparent={true}
        onRequestClose={handleSkipBiometric}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalIcon}>
              <Ionicons
                name={getBiometricIcon(biometricStatus?.biometricType || 'none') as any}
                size={48}
                color="#34C759"
              />
            </View>
            
            <Text style={styles.modalTitle}>
              Enable {biometricStatus?.biometricLabel}?
            </Text>
            
            <Text style={styles.modalDescription}>
              Login faster next time using {biometricStatus?.biometricLabel}. 
              Your credentials will be stored securely on this device.
            </Text>
            
            <View style={styles.modalButtons}>
              <TouchableOpacity
                style={styles.modalButtonSecondary}
                onPress={handleSkipBiometric}
              >
                <Text style={styles.modalButtonSecondaryText}>Not Now</Text>
              </TouchableOpacity>
              
              <TouchableOpacity
                style={styles.modalButtonPrimary}
                onPress={handleEnableBiometric}
              >
                <Text style={styles.modalButtonPrimaryText}>Enable</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  innerContainer: {
    flex: 1,
  },
  keyboardView: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    justifyContent: 'center',
    paddingHorizontal: 24,
    paddingVertical: 40,
    maxWidth: 440,
    width: '100%',
    alignSelf: 'center',
  },
  header: {
    marginBottom: 32,
    alignItems: 'center',
    width: '100%',
    minHeight: 220,
    justifyContent: 'center',
  },
  logoContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    width: 180,
    height: 180,
    aspectRatio: 1,
  },
  logoImage: {
    width: 180,
    height: 180,
    aspectRatio: 1,
  },
  tagline: {
    fontSize: 16,
    color: colors.textSecondary,
    letterSpacing: 2,
    textTransform: 'uppercase',
    textAlign: 'center',
    marginTop: 8,
  },
  form: {
    gap: 16,
  },
  input: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    fontSize: 18,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
    // iOS PWA: ensure keyboard triggers on first tap
    ...(Platform.OS === 'web' ? { 
      cursor: 'text' as any,
      userSelect: 'text' as any,
      WebkitUserSelect: 'text' as any,
    } : {}),
  },
  passwordContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
  },
  passwordInput: {
    flex: 1,
    padding: 16,
    fontSize: 18,
    color: colors.text,
    ...(Platform.OS === 'web' ? { 
      cursor: 'text' as any,
      userSelect: 'text' as any,
      WebkitUserSelect: 'text' as any,
    } : {}),
  },
  eyeButton: {
    padding: 16,
  },
  optionsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: -8,
  },
  rememberMeContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  checkbox: {
    width: 20,
    height: 20,
    borderRadius: 4,
    borderWidth: 2,
    borderColor: colors.surface,
    backgroundColor: 'transparent',
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkboxChecked: {
    backgroundColor: '#007AFF',
    borderColor: '#007AFF',
  },
  rememberMeText: {
    color: colors.textSecondary,
    fontSize: 16,
  },
  forgotButton: {},
  forgotText: {
    color: '#007AFF',
    fontSize: 16,
  },
  buttonDisabled: {
    opacity: 0.5,
  },
  biometricButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    gap: 10,
    borderWidth: 1,
    borderColor: '#007AFF',
  },
  biometricButtonText: {
    color: '#007AFF',
    fontSize: 18,
    fontWeight: '600',
  },
  signupContainer: {
    marginTop: 24,
    alignItems: 'center',
  },
  signupText: {
    color: colors.textSecondary,
    fontSize: 17,
    marginBottom: 8,
  },
  refreshButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 24,
    paddingVertical: 12,
    gap: 8,
  },
  refreshButtonText: {
    color: colors.textSecondary,
    fontSize: 16,
    fontWeight: '500',
  },
  errorContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FF3B3010',
    borderRadius: 8,
    padding: 12,
    marginTop: 12,
    gap: 8,
  },
  errorText: {
    color: '#FF3B30',
    fontSize: 16,
    fontWeight: '500',
    flex: 1,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.8)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  modalContent: {
    backgroundColor: colors.card,
    borderRadius: 20,
    padding: 24,
    width: '100%',
    maxWidth: 340,
    alignItems: 'center',
  },
  modalIcon: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: '#007AFF20',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 20,
  },
  modalTitle: {
    fontSize: 22,
    fontWeight: 'bold',
    color: colors.text,
    textAlign: 'center',
    marginBottom: 12,
  },
  modalDescription: {
    fontSize: 17,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: 24,
  },
  modalButtons: {
    flexDirection: 'row',
    gap: 12,
    width: '100%',
  },
  modalButtonSecondary: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 14,
    alignItems: 'center',
  },
  modalButtonSecondaryText: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '600',
  },
  modalButtonPrimary: {
    flex: 1,
    backgroundColor: '#007AFF',
    borderRadius: 12,
    padding: 14,
    alignItems: 'center',
  },
  modalButtonPrimaryText: {
    color: '#FFFFFF',
    fontSize: 18,
    fontWeight: '600',
  },
});
