import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  ActivityIndicator,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { authAPI } from '../../services/api';
import { useAuthStore } from '../../store/authStore';
import { showAlert, showSimpleAlert } from '../../services/alert';

import { useThemeStore } from '../../store/themeStore';
type Step = 'email' | 'code' | 'password';
export type CodeFlowMode = 'reset' | 'activate';

const COPY = {
  reset: {
    title: 'Reset Your Password',
    description: "Enter your phone number or email. We'll text a 6-digit code to your registered mobile number.",
    requestBtn: 'Send Reset Code',
    sentTitle: 'Code Sent',
    sentBody: 'A 6-digit reset code has been sent via text to your registered phone number. Check your messages.',
    codeTitle: 'Check Your Texts',
    codeDescription: "Enter the 6-digit code texted to your registered phone number.\nDidn't get it? Check that your phone number is on your account.",
    passwordTitle: 'New Password',
    passwordDescription: 'Create a new password for your account.',
    submitBtn: 'Reset Password',
  },
  activate: {
    title: 'Activate Your Account',
    description: "Enter the mobile number your manager put on your account. We'll text you a 6-digit code to verify it's you.",
    requestBtn: 'Text Me a Code',
    sentTitle: 'Code Sent',
    sentBody: 'We just texted a 6-digit activation code to that number. Enter it on the next screen.',
    codeTitle: 'Check Your Texts',
    codeDescription: "Enter the 6-digit code we just texted you.\nNo text? Make sure this is the number your manager used to set up your account.",
    passwordTitle: 'Choose Your Password',
    passwordDescription: "Phone verified. Now create the password you'll use to log in.",
    submitBtn: 'Activate & Log In',
  },
};

export default function ForgotPasswordScreen({ mode = 'reset' }: { mode?: CodeFlowMode }) {
  const { colors: themeColors } = useThemeStore();
  // Force light theme for public auth page
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
  const styles = getStyles(colors);
  const router = useRouter();
  const login = useAuthStore((s) => s.login);
  const copy = COPY[mode];
  const isActivate = mode === 'activate';
  
  const [step, setStep] = useState<Step>('email');
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [verifiedEmail, setVerifiedEmail] = useState<string | null>(null);
  
  const handleRequestCode = async () => {
    if (!email.trim()) {
      showSimpleAlert('Error', isActivate ? 'Please enter your mobile number' : 'Please enter your phone number or email');
      return;
    }

    setLoading(true);
    try {
      // Send phone or email — backend handles both
      if (isActivate) await authAPI.activateRequest(email.trim());
      else await authAPI.forgotPassword(email.trim());
      showAlert(copy.sentTitle, copy.sentBody, [{ text: 'OK', onPress: () => setStep('code') }]);
    } catch (error: any) {
      const message = error?.response?.data?.detail || 'Failed to send code. Make sure you have a phone number registered on your account.';
      showSimpleAlert('Error', message);
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyCode = async () => {
    if (!code || code.length !== 6) {
      showSimpleAlert('Error', 'Please enter the 6-digit code from your text message');
      return;
    }

    setLoading(true);
    try {
      if (isActivate) {
        const res = await authAPI.activateVerify(email.trim(), code);
        setVerifiedEmail(res?.email || null);
      } else {
        await authAPI.verifyResetCode(email.trim(), code);
      }
      setStep('password');
    } catch (error: any) {
      const message = error?.response?.data?.detail || 'Invalid or expired code';
      showSimpleAlert('Error', message);
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async () => {
    if (!newPassword || newPassword.length < 6) {
      showSimpleAlert('Error', 'Password must be at least 6 characters');
      return;
    }

    if (newPassword !== confirmPassword) {
      showSimpleAlert('Error', 'Passwords do not match');
      return;
    }

    setLoading(true);
    try {
      if (isActivate) {
        const res = await authAPI.activateComplete(email.trim(), code, newPassword);
        const loginEmail = res?.email || verifiedEmail;
        if (loginEmail) {
          try {
            await login(loginEmail, newPassword);
            router.replace('/');
            return;
          } catch {
            // fall through to manual login prompt
          }
        }
        showAlert('Account Activated', 'Your password is set. Log in to get started.', [
          { text: 'Log In', onPress: () => router.replace('/auth/login') },
        ]);
        return;
      }
      await authAPI.resetPassword(email.trim(), code, newPassword);
      showAlert(
        'Password Reset',
        'Your password has been updated. You can now log in with your new password.',
        [{ text: 'Log In', onPress: () => router.replace('/auth/login') }]
      );
    } catch (error: any) {
      const message = error?.response?.data?.detail || (isActivate ? 'Failed to activate account' : 'Failed to reset password');
      showSimpleAlert('Error', message);
    } finally {
      setLoading(false);
    }
  };

  const renderEmailStep = () => (
    <>
      <Text style={styles.stepTitle} testID="code-flow-title" dataSet={{ testid: 'code-flow-title' }}>{copy.title}</Text>
      <Text style={styles.stepDescription}>{copy.description}</Text>

      <TextInput
        style={styles.input}
        placeholder={isActivate ? 'Mobile number' : 'Phone number or email'}
        placeholderTextColor={colors.textSecondary}
        value={email}
        onChangeText={setEmail}
        keyboardType={isActivate ? 'phone-pad' : 'default'}
        autoCapitalize="none"
        autoCorrect={false}
        autoFocus
        testID="code-flow-identifier"
        dataSet={{ testid: 'code-flow-identifier' }}
      />
      
      <TouchableOpacity
        style={[styles.button, loading && styles.buttonDisabled]}
        onPress={handleRequestCode}
        disabled={loading}
        testID="code-flow-request-btn"
        dataSet={{ testid: 'code-flow-request-btn' }}
      >
        {loading ? (
          <ActivityIndicator color="#FFFFFF" />
        ) : (
          <Text style={styles.buttonText}>{copy.requestBtn}</Text>
        )}
      </TouchableOpacity>
    </>
  );
  
  const renderCodeStep = () => (
    <>
      <Text style={styles.stepTitle}>{copy.codeTitle}</Text>
      <Text style={styles.stepDescription}>{copy.codeDescription}</Text>

      <TextInput
        style={[styles.input, styles.codeInput]}
        placeholder="000000"
        placeholderTextColor={colors.textSecondary}
        value={code}
        onChangeText={setCode}
        keyboardType="number-pad"
        maxLength={6}
        autoFocus
        testID="code-flow-code-input"
        dataSet={{ testid: 'code-flow-code-input' }}
      />
      
      <TouchableOpacity
        style={[styles.button, loading && styles.buttonDisabled]}
        onPress={handleVerifyCode}
        disabled={loading}
        testID="code-flow-verify-btn"
        dataSet={{ testid: 'code-flow-verify-btn' }}
      >
        {loading ? (
          <ActivityIndicator color="#FFFFFF" />
        ) : (
          <Text style={styles.buttonText}>Verify Code</Text>
        )}
      </TouchableOpacity>
      
      <TouchableOpacity
        style={styles.linkButton}
        onPress={handleRequestCode}
        disabled={loading}
        testID="code-flow-resend-btn"
        dataSet={{ testid: 'code-flow-resend-btn' }}
      >
        <Text style={styles.linkText}>Didn't receive code? Resend</Text>
      </TouchableOpacity>
    </>
  );
  
  const renderPasswordStep = () => (
    <>
      <Text style={styles.stepTitle}>{copy.passwordTitle}</Text>
      <Text style={styles.stepDescription}>{copy.passwordDescription}</Text>
      
      <View style={styles.passwordContainer}>
        <TextInput
          style={styles.passwordInput}
          placeholder="New Password"
          placeholderTextColor={colors.textSecondary}
          value={newPassword}
          onChangeText={setNewPassword}
          secureTextEntry={!showPassword}
          autoCapitalize="none"
          autoFocus
          testID="code-flow-password"
          dataSet={{ testid: 'code-flow-password' }}
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
      
      <TextInput
        style={styles.input}
        placeholder="Confirm New Password"
        placeholderTextColor={colors.textSecondary}
        value={confirmPassword}
        onChangeText={setConfirmPassword}
        secureTextEntry={!showPassword}
        autoCapitalize="none"
        testID="code-flow-password-confirm"
        dataSet={{ testid: 'code-flow-password-confirm' }}
      />
      
      <TouchableOpacity
        style={[styles.button, loading && styles.buttonDisabled]}
        onPress={handleResetPassword}
        disabled={loading}
        testID="code-flow-submit-btn"
        dataSet={{ testid: 'code-flow-submit-btn' }}
      >
        {loading ? (
          <ActivityIndicator color="#FFFFFF" />
        ) : (
          <Text style={styles.buttonText}>{copy.submitBtn}</Text>
        )}
      </TouchableOpacity>

      {isActivate && (
        <Text style={styles.legalText}>
          By continuing you agree to our{' '}
          <Text style={styles.legalLink} onPress={() => router.push('/terms')}>Terms of Service</Text>
          {' '}and{' '}
          <Text style={styles.legalLink} onPress={() => router.push('/privacy')}>Privacy Policy</Text>.
        </Text>
      )}
    </>
  );
  
  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.keyboardView}
      >
        <ScrollView contentContainerStyle={styles.scrollContent}>
          {/* Header */}
          <View style={styles.header}>
            <TouchableOpacity
              onPress={() => {
                if (step === 'email') {
                  if (router.canGoBack()) router.back(); else router.replace('/auth/login');
                } else if (step === 'code') {
                  setStep('email');
                } else {
                  setStep('code');
                }
              }}
              style={styles.backButton}
              testID="code-flow-back-btn"
              dataSet={{ testid: 'code-flow-back-btn' }}
            >
              <Ionicons name="chevron-back" size={28} color="#007AFF" />
            </TouchableOpacity>
            
            {/* Progress indicator */}
            <View style={styles.progressContainer}>
              {(['email', 'code', 'password'] as Step[]).map((s, index) => (
                <View
                  key={s}
                  style={[
                    styles.progressDot,
                    step === s && styles.progressDotActive,
                    (['email', 'code', 'password'].indexOf(step) > index) && styles.progressDotCompleted,
                  ]}
                />
              ))}
            </View>
            
            <View style={{ width: 28 }} />
          </View>
          
          <View style={styles.form}>
            {step === 'email' && renderEmailStep()}
            {step === 'code' && renderCodeStep()}
            {step === 'password' && renderPasswordStep()}
          </View>
          
          <TouchableOpacity
            style={styles.cancelButton}
            onPress={() => router.replace('/auth/login')}
            testID="code-flow-cancel-btn"
            dataSet={{ testid: 'code-flow-cancel-btn' }}
          >
            <Text style={styles.cancelText}>{isActivate ? 'Already activated? Log in' : 'Cancel and return to login'}</Text>
          </TouchableOpacity>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  keyboardView: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    padding: 24,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 32,
  },
  backButton: {
    padding: 4,
  },
  progressContainer: {
    flexDirection: 'row',
    gap: 8,
  },
  progressDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: colors.surface,
  },
  progressDotActive: {
    backgroundColor: '#007AFF',
    width: 24,
  },
  progressDotCompleted: {
    backgroundColor: '#34C759',
  },
  form: {
    flex: 1,
    gap: 16,
  },
  stepTitle: {
    fontSize: 28,
    fontWeight: 'bold',
    color: colors.text,
    marginBottom: 8,
  },
  stepDescription: {
    fontSize: 18,
    color: colors.textSecondary,
    marginBottom: 24,
    lineHeight: 22,
  },
  input: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    fontSize: 18,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.surface,
  },
  codeInput: {
    textAlign: 'center',
    fontSize: 24,
    fontWeight: '600',
    letterSpacing: 8,
  },
  passwordContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.surface,
  },
  passwordInput: {
    flex: 1,
    padding: 16,
    fontSize: 18,
    color: colors.text,
  },
  eyeButton: {
    padding: 16,
  },
  button: {
    backgroundColor: '#007AFF',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
    marginTop: 8,
  },
  buttonDisabled: {
    opacity: 0.5,
  },
  buttonText: {
    color: '#FFFFFF',
    fontSize: 18,
    fontWeight: '600',
  },
  linkButton: {
    marginTop: 16,
    alignItems: 'center',
  },
  linkText: {
    color: '#007AFF',
    fontSize: 17,
  },
  legalText: {
    marginTop: 16,
    fontSize: 13,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 18,
  },
  legalLink: {
    color: '#007AFF',
    fontWeight: '600',
  },
  cancelButton: {
    marginTop: 32,
    alignItems: 'center',
  },
  cancelText: {
    color: colors.textSecondary,
    fontSize: 17,
  },
});
