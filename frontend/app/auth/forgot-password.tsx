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
import { showAlert, showSimpleAlert } from '../../services/alert';

import { useThemeStore } from '../../store/themeStore';
type Step = 'email' | 'code' | 'password';

export default function ForgotPasswordScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  
  const [step, setStep] = useState<Step>('email');
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [devCode, setDevCode] = useState<string | null>(null);
  
  const handleRequestCode = async () => {
    if (!email) {
      showSimpleAlert('Error', 'Please enter your email address');
      return;
    }
    
    setLoading(true);
    try {
      const response = await authAPI.forgotPassword(email);
      // Store dev code for testing (shown in alert in dev mode)
      if (response.dev_code) {
        setDevCode(response.dev_code);
        showAlert(
          'Code Sent',
          `For testing, your reset code is: ${response.dev_code}\n\nIn production, this would be sent to your email.`,
          [{ text: 'OK', onPress: () => setStep('code') }]
        );
      } else {
        showAlert(
          'Code Sent',
          'If an account with that email exists, a reset code has been sent.',
          [{ text: 'OK', onPress: () => setStep('code') }]
        );
      }
    } catch (error: any) {
      const message = error?.response?.data?.detail || 'Failed to send reset code';
      showSimpleAlert('Error', message);
    } finally {
      setLoading(false);
    }
  };
  
  const handleVerifyCode = async () => {
    if (!code || code.length !== 6) {
      showSimpleAlert('Error', 'Please enter a valid 6-digit code');
      return;
    }
    
    setLoading(true);
    try {
      await authAPI.verifyResetCode(email, code);
      setStep('password');
    } catch (error: any) {
      const message = error?.response?.data?.detail || 'Invalid or expired code';
      showSimpleAlert('Error', message);
    } finally {
      setLoading(false);
    }
  };
  
  const handleResetPassword = async () => {
    if (!newPassword || newPassword.length < 4) {
      showSimpleAlert('Error', 'Password must be at least 4 characters');
      return;
    }
    
    if (newPassword !== confirmPassword) {
      showSimpleAlert('Error', 'Passwords do not match');
      return;
    }
    
    setLoading(true);
    try {
      await authAPI.resetPassword(email, code, newPassword);
      showAlert(
        'Success',
        'Your password has been reset. You can now log in with your new password.',
        [{ text: 'OK', onPress: () => router.replace('/auth/login') }]
      );
    } catch (error: any) {
      const message = error?.response?.data?.detail || 'Failed to reset password';
      showSimpleAlert('Error', message);
    } finally {
      setLoading(false);
    }
  };
  
  const renderEmailStep = () => (
    <>
      <Text style={styles.stepTitle}>Reset Your Password</Text>
      <Text style={styles.stepDescription}>
        Enter your email address and we'll send you a code to reset your password.
      </Text>
      
      <TextInput
        style={styles.input}
        placeholder="Email"
        placeholderTextColor={colors.textSecondary}
        value={email}
        onChangeText={setEmail}
        keyboardType="email-address"
        autoCapitalize="none"
        autoCorrect={false}
        autoFocus
      />
      
      <TouchableOpacity
        style={[styles.button, loading && styles.buttonDisabled]}
        onPress={handleRequestCode}
        disabled={loading}
      >
        {loading ? (
          <ActivityIndicator color={colors.text} />
        ) : (
          <Text style={styles.buttonText}>Send Reset Code</Text>
        )}
      </TouchableOpacity>
    </>
  );
  
  const renderCodeStep = () => (
    <>
      <Text style={styles.stepTitle}>Enter Code</Text>
      <Text style={styles.stepDescription}>
        Enter the 6-digit code sent to {email}
      </Text>
      
      {devCode && (
        <View style={styles.devCodeBox}>
          <Text style={styles.devCodeLabel}>Dev Mode - Your Code:</Text>
          <Text style={styles.devCodeText}>{devCode}</Text>
        </View>
      )}
      
      <TextInput
        style={[styles.input, styles.codeInput]}
        placeholder="000000"
        placeholderTextColor={colors.textSecondary}
        value={code}
        onChangeText={setCode}
        keyboardType="number-pad"
        maxLength={6}
        autoFocus
      />
      
      <TouchableOpacity
        style={[styles.button, loading && styles.buttonDisabled]}
        onPress={handleVerifyCode}
        disabled={loading}
      >
        {loading ? (
          <ActivityIndicator color={colors.text} />
        ) : (
          <Text style={styles.buttonText}>Verify Code</Text>
        )}
      </TouchableOpacity>
      
      <TouchableOpacity
        style={styles.linkButton}
        onPress={handleRequestCode}
        disabled={loading}
      >
        <Text style={styles.linkText}>Didn't receive code? Resend</Text>
      </TouchableOpacity>
    </>
  );
  
  const renderPasswordStep = () => (
    <>
      <Text style={styles.stepTitle}>New Password</Text>
      <Text style={styles.stepDescription}>
        Create a new password for your account.
      </Text>
      
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
      />
      
      <TouchableOpacity
        style={[styles.button, loading && styles.buttonDisabled]}
        onPress={handleResetPassword}
        disabled={loading}
      >
        {loading ? (
          <ActivityIndicator color={colors.text} />
        ) : (
          <Text style={styles.buttonText}>Reset Password</Text>
        )}
      </TouchableOpacity>
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
                  router.back();
                } else if (step === 'code') {
                  setStep('email');
                } else {
                  setStep('code');
                }
              }}
              style={styles.backButton}
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
          >
            <Text style={styles.cancelText}>Cancel and return to login</Text>
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
    fontSize: 16,
    color: colors.textSecondary,
    marginBottom: 24,
    lineHeight: 22,
  },
  input: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    fontSize: 16,
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
    fontSize: 16,
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
    color: colors.text,
    fontSize: 17,
    fontWeight: '600',
  },
  linkButton: {
    marginTop: 16,
    alignItems: 'center',
  },
  linkText: {
    color: '#007AFF',
    fontSize: 15,
  },
  cancelButton: {
    marginTop: 32,
    alignItems: 'center',
  },
  cancelText: {
    color: colors.textSecondary,
    fontSize: 15,
  },
  devCodeBox: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: '#FF9500',
    marginBottom: 8,
  },
  devCodeLabel: {
    fontSize: 12,
    color: '#FF9500',
    marginBottom: 4,
    textTransform: 'uppercase',
  },
  devCodeText: {
    fontSize: 24,
    fontWeight: 'bold',
    color: colors.text,
    textAlign: 'center',
    letterSpacing: 4,
  },
});
