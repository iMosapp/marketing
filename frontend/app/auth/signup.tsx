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
  Image,
  LayoutAnimation,
  UIManager,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';

import { useThemeStore } from '../../store/themeStore';
// Enable LayoutAnimation on Android
if (Platform.OS === 'android' && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

interface Organization {
  _id: string;
  name: string;
}

// Special "Independent" option
const INDEPENDENT_ORG = { _id: 'independent', name: 'I work independently' };

export default function SignupScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
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
  
  // Optional fields
  const [showOptionalFields, setShowOptionalFields] = useState(false);
  const [photo, setPhoto] = useState<string | null>(null);
  const [bio, setBio] = useState('');
  const [socialLinks, setSocialLinks] = useState({
    instagram: '',
    facebook: '',
    linkedin: '',
  });
  
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
  
  // Web-compatible alert function
  const showAlert = (title: string, message: string, onOk?: () => void) => {
    if (Platform.OS === 'web') {
      // Use window.alert for web, then execute callback
      window.alert(`${title}\n\n${message}`);
      if (onOk) onOk();
    } else {
      Alert.alert(title, message, onOk ? [{ text: 'OK', onPress: onOk }] : undefined);
    }
  };

  // Toggle optional fields section
  const toggleOptionalFields = () => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setShowOptionalFields(!showOptionalFields);
  };

  // Handle photo selection
  const handleSelectPhoto = async () => {
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: true,
        aspect: [1, 1],
        quality: 0.7,
        base64: true,
      });

      if (!result.canceled && result.assets[0]) {
        const asset = result.assets[0];
        if (asset.base64) {
          setPhoto(`data:image/jpeg;base64,${asset.base64}`);
        }
      }
    } catch (error) {
      console.error('Error picking image:', error);
    }
  };

  const handleSignup = async () => {
    console.log('[Signup] handleSignup called');
    
    if (!name || !email || !phone || !password) {
      showAlert('Error', 'Please fill in all required fields');
      return;
    }
    
    if (!selectedOrg) {
      showAlert('Error', 'Please select how you work');
      return;
    }
    
    if (!role.trim()) {
      showAlert('Error', 'Please enter your role/title');
      return;
    }
    
    if (!acceptedTerms) {
      showAlert('Terms Required', 'Please accept the Terms of Service and Privacy Policy to continue');
      return;
    }
    
    setLoading(true);
    console.log('[Signup] Starting signup process...');
    
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
      
      // Include optional fields if provided
      if (photo) {
        signupData.photo_url = photo;
      }
      if (bio.trim()) {
        signupData.bio = bio.trim();
      }
      if (socialLinks.instagram || socialLinks.facebook || socialLinks.linkedin) {
        signupData.social_links = {};
        if (socialLinks.instagram) signupData.social_links.instagram = socialLinks.instagram;
        if (socialLinks.facebook) signupData.social_links.facebook = socialLinks.facebook;
        if (socialLinks.linkedin) signupData.social_links.linkedin = socialLinks.linkedin;
      }
      
      console.log('[Signup] Calling signup API with data:', { ...signupData, password: '***', photo_url: signupData.photo_url ? '[photo]' : undefined });
      await signup(signupData);
      console.log('[Signup] Signup successful!');
      
      // Different messages based on account type - redirect immediately on web
      if (Platform.OS === 'web') {
        if (isIndependent) {
          window.alert("Welcome to iMOs!\n\nYour account is ready! Let's set up your profile, AI assistant, and virtual business card.");
        } else {
          window.alert("Account Created!\n\nYour account is pending approval. You can set up your profile and business card while you wait.");
        }
        router.replace('/');
      } else {
        if (isIndependent) {
          Alert.alert(
            'Welcome to iMOs!',
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
      }
    } catch (error: any) {
      console.error('[Signup] Error:', error);
      const message = error?.response?.data?.detail || 'Failed to create account';
      showAlert('Error', message);
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
            <View style={styles.subtitleContainer}>
              <Text style={styles.subtitle}>Start your journey with </Text>
              <Image 
                source={require('../../assets/images/imos-logo-white-v3.png')}
                style={styles.subtitleLogo}
                resizeMode="contain"
              />
            </View>
          </View>
          
          <View style={styles.form}>
            <TextInput
              style={styles.input}
              placeholder="Full Name *"
              placeholderTextColor={colors.textSecondary}
              value={name}
              onChangeText={setName}
              autoCapitalize="words"
              data-testid="signup-name-input"
            />
            
            <TextInput
              style={styles.input}
              placeholder="Email *"
              placeholderTextColor={colors.textSecondary}
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
              placeholderTextColor={colors.textSecondary}
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
              <Ionicons name="chevron-down" size={20} color={colors.textSecondary} />
            </TouchableOpacity>
            
            {/* Role/Title Input */}
            <TextInput
              style={styles.input}
              placeholder="Your Role/Title (e.g. Sales Rep, Manager) *"
              placeholderTextColor={colors.textSecondary}
              value={role}
              onChangeText={setRole}
              autoCapitalize="words"
              data-testid="signup-role-input"
            />
            
            <View style={styles.passwordContainer}>
              <TextInput
                style={styles.passwordInput}
                placeholder="Password *"
                placeholderTextColor={colors.textSecondary}
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
                  color={colors.textSecondary}
                />
              </TouchableOpacity>
            </View>
            
            {/* Optional Fields Section */}
            <TouchableOpacity 
              style={styles.optionalToggle}
              onPress={toggleOptionalFields}
            >
              <View style={styles.optionalToggleLeft}>
                <Ionicons name="add-circle" size={20} color="#007AFF" />
                <Text style={styles.optionalToggleText}>
                  Add more info (optional)
                </Text>
              </View>
              <Ionicons 
                name={showOptionalFields ? "chevron-up" : "chevron-down"} 
                size={18} 
                color={colors.textSecondary} 
              />
            </TouchableOpacity>
            
            {showOptionalFields && (
              <View style={styles.optionalFields}>
                {/* Photo */}
                <TouchableOpacity 
                  style={styles.photoSection}
                  onPress={handleSelectPhoto}
                >
                  {photo ? (
                    <Image source={{ uri: photo }} style={styles.photoPreview} />
                  ) : (
                    <View style={styles.photoPlaceholder}>
                      <Ionicons name="camera" size={28} color={colors.textSecondary} />
                    </View>
                  )}
                  <View style={styles.photoTextContainer}>
                    <Text style={styles.photoLabel}>Profile Photo</Text>
                    <Text style={styles.photoHint}>
                      {photo ? 'Tap to change' : 'Helps customers recognize you'}
                    </Text>
                  </View>
                </TouchableOpacity>
                
                {/* Bio */}
                <TextInput
                  style={[styles.input, styles.textArea]}
                  placeholder="Brief bio about yourself..."
                  placeholderTextColor={colors.textSecondary}
                  value={bio}
                  onChangeText={setBio}
                  multiline
                  numberOfLines={3}
                />
                
                {/* Social Links */}
                <Text style={styles.socialLabel}>Social Links (for your business card)</Text>
                <View style={styles.socialInputContainer}>
                  <Ionicons name="logo-instagram" size={20} color="#E1306C" />
                  <TextInput
                    style={styles.socialInput}
                    placeholder="Instagram username"
                    placeholderTextColor="#6E6E73"
                    value={socialLinks.instagram}
                    onChangeText={(text) => setSocialLinks(prev => ({ ...prev, instagram: text }))}
                    autoCapitalize="none"
                  />
                </View>
                <View style={styles.socialInputContainer}>
                  <Ionicons name="logo-facebook" size={20} color="#4267B2" />
                  <TextInput
                    style={styles.socialInput}
                    placeholder="Facebook profile URL"
                    placeholderTextColor="#6E6E73"
                    value={socialLinks.facebook}
                    onChangeText={(text) => setSocialLinks(prev => ({ ...prev, facebook: text }))}
                    autoCapitalize="none"
                  />
                </View>
                <View style={styles.socialInputContainer}>
                  <Ionicons name="logo-linkedin" size={20} color="#0077B5" />
                  <TextInput
                    style={styles.socialInput}
                    placeholder="LinkedIn profile URL"
                    placeholderTextColor="#6E6E73"
                    value={socialLinks.linkedin}
                    onChangeText={(text) => setSocialLinks(prev => ({ ...prev, linkedin: text }))}
                    autoCapitalize="none"
                  />
                </View>
                
                <Text style={styles.optionalHint}>
                  You can always add or change these later
                </Text>
              </View>
            )}
            
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
              {Platform.OS === 'web' ? (
                <button
                  type="button"
                  onClick={() => setAcceptedTerms(!acceptedTerms)}
                  data-testid="terms-checkbox"
                  style={{
                    background: 'transparent',
                    border: 'none',
                    cursor: 'pointer',
                    padding: '4px',
                    display: 'flex',
                    alignItems: 'center',
                  }}
                >
                  <Ionicons
                    name={acceptedTerms ? 'checkbox' : 'square-outline'}
                    size={24}
                    color={acceptedTerms ? '#007AFF' : colors.textSecondary}
                  />
                </button>
              ) : (
                <TouchableOpacity
                  style={styles.checkbox}
                  onPress={() => setAcceptedTerms(!acceptedTerms)}
                  data-testid="terms-checkbox"
                >
                  <Ionicons
                    name={acceptedTerms ? 'checkbox' : 'square-outline'}
                    size={24}
                    color={acceptedTerms ? '#007AFF' : colors.textSecondary}
                  />
                </TouchableOpacity>
              )}
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
            
            {Platform.OS === 'web' ? (
              <button
                type="button"
                style={{
                  width: '100%',
                  padding: '16px',
                  backgroundColor: (loading || !acceptedTerms) ? colors.surface : '#007AFF',
                  border: 'none',
                  borderRadius: '12px',
                  cursor: (loading || !acceptedTerms) ? 'not-allowed' : 'pointer',
                  opacity: (loading || !acceptedTerms) ? 0.5 : 1,
                }}
                onClick={() => {
                  console.log('[Signup] Button clicked');
                  handleSignup();
                }}
                disabled={loading || !acceptedTerms}
                data-testid="signup-submit-button"
              >
                <span style={{ color: colors.text, fontSize: '18px', fontWeight: '600' }}>
                  {loading ? 'Creating Account...' : 'Sign Up'}
                </span>
              </button>
            ) : (
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
            )}
            
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
                <Ionicons name="close" size={24} color={colors.textSecondary} />
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
    justifyContent: 'center',
    padding: 24,
  },
  header: {
    marginBottom: 32,
  },
  title: {
    fontSize: 32,
    fontWeight: 'bold',
    color: colors.text,
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 18,
    color: colors.textSecondary,
  },
  subtitleContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  subtitleLogo: {
    width: 50,
    height: 20,
    marginLeft: 4,
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
    borderColor: colors.surface,
  },
  pickerButton: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderWidth: 1,
    borderColor: colors.surface,
  },
  pickerText: {
    fontSize: 16,
    color: colors.text,
  },
  pickerPlaceholder: {
    color: colors.textSecondary,
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
    color: colors.textSecondary,
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
    color: colors.text,
    fontSize: 17,
    fontWeight: '600',
  },
  linkButton: {
    marginTop: 16,
    alignItems: 'center',
  },
  linkText: {
    color: colors.textSecondary,
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
    color: colors.textSecondary,
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
    backgroundColor: colors.card,
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
    borderBottomColor: colors.surface,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
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
    color: colors.textSecondary,
    marginTop: 12,
  },
  emptySubtext: {
    fontSize: 14,
    color: colors.textTertiary,
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
    backgroundColor: colors.surface,
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
    color: colors.textSecondary,
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
    color: colors.text,
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
    color: colors.textSecondary,
    fontSize: 12,
  },
  // Optional Fields Styles
  optionalToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 14,
    marginTop: 8,
  },
  optionalToggleLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  optionalToggleText: {
    fontSize: 15,
    color: '#007AFF',
    fontWeight: '500',
  },
  optionalFields: {
    marginTop: 12,
    gap: 12,
  },
  photoSection: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 12,
    gap: 14,
  },
  photoPreview: {
    width: 64,
    height: 64,
    borderRadius: 32,
  },
  photoPlaceholder: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  photoTextContainer: {
    flex: 1,
  },
  photoLabel: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.text,
  },
  photoHint: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 2,
  },
  textArea: {
    minHeight: 80,
    paddingTop: 14,
    textAlignVertical: 'top',
  },
  socialLabel: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 8,
    marginBottom: 4,
  },
  socialInputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    gap: 10,
  },
  socialInput: {
    flex: 1,
    fontSize: 15,
    color: colors.text,
  },
  optionalHint: {
    fontSize: 12,
    color: '#6E6E73',
    textAlign: 'center',
    fontStyle: 'italic',
    marginTop: 4,
  },
});