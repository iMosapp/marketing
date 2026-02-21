import React, { useState, useEffect } from 'react';
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
  Modal,
  FlatList,
  ActivityIndicator,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';

interface Organization {
  _id: string;
  name: string;
}

// Special "Independent" option
const INDEPENDENT_ORG = { _id: 'independent', name: 'I work independently' };

export default function SignupScreen() {
  const router = useRouter();
  const signup = useAuthStore((state) => state.signup);
  
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('');
  const [selectedOrg, setSelectedOrg] = useState<Organization | null>(null);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [showOrgPicker, setShowOrgPicker] = useState(false);
  const [loadingOrgs, setLoadingOrgs] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  
  const isIndependent = selectedOrg?._id === 'independent';
  
  useEffect(() => {
    loadOrganizations();
  }, []);
  
  const loadOrganizations = async () => {
    try {
      const response = await api.get('/admin/organizations');
      setOrganizations(response.data);
    } catch (error) {
      console.error('Failed to load organizations:', error);
    } finally {
      setLoadingOrgs(false);
    }
  };
  
  const handleSignup = async () => {
    if (!name || !email || !phone || !password) {
      Alert.alert('Error', 'Please fill in all required fields');
      return;
    }
    
    if (!selectedOrg) {
      Alert.alert('Error', 'Please select how you work');
      return;
    }
    
    if (!role.trim()) {
      Alert.alert('Error', 'Please enter your role/title');
      return;
    }
    
    if (!acceptedTerms) {
      Alert.alert('Terms Required', 'Please accept the Terms of Service and Privacy Policy to continue');
      return;
    }
    
    setLoading(true);
    try {
      const signupData: any = { 
        name, 
        email, 
        phone, 
        password,
        role: role.trim(),
        account_type: isIndependent ? 'independent' : 'organization',
      };
      
      // Only include org ID if not independent
      if (!isIndependent) {
        signupData.organization_id = selectedOrg._id;
      }
      
      await signup(signupData);
      
      // Different messages based on account type
      if (isIndependent) {
        Alert.alert(
          'Welcome to MVPLine!',
          "Your account is ready! Let's set up your profile, AI assistant, and virtual business card to get started.",
          [{ text: 'Let\'s Go!', onPress: () => router.replace('/') }]
        );
      } else {
        Alert.alert(
          'Account Created!',
          'Your account is pending approval. You can set up your profile and business card while you wait for admin configuration.',
          [{ text: 'OK', onPress: () => router.replace('/') }]
        );
      }
    } catch (error: any) {
      const message = error?.response?.data?.detail || 'Failed to create account';
      Alert.alert('Error', message);
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.keyboardView}
      >
        <ScrollView contentContainerStyle={styles.scrollContent}>
          <View style={styles.header}>
            <Text style={styles.title}>Create Account</Text>
            <Text style={styles.subtitle}>Start your journey with MVPLine</Text>
          </View>
          
          <View style={styles.form}>
            <TextInput
              style={styles.input}
              placeholder="Full Name *"
              placeholderTextColor="#8E8E93"
              value={name}
              onChangeText={setName}
              autoCapitalize="words"
              data-testid="signup-name-input"
            />
            
            <TextInput
              style={styles.input}
              placeholder="Email *"
              placeholderTextColor="#8E8E93"
              value={email}
              onChangeText={setEmail}
              keyboardType="email-address"
              autoCapitalize="none"
              autoCorrect={false}
              data-testid="signup-email-input"
            />
            
            <TextInput
              style={styles.input}
              placeholder="Phone Number *"
              placeholderTextColor="#8E8E93"
              value={phone}
              onChangeText={setPhone}
              keyboardType="phone-pad"
              data-testid="signup-phone-input"
            />
            
            {/* Organization/Independent Picker */}
            <TouchableOpacity 
              style={styles.pickerButton}
              onPress={() => setShowOrgPicker(true)}
              data-testid="signup-org-picker"
            >
              <Text style={[styles.pickerText, !selectedOrg && styles.pickerPlaceholder]}>
                {selectedOrg 
                  ? (isIndependent ? 'Independent Professional' : selectedOrg.name) 
                  : 'How do you work? *'}
              </Text>
              <Ionicons name="chevron-down" size={20} color="#8E8E93" />
            </TouchableOpacity>
            
            {/* Role/Title Input */}
            <TextInput
              style={styles.input}
              placeholder="Your Role/Title (e.g. Sales Rep, Manager) *"
              placeholderTextColor="#8E8E93"
              value={role}
              onChangeText={setRole}
              autoCapitalize="words"
              data-testid="signup-role-input"
            />
            
            <View style={styles.passwordContainer}>
              <TextInput
                style={styles.passwordInput}
                placeholder="Password *"
                placeholderTextColor="#8E8E93"
                value={password}
                onChangeText={setPassword}
                secureTextEntry={!showPassword}
                autoCapitalize="none"
                data-testid="signup-password-input"
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
            
            {/* Info Banner - Different message for independent vs org */}
            <View style={[styles.infoBanner, isIndependent && styles.infoBannerSuccess]}>
              <Ionicons name={isIndependent ? "checkmark-circle" : "information-circle"} size={20} color={isIndependent ? "#34C759" : "#007AFF"} />
              <Text style={styles.infoText}>
                {isIndependent 
                  ? "As an independent, you'll have full access right away. We'll guide you through setting up your profile, AI assistant, and business card."
                  : "Your account will be reviewed by an admin. You'll have access to set up your profile, AI assistant, and business card while waiting."}
              </Text>
            </View>
            
            <View style={styles.termsContainer}>
              <TouchableOpacity
                style={styles.checkbox}
                onPress={() => setAcceptedTerms(!acceptedTerms)}
                data-testid="terms-checkbox"
              >
                <Ionicons
                  name={acceptedTerms ? 'checkbox' : 'square-outline'}
                  size={24}
                  color={acceptedTerms ? '#007AFF' : '#8E8E93'}
                />
              </TouchableOpacity>
              <Text style={styles.termsText}>
                I agree to the{' '}
                <Text 
                  style={styles.termsLink}
                  onPress={() => router.push('/terms')}
                >
                  Terms of Service
                </Text>
                {' '}and{' '}
                <Text 
                  style={styles.termsLink}
                  onPress={() => router.push('/privacy')}
                >
                  Privacy Policy
                </Text>
              </Text>
            </View>
            
            <TouchableOpacity
              style={[styles.button, (loading || !acceptedTerms) && styles.buttonDisabled]}
              onPress={handleSignup}
              disabled={loading || !acceptedTerms}
              data-testid="signup-submit-button"
            >
              <Text style={styles.buttonText}>
                {loading ? 'Creating Account...' : 'Sign Up'}
              </Text>
            </TouchableOpacity>
            
            <TouchableOpacity
              style={styles.linkButton}
              onPress={() => router.back()}
            >
              <Text style={styles.linkText}>
                Already have an account? <Text style={styles.linkTextBold}>Log In</Text>
              </Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
      
      {/* Organization Picker Modal */}
      <Modal
        visible={showOrgPicker}
        animationType="slide"
        transparent
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>How do you work?</Text>
              <TouchableOpacity onPress={() => setShowOrgPicker(false)}>
                <Ionicons name="close" size={24} color="#8E8E93" />
              </TouchableOpacity>
            </View>
            
            {loadingOrgs ? (
              <View style={styles.loadingContainer}>
                <ActivityIndicator size="large" color="#007AFF" />
              </View>
            ) : (
              <ScrollView style={styles.orgList}>
                {/* Independent Option */}
                <TouchableOpacity
                  style={[
                    styles.orgOption,
                    styles.independentOption,
                    selectedOrg?._id === 'independent' && styles.orgOptionSelected
                  ]}
                  onPress={() => {
                    setSelectedOrg(INDEPENDENT_ORG);
                    setShowOrgPicker(false);
                  }}
                >
                  <View style={[styles.orgIcon, { backgroundColor: '#34C75920' }]}>
                    <Ionicons name="person" size={24} color="#34C759" />
                  </View>
                  <View style={styles.independentInfo}>
                    <Text style={styles.orgName}>I work independently</Text>
                    <Text style={styles.independentDesc}>Full access, set up your own profile</Text>
                  </View>
                  {selectedOrg?._id === 'independent' && (
                    <Ionicons name="checkmark-circle" size={24} color="#34C759" />
                  )}
                </TouchableOpacity>
                
                {/* Divider */}
                <View style={styles.divider}>
                  <View style={styles.dividerLine} />
                  <Text style={styles.dividerText}>Or select your organization</Text>
                  <View style={styles.dividerLine} />
                </View>
                
                {/* Organization Options */}
                {organizations.length === 0 ? (
                  <View style={styles.emptyContainer}>
                    <Text style={styles.emptyText}>No organizations available</Text>
                  </View>
                ) : (
                  organizations.map(org => (
                    <TouchableOpacity
                      key={org._id}
                      style={[
                        styles.orgOption,
                        selectedOrg?._id === org._id && styles.orgOptionSelected
                      ]}
                      onPress={() => {
                        setSelectedOrg(org);
                        setShowOrgPicker(false);
                      }}
                    >
                      <View style={styles.orgIcon}>
                        <Ionicons name="business" size={24} color="#007AFF" />
                      </View>
                      <Text style={styles.orgName}>{org.name}</Text>
                      {selectedOrg?._id === org._id && (
                        <Ionicons name="checkmark-circle" size={24} color="#007AFF" />
                      )}
                    </TouchableOpacity>
                  ))
                )}
              </ScrollView>
            )}
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
    marginBottom: 32,
  },
  title: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#FFF',
    marginBottom: 8,
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
  pickerButton: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderWidth: 1,
    borderColor: '#2C2C2E',
  },
  pickerText: {
    fontSize: 16,
    color: '#FFF',
  },
  pickerPlaceholder: {
    color: '#8E8E93',
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
  infoBanner: {
    backgroundColor: '#007AFF20',
    borderRadius: 12,
    padding: 14,
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    borderWidth: 1,
    borderColor: '#007AFF40',
  },
  infoBannerSuccess: {
    backgroundColor: '#34C75920',
    borderColor: '#34C75940',
  },
  infoText: {
    flex: 1,
    fontSize: 13,
    color: '#8E8E93',
    lineHeight: 18,
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
    color: '#FFF',
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
  termsContainer: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginTop: 8,
    paddingHorizontal: 4,
  },
  checkbox: {
    marginRight: 12,
    marginTop: 2,
  },
  termsText: {
    flex: 1,
    fontSize: 14,
    color: '#8E8E93',
    lineHeight: 22,
  },
  termsLink: {
    color: '#007AFF',
    fontWeight: '500',
  },
  // Modal styles
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.8)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: '#1C1C1E',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: '70%',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFF',
  },
  loadingContainer: {
    padding: 40,
    alignItems: 'center',
  },
  emptyContainer: {
    padding: 40,
    alignItems: 'center',
  },
  emptyText: {
    fontSize: 16,
    color: '#8E8E93',
    marginTop: 12,
  },
  emptySubtext: {
    fontSize: 14,
    color: '#636366',
    marginTop: 4,
  },
  orgList: {
    padding: 8,
  },
  orgOption: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 14,
    marginHorizontal: 8,
    marginVertical: 4,
    borderRadius: 12,
    backgroundColor: '#2C2C2E',
    gap: 12,
  },
  independentOption: {
    borderWidth: 1,
    borderColor: '#34C759',
    backgroundColor: '#34C75910',
  },
  independentInfo: {
    flex: 1,
  },
  independentDesc: {
    fontSize: 12,
    color: '#8E8E93',
    marginTop: 2,
  },
  orgOptionSelected: {
    backgroundColor: '#007AFF20',
    borderWidth: 1,
    borderColor: '#007AFF',
  },
  orgIcon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#007AFF20',
    alignItems: 'center',
    justifyContent: 'center',
  },
  orgName: {
    flex: 1,
    fontSize: 16,
    color: '#FFF',
    fontWeight: '500',
  },
  divider: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 16,
    gap: 12,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: '#3C3C3E',
  },
  dividerText: {
    color: '#8E8E93',
    fontSize: 12,
  },
});