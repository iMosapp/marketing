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
  { num: 1, title: 'Organization', icon: 'business-outline' },
  { num: 2, title: 'Branding', icon: 'color-palette-outline' },
  { num: 3, title: 'Create User', icon: 'person-add-outline' },
  { num: 4, title: 'Profile', icon: 'id-card-outline' },
  { num: 5, title: 'Reviews', icon: 'star-outline' },
  { num: 6, title: 'Templates', icon: 'document-text-outline' },
  { num: 7, title: 'Tags', icon: 'pricetags-outline' },
  { num: 8, title: 'Handoff', icon: 'checkmark-circle-outline' },
];

const INDUSTRIES = [
  'Automotive / Dealership', 'Real Estate', 'Restaurant / Hospitality',
  'Salon / Barbershop', 'Health & Wellness', 'Insurance',
  'Financial Services', 'Home Services', 'Retail', 'Other',
];

const BRAND_COLORS = [
  '#C9A962', '#007AFF', '#34C759', '#FF3B30', '#FF9500',
  '#AF52DE', '#5856D6', '#FF2D55', '#00C7BE', '#30D158',
];

const DEFAULT_TEMPLATES = [
  { name: 'Welcome', content: "Hi {name}! Welcome to the family. I'm {user_name} and I'll be taking care of you. Let me know if you need anything!", category: 'greeting' },
  { name: 'Follow Up', content: "Hey {name}, just checking in! How's everything going? Let me know if I can help with anything.", category: 'follow_up' },
  { name: 'Review Request', content: 'Hi {name}! It was great working with you. If you have a moment, I\'d love a quick review: {review_link}', category: 'review' },
  { name: 'Referral Ask', content: "Hi {name}! If you know anyone who could benefit from our services, I'd really appreciate the referral!", category: 'referral' },
  { name: 'Birthday', content: 'Happy Birthday, {name}! Hope you have an amazing day!', category: 'celebration' },
  { name: 'Anniversary', content: "Happy anniversary, {name}! Can you believe it's been {years} year(s)? Thanks for being with us!", category: 'celebration' },
];

export default function SetupWizardScreen() {
  const { colors } = useThemeStore();
  const s = getS(colors);
  const router = useRouter();
  const scrollRef = useRef<ScrollView>(null);
  const fadeAnim = useRef(new Animated.Value(1)).current;

  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [currentUser, setCurrentUser] = useState<any>(null);
  const [skipped, setSkipped] = useState<Set<number>>(new Set());

  // Existing data
  const [existingOrgs, setExistingOrgs] = useState<any[]>([]);
  const [existingStores, setExistingStores] = useState<any[]>([]);
  const [orgStores, setOrgStores] = useState<any[]>([]);

  // Step 1: Organization
  const [orgId, setOrgId] = useState('');
  const [storeId, setStoreId] = useState('');
  const [orgName, setOrgName] = useState('');
  const [storeName, setStoreName] = useState('');
  const [phone, setPhone] = useState('');
  const [address, setAddress] = useState('');
  const [city, setCity] = useState('');
  const [stateVal, setStateVal] = useState('');
  const [website, setWebsite] = useState('');
  const [industry, setIndustry] = useState('');
  const [isNewOrg, setIsNewOrg] = useState(true);
  const [isNewStore, setIsNewStore] = useState(true);
  const [showIndustryPicker, setShowIndustryPicker] = useState(false);

  // Step 2: Branding
  const [primaryColor, setPrimaryColor] = useState('#C9A962');
  const [logoUrl, setLogoUrl] = useState('');
  const [logoUploading, setLogoUploading] = useState(false);
  const [emailFooter, setEmailFooter] = useState('');

  // Step 3: Create User
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [userEmail, setUserEmail] = useState('');
  const [userPhone, setUserPhone] = useState('');
  const [userRole, setUserRole] = useState('user');
  const [tempPassword, setTempPassword] = useState('');
  const [createdUserId, setCreatedUserId] = useState('');

  // Step 4: User Profile
  const [userTitle, setUserTitle] = useState('');
  const [userBio, setUserBio] = useState('');
  const [userPhoto, setUserPhoto] = useState('');
  const [photoUploading, setPhotoUploading] = useState(false);
  const [socialIG, setSocialIG] = useState('');
  const [socialFB, setSocialFB] = useState('');
  const [socialLI, setSocialLI] = useState('');

  // Step 5: Review Links
  const [googleReview, setGoogleReview] = useState('');
  const [facebookReview, setFacebookReview] = useState('');
  const [yelpReview, setYelpReview] = useState('');
  const [dealerraterReview, setDealerraterReview] = useState('');
  const [customReviewName, setCustomReviewName] = useState('');
  const [customReviewUrl, setCustomReviewUrl] = useState('');

  // Step 6: Templates
  const [templates, setTemplates] = useState(DEFAULT_TEMPLATES.map(t => ({ ...t, enabled: true })));
  const [newTemplateName, setNewTemplateName] = useState('');
  const [newTemplateContent, setNewTemplateContent] = useState('');

  // Step 7: Tags
  const [existingTags, setExistingTags] = useState<any[]>([]);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [newTagName, setNewTagName] = useState('');

  useEffect(() => { loadInitialData(); }, []);

  const loadInitialData = async () => {
    try {
      const userStr = await AsyncStorage.getItem('user');
      const user = userStr ? JSON.parse(userStr) : null;
      setCurrentUser(user);
      const pw = 'Welcome' + Math.floor(1000 + Math.random() * 9000) + '!';
      setTempPassword(pw);
      const [orgsRes, storesRes] = await Promise.all([
        api.get('/admin/organizations').catch(() => ({ data: [] })),
        api.get('/admin/stores').catch(() => ({ data: [] })),
      ]);
      setExistingOrgs(Array.isArray(orgsRes.data) ? orgsRes.data : []);
      setExistingStores(Array.isArray(storesRes.data) ? storesRes.data : []);
      if (user?._id) {
        const tagsRes = await api.get(`/tags/${user._id}`).catch(() => ({ data: [] }));
        setExistingTags(Array.isArray(tagsRes.data) ? tagsRes.data : []);
      }
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const selectExistingOrg = (org: any) => {
    setOrgId(org._id);
    setOrgName(org.name);
    setIsNewOrg(false);
    // Filter stores for this org
    const filtered = existingStores.filter((s: any) => s.organization_id === org._id);
    setOrgStores(filtered);
    // Reset store selection
    setStoreId('');
    setStoreName('');
    setIsNewStore(true);
  };

  const selectExistingStore = (store: any) => {
    setStoreId(store._id);
    setStoreName(store.name);
    setIsNewStore(false);
    if (store.phone) setPhone(store.phone);
    if (store.city) setCity(store.city);
    if (store.state) setStateVal(store.state);
    if (store.website) setWebsite(store.website);
    if (store.industry) setIndustry(store.industry);
  };

  const go = (next: number) => {
    Animated.sequence([
      Animated.timing(fadeAnim, { toValue: 0, duration: 100, useNativeDriver: true }),
      Animated.timing(fadeAnim, { toValue: 1, duration: 150, useNativeDriver: true }),
    ]).start();
    setTimeout(() => { setStep(next); scrollRef.current?.scrollTo({ y: 0, animated: false }); }, 100);
  };

  const skip = () => { setSkipped(prev => new Set(prev).add(step)); go(step + 1); };

  // ---- STEP 1: Save Org/Store ----
  const saveOrg = async () => {
    if (!orgName.trim()) { alert('Enter an organization name'); return; }
    setSaving(true);
    try {
      let oid = orgId;
      if (isNewOrg || !oid) {
        const res = await api.post('/admin/organizations', {
          name: orgName, admin_email: currentUser?.email || '', admin_phone: phone,
          address, city, state: stateVal, account_type: 'organization',
        });
        oid = res.data._id || res.data.id;
        setOrgId(oid); setIsNewOrg(false);
      } else {
        await api.put(`/admin/organizations/${oid}`, { name: orgName, admin_phone: phone, address, city, state: stateVal });
      }
      let sid = storeId;
      if (isNewStore || !sid) {
        const res = await api.post('/admin/stores', {
          organization_id: oid, name: storeName || orgName,
          phone, address, city, state: stateVal, website, industry,
        });
        sid = res.data._id || res.data.id;
        setStoreId(sid); setIsNewStore(false);
      } else {
        await api.put(`/admin/stores/${sid}`, { name: storeName || orgName, phone, address, city, state: stateVal, website, industry });
      }
      go(2);
    } catch (e: any) { alert(e.response?.data?.detail || 'Error saving'); }
    finally { setSaving(false); }
  };

  // ---- STEP 2: Save Branding ----
  const uploadLogo = async () => {
    if (Platform.OS !== 'web') return;
    const input = document.createElement('input');
    input.type = 'file'; input.accept = 'image/*';
    input.onchange = async (e: any) => {
      const file = e.target.files[0]; if (!file) return;
      setLogoUploading(true);
      try {
        const fd = new FormData(); fd.append('file', file);
        const endpoint = storeId ? `/admin/stores/${storeId}/upload-logo` : `/admin/organizations/${orgId}/upload-logo`;
        const res = await api.post(endpoint, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
        setLogoUrl(res.data.logo_url || '');
      } catch { alert('Error uploading logo'); }
      finally { setLogoUploading(false); }
    };
    input.click();
  };

  const saveBranding = async () => {
    setSaving(true);
    try {
      if (storeId) await api.put(`/admin/stores/${storeId}`, { primary_color: primaryColor, email_footer: emailFooter });
      go(3);
    } catch { alert('Error saving branding'); }
    finally { setSaving(false); }
  };

  // ---- STEP 3: Create User ----
  const createUser = async () => {
    if (!firstName.trim() || !userEmail.trim()) { alert('First name and email required'); return; }
    setSaving(true);
    try {
      const fullName = `${firstName.trim()} ${lastName.trim()}`.trim();
      const res = await api.post('/admin/users', {
        name: fullName,
        email: userEmail,
        phone: userPhone,
        password: tempPassword,
        role: userRole,
        store_id: storeId,
        organization_id: orgId,
      });
      const uid = res.data._id || res.data.id;
      setCreatedUserId(uid);
      go(4);
    } catch (e: any) { alert(e.response?.data?.detail || 'Error creating user'); }
    finally { setSaving(false); }
  };

  // ---- STEP 4: Save Profile ----
  const uploadPhoto = async () => {
    if (Platform.OS !== 'web') return;
    const input = document.createElement('input');
    input.type = 'file'; input.accept = 'image/*';
    input.onchange = async (e: any) => {
      const file = e.target.files[0]; if (!file) return;
      setPhotoUploading(true);
      try {
        if (createdUserId) {
          const fd = new FormData(); fd.append('file', file);
          const res = await api.post(`/profile/${createdUserId}/photo`, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
          if (res.data.photo_url) { setUserPhoto(res.data.photo_url); setPhotoUploading(false); return; }
        }
        const reader = new FileReader();
        reader.onload = () => { setUserPhoto(reader.result as string); setPhotoUploading(false); };
        reader.readAsDataURL(file);
      } catch { setPhotoUploading(false); }
    };
    input.click();
  };

  const saveProfile = async () => {
    setSaving(true);
    try {
      if (createdUserId) {
        const profileData: any = { title: userTitle, bio: userBio };
        if (socialIG) profileData.social_instagram = socialIG;
        if (socialFB) profileData.social_facebook = socialFB;
        if (socialLI) profileData.social_linkedin = socialLI;
        if (userPhoto && !userPhoto.startsWith('data:')) profileData.photo_url = userPhoto;
        await api.put(`/admin/users/${createdUserId}`, profileData);
      }
      go(5);
    } catch (e: any) { alert(e.response?.data?.detail || 'Error saving profile'); }
    finally { setSaving(false); }
  };

  // ---- STEP 5: Save Review Links ----
  const saveReviews = async () => {
    setSaving(true);
    try {
      if (storeId) {
        const links: any = {};
        if (googleReview) links.google = googleReview;
        if (facebookReview) links.facebook = facebookReview;
        if (yelpReview) links.yelp = yelpReview;
        if (dealerraterReview) links.dealerrater = dealerraterReview;
        if (customReviewUrl) links.custom = [{ name: customReviewName || 'Custom', url: customReviewUrl }];
        await api.put(`/admin/stores/${storeId}/review-links`, links);
      }
      go(6);
    } catch { alert('Error saving review links'); }
    finally { setSaving(false); }
  };

  // ---- STEP 6: Save Templates ----
  const addTemplate = () => {
    if (!newTemplateName.trim() || !newTemplateContent.trim()) return;
    setTemplates([...templates, { name: newTemplateName, content: newTemplateContent, category: 'custom', enabled: true }]);
    setNewTemplateName(''); setNewTemplateContent('');
  };

  const saveTemplates = async () => {
    setSaving(true);
    try {
      const uid = createdUserId || currentUser?._id;
      if (uid) {
        for (const t of templates.filter(t => t.enabled)) {
          await api.post(`/templates/${uid}`, { name: t.name, content: t.content, category: t.category }).catch(() => {});
        }
      }
      go(7);
    } catch { alert('Error saving templates'); }
    finally { setSaving(false); }
  };

  // ---- STEP 7: Save Tags ----
  const addNewTag = async () => {
    if (!newTagName.trim()) return;
    const uid = createdUserId || currentUser?._id;
    try {
      await api.post(`/tags/${uid}`, { name: newTagName, color: primaryColor, icon: 'pricetag' });
      setSelectedTags([...selectedTags, newTagName]);
      setNewTagName('');
      const res = await api.get(`/tags/${uid}`).catch(() => ({ data: [] }));
      setExistingTags(Array.isArray(res.data) ? res.data : []);
    } catch (e: any) { alert(e.response?.data?.detail || 'Error creating tag'); }
  };

  // ---- Build Handoff Checklist ----
  const getHandoffItems = () => {
    const items: Array<{ label: string; done: boolean; userAction: string }> = [
      { label: 'Organization created', done: !!orgId, userAction: '' },
      { label: 'Store configured', done: !!storeId, userAction: '' },
      { label: 'Logo uploaded', done: !!logoUrl, userAction: logoUrl ? '' : 'Upload company logo in Settings > Branding' },
      { label: 'Brand color set', done: primaryColor !== '#C9A962' || !!logoUrl, userAction: '' },
      { label: 'User account created', done: !!createdUserId, userAction: '' },
      { label: 'Password reset needed', done: false, userAction: 'Reset password on first login' },
      { label: 'Headshot uploaded', done: !!userPhoto, userAction: userPhoto ? '' : 'Upload profile photo in My Account' },
      { label: 'Bio / Title set', done: !!(userTitle && userBio), userAction: (!userTitle || !userBio) ? 'Add title & bio in My Account' : '' },
      { label: 'Google Review link', done: !!googleReview, userAction: googleReview ? '' : 'Add Google review link in Settings > Review Links' },
      { label: 'Facebook Review link', done: !!facebookReview, userAction: facebookReview ? '' : 'Add Facebook review link (optional)' },
      { label: 'Message templates', done: !skipped.has(6), userAction: skipped.has(6) ? 'Customize message templates in Settings' : '' },
      { label: 'Tags configured', done: selectedTags.length > 0 || !skipped.has(7), userAction: skipped.has(7) ? 'Set up contact tags in Settings > Tags' : '' },
    ];
    return items;
  };

  // ---- Shared Components ----
  const SectionCard = ({ children, style }: { children: React.ReactNode; style?: any }) => (
    <View style={[s.sectionCard, style]}>{children}</View>
  );

  const StepHeader = ({ title, desc }: { title: string; desc: string }) => (
    <View style={{ marginBottom: 24 }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 6 }}>
        <View style={s.stepNumBadge}>
          <Text style={s.stepNumBadgeText}>{step}</Text>
        </View>
        <Text style={s.stepTitle}>{title}</Text>
      </View>
      <Text style={s.stepDesc}>{desc}</Text>
    </View>
  );

  const Label = ({ text, required }: { text: string; required?: boolean }) => (
    <Text style={s.label}>{text}{required ? <Text style={{ color: '#C9A962' }}> *</Text> : null}</Text>
  );

  const BtnRow = ({ onBack, onSkip, onNext, nextLabel, nextDisabled }: any) => (
    <View style={s.btnRow}>
      {onBack && <TouchableOpacity style={s.btnSecondary} onPress={onBack} data-testid="wizard-back-btn"><Ionicons name="arrow-back" size={18} color={colors.textSecondary} /><Text style={s.btnSecondaryText}>Back</Text></TouchableOpacity>}
      {onSkip && <TouchableOpacity style={s.btnSkip} onPress={onSkip} data-testid="wizard-skip-btn"><Text style={s.btnSkipText}>Skip</Text><Ionicons name="arrow-forward" size={16} color="#FF9500" /></TouchableOpacity>}
      <TouchableOpacity style={[s.btnPrimary, nextDisabled && s.btnDisabled]} onPress={onNext} disabled={saving || nextDisabled} data-testid="wizard-next-btn">
        {saving ? <ActivityIndicator size="small" color="#000" /> : <><Text style={s.btnPrimaryText}>{nextLabel || 'Continue'}</Text><Ionicons name="arrow-forward" size={18} color="#000" /></>}
      </TouchableOpacity>
    </View>
  );

  // ---- RENDER: Step Bar ----
  const renderStepBar = () => (
    <View style={s.stepBarContainer}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.stepBar}>
        {STEPS.map((st) => {
          const active = step === st.num;
          const done = step > st.num && !skipped.has(st.num);
          const wasSkipped = skipped.has(st.num);
          return (
            <TouchableOpacity key={st.num} style={s.stepDot} onPress={() => st.num < step && go(st.num)} data-testid={`wizard-step-${st.num}`}>
              <View style={[s.dot, done && s.dotDone, active && s.dotActive, wasSkipped && s.dotSkipped]}>
                {done ? <Ionicons name="checkmark" size={14} color="#FFF" /> :
                 wasSkipped ? <Ionicons name="arrow-forward" size={12} color="#FF9500" /> :
                 active ? <Ionicons name={st.icon as any} size={14} color="#000" /> :
                 <Text style={s.dotText}>{st.num}</Text>}
              </View>
              <Text style={[s.stepLabel, active && s.stepLabelActive, done && s.stepLabelDone]} numberOfLines={1}>{st.title}</Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>
      {/* Progress bar */}
      <View style={s.progressTrack}>
        <Animated.View style={[s.progressFill, { width: `${((step - 1) / (STEPS.length - 1)) * 100}%` }]} />
      </View>
    </View>
  );

  // ---- RENDER: Step 1 ----
  const renderStep1 = () => (
    <View>
      <StepHeader title="Organization & Store" desc="Create a new organization or select an existing one to configure." />

      {existingOrgs.length > 0 && (
        <SectionCard>
          <Label text="Select Existing Organization" />
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 8 }}>
            {existingOrgs.map(o => (
              <TouchableOpacity key={o._id} onPress={() => selectExistingOrg(o)}
                style={[s.chip, orgId === o._id && !isNewOrg && s.chipActive]} data-testid={`org-chip-${o._id}`}>
                <Ionicons name="business" size={14} color={orgId === o._id && !isNewOrg ? '#000' : colors.textSecondary} />
                <Text style={[s.chipText, orgId === o._id && !isNewOrg && s.chipTextActive]}>{o.name}</Text>
              </TouchableOpacity>
            ))}
            <TouchableOpacity onPress={() => { setOrgId(''); setOrgName(''); setIsNewOrg(true); setOrgStores([]); setStoreId(''); setStoreName(''); setIsNewStore(true); }}
              style={[s.chip, isNewOrg && s.chipActive]} data-testid="new-org-chip">
              <Ionicons name="add-circle" size={16} color={isNewOrg ? '#000' : '#C9A962'} />
              <Text style={[s.chipText, isNewOrg && s.chipTextActive]}>Create New</Text>
            </TouchableOpacity>
          </ScrollView>
        </SectionCard>
      )}

      {/* Show store picker if existing org selected */}
      {!isNewOrg && orgStores.length > 0 && (
        <SectionCard>
          <Label text="Select Store" />
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 8 }}>
            {orgStores.map(st => (
              <TouchableOpacity key={st._id} onPress={() => selectExistingStore(st)}
                style={[s.chip, storeId === st._id && !isNewStore && s.chipActive]} data-testid={`store-chip-${st._id}`}>
                <Ionicons name="storefront" size={14} color={storeId === st._id && !isNewStore ? '#000' : colors.textSecondary} />
                <Text style={[s.chipText, storeId === st._id && !isNewStore && s.chipTextActive]}>{st.name}</Text>
              </TouchableOpacity>
            ))}
            <TouchableOpacity onPress={() => { setStoreId(''); setStoreName(''); setIsNewStore(true); }}
              style={[s.chip, isNewStore && s.chipActive]} data-testid="new-store-chip">
              <Ionicons name="add-circle" size={16} color={isNewStore ? '#000' : '#C9A962'} />
              <Text style={[s.chipText, isNewStore && s.chipTextActive]}>New Store</Text>
            </TouchableOpacity>
          </ScrollView>
        </SectionCard>
      )}

      <SectionCard>
        <Label text="Organization Name" required />
        <TextInput style={s.input} placeholder="e.g., Rev1 Auto Group" placeholderTextColor={colors.textTertiary}
          value={orgName} onChangeText={setOrgName} data-testid="org-name-input" />

        <Label text="Store / Location Name" />
        <TextInput style={s.input} placeholder="e.g., Rev1 Downtown (defaults to org name)" placeholderTextColor={colors.textTertiary}
          value={storeName} onChangeText={setStoreName} data-testid="store-name-input" />

        {/* Industry Picker */}
        <Label text="Industry" />
        <TouchableOpacity style={[s.input, { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }]}
          onPress={() => setShowIndustryPicker(!showIndustryPicker)} data-testid="industry-picker">
          <Text style={{ fontSize: 16, color: industry ? colors.text : colors.textTertiary }}>{industry || 'Select industry...'}</Text>
          <Ionicons name={showIndustryPicker ? 'chevron-up' : 'chevron-down'} size={18} color={colors.textTertiary} />
        </TouchableOpacity>
        {showIndustryPicker && (
          <View style={s.pickerDropdown}>
            {INDUSTRIES.map(ind => (
              <TouchableOpacity key={ind} style={[s.pickerItem, industry === ind && s.pickerItemActive]}
                onPress={() => { setIndustry(ind); setShowIndustryPicker(false); }}>
                <Text style={[s.pickerItemText, industry === ind && s.pickerItemTextActive]}>{ind}</Text>
                {industry === ind && <Ionicons name="checkmark" size={18} color="#C9A962" />}
              </TouchableOpacity>
            ))}
          </View>
        )}
      </SectionCard>

      <SectionCard>
        <View style={{ flexDirection: 'row', gap: 12 }}>
          <View style={{ flex: 1 }}>
            <Label text="Phone" />
            <TextInput style={s.input} placeholder="(555) 123-4567" placeholderTextColor={colors.textTertiary}
              value={phone} onChangeText={setPhone} keyboardType="phone-pad" data-testid="org-phone-input" />
          </View>
          <View style={{ flex: 1 }}>
            <Label text="Website" />
            <TextInput style={s.input} placeholder="www.example.com" placeholderTextColor={colors.textTertiary}
              value={website} onChangeText={setWebsite} autoCapitalize="none" data-testid="org-website-input" />
          </View>
        </View>
        <View style={{ flexDirection: 'row', gap: 12 }}>
          <View style={{ flex: 2 }}>
            <Label text="City" />
            <TextInput style={s.input} placeholder="City" placeholderTextColor={colors.textTertiary}
              value={city} onChangeText={setCity} data-testid="org-city-input" />
          </View>
          <View style={{ flex: 1 }}>
            <Label text="State" />
            <TextInput style={s.input} placeholder="ST" placeholderTextColor={colors.textTertiary}
              value={stateVal} onChangeText={setStateVal} autoCapitalize="characters" maxLength={2} data-testid="org-state-input" />
          </View>
        </View>
      </SectionCard>

      <BtnRow onBack={() => router.back()} onNext={saveOrg} nextLabel="Create & Continue" nextDisabled={!orgName.trim()} />
    </View>
  );

  // ---- RENDER: Step 2 ----
  const renderStep2 = () => (
    <View>
      <StepHeader title="Branding" desc={`Upload logo and set brand colors for ${storeName || orgName}.`} />

      <SectionCard>
        <Label text="Logo" />
        <TouchableOpacity style={s.logoBox} onPress={uploadLogo} data-testid="upload-logo-btn">
          {logoUploading ? <ActivityIndicator size="large" color="#C9A962" /> :
           logoUrl ? <Image source={{ uri: logoUrl }} style={{ width: 120, height: 120, borderRadius: 16 }} resizeMode="contain" /> :
           <View style={{ alignItems: 'center' }}>
             <View style={s.uploadIconCircle}>
               <Ionicons name="cloud-upload-outline" size={28} color="#C9A962" />
             </View>
             <Text style={{ color: colors.textSecondary, marginTop: 10, fontSize: 14, fontWeight: '500' }}>Tap to upload logo</Text>
             <Text style={{ color: colors.textTertiary, fontSize: 12, marginTop: 2 }}>PNG, JPG up to 5MB</Text>
           </View>}
        </TouchableOpacity>
      </SectionCard>

      <SectionCard>
        <Label text="Brand Color" />
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginBottom: 16 }}>
          {BRAND_COLORS.map(c => (
            <TouchableOpacity key={c} onPress={() => setPrimaryColor(c)} data-testid={`color-${c}`}
              style={[s.colorSwatch, { backgroundColor: c }, primaryColor === c && s.colorSwatchActive]}>
              {primaryColor === c && <Ionicons name="checkmark" size={18} color="#FFF" />}
            </TouchableOpacity>
          ))}
        </View>
      </SectionCard>

      <SectionCard>
        <Label text="Custom Email Footer" />
        <TextInput style={s.input} placeholder="e.g., Powered by Rev1 Auto Group" placeholderTextColor={colors.textTertiary}
          value={emailFooter} onChangeText={setEmailFooter} data-testid="email-footer-input" />
      </SectionCard>

      <BtnRow onBack={() => go(1)} onSkip={skip} onNext={saveBranding} />
    </View>
  );

  // ---- RENDER: Step 3 ----
  const renderStep3 = () => (
    <View>
      <StepHeader title="Create User" desc={`Set up the primary user account for ${storeName || orgName}.`} />

      <SectionCard>
        <View style={{ flexDirection: 'row', gap: 12 }}>
          <View style={{ flex: 1 }}>
            <Label text="First Name" required />
            <TextInput style={s.input} placeholder="Todd" placeholderTextColor={colors.textTertiary}
              value={firstName} onChangeText={setFirstName} data-testid="user-first-name" />
          </View>
          <View style={{ flex: 1 }}>
            <Label text="Last Name" />
            <TextInput style={s.input} placeholder="Berry" placeholderTextColor={colors.textTertiary}
              value={lastName} onChangeText={setLastName} data-testid="user-last-name" />
          </View>
        </View>

        <Label text="Email (login)" required />
        <TextInput style={s.input} placeholder="todd@rev1.com" placeholderTextColor={colors.textTertiary}
          value={userEmail} onChangeText={setUserEmail} keyboardType="email-address" autoCapitalize="none" data-testid="user-email-input" />

        <Label text="Phone" />
        <TextInput style={s.input} placeholder="555-123-4567" placeholderTextColor={colors.textTertiary}
          value={userPhone} onChangeText={setUserPhone} keyboardType="phone-pad" data-testid="user-phone-input" />
      </SectionCard>

      <SectionCard>
        <Label text="Role" />
        <View style={{ flexDirection: 'row', gap: 8, marginBottom: 16 }}>
          {['user', 'manager', 'admin'].map(r => (
            <TouchableOpacity key={r} onPress={() => setUserRole(r)}
              style={[s.chip, userRole === r && s.chipActive]} data-testid={`role-chip-${r}`}>
              <Ionicons name={r === 'admin' ? 'shield' : r === 'manager' ? 'people' : 'person'} size={14} color={userRole === r ? '#000' : colors.textSecondary} />
              <Text style={[s.chipText, userRole === r && s.chipTextActive]}>{r.charAt(0).toUpperCase() + r.slice(1)}</Text>
            </TouchableOpacity>
          ))}
        </View>

        <Label text="Temporary Password" />
        <View style={[s.input, { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.bg }]}>
          <Ionicons name="key" size={18} color="#C9A962" style={{ marginRight: 8 }} />
          <Text style={{ flex: 1, fontSize: 16, color: colors.text, fontFamily: Platform.OS === 'web' ? 'monospace' : undefined, letterSpacing: 1 }}>{tempPassword}</Text>
          <TouchableOpacity onPress={() => { if (Platform.OS === 'web') navigator.clipboard?.writeText(tempPassword); }} data-testid="copy-password-btn">
            <Ionicons name="copy-outline" size={20} color="#007AFF" />
          </TouchableOpacity>
        </View>
      </SectionCard>

      <BtnRow onBack={() => go(2)} onNext={createUser} nextLabel="Create User" nextDisabled={!firstName.trim() || !userEmail.trim()} />
    </View>
  );

  // ---- RENDER: Step 4 ----
  const renderStep4 = () => (
    <View>
      <StepHeader title="User Profile" desc={`Set up ${firstName}'s profile for their digital card.`} />

      <SectionCard style={{ alignItems: 'center' }}>
        <TouchableOpacity onPress={uploadPhoto} activeOpacity={0.7} data-testid="upload-photo-btn">
          {userPhoto ? (
            <Image source={{ uri: userPhoto }} style={{ width: 110, height: 110, borderRadius: 55, borderWidth: 3, borderColor: primaryColor }} />
          ) : (
            <View style={[s.photoPlaceholder, { borderColor: primaryColor + '60' }]}>
              {photoUploading ? <ActivityIndicator color={primaryColor} /> : <Ionicons name="camera" size={36} color={colors.textTertiary} />}
            </View>
          )}
        </TouchableOpacity>
        <TouchableOpacity onPress={uploadPhoto} style={{ marginTop: 8 }}>
          <Text style={{ fontSize: 14, color: '#007AFF', fontWeight: '600' }}>{userPhoto ? 'Change Photo' : 'Upload Headshot'}</Text>
        </TouchableOpacity>
      </SectionCard>

      <SectionCard>
        <Label text="Job Title" />
        <TextInput style={s.input} placeholder="e.g., Sales Manager" placeholderTextColor={colors.textTertiary}
          value={userTitle} onChangeText={setUserTitle} data-testid="user-title-input" />

        <Label text="Bio" />
        <TextInput style={[s.input, { minHeight: 80, textAlignVertical: 'top' }]} placeholder="Short bio for their digital card..."
          placeholderTextColor={colors.textTertiary} value={userBio} onChangeText={setUserBio} multiline data-testid="user-bio-input" />
      </SectionCard>

      <SectionCard>
        <Label text="Social Links (optional)" />
        <View style={{ gap: 10 }}>
          {[
            { icon: 'logo-instagram', color: '#E1306C', val: socialIG, set: setSocialIG, ph: 'Instagram handle', tid: 'social-ig' },
            { icon: 'logo-facebook', color: '#1877F2', val: socialFB, set: setSocialFB, ph: 'Facebook URL', tid: 'social-fb' },
            { icon: 'logo-linkedin', color: '#0A66C2', val: socialLI, set: setSocialLI, ph: 'LinkedIn URL', tid: 'social-li' },
          ].map(soc => (
            <View key={soc.tid} style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <View style={[s.socialIconBox, { backgroundColor: soc.color + '18' }]}>
                <Ionicons name={soc.icon as any} size={18} color={soc.color} />
              </View>
              <TextInput style={[s.input, { flex: 1, marginBottom: 0 }]} placeholder={soc.ph} placeholderTextColor={colors.textTertiary}
                value={soc.val} onChangeText={soc.set} autoCapitalize="none" data-testid={soc.tid} />
            </View>
          ))}
        </View>
      </SectionCard>

      <BtnRow onBack={() => go(3)} onSkip={skip} onNext={saveProfile} />
    </View>
  );

  // ---- RENDER: Step 5 ----
  const renderStep5 = () => (
    <View>
      <StepHeader title="Review Links" desc={`Add review platform links so ${firstName || 'the user'} can send review requests.`} />

      <SectionCard>
        {[
          { label: 'Google Reviews', value: googleReview, set: setGoogleReview, icon: 'logo-google', color: '#4285F4', tid: 'review-google' },
          { label: 'Facebook', value: facebookReview, set: setFacebookReview, icon: 'logo-facebook', color: '#1877F2', tid: 'review-facebook' },
          { label: 'Yelp', value: yelpReview, set: setYelpReview, icon: 'star', color: '#D32323', tid: 'review-yelp' },
          { label: 'DealerRater', value: dealerraterReview, set: setDealerraterReview, icon: 'car-sport', color: '#ED8B00', tid: 'review-dealerrater' },
        ].map(r => (
          <View key={r.tid} style={{ marginBottom: 12 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <View style={[s.socialIconBox, { backgroundColor: r.color + '18' }]}>
                <Ionicons name={r.icon as any} size={16} color={r.color} />
              </View>
              <Text style={[s.label, { marginBottom: 0, marginTop: 0 }]}>{r.label}</Text>
            </View>
            <TextInput style={s.input} placeholder={`Paste ${r.label} URL`} placeholderTextColor={colors.textTertiary}
              value={r.value} onChangeText={r.set} autoCapitalize="none" data-testid={r.tid} />
          </View>
        ))}
      </SectionCard>

      <SectionCard>
        <Label text="Custom Review Link" />
        <View style={{ flexDirection: 'row', gap: 8 }}>
          <TextInput style={[s.input, { flex: 1 }]} placeholder="Name (e.g., Edmunds)" placeholderTextColor={colors.textTertiary}
            value={customReviewName} onChangeText={setCustomReviewName} data-testid="custom-review-name" />
          <TextInput style={[s.input, { flex: 2 }]} placeholder="URL" placeholderTextColor={colors.textTertiary}
            value={customReviewUrl} onChangeText={setCustomReviewUrl} autoCapitalize="none" data-testid="custom-review-url" />
        </View>
      </SectionCard>

      <BtnRow onBack={() => go(4)} onSkip={skip} onNext={saveReviews} />
    </View>
  );

  // ---- RENDER: Step 6 ----
  const renderStep6 = () => (
    <View>
      <StepHeader title="Message Templates" desc={`Pre-load message templates for ${firstName || 'the user'}. Toggle off any you don't want.`} />

      <SectionCard>
        {templates.map((t, i) => (
          <TouchableOpacity key={i} onPress={() => {
            const u = [...templates]; u[i] = { ...u[i], enabled: !u[i].enabled }; setTemplates(u);
          }} style={[s.templateCard, !t.enabled && { opacity: 0.4 }]} data-testid={`template-${i}`}>
            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, flex: 1 }}>
                <Ionicons name="document-text" size={16} color={t.enabled ? '#C9A962' : colors.textTertiary} />
                <Text style={{ fontSize: 15, fontWeight: '600', color: colors.text }}>{t.name}</Text>
              </View>
              <Ionicons name={t.enabled ? 'checkmark-circle' : 'ellipse-outline'} size={24} color={t.enabled ? '#34C759' : colors.textTertiary} />
            </View>
            <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 6, marginLeft: 24 }} numberOfLines={2}>{t.content}</Text>
          </TouchableOpacity>
        ))}
      </SectionCard>

      <SectionCard>
        <Text style={{ fontSize: 14, fontWeight: '600', color: colors.text, marginBottom: 10 }}>Add Custom Template</Text>
        <TextInput style={s.input} placeholder="Template name" placeholderTextColor={colors.textTertiary}
          value={newTemplateName} onChangeText={setNewTemplateName} data-testid="new-template-name" />
        <TextInput style={[s.input, { minHeight: 60, textAlignVertical: 'top' }]} placeholder="Message content (use {name} for contact name)"
          placeholderTextColor={colors.textTertiary} value={newTemplateContent} onChangeText={setNewTemplateContent} multiline data-testid="new-template-content" />
        <TouchableOpacity style={[s.btnSmall, (!newTemplateName.trim() || !newTemplateContent.trim()) && s.btnDisabled]}
          onPress={addTemplate} disabled={!newTemplateName.trim() || !newTemplateContent.trim()} data-testid="add-template-btn">
          <Ionicons name="add" size={16} color="#000" />
          <Text style={{ fontSize: 13, fontWeight: '600', color: '#000' }}>Add Template</Text>
        </TouchableOpacity>
      </SectionCard>

      <BtnRow onBack={() => go(5)} onSkip={skip} onNext={saveTemplates} nextLabel="Save Templates" />
    </View>
  );

  // ---- RENDER: Step 7 ----
  const renderStep7 = () => (
    <View>
      <StepHeader title="Tags" desc="Set up contact tags for organizing customers." />

      <SectionCard>
        {existingTags.length > 0 && (
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 16 }}>
            {existingTags.map(tag => {
              const active = selectedTags.includes(tag.name);
              return (
                <TouchableOpacity key={tag._id || tag.name} onPress={() => {
                  setSelectedTags(active ? selectedTags.filter(t => t !== tag.name) : [...selectedTags, tag.name]);
                }} style={[s.chip, active && { backgroundColor: tag.color || '#C9A962', borderColor: tag.color || '#C9A962' }]} data-testid={`tag-chip-${tag.name}`}>
                  <Text style={[s.chipText, active && { color: '#FFF' }]}>{tag.name}</Text>
                </TouchableOpacity>
              );
            })}
          </View>
        )}

        <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}>
          <TextInput style={[s.input, { flex: 1, marginBottom: 0 }]} placeholder="Create new tag..." placeholderTextColor={colors.textTertiary}
            value={newTagName} onChangeText={setNewTagName} data-testid="new-tag-input" />
          <TouchableOpacity style={[s.btnSmall, !newTagName.trim() && s.btnDisabled]} onPress={addNewTag} disabled={!newTagName.trim()} data-testid="add-tag-btn">
            <Ionicons name="add" size={16} color="#000" />
            <Text style={{ fontSize: 13, fontWeight: '600', color: '#000' }}>Create</Text>
          </TouchableOpacity>
        </View>
      </SectionCard>

      <BtnRow onBack={() => go(6)} onSkip={skip} onNext={() => go(8)} />
    </View>
  );

  // ---- RENDER: Step 8 (Handoff) ----
  const renderStep8 = () => {
    const items = getHandoffItems();
    const doneCount = items.filter(i => i.done).length;
    const userTodos = items.filter(i => i.userAction);
    return (
      <View>
        <StepHeader title="Setup Complete!" desc={`${doneCount}/${items.length} items configured for ${firstName} ${lastName} at ${storeName || orgName}.`} />

        {/* Summary Card */}
        <View style={[s.summaryCard, { borderColor: primaryColor }]} data-testid="handoff-summary-card">
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 14, marginBottom: 16 }}>
            {userPhoto ? <Image source={{ uri: userPhoto }} style={{ width: 56, height: 56, borderRadius: 28, borderWidth: 3, borderColor: primaryColor }} /> :
             <View style={{ width: 56, height: 56, borderRadius: 28, backgroundColor: primaryColor + '25', alignItems: 'center', justifyContent: 'center' }}>
               <Text style={{ fontSize: 20, fontWeight: '800', color: primaryColor }}>{firstName?.[0]}{lastName?.[0]}</Text>
             </View>}
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 18, fontWeight: '700', color: colors.text }}>{firstName} {lastName}</Text>
              <Text style={{ fontSize: 14, color: colors.textSecondary }}>{userTitle || userRole} at {storeName || orgName}</Text>
              <Text style={{ fontSize: 13, color: colors.textTertiary, marginTop: 2 }}>{userEmail}</Text>
            </View>
          </View>
          <TouchableOpacity style={s.copyLoginBtn} onPress={() => {
            const creds = `Email: ${userEmail}\nPassword: ${tempPassword}`;
            if (Platform.OS === 'web') { navigator.clipboard?.writeText(creds); alert('Login credentials copied!'); }
          }} data-testid="copy-login-btn">
            <Ionicons name="copy-outline" size={16} color="#000" />
            <Text style={{ fontSize: 14, fontWeight: '700', color: '#000' }}>Copy Login Credentials</Text>
          </TouchableOpacity>
        </View>

        {/* Configuration Status */}
        <SectionCard>
          <Text style={[s.label, { fontSize: 14, marginBottom: 10 }]}>Configuration Status</Text>
          {items.map((item, i) => (
            <View key={i} style={s.checklistRow} data-testid={`checklist-item-${i}`}>
              <Ionicons name={item.done ? 'checkmark-circle' : 'ellipse-outline'} size={22}
                color={item.done ? '#34C759' : '#FF9500'} />
              <Text style={{ flex: 1, fontSize: 14, color: item.done ? colors.text : colors.textSecondary, fontWeight: item.done ? '500' : '400' }}>{item.label}</Text>
            </View>
          ))}
        </SectionCard>

        {/* User Handoff Checklist */}
        {userTodos.length > 0 && (
          <SectionCard style={{ borderColor: '#FF9500', borderWidth: 1 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <Ionicons name="alert-circle" size={20} color="#FF9500" />
              <Text style={{ fontSize: 14, fontWeight: '700', color: '#FF9500' }}>User Needs To Complete</Text>
            </View>
            {userTodos.map((item, i) => (
              <View key={i} style={{ flexDirection: 'row', alignItems: 'flex-start', paddingVertical: 6, gap: 10 }}>
                <View style={s.todoCheckbox} />
                <Text style={{ flex: 1, fontSize: 14, color: colors.text, lineHeight: 20 }}>{item.userAction}</Text>
              </View>
            ))}
          </SectionCard>
        )}

        <View style={s.btnRow}>
          <TouchableOpacity style={s.btnSecondary} onPress={() => go(7)} data-testid="handoff-back-btn">
            <Ionicons name="arrow-back" size={18} color={colors.textSecondary} />
            <Text style={s.btnSecondaryText}>Back</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[s.btnPrimary, { flex: 1 }]} onPress={() => router.push('/admin' as any)} data-testid="wizard-done-btn">
            <Ionicons name="checkmark-circle" size={20} color="#000" />
            <Text style={s.btnPrimaryText}>Finish Setup</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  };

  if (loading) return (
    <SafeAreaView style={[s.container, { justifyContent: 'center', alignItems: 'center' }]}>
      <ActivityIndicator size="large" color="#C9A962" />
      <Text style={{ color: colors.textSecondary, marginTop: 12, fontSize: 14 }}>Loading wizard...</Text>
    </SafeAreaView>
  );

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        <View style={s.header}>
          <TouchableOpacity onPress={() => router.back()} style={s.headerCloseBtn} data-testid="wizard-close-btn">
            <Ionicons name="close" size={20} color={colors.text} />
          </TouchableOpacity>
          <View style={{ alignItems: 'center' }}>
            <Text style={s.headerTitle}>Onboard Account</Text>
            <Text style={s.headerSubtitle}>Step {step} of {STEPS.length}</Text>
          </View>
          <View style={{ width: 36 }} />
        </View>
        {renderStepBar()}
        <ScrollView ref={scrollRef} contentContainerStyle={s.content} showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled">
          <Animated.View style={{ opacity: fadeAnim }}>
            {step === 1 && renderStep1()}
            {step === 2 && renderStep2()}
            {step === 3 && renderStep3()}
            {step === 4 && renderStep4()}
            {step === 5 && renderStep5()}
            {step === 6 && renderStep6()}
            {step === 7 && renderStep7()}
            {step === 8 && renderStep8()}
          </Animated.View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const getS = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.border },
  headerCloseBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center' },
  headerTitle: { fontSize: 17, fontWeight: '700', color: colors.text },
  headerSubtitle: { fontSize: 12, color: colors.textTertiary, marginTop: 1 },
  stepBarContainer: { borderBottomWidth: 1, borderBottomColor: colors.border, paddingBottom: 0 },
  stepBar: { flexDirection: 'row', paddingHorizontal: 12, paddingTop: 10, paddingBottom: 8, gap: 2 },
  stepDot: { alignItems: 'center', width: 60 },
  dot: { width: 30, height: 30, borderRadius: 15, borderWidth: 2, borderColor: colors.border, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.card },
  dotDone: { backgroundColor: '#34C759', borderColor: '#34C759' },
  dotActive: { backgroundColor: '#C9A962', borderColor: '#C9A962' },
  dotSkipped: { backgroundColor: '#FF950020', borderColor: '#FF9500' },
  dotText: { fontSize: 12, fontWeight: '700', color: colors.textTertiary },
  stepLabel: { fontSize: 10, color: colors.textTertiary, marginTop: 4, textAlign: 'center', fontWeight: '500' },
  stepLabelActive: { color: '#C9A962', fontWeight: '700' },
  stepLabelDone: { color: '#34C759' },
  progressTrack: { height: 3, backgroundColor: colors.border, marginHorizontal: 16, borderRadius: 2 },
  progressFill: { height: 3, backgroundColor: '#C9A962', borderRadius: 2 },
  content: { padding: 20, paddingBottom: 80, maxWidth: 700, alignSelf: 'center', width: '100%' },
  sectionCard: { backgroundColor: colors.card, borderRadius: 14, padding: 18, marginBottom: 16, borderWidth: 1, borderColor: colors.border },
  stepNumBadge: { width: 28, height: 28, borderRadius: 8, backgroundColor: '#C9A962', alignItems: 'center', justifyContent: 'center' },
  stepNumBadgeText: { fontSize: 14, fontWeight: '800', color: '#000' },
  stepTitle: { fontSize: 22, fontWeight: '800', color: colors.text },
  stepDesc: { fontSize: 14, color: colors.textSecondary, lineHeight: 20, marginLeft: 38 },
  label: { fontSize: 13, fontWeight: '600', color: colors.textSecondary, marginBottom: 6, marginTop: 6 },
  input: { backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.border, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 12, fontSize: 16, color: colors.text, marginBottom: 12 },
  chip: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 14, paddingVertical: 9, borderRadius: 20, borderWidth: 1.5, borderColor: colors.border, backgroundColor: colors.card, marginRight: 8 },
  chipActive: { backgroundColor: '#C9A962', borderColor: '#C9A962' },
  chipText: { fontSize: 13, fontWeight: '600', color: colors.text },
  chipTextActive: { color: '#000' },
  pickerDropdown: { backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: colors.border, marginBottom: 12, overflow: 'hidden' },
  pickerItem: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 14, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.border },
  pickerItemActive: { backgroundColor: '#C9A96215' },
  pickerItemText: { fontSize: 15, color: colors.text },
  pickerItemTextActive: { color: '#C9A962', fontWeight: '600' },
  logoBox: { width: '100%', height: 160, borderRadius: 14, borderWidth: 2, borderColor: colors.border, borderStyle: 'dashed', alignItems: 'center', justifyContent: 'center', marginBottom: 8, backgroundColor: colors.bg },
  uploadIconCircle: { width: 52, height: 52, borderRadius: 26, backgroundColor: '#C9A96218', alignItems: 'center', justifyContent: 'center' },
  colorSwatch: { width: 40, height: 40, borderRadius: 10, alignItems: 'center', justifyContent: 'center', borderWidth: 0 },
  colorSwatchActive: { borderWidth: 3, borderColor: '#FFF', transform: [{ scale: 1.1 }] },
  photoPlaceholder: { width: 110, height: 110, borderRadius: 55, backgroundColor: colors.card, borderWidth: 2, alignItems: 'center', justifyContent: 'center' },
  socialIconBox: { width: 32, height: 32, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  templateCard: { padding: 12, borderRadius: 10, borderWidth: 1, borderColor: colors.border, marginBottom: 8, backgroundColor: colors.bg },
  summaryCard: { padding: 20, backgroundColor: colors.card, borderRadius: 16, borderWidth: 2, marginBottom: 16 },
  copyLoginBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#C9A962', paddingVertical: 12, borderRadius: 10 },
  checklistRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: colors.border },
  todoCheckbox: { width: 20, height: 20, borderRadius: 4, borderWidth: 2, borderColor: '#FF9500', marginTop: 1 },
  btnRow: { flexDirection: 'row', gap: 10, marginTop: 16, marginBottom: 20 },
  btnPrimary: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#C9A962', paddingVertical: 14, paddingHorizontal: 24, borderRadius: 12 },
  btnPrimaryText: { fontSize: 16, fontWeight: '700', color: '#000' },
  btnSecondary: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 14, paddingHorizontal: 18, borderRadius: 12, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.card },
  btnSecondaryText: { fontSize: 15, fontWeight: '600', color: colors.textSecondary },
  btnSkip: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingVertical: 14, paddingHorizontal: 14 },
  btnSkipText: { fontSize: 15, color: '#FF9500', fontWeight: '600' },
  btnDisabled: { opacity: 0.4 },
  btnSmall: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 16, paddingVertical: 10, borderRadius: 10, backgroundColor: '#C9A962' },
});
