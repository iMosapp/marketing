import React, { useState, useEffect } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet, ScrollView,
  ActivityIndicator, Platform, Image, KeyboardAvoidingView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import api from '../../services/api';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';

const STEPS = [
  { key: 'password', title: 'Secure Your Account', desc: 'Replace your temporary password with one you\'ll remember.', icon: 'lock-closed-outline' },
  { key: 'photo_about', title: 'About You', desc: 'This info powers your digital card and helps AI write in your voice.', icon: 'person-outline' },
  { key: 'links', title: 'Your Links', desc: 'Connect your profiles so customers can find and follow you.', icon: 'link-outline' },
  { key: 'bio_preview', title: 'Your Bio & Card', desc: 'AI writes your bio based on what you shared. Preview your digital card!', icon: 'sparkles-outline' },
];

export default function CompleteProfileScreen() {
  const { colors } = useThemeStore();
  const s = getS(colors);
  const router = useRouter();
  const { user, updateUser } = useAuthStore();
  const userId = user?._id || '';

  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);

  // Password
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPass, setShowPass] = useState(false);
  const [passwordDone, setPasswordDone] = useState(false);

  // Photo
  const [photoUrl, setPhotoUrl] = useState(user?.photo_url || '');
  const [photoUploading, setPhotoUploading] = useState(false);

  // About — pre-fill from creator data
  const [title, setTitle] = useState('');
  const [company, setCompany] = useState('');
  const [hometown, setHometown] = useState('');
  const [yearsExp, setYearsExp] = useState('');
  const [hobbies, setHobbies] = useState('');
  const [familyInfo, setFamilyInfo] = useState('');
  const [funFacts, setFunFacts] = useState('');
  const [tonePref, setTonePref] = useState('friendly');

  // Links — pre-fill from creator data
  const [website, setWebsite] = useState('');
  const [instagram, setInstagram] = useState('');
  const [facebook, setFacebook] = useState('');
  const [linkedin, setLinkedin] = useState('');
  const [twitter, setTwitter] = useState('');
  const [tiktok, setTiktok] = useState('');
  const [reviewUrl, setReviewUrl] = useState('');

  // Bio
  const [bio, setBio] = useState('');
  const [generatingBio, setGeneratingBio] = useState(false);
  const [bioGenerated, setBioGenerated] = useState(false);

  // Pre-fill from user profile data (set by creator)
  useEffect(() => {
    if (!userId) return;
    api.get(`/profile/${userId}`).then(res => {
      const p = res.data?.user || res.data;
      if (p.title && p.title !== 'Sales Professional') setTitle(p.title);
      if (p.company) setCompany(p.company);
      if (p.website) setWebsite(p.website);
      if (p.bio) setBio(p.bio);
      if (p.photo_url) setPhotoUrl(p.photo_url);
      if (p.review_url) setReviewUrl(p.review_url);
      const sl = p.social_links || {};
      if (sl.instagram) setInstagram(sl.instagram);
      if (sl.facebook) setFacebook(sl.facebook);
      if (sl.linkedin) setLinkedin(sl.linkedin);
      if (sl.twitter) setTwitter(sl.twitter);
      if (sl.tiktok) setTiktok(sl.tiktok);
      if (p.hobbies) setHobbies(Array.isArray(p.hobbies) ? p.hobbies.join(', ') : p.hobbies);
      if (p.hometown) setHometown(p.hometown);
      if (p.family_info) setFamilyInfo(p.family_info);
      if (p.tone_preference && p.tone_preference !== 'friendly') setTonePref(p.tone_preference);
      // If password was already changed, skip step 0
      if (!p.needs_password_change) { setPasswordDone(true); setStep(1); }
    }).catch(() => {});
  }, [userId]);

  const uploadPhoto = async () => {
    if (Platform.OS !== 'web') return;
    const input = document.createElement('input');
    input.type = 'file'; input.accept = 'image/*';
    input.onchange = async (e: any) => {
      const file = e.target.files[0]; if (!file) return;
      setPhotoUploading(true);
      try {
        const fd = new FormData(); fd.append('file', file);
        const res = await api.post(`/profile/${userId}/photo`, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
        if (res.data.photo_url) setPhotoUrl(res.data.photo_url);
      } catch { alert('Error uploading photo.'); }
      finally { setPhotoUploading(false); }
    };
    input.click();
  };

  const saveAllProfile = async () => {
    const data: any = {};
    if (title) data.title = title;
    if (company) data.company = company;
    if (website) data.website = website;
    if (bio) data.bio = bio;
    if (hometown) data.hometown = hometown;
    if (yearsExp) data.years_experience = yearsExp;
    if (familyInfo) data.family_info = familyInfo;
    if (tonePref) data.tone_preference = tonePref;
    if (hobbies) data.hobbies = hobbies.split(',').map((h: string) => h.trim()).filter(Boolean);
    if (funFacts) data.fun_facts = funFacts.split(',').map((f: string) => f.trim()).filter(Boolean);

    const socials: any = {};
    if (instagram) socials.instagram = instagram;
    if (facebook) socials.facebook = facebook;
    if (linkedin) socials.linkedin = linkedin;
    if (twitter) socials.twitter = twitter;
    if (tiktok) socials.tiktok = tiktok;
    data.social_instagram = instagram;
    data.social_facebook = facebook;
    data.social_linkedin = linkedin;
    data.social_twitter = twitter;
    data.social_tiktok = tiktok;
    if (reviewUrl) data.review_url = reviewUrl;

    if (Object.keys(data).length > 0) {
      await api.put(`/profile/${userId}`, data);
    }
  };

  const generateBio = async () => {
    setGeneratingBio(true);
    try {
      const res = await api.post(`/profile/${userId}/generate-bio`, {
        name: user?.name || `${user?.first_name || ''} ${user?.last_name || ''}`.trim(),
        title,
        hobbies: hobbies ? hobbies.split(',').map((h: string) => h.trim()).filter(Boolean) : [],
        family_info: familyInfo,
        hometown,
        years_experience: yearsExp,
        fun_facts: funFacts ? funFacts.split(',').map((f: string) => f.trim()).filter(Boolean) : [],
        tone: tonePref,
      });
      if (res.data.bio) {
        setBio(res.data.bio);
        setBioGenerated(true);
      }
    } catch (e) {
      alert('Could not generate bio. You can write one manually below.');
    } finally { setGeneratingBio(false); }
  };

  const handleNext = async () => {
    setSaving(true);
    try {
      if (step === 0) {
        // Password
        if (!newPassword || newPassword.length < 6) { alert('Password must be at least 6 characters'); setSaving(false); return; }
        if (newPassword !== confirmPassword) { alert('Passwords don\'t match'); setSaving(false); return; }
        try {
          await api.post('/auth/change-password', { user_id: userId, current_password: currentPassword, new_password: newPassword });
          setPasswordDone(true);
        } catch (e: any) {
          alert(e.response?.data?.detail || 'Error changing password');
          setSaving(false);
          return;
        }
        setStep(1);
      } else if (step === 1) {
        // Photo + About — save profile
        await saveAllProfile();
        setStep(2);
      } else if (step === 2) {
        // Links — save
        await saveAllProfile();
        // Auto-generate bio if not already done
        if (!bio && !bioGenerated) await generateBio();
        setStep(3);
      } else if (step === 3) {
        // Final — save and finish
        await saveAllProfile();
        await finishOnboarding();
      }
    } catch (e) { console.error(e); }
    finally { setSaving(false); }
  };

  const finishOnboarding = async () => {
    try {
      await api.put(`/profile/${userId}`, { onboarding_complete: true });
      updateUser({ onboarding_complete: true });
      const userStr = await AsyncStorage.getItem('user');
      if (userStr) {
        const ud = JSON.parse(userStr);
        ud.onboarding_complete = true;
        await AsyncStorage.setItem('user', JSON.stringify(ud));
      }
      router.replace('/(tabs)/home' as any);
    } catch {
      router.replace('/(tabs)/home' as any);
    }
  };

  const handleSkip = () => {
    if (step < STEPS.length - 1) setStep(step + 1);
    else finishOnboarding();
  };

  const stepInfo = STEPS[step];
  const pct = ((step + 1) / STEPS.length) * 100;
  const TONES = [
    { key: 'professional', label: 'Professional', icon: 'briefcase-outline' },
    { key: 'friendly', label: 'Friendly', icon: 'happy-outline' },
    { key: 'casual', label: 'Casual', icon: 'cafe-outline' },
    { key: 'witty', label: 'Witty', icon: 'bulb-outline' },
  ];

  return (
    <SafeAreaView style={s.container} edges={['top', 'bottom']}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        <View style={s.header}>
          <View style={{ flex: 1 }}>
            <Text style={s.headerTitle}>Set Up Your Profile</Text>
            <Text style={s.headerSub}>Step {step + 1} of {STEPS.length}</Text>
          </View>
          <TouchableOpacity onPress={handleSkip} style={s.skipBtn} data-testid="onboarding-skip-btn">
            <Text style={s.skipText}>{step === STEPS.length - 1 ? 'Skip & Finish' : 'Skip'}</Text>
          </TouchableOpacity>
        </View>

        <View style={s.track}><View style={[s.fill, { width: `${pct}%` }]} /></View>

        <ScrollView contentContainerStyle={s.content} showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled">
          <View style={s.iconRow}>
            <View style={s.iconCircle}>
              <Ionicons name={stepInfo.icon as any} size={28} color="#007AFF" />
            </View>
          </View>
          <Text style={s.stepTitle}>{stepInfo.title}</Text>
          <Text style={s.stepDesc}>{stepInfo.desc}</Text>

          {/* === STEP 0: Password === */}
          {step === 0 && (
            <View style={s.body}>
              <Text style={s.label}>Temporary Password</Text>
              <TextInput style={s.input} placeholder="Paste the password you were given" placeholderTextColor={colors.textTertiary}
                value={currentPassword} onChangeText={setCurrentPassword} secureTextEntry={!showPass} data-testid="current-password" />

              <Text style={s.label}>New Password</Text>
              <View style={{ position: 'relative' }}>
                <TextInput style={s.input} placeholder="At least 6 characters" placeholderTextColor={colors.textTertiary}
                  value={newPassword} onChangeText={setNewPassword} secureTextEntry={!showPass} data-testid="new-password" />
                <TouchableOpacity onPress={() => setShowPass(!showPass)} style={{ position: 'absolute', right: 14, top: 14 }}>
                  <Ionicons name={showPass ? 'eye-off' : 'eye'} size={20} color={colors.textTertiary} />
                </TouchableOpacity>
              </View>

              <Text style={s.label}>Confirm Password</Text>
              <TextInput style={s.input} placeholder="Re-enter new password" placeholderTextColor={colors.textTertiary}
                value={confirmPassword} onChangeText={setConfirmPassword} secureTextEntry={!showPass} data-testid="confirm-password" />

              {newPassword.length > 0 && newPassword.length < 6 && (
                <View style={s.errRow}><Ionicons name="alert-circle" size={14} color="#FF3B30" /><Text style={s.errText}>Must be at least 6 characters</Text></View>
              )}
              {confirmPassword.length > 0 && newPassword !== confirmPassword && (
                <View style={s.errRow}><Ionicons name="alert-circle" size={14} color="#FF3B30" /><Text style={s.errText}>Passwords don't match</Text></View>
              )}
            </View>
          )}

          {/* === STEP 1: Photo + About === */}
          {step === 1 && (
            <View style={s.body}>
              <TouchableOpacity onPress={uploadPhoto} activeOpacity={0.7} style={s.photoArea} data-testid="profile-photo-upload">
                {photoUrl ? (
                  <Image source={{ uri: photoUrl }} style={s.photoImg} />
                ) : (
                  <View style={s.photoEmpty}>
                    {photoUploading ? <ActivityIndicator size="large" color="#007AFF" /> : <>
                      <Ionicons name="camera" size={36} color={colors.textTertiary} />
                      <Text style={{ color: colors.textSecondary, marginTop: 6, fontSize: 13 }}>Tap to upload headshot</Text>
                    </>}
                  </View>
                )}
              </TouchableOpacity>
              {photoUrl ? <TouchableOpacity onPress={uploadPhoto} style={{ alignSelf: 'center', marginTop: 6, marginBottom: 12 }}><Text style={{ color: '#007AFF', fontWeight: '600', fontSize: 13 }}>Change Photo</Text></TouchableOpacity> : null}

              <Text style={s.label}>Job Title</Text>
              <TextInput style={s.input} placeholder="e.g., Sales Manager" placeholderTextColor={colors.textTertiary} value={title} onChangeText={setTitle} data-testid="profile-title" />

              <Text style={s.label}>Company</Text>
              <TextInput style={s.input} placeholder="e.g., ABC Motors" placeholderTextColor={colors.textTertiary} value={company} onChangeText={setCompany} data-testid="profile-company" />

              <Text style={s.label}>Hometown</Text>
              <TextInput style={s.input} placeholder="Where are you from?" placeholderTextColor={colors.textTertiary} value={hometown} onChangeText={setHometown} data-testid="profile-hometown" />

              <Text style={s.label}>Years of Experience</Text>
              <TextInput style={s.input} placeholder="e.g., 8" placeholderTextColor={colors.textTertiary} value={yearsExp} onChangeText={setYearsExp} keyboardType="numeric" data-testid="profile-years" />

              <Text style={s.label}>Interests & Hobbies</Text>
              <TextInput style={s.input} placeholder="Golf, fishing, cooking (comma separated)" placeholderTextColor={colors.textTertiary} value={hobbies} onChangeText={setHobbies} data-testid="profile-hobbies" />

              <Text style={s.label}>Family / Personal</Text>
              <TextInput style={s.input} placeholder="e.g., Married, 2 kids, love my dog Max" placeholderTextColor={colors.textTertiary} value={familyInfo} onChangeText={setFamilyInfo} data-testid="profile-family" />

              <Text style={s.label}>Fun Facts</Text>
              <TextInput style={s.input} placeholder="e.g., Ran a marathon, love 80s music" placeholderTextColor={colors.textTertiary} value={funFacts} onChangeText={setFunFacts} data-testid="profile-funfacts" />

              <Text style={[s.label, { marginTop: 8 }]}>AI Persona Tone</Text>
              <Text style={{ fontSize: 12, color: colors.textTertiary, marginBottom: 8 }}>How should AI write on your behalf?</Text>
              <View style={s.toneRow}>
                {TONES.map(t => (
                  <TouchableOpacity key={t.key} style={[s.toneChip, tonePref === t.key && s.toneActive]} onPress={() => setTonePref(t.key)} data-testid={`tone-${t.key}`}>
                    <Ionicons name={t.icon as any} size={16} color={tonePref === t.key ? '#fff' : colors.textSecondary} />
                    <Text style={[s.toneText, tonePref === t.key && { color: '#fff' }]}>{t.label}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>
          )}

          {/* === STEP 2: Links === */}
          {step === 2 && (
            <View style={s.body}>
              <Text style={s.label}>Website</Text>
              <View style={s.linkRow}>
                <Ionicons name="globe-outline" size={18} color={colors.textSecondary} />
                <TextInput style={s.linkInput} placeholder="www.yoursite.com" placeholderTextColor={colors.textTertiary} value={website} onChangeText={setWebsite} autoCapitalize="none" keyboardType="url" data-testid="link-website" />
              </View>

              {[
                { icon: 'logo-instagram', color: '#E1306C', val: instagram, set: setInstagram, ph: 'Instagram URL or @handle', tid: 'link-ig' },
                { icon: 'logo-facebook', color: '#1877F2', val: facebook, set: setFacebook, ph: 'Facebook profile URL', tid: 'link-fb' },
                { icon: 'logo-linkedin', color: '#0A66C2', val: linkedin, set: setLinkedin, ph: 'LinkedIn profile URL', tid: 'link-li' },
                { icon: 'logo-twitter', color: '#1DA1F2', val: twitter, set: setTwitter, ph: 'Twitter/X profile URL', tid: 'link-tw' },
                { icon: 'logo-tiktok', color: '#000', val: tiktok, set: setTiktok, ph: 'TikTok profile URL', tid: 'link-tt' },
              ].map(soc => (
                <View key={soc.tid} style={s.linkRow}>
                  <Ionicons name={soc.icon as any} size={18} color={soc.color} />
                  <TextInput style={s.linkInput} placeholder={soc.ph} placeholderTextColor={colors.textTertiary} value={soc.val} onChangeText={soc.set} autoCapitalize="none" data-testid={soc.tid} />
                </View>
              ))}

              <Text style={[s.label, { marginTop: 16 }]}>Review Page URL</Text>
              <View style={s.linkRow}>
                <Ionicons name="star-outline" size={18} color="#FF9500" />
                <TextInput style={s.linkInput} placeholder="Google Reviews or Yelp URL" placeholderTextColor={colors.textTertiary} value={reviewUrl} onChangeText={setReviewUrl} autoCapitalize="none" keyboardType="url" data-testid="link-review" />
              </View>

              <View style={s.tip}>
                <Ionicons name="information-circle-outline" size={16} color="#007AFF" />
                <Text style={s.tipText}>Skip any you don't use. These show on your digital card.</Text>
              </View>
            </View>
          )}

          {/* === STEP 3: Bio + Preview === */}
          {step === 3 && (
            <View style={s.body}>
              {!bioGenerated && !bio && (
                <TouchableOpacity style={s.genBtn} onPress={generateBio} disabled={generatingBio} data-testid="generate-bio-btn">
                  {generatingBio ? <ActivityIndicator size="small" color="#fff" /> : <>
                    <Ionicons name="sparkles" size={18} color="#fff" />
                    <Text style={s.genBtnText}>Generate My Bio with AI</Text>
                  </>}
                </TouchableOpacity>
              )}

              {(bio || bioGenerated) && (
                <>
                  <Text style={s.label}>Your Bio</Text>
                  <TextInput style={[s.input, { minHeight: 100, textAlignVertical: 'top' }]}
                    value={bio} onChangeText={setBio} multiline data-testid="bio-input" />
                  <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginTop: -8, marginBottom: 12 }}>
                    <Text style={{ fontSize: 12, color: colors.textTertiary }}>{bio.length}/300</Text>
                    <TouchableOpacity onPress={generateBio} disabled={generatingBio}>
                      <Text style={{ fontSize: 12, color: '#007AFF', fontWeight: '600' }}>{generatingBio ? 'Generating...' : 'Regenerate'}</Text>
                    </TouchableOpacity>
                  </View>
                </>
              )}

              {!bio && !generatingBio && (
                <>
                  <Text style={[s.label, { marginTop: 12 }]}>Or write your own</Text>
                  <TextInput style={[s.input, { minHeight: 100, textAlignVertical: 'top' }]}
                    placeholder="Tell customers about yourself..." placeholderTextColor={colors.textTertiary}
                    value={bio} onChangeText={setBio} multiline data-testid="bio-input-manual" />
                </>
              )}

              {/* Mini Card Preview */}
              <View style={s.previewCard} data-testid="card-preview">
                <Text style={s.previewTitle}>Your Digital Card Preview</Text>
                <View style={s.previewBody}>
                  {photoUrl ? <Image source={{ uri: photoUrl }} style={s.previewPhoto} /> : (
                    <View style={[s.previewPhoto, { backgroundColor: colors.border, alignItems: 'center', justifyContent: 'center' }]}>
                      <Ionicons name="person" size={24} color={colors.textTertiary} />
                    </View>
                  )}
                  <Text style={s.previewName}>{user?.name || `${user?.first_name || ''} ${user?.last_name || ''}`.trim() || 'Your Name'}</Text>
                  {title ? <Text style={s.previewRole}>{title}{company ? ` at ${company}` : ''}</Text> : null}
                  {bio ? <Text style={s.previewBio}>{bio}</Text> : <Text style={[s.previewBio, { fontStyle: 'italic', color: colors.textTertiary }]}>Your bio will appear here</Text>}
                  <View style={s.previewIcons}>
                    {instagram ? <Ionicons name="logo-instagram" size={16} color="#E1306C" /> : null}
                    {facebook ? <Ionicons name="logo-facebook" size={16} color="#1877F2" /> : null}
                    {linkedin ? <Ionicons name="logo-linkedin" size={16} color="#0A66C2" /> : null}
                    {twitter ? <Ionicons name="logo-twitter" size={16} color="#1DA1F2" /> : null}
                    {website ? <Ionicons name="globe-outline" size={16} color="#007AFF" /> : null}
                  </View>
                </View>
              </View>
            </View>
          )}
        </ScrollView>

        <View style={s.bottom}>
          {step > 0 && (
            <TouchableOpacity style={s.backBtn} onPress={() => setStep(step - 1)} data-testid="onboarding-back-btn">
              <Ionicons name="arrow-back" size={20} color={colors.textSecondary} />
            </TouchableOpacity>
          )}
          <TouchableOpacity style={[s.nextBtn, saving && { opacity: 0.6 }]} onPress={handleNext} disabled={saving} data-testid="onboarding-continue-btn">
            {saving ? <ActivityIndicator size="small" color="#fff" /> : <>
              <Text style={s.nextText}>{step === STEPS.length - 1 ? "Finish & Go!" : 'Continue'}</Text>
              <Ionicons name={step === STEPS.length - 1 ? 'checkmark-circle' : 'arrow-forward'} size={20} color="#fff" />
            </>}
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const getS = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 20, paddingVertical: 14 },
  headerTitle: { fontSize: 18, fontWeight: '700', color: colors.text },
  headerSub: { fontSize: 13, color: colors.textTertiary, marginTop: 2 },
  skipBtn: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border },
  skipText: { fontSize: 13, fontWeight: '600', color: '#FF9500' },
  track: { height: 4, backgroundColor: colors.border, marginHorizontal: 20, borderRadius: 2 },
  fill: { height: 4, backgroundColor: '#007AFF', borderRadius: 2 },
  content: { padding: 24, paddingBottom: 120, maxWidth: 500, alignSelf: 'center' as const, width: '100%' },
  iconRow: { alignItems: 'center' as const, marginTop: 12, marginBottom: 12 },
  iconCircle: { width: 64, height: 64, borderRadius: 32, backgroundColor: 'rgba(0,122,255,0.1)', alignItems: 'center' as const, justifyContent: 'center' as const },
  stepTitle: { fontSize: 22, fontWeight: '800', color: colors.text, textAlign: 'center' as const, marginBottom: 6 },
  stepDesc: { fontSize: 14, color: colors.textSecondary, textAlign: 'center' as const, lineHeight: 20, marginBottom: 20 },
  body: { gap: 4 },
  label: { fontSize: 13, fontWeight: '600', color: colors.text, marginBottom: 4, marginTop: 2 },
  input: { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: 12, paddingHorizontal: 16, paddingVertical: 13, fontSize: 16, color: colors.text, marginBottom: 10 },
  errRow: { flexDirection: 'row' as const, alignItems: 'center' as const, gap: 6, marginTop: -4, marginBottom: 4 },
  errText: { fontSize: 12, color: '#FF3B30' },
  photoArea: { alignSelf: 'center' as const, marginBottom: 4 },
  photoImg: { width: 120, height: 120, borderRadius: 60, borderWidth: 3, borderColor: '#007AFF' },
  photoEmpty: { width: 120, height: 120, borderRadius: 60, borderWidth: 2, borderColor: colors.border, borderStyle: 'dashed' as const, alignItems: 'center' as const, justifyContent: 'center' as const, backgroundColor: colors.card },
  toneRow: { flexDirection: 'row' as const, flexWrap: 'wrap' as const, gap: 8, marginBottom: 8 },
  toneChip: { flexDirection: 'row' as const, alignItems: 'center' as const, gap: 6, paddingHorizontal: 14, paddingVertical: 10, borderRadius: 20, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border },
  toneActive: { backgroundColor: '#007AFF', borderColor: '#007AFF' },
  toneText: { fontSize: 13, fontWeight: '600', color: colors.textSecondary },
  linkRow: { flexDirection: 'row' as const, alignItems: 'center' as const, gap: 10, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: 12, paddingHorizontal: 14, marginBottom: 10 },
  linkInput: { flex: 1, paddingVertical: 13, fontSize: 16, color: colors.text },
  tip: { flexDirection: 'row' as const, alignItems: 'flex-start' as const, gap: 8, padding: 12, backgroundColor: 'rgba(0,122,255,0.06)', borderRadius: 10, marginTop: 8 },
  tipText: { flex: 1, fontSize: 12, color: colors.textSecondary, lineHeight: 16 },
  genBtn: { flexDirection: 'row' as const, alignItems: 'center' as const, justifyContent: 'center' as const, gap: 8, backgroundColor: '#007AFF', paddingVertical: 16, borderRadius: 14, marginBottom: 16 },
  genBtnText: { fontSize: 16, fontWeight: '700', color: '#fff' },
  previewCard: { marginTop: 20, backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: colors.border, overflow: 'hidden' as const },
  previewTitle: { fontSize: 12, fontWeight: '700', color: colors.textTertiary, textTransform: 'uppercase' as const, letterSpacing: 1, padding: 12, paddingBottom: 0 },
  previewBody: { alignItems: 'center' as const, padding: 20 },
  previewPhoto: { width: 72, height: 72, borderRadius: 36, marginBottom: 10 },
  previewName: { fontSize: 18, fontWeight: '700', color: colors.text },
  previewRole: { fontSize: 13, color: colors.textSecondary, marginTop: 2 },
  previewBio: { fontSize: 13, color: colors.text, textAlign: 'center' as const, lineHeight: 18, marginTop: 10, paddingHorizontal: 12 },
  previewIcons: { flexDirection: 'row' as const, gap: 12, marginTop: 12 },
  bottom: { flexDirection: 'row' as const, gap: 10, paddingHorizontal: 20, paddingVertical: 14, borderTopWidth: 1, borderTopColor: colors.border, backgroundColor: colors.bg },
  backBtn: { width: 50, height: 50, borderRadius: 14, borderWidth: 1, borderColor: colors.border, alignItems: 'center' as const, justifyContent: 'center' as const, backgroundColor: colors.card },
  nextBtn: { flex: 1, flexDirection: 'row' as const, alignItems: 'center' as const, justifyContent: 'center' as const, gap: 8, backgroundColor: '#007AFF', paddingVertical: 16, borderRadius: 14 },
  nextText: { fontSize: 17, fontWeight: '700', color: '#fff' },
});
