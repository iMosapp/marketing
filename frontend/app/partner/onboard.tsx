import React, { useState, useEffect, useRef } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet, ScrollView,
  ActivityIndicator, Platform, Image, KeyboardAvoidingView, Animated,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import api from '../../services/api';
import { useThemeStore } from '../../store/themeStore';

const STEPS = [
  { num: 1, title: 'Location', icon: 'storefront-outline' },
  { num: 2, title: 'Branding', icon: 'color-palette-outline' },
  { num: 3, title: 'Team', icon: 'people-outline' },
  { num: 4, title: 'Reviews', icon: 'star-outline' },
  { num: 5, title: 'Handoff', icon: 'checkmark-circle-outline' },
];

const BRAND_COLORS = [
  '#C9A962', '#007AFF', '#34C759', '#FF3B30', '#FF9500',
  '#AF52DE', '#5856D6', '#FF2D55', '#00C7BE', '#30D158',
];

interface TeamMember {
  firstName: string; lastName: string; email: string; phone: string;
  role: 'user' | 'manager' | 'admin'; tempPassword: string;
  createdId?: string; error?: string;
}

const genPassword = () => 'Welcome' + Math.floor(1000 + Math.random() * 9000) + '!';

export default function PartnerOnboardScreen() {
  const { colors } = useThemeStore();
  const s = getS(colors);
  const router = useRouter();
  const params = useLocalSearchParams<{ org_id?: string; org_name?: string }>();
  const scrollRef = useRef<ScrollView>(null);
  const fadeAnim = useRef(new Animated.Value(1)).current;

  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [skipped, setSkipped] = useState<Set<number>>(new Set());

  // Org context (read-only for partners)
  const [orgs, setOrgs] = useState<any[]>([]);
  const [selectedOrgId, setSelectedOrgId] = useState(params.org_id || '');
  const [selectedOrgName, setSelectedOrgName] = useState(params.org_name || '');

  // Step 1: Store/Location
  const [storeName, setStoreName] = useState('');
  const [storeId, setStoreId] = useState('');
  const [phone, setPhone] = useState('');
  const [city, setCity] = useState('');
  const [stateVal, setStateVal] = useState('');
  const [website, setWebsite] = useState('');

  // Step 2: Branding
  const [primaryColor, setPrimaryColor] = useState('#C9A962');
  const [logoUrl, setLogoUrl] = useState('');
  const [logoUploading, setLogoUploading] = useState(false);

  // Step 3: Team
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([
    { firstName: '', lastName: '', email: '', phone: '', role: 'user', tempPassword: genPassword() },
  ]);
  const [bulkCreating, setBulkCreating] = useState(false);
  const [bulkCreated, setBulkCreated] = useState(false);

  // Step 4: Review Links
  const [googleReview, setGoogleReview] = useState('');
  const [facebookReview, setFacebookReview] = useState('');
  const [yelpReview, setYelpReview] = useState('');

  useEffect(() => { loadData(); }, []);

  const loadData = async () => {
    try {
      const res = await api.get('/partners/portal/orgs');
      const data = Array.isArray(res.data) ? res.data : [];
      setOrgs(data);
      if (params.org_id) {
        const matched = data.find((o: any) => o._id === params.org_id);
        if (matched) { setSelectedOrgId(matched._id); setSelectedOrgName(matched.name); }
      } else if (data.length === 1) {
        setSelectedOrgId(data[0]._id); setSelectedOrgName(data[0].name);
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

  // Step 1: Create Store
  const saveStore = async () => {
    if (!selectedOrgId) { alert('Select an organization first'); return; }
    if (!storeName.trim()) { alert('Enter a location name'); return; }
    setSaving(true);
    try {
      const res = await api.post('/admin/stores', {
        organization_id: selectedOrgId, name: storeName,
        phone, city, state: stateVal, website,
      });
      setStoreId(res.data._id || res.data.id);
      go(2);
    } catch (e: any) { alert(e.response?.data?.detail || 'Error creating store'); }
    finally { setSaving(false); }
  };

  // Step 2: Branding
  const uploadLogo = async () => {
    if (Platform.OS !== 'web' || !storeId) return;
    const input = document.createElement('input');
    input.type = 'file'; input.accept = 'image/*';
    input.onchange = async (e: any) => {
      const file = e.target.files[0]; if (!file) return;
      setLogoUploading(true);
      try {
        const fd = new FormData(); fd.append('file', file);
        const res = await api.post(`/admin/stores/${storeId}/upload-logo`, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
        setLogoUrl(res.data.logo_url || '');
      } catch { alert('Error uploading logo'); }
      finally { setLogoUploading(false); }
    };
    input.click();
  };

  const saveBranding = async () => {
    setSaving(true);
    try {
      if (storeId) await api.put(`/admin/stores/${storeId}`, { primary_color: primaryColor });
      go(3);
    } catch { alert('Error saving'); }
    finally { setSaving(false); }
  };

  // Step 3: Team
  const updateMember = (idx: number, field: keyof TeamMember, value: string) => {
    const updated = [...teamMembers]; (updated[idx] as any)[field] = value; setTeamMembers(updated);
  };
  const addMember = () => setTeamMembers([...teamMembers, { firstName: '', lastName: '', email: '', phone: '', role: 'user', tempPassword: genPassword() }]);
  const removeMember = (idx: number) => { if (teamMembers.length > 1) setTeamMembers(teamMembers.filter((_, i) => i !== idx)); };

  const createAllUsers = async () => {
    const valid = teamMembers.filter(m => m.firstName.trim() && m.email.trim());
    if (valid.length === 0) { alert('Add at least one member'); return; }
    setBulkCreating(true);
    const updated = [...teamMembers];
    let anyCreated = false;
    for (let i = 0; i < updated.length; i++) {
      const m = updated[i];
      if (!m.firstName.trim() || !m.email.trim() || m.createdId) continue;
      try {
        const res = await api.post('/admin/users', {
          name: `${m.firstName.trim()} ${m.lastName.trim()}`.trim(),
          email: m.email, phone: m.phone, password: m.tempPassword,
          role: m.role, store_id: storeId, organization_id: selectedOrgId,
          needs_password_change: true, onboarding_complete: false,
        });
        updated[i] = { ...m, createdId: res.data._id || res.data.id, error: undefined };
        anyCreated = true;
      } catch (e: any) { updated[i] = { ...m, error: e.response?.data?.detail || 'Failed' }; }
    }
    setTeamMembers(updated); setBulkCreated(anyCreated); setBulkCreating(false);
  };

  // Step 4: Reviews
  const saveReviews = async () => {
    setSaving(true);
    try {
      if (storeId) {
        const links: any = {};
        if (googleReview) links.google = googleReview;
        if (facebookReview) links.facebook = facebookReview;
        if (yelpReview) links.yelp = yelpReview;
        await api.put(`/admin/stores/${storeId}/review-links`, links);
      }
      go(5);
    } catch { alert('Error saving'); }
    finally { setSaving(false); }
  };

  // CSV/Copy helpers
  const getCredsText = () => teamMembers.filter(m => m.createdId).map(m => `${m.firstName} ${m.lastName} | ${m.email} | ${m.tempPassword} | ${m.role}`).join('\n');
  const downloadCSV = () => {
    const rows = [['Name', 'Email', 'Temp Password', 'Role']];
    teamMembers.filter(m => m.createdId).forEach(m => rows.push([`${m.firstName} ${m.lastName}`, m.email, m.tempPassword, m.role]));
    const blob = new Blob([rows.map(r => r.join(',')).join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob); const a = document.createElement('a');
    a.href = url; a.download = `${storeName.replace(/\s/g, '_')}_credentials.csv`; a.click(); URL.revokeObjectURL(url);
  };

  // Shared UI
  const SectionCard = ({ children, style }: any) => <View style={[s.card, style]}>{children}</View>;
  const Label = ({ text, required }: { text: string; required?: boolean }) => (
    <Text style={s.label}>{text}{required ? <Text style={{ color: '#C9A962' }}> *</Text> : null}</Text>
  );
  const BtnRow = ({ onBack, onSkip, onNext, nextLabel, nextDisabled }: any) => (
    <View style={s.btnRow}>
      {onBack && <TouchableOpacity style={s.btnSec} onPress={onBack}><Ionicons name="arrow-back" size={18} color={colors.textSecondary} /><Text style={s.btnSecText}>Back</Text></TouchableOpacity>}
      {onSkip && <TouchableOpacity style={s.btnSkip} onPress={onSkip}><Text style={{ fontSize: 17, color: '#FF9500', fontWeight: '600' }}>Skip</Text></TouchableOpacity>}
      <TouchableOpacity style={[s.btnPrimary, nextDisabled && { opacity: 0.4 }]} onPress={onNext} disabled={saving || nextDisabled}>
        {saving ? <ActivityIndicator size="small" color="#000" /> : <><Text style={s.btnPrimaryText}>{nextLabel || 'Continue'}</Text><Ionicons name="arrow-forward" size={18} color="#000" /></>}
      </TouchableOpacity>
    </View>
  );

  // Step Bar
  const renderStepBar = () => (
    <View style={{ borderBottomWidth: 1, borderBottomColor: colors.border }}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ flexDirection: 'row', paddingHorizontal: 16, paddingVertical: 10, gap: 4 }}>
        {STEPS.map(st => {
          const active = step === st.num; const done = step > st.num;
          return (
            <TouchableOpacity key={st.num} style={{ alignItems: 'center', width: 64 }} onPress={() => st.num < step && go(st.num)}>
              <View style={[s.dot, done && { backgroundColor: '#34C759', borderColor: '#34C759' }, active && { backgroundColor: '#C9A962', borderColor: '#C9A962' }]}>
                {done ? <Ionicons name="checkmark" size={14} color="#FFF" /> : active ? <Ionicons name={st.icon as any} size={14} color="#000" /> : <Text style={{ fontSize: 14, fontWeight: '700', color: colors.textTertiary }}>{st.num}</Text>}
              </View>
              <Text style={[s.dotLabel, active && { color: '#C9A962', fontWeight: '700' }, done && { color: '#34C759' }]}>{st.title}</Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>
      <View style={s.progressTrack}><View style={[s.progressFill, { width: `${((step - 1) / (STEPS.length - 1)) * 100}%` }]} /></View>
    </View>
  );

  // Step 1: Location
  const renderStep1 = () => (
    <View>
      <View style={{ marginBottom: 24 }}>
        <Text style={s.stepTitle}>Add Location</Text>
        <Text style={s.stepDesc}>Add a new store or location under an existing organization.</Text>
      </View>

      {/* Org Selector (read-only selection) */}
      <SectionCard>
        <Label text="Organization" required />
        {orgs.length === 0 ? (
          <Text style={{ fontSize: 16, color: colors.textTertiary }}>No organizations assigned.</Text>
        ) : (
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 8 }}>
            {orgs.map(o => (
              <TouchableOpacity key={o._id} onPress={() => { setSelectedOrgId(o._id); setSelectedOrgName(o.name); }}
                style={[s.chip, selectedOrgId === o._id && s.chipActive]}>
                <Ionicons name="business" size={14} color={selectedOrgId === o._id ? '#000' : colors.textSecondary} />
                <Text style={[s.chipText, selectedOrgId === o._id && { color: '#000' }]}>{o.name}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        )}
        {selectedOrgName ? (
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, padding: 10, backgroundColor: '#34C75910', borderRadius: 8, marginTop: 4 }}>
            <Ionicons name="checkmark-circle" size={16} color="#34C759" />
            <Text style={{ fontSize: 15, color: '#34C759', fontWeight: '600' }}>Adding to: {selectedOrgName}</Text>
          </View>
        ) : null}
      </SectionCard>

      <SectionCard>
        <Label text="Location Name" required />
        <TextInput style={s.input} placeholder="e.g., Kubota of Austin" placeholderTextColor={colors.textTertiary}
          value={storeName} onChangeText={setStoreName} />
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
            <TextInput style={s.input} placeholder="ST" placeholderTextColor={colors.textTertiary} value={stateVal} onChangeText={setStateVal} maxLength={2} autoCapitalize="characters" /></View>
        </View>
      </SectionCard>
      <BtnRow onBack={() => router.back()} onNext={saveStore} nextLabel="Create Location" nextDisabled={!selectedOrgId || !storeName.trim()} />
    </View>
  );

  // Step 2: Branding
  const renderStep2 = () => (
    <View>
      <Text style={s.stepTitle}>Branding</Text>
      <Text style={s.stepDesc}>Upload a logo and set brand color for {storeName}.</Text>
      <SectionCard style={{ marginTop: 20 }}>
        <TouchableOpacity style={s.logoBox} onPress={uploadLogo}>
          {logoUploading ? <ActivityIndicator size="large" color="#C9A962" /> :
           logoUrl ? <Image source={{ uri: logoUrl }} style={{ width: 120, height: 120, borderRadius: 16 }} resizeMode="contain" /> :
           <View style={{ alignItems: 'center' }}><Ionicons name="cloud-upload-outline" size={28} color="#C9A962" /><Text style={{ color: colors.textSecondary, marginTop: 8, fontSize: 16 }}>Tap to upload logo</Text></View>}
        </TouchableOpacity>
      </SectionCard>
      <SectionCard>
        <Label text="Brand Color" />
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
          {BRAND_COLORS.map(c => (
            <TouchableOpacity key={c} onPress={() => setPrimaryColor(c)}
              style={[{ width: 40, height: 40, borderRadius: 10, backgroundColor: c, alignItems: 'center', justifyContent: 'center' }, primaryColor === c && { borderWidth: 3, borderColor: '#FFF', transform: [{ scale: 1.1 }] }]}>
              {primaryColor === c && <Ionicons name="checkmark" size={18} color="#FFF" />}
            </TouchableOpacity>
          ))}
        </View>
      </SectionCard>
      <BtnRow onBack={() => go(1)} onSkip={skip} onNext={saveBranding} />
    </View>
  );

  // Step 3: Team
  const renderStep3 = () => (
    <View>
      <Text style={s.stepTitle}>Team Roster</Text>
      <Text style={s.stepDesc}>Add team members for {storeName}. They'll complete their profiles on first login.</Text>
      <SectionCard style={{ marginTop: 20, padding: 12 }}>
        <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 8 }}>
          <Ionicons name="information-circle-outline" size={18} color="#007AFF" />
          <Text style={{ flex: 1, fontSize: 15, color: colors.textSecondary, lineHeight: 18 }}>Each user will be prompted to upload photo, title, bio, and reset password on first login.</Text>
        </View>
      </SectionCard>

      {teamMembers.map((m, idx) => (
        <SectionCard key={idx} style={m.createdId ? { borderColor: '#34C759', borderWidth: 1.5 } : m.error ? { borderColor: '#FF3B30', borderWidth: 1.5 } : undefined}>
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <Text style={{ fontSize: 17, fontWeight: '700', color: colors.text }}>
              {m.createdId ? `${m.firstName} ${m.lastName}` : `Team Member ${idx + 1}`}
            </Text>
            {!m.createdId && teamMembers.length > 1 && (
              <TouchableOpacity onPress={() => removeMember(idx)}><Ionicons name="close-circle" size={22} color="#FF3B30" /></TouchableOpacity>
            )}
          </View>
          {m.createdId ? (
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, padding: 8, backgroundColor: '#34C75910', borderRadius: 8 }}>
              <Ionicons name="checkmark" size={16} color="#34C759" />
              <Text style={{ fontSize: 15, color: '#34C759' }}>Created! Password: <Text style={{ fontWeight: '700', fontFamily: Platform.OS === 'web' ? 'monospace' : undefined }}>{m.tempPassword}</Text></Text>
            </View>
          ) : (
            <View>
              {m.error && <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8, backgroundColor: '#FF3B3015', padding: 8, borderRadius: 8 }}><Ionicons name="alert-circle" size={16} color="#FF3B30" /><Text style={{ fontSize: 14, color: '#FF3B30' }}>{m.error}</Text></View>}
              <View style={{ flexDirection: 'row', gap: 10 }}>
                <TextInput style={[s.input, { flex: 1 }]} placeholder="First name *" placeholderTextColor={colors.textTertiary} value={m.firstName} onChangeText={v => updateMember(idx, 'firstName', v)} />
                <TextInput style={[s.input, { flex: 1 }]} placeholder="Last name" placeholderTextColor={colors.textTertiary} value={m.lastName} onChangeText={v => updateMember(idx, 'lastName', v)} />
              </View>
              <TextInput style={s.input} placeholder="Email *" placeholderTextColor={colors.textTertiary} value={m.email} onChangeText={v => updateMember(idx, 'email', v)} keyboardType="email-address" autoCapitalize="none" />
              <View style={{ flexDirection: 'row', gap: 10 }}>
                <TextInput style={[s.input, { flex: 1 }]} placeholder="Phone" placeholderTextColor={colors.textTertiary} value={m.phone} onChangeText={v => updateMember(idx, 'phone', v)} keyboardType="phone-pad" />
                <View style={{ flex: 1, flexDirection: 'row', gap: 4 }}>
                  {(['user', 'manager'] as const).map(r => (
                    <TouchableOpacity key={r} onPress={() => updateMember(idx, 'role', r)}
                      style={[s.roleChip, m.role === r && { backgroundColor: '#C9A962', borderColor: '#C9A962' }]}>
                      <Text style={[{ fontSize: 14, fontWeight: '600', color: colors.textSecondary }, m.role === r && { color: '#000' }]}>{r === 'user' ? 'Sales' : 'Manager'}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </View>
            </View>
          )}
        </SectionCard>
      ))}

      {!bulkCreated && (
        <TouchableOpacity style={s.addBtn} onPress={addMember}>
          <Ionicons name="add-circle-outline" size={20} color="#C9A962" />
          <Text style={{ fontSize: 16, fontWeight: '600', color: '#C9A962' }}>Add Another</Text>
        </TouchableOpacity>
      )}
      {bulkCreating && <ActivityIndicator size="large" color="#C9A962" style={{ marginVertical: 16 }} />}
      <BtnRow onBack={() => go(2)}
        onNext={bulkCreated ? () => go(4) : createAllUsers}
        nextLabel={bulkCreated ? 'Continue' : `Create ${teamMembers.filter(m => m.firstName.trim() && m.email.trim()).length} User${teamMembers.filter(m => m.firstName.trim() && m.email.trim()).length !== 1 ? 's' : ''}`}
        nextDisabled={!bulkCreated && teamMembers.filter(m => m.firstName.trim() && m.email.trim()).length === 0} />
    </View>
  );

  // Step 4: Reviews
  const renderStep4 = () => (
    <View>
      <Text style={s.stepTitle}>Review Links</Text>
      <Text style={s.stepDesc}>Add review platform links for {storeName}.</Text>
      <SectionCard style={{ marginTop: 20 }}>
        {[
          { label: 'Google Reviews', value: googleReview, set: setGoogleReview, icon: 'logo-google', color: '#4285F4' },
          { label: 'Facebook', value: facebookReview, set: setFacebookReview, icon: 'logo-facebook', color: '#1877F2' },
          { label: 'Yelp', value: yelpReview, set: setYelpReview, icon: 'star', color: '#D32323' },
        ].map(r => (
          <View key={r.label} style={{ marginBottom: 12 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <View style={{ width: 28, height: 28, borderRadius: 6, backgroundColor: r.color + '18', alignItems: 'center', justifyContent: 'center' }}>
                <Ionicons name={r.icon as any} size={14} color={r.color} />
              </View>
              <Text style={s.label}>{r.label}</Text>
            </View>
            <TextInput style={s.input} placeholder={`Paste ${r.label} URL`} placeholderTextColor={colors.textTertiary} value={r.value} onChangeText={r.set} autoCapitalize="none" />
          </View>
        ))}
      </SectionCard>
      <BtnRow onBack={() => go(3)} onSkip={skip} onNext={saveReviews} />
    </View>
  );

  // Step 5: Handoff
  const renderStep5 = () => {
    const created = teamMembers.filter(m => m.createdId);
    const items = [
      { label: `Location: ${storeName}`, done: !!storeId },
      { label: 'Logo uploaded', done: !!logoUrl, action: !logoUrl ? 'Upload in Settings > Branding' : '' },
      { label: `Team created (${created.length})`, done: created.length > 0 },
      { label: 'Google Review link', done: !!googleReview, action: !googleReview ? 'Add in Settings > Review Links' : '' },
    ];
    const todos = items.filter(i => i.action);
    return (
      <View>
        <Text style={s.stepTitle}>Setup Complete!</Text>
        <Text style={s.stepDesc}>{storeName} under {selectedOrgName} is ready to go.</Text>

        {created.length > 0 && (
          <SectionCard style={{ borderColor: '#C9A962', borderWidth: 2, marginTop: 20 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <Text style={{ fontSize: 18, fontWeight: '700', color: colors.text }}>Team Credentials ({created.length})</Text>
              <View style={{ flexDirection: 'row', gap: 8 }}>
                <TouchableOpacity style={s.actionChip} onPress={() => { if (Platform.OS === 'web') { navigator.clipboard?.writeText(getCredsText()); alert('Copied!'); } }}>
                  <Ionicons name="copy-outline" size={14} color="#007AFF" /><Text style={{ fontSize: 14, color: '#007AFF', fontWeight: '600' }}>Copy</Text>
                </TouchableOpacity>
                {Platform.OS === 'web' && (
                  <TouchableOpacity style={s.actionChip} onPress={downloadCSV}>
                    <Ionicons name="download-outline" size={14} color="#007AFF" /><Text style={{ fontSize: 14, color: '#007AFF', fontWeight: '600' }}>CSV</Text>
                  </TouchableOpacity>
                )}
              </View>
            </View>
            {created.map((m, i) => (
              <View key={i} style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.border }}>
                <View style={{ width: 30, height: 30, borderRadius: 15, backgroundColor: '#C9A96220', alignItems: 'center', justifyContent: 'center' }}>
                  <Text style={{ fontSize: 14, fontWeight: '700', color: '#C9A962' }}>{m.firstName[0]}{m.lastName?.[0]}</Text>
                </View>
                <View style={{ flex: 1, marginLeft: 10 }}>
                  <Text style={{ fontSize: 16, fontWeight: '600', color: colors.text }}>{m.firstName} {m.lastName}</Text>
                  <Text style={{ fontSize: 14, color: colors.textSecondary }}>{m.email}</Text>
                </View>
                <View style={{ alignItems: 'flex-end' }}>
                  <Text style={{ fontSize: 13, fontWeight: '600', color: '#C9A962', textTransform: 'uppercase' }}>{m.role === 'user' ? 'sales' : m.role}</Text>
                  <Text style={{ fontSize: 14, color: colors.textTertiary, fontFamily: Platform.OS === 'web' ? 'monospace' : undefined }}>{m.tempPassword}</Text>
                </View>
              </View>
            ))}
          </SectionCard>
        )}

        <SectionCard>
          {items.map((item, i) => (
            <View key={i} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: colors.border }}>
              <Ionicons name={item.done ? 'checkmark-circle' : 'ellipse-outline'} size={22} color={item.done ? '#34C759' : '#FF9500'} />
              <Text style={{ flex: 1, fontSize: 16, color: item.done ? colors.text : colors.textSecondary }}>{item.label}</Text>
            </View>
          ))}
        </SectionCard>

        {todos.length > 0 && (
          <SectionCard style={{ borderColor: '#FF9500', borderWidth: 1 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <Ionicons name="alert-circle" size={18} color="#FF9500" />
              <Text style={{ fontSize: 15, fontWeight: '700', color: '#FF9500' }}>Remaining Items</Text>
            </View>
            {todos.map((t, i) => (
              <View key={i} style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 4 }}>
                <View style={{ width: 18, height: 18, borderRadius: 3, borderWidth: 2, borderColor: '#FF9500' }} />
                <Text style={{ fontSize: 15, color: colors.text }}>{t.action}</Text>
              </View>
            ))}
          </SectionCard>
        )}

        <View style={s.btnRow}>
          <TouchableOpacity style={s.btnSec} onPress={() => go(4)}><Ionicons name="arrow-back" size={18} color={colors.textSecondary} /><Text style={s.btnSecText}>Back</Text></TouchableOpacity>
          <TouchableOpacity style={[s.btnPrimary, { flex: 1 }]} onPress={() => router.push('/partner/dashboard' as any)}>
            <Ionicons name="checkmark-circle" size={20} color="#000" /><Text style={s.btnPrimaryText}>Done</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  };

  if (loading) return <SafeAreaView style={[s.container, { justifyContent: 'center', alignItems: 'center' }]}><ActivityIndicator size="large" color="#C9A962" /></SafeAreaView>;

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        <View style={s.header}>
          <TouchableOpacity onPress={() => router.back()} style={s.closeBtn}><Ionicons name="close" size={20} color={colors.text} /></TouchableOpacity>
          <View style={{ alignItems: 'center' }}><Text style={s.headerTitle}>Add Location</Text><Text style={s.headerSub}>Step {step} of {STEPS.length}</Text></View>
          <View style={{ width: 36 }} />
        </View>
        {renderStepBar()}
        <ScrollView ref={scrollRef} contentContainerStyle={s.scrollContent} showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled">
          <Animated.View style={{ opacity: fadeAnim }}>
            {step === 1 && renderStep1()}
            {step === 2 && renderStep2()}
            {step === 3 && renderStep3()}
            {step === 4 && renderStep4()}
            {step === 5 && renderStep5()}
          </Animated.View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const getS = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.border },
  closeBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center' },
  headerTitle: { fontSize: 18, fontWeight: '700', color: colors.text },
  headerSub: { fontSize: 14, color: colors.textTertiary },
  scrollContent: { padding: 20, paddingBottom: 80, maxWidth: 700, alignSelf: 'center', width: '100%' },
  dot: { width: 30, height: 30, borderRadius: 15, borderWidth: 2, borderColor: colors.border, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.card },
  dotLabel: { fontSize: 12, color: colors.textTertiary, marginTop: 4, textAlign: 'center', fontWeight: '500' },
  progressTrack: { height: 3, backgroundColor: colors.border, marginHorizontal: 16, borderRadius: 2 },
  progressFill: { height: 3, backgroundColor: '#C9A962', borderRadius: 2 },
  stepTitle: { fontSize: 22, fontWeight: '800', color: colors.text, marginBottom: 6 },
  stepDesc: { fontSize: 16, color: colors.textSecondary, lineHeight: 20 },
  card: { backgroundColor: colors.card, borderRadius: 14, padding: 18, marginBottom: 16, borderWidth: 1, borderColor: colors.border },
  label: { fontSize: 15, fontWeight: '600', color: colors.textSecondary, marginBottom: 6, marginTop: 6 },
  input: { backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.border, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 12, fontSize: 18, color: colors.text, marginBottom: 12 },
  chip: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 14, paddingVertical: 9, borderRadius: 20, borderWidth: 1.5, borderColor: colors.border, backgroundColor: colors.card, marginRight: 8 },
  chipActive: { backgroundColor: '#C9A962', borderColor: '#C9A962' },
  chipText: { fontSize: 15, fontWeight: '600', color: colors.text },
  logoBox: { width: '100%', height: 140, borderRadius: 14, borderWidth: 2, borderColor: colors.border, borderStyle: 'dashed', alignItems: 'center', justifyContent: 'center', backgroundColor: colors.bg },
  roleChip: { flex: 1, paddingVertical: 8, borderRadius: 8, borderWidth: 1, borderColor: colors.border, alignItems: 'center', backgroundColor: colors.bg },
  addBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 14, borderRadius: 12, borderWidth: 2, borderColor: '#C9A96240', borderStyle: 'dashed', marginBottom: 16 },
  actionChip: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 8, borderWidth: 1, borderColor: '#007AFF30', backgroundColor: '#007AFF10' },
  btnRow: { flexDirection: 'row', gap: 10, marginTop: 16, marginBottom: 20 },
  btnPrimary: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#C9A962', paddingVertical: 14, paddingHorizontal: 24, borderRadius: 12 },
  btnPrimaryText: { fontSize: 18, fontWeight: '700', color: '#000' },
  btnSec: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 14, paddingHorizontal: 18, borderRadius: 12, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.card },
  btnSecText: { fontSize: 17, fontWeight: '600', color: colors.textSecondary },
  btnSkip: { paddingVertical: 14, paddingHorizontal: 14 },
});
