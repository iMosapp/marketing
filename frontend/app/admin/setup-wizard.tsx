import React, { useState, useEffect, useRef } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet, ScrollView,
  ActivityIndicator, Platform, Image, KeyboardAvoidingView, Animated,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import api from '../../services/api';

import { useThemeStore } from '../../store/themeStore';
const STEPS = [
  { num: 1, title: 'Company Info', icon: 'business-outline' },
  { num: 2, title: 'Branding', icon: 'color-palette-outline' },
  { num: 3, title: 'Review Links', icon: 'star-outline' },
  { num: 4, title: 'Team Members', icon: 'people-outline' },
  { num: 5, title: 'Summary', icon: 'checkmark-circle-outline' },
];

const INDUSTRIES = [
  'Automotive / Dealership', 'Real Estate', 'Restaurant / Hospitality',
  'Salon / Barbershop', 'Health & Wellness', 'Insurance',
  'Financial Services', 'Home Services', 'Retail', 'Other',
];

const COLORS = [
  '#C9A962', '#007AFF', '#34C759', '#FF3B30', '#FF9500',
  '#AF52DE', '#5856D6', '#FF2D55', '#00C7BE', '#30D158',
];

export default function SetupWizardScreen() {
  const { colors } = useThemeStore();
  const s = getS(colors);
  const router = useRouter();
  const scrollRef = useRef<ScrollView>(null);
  const fadeAnim = useRef(new Animated.Value(1)).current;

  const [currentStep, setCurrentStep] = useState(1);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [currentUser, setCurrentUser] = useState<any>(null);

  // Existing data
  const [existingOrgs, setExistingOrgs] = useState<any[]>([]);
  const [existingStores, setExistingStores] = useState<any[]>([]);

  // Step 1: Company Info
  const [selectedOrgId, setSelectedOrgId] = useState('');
  const [selectedStoreId, setSelectedStoreId] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [industry, setIndustry] = useState('');
  const [phone, setPhone] = useState('');
  const [address, setAddress] = useState('');
  const [city, setCity] = useState('');
  const [state, setState] = useState('');
  const [website, setWebsite] = useState('');
  const [isNewOrg, setIsNewOrg] = useState(false);
  const [isNewStore, setIsNewStore] = useState(false);
  const [adminEmail, setAdminEmail] = useState('');

  // Step 2: Branding
  const [primaryColor, setPrimaryColor] = useState('#C9A962');
  const [logoPreview, setLogoPreview] = useState('');
  const [logoUploading, setLogoUploading] = useState(false);

  // Step 3: Review Links
  const [googleReview, setGoogleReview] = useState('');
  const [facebookReview, setFacebookReview] = useState('');
  const [yelpReview, setYelpReview] = useState('');

  // Step 4: Team Members
  const [teamMembers, setTeamMembers] = useState<Array<{ name: string; email: string; phone: string; role: string }>>([]);
  const [inviteResults, setInviteResults] = useState<any[]>([]);

  // Step 5: Completion
  const [wizardComplete, setWizardComplete] = useState(false);

  useEffect(() => {
    loadInitialData();
  }, []);

  const loadInitialData = async () => {
    try {
      const userStr = await AsyncStorage.getItem('user');
      const user = userStr ? JSON.parse(userStr) : null;
      setCurrentUser(user);
      if (user?.email) setAdminEmail(user.email);

      // Load existing orgs and stores
      const [orgsRes, storesRes] = await Promise.all([
        api.get('/admin/organizations').catch(() => ({ data: [] })),
        api.get('/admin/stores').catch(() => ({ data: [] })),
      ]);
      setExistingOrgs(Array.isArray(orgsRes.data) ? orgsRes.data : []);
      setExistingStores(Array.isArray(storesRes.data) ? storesRes.data : []);
    } catch (e) {
      console.error('Error loading data:', e);
    } finally {
      setLoading(false);
    }
  };

  const animateStepChange = (next: number) => {
    Animated.sequence([
      Animated.timing(fadeAnim, { toValue: 0, duration: 120, useNativeDriver: true }),
      Animated.timing(fadeAnim, { toValue: 1, duration: 200, useNativeDriver: true }),
    ]).start();
    setTimeout(() => {
      setCurrentStep(next);
      scrollRef.current?.scrollTo({ y: 0, animated: false });
    }, 120);
  };

  const selectExistingOrg = (org: any) => {
    setSelectedOrgId(org._id);
    setCompanyName(org.name || '');
    setAdminEmail(org.admin_email || '');
    setPhone(org.admin_phone || '');
    setAddress(org.address || '');
    setCity(org.city || '');
    setState(org.state || '');
    setIsNewOrg(false);

    // Load stores for this org
    const orgStores = existingStores.filter((s: any) => s.organization_id === org._id);
    if (orgStores.length > 0) {
      selectExistingStore(orgStores[0]);
    }
  };

  const selectExistingStore = (store: any) => {
    setSelectedStoreId(store._id);
    if (store.phone) setPhone(store.phone);
    if (store.address) setAddress(store.address);
    if (store.city) setCity(store.city);
    if (store.state) setState(store.state);
    if (store.website) setWebsite(store.website);
    if (store.primary_color) setPrimaryColor(store.primary_color);
    if (store.logo_url) setLogoPreview(store.logo_url);
    if (store.review_links) {
      setGoogleReview(store.review_links.google || '');
      setFacebookReview(store.review_links.facebook || '');
      setYelpReview(store.review_links.yelp || '');
    }
    setIsNewStore(false);
  };

  // ─── Step 1: Save Company Info ───
  const saveCompanyInfo = async () => {
    if (!companyName.trim()) { alert('Please enter a company name'); return; }
    setSaving(true);
    try {
      let orgId = selectedOrgId;
      let storeId = selectedStoreId;

      // Create org if new
      if (isNewOrg || !orgId) {
        const slug = companyName.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
        const res = await api.post('/admin/organizations', {
          name: companyName,
          admin_email: adminEmail || currentUser?.email || '',
          admin_phone: phone,
          address, city, state,
          account_type: 'organization',
        });
        orgId = res.data._id || res.data.id;
        setSelectedOrgId(orgId);
        setIsNewOrg(false);
      } else {
        // Update existing org
        await api.put(`/admin/organizations/${orgId}`, {
          name: companyName, admin_phone: phone, address, city, state,
        });
      }

      // Create store if new
      if (isNewStore || !storeId) {
        const res = await api.post('/admin/stores', {
          organization_id: orgId,
          name: companyName,
          phone, address, city, state, website,
        });
        storeId = res.data._id || res.data.id;
        setSelectedStoreId(storeId);
        setIsNewStore(false);
      } else {
        // Update existing store
        await api.put(`/admin/stores/${storeId}`, {
          name: companyName, phone, address, city, state, website,
        });
      }

      animateStepChange(2);
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Error saving company info');
    } finally {
      setSaving(false);
    }
  };

  // ─── Step 2: Save Branding ───
  const handleLogoUpload = async () => {
    if (Platform.OS !== 'web') return;
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.onchange = async (e: any) => {
      const file = e.target.files[0];
      if (!file) return;
      setLogoUploading(true);
      try {
        const formData = new FormData();
        formData.append('file', file);
        const endpoint = selectedStoreId
          ? `/admin/stores/${selectedStoreId}/upload-logo`
          : `/admin/organizations/${selectedOrgId}/upload-logo`;
        const res = await api.post(endpoint, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
        setLogoPreview(res.data.logo_url || '');
      } catch (err: any) {
        alert('Error uploading logo');
      } finally {
        setLogoUploading(false);
      }
    };
    input.click();
  };

  const saveBranding = async () => {
    setSaving(true);
    try {
      if (selectedStoreId) {
        await api.put(`/admin/stores/${selectedStoreId}`, { primary_color: primaryColor });
      }
      animateStepChange(3);
    } catch (e) {
      alert('Error saving branding');
    } finally {
      setSaving(false);
    }
  };

  // ─── Step 3: Save Review Links ───
  const saveReviewLinks = async () => {
    setSaving(true);
    try {
      if (selectedStoreId) {
        await api.put(`/admin/stores/${selectedStoreId}/review-links`, {
          google: googleReview || null,
          facebook: facebookReview || null,
          yelp: yelpReview || null,
        });
      }
      animateStepChange(4);
    } catch (e) {
      alert('Error saving review links');
    } finally {
      setSaving(false);
    }
  };

  // ─── Step 4: Send Invites ───
  const addTeamRow = () => {
    setTeamMembers([...teamMembers, { name: '', email: '', phone: '', role: 'user' }]);
  };

  const updateTeamMember = (index: number, field: string, value: string) => {
    const updated = [...teamMembers];
    (updated[index] as any)[field] = value;
    setTeamMembers(updated);
  };

  const removeTeamMember = (index: number) => {
    setTeamMembers(teamMembers.filter((_, i) => i !== index));
  };

  const sendInvites = async () => {
    const valid = teamMembers.filter(m => m.name.trim() && m.email.trim());
    if (valid.length === 0) {
      animateStepChange(5);
      return;
    }
    setSaving(true);
    try {
      const res = await api.post('/setup-wizard/bulk-invite', {
        store_id: selectedStoreId,
        members: valid,
      });
      setInviteResults(res.data.results || []);
      animateStepChange(5);
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Error sending invites');
    } finally {
      setSaving(false);
    }
  };

  // ─── Step 5: Complete ───
  const completeWizard = async () => {
    setSaving(true);
    try {
      if (selectedOrgId) {
        await api.post(`/setup-wizard/complete/${selectedOrgId}`);
      }
      setWizardComplete(true);
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  };

  // ─── Render Helpers ───
  const renderStepIndicator = () => (
    <View style={s.stepBar}>
      {STEPS.map((step, i) => {
        const isActive = currentStep === step.num;
        const isDone = currentStep > step.num;
        return (
          <View key={step.num} style={s.stepDot}>
            <View style={[
              s.dot,
              isDone && s.dotDone,
              isActive && s.dotActive,
            ]}>
              {isDone ? (
                <Ionicons name="checkmark" size={14} color={colors.text} />
              ) : (
                <Text style={[s.dotText, isActive && s.dotTextActive]}>{step.num}</Text>
              )}
            </View>
            <Text style={[s.stepLabel, isActive && s.stepLabelActive]} numberOfLines={1}>{step.title}</Text>
            {i < STEPS.length - 1 && <View style={[s.stepLine, isDone && s.stepLineDone]} />}
          </View>
        );
      })}
    </View>
  );

  const renderInput = (label: string, value: string, onChange: (t: string) => void, opts?: { placeholder?: string; keyboardType?: any; multiline?: boolean }) => (
    <View style={s.fieldWrap}>
      <Text style={s.fieldLabel}>{label}</Text>
      <TextInput
        style={[s.input, opts?.multiline && { height: 80, textAlignVertical: 'top' }]}
        value={value}
        onChangeText={onChange}
        placeholder={opts?.placeholder || ''}
        placeholderTextColor="#555"
        keyboardType={opts?.keyboardType}
        multiline={opts?.multiline}
        data-testid={`wizard-input-${label.toLowerCase().replace(/\s+/g, '-')}`}
      />
    </View>
  );

  // ─── Step Renderers ───

  const renderStep1 = () => (
    <View>
      <Text style={s.stepTitle}>Company Information</Text>
      <Text style={s.stepDesc}>Let's start with the basics about this business.</Text>

      {existingOrgs.length > 0 && !selectedOrgId && (
        <View style={s.existingSection}>
          <Text style={s.existingLabel}>Select an existing organization or create new:</Text>
          {existingOrgs.map((org: any) => (
            <TouchableOpacity key={org._id} style={s.existingCard} onPress={() => selectExistingOrg(org)} data-testid={`select-org-${org._id}`}>
              <Ionicons name="business" size={20} color="#C9A962" />
              <Text style={s.existingName}>{org.name}</Text>
              <Ionicons name="chevron-forward" size={18} color="#555" />
            </TouchableOpacity>
          ))}
          <TouchableOpacity style={[s.existingCard, s.newCard]} onPress={() => { setIsNewOrg(true); setSelectedOrgId(''); }} data-testid="create-new-org">
            <Ionicons name="add-circle-outline" size={20} color="#34C759" />
            <Text style={[s.existingName, { color: '#34C759' }]}>Create New Organization</Text>
          </TouchableOpacity>
        </View>
      )}

      {renderInput('Company / Store Name *', companyName, setCompanyName, { placeholder: 'e.g. Acme Auto Group' })}

      <View style={s.fieldWrap}>
        <Text style={s.fieldLabel}>Industry</Text>
        <View style={s.chipGrid}>
          {INDUSTRIES.map(ind => (
            <TouchableOpacity
              key={ind}
              style={[s.chip, industry === ind && s.chipActive]}
              onPress={() => setIndustry(ind)}
              data-testid={`industry-${ind}`}
            >
              <Text style={[s.chipText, industry === ind && s.chipTextActive]}>{ind}</Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {renderInput('Phone', phone, setPhone, { placeholder: '(555) 123-4567', keyboardType: 'phone-pad' })}
      {renderInput('Address', address, setAddress, { placeholder: '123 Main St' })}

      <View style={s.row}>
        <View style={{ flex: 1, marginRight: 8 }}>
          {renderInput('City', city, setCity, { placeholder: 'Salt Lake City' })}
        </View>
        <View style={{ flex: 0.5 }}>
          {renderInput('State', state, setState, { placeholder: 'UT' })}
        </View>
      </View>

      {renderInput('Website', website, setWebsite, { placeholder: 'https://example.com', keyboardType: 'url' })}
      {renderInput('Admin Email', adminEmail, setAdminEmail, { placeholder: 'admin@company.com', keyboardType: 'email-address' })}

      <TouchableOpacity style={s.nextBtn} onPress={saveCompanyInfo} disabled={saving} data-testid="wizard-next-step1">
        {saving ? <ActivityIndicator color={colors.text} /> : (
          <>
            <Text style={s.nextBtnText}>Save & Continue</Text>
            <Ionicons name="arrow-forward" size={20} color={colors.text} />
          </>
        )}
      </TouchableOpacity>
    </View>
  );

  const renderStep2 = () => (
    <View>
      <Text style={s.stepTitle}>Branding</Text>
      <Text style={s.stepDesc}>Upload your logo and pick your brand color. This will appear on cards, emails, and the showcase.</Text>

      <View style={s.logoSection}>
        <TouchableOpacity style={s.logoUploadBox} onPress={handleLogoUpload} data-testid="wizard-upload-logo">
          {logoUploading ? (
            <ActivityIndicator color="#C9A962" />
          ) : logoPreview ? (
            <Image source={{ uri: logoPreview.startsWith('/') ? `${api.defaults.baseURL?.replace('/api', '')}${logoPreview}` : logoPreview }} style={s.logoImage} resizeMode="contain" />
          ) : (
            <View style={s.logoPlaceholder}>
              <Ionicons name="cloud-upload-outline" size={36} color="#555" />
              <Text style={s.logoPlaceholderText}>Tap to upload logo</Text>
              <Text style={s.logoHint}>PNG, JPG, or SVG. Recommended 512x512px.</Text>
            </View>
          )}
        </TouchableOpacity>
      </View>

      <View style={s.fieldWrap}>
        <Text style={s.fieldLabel}>Primary Brand Color</Text>
        <View style={s.colorGrid}>
          {COLORS.map(c => (
            <TouchableOpacity
              key={c}
              style={[s.colorSwatch, { backgroundColor: c }, primaryColor === c && s.colorSwatchActive]}
              onPress={() => setPrimaryColor(c)}
              data-testid={`color-${c}`}
            />
          ))}
        </View>
        <View style={s.colorPreviewRow}>
          <View style={[s.colorPreviewDot, { backgroundColor: primaryColor }]} />
          <Text style={s.colorPreviewText}>{primaryColor}</Text>
        </View>
      </View>

      <View style={s.btnRow}>
        <TouchableOpacity style={s.backBtn} onPress={() => animateStepChange(1)} data-testid="wizard-back-step2">
          <Ionicons name="arrow-back" size={18} color={colors.text} />
          <Text style={s.backBtnText}>Back</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[s.nextBtn, { flex: 1 }]} onPress={saveBranding} disabled={saving} data-testid="wizard-next-step2">
          {saving ? <ActivityIndicator color={colors.text} /> : (
            <>
              <Text style={s.nextBtnText}>Save & Continue</Text>
              <Ionicons name="arrow-forward" size={20} color={colors.text} />
            </>
          )}
        </TouchableOpacity>
      </View>
    </View>
  );

  const renderStep3 = () => (
    <View>
      <Text style={s.stepTitle}>Review Links</Text>
      <Text style={s.stepDesc}>Paste your review page URLs. Your team will use these to send one-tap review requests to customers.</Text>

      <View style={s.reviewCard}>
        <View style={s.reviewIconRow}>
          <View style={[s.reviewIcon, { backgroundColor: '#4285F4' }]}>
            <Text style={s.reviewIconText}>G</Text>
          </View>
          <Text style={s.reviewLinkLabel}>Google Reviews</Text>
        </View>
        <TextInput
          style={s.input}
          value={googleReview}
          onChangeText={setGoogleReview}
          placeholder="https://g.page/your-business/review"
          placeholderTextColor="#555"
          data-testid="wizard-google-review"
        />
      </View>

      <View style={s.reviewCard}>
        <View style={s.reviewIconRow}>
          <View style={[s.reviewIcon, { backgroundColor: '#1877F2' }]}>
            <Text style={s.reviewIconText}>f</Text>
          </View>
          <Text style={s.reviewLinkLabel}>Facebook Reviews</Text>
        </View>
        <TextInput
          style={s.input}
          value={facebookReview}
          onChangeText={setFacebookReview}
          placeholder="https://facebook.com/your-page/reviews"
          placeholderTextColor="#555"
          data-testid="wizard-facebook-review"
        />
      </View>

      <View style={s.reviewCard}>
        <View style={s.reviewIconRow}>
          <View style={[s.reviewIcon, { backgroundColor: '#FF1A1A' }]}>
            <Text style={s.reviewIconText}>Y</Text>
          </View>
          <Text style={s.reviewLinkLabel}>Yelp Reviews</Text>
        </View>
        <TextInput
          style={s.input}
          value={yelpReview}
          onChangeText={setYelpReview}
          placeholder="https://yelp.com/biz/your-business"
          placeholderTextColor="#555"
          data-testid="wizard-yelp-review"
        />
      </View>

      <Text style={s.skipHint}>You can add or change these later in Store Settings.</Text>

      <View style={s.btnRow}>
        <TouchableOpacity style={s.backBtn} onPress={() => animateStepChange(2)} data-testid="wizard-back-step3">
          <Ionicons name="arrow-back" size={18} color={colors.text} />
          <Text style={s.backBtnText}>Back</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[s.nextBtn, { flex: 1 }]} onPress={saveReviewLinks} disabled={saving} data-testid="wizard-next-step3">
          {saving ? <ActivityIndicator color={colors.text} /> : (
            <>
              <Text style={s.nextBtnText}>Save & Continue</Text>
              <Ionicons name="arrow-forward" size={20} color={colors.text} />
            </>
          )}
        </TouchableOpacity>
      </View>
    </View>
  );

  const renderStep4 = () => (
    <View>
      <Text style={s.stepTitle}>Add Team Members</Text>
      <Text style={s.stepDesc}>Add your team. They'll each get login credentials and their own digital card, automatically branded.</Text>

      {teamMembers.map((member, idx) => (
        <View key={idx} style={s.teamRow}>
          <View style={s.teamRowHeader}>
            <Text style={s.teamRowNum}>Member {idx + 1}</Text>
            <TouchableOpacity onPress={() => removeTeamMember(idx)} data-testid={`remove-member-${idx}`}>
              <Ionicons name="close-circle" size={22} color="#FF3B30" />
            </TouchableOpacity>
          </View>
          <TextInput style={s.input} value={member.name} onChangeText={v => updateTeamMember(idx, 'name', v)} placeholder="Full Name" placeholderTextColor="#555" data-testid={`member-name-${idx}`} />
          <TextInput style={[s.input, { marginTop: 8 }]} value={member.email} onChangeText={v => updateTeamMember(idx, 'email', v)} placeholder="Email" placeholderTextColor="#555" keyboardType="email-address" autoCapitalize="none" data-testid={`member-email-${idx}`} />
          <TextInput style={[s.input, { marginTop: 8 }]} value={member.phone} onChangeText={v => updateTeamMember(idx, 'phone', v)} placeholder="Phone (optional)" placeholderTextColor="#555" keyboardType="phone-pad" data-testid={`member-phone-${idx}`} />
          <View style={s.roleRow}>
            {['user', 'store_manager'].map(r => (
              <TouchableOpacity
                key={r}
                style={[s.roleChip, member.role === r && s.roleChipActive]}
                onPress={() => updateTeamMember(idx, 'role', r)}
                data-testid={`member-role-${idx}-${r}`}
              >
                <Text style={[s.roleChipText, member.role === r && s.roleChipTextActive]}>
                  {r === 'user' ? 'Sales Rep' : 'Manager'}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      ))}

      <TouchableOpacity style={s.addMemberBtn} onPress={addTeamRow} data-testid="wizard-add-member">
        <Ionicons name="add-circle-outline" size={22} color="#C9A962" />
        <Text style={s.addMemberText}>Add Team Member</Text>
      </TouchableOpacity>

      <Text style={s.skipHint}>You can always add more team members later from Manage Team.</Text>

      <View style={s.btnRow}>
        <TouchableOpacity style={s.backBtn} onPress={() => animateStepChange(3)} data-testid="wizard-back-step4">
          <Ionicons name="arrow-back" size={18} color={colors.text} />
          <Text style={s.backBtnText}>Back</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[s.nextBtn, { flex: 1 }]} onPress={sendInvites} disabled={saving} data-testid="wizard-next-step4">
          {saving ? <ActivityIndicator color={colors.text} /> : (
            <>
              <Text style={s.nextBtnText}>{teamMembers.length > 0 ? 'Create Accounts & Continue' : 'Skip & Continue'}</Text>
              <Ionicons name="arrow-forward" size={20} color={colors.text} />
            </>
          )}
        </TouchableOpacity>
      </View>
    </View>
  );

  const renderStep5 = () => (
    <View>
      {!wizardComplete ? (
        <>
          <Text style={s.stepTitle}>Review & Launch</Text>
          <Text style={s.stepDesc}>Here's everything we've set up. Review and activate when ready.</Text>

          <View style={s.summaryCard}>
            <View style={s.summaryRow}>
              <Ionicons name="business" size={20} color="#C9A962" />
              <View style={s.summaryInfo}>
                <Text style={s.summaryLabel}>Company</Text>
                <Text style={s.summaryValue}>{companyName}</Text>
              </View>
              <Ionicons name="checkmark-circle" size={20} color="#34C759" />
            </View>
            {industry ? (
              <View style={s.summaryRow}>
                <Ionicons name="briefcase-outline" size={20} color="#C9A962" />
                <View style={s.summaryInfo}>
                  <Text style={s.summaryLabel}>Industry</Text>
                  <Text style={s.summaryValue}>{industry}</Text>
                </View>
                <Ionicons name="checkmark-circle" size={20} color="#34C759" />
              </View>
            ) : null}
          </View>

          <View style={s.summaryCard}>
            <View style={s.summaryRow}>
              <View style={[s.summaryColorDot, { backgroundColor: primaryColor }]} />
              <View style={s.summaryInfo}>
                <Text style={s.summaryLabel}>Brand Color</Text>
                <Text style={s.summaryValue}>{primaryColor}</Text>
              </View>
              <Ionicons name="checkmark-circle" size={20} color="#34C759" />
            </View>
            <View style={s.summaryRow}>
              <Ionicons name="image-outline" size={20} color="#C9A962" />
              <View style={s.summaryInfo}>
                <Text style={s.summaryLabel}>Logo</Text>
                <Text style={s.summaryValue}>{logoPreview ? 'Uploaded' : 'Not uploaded yet'}</Text>
              </View>
              {logoPreview ? <Ionicons name="checkmark-circle" size={20} color="#34C759" /> : <Ionicons name="ellipse-outline" size={20} color="#555" />}
            </View>
          </View>

          <View style={s.summaryCard}>
            <View style={s.summaryRow}>
              <Ionicons name="star-outline" size={20} color="#C9A962" />
              <View style={s.summaryInfo}>
                <Text style={s.summaryLabel}>Review Links</Text>
                <Text style={s.summaryValue}>
                  {[googleReview && 'Google', facebookReview && 'Facebook', yelpReview && 'Yelp'].filter(Boolean).join(', ') || 'None added'}
                </Text>
              </View>
              {(googleReview || facebookReview || yelpReview) ? <Ionicons name="checkmark-circle" size={20} color="#34C759" /> : <Ionicons name="ellipse-outline" size={20} color="#555" />}
            </View>
          </View>

          <View style={s.summaryCard}>
            <View style={s.summaryRow}>
              <Ionicons name="people-outline" size={20} color="#C9A962" />
              <View style={s.summaryInfo}>
                <Text style={s.summaryLabel}>Team Members</Text>
                <Text style={s.summaryValue}>
                  {inviteResults.length > 0 ? `${inviteResults.filter(r => r.status === 'created').length} created` : 'None added yet'}
                </Text>
              </View>
              {inviteResults.some(r => r.status === 'created') ? <Ionicons name="checkmark-circle" size={20} color="#34C759" /> : <Ionicons name="ellipse-outline" size={20} color="#555" />}
            </View>
          </View>

          {inviteResults.length > 0 && (
            <View style={s.credentialsCard}>
              <Text style={s.credentialsTitle}>Team Login Credentials</Text>
              <Text style={s.credentialsHint}>Share these with your team members so they can log in.</Text>
              {inviteResults.filter(r => r.status === 'created').map((r, i) => (
                <View key={i} style={s.credentialRow}>
                  <Text style={s.credentialName}>{r.name}</Text>
                  <Text style={s.credentialDetail}>{r.email}</Text>
                  <Text style={s.credentialPassword}>Temp Password: {r.temp_password}</Text>
                </View>
              ))}
            </View>
          )}

          <View style={s.btnRow}>
            <TouchableOpacity style={s.backBtn} onPress={() => animateStepChange(4)} data-testid="wizard-back-step5">
              <Ionicons name="arrow-back" size={18} color={colors.text} />
              <Text style={s.backBtnText}>Back</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[s.nextBtn, s.launchBtn, { flex: 1 }]} onPress={completeWizard} disabled={saving} data-testid="wizard-complete">
              {saving ? <ActivityIndicator color={colors.text} /> : (
                <>
                  <Ionicons name="rocket-outline" size={20} color={colors.text} />
                  <Text style={s.nextBtnText}>Activate & Launch</Text>
                </>
              )}
            </TouchableOpacity>
          </View>
        </>
      ) : (
        <View style={s.doneContainer}>
          <View style={s.doneIconWrap}>
            <Ionicons name="checkmark-circle" size={72} color="#34C759" />
          </View>
          <Text style={s.doneTitle}>Setup Complete!</Text>
          <Text style={s.doneDesc}>
            {companyName} is live and ready to go. Team members can log in now and their digital cards, review links, and showcase pages are all configured.
          </Text>

          <TouchableOpacity style={s.doneBtn} onPress={() => router.push('/admin/manage-team' as any)} data-testid="wizard-goto-team">
            <Ionicons name="people-outline" size={20} color={colors.text} />
            <Text style={s.doneBtnText}>Manage Team</Text>
          </TouchableOpacity>

          <TouchableOpacity style={[s.doneBtn, { backgroundColor: 'transparent', borderWidth: 1, borderColor: colors.surface }]} onPress={() => router.back()} data-testid="wizard-goto-menu">
            <Text style={[s.doneBtnText, { color: colors.text }]}>Back to Menu</Text>
          </TouchableOpacity>
        </View>
      )}
    </View>
  );

  if (loading) {
    return (
      <SafeAreaView style={s.safe}>
        <View style={s.loadingWrap}><ActivityIndicator size="large" color="#C9A962" /></View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={s.safe}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        {/* Header */}
        <View style={s.header}>
          <TouchableOpacity onPress={() => router.back()} style={s.headerBack} data-testid="wizard-back-nav">
            <Ionicons name="chevron-back" size={24} color={colors.text} />
          </TouchableOpacity>
          <Text style={s.headerTitle}>Setup Wizard</Text>
          <View style={{ width: 32 }} />
        </View>

        {renderStepIndicator()}

        <ScrollView ref={scrollRef} style={s.body} contentContainerStyle={s.bodyContent} keyboardShouldPersistTaps="handled">
          <Animated.View style={{ opacity: fadeAnim }}>
            {currentStep === 1 && renderStep1()}
            {currentStep === 2 && renderStep2()}
            {currentStep === 3 && renderStep3()}
            {currentStep === 4 && renderStep4()}
            {currentStep === 5 && renderStep5()}
          </Animated.View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const getS = (colors: any) => StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  loadingWrap: { flex: 1, justifyContent: 'center', alignItems: 'center' },

  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.card },
  headerBack: { width: 32, height: 32, justifyContent: 'center' },
  headerTitle: { fontSize: 17, fontWeight: '700', color: colors.card },

  // Step indicator
  stepBar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingHorizontal: 20, paddingVertical: 16, gap: 0 },
  stepDot: { alignItems: 'center', flex: 1, position: 'relative' },
  dot: { width: 28, height: 28, borderRadius: 14, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center', borderWidth: 2, borderColor: colors.surface },
  dotDone: { backgroundColor: '#C9A962', borderColor: '#C9A962' },
  dotActive: { borderColor: '#C9A962', backgroundColor: colors.card },
  dotText: { fontSize: 12, fontWeight: '700', color: '#555' },
  dotTextActive: { color: '#C9A962' },
  stepLabel: { fontSize: 10, color: '#555', marginTop: 4, textAlign: 'center' },
  stepLabelActive: { color: '#C9A962', fontWeight: '600' },
  stepLine: { position: 'absolute', top: 13, right: -50 + '%' as any, width: '100%' as any, height: 2, backgroundColor: colors.card, zIndex: -1 },
  stepLineDone: { backgroundColor: '#C9A962' },

  // Body
  body: { flex: 1 },
  bodyContent: { padding: 20, paddingBottom: 40 },
  stepTitle: { fontSize: 24, fontWeight: '800', color: colors.card, marginBottom: 8 },
  stepDesc: { fontSize: 14, color: '#8E8E93', lineHeight: 20, marginBottom: 24 },

  // Form fields
  fieldWrap: { marginBottom: 18 },
  fieldLabel: { fontSize: 13, fontWeight: '600', color: '#8E8E93', marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5 },
  input: { backgroundColor: colors.card, borderRadius: 12, padding: 14, fontSize: 16, color: colors.card, borderWidth: 1, borderColor: colors.surface },
  row: { flexDirection: 'row' },

  // Existing org/store selection
  existingSection: { marginBottom: 24 },
  existingLabel: { fontSize: 13, color: '#8E8E93', marginBottom: 10 },
  existingCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, padding: 14, borderRadius: 12, marginBottom: 8, gap: 12, borderWidth: 1, borderColor: colors.surface },
  existingName: { flex: 1, fontSize: 15, fontWeight: '600', color: colors.card },
  newCard: { borderColor: '#34C759', borderStyle: 'dashed' as any },

  // Industry chips
  chipGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.surface },
  chipActive: { backgroundColor: '#C9A962', borderColor: '#C9A962' },
  chipText: { fontSize: 13, color: '#AAA' },
  chipTextActive: { color: colors.card, fontWeight: '700' },

  // Colors
  colorGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginBottom: 12 },
  colorSwatch: { width: 40, height: 40, borderRadius: 20, borderWidth: 3, borderColor: 'transparent' },
  colorSwatchActive: { borderColor: colors.surface },
  colorPreviewRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  colorPreviewDot: { width: 16, height: 16, borderRadius: 8 },
  colorPreviewText: { fontSize: 13, color: '#8E8E93', fontFamily: Platform.OS === 'web' ? 'monospace' : undefined },

  // Logo
  logoSection: { marginBottom: 24 },
  logoUploadBox: { width: '100%' as any, height: 180, borderRadius: 16, borderWidth: 2, borderColor: colors.surface, borderStyle: 'dashed' as any, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.bg, overflow: 'hidden' },
  logoImage: { width: '100%' as any, height: '100%' as any },
  logoPlaceholder: { alignItems: 'center', gap: 8 },
  logoPlaceholderText: { fontSize: 15, color: '#8E8E93', fontWeight: '600' },
  logoHint: { fontSize: 12, color: '#555' },

  // Review links
  reviewCard: { backgroundColor: colors.bg, borderRadius: 14, padding: 16, marginBottom: 14, borderWidth: 1, borderColor: colors.card },
  reviewIconRow: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 10 },
  reviewIcon: { width: 28, height: 28, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  reviewIconText: { fontSize: 16, fontWeight: '800', color: colors.card },
  reviewLinkLabel: { fontSize: 15, fontWeight: '600', color: colors.card },
  skipHint: { fontSize: 12, color: '#555', textAlign: 'center', marginTop: 8, marginBottom: 16 },

  // Team members
  teamRow: { backgroundColor: colors.bg, borderRadius: 14, padding: 16, marginBottom: 12, borderWidth: 1, borderColor: colors.card },
  teamRowHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  teamRowNum: { fontSize: 13, fontWeight: '700', color: '#C9A962' },
  roleRow: { flexDirection: 'row', gap: 8, marginTop: 10 },
  roleChip: { flex: 1, paddingVertical: 10, borderRadius: 10, backgroundColor: colors.card, alignItems: 'center', borderWidth: 1, borderColor: colors.surface },
  roleChipActive: { backgroundColor: '#C9A962', borderColor: '#C9A962' },
  roleChipText: { fontSize: 13, fontWeight: '600', color: '#8E8E93' },
  roleChipTextActive: { color: colors.card },
  addMemberBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 14, borderRadius: 12, borderWidth: 1, borderColor: colors.surface, borderStyle: 'dashed' as any, marginBottom: 8 },
  addMemberText: { fontSize: 15, fontWeight: '600', color: '#C9A962' },

  // Buttons
  btnRow: { flexDirection: 'row', gap: 10, marginTop: 16 },
  nextBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#C9A962', paddingVertical: 16, borderRadius: 50, marginTop: 16 },
  nextBtnText: { fontSize: 16, fontWeight: '800', color: colors.card },
  backBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 20, paddingVertical: 16, borderRadius: 50, backgroundColor: colors.card, marginTop: 16 },
  backBtnText: { fontSize: 14, fontWeight: '600', color: colors.card },
  launchBtn: { backgroundColor: '#34C759' },

  // Summary
  summaryCard: { backgroundColor: colors.bg, borderRadius: 14, padding: 16, marginBottom: 12, borderWidth: 1, borderColor: colors.card },
  summaryRow: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 8 },
  summaryInfo: { flex: 1 },
  summaryLabel: { fontSize: 12, color: '#8E8E93', marginBottom: 2 },
  summaryValue: { fontSize: 15, fontWeight: '600', color: colors.card },
  summaryColorDot: { width: 20, height: 20, borderRadius: 10 },

  // Credentials
  credentialsCard: { backgroundColor: '#1A1500', borderRadius: 14, padding: 16, marginBottom: 12, borderWidth: 1, borderColor: '#C9A96233' },
  credentialsTitle: { fontSize: 15, fontWeight: '700', color: '#C9A962', marginBottom: 4 },
  credentialsHint: { fontSize: 12, color: '#8E8E93', marginBottom: 12 },
  credentialRow: { backgroundColor: colors.bg, borderRadius: 10, padding: 12, marginBottom: 8 },
  credentialName: { fontSize: 14, fontWeight: '700', color: colors.card, marginBottom: 2 },
  credentialDetail: { fontSize: 12, color: '#8E8E93', marginBottom: 4 },
  credentialPassword: { fontSize: 13, color: '#C9A962', fontFamily: Platform.OS === 'web' ? 'monospace' : undefined },

  // Done
  doneContainer: { alignItems: 'center', paddingTop: 40 },
  doneIconWrap: { marginBottom: 20 },
  doneTitle: { fontSize: 28, fontWeight: '900', color: colors.card, marginBottom: 12 },
  doneDesc: { fontSize: 15, color: '#8E8E93', textAlign: 'center', lineHeight: 22, marginBottom: 32, paddingHorizontal: 10 },
  doneBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#C9A962', paddingVertical: 16, paddingHorizontal: 32, borderRadius: 50, marginBottom: 12, width: '100%' as any },
  doneBtnText: { fontSize: 16, fontWeight: '800', color: colors.card },
});
