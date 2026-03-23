import React, {
  useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Switch,
  Alert,
  ScrollView,
  ActivityIndicator,
  TextInput,
  Modal,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import { authAPI } from '../../services/api';
import { useToast } from '../../components/common/Toast';
import { useThemeStore } from '../../store/themeStore';
import {
  checkBiometricSupport,
  enableBiometricLogin,
  disableBiometricLogin,
  getBiometricIcon,
  BiometricStatus,
} from '../../utils/biometrics';

export default function SecuritySettingsScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  
const { showToast } = useToast();
    const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState(false);
  const [biometricStatus, setBiometricStatus] = useState<BiometricStatus | null>(null);
  
  // Change password modal state
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [changingPassword, setChangingPassword] = useState(false);
  
  useFocusEffect(
    useCallback(() => {
      loadBiometricStatus();
    }, [])
  );
  
  const loadBiometricStatus = async () => {
    setLoading(true);
    const status = await checkBiometricSupport();
    setBiometricStatus(status);
    setLoading(false);
  };
  
  const handleToggleBiometric = async (value: boolean) => {
    if (!biometricStatus?.isAvailable) return;
    
    setToggling(true);
    
    if (value) {
      // Enable biometric - need to get current password
      Alert.prompt(
        'Enable ' + biometricStatus.biometricLabel,
        'Enter your password to enable biometric login',
        [
          { text: 'Cancel', style: 'cancel', onPress: () => setToggling(false) },
          {
            text: 'Enable',
            onPress: async (password) => {
              if (!password || !user?.email) {
                setToggling(false);
                return;
              }
              
              const success = await enableBiometricLogin({
                email: user.email,
                password: password,
              });
              
              if (success) {
                setBiometricStatus(prev => prev ? { ...prev, isEnabled: true } : null);
                showToast('${biometricStatus.biometricLabel} login enabled!');
              } else {
                Alert.alert('Error', 'Failed to enable biometric login. Please try again.');
              }
              setToggling(false);
            },
          },
        ],
        'secure-text'
      );
    } else {
      // Disable biometric
      Alert.alert(
        'Disable ' + biometricStatus.biometricLabel,
        `Are you sure you want to disable ${biometricStatus.biometricLabel} login?`,
        [
          { text: 'Cancel', style: 'cancel', onPress: () => setToggling(false) },
          {
            text: 'Disable',
            style: 'destructive',
            onPress: async () => {
              const success = await disableBiometricLogin();
              if (success) {
                setBiometricStatus(prev => prev ? { ...prev, isEnabled: false } : null);
              }
              setToggling(false);
            },
          },
        ]
      );
    }
  };
  
  // Fallback for platforms without Alert.prompt (Android)
  const handleToggleBiometricAndroid = async (value: boolean) => {
    if (!biometricStatus?.isAvailable) return;
    
    setToggling(true);
    
    if (value) {
      // For Android, we'll use the biometric prompt itself to verify identity
      const success = await enableBiometricLogin({
        email: user?.email || '',
        password: '', // We'll need to handle this differently for Android
      });
      
      if (success) {
        setBiometricStatus(prev => prev ? { ...prev, isEnabled: true } : null);
        showToast('${biometricStatus.biometricLabel} login enabled!');
      } else {
        Alert.alert('Note', 'To enable biometric login, please log out and log back in with your password.');
      }
      setToggling(false);
    } else {
      Alert.alert(
        'Disable ' + biometricStatus.biometricLabel,
        `Are you sure you want to disable ${biometricStatus.biometricLabel} login?`,
        [
          { text: 'Cancel', style: 'cancel', onPress: () => setToggling(false) },
          {
            text: 'Disable',
            style: 'destructive',
            onPress: async () => {
              const success = await disableBiometricLogin();
              if (success) {
                setBiometricStatus(prev => prev ? { ...prev, isEnabled: false } : null);
              }
              setToggling(false);
            },
          },
        ]
      );
    }
  };
  
  const handleChangePassword = async () => {
    if (!currentPassword) {
      Alert.alert('Error', 'Please enter your current password');
      return;
    }
    if (!newPassword || newPassword.length < 4) {
      Alert.alert('Error', 'New password must be at least 4 characters');
      return;
    }
    if (newPassword !== confirmPassword) {
      Alert.alert('Error', 'New passwords do not match');
      return;
    }
    if (currentPassword === newPassword) {
      Alert.alert('Error', 'New password must be different from current password');
      return;
    }
    
    setChangingPassword(true);
    try {
      await authAPI.changePassword(user?._id || '', currentPassword, newPassword);
      showToast('Your password has been changed successfully');
      setShowPasswordModal(false);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (error: any) {
      const message = error?.response?.data?.detail || 'Failed to change password';
      Alert.alert('Error', message);
    } finally {
      setChangingPassword(false);
    }
  };
  
  const renderPasswordModal = () => (
    <Modal
      visible={showPasswordModal}
      animationType="slide"
      presentationStyle="pageSheet"
      onRequestClose={() => setShowPasswordModal(false)}
    >
      <SafeAreaView style={styles.modalContainer}>
        <View style={styles.modalHeader}>
          <TouchableOpacity onPress={() => setShowPasswordModal(false)}>
            <Text style={styles.modalCancel}>Cancel</Text>
          </TouchableOpacity>
          <Text style={styles.modalTitle}>Change Password</Text>
          <TouchableOpacity 
            onPress={handleChangePassword}
            disabled={changingPassword}
          >
            {changingPassword ? (
              <ActivityIndicator size="small" color="#007AFF" />
            ) : (
              <Text style={styles.modalSave}>Save</Text>
            )}
          </TouchableOpacity>
        </View>
        
        <ScrollView style={styles.modalContent}>
          <Text style={styles.modalSectionTitle}>Current Password</Text>
          <View style={styles.passwordInputContainer}>
            <TextInput
              style={styles.passwordInput}
              placeholder="Enter current password"
              placeholderTextColor={colors.textSecondary}
              value={currentPassword}
              onChangeText={setCurrentPassword}
              secureTextEntry={!showCurrentPassword}
              autoCapitalize="none"
            />
            <TouchableOpacity
              style={styles.eyeButton}
              onPress={() => setShowCurrentPassword(!showCurrentPassword)}
            >
              <Ionicons
                name={showCurrentPassword ? 'eye-off' : 'eye'}
                size={22}
                color={colors.textSecondary}
              />
            </TouchableOpacity>
          </View>
          
          <Text style={[styles.modalSectionTitle, { marginTop: 24 }]}>New Password</Text>
          <View style={styles.passwordInputContainer}>
            <TextInput
              style={styles.passwordInput}
              placeholder="Enter new password"
              placeholderTextColor={colors.textSecondary}
              value={newPassword}
              onChangeText={setNewPassword}
              secureTextEntry={!showNewPassword}
              autoCapitalize="none"
            />
            <TouchableOpacity
              style={styles.eyeButton}
              onPress={() => setShowNewPassword(!showNewPassword)}
            >
              <Ionicons
                name={showNewPassword ? 'eye-off' : 'eye'}
                size={22}
                color={colors.textSecondary}
              />
            </TouchableOpacity>
          </View>
          
          <TextInput
            style={[styles.textInput, { marginTop: 12 }]}
            placeholder="Confirm new password"
            placeholderTextColor={colors.textSecondary}
            value={confirmPassword}
            onChangeText={setConfirmPassword}
            secureTextEntry={!showNewPassword}
            autoCapitalize="none"
          />
          
          <Text style={styles.passwordHint}>
            Password must be at least 4 characters long
          </Text>
        </ScrollView>
      </SafeAreaView>
    </Modal>
  );
  
  if (loading) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
            <Ionicons name="chevron-back" size={28} color="#007AFF" />
          </TouchableOpacity>
          <Text style={styles.title}>Security</Text>
          <View style={{ width: 28 }} />
        </View>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
        </View>
      </SafeAreaView>
    );
  }
  
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.title}>Security</Text>
        <View style={{ width: 28 }} />
      </View>
      
      <ScrollView contentContainerStyle={styles.content}>
        {/* Biometric Section */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>BIOMETRIC LOGIN</Text>
          
          {biometricStatus?.isAvailable ? (
            <View style={styles.settingItem}>
              <View style={styles.settingIcon}>
                <Ionicons 
                  name={getBiometricIcon(biometricStatus.biometricType) as any} 
                  size={24} 
                  color="#007AFF" 
                />
              </View>
              <View style={styles.settingContent}>
                <Text style={styles.settingTitle}>{biometricStatus.biometricLabel}</Text>
                <Text style={styles.settingDescription}>
                  {biometricStatus.isEnabled 
                    ? 'Login quickly using biometrics'
                    : 'Enable for faster login'}
                </Text>
              </View>
              <Switch
                value={biometricStatus.isEnabled}
                onValueChange={handleToggleBiometric}
                trackColor={{ false: colors.borderLight, true: '#34C759' }}
                thumbColor="#FFF"
                disabled={toggling}
              />
            </View>
          ) : (
            <View style={styles.unavailableContainer}>
              <Ionicons name="lock-closed-outline" size={32} color={colors.textSecondary} />
              <Text style={styles.unavailableText}>
                {biometricStatus?.biometricLabel || 'Biometric login is not available on this device'}
              </Text>
            </View>
          )}
        </View>
        
        {/* Security Info */}
        <View style={styles.infoSection}>
          <Ionicons name="shield-checkmark" size={20} color="#34C759" />
          <Text style={styles.infoText}>
            Your biometric data never leaves your device. Credentials are stored securely using encrypted storage.
          </Text>
        </View>
        
        {/* Other Security Options */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>ACCOUNT SECURITY</Text>
          
          <TouchableOpacity 
            style={styles.settingItem}
            onPress={() => setShowPasswordModal(true)}
          >
            <View style={styles.settingIcon}>
              <Ionicons name="key-outline" size={24} color="#FF9500" />
            </View>
            <View style={styles.settingContent}>
              <Text style={styles.settingTitle}>Change Password</Text>
              <Text style={styles.settingDescription}>Update your account password</Text>
            </View>
            <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
          </TouchableOpacity>
          
          <TouchableOpacity 
            style={[styles.settingItem, { marginTop: 8 }]}
            onPress={() => router.push('/auth/forgot-password')}
          >
            <View style={styles.settingIcon}>
              <Ionicons name="refresh-outline" size={24} color="#007AFF" />
            </View>
            <View style={styles.settingContent}>
              <Text style={styles.settingTitle}>Reset Password</Text>
              <Text style={styles.settingDescription}>Forgot your password? Reset via email</Text>
            </View>
            <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
          </TouchableOpacity>
        </View>
      </ScrollView>
      
      {renderPasswordModal()}
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingTop: 28,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.surface,
  },
  backButton: {
    padding: 4,
  },
  title: {
    fontSize: 21,
    fontWeight: 'bold',
    color: colors.text,
  },
  content: {
    padding: 16,
  },
  section: {
    marginBottom: 32,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 12,
    marginLeft: 4,
  },
  settingItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
  },
  settingIcon: {
    width: 40,
    height: 40,
    borderRadius: 10,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 14,
  },
  settingContent: {
    flex: 1,
  },
  settingTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  settingDescription: {
    fontSize: 16,
    color: colors.textSecondary,
    marginTop: 2,
  },
  unavailableContainer: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 24,
    alignItems: 'center',
    gap: 12,
  },
  unavailableText: {
    fontSize: 17,
    color: colors.textSecondary,
    textAlign: 'center',
  },
  infoSection: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginBottom: 32,
    gap: 12,
  },
  infoText: {
    flex: 1,
    fontSize: 16,
    color: colors.textSecondary,
    lineHeight: 20,
  },
  // Modal styles
  modalContainer: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: colors.surface,
  },
  modalCancel: {
    fontSize: 18,
    color: '#007AFF',
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  modalSave: {
    fontSize: 18,
    fontWeight: '600',
    color: '#007AFF',
  },
  modalContent: {
    padding: 16,
  },
  modalSectionTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 8,
    marginLeft: 4,
  },
  passwordInputContainer: {
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
  textInput: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    fontSize: 18,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.surface,
  },
  passwordHint: {
    fontSize: 15,
    color: colors.textSecondary,
    marginTop: 12,
    marginLeft: 4,
  },
});
