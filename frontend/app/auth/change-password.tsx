import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import { WebSafeButton } from '../../components/WebSafeButton';
import api from '../../services/api';
import { showSimpleAlert } from '../../services/alert';

import { useThemeStore } from '../../store/themeStore';
export default function ChangePasswordScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { user, updateUser } = useAuthStore();
  
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const isFirstTimeChange = user?.needs_password_change === true;

  const handleChangePassword = async () => {
    setError('');
    
    if (!currentPassword) {
      setError('Please enter your current password');
      return;
    }
    
    if (!newPassword) {
      setError('Please enter a new password');
      return;
    }
    
    if (newPassword.length < 6) {
      setError('New password must be at least 6 characters');
      return;
    }
    
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }
    
    if (newPassword === currentPassword) {
      setError('New password must be different from current password');
      return;
    }
    
    setLoading(true);
    try {
      await api.post('/auth/change-password', {
        user_id: user?._id,
        current_password: currentPassword,
        new_password: newPassword,
      });
      
      // Update local user state to clear the flag
      updateUser({ needs_password_change: false });
      
      showSimpleAlert('Success', 'Password changed successfully!');
      
      // Navigate to main app
      router.replace('/(tabs)/inbox');
    } catch (err: any) {
      const message = err?.response?.data?.detail || 'Failed to change password';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={{ flex: 1 }}
      >
        <ScrollView 
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
        >
          <View style={styles.header}>
            <View style={styles.iconContainer}>
              <Ionicons name="lock-closed" size={48} color="#007AFF" />
            </View>
            <Text style={styles.title}>
              {isFirstTimeChange ? 'Set Your Password' : 'Change Password'}
            </Text>
            <Text style={styles.subtitle}>
              {isFirstTimeChange 
                ? 'Please create a new password for your account. This is required for security.'
                : 'Enter your current password and choose a new one.'
              }
            </Text>
          </View>

          <View style={styles.form}>
            {/* Current Password */}
            <Text style={styles.inputLabel}>
              {isFirstTimeChange ? 'Temporary Password' : 'Current Password'}
            </Text>
            <View style={styles.inputContainer}>
              <TextInput
                style={styles.input}
                placeholder={isFirstTimeChange ? 'Enter temporary password' : 'Enter current password'}
                placeholderTextColor={colors.textSecondary}
                value={currentPassword}
                onChangeText={setCurrentPassword}
                secureTextEntry={!showCurrentPassword}
                autoCapitalize="none"
              />
              <WebSafeButton
                onPress={() => setShowCurrentPassword(!showCurrentPassword)}
                variant="ghost"
                testID="toggle-current-password"
                style={styles.eyeButton}
              >
                <Ionicons 
                  name={showCurrentPassword ? 'eye-off' : 'eye'} 
                  size={22} 
                  color={colors.textSecondary} 
                />
              </WebSafeButton>
            </View>

            {/* New Password */}
            <Text style={styles.inputLabel}>New Password</Text>
            <View style={styles.inputContainer}>
              <TextInput
                style={styles.input}
                placeholder="Enter new password (min 6 characters)"
                placeholderTextColor={colors.textSecondary}
                value={newPassword}
                onChangeText={setNewPassword}
                secureTextEntry={!showNewPassword}
                autoCapitalize="none"
              />
              <WebSafeButton
                onPress={() => setShowNewPassword(!showNewPassword)}
                variant="ghost"
                testID="toggle-new-password"
                style={styles.eyeButton}
              >
                <Ionicons 
                  name={showNewPassword ? 'eye-off' : 'eye'} 
                  size={22} 
                  color={colors.textSecondary} 
                />
              </WebSafeButton>
            </View>

            {/* Confirm Password */}
            <Text style={styles.inputLabel}>Confirm New Password</Text>
            <View style={styles.inputContainer}>
              <TextInput
                style={styles.input}
                placeholder="Re-enter new password"
                placeholderTextColor={colors.textSecondary}
                value={confirmPassword}
                onChangeText={setConfirmPassword}
                secureTextEntry={!showConfirmPassword}
                autoCapitalize="none"
              />
              <WebSafeButton
                onPress={() => setShowConfirmPassword(!showConfirmPassword)}
                variant="ghost"
                testID="toggle-confirm-password"
                style={styles.eyeButton}
              >
                <Ionicons 
                  name={showConfirmPassword ? 'eye-off' : 'eye'} 
                  size={22} 
                  color={colors.textSecondary} 
                />
              </WebSafeButton>
            </View>

            {/* Error Message */}
            {error ? (
              <View style={styles.errorContainer}>
                <Ionicons name="alert-circle" size={18} color="#FF3B30" />
                <Text style={styles.errorText}>{error}</Text>
              </View>
            ) : null}

            {/* Submit Button */}
            <WebSafeButton
              onPress={handleChangePassword}
              variant="primary"
              loading={loading}
              disabled={loading}
              testID="change-password-submit"
              style={styles.submitButton}
            >
              <Text style={styles.submitButtonText}>
                {isFirstTimeChange ? 'Set Password' : 'Change Password'}
              </Text>
            </WebSafeButton>

            {/* Password Requirements */}
            <View style={styles.requirementsContainer}>
              <Text style={styles.requirementsTitle}>Password Requirements:</Text>
              <View style={styles.requirementRow}>
                <Ionicons 
                  name={newPassword.length >= 6 ? 'checkmark-circle' : 'ellipse-outline'} 
                  size={16} 
                  color={newPassword.length >= 6 ? '#34C759' : colors.textSecondary} 
                />
                <Text style={[
                  styles.requirementText,
                  newPassword.length >= 6 && styles.requirementMet
                ]}>
                  At least 6 characters
                </Text>
              </View>
              <View style={styles.requirementRow}>
                <Ionicons 
                  name={newPassword && newPassword !== currentPassword ? 'checkmark-circle' : 'ellipse-outline'} 
                  size={16} 
                  color={newPassword && newPassword !== currentPassword ? '#34C759' : colors.textSecondary} 
                />
                <Text style={[
                  styles.requirementText,
                  newPassword && newPassword !== currentPassword && styles.requirementMet
                ]}>
                  Different from current password
                </Text>
              </View>
              <View style={styles.requirementRow}>
                <Ionicons 
                  name={confirmPassword && newPassword === confirmPassword ? 'checkmark-circle' : 'ellipse-outline'} 
                  size={16} 
                  color={confirmPassword && newPassword === confirmPassword ? '#34C759' : colors.textSecondary} 
                />
                <Text style={[
                  styles.requirementText,
                  confirmPassword && newPassword === confirmPassword && styles.requirementMet
                ]}>
                  Passwords match
                </Text>
              </View>
            </View>
          </View>
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
  scrollContent: {
    flexGrow: 1,
    padding: 24,
  },
  header: {
    alignItems: 'center',
    marginBottom: 32,
  },
  iconContainer: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: '#007AFF20',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 20,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 12,
    textAlign: 'center',
  },
  subtitle: {
    fontSize: 16,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 22,
    paddingHorizontal: 20,
  },
  form: {
    width: '100%',
    maxWidth: 400,
    alignSelf: 'center',
  },
  inputLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 8,
    marginTop: 16,
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.surface,
  },
  input: {
    flex: 1,
    padding: 16,
    fontSize: 16,
    color: colors.text,
  },
  eyeButton: {
    padding: 12,
  },
  errorContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#FF3B3020',
    padding: 12,
    borderRadius: 10,
    marginTop: 16,
  },
  errorText: {
    flex: 1,
    fontSize: 14,
    color: '#FF3B30',
  },
  submitButton: {
    marginTop: 24,
    paddingVertical: 16,
  },
  submitButtonText: {
    fontSize: 17,
    fontWeight: '600',
    color: colors.text,
  },
  requirementsContainer: {
    marginTop: 24,
    padding: 16,
    backgroundColor: colors.card,
    borderRadius: 12,
  },
  requirementsTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 12,
  },
  requirementRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  requirementText: {
    fontSize: 14,
    color: colors.textSecondary,
  },
  requirementMet: {
    color: '#34C759',
  },
});
