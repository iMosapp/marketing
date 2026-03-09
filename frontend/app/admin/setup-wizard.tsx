import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
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
  { num: 3, title: 'Team', icon: 'people-outline' },
  { num: 4, title: 'Reviews', icon: 'star-outline' },
  { num: 5, title: 'Templates', icon: 'document-text-outline' },
  { num: 6, title: 'Tags', icon: 'pricetags-outline' },
  { num: 7, title: 'Handoff', icon: 'checkmark-circle-outline' },
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

interface TeamMember {
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  role: 'user' | 'manager' | 'admin';
  tempPassword: string;
  createdId?: string;
  error?: string;
}

const genPassword = () => 'Welcome' + Math.floor(1000 + Math.random() * 9000) + '!';

export default function SetupWizardScreen() {
  const { colors } = useThemeStore();
  const s = useMemo(() => getS(colors), [colors]);
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

  // Step 1
  const [orgId, setOrgId] = useState('');
  const [storeId, setStoreId] = useState('');
  const [orgName, setOrgName] = useState('');
  const [storeName, setStoreName] = useState('');
  const [phone, setPhone] = useState('');
  const [city, setCity] = useState('');
  const [stateVal, setStateVal] = useState('');
  const [website, setWebsite] = useState('');
  const [industry, setIndustry] = useState('');
  const [isNewOrg, setIsNewOrg] = useState(true);
  const [isNewStore, setIsNewStore] = useState(true);
  const [showIndustryPicker, setShowIndustryPicker] = useState(false);

  // Step 2
  const [primaryColor, setPrimaryColor] = useState('#C9A962');
  const [logoUrl, setLogoUrl] = useState('');
  const [logoUploading, setLogoUploading] = useState(false);
  const [emailFooter, setEmailFooter] = useState('');

  // Step 3: Team Roster
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([
    { firstName: '', lastName: '', email: '', phone: '', role: 'user', tempPassword: genPassword() },
  ]);
  const [bulkCreating, setBulkCreating] = useState(false);
  const [bulkCreated, setBulkCreated] = useState(false);

  // Step 4: Review Links
  const [googleReview, setGoogleReview] = useState('');
  const [facebookReview, setFacebookReview] = useState('');
  const [yelpReview, setYelpReview] = useState('');
  const [dealerraterReview, setDealerraterReview] = useState('');
  const [customReviewName, setCustomReviewName] = useState('');
  const [customReviewUrl, setCustomReviewUrl] = useState('');

  // Step 5: Templates
  const [templates, setTemplates] = useState(DEFAULT_TEMPLATES.map(t => ({ ...t, enabled: true })));
  const [newTemplateName, setNewTemplateName] = useState('');
  const [newTemplateContent, setNewTemplateContent] = useState('');

  // Step 6: Tags
  const [existingTags, setExistingTags] = useState<any[]>([]);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [newTagName, setNewTagName] = useState('');

  useEffect(() => { loadInitialData(); }, []);

  const loadInitialData = async () => {
    try {
      const userStr = await AsyncStorage.getItem('user');
      const user = userStr ? JSON.parse(userStr) : null;
      setCurrentUser(user);
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
    setOrgId(org._id); setOrgName(org.name); setIsNewOrg(false);
    const filtered = existingStores.filter((s: any) => s.organization_id === org._id);
    setOrgStores(filtered);
    setStoreId(''); setStoreName(''); setIsNewStore(true);
  };

  const selectExistingStore = (store: any) => {
    setStoreId(store._id); setStoreName(store.name); setIsNewStore(false);
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

  // ==== STEP 1: Save Org/Store ====
  const saveOrg = async () => {
    if (!orgName.trim()) { alert('Enter an organization name'); return; }
    setSaving(true);
    try {
      let oid = orgId;
      if (isNewOrg || !oid) {
        const res = await api.post('/admin/organizations', {
          name: orgName, admin_email: currentUser?.email || '', admin_phone: phone,
          city, state: stateVal, account_type: 'organization',
        });
        oid = res.data._id || res.data.id;
        setOrgId(oid); setIsNewOrg(false);
      } else {
        await api.put(`/admin/organizations/${oid}`, { name: orgName, admin_phone: phone, city, state: stateVal });
      }
      let sid = storeId;
      if (isNewStore || !sid) {
        const res = await api.post('/admin/stores', {
          organization_id: oid, name: storeName || orgName,
          phone, city, state: stateVal, website, industry,
        });
        sid = res.data._id || res.data.id;
        setStoreId(sid); setIsNewStore(false);
      } else {
        await api.put(`/admin/stores/${sid}`, { name: storeName || orgName, phone, city, state: stateVal, website, industry });
      }
      go(2);
    } catch (e: any) { alert(e.response?.data?.detail || 'Error saving'); }
    finally { setSaving(false); }
  };

  // ==== STEP 2: Branding ====
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

  // ==== STEP 3: Bulk Team Roster ====
  const updateMember = (idx: number, field: keyof TeamMember, value: string) => {
    const updated = [...teamMembers];
    (updated[idx] as any)[field] = value;
    setTeamMembers(updated);
  };

  const addMember = () => {
    setTeamMembers([...teamMembers, { firstName: '', lastName: '', email: '', phone: '', role: 'user', tempPassword: genPassword() }]);
  };

  const removeMember = (idx: number) => {
    if (teamMembers.length <= 1) return;
    setTeamMembers(teamMembers.filter((_, i) => i !== idx));
  };

  const createAllUsers = async () => {
    const valid = teamMembers.filter(m => m.firstName.trim() && m.email.trim());
    if (valid.length === 0) { alert('Add at least one team member with name and email'); return; }
    setBulkCreating(true);
    const updated = [...teamMembers];
    let anyCreated = false;
    for (let i = 0; i < updated.length; i++) {
      const m = updated[i];
      if (!m.firstName.trim() || !m.email.trim() || m.createdId) continue;
      try {
        const fullName = `${m.firstName.trim()} ${m.lastName.trim()}`.trim();
        const res = await api.post('/admin/users', {
          name: fullName, email: m.email, phone: m.phone,
          password: m.tempPassword, role: m.role,
          store_id: storeId, organization_id: orgId,
          needs_password_change: true, onboarding_complete: false,
        });
        updated[i] = { ...m, createdId: res.data._id || res.data.id, error: undefined };
        anyCreated = true;
      } catch (e: any) {
        updated[i] = { ...m, error: e.response?.data?.detail || 'Failed to create' };
      }
    }
    setTeamMembers(updated);
    setBulkCreated(anyCreated);
    setBulkCreating(false);
    if (anyCreated) {
      const failCount = updated.filter(m => m.error).length;
      if (failCount > 0) alert(`${updated.filter(m => m.createdId).length} users created. ${failCount} failed — check errors below.`);
    }
  };

  // ==== STEP 4: Review Links ====
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
      go(5);
    } catch { alert('Error saving review links'); }
    finally { setSaving(false); }
  };

  // ==== STEP 5: Templates ====
  const addTemplate = () => {
    if (!newTemplateName.trim() || !newTemplateContent.trim()) return;
    setTemplates([...templates, { name: newTemplateName, content: newTemplateContent, category: 'custom', enabled: true }]);
    setNewTemplateName(''); setNewTemplateContent('');
  };

  const saveTemplates = async () => {
    setSaving(true);
    try {
      // Save templates for each created user
      const createdUsers = teamMembers.filter(m => m.createdId);
      const uid = createdUsers.length > 0 ? createdUsers[0].createdId : currentUser?._id;
      if (uid) {
        for (const t of templates.filter(t => t.enabled)) {
          await api.post(`/templates/${uid}`, { name: t.name, content: t.content, category: t.category }).catch(() => {});
        }
      }
      go(6);
    } catch { alert('Error saving templates'); }
    finally { setSaving(false); }
  };

  // ==== STEP 6: Tags ====
  const addNewTag = async () => {
    if (!newTagName.trim()) return;
    const uid = currentUser?._id;
    try {
      await api.post(`/tags/${uid}`, { name: newTagName, color: primaryColor, icon: 'pricetag' });
      setSelectedTags([...selectedTags, newTagName]);
      setNewTagName('');
      const res = await api.get(`/tags/${uid}`).catch(() => ({ data: [] }));
      setExistingTags(Array.isArray(res.data) ? res.data : []);
    } catch (e: any) { alert(e.response?.data?.detail || 'Error creating tag'); }
  };

  // ==== CSV / Copy ====
  const getCredsText = () => {
    const created = teamMembers.filter(m => m.createdId);
    return created.map(m => `${m.firstName} ${m.lastName} | ${m.email} | ${m.tempPassword} | ${m.role}`).join('\n');
  };

  const downloadCSV = () => {
    const created = teamMembers.filter(m => m.createdId);
    const rows = [['Name', 'Email', 'Temp Password', 'Role']];
    created.forEach(m => rows.push([`${m.firstName} ${m.lastName}`, m.email, m.tempPassword, m.role]));
    const csv = rows.map(r => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = `${(storeName || orgName).replace(/\s/g, '_')}_team_credentials.csv`;
    a.click(); URL.revokeObjectURL(url);
  };

  // ==== Handoff Checklist ====
  const getHandoffItems = () => {
    const created = teamMembers.filter(m => m.createdId);
    return [
      { label: 'Organization created', done: !!orgId, action: '' },
      { label: 'Store configured', done: !!storeId, action: '' },
      { label: 'Logo uploaded', done: !!logoUrl, action: logoUrl ? '' : 'Upload company logo in Settings > Branding' },
      { label: 'Brand color set', done: primaryColor !== '#C9A962', action: '' },
      { label: `Team accounts created (${created.length})`, done: created.length > 0, action: created.length === 0 ? 'Create team member accounts' : '' },
      { label: 'Google Review link', done: !!googleReview, action: googleReview ? '' : 'Add Google review link in Settings > Review Links' },
      { label: 'Message templates loaded', done: !skipped.has(5), action: skipped.has(5) ? 'Customize message templates in Settings' : '' },
      { label: 'Tags configured', done: selectedTags.length > 0 || !skipped.has(6), action: skipped.has(6) ? 'Set up contact tags in Settings > Tags' : '' },
    ];
  };

  // ---- Shared UI ----
  // Memoized sub-components — prevents TextInput from losing focus on re-render
  const SectionCard = useMemo(() => React.memo(({ children, style }: { children: React.ReactNode; style?: any }) => (
    <View style={[s.sectionCard, style]}>{children}</View>
  )), [s]);
  const StepHeader = useMemo(() => React.memo(({ title, desc }: { title: string; desc: string }) => (
    <View style={{ marginBottom: 24 }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 6 }}>
        <View style={s.stepNumBadge}><Text style={s.stepNumBadgeText}>{step}</Text></View>
        <Text style={s.stepTitle}>{title}</Text>
      </View>
      <Text style={s.stepDesc}>{desc}</Text>
    </View>
  )), [step, s]);
  const Label = useMemo(() => React.memo(({ text, required }: { text: string; required?: boolean }) => (
    <Text style={s.label}>{text}{required ? <Text style={{ color: '#C9A962' }}> *</Text> : null}</Text>
  )), [s]);
  const BtnRow = useMemo(() => React.memo(({ onBack, onSkip, onNext, nextLabel, nextDisabled }: any) => (
    <View style={s.btnRow}>
      {onBack && <TouchableOpacity style={s.btnSecondary} onPress={onBack} data-testid="wizard-back-btn"><Ionicons name="arrow-back" size={18} color={colors.textSecondary} /><Text style={s.btnSecondaryText}>Back</Text></TouchableOpacity>}
      {onSkip && <TouchableOpacity style={s.btnSkip} onPress={onSkip} data-testid="wizard-skip-btn"><Text style={s.btnSkipText}>Skip</Text><Ionicons name="arrow-forward" size={16} color="#FF9500" /></TouchableOpacity>}
      <TouchableOpacity style={[s.btnPrimary, nextDisabled && s.btnDisabled]} onPress={onNext} disabled={saving || nextDisabled} data-testid="wizard-next-btn">
        {saving ? <ActivityIndicator size="small" color="#000" /> : <><Text style={s.btnPrimaryText}>{nextLabel || 'Continue'}</Text><Ionicons name="arrow-forward" size={18} color="#000" /></>}
      </TouchableOpacity>
    </View>
  )), [s, saving, colors]);

  // ---- Step Bar ----
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
      <View style={s.progressTrack}>
        <Animated.View style={[s.progressFill, { width: `${((step - 1) / (STEPS.length - 1)) * 100}%` }]} />
      </View>
    </View>
  );

  // ---- STEP 1 ----
  const renderStep1 = () => (
    <View>
      <StepHeader title="Organization & Store" desc="Create a new organization or select an existing one to configure." />
      {existingOrgs.length > 0 && (
        <SectionCard>
          <Label text="Select Existing Organization" />
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 8 }}>
            {existingOrgs.map(o => (
              <TouchableOpacity key={o._id} onPress={() => selectExistingOrg(o)}
                style={[s.chip, orgId === o._id && !isNewOrg && s.chipActive]}>
                <Ionicons name="business" size={14} color={orgId === o._id && !isNewOrg ? '#000' : colors.textSecondary} />
                <Text style={[s.chipText, orgId === o._id && !isNewOrg && s.chipTextActive]}>{o.name}</Text>
              </TouchableOpacity>
            ))}
            <TouchableOpacity onPress={() => { setOrgId(''); setOrgName(''); setIsNewOrg(true); setOrgStores([]); setStoreId(''); setStoreName(''); setIsNewStore(true); }}
              style={[s.chip, isNewOrg && s.chipActive]}>
              <Ionicons name="add-circle" size={16} color={isNewOrg ? '#000' : '#C9A962'} />
              <Text style={[s.chipText, isNewOrg && s.chipTextActive]}>Create New</Text>
            </TouchableOpacity>
          </ScrollView>
        </SectionCard>
      )}
      {!isNewOrg && orgStores.length > 0 && (
        <SectionCard>
          <Label text="Select Store" />
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 8 }}>
            {orgStores.map(st => (
              <TouchableOpacity key={st._id} onPress={() => selectExistingStore(st)}
                style={[s.chip, storeId === st._id && !isNewStore && s.chipActive]}>
                <Ionicons name="storefront" size={14} color={storeId === st._id && !isNewStore ? '#000' : colors.textSecondary} />
                <Text style={[s.chipText, storeId === st._id && !isNewStore && s.chipTextActive]}>{st.name}</Text>
              </TouchableOpacity>
            ))}
            <TouchableOpacity onPress={() => { setStoreId(''); setStoreName(''); setIsNewStore(true); }}
              style={[s.chip, isNewStore && s.chipActive]}>
              <Ionicons name="add-circle" size={16} color={isNewStore ? '#000' : '#C9A962'} />
              <Text style={[s.chipText, isNewStore && s.chipTextActive]}>New Store</Text>
            </TouchableOpacity>
          </ScrollView>
        </SectionCard>
      )}
      <SectionCard>
        <Label text="Organization Name" required />
        <TextInput style={s.input} placeholder="e.g., Rev1 Auto Group" placeholderTextColor={colors.textTertiary}
          value={orgName} onChangeText={setOrgName} />
        <Label text="Store / Location Name" />
        <TextInput style={s.input} placeholder="e.g., Rev1 Downtown (defaults to org name)" placeholderTextColor={colors.textTertiary}
          value={storeName} onChangeText={setStoreName} />
        <Label text="Industry" />
        <TouchableOpacity style={[s.input, { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }]}
          onPress={() => setShowIndustryPicker(!showIndustryPicker)}>
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
          <View style={{ flex: 1 }}><Label text="Phone" />
            <TextInput style={s.input} placeholder="(555) 123-4567" placeholderTextColor={colors.textTertiary} value={phone} onChangeText={setPhone} keyboardType="phone-pad" /></View>
          <View style={{ flex: 1 }}><Label text="Website" />
            <TextInput style={s.input} placeholder="www.example.com" placeholderTextColor={colors.textTertiary} value={website} onChangeText={setWebsite} autoCapitalize="none" /></View>
        </View>
        <View style={{ flexDirection: 'row', gap: 12 }}>
          <View style={{ flex: 2 }}><Label text="City" />
            <TextInput style={s.input} placeholder="City" placeholderTextColor={colors.textTertiary} value={city} onChangeText={setCity} /></View>
          <View style={{ flex: 1 }}><Label text="State" />
            <TextInput style={s.input} placeholder="ST" placeholderTextColor={colors.textTertiary} value={stateVal} onChangeText={setStateVal} autoCapitalize="characters" maxLength={2} /></View>
        </View>
      </SectionCard>
      <BtnRow onBack={() => router.back()} onNext={saveOrg} nextLabel="Create & Continue" nextDisabled={!orgName.trim()} />
    </View>
  );

  // ---- STEP 2 ----
  const renderStep2 = () => (
    <View>
      <StepHeader title="Branding" desc={`Upload logo and set brand colors for ${storeName || orgName}.`} />
      <SectionCard>
        <Label text="Logo" />
        <TouchableOpacity style={s.logoBox} onPress={uploadLogo}>
          {logoUploading ? <ActivityIndicator size="large" color="#C9A962" /> :
           logoUrl ? <Image source={{ uri: logoUrl }} style={{ width: 120, height: 120, borderRadius: 16 }} resizeMode="contain" /> :
           <View style={{ alignItems: 'center' }}>
             <View style={s.uploadIconCircle}><Ionicons name="cloud-upload-outline" size={28} color="#C9A962" /></View>
             <Text style={{ color: colors.textSecondary, marginTop: 10, fontSize: 14, fontWeight: '500' }}>Tap to upload logo</Text>
             <Text style={{ color: colors.textTertiary, fontSize: 12, marginTop: 2 }}>PNG, JPG up to 5MB</Text>
           </View>}
        </TouchableOpacity>
      </SectionCard>
      <SectionCard>
        <Label text="Brand Color" />
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginBottom: 16 }}>
          {BRAND_COLORS.map(c => (
            <TouchableOpacity key={c} onPress={() => setPrimaryColor(c)}
              style={[s.colorSwatch, { backgroundColor: c }, primaryColor === c && s.colorSwatchActive]}>
              {primaryColor === c && <Ionicons name="checkmark" size={18} color="#FFF" />}
            </TouchableOpacity>
          ))}
        </View>
      </SectionCard>
      <SectionCard>
        <Label text="Custom Email Footer" />
        <TextInput style={s.input} placeholder="e.g., Powered by Rev1 Auto Group" placeholderTextColor={colors.textTertiary} value={emailFooter} onChangeText={setEmailFooter} />
      </SectionCard>
      <BtnRow onBack={() => go(1)} onSkip={skip} onNext={saveBranding} />
    </View>
  );

  // ---- STEP 3: Team Roster ----
  const renderStep3 = () => (
    <View>
      <StepHeader title="Team Roster" desc={`Add all team members for ${storeName || orgName}. They'll set up their own profiles on first login.`} />
      <SectionCard style={{ padding: 12 }}>
        <View style={s.rosterHeader}>
          <Ionicons name="information-circle-outline" size={18} color="#007AFF" />
          <Text style={{ flex: 1, fontSize: 13, color: colors.textSecondary, marginLeft: 8, lineHeight: 18 }}>
            Each user will be prompted to upload their photo, title, bio, and reset their password on first login.
          </Text>
        </View>
      </SectionCard>

      {teamMembers.map((m, idx) => (
        <SectionCard key={idx} style={m.createdId ? { borderColor: '#34C759', borderWidth: 1.5 } : m.error ? { borderColor: '#FF3B30', borderWidth: 1.5 } : undefined}>
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <View style={[s.memberBadge, m.createdId ? { backgroundColor: '#34C75920' } : {}]}>
                {m.createdId ? <Ionicons name="checkmark-circle" size={16} color="#34C759" /> : <Text style={{ fontSize: 13, fontWeight: '700', color: colors.textSecondary }}>{idx + 1}</Text>}
              </View>
              <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text }}>
                {m.createdId ? `${m.firstName} ${m.lastName}` : `Team Member ${idx + 1}`}
              </Text>
            </View>
            {!m.createdId && teamMembers.length > 1 && (
              <TouchableOpacity onPress={() => removeMember(idx)} style={{ padding: 4 }}>
                <Ionicons name="close-circle" size={22} color="#FF3B30" />
              </TouchableOpacity>
            )}
          </View>

          {m.createdId ? (
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, padding: 8, backgroundColor: '#34C75910', borderRadius: 8 }}>
              <Ionicons name="checkmark" size={16} color="#34C759" />
              <Text style={{ flex: 1, fontSize: 13, color: '#34C759' }}>Created! Password: <Text style={{ fontWeight: '700', fontFamily: Platform.OS === 'web' ? 'monospace' : undefined }}>{m.tempPassword}</Text></Text>
            </View>
          ) : (
            <View>
              {m.error && (
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8, backgroundColor: '#FF3B3015', padding: 8, borderRadius: 8 }}>
                  <Ionicons name="alert-circle" size={16} color="#FF3B30" />
                  <Text style={{ fontSize: 12, color: '#FF3B30' }}>{m.error}</Text>
                </View>
              )}
              <View style={{ flexDirection: 'row', gap: 10 }}>
                <View style={{ flex: 1 }}>
                  <TextInput style={s.input} placeholder="First name *" placeholderTextColor={colors.textTertiary}
                    value={m.firstName} onChangeText={v => updateMember(idx, 'firstName', v)} />
                </View>
                <View style={{ flex: 1 }}>
                  <TextInput style={s.input} placeholder="Last name" placeholderTextColor={colors.textTertiary}
                    value={m.lastName} onChangeText={v => updateMember(idx, 'lastName', v)} />
                </View>
              </View>
              <TextInput style={s.input} placeholder="Email *" placeholderTextColor={colors.textTertiary}
                value={m.email} onChangeText={v => updateMember(idx, 'email', v)} keyboardType="email-address" autoCapitalize="none" />
              <View style={{ flexDirection: 'row', gap: 10 }}>
                <View style={{ flex: 1 }}>
                  <TextInput style={s.input} placeholder="Phone (optional)" placeholderTextColor={colors.textTertiary}
                    value={m.phone} onChangeText={v => updateMember(idx, 'phone', v)} keyboardType="phone-pad" />
                </View>
                <View style={{ flex: 1 }}>
                  <View style={{ flexDirection: 'row', gap: 4 }}>
                    {(['user', 'manager', 'admin'] as const).map(r => (
                      <TouchableOpacity key={r} onPress={() => updateMember(idx, 'role', r)}
                        style={[s.roleChip, m.role === r && s.roleChipActive]}>
                        <Text style={[s.roleChipText, m.role === r && s.roleChipTextActive]}>
                          {r === 'user' ? 'Sales' : r.charAt(0).toUpperCase() + r.slice(1)}
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </View>
              </View>
            </View>
          )}
        </SectionCard>
      ))}

      {!bulkCreated && (
        <TouchableOpacity style={s.addMemberBtn} onPress={addMember}>
          <Ionicons name="add-circle-outline" size={22} color="#C9A962" />
          <Text style={{ fontSize: 15, fontWeight: '600', color: '#C9A962' }}>Add Another Team Member</Text>
        </TouchableOpacity>
      )}

      <BtnRow onBack={() => go(2)}
        onNext={bulkCreated ? () => go(4) : createAllUsers}
        nextLabel={bulkCreated ? 'Continue' : `Create ${teamMembers.filter(m => m.firstName.trim() && m.email.trim()).length} User${teamMembers.filter(m => m.firstName.trim() && m.email.trim()).length !== 1 ? 's' : ''}`}
        nextDisabled={!bulkCreated && teamMembers.filter(m => m.firstName.trim() && m.email.trim()).length === 0} />

      {bulkCreating && (
        <View style={{ alignItems: 'center', paddingVertical: 16 }}>
          <ActivityIndicator size="large" color="#C9A962" />
          <Text style={{ color: colors.textSecondary, marginTop: 8, fontSize: 14 }}>Creating accounts...</Text>
        </View>
      )}
    </View>
  );

  // ---- STEP 4: Review Links ----
  const renderStep4 = () => (
    <View>
      <StepHeader title="Review Links" desc={`Add review platform links so your team can send review requests.`} />
      <SectionCard>
        {[
          { label: 'Google Reviews', value: googleReview, set: setGoogleReview, icon: 'logo-google', color: '#4285F4' },
          { label: 'Facebook', value: facebookReview, set: setFacebookReview, icon: 'logo-facebook', color: '#1877F2' },
          { label: 'Yelp', value: yelpReview, set: setYelpReview, icon: 'star', color: '#D32323' },
          { label: 'DealerRater', value: dealerraterReview, set: setDealerraterReview, icon: 'car-sport', color: '#ED8B00' },
        ].map(r => (
          <View key={r.label} style={{ marginBottom: 12 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <View style={[s.socialIconBox, { backgroundColor: r.color + '18' }]}>
                <Ionicons name={r.icon as any} size={16} color={r.color} />
              </View>
              <Text style={[s.label, { marginBottom: 0, marginTop: 0 }]}>{r.label}</Text>
            </View>
            <TextInput style={s.input} placeholder={`Paste ${r.label} URL`} placeholderTextColor={colors.textTertiary}
              value={r.value} onChangeText={r.set} autoCapitalize="none" />
          </View>
        ))}
      </SectionCard>
      <SectionCard>
        <Label text="Custom Review Link" />
        <View style={{ flexDirection: 'row', gap: 8 }}>
          <TextInput style={[s.input, { flex: 1 }]} placeholder="Name" placeholderTextColor={colors.textTertiary} value={customReviewName} onChangeText={setCustomReviewName} />
          <TextInput style={[s.input, { flex: 2 }]} placeholder="URL" placeholderTextColor={colors.textTertiary} value={customReviewUrl} onChangeText={setCustomReviewUrl} autoCapitalize="none" />
        </View>
      </SectionCard>
      <BtnRow onBack={() => go(3)} onSkip={skip} onNext={saveReviews} />
    </View>
  );

  // ---- STEP 5: Templates ----
  const renderStep5 = () => (
    <View>
      <StepHeader title="Message Templates" desc="Pre-load message templates for the team. Toggle off any you don't want." />
      <SectionCard>
        {templates.map((t, i) => (
          <TouchableOpacity key={i} onPress={() => {
            const u = [...templates]; u[i] = { ...u[i], enabled: !u[i].enabled }; setTemplates(u);
          }} style={[s.templateCard, !t.enabled && { opacity: 0.4 }]}>
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
        <TextInput style={s.input} placeholder="Template name" placeholderTextColor={colors.textTertiary} value={newTemplateName} onChangeText={setNewTemplateName} />
        <TextInput style={[s.input, { minHeight: 60, textAlignVertical: 'top' }]} placeholder="Message content ({name} = contact)" placeholderTextColor={colors.textTertiary} value={newTemplateContent} onChangeText={setNewTemplateContent} multiline />
        <TouchableOpacity style={[s.btnSmall, (!newTemplateName.trim() || !newTemplateContent.trim()) && s.btnDisabled]}
          onPress={addTemplate} disabled={!newTemplateName.trim() || !newTemplateContent.trim()}>
          <Ionicons name="add" size={16} color="#000" /><Text style={{ fontSize: 13, fontWeight: '600', color: '#000' }}>Add Template</Text>
        </TouchableOpacity>
      </SectionCard>
      <BtnRow onBack={() => go(4)} onSkip={skip} onNext={saveTemplates} nextLabel="Save Templates" />
    </View>
  );

  // ---- STEP 6: Tags ----
  const renderStep6 = () => (
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
                }} style={[s.chip, active && { backgroundColor: tag.color || '#C9A962', borderColor: tag.color || '#C9A962' }]}>
                  <Text style={[s.chipText, active && { color: '#FFF' }]}>{tag.name}</Text>
                </TouchableOpacity>
              );
            })}
          </View>
        )}
        <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}>
          <TextInput style={[s.input, { flex: 1, marginBottom: 0 }]} placeholder="Create new tag..." placeholderTextColor={colors.textTertiary} value={newTagName} onChangeText={setNewTagName} />
          <TouchableOpacity style={[s.btnSmall, !newTagName.trim() && s.btnDisabled]} onPress={addNewTag} disabled={!newTagName.trim()}>
            <Ionicons name="add" size={16} color="#000" /><Text style={{ fontSize: 13, fontWeight: '600', color: '#000' }}>Create</Text>
          </TouchableOpacity>
        </View>
      </SectionCard>
      <BtnRow onBack={() => go(5)} onSkip={skip} onNext={() => go(7)} />
    </View>
  );

  // ---- STEP 7: Handoff ----
  const renderStep7 = () => {
    const items = getHandoffItems();
    const doneCount = items.filter(i => i.done).length;
    const todos = items.filter(i => i.action);
    const created = teamMembers.filter(m => m.createdId);
    return (
      <View>
        <StepHeader title="Setup Complete!" desc={`${doneCount}/${items.length} items configured for ${storeName || orgName}.`} />

        {/* Team Credentials */}
        {created.length > 0 && (
          <SectionCard style={{ borderColor: primaryColor, borderWidth: 2 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
              <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text }}>Team Credentials ({created.length})</Text>
              <View style={{ flexDirection: 'row', gap: 8 }}>
                <TouchableOpacity style={s.actionChip} onPress={() => { if (Platform.OS === 'web') { navigator.clipboard?.writeText(getCredsText()); alert('Copied!'); } }}>
                  <Ionicons name="copy-outline" size={14} color="#007AFF" /><Text style={{ fontSize: 12, color: '#007AFF', fontWeight: '600' }}>Copy</Text>
                </TouchableOpacity>
                {Platform.OS === 'web' && (
                  <TouchableOpacity style={s.actionChip} onPress={downloadCSV}>
                    <Ionicons name="download-outline" size={14} color="#007AFF" /><Text style={{ fontSize: 12, color: '#007AFF', fontWeight: '600' }}>CSV</Text>
                  </TouchableOpacity>
                )}
              </View>
            </View>
            {created.map((m, i) => (
              <View key={i} style={s.credRow}>
                <View style={[s.memberBadge, { backgroundColor: primaryColor + '20' }]}>
                  <Text style={{ fontSize: 12, fontWeight: '700', color: primaryColor }}>{m.firstName[0]}{m.lastName?.[0] || ''}</Text>
                </View>
                <View style={{ flex: 1, marginLeft: 10 }}>
                  <Text style={{ fontSize: 14, fontWeight: '600', color: colors.text }}>{m.firstName} {m.lastName}</Text>
                  <Text style={{ fontSize: 12, color: colors.textSecondary }}>{m.email}</Text>
                </View>
                <View style={{ alignItems: 'flex-end' }}>
                  <Text style={{ fontSize: 11, fontWeight: '600', color: '#C9A962', textTransform: 'uppercase' }}>{m.role === 'user' ? 'sales' : m.role}</Text>
                  <Text style={{ fontSize: 12, color: colors.textTertiary, fontFamily: Platform.OS === 'web' ? 'monospace' : undefined }}>{m.tempPassword}</Text>
                </View>
              </View>
            ))}
          </SectionCard>
        )}

        {/* Configuration Checklist */}
        <SectionCard>
          <Text style={[s.label, { fontSize: 14, marginBottom: 10 }]}>Configuration Status</Text>
          {items.map((item, i) => (
            <View key={i} style={s.checklistRow}>
              <Ionicons name={item.done ? 'checkmark-circle' : 'ellipse-outline'} size={22} color={item.done ? '#34C759' : '#FF9500'} />
              <Text style={{ flex: 1, fontSize: 14, color: item.done ? colors.text : colors.textSecondary, fontWeight: item.done ? '500' : '400' }}>{item.label}</Text>
            </View>
          ))}
        </SectionCard>

        {/* User to-do */}
        {todos.length > 0 && (
          <SectionCard style={{ borderColor: '#FF9500', borderWidth: 1 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <Ionicons name="alert-circle" size={20} color="#FF9500" />
              <Text style={{ fontSize: 14, fontWeight: '700', color: '#FF9500' }}>Remaining Items</Text>
            </View>
            {todos.map((item, i) => (
              <View key={i} style={{ flexDirection: 'row', alignItems: 'flex-start', paddingVertical: 6, gap: 10 }}>
                <View style={s.todoCheckbox} />
                <Text style={{ flex: 1, fontSize: 14, color: colors.text, lineHeight: 20 }}>{item.action}</Text>
              </View>
            ))}
          </SectionCard>
        )}

        <View style={s.btnRow}>
          <TouchableOpacity style={s.btnSecondary} onPress={() => go(6)}>
            <Ionicons name="arrow-back" size={18} color={colors.textSecondary} /><Text style={s.btnSecondaryText}>Back</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[s.btnPrimary, { flex: 1 }]} onPress={() => router.push('/admin' as any)}>
            <Ionicons name="checkmark-circle" size={20} color="#000" /><Text style={s.btnPrimaryText}>Finish Setup</Text>
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
          <TouchableOpacity onPress={() => router.back()} style={s.headerCloseBtn}>
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
  stepBarContainer: { borderBottomWidth: 1, borderBottomColor: colors.border },
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
  colorSwatch: { width: 40, height: 40, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  colorSwatchActive: { borderWidth: 3, borderColor: '#FFF', transform: [{ scale: 1.1 }] },
  socialIconBox: { width: 32, height: 32, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  templateCard: { padding: 12, borderRadius: 10, borderWidth: 1, borderColor: colors.border, marginBottom: 8, backgroundColor: colors.bg },
  rosterHeader: { flexDirection: 'row', alignItems: 'flex-start', padding: 4 },
  memberBadge: { width: 30, height: 30, borderRadius: 15, backgroundColor: colors.bg, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: colors.border },
  roleChip: { flex: 1, paddingVertical: 8, borderRadius: 8, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.bg },
  roleChipActive: { backgroundColor: '#C9A962', borderColor: '#C9A962' },
  roleChipText: { fontSize: 11, fontWeight: '600', color: colors.textSecondary },
  roleChipTextActive: { color: '#000' },
  addMemberBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 14, borderRadius: 12, borderWidth: 2, borderColor: '#C9A96240', borderStyle: 'dashed', marginBottom: 16 },
  credRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.border },
  actionChip: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 8, borderWidth: 1, borderColor: '#007AFF30', backgroundColor: '#007AFF10' },
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
