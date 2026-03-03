import React, { useState, useEffect, useRef } from 'react';
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
    try {
      await login(email, password);
      
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
      
      // After successful login, check if we should offer biometric setup
      if (biometricStatus?.isAvailable && !biometricStatus?.isEnabled) {
        setPendingCredentials({ email, password });
        setShowBiometricPrompt(true);
      } else {
        // Navigate based on user role
        router.replace(defaultRoute as any);
      }
    } catch (error: any) {
      try { Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error); } catch {}
      setLoginError('Invalid email or password');
    } finally {
      setLoading(false);
    }
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
        
        router.replace(getDefaultRoute(loggedInUser?.role) as any);
      } else if (result.error) {
        // Only show error if user didn't cancel
        if (!result.error.includes('cancel') && !result.error.includes('Cancel')) {
          Alert.alert('Authentication Failed', result.error);
        }
      }
    } catch (error: any) {
      console.error('Biometric login error:', error);
      Alert.alert('Error', 'Biometric login failed. Please use your password.');
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
      Alert.alert(
        'Success',
        `${biometricStatus?.biometricLabel} login enabled! You can now login faster.`,
        [{ text: 'OK', onPress: () => router.replace(defaultRoute as any) }]
      );
    } else {
      // Still navigate even if enabling failed
      router.replace(defaultRoute as any);
    }
    
    setShowBiometricPrompt(false);
    setPendingCredentials(null);
  };
  
  const handleSkipBiometric = () => {
    setShowBiometricPrompt(false);
    setPendingCredentials(null);
    const loggedInUser = useAuthStore.getState().user;
    router.replace(getDefaultRoute(loggedInUser?.role) as any);
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
              />
              
              <View style={styles.passwordContainer}>
                <TextInput
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
                <TouchableOpacity
                  style={styles.refreshButton}
                  onPress={() => {
                    if (typeof window !== 'undefined') {
                      window.location.reload();
                    }
                  }}
                  data-testid="refresh-app-btn"
                >
                  <Ionicons name="refresh" size={18} color={colors.textSecondary} />
                  <Text style={styles.refreshButtonText}>Refresh App</Text>
                </TouchableOpacity>
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
    fontSize: 14,
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
    fontSize: 16,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
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
    fontSize: 16,
    color: colors.text,
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
    fontSize: 14,
  },
  forgotButton: {},
  forgotText: {
    color: '#007AFF',
    fontSize: 14,
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
    fontSize: 17,
    fontWeight: '600',
  },
  signupContainer: {
    marginTop: 24,
    alignItems: 'center',
  },
  signupText: {
    color: colors.textSecondary,
    fontSize: 15,
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
    fontSize: 14,
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
    fontSize: 14,
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
    fontSize: 15,
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
    fontSize: 16,
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
    fontSize: 16,
    fontWeight: '600',
  },
});
