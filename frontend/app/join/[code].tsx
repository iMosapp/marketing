import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  ActivityIndicator,
  KeyboardAvoidingView,
  ScrollView,
  Platform,
  Image,
  Linking,
  Pressable,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';

export default function JoinTeamScreen() {
  const { code } = useLocalSearchParams<{ code: string }>();
  const router = useRouter();
  const login = useAuthStore((state) => state.login);
  
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  
  const [inviteData, setInviteData] = useState<any>(null);
  const [formData, setFormData] = useState({
    name: '',
    phone: '',
    email: '',
    password: '',
    confirmPassword: '',
  });
  const [showPassword, setShowPassword] = useState(false);
  const [trainingLink, setTrainingLink] = useState('');
  
  useEffect(() => {
    if (code) {
      validateInvite();
    }
  }, [code]);
  
  const validateInvite = async () => {
    try {
      setLoading(true);
      setError('');
      // Use the new endpoint that returns email/name pre-fill for email invites
      const res = await api.get(`/team-invite/validate-email/${code}`);
      setInviteData(res.data);
      
      // Pre-fill form if data available from email invite
      if (res.data.recipient_email) {
        setFormData(prev => ({ ...prev, email: res.data.recipient_email }));
      }
      if (res.data.recipient_name) {
        setFormData(prev => ({ ...prev, name: res.data.recipient_name }));
      }
    } catch (err: any) {
      console.error('Invalid invite:', err);
      setError(err.response?.data?.detail || 'This invite link is invalid or has expired.');
    } finally {
      setLoading(false);
    }
  };
  
  const handleSubmit = async () => {
    // Validation
    if (!formData.name.trim()) {
      setError('Please enter your name');
      return;
    }
    if (!formData.email.trim() || !formData.email.includes('@')) {
      setError('Please enter a valid email address');
      return;
    }
    if (!formData.password) {
      setError('Please create a password');
      return;
    }
    if (formData.password.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }
    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }
    
    try {
      setSubmitting(true);
      setError('');
      
      // Use the new accept endpoint with password
      const res = await api.post('/team-invite/accept', {
        invite_code: code,
        name: formData.name.trim(),
        email: formData.email.trim().toLowerCase(),
        password: formData.password,
        phone: formData.phone.trim() || undefined,
      });
      
      if (res.data.success) {
        // Auto-login with the new credentials
        try {
          await login({ 
            email: formData.email.trim().toLowerCase(), 
            password: formData.password 
          });
          // Navigate to main app after successful login
          router.replace('/');
        } catch (loginErr) {
          // If auto-login fails, still show success but redirect to login
          setSuccess(true);
        }
      }
    } catch (err: any) {
      console.error('Join failed:', err);
      setError(err.response?.data?.detail || 'Failed to create your account. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };
  
  const openAppStore = () => {
    const url = inviteData?.app_links?.app_store_url;
    if (url) {
      Linking.openURL(url);
    }
  };
  
  const openPlayStore = () => {
    const url = inviteData?.app_links?.google_play_url;
    if (url) {
      Linking.openURL(url);
    }
  };
  
  const openTraining = () => {
    if (trainingLink) {
      router.push('/onboarding');
    }
  };
  
  // Loading State
  if (loading) {
    return (
      <View style={styles.container}>
        <LinearGradient colors={['#1A1A2E', '#16213E']} style={StyleSheet.absoluteFill} />
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#C9A962" />
          <Text style={styles.loadingText}>Validating your invite...</Text>
        </View>
      </View>
    );
  }
  
  // Error State (Invalid Invite)
  if (error && !inviteData) {
    return (
      <View style={styles.container}>
        <LinearGradient colors={['#1A1A2E', '#16213E']} style={StyleSheet.absoluteFill} />
        <SafeAreaView style={styles.safeArea}>
          <View style={styles.errorContainer}>
            <View style={styles.errorIconContainer}>
              <Ionicons name="close-circle" size={64} color="#FF3B30" />
            </View>
            <Text style={styles.errorTitle}>Oops!</Text>
            <Text style={styles.errorMessage}>{error}</Text>
            <Text style={styles.errorHint}>
              Please contact the person who shared this link with you for a new invite.
            </Text>
          </View>
        </SafeAreaView>
      </View>
    );
  }
  
  // Success State
  if (success) {
    const hasAppLinks = inviteData?.app_links?.app_store_url || inviteData?.app_links?.google_play_url;
    
    return (
      <View style={styles.container}>
        <LinearGradient colors={['#0F2E1A', '#1A1A1A']} style={StyleSheet.absoluteFill} />
        <SafeAreaView style={styles.safeArea}>
          <ScrollView contentContainerStyle={styles.successContent}>
            <View style={styles.successIconContainer}>
              <Ionicons name="checkmark-circle" size={80} color="#34C759" />
            </View>
            
            <Text style={styles.successTitle}>Welcome to the Team!</Text>
            <Text style={styles.successSubtitle}>{inviteData?.store_name}</Text>
            
            <Text style={styles.successMessage}>
              Your account has been created! Here's what to do next:
            </Text>
            
            {/* Step 1: Download App */}
            {hasAppLinks && (
              <View style={styles.stepCard}>
                <View style={styles.stepNumber}>
                  <Text style={styles.stepNumberText}>1</Text>
                </View>
                <View style={styles.stepContent}>
                  <Text style={styles.stepTitle}>Download the App</Text>
                  <Text style={styles.stepDescription}>
                    Get the mobile app for the best experience
                  </Text>
                  <View style={styles.appButtonsRow}>
                    {inviteData?.app_links?.app_store_url && (
                      <TouchableOpacity style={styles.appButton} onPress={openAppStore}>
                        <Ionicons name="logo-apple" size={20} color="#FFF" />
                        <Text style={styles.appButtonText}>App Store</Text>
                      </TouchableOpacity>
                    )}
                    {inviteData?.app_links?.google_play_url && (
                      <TouchableOpacity style={styles.appButton} onPress={openPlayStore}>
                        <Ionicons name="logo-google-playstore" size={20} color="#FFF" />
                        <Text style={styles.appButtonText}>Google Play</Text>
                      </TouchableOpacity>
                    )}
                  </View>
                </View>
              </View>
            )}
            
            {/* Step 2: Complete Training */}
            <View style={styles.stepCard}>
              <View style={styles.stepNumber}>
                <Text style={styles.stepNumberText}>{hasAppLinks ? '2' : '1'}</Text>
              </View>
              <View style={styles.stepContent}>
                <Text style={styles.stepTitle}>Complete Your Training</Text>
                <Text style={styles.stepDescription}>
                  Learn how to use all the features and start closing deals
                </Text>
                <TouchableOpacity style={styles.trainingButton} onPress={openTraining}>
                  <Ionicons name="school" size={20} color="#000" />
                  <Text style={styles.trainingButtonText}>Start Training</Text>
                </TouchableOpacity>
              </View>
            </View>
            
            {/* Check SMS Notice */}
            <View style={styles.smsNotice}>
              <Ionicons name="chatbubble-ellipses" size={18} color="#007AFF" />
              <Text style={styles.smsNoticeText}>
                Check your phone! We sent you a text with your login details.
              </Text>
            </View>
          </ScrollView>
        </SafeAreaView>
      </View>
    );
  }
  
  // Main Form
  const primaryColor = inviteData?.branding?.primary_color || '#C9A962';
  
  return (
    <View style={styles.container}>
      <LinearGradient colors={['#1A1A2E', '#16213E']} style={StyleSheet.absoluteFill} />
      
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.keyboardView}
      >
        <SafeAreaView style={styles.safeArea}>
          <ScrollView
            contentContainerStyle={styles.scrollContent}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
          >
            {/* Store Logo/Header */}
            <View style={styles.header}>
              {inviteData?.store_logo ? (
                <Image
                  source={{ uri: inviteData.store_logo }}
                  style={styles.storeLogo}
                  resizeMode="contain"
                />
              ) : (
                <View style={[styles.storeIconContainer, { backgroundColor: `${primaryColor}20` }]}>
                  <Ionicons name="storefront" size={40} color={primaryColor} />
                </View>
              )}
              
              <Text style={styles.welcomeTitle}>Join the Team!</Text>
              <Text style={[styles.storeName, { color: primaryColor }]}>
                {inviteData?.store_name}
              </Text>
              {inviteData?.organization?.name && (
                <Text style={styles.orgName}>{inviteData.organization.name}</Text>
              )}
            </View>
            
            {/* Form */}
            <View style={styles.formContainer}>
              <Text style={styles.formTitle}>Create Your Account</Text>
              <Text style={styles.formSubtitle}>
                Set up your credentials to join {inviteData?.store_name}
              </Text>
              
              {/* Name Input */}
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Full Name *</Text>
                <View style={styles.inputContainer}>
                  <Ionicons name="person-outline" size={20} color="#8E8E93" style={styles.inputIcon} />
                  <TextInput
                    style={styles.textInput}
                    value={formData.name}
                    onChangeText={(text) => setFormData(prev => ({ ...prev, name: text }))}
                    placeholder="John Smith"
                    placeholderTextColor="#6E6E73"
                    autoCapitalize="words"
                    autoCorrect={false}
                    data-testid="join-name-input"
                  />
                </View>
              </View>
              
              {/* Email Input */}
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Email Address *</Text>
                <View style={[
                  styles.inputContainer, 
                  inviteData?.recipient_email && styles.inputContainerDisabled
                ]}>
                  <Ionicons name="mail-outline" size={20} color="#8E8E93" style={styles.inputIcon} />
                  <TextInput
                    style={[
                      styles.textInput,
                      inviteData?.recipient_email && styles.textInputDisabled
                    ]}
                    value={formData.email}
                    onChangeText={(text) => setFormData(prev => ({ ...prev, email: text }))}
                    placeholder="john@example.com"
                    placeholderTextColor="#6E6E73"
                    keyboardType="email-address"
                    autoCapitalize="none"
                    autoCorrect={false}
                    editable={!inviteData?.recipient_email}
                    data-testid="join-email-input"
                  />
                </View>
                {inviteData?.recipient_email && (
                  <Text style={styles.inputHint}>Email pre-filled from your invite</Text>
                )}
              </View>
              
              {/* Phone Input (Optional) */}
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Phone Number (optional)</Text>
                <View style={styles.inputContainer}>
                  <Ionicons name="call-outline" size={20} color="#8E8E93" style={styles.inputIcon} />
                  <TextInput
                    style={styles.textInput}
                    value={formData.phone}
                    onChangeText={(text) => setFormData(prev => ({ ...prev, phone: text }))}
                    placeholder="(555) 123-4567"
                    placeholderTextColor="#6E6E73"
                    keyboardType="phone-pad"
                    autoCorrect={false}
                    data-testid="join-phone-input"
                  />
                </View>
              </View>
              
              {/* Password Input */}
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Create Password *</Text>
                <View style={styles.inputContainer}>
                  <Ionicons name="lock-closed-outline" size={20} color="#8E8E93" style={styles.inputIcon} />
                  <TextInput
                    style={styles.textInput}
                    value={formData.password}
                    onChangeText={(text) => setFormData(prev => ({ ...prev, password: text }))}
                    placeholder="At least 6 characters"
                    placeholderTextColor="#6E6E73"
                    secureTextEntry={!showPassword}
                    autoCapitalize="none"
                    autoCorrect={false}
                    data-testid="join-password-input"
                  />
                  <Pressable
                    style={styles.eyeButton}
                    onPress={() => setShowPassword(!showPassword)}
                  >
                    <Ionicons
                      name={showPassword ? 'eye-off-outline' : 'eye-outline'}
                      size={20}
                      color="#8E8E93"
                    />
                  </Pressable>
                </View>
              </View>
              
              {/* Confirm Password Input */}
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Confirm Password *</Text>
                <View style={styles.inputContainer}>
                  <Ionicons name="lock-closed-outline" size={20} color="#8E8E93" style={styles.inputIcon} />
                  <TextInput
                    style={styles.textInput}
                    value={formData.confirmPassword}
                    onChangeText={(text) => setFormData(prev => ({ ...prev, confirmPassword: text }))}
                    placeholder="Re-enter password"
                    placeholderTextColor="#6E6E73"
                    secureTextEntry={!showPassword}
                    autoCapitalize="none"
                    autoCorrect={false}
                    data-testid="join-confirm-password-input"
                  />
                </View>
              </View>
              
              {/* Error Message */}
              {error && (
                <View style={styles.errorBox}>
                  <Ionicons name="alert-circle" size={18} color="#FF3B30" />
                  <Text style={styles.errorBoxText}>{error}</Text>
                </View>
              )}
              
              {/* Submit Button */}
              <TouchableOpacity
                style={[styles.submitButton, { backgroundColor: primaryColor }]}
                onPress={handleSubmit}
                disabled={submitting}
                data-testid="join-submit-button"
              >
                {submitting ? (
                  <ActivityIndicator size="small" color="#000" />
                ) : (
                  <>
                    <Ionicons name="checkmark-circle" size={20} color="#000" />
                    <Text style={styles.submitButtonText}>Create Account & Join</Text>
                  </>
                )}
              </TouchableOpacity>
              
              {/* Login Link */}
              <View style={styles.loginLinkContainer}>
                <Text style={styles.loginLinkText}>Already have an account? </Text>
                <Pressable onPress={() => router.push('/auth/login')}>
                  <Text style={styles.loginLink}>Log In</Text>
                </Pressable>
              </View>
              
              {/* Privacy Note */}
              <Text style={styles.privacyNote}>
                By joining, you agree to receive messages about your account and training.
              </Text>
            </View>
          </ScrollView>
        </SafeAreaView>
      </KeyboardAvoidingView>
    </View>
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
  safeArea: {
    flex: 1,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    color: '#8E8E93',
    fontSize: 15,
    marginTop: 16,
  },
  // Error State
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
  },
  errorIconContainer: {
    marginBottom: 20,
  },
  errorTitle: {
    fontSize: 28,
    fontWeight: '700',
    color: '#FFF',
    marginBottom: 12,
  },
  errorMessage: {
    fontSize: 16,
    color: 'rgba(255,255,255,0.8)',
    textAlign: 'center',
    marginBottom: 16,
    lineHeight: 24,
  },
  errorHint: {
    fontSize: 14,
    color: '#8E8E93',
    textAlign: 'center',
  },
  // Scroll Content
  scrollContent: {
    flexGrow: 1,
    paddingHorizontal: 24,
    paddingTop: 20,
    paddingBottom: 40,
  },
  // Header
  header: {
    alignItems: 'center',
    marginBottom: 32,
  },
  storeLogo: {
    width: 80,
    height: 80,
    borderRadius: 16,
    marginBottom: 16,
  },
  storeIconContainer: {
    width: 80,
    height: 80,
    borderRadius: 40,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  welcomeTitle: {
    fontSize: 28,
    fontWeight: '700',
    color: '#FFF',
    marginBottom: 8,
  },
  storeName: {
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 4,
  },
  orgName: {
    fontSize: 14,
    color: '#8E8E93',
  },
  // Form
  formContainer: {
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderRadius: 16,
    padding: 20,
  },
  formTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 4,
  },
  formSubtitle: {
    fontSize: 14,
    color: '#8E8E93',
    marginBottom: 20,
  },
  inputGroup: {
    marginBottom: 16,
  },
  inputLabel: {
    fontSize: 14,
    fontWeight: '500',
    color: '#FFF',
    marginBottom: 8,
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#2C2C2E',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#3C3C3E',
  },
  inputIcon: {
    paddingLeft: 14,
  },
  textInput: {
    flex: 1,
    padding: 14,
    fontSize: 16,
    color: '#FFF',
  },
  errorBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255,59,48,0.1)',
    padding: 12,
    borderRadius: 10,
    marginBottom: 16,
    gap: 8,
  },
  errorBoxText: {
    color: '#FF3B30',
    fontSize: 14,
    flex: 1,
  },
  submitButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 16,
    borderRadius: 30,
    gap: 8,
    marginTop: 8,
  },
  submitButtonText: {
    fontSize: 17,
    fontWeight: '600',
    color: '#000',
  },
  privacyNote: {
    fontSize: 12,
    color: '#6E6E73',
    textAlign: 'center',
    marginTop: 16,
  },
  // Success State
  successContent: {
    flexGrow: 1,
    paddingHorizontal: 24,
    paddingTop: 40,
    paddingBottom: 40,
  },
  successIconContainer: {
    alignItems: 'center',
    marginBottom: 20,
  },
  successTitle: {
    fontSize: 28,
    fontWeight: '700',
    color: '#FFF',
    textAlign: 'center',
    marginBottom: 4,
  },
  successSubtitle: {
    fontSize: 16,
    color: '#34C759',
    textAlign: 'center',
    marginBottom: 16,
  },
  successMessage: {
    fontSize: 15,
    color: 'rgba(255,255,255,0.8)',
    textAlign: 'center',
    marginBottom: 32,
  },
  stepCard: {
    flexDirection: 'row',
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
  },
  stepNumber: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: '#34C759',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 14,
  },
  stepNumberText: {
    fontSize: 16,
    fontWeight: '700',
    color: '#000',
  },
  stepContent: {
    flex: 1,
  },
  stepTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 4,
  },
  stepDescription: {
    fontSize: 14,
    color: '#8E8E93',
    marginBottom: 12,
  },
  appButtonsRow: {
    flexDirection: 'row',
    gap: 10,
  },
  appButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#2C2C2E',
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderRadius: 10,
    gap: 6,
  },
  appButtonText: {
    color: '#FFF',
    fontSize: 14,
    fontWeight: '500',
  },
  trainingButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#C9A962',
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 20,
    gap: 8,
  },
  trainingButtonText: {
    color: '#000',
    fontSize: 15,
    fontWeight: '600',
  },
  smsNotice: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(0,122,255,0.1)',
    padding: 14,
    borderRadius: 12,
    marginTop: 8,
    gap: 10,
  },
  smsNoticeText: {
    color: '#007AFF',
    fontSize: 14,
    flex: 1,
  },
});
