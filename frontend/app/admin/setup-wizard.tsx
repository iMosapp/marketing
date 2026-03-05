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
  { name: 'Welcome', content: 'Hi {name}! Welcome to the family. I\'m {user_name} and I\'ll be taking care of you. Let me know if you need anything!', category: 'greeting' },
  { name: 'Follow Up', content: 'Hey {name}, just checking in! How\'s everything going? Let me know if I can help with anything.', category: 'follow_up' },
  { name: 'Review Request', content: 'Hi {name}! It was great working with you. If you have a moment, I\'d love a quick review: {review_link}', category: 'review' },
  { name: 'Referral Ask', content: 'Hi {name}! If you know anyone who could benefit from our services, I\'d really appreciate the referral!', category: 'referral' },
  { name: 'Birthday', content: 'Happy Birthday, {name}! Hope you have an amazing day!', category: 'celebration' },
  { name: 'Anniversary', content: 'Happy anniversary, {name}! Can you believe it\'s been {years} year(s)? Thanks for being with us!', category: 'celebration' },
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

  // Step 1: Organization
  const [orgId, setOrgId] = useState('');
  const [storeId, setStoreId] = useState('');
  const [orgName, setOrgName] = useState('');
  const [storeName, setStoreName] = useState('');
  const [phone, setPhone] = useState('');
  const [address, setAddress] = useState('');
  const [city, setCity] = useState('');
  const [state, setState] = useState('');
  const [website, setWebsite] = useState('');
  const [industry, setIndustry] = useState('');
  const [isNewOrg, setIsNewOrg] = useState(true);
  const [isNewStore, setIsNewStore] = useState(true);

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
      // Load tags
      if (user?._id) {
        const tagsRes = await api.get(`/tags/${user._id}`).catch(() => ({ data: [] }));
        setExistingTags(Array.isArray(tagsRes.data) ? tagsRes.data : []);
      }
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const go = (next: number) => {
    Animated.sequence([
      Animated.timing(fadeAnim, { toValue: 0, duration: 100, useNativeDriver: true }),
      Animated.timing(fadeAnim, { toValue: 1, duration: 150, useNativeDriver: true }),
    ]).start();
    setTimeout(() => { setStep(next); scrollRef.current?.scrollTo({ y: 0, animated: false }); }, 100);
  };

  const skip = () => { setSkipped(prev => new Set(prev).add(step)); go(step + 1); };

  // ─── STEP 1: Save Org/Store ───
  const saveOrg = async () => {
    if (!orgName.trim()) { alert('Enter an organization name'); return; }
    setSaving(true);
    try {
      let oid = orgId;
      if (isNewOrg || !oid) {
        const res = await api.post('/admin/organizations', {
          name: orgName, admin_email: currentUser?.email || '', admin_phone: phone,
          address, city, state, account_type: 'organization',
        });
        oid = res.data._id || res.data.id;
        setOrgId(oid); setIsNewOrg(false);
      } else {
        await api.put(`/admin/organizations/${oid}`, { name: orgName, admin_phone: phone, address, city, state });
      }
      let sid = storeId;
      if (isNewStore || !sid) {
        const res = await api.post('/admin/stores', {
          organization_id: oid, name: storeName || orgName,
          phone, address, city, state, website, industry,
        });
        sid = res.data._id || res.data.id;
        setStoreId(sid); setIsNewStore(false);
      } else {
        await api.put(`/admin/stores/${sid}`, { name: storeName || orgName, phone, address, city, state, website, industry });
      }
      go(2);
    } catch (e: any) { alert(e.response?.data?.detail || 'Error saving'); }
    finally { setSaving(false); }
  };

  // ─── STEP 2: Save Branding ───
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

  // ─── STEP 3: Create User ───
  const createUser = async () => {
    if (!firstName.trim() || !userEmail.trim()) { alert('First name and email required'); return; }
    setSaving(true);
    try {
      const res = await api.post('/admin/users', {
        first_name: firstName, last_name: lastName,
        email: userEmail, phone: userPhone,
        password: tempPassword, role: userRole,
        store_id: storeId, org_id: orgId,
      });
      const uid = res.data._id || res.data.id;
      setCreatedUserId(uid);
      go(4);
    } catch (e: any) { alert(e.response?.data?.detail || 'Error creating user'); }
    finally { setSaving(false); }
  };

  // ─── STEP 4: Save Profile ───
  const uploadPhoto = async () => {
    if (Platform.OS !== 'web') return;
    const input = document.createElement('input');
    input.type = 'file'; input.accept = 'image/*';
    input.onchange = async (e: any) => {
      const file = e.target.files[0]; if (!file) return;
      setPhotoUploading(true);
      try {
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
        if (userPhoto) profileData.photo = userPhoto;
        await api.put(`/admin/users/${createdUserId}`, profileData);
      }
      go(5);
    } catch (e: any) { alert(e.response?.data?.detail || 'Error saving profile'); }
    finally { setSaving(false); }
  };

  // ─── STEP 5: Save Review Links ───
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

  // ─── STEP 6: Save Templates ───
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

  // ─── STEP 7: Save Tags ───
  const addNewTag = async () => {
    if (!newTagName.trim()) return;
    const uid = createdUserId || currentUser?._id;
    try {
      await api.post(`/tags/${uid}`, { name: newTagName, color: '#C9A962', icon: 'pricetag' });
      setSelectedTags([...selectedTags, newTagName]);
      setNewTagName('');
      // Refresh tags
      const res = await api.get(`/tags/${uid}`).catch(() => ({ data: [] }));
      setExistingTags(Array.isArray(res.data) ? res.data : []);
    } catch (e: any) { alert(e.response?.data?.detail || 'Error creating tag'); }
  };

  // ─── Build Handoff Checklist ───
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

  // ─── RENDER ───
  const renderStepBar = () => (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.stepBar}>
      {STEPS.map((st, i) => {
        const active = step === st.num;
        const done = step > st.num && !skipped.has(st.num);
        const wasSkipped = skipped.has(st.num);
        return (
          <TouchableOpacity key={st.num} style={s.stepDot} onPress={() => st.num < step && go(st.num)}>
            <View style={[s.dot, done && s.dotDone, active && s.dotActive, wasSkipped && { backgroundColor: '#FF950030', borderColor: '#FF9500' }]}>
              {done ? <Ionicons name="checkmark" size={14} color="#FFF" /> :
               wasSkipped ? <Ionicons name="arrow-forward" size={12} color="#FF9500" /> :
               <Text style={[s.dotText, active && s.dotTextActive]}>{st.num}</Text>}
            </View>
            <Text style={[s.stepLabel, active && s.stepLabelActive]} numberOfLines={1}>{st.title}</Text>
          </TouchableOpacity>
        );
      })}
    </ScrollView>
  );

  const renderStep1 = () => (
    <View>
      <Text style={s.stepTitle}>Organization & Store</Text>
      <Text style={s.stepDesc}>Create or select the organization and store account.</Text>

      {existingOrgs.length > 0 && (
        <View style={{ marginBottom: 16 }}>
          <Text style={s.label}>Existing Organizations</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 8 }}>
            {existingOrgs.map(o => (
              <TouchableOpacity key={o._id} onPress={() => { setOrgId(o._id); setOrgName(o.name); setIsNewOrg(false); }}
                style={[s.chip, orgId === o._id && s.chipActive]}>
                <Text style={[s.chipText, orgId === o._id && s.chipTextActive]}>{o.name}</Text>
              </TouchableOpacity>
            ))}
            <TouchableOpacity onPress={() => { setOrgId(''); setOrgName(''); setIsNewOrg(true); }}
              style={[s.chip, isNewOrg && s.chipActive]}>
              <Ionicons name="add" size={16} color={isNewOrg ? '#FFF' : colors.text} />
              <Text style={[s.chipText, isNewOrg && s.chipTextActive]}>New</Text>
            </TouchableOpacity>
          </ScrollView>
        </View>
      )}

      <Text style={s.label}>Organization Name *</Text>
      <TextInput style={s.input} placeholder="e.g., RevRev1" placeholderTextColor={colors.textTertiary}
        value={orgName} onChangeText={setOrgName} />

      <Text style={s.label}>Store / Account Name</Text>
      <TextInput style={s.input} placeholder="e.g., Rev1 (defaults to org name)" placeholderTextColor={colors.textTertiary}
        value={storeName} onChangeText={setStoreName} />

      <View style={{ flexDirection: 'row', gap: 12 }}>
        <View style={{ flex: 1 }}>
          <Text style={s.label}>Phone</Text>
          <TextInput style={s.input} placeholder="Store phone" placeholderTextColor={colors.textTertiary}
            value={phone} onChangeText={setPhone} keyboardType="phone-pad" />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={s.label}>Website</Text>
          <TextInput style={s.input} placeholder="www.example.com" placeholderTextColor={colors.textTertiary}
            value={website} onChangeText={setWebsite} autoCapitalize="none" />
        </View>
      </View>

      <View style={{ flexDirection: 'row', gap: 12 }}>
        <View style={{ flex: 2 }}>
          <Text style={s.label}>City</Text>
          <TextInput style={s.input} placeholder="City" placeholderTextColor={colors.textTertiary}
            value={city} onChangeText={setCity} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={s.label}>State</Text>
          <TextInput style={s.input} placeholder="ST" placeholderTextColor={colors.textTertiary}
            value={state} onChangeText={setState} autoCapitalize="characters" maxLength={2} />
        </View>
      </View>

      <View style={s.btnRow}>
        <TouchableOpacity style={s.btnSecondary} onPress={() => router.back()}>
          <Text style={s.btnSecondaryText}>Cancel</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[s.btnPrimary, !orgName.trim() && s.btnDisabled]} onPress={saveOrg} disabled={saving || !orgName.trim()}>
          {saving ? <ActivityIndicator size="small" color="#000" /> : <Text style={s.btnPrimaryText}>Next</Text>}
        </TouchableOpacity>
      </View>
    </View>
  );

  const renderStep2 = () => (
    <View>
      <Text style={s.stepTitle}>Branding</Text>
      <Text style={s.stepDesc}>Upload logo and set brand colors for {storeName || orgName}.</Text>

      <Text style={s.label}>Logo</Text>
      <TouchableOpacity style={s.logoBox} onPress={uploadLogo} data-testid="upload-logo-btn">
        {logoUploading ? <ActivityIndicator size="large" color="#C9A962" /> :
         logoUrl ? <Image source={{ uri: logoUrl }} style={{ width: 120, height: 120, borderRadius: 16 }} resizeMode="contain" /> :
         <View style={{ alignItems: 'center' }}>
           <Ionicons name="cloud-upload-outline" size={40} color={colors.textTertiary} />
           <Text style={{ color: colors.textTertiary, marginTop: 8, fontSize: 14 }}>Tap to upload logo</Text>
         </View>}
      </TouchableOpacity>

      <Text style={s.label}>Brand Color</Text>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginBottom: 16 }}>
        {BRAND_COLORS.map(c => (
          <TouchableOpacity key={c} onPress={() => setPrimaryColor(c)}
            style={{ width: 40, height: 40, borderRadius: 10, backgroundColor: c,
              borderWidth: primaryColor === c ? 3 : 0, borderColor: '#FFF' }} />
        ))}
      </View>

      <Text style={s.label}>Custom Email Footer (optional)</Text>
      <TextInput style={s.input} placeholder="e.g., Powered by Rev1 Auto Group" placeholderTextColor={colors.textTertiary}
        value={emailFooter} onChangeText={setEmailFooter} />

      <View style={s.btnRow}>
        <TouchableOpacity style={s.btnSecondary} onPress={() => go(1)}><Text style={s.btnSecondaryText}>Back</Text></TouchableOpacity>
        <TouchableOpacity style={s.btnSkip} onPress={skip}><Text style={s.btnSkipText}>Skip</Text></TouchableOpacity>
        <TouchableOpacity style={s.btnPrimary} onPress={saveBranding} disabled={saving}>
          {saving ? <ActivityIndicator size="small" color="#000" /> : <Text style={s.btnPrimaryText}>Next</Text>}
        </TouchableOpacity>
      </View>
    </View>
  );

  const renderStep3 = () => (
    <View>
      <Text style={s.stepTitle}>Create User</Text>
      <Text style={s.stepDesc}>Set up the user account for {storeName || orgName}.</Text>

      <View style={{ flexDirection: 'row', gap: 12 }}>
        <View style={{ flex: 1 }}>
          <Text style={s.label}>First Name *</Text>
          <TextInput style={s.input} placeholder="Todd" placeholderTextColor={colors.textTertiary}
            value={firstName} onChangeText={setFirstName} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={s.label}>Last Name</Text>
          <TextInput style={s.input} placeholder="Berry" placeholderTextColor={colors.textTertiary}
            value={lastName} onChangeText={setLastName} />
        </View>
      </View>

      <Text style={s.label}>Email * (login)</Text>
      <TextInput style={s.input} placeholder="todd@rev1.com" placeholderTextColor={colors.textTertiary}
        value={userEmail} onChangeText={setUserEmail} keyboardType="email-address" autoCapitalize="none" />

      <Text style={s.label}>Phone</Text>
      <TextInput style={s.input} placeholder="555-123-4567" placeholderTextColor={colors.textTertiary}
        value={userPhone} onChangeText={setUserPhone} keyboardType="phone-pad" />

      <Text style={s.label}>Role</Text>
      <View style={{ flexDirection: 'row', gap: 8, marginBottom: 16 }}>
        {['user', 'manager', 'admin'].map(r => (
          <TouchableOpacity key={r} onPress={() => setUserRole(r)}
            style={[s.chip, userRole === r && s.chipActive]}>
            <Text style={[s.chipText, userRole === r && s.chipTextActive]}>{r.charAt(0).toUpperCase() + r.slice(1)}</Text>
          </TouchableOpacity>
        ))}
      </View>

      <Text style={s.label}>Temporary Password</Text>
      <View style={[s.input, { flexDirection: 'row', alignItems: 'center' }]}>
        <Text style={{ flex: 1, fontSize: 16, color: colors.text, fontFamily: Platform.OS === 'web' ? 'monospace' : undefined }}>{tempPassword}</Text>
        <TouchableOpacity onPress={() => { if (Platform.OS === 'web') navigator.clipboard?.writeText(tempPassword); }}>
          <Ionicons name="copy-outline" size={20} color="#007AFF" />
        </TouchableOpacity>
      </View>

      <View style={s.btnRow}>
        <TouchableOpacity style={s.btnSecondary} onPress={() => go(2)}><Text style={s.btnSecondaryText}>Back</Text></TouchableOpacity>
        <TouchableOpacity style={[s.btnPrimary, (!firstName.trim() || !userEmail.trim()) && s.btnDisabled]}
          onPress={createUser} disabled={saving || !firstName.trim() || !userEmail.trim()}>
          {saving ? <ActivityIndicator size="small" color="#000" /> : <Text style={s.btnPrimaryText}>Create & Next</Text>}
        </TouchableOpacity>
      </View>
    </View>
  );

  const renderStep4 = () => (
    <View>
      <Text style={s.stepTitle}>User Profile</Text>
      <Text style={s.stepDesc}>Set up {firstName}'s profile — headshot, title, and bio for their digital card.</Text>

      <View style={{ alignItems: 'center', marginBottom: 20 }}>
        <TouchableOpacity onPress={uploadPhoto} activeOpacity={0.7}>
          {userPhoto ? (
            <Image source={{ uri: userPhoto }} style={{ width: 100, height: 100, borderRadius: 50, borderWidth: 3, borderColor: primaryColor }} />
          ) : (
            <View style={{ width: 100, height: 100, borderRadius: 50, backgroundColor: colors.card, borderWidth: 2, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }}>
              {photoUploading ? <ActivityIndicator color={primaryColor} /> : <Ionicons name="camera" size={32} color={colors.textTertiary} />}
            </View>
          )}
        </TouchableOpacity>
        <TouchableOpacity onPress={uploadPhoto} style={{ marginTop: 6 }}>
          <Text style={{ fontSize: 13, color: '#007AFF', fontWeight: '600' }}>{userPhoto ? 'Change Photo' : 'Add Photo'}</Text>
        </TouchableOpacity>
      </View>

      <Text style={s.label}>Title</Text>
      <TextInput style={s.input} placeholder="e.g., Sales Manager" placeholderTextColor={colors.textTertiary}
        value={userTitle} onChangeText={setUserTitle} />

      <Text style={s.label}>Bio</Text>
      <TextInput style={[s.input, { minHeight: 80, textAlignVertical: 'top' }]} placeholder="Short bio for their digital card..."
        placeholderTextColor={colors.textTertiary} value={userBio} onChangeText={setUserBio} multiline />

      <Text style={s.label}>Social Links (optional)</Text>
      <View style={{ gap: 8 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <Ionicons name="logo-instagram" size={20} color="#E1306C" />
          <TextInput style={[s.input, { flex: 1, marginBottom: 0 }]} placeholder="Instagram handle" placeholderTextColor={colors.textTertiary}
            value={socialIG} onChangeText={setSocialIG} autoCapitalize="none" />
        </View>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <Ionicons name="logo-facebook" size={20} color="#1877F2" />
          <TextInput style={[s.input, { flex: 1, marginBottom: 0 }]} placeholder="Facebook URL" placeholderTextColor={colors.textTertiary}
            value={socialFB} onChangeText={setSocialFB} autoCapitalize="none" />
        </View>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <Ionicons name="logo-linkedin" size={20} color="#0A66C2" />
          <TextInput style={[s.input, { flex: 1, marginBottom: 0 }]} placeholder="LinkedIn URL" placeholderTextColor={colors.textTertiary}
            value={socialLI} onChangeText={setSocialLI} autoCapitalize="none" />
        </View>
      </View>

      <View style={[s.btnRow, { marginTop: 20 }]}>
        <TouchableOpacity style={s.btnSecondary} onPress={() => go(3)}><Text style={s.btnSecondaryText}>Back</Text></TouchableOpacity>
        <TouchableOpacity style={s.btnSkip} onPress={skip}><Text style={s.btnSkipText}>Skip</Text></TouchableOpacity>
        <TouchableOpacity style={s.btnPrimary} onPress={saveProfile} disabled={saving}>
          {saving ? <ActivityIndicator size="small" color="#000" /> : <Text style={s.btnPrimaryText}>Next</Text>}
        </TouchableOpacity>
      </View>
    </View>
  );

  const renderStep5 = () => (
    <View>
      <Text style={s.stepTitle}>Review Links</Text>
      <Text style={s.stepDesc}>Add review platform links so {firstName || 'the user'} can send review requests.</Text>

      {[
        { label: 'Google Reviews', value: googleReview, set: setGoogleReview, icon: 'logo-google', color: '#4285F4' },
        { label: 'Facebook', value: facebookReview, set: setFacebookReview, icon: 'logo-facebook', color: '#1877F2' },
        { label: 'Yelp', value: yelpReview, set: setYelpReview, icon: 'star', color: '#D32323' },
        { label: 'DealerRater', value: dealerraterReview, set: setDealerraterReview, icon: 'car-sport', color: '#ED8B00' },
      ].map(r => (
        <View key={r.label}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <Ionicons name={r.icon as any} size={18} color={r.color} />
            <Text style={s.label}>{r.label}</Text>
          </View>
          <TextInput style={s.input} placeholder={`Paste ${r.label} URL`} placeholderTextColor={colors.textTertiary}
            value={r.value} onChangeText={r.set} autoCapitalize="none" />
        </View>
      ))}

      <Text style={[s.label, { marginTop: 8 }]}>Custom Review Link</Text>
      <View style={{ flexDirection: 'row', gap: 8 }}>
        <TextInput style={[s.input, { flex: 1 }]} placeholder="Name (e.g., Edmunds)" placeholderTextColor={colors.textTertiary}
          value={customReviewName} onChangeText={setCustomReviewName} />
        <TextInput style={[s.input, { flex: 2 }]} placeholder="URL" placeholderTextColor={colors.textTertiary}
          value={customReviewUrl} onChangeText={setCustomReviewUrl} autoCapitalize="none" />
      </View>

      <View style={s.btnRow}>
        <TouchableOpacity style={s.btnSecondary} onPress={() => go(4)}><Text style={s.btnSecondaryText}>Back</Text></TouchableOpacity>
        <TouchableOpacity style={s.btnSkip} onPress={skip}><Text style={s.btnSkipText}>Skip</Text></TouchableOpacity>
        <TouchableOpacity style={s.btnPrimary} onPress={saveReviews} disabled={saving}>
          {saving ? <ActivityIndicator size="small" color="#000" /> : <Text style={s.btnPrimaryText}>Next</Text>}
        </TouchableOpacity>
      </View>
    </View>
  );

  const renderStep6 = () => (
    <View>
      <Text style={s.stepTitle}>Message Templates</Text>
      <Text style={s.stepDesc}>Pre-load message templates for {firstName || 'the user'}. Toggle off any you don't want.</Text>

      {templates.map((t, i) => (
        <View key={i} style={[s.templateCard, !t.enabled && { opacity: 0.4 }]}>
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
            <Text style={{ fontSize: 15, fontWeight: '600', color: colors.text }}>{t.name}</Text>
            <TouchableOpacity onPress={() => {
              const u = [...templates]; u[i] = { ...u[i], enabled: !u[i].enabled }; setTemplates(u);
            }}>
              <Ionicons name={t.enabled ? 'checkmark-circle' : 'ellipse-outline'} size={24} color={t.enabled ? '#34C759' : colors.textTertiary} />
            </TouchableOpacity>
          </View>
          <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 4 }} numberOfLines={2}>{t.content}</Text>
        </View>
      ))}

      <View style={{ marginTop: 12, padding: 12, backgroundColor: colors.card, borderRadius: 10, borderWidth: 1, borderColor: colors.border }}>
        <Text style={{ fontSize: 13, fontWeight: '600', color: colors.text, marginBottom: 6 }}>Add Custom Template</Text>
        <TextInput style={[s.input, { marginBottom: 6 }]} placeholder="Template name" placeholderTextColor={colors.textTertiary}
          value={newTemplateName} onChangeText={setNewTemplateName} />
        <TextInput style={[s.input, { minHeight: 50, textAlignVertical: 'top', marginBottom: 6 }]} placeholder="Message content (use {name} for contact name)"
          placeholderTextColor={colors.textTertiary} value={newTemplateContent} onChangeText={setNewTemplateContent} multiline />
        <TouchableOpacity style={[s.btnSmall, (!newTemplateName.trim() || !newTemplateContent.trim()) && s.btnDisabled]}
          onPress={addTemplate} disabled={!newTemplateName.trim() || !newTemplateContent.trim()}>
          <Ionicons name="add" size={16} color="#FFF" />
          <Text style={{ fontSize: 13, fontWeight: '600', color: '#FFF' }}>Add</Text>
        </TouchableOpacity>
      </View>

      <View style={[s.btnRow, { marginTop: 16 }]}>
        <TouchableOpacity style={s.btnSecondary} onPress={() => go(5)}><Text style={s.btnSecondaryText}>Back</Text></TouchableOpacity>
        <TouchableOpacity style={s.btnSkip} onPress={skip}><Text style={s.btnSkipText}>Skip</Text></TouchableOpacity>
        <TouchableOpacity style={s.btnPrimary} onPress={saveTemplates} disabled={saving}>
          {saving ? <ActivityIndicator size="small" color="#000" /> : <Text style={s.btnPrimaryText}>Next</Text>}
        </TouchableOpacity>
      </View>
    </View>
  );

  const renderStep7 = () => (
    <View>
      <Text style={s.stepTitle}>Tags</Text>
      <Text style={s.stepDesc}>Set up contact tags for organizing customers.</Text>

      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 16 }}>
        {existingTags.map(tag => {
          const active = selectedTags.includes(tag.name);
          return (
            <TouchableOpacity key={tag._id || tag.name} onPress={() => {
              setSelectedTags(active ? selectedTags.filter(t => t !== tag.name) : [...selectedTags, tag.name]);
            }} style={[s.chip, active && { backgroundColor: tag.color || '#C9A962', borderColor: tag.color || '#C9A962' }]}>
              {tag.icon && <Ionicons name={tag.icon as any} size={14} color={active ? '#FFF' : tag.color || colors.textSecondary} />}
              <Text style={[s.chipText, active && { color: '#FFF' }]}>{tag.name}</Text>
            </TouchableOpacity>
          );
        })}
      </View>

      <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}>
        <TextInput style={[s.input, { flex: 1, marginBottom: 0 }]} placeholder="Create new tag..." placeholderTextColor={colors.textTertiary}
          value={newTagName} onChangeText={setNewTagName} />
        <TouchableOpacity style={[s.btnSmall, !newTagName.trim() && s.btnDisabled]} onPress={addNewTag} disabled={!newTagName.trim()}>
          <Ionicons name="add" size={16} color="#FFF" />
          <Text style={{ fontSize: 13, fontWeight: '600', color: '#FFF' }}>Create</Text>
        </TouchableOpacity>
      </View>

      <View style={[s.btnRow, { marginTop: 20 }]}>
        <TouchableOpacity style={s.btnSecondary} onPress={() => go(6)}><Text style={s.btnSecondaryText}>Back</Text></TouchableOpacity>
        <TouchableOpacity style={s.btnSkip} onPress={skip}><Text style={s.btnSkipText}>Skip</Text></TouchableOpacity>
        <TouchableOpacity style={s.btnPrimary} onPress={() => go(8)} disabled={saving}>
          <Text style={s.btnPrimaryText}>Next</Text>
        </TouchableOpacity>
      </View>
    </View>
  );

  const renderStep8 = () => {
    const items = getHandoffItems();
    const done = items.filter(i => i.done).length;
    const userTodos = items.filter(i => i.userAction);
    return (
      <View>
        <Text style={s.stepTitle}>Setup Complete</Text>
        <Text style={s.stepDesc}>{done}/{items.length} items configured for {firstName} {lastName} at {storeName || orgName}.</Text>

        {/* Summary Card */}
        <View style={[s.summaryCard, { borderColor: primaryColor }]}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 12 }}>
            {userPhoto ? <Image source={{ uri: userPhoto }} style={{ width: 48, height: 48, borderRadius: 24 }} /> :
             <View style={{ width: 48, height: 48, borderRadius: 24, backgroundColor: primaryColor + '30', alignItems: 'center', justifyContent: 'center' }}>
               <Text style={{ fontSize: 18, fontWeight: '700', color: primaryColor }}>{firstName?.[0]}{lastName?.[0]}</Text>
             </View>}
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 17, fontWeight: '700', color: colors.text }}>{firstName} {lastName}</Text>
              <Text style={{ fontSize: 13, color: colors.textSecondary }}>{userTitle || userRole} at {storeName || orgName}</Text>
              <Text style={{ fontSize: 12, color: colors.textTertiary }}>{userEmail}</Text>
            </View>
          </View>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <TouchableOpacity style={[s.btnSmall, { flex: 1 }]} onPress={() => {
              const creds = `Email: ${userEmail}\nPassword: ${tempPassword}`;
              if (Platform.OS === 'web') navigator.clipboard?.writeText(creds);
            }}>
              <Ionicons name="copy-outline" size={14} color="#FFF" />
              <Text style={{ fontSize: 12, fontWeight: '600', color: '#FFF' }}>Copy Login</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Configuration Status */}
        <Text style={[s.label, { marginTop: 16 }]}>Configuration Status</Text>
        {items.map((item, i) => (
          <View key={i} style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: colors.border }}>
            <Ionicons name={item.done ? 'checkmark-circle' : 'ellipse-outline'} size={20}
              color={item.done ? '#34C759' : '#FF9500'} style={{ marginRight: 10 }} />
            <Text style={{ flex: 1, fontSize: 14, color: item.done ? colors.text : colors.textSecondary }}>{item.label}</Text>
          </View>
        ))}

        {/* User Handoff Checklist */}
        {userTodos.length > 0 && (
          <View style={{ marginTop: 20 }}>
            <Text style={[s.label, { color: '#FF9500' }]}>User Needs To Complete:</Text>
            {userTodos.map((item, i) => (
              <View key={i} style={{ flexDirection: 'row', alignItems: 'flex-start', paddingVertical: 6, gap: 8 }}>
                <View style={{ width: 20, height: 20, borderRadius: 4, borderWidth: 2, borderColor: '#FF9500', marginTop: 1 }} />
                <Text style={{ flex: 1, fontSize: 14, color: colors.text }}>{item.userAction}</Text>
              </View>
            ))}
          </View>
        )}

        <View style={[s.btnRow, { marginTop: 24 }]}>
          <TouchableOpacity style={s.btnSecondary} onPress={() => go(7)}><Text style={s.btnSecondaryText}>Back</Text></TouchableOpacity>
          <TouchableOpacity style={[s.btnPrimary, { flex: 1 }]} onPress={() => router.push('/admin' as any)}>
            <Ionicons name="checkmark-circle" size={18} color="#000" />
            <Text style={s.btnPrimaryText}>Done</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  };

  if (loading) return (
    <SafeAreaView style={[s.container, { justifyContent: 'center', alignItems: 'center' }]}>
      <ActivityIndicator size="large" color="#C9A962" />
    </SafeAreaView>
  );

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        <View style={s.header}>
          <TouchableOpacity onPress={() => router.back()}><Ionicons name="close" size={24} color={colors.text} /></TouchableOpacity>
          <Text style={s.headerTitle}>Onboard Account</Text>
          <View style={{ width: 24 }} />
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
  headerTitle: { fontSize: 17, fontWeight: '700', color: colors.text },
  stepBar: { flexDirection: 'row', paddingHorizontal: 12, paddingVertical: 10, gap: 2 },
  stepDot: { alignItems: 'center', width: 56 },
  dot: { width: 28, height: 28, borderRadius: 14, borderWidth: 2, borderColor: colors.border, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.card },
  dotDone: { backgroundColor: '#34C759', borderColor: '#34C759' },
  dotActive: { backgroundColor: '#C9A962', borderColor: '#C9A962' },
  dotText: { fontSize: 12, fontWeight: '700', color: colors.textTertiary },
  dotTextActive: { color: '#000' },
  stepLabel: { fontSize: 9, color: colors.textTertiary, marginTop: 3, textAlign: 'center' },
  stepLabelActive: { color: '#C9A962', fontWeight: '600' },
  content: { padding: 20, paddingBottom: 60 },
  stepTitle: { fontSize: 22, fontWeight: '800', color: colors.text, marginBottom: 4 },
  stepDesc: { fontSize: 14, color: colors.textSecondary, marginBottom: 20 },
  label: { fontSize: 13, fontWeight: '600', color: colors.textSecondary, marginBottom: 6, marginTop: 4 },
  input: { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 12, fontSize: 16, color: colors.text, marginBottom: 12 },
  chip: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.card },
  chipActive: { backgroundColor: '#C9A962', borderColor: '#C9A962' },
  chipText: { fontSize: 13, fontWeight: '600', color: colors.text },
  chipTextActive: { color: '#000' },
  logoBox: { width: '100%', height: 140, borderRadius: 14, borderWidth: 2, borderColor: colors.border, borderStyle: 'dashed', alignItems: 'center', justifyContent: 'center', marginBottom: 16, backgroundColor: colors.card },
  btnRow: { flexDirection: 'row', gap: 10, marginTop: 12 },
  btnPrimary: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#C9A962', paddingVertical: 14, paddingHorizontal: 24, borderRadius: 12 },
  btnPrimaryText: { fontSize: 16, fontWeight: '700', color: '#000' },
  btnSecondary: { paddingVertical: 14, paddingHorizontal: 20, borderRadius: 12, borderWidth: 1, borderColor: colors.border },
  btnSecondaryText: { fontSize: 15, fontWeight: '600', color: colors.textSecondary },
  btnSkip: { paddingVertical: 14, paddingHorizontal: 16 },
  btnSkipText: { fontSize: 15, color: '#FF9500', fontWeight: '600' },
  btnDisabled: { opacity: 0.4 },
  btnSmall: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8, backgroundColor: '#C9A962' },
  templateCard: { padding: 12, backgroundColor: colors.card, borderRadius: 10, borderWidth: 1, borderColor: colors.border, marginBottom: 8 },
  summaryCard: { padding: 16, backgroundColor: colors.card, borderRadius: 14, borderWidth: 2, marginBottom: 8 },
});
