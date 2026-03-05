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

const PROFILE_STEPS = [
  { key: 'photo', title: 'Add Your Headshot', desc: "Let's start with a great photo. This shows up on your digital card and when customers look you up.", icon: 'camera-outline' },
  { key: 'info', title: 'Your Details', desc: 'Add your title and a short bio so customers know who they\'re working with.', icon: 'person-outline' },
  { key: 'social', title: 'Social Links', desc: 'Connect your social accounts so customers can find and follow you.', icon: 'share-social-outline' },
  { key: 'password', title: 'Set Your Password', desc: 'Create a secure password to replace the temporary one.', icon: 'lock-closed-outline' },
];

export default function CompleteProfileScreen() {
  const { colors } = useThemeStore();
  const s = getS(colors);
  const router = useRouter();
  const { user, updateUser } = useAuthStore();

  const [currentStep, setCurrentStep] = useState(0);
  const [saving, setSaving] = useState(false);

  // Photo
  const [photoUrl, setPhotoUrl] = useState(user?.photo_url || '');
  const [photoUploading, setPhotoUploading] = useState(false);

  // Info
  const [title, setTitle] = useState('');
  const [bio, setBio] = useState('');

  // Social
  const [instagram, setInstagram] = useState('');
  const [facebook, setFacebook] = useState('');
  const [linkedin, setLinkedin] = useState('');

  // Password
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [currentPassword, setCurrentPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  const userId = user?._id || '';

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
      } catch { alert('Error uploading photo. Please try again.'); }
      finally { setPhotoUploading(false); }
    };
    input.click();
  };

  const saveProfile = async () => {
    setSaving(true);
    try {
      const profileData: any = {};
      if (title) profileData.title = title;
      if (bio) profileData.bio = bio;
      if (instagram) profileData.social_instagram = instagram;
      if (facebook) profileData.social_facebook = facebook;
      if (linkedin) profileData.social_linkedin = linkedin;

      if (Object.keys(profileData).length > 0) {
        await api.put(`/profile/${userId}`, profileData);
      }
    } catch (e) { console.error('Error saving profile:', e); }
    finally { setSaving(false); }
  };

  const changePassword = async () => {
    if (!newPassword || newPassword.length < 6) { alert('Password must be at least 6 characters'); return false; }
    if (newPassword !== confirmPassword) { alert('Passwords don\'t match'); return false; }
    try {
      await api.post('/auth/change-password', { user_id: userId, current_password: currentPassword, new_password: newPassword });
      return true;
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Error changing password');
      return false;
    }
  };

  const handleNext = async () => {
    setSaving(true);
    try {
      if (currentStep === 0) {
        // Photo step — just continue
        setCurrentStep(1);
      } else if (currentStep === 1) {
        await saveProfile();
        setCurrentStep(2);
      } else if (currentStep === 2) {
        await saveProfile();
        setCurrentStep(3);
      } else if (currentStep === 3) {
        // Password step
        if (newPassword) {
          const ok = await changePassword();
          if (!ok) { setSaving(false); return; }
        }
        await finishOnboarding();
      }
    } catch (e) { console.error(e); }
    finally { setSaving(false); }
  };

  const finishOnboarding = async () => {
    try {
      await api.put(`/profile/${userId}`, { onboarding_complete: true });
      // Update local user state
      updateUser({ onboarding_complete: true });
      const userStr = await AsyncStorage.getItem('user');
      if (userStr) {
        const userData = JSON.parse(userStr);
        userData.onboarding_complete = true;
        await AsyncStorage.setItem('user', JSON.stringify(userData));
      }
      router.replace('/(tabs)/home' as any);
    } catch (e) {
      console.error(e);
      router.replace('/(tabs)/home' as any);
    }
  };

  const handleSkip = () => {
    if (currentStep < PROFILE_STEPS.length - 1) {
      setCurrentStep(currentStep + 1);
    } else {
      finishOnboarding();
    }
  };

  const stepInfo = PROFILE_STEPS[currentStep];
  const progressPct = ((currentStep + 1) / PROFILE_STEPS.length) * 100;

  return (
    <SafeAreaView style={s.container} edges={['top', 'bottom']}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        {/* Header */}
        <View style={s.header}>
          <View style={{ flex: 1 }}>
            <Text style={s.headerTitle}>Complete Your Profile</Text>
            <Text style={s.headerSubtitle}>Step {currentStep + 1} of {PROFILE_STEPS.length}</Text>
          </View>
          <TouchableOpacity onPress={handleSkip} style={s.skipBtn} data-testid="onboarding-skip-btn">
            <Text style={s.skipText}>{currentStep === PROFILE_STEPS.length - 1 ? 'Skip & Finish' : 'Skip'}</Text>
          </TouchableOpacity>
        </View>

        {/* Progress */}
        <View style={s.progressTrack}>
          <View style={[s.progressFill, { width: `${progressPct}%` }]} />
        </View>

        <ScrollView contentContainerStyle={s.content} showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled">
          {/* Step Icon + Title */}
          <View style={s.stepIconRow}>
            <View style={s.stepIconCircle}>
              <Ionicons name={stepInfo.icon as any} size={32} color="#C9A962" />
            </View>
          </View>
          <Text style={s.stepTitle}>{stepInfo.title}</Text>
          <Text style={s.stepDesc}>{stepInfo.desc}</Text>

          {/* Step 0: Photo */}
          {currentStep === 0 && (
            <View style={s.stepBody}>
              <TouchableOpacity onPress={uploadPhoto} activeOpacity={0.7} style={s.photoUploadArea} data-testid="profile-photo-upload">
                {photoUrl ? (
                  <Image source={{ uri: photoUrl }} style={s.photoPreview} />
                ) : (
                  <View style={s.photoPlaceholder}>
                    {photoUploading ? <ActivityIndicator size="large" color="#C9A962" /> :
                    <>
                      <Ionicons name="camera" size={40} color={colors.textTertiary} />
                      <Text style={{ color: colors.textSecondary, marginTop: 8, fontSize: 14 }}>Tap to upload</Text>
                    </>}
                  </View>
                )}
              </TouchableOpacity>
              {photoUrl && (
                <TouchableOpacity onPress={uploadPhoto} style={{ alignSelf: 'center', marginTop: 10 }}>
                  <Text style={{ color: '#007AFF', fontWeight: '600', fontSize: 14 }}>Change Photo</Text>
                </TouchableOpacity>
              )}
              <View style={s.tipBox}>
                <Ionicons name="bulb-outline" size={16} color="#FF9500" />
                <Text style={s.tipText}>Tip: Use a well-lit, professional headshot. Customers see this on your digital card!</Text>
              </View>
            </View>
          )}

          {/* Step 1: Title + Bio */}
          {currentStep === 1 && (
            <View style={s.stepBody}>
              <Text style={s.fieldLabel}>Job Title <Text style={{ color: '#C9A962' }}>*</Text></Text>
              <TextInput style={s.input} placeholder="e.g., Sales Manager, Finance Director" placeholderTextColor={colors.textTertiary}
                value={title} onChangeText={setTitle} data-testid="profile-title-input" />

              <Text style={s.fieldLabel}>Bio</Text>
              <TextInput style={[s.input, { minHeight: 100, textAlignVertical: 'top' }]}
                placeholder="Tell customers about yourself... What makes you great at what you do?"
                placeholderTextColor={colors.textTertiary} value={bio} onChangeText={setBio} multiline data-testid="profile-bio-input" />
              <Text style={{ fontSize: 12, color: colors.textTertiary, textAlign: 'right', marginTop: -8 }}>{bio.length}/250</Text>
            </View>
          )}

          {/* Step 2: Social Links */}
          {currentStep === 2 && (
            <View style={s.stepBody}>
              {[
                { icon: 'logo-instagram', color: '#E1306C', val: instagram, set: setInstagram, ph: '@handle or full URL', label: 'Instagram', tid: 'social-ig' },
                { icon: 'logo-facebook', color: '#1877F2', val: facebook, set: setFacebook, ph: 'Facebook profile URL', label: 'Facebook', tid: 'social-fb' },
                { icon: 'logo-linkedin', color: '#0A66C2', val: linkedin, set: setLinkedin, ph: 'LinkedIn profile URL', label: 'LinkedIn', tid: 'social-li' },
              ].map(soc => (
                <View key={soc.tid} style={{ marginBottom: 16 }}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                    <View style={[s.socialBadge, { backgroundColor: soc.color + '18' }]}>
                      <Ionicons name={soc.icon as any} size={18} color={soc.color} />
                    </View>
                    <Text style={s.fieldLabel}>{soc.label}</Text>
                  </View>
                  <TextInput style={s.input} placeholder={soc.ph} placeholderTextColor={colors.textTertiary}
                    value={soc.val} onChangeText={soc.set} autoCapitalize="none" data-testid={soc.tid} />
                </View>
              ))}
              <View style={s.tipBox}>
                <Ionicons name="bulb-outline" size={16} color="#FF9500" />
                <Text style={s.tipText}>These show up on your digital business card. Skip any you don't use.</Text>
              </View>
            </View>
          )}

          {/* Step 3: Password */}
          {currentStep === 3 && (
            <View style={s.stepBody}>
              <Text style={s.fieldLabel}>Current Password (temporary)</Text>
              <TextInput style={s.input} placeholder="Enter the password you were given" placeholderTextColor={colors.textTertiary}
                value={currentPassword} onChangeText={setCurrentPassword} secureTextEntry={!showPassword} data-testid="current-password" />

              <Text style={s.fieldLabel}>New Password <Text style={{ color: '#C9A962' }}>*</Text></Text>
              <View style={{ position: 'relative' }}>
                <TextInput style={s.input} placeholder="At least 6 characters" placeholderTextColor={colors.textTertiary}
                  value={newPassword} onChangeText={setNewPassword} secureTextEntry={!showPassword} data-testid="new-password" />
                <TouchableOpacity onPress={() => setShowPassword(!showPassword)}
                  style={{ position: 'absolute', right: 14, top: 14 }}>
                  <Ionicons name={showPassword ? 'eye-off' : 'eye'} size={20} color={colors.textTertiary} />
                </TouchableOpacity>
              </View>

              <Text style={s.fieldLabel}>Confirm New Password</Text>
              <TextInput style={s.input} placeholder="Re-enter new password" placeholderTextColor={colors.textTertiary}
                value={confirmPassword} onChangeText={setConfirmPassword} secureTextEntry={!showPassword} data-testid="confirm-password" />

              {newPassword.length > 0 && newPassword.length < 6 && (
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: -4 }}>
                  <Ionicons name="alert-circle" size={14} color="#FF3B30" />
                  <Text style={{ fontSize: 12, color: '#FF3B30' }}>Must be at least 6 characters</Text>
                </View>
              )}
              {confirmPassword.length > 0 && newPassword !== confirmPassword && (
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 4 }}>
                  <Ionicons name="alert-circle" size={14} color="#FF3B30" />
                  <Text style={{ fontSize: 12, color: '#FF3B30' }}>Passwords don't match</Text>
                </View>
              )}
            </View>
          )}
        </ScrollView>

        {/* Bottom Action */}
        <View style={s.bottomBar}>
          {currentStep > 0 && (
            <TouchableOpacity style={s.backBtn} onPress={() => setCurrentStep(currentStep - 1)} data-testid="onboarding-back-btn">
              <Ionicons name="arrow-back" size={20} color={colors.textSecondary} />
            </TouchableOpacity>
          )}
          <TouchableOpacity style={[s.continueBtn, saving && { opacity: 0.6 }]} onPress={handleNext} disabled={saving} data-testid="onboarding-continue-btn">
            {saving ? <ActivityIndicator size="small" color="#000" /> :
            <>
              <Text style={s.continueBtnText}>{currentStep === PROFILE_STEPS.length - 1 ? "Let's Go!" : 'Continue'}</Text>
              <Ionicons name={currentStep === PROFILE_STEPS.length - 1 ? 'rocket' : 'arrow-forward'} size={20} color="#000" />
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
  headerSubtitle: { fontSize: 13, color: colors.textTertiary, marginTop: 2 },
  skipBtn: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border },
  skipText: { fontSize: 14, fontWeight: '600', color: '#FF9500' },
  progressTrack: { height: 4, backgroundColor: colors.border, marginHorizontal: 20, borderRadius: 2 },
  progressFill: { height: 4, backgroundColor: '#C9A962', borderRadius: 2 },
  content: { padding: 24, paddingBottom: 120, maxWidth: 500, alignSelf: 'center', width: '100%' },
  stepIconRow: { alignItems: 'center', marginTop: 20, marginBottom: 16 },
  stepIconCircle: { width: 72, height: 72, borderRadius: 36, backgroundColor: '#C9A96218', alignItems: 'center', justifyContent: 'center' },
  stepTitle: { fontSize: 24, fontWeight: '800', color: colors.text, textAlign: 'center', marginBottom: 8 },
  stepDesc: { fontSize: 15, color: colors.textSecondary, textAlign: 'center', lineHeight: 22, marginBottom: 28 },
  stepBody: { gap: 4 },
  fieldLabel: { fontSize: 14, fontWeight: '600', color: colors.text, marginBottom: 6, marginTop: 4 },
  input: { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: 12, paddingHorizontal: 16, paddingVertical: 14, fontSize: 16, color: colors.text, marginBottom: 12 },
  photoUploadArea: { alignSelf: 'center', marginBottom: 8 },
  photoPreview: { width: 160, height: 160, borderRadius: 80, borderWidth: 4, borderColor: '#C9A962' },
  photoPlaceholder: { width: 160, height: 160, borderRadius: 80, borderWidth: 3, borderColor: colors.border, borderStyle: 'dashed', alignItems: 'center', justifyContent: 'center', backgroundColor: colors.card },
  socialBadge: { width: 34, height: 34, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  tipBox: { flexDirection: 'row', alignItems: 'flex-start', gap: 8, padding: 14, backgroundColor: '#FF950010', borderRadius: 10, marginTop: 16, borderWidth: 1, borderColor: '#FF950030' },
  tipText: { flex: 1, fontSize: 13, color: colors.textSecondary, lineHeight: 18 },
  bottomBar: { flexDirection: 'row', gap: 10, paddingHorizontal: 20, paddingVertical: 14, borderTopWidth: 1, borderTopColor: colors.border, backgroundColor: colors.bg },
  backBtn: { width: 50, height: 50, borderRadius: 14, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.card },
  continueBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#C9A962', paddingVertical: 16, borderRadius: 14 },
  continueBtnText: { fontSize: 17, fontWeight: '700', color: '#000' },
});
