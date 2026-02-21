import React, { useState, useEffect } from 'react';
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
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useAuthStore } from '../../store/authStore';
import {
  checkBiometricSupport,
  authenticateWithBiometric,
  enableBiometricLogin,
  getBiometricIcon,
  BiometricStatus,
} from '../../utils/biometrics';

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

export default function LoginScreen() {
  const router = useRouter();
  const login = useAuthStore((state) => state.login);
  const user = useAuthStore((state) => state.user);
  
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
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
      setLoginError('Please fill in all fields');
      return;
    }
    
    // Light haptic on login button press
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    
    setLoading(true);
    try {
      await login(email, password);
      
      // Save or clear remembered email based on checkbox
      await saveRememberedEmail(email);
      
      // Success haptic on successful login
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      
      // Get the user from store after login
      const loggedInUser = useAuthStore.getState().user;
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
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
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
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.keyboardView}
      >
        <ScrollView 
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
        >
          <View style={styles.header}>
            <Image 
              source={require('../../assets/images/imos-logo.png')} 
              style={styles.logo}
              resizeMode="contain"
            />
          </View>
          
          <View style={styles.form}>
            <TextInput
              style={styles.input}
              placeholder="Email"
              placeholderTextColor="#8E8E93"
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
                placeholderTextColor="#8E8E93"
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
                  color="#8E8E93"
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
                    <Ionicons name="checkmark" size={14} color="#FFF" />
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
            
            {Platform.OS === 'web' ? (
              <button
                type="submit"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  if (!loading) {
                    handleLogin();
                  }
                }}
                onTouchEnd={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  if (!loading) {
                    handleLogin();
                  }
                }}
                disabled={loading}
                style={{
                  backgroundColor: '#007AFF',
                  borderRadius: 12,
                  padding: 16,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginTop: 8,
                  cursor: loading ? 'not-allowed' : 'pointer',
                  opacity: loading ? 0.5 : 1,
                  border: 'none',
                  width: '100%',
                  WebkitAppearance: 'none',
                  WebkitTapHighlightColor: 'transparent',
                  touchAction: 'manipulation',
                  userSelect: 'none',
                  fontSize: 16,
                  fontWeight: '600',
                  color: '#FFFFFF',
                }}
              >
                {loading ? 'Logging in...' : 'Log In'}
              </button>
            ) : (
              <Pressable
                style={({ pressed }) => [
                  styles.button,
                  loading && styles.buttonDisabled,
                  pressed && styles.buttonPressed,
                ]}
                onPress={handleLogin}
                disabled={loading}
                data-testid="login-button"
              >
                <Text style={styles.buttonText}>
                  {loading ? 'Logging in...' : 'Log In'}
                </Text>
              </Pressable>
            )}
            
            {/* Error Message */}
            {loginError ? (
              <View style={styles.errorContainer}>
                <Ionicons name="alert-circle" size={18} color="#FF3B30" />
                <Text style={styles.errorText}>{loginError}</Text>
              </View>
            ) : null}
            
            {/* Biometric Login Button */}
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
              {Platform.OS === 'web' ? (
                <button
                  type="button"
                  onClick={() => router.push('/auth/signup')}
                  onTouchEnd={(e) => {
                    e.preventDefault();
                    router.push('/auth/signup');
                  }}
                  style={{
                    backgroundColor: '#1C1C1E',
                    border: '2px solid #007AFF',
                    borderRadius: 12,
                    padding: '16px 32px',
                    cursor: 'pointer',
                    marginTop: 12,
                    width: '100%',
                    WebkitAppearance: 'none',
                    WebkitTapHighlightColor: 'transparent',
                    touchAction: 'manipulation',
                    userSelect: 'none',
                  }}
                >
                  <Text style={styles.signupButtonTextLarge}>Sign Up</Text>
                </button>
              ) : (
                <TouchableOpacity
                  style={styles.signupButtonLarge}
                  onPress={() => router.push('/auth/signup')}
                >
                  <Text style={styles.signupButtonTextLarge}>Sign Up</Text>
                </TouchableOpacity>
              )}
            </View>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
      
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
                color="#007AFF"
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
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
  },
  keyboardView: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    justifyContent: 'center',
    padding: 24,
  },
  header: {
    marginBottom: 48,
    alignItems: 'center',
  },
  logo: {
    width: 180,
    height: 80,
    marginBottom: 8,
  },
  title: {
    fontSize: 48,
    fontWeight: 'bold',
    color: '#FFF',
    marginBottom: 8,
  },
  tagline: {
    fontSize: 16,
    color: '#8E8E93',
    textAlign: 'center',
    fontStyle: 'italic',
  },
  subtitle: {
    fontSize: 18,
    color: '#8E8E93',
  },
  form: {
    gap: 16,
  },
  input: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    fontSize: 16,
    color: '#FFF',
    borderWidth: 1,
    borderColor: '#2C2C2E',
  },
  passwordContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#2C2C2E',
  },
  passwordInput: {
    flex: 1,
    padding: 16,
    fontSize: 16,
    color: '#FFF',
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
    borderColor: '#48484A',
    backgroundColor: 'transparent',
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkboxChecked: {
    backgroundColor: '#007AFF',
    borderColor: '#007AFF',
  },
  rememberMeText: {
    color: '#8E8E93',
    fontSize: 14,
  },
  forgotButton: {
  },
  forgotText: {
    color: '#007AFF',
    fontSize: 14,
  },
  button: {
    backgroundColor: '#007AFF',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
    marginTop: 8,
    cursor: 'pointer',
  },
  buttonPressed: {
    opacity: 0.8,
    transform: [{ scale: 0.98 }],
  },
  buttonDisabled: {
    opacity: 0.5,
  },
  buttonText: {
    color: '#FFF',
    fontSize: 17,
    fontWeight: '600',
  },
  biometricButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#1C1C1E',
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
  linkButton: {
    marginTop: 16,
    alignItems: 'center',
  },
  linkText: {
    color: '#8E8E93',
    fontSize: 15,
  },
  linkTextBold: {
    color: '#007AFF',
    fontWeight: '600',
  },
  signupContainer: {
    marginTop: 24,
    alignItems: 'center',
  },
  signupText: {
    color: '#8E8E93',
    fontSize: 15,
    marginBottom: 8,
  },
  signupButton: {
    padding: 8,
  },
  signupButtonText: {
    color: '#007AFF',
    fontSize: 16,
    fontWeight: '600',
  },
  signupButtonLarge: {
    backgroundColor: '#1C1C1E',
    borderWidth: 2,
    borderColor: '#007AFF',
    borderRadius: 12,
    paddingVertical: 16,
    paddingHorizontal: 32,
    marginTop: 12,
    width: '100%',
    alignItems: 'center',
  },
  signupButtonTextLarge: {
    color: '#007AFF',
    fontSize: 18,
    fontWeight: '700',
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
  // Modal styles
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.8)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  modalContent: {
    backgroundColor: '#1C1C1E',
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
    color: '#FFF',
    textAlign: 'center',
    marginBottom: 12,
  },
  modalDescription: {
    fontSize: 15,
    color: '#8E8E93',
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
    backgroundColor: '#2C2C2E',
    borderRadius: 12,
    padding: 14,
    alignItems: 'center',
  },
  modalButtonSecondaryText: {
    color: '#FFF',
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
    color: '#FFF',
    fontSize: 16,
    fontWeight: '600',
  },
});
