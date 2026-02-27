import React, {
  useState, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Alert,
  Linking,
  Image,
  ActivityIndicator,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as Clipboard from 'expo-clipboard';
import * as ImagePicker from 'expo-image-picker';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';
import VoiceInput from '../../components/VoiceInput';
import { useToast } from '../../components/common/Toast';

const DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];

const DEFAULT_HOURS = {
  monday: { open: '09:00', close: '18:00' },
  tuesday: { open: '09:00', close: '18:00' },
  wednesday: { open: '09:00', close: '18:00' },
  thursday: { open: '09:00', close: '18:00' },
  friday: { open: '09:00', close: '18:00' },
  saturday: { open: '09:00', close: '17:00' },
  sunday: null,
};

export default function StoreProfileScreen() {
  const router = useRouter();
  const { user, isLoading: authLoading } = useAuthStore();
const { showToast } = useToast();
    const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [store, setStore] = useState<any>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    // Wait for auth to finish loading before checking store_id
    if (!authLoading) {
      loadStoreProfile();
    }
  }, [user?.store_id, authLoading]);

  const loadStoreProfile = async () => {
    if (!user?.store_id) {
      setLoading(false);
      return;
    }
    
    try {
      const canEdit = ['super_admin', 'org_admin', 'store_manager'].includes(user.role || '');
      setIsAdmin(canEdit);

      const response = await api.get(`/admin/stores/${user.store_id}`);
      setStore({
        ...response.data,
        business_hours: response.data.business_hours || DEFAULT_HOURS,
        social_links: response.data.social_links || {},
      });
    } catch (error) {
      console.error('Error loading store:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!user?.store_id || !store) return;

    setSaving(true);
    try {
      await api.put(`/admin/stores/${user.store_id}`, store);
      showToast('Account profile updated');
    } catch (error) {
      Alert.alert('Error', 'Failed to save store profile');
    } finally {
      setSaving(false);
    }
  };

  const updateField = (field: string, value: any) => {
    setStore((prev: any) => ({ ...prev, [field]: value }));
  };

  const updateHours = (day: string, field: string, value: string) => {
    setStore((prev: any) => ({
      ...prev,
      business_hours: {
        ...prev.business_hours,
        [day]: prev.business_hours[day] 
          ? { ...prev.business_hours[day], [field]: value }
          : { open: '09:00', close: '18:00', [field]: value }
      }
    }));
  };

  const toggleDayClosed = (day: string) => {
    setStore((prev: any) => ({
      ...prev,
      business_hours: {
        ...prev.business_hours,
        [day]: prev.business_hours[day] ? null : { open: '09:00', close: '18:00' }
      }
    }));
  };

  const updateSocial = (platform: string, value: string) => {
    setStore((prev: any) => ({
      ...prev,
      social_links: {
        ...prev.social_links,
        [platform]: value || null
      }
    }));
  };

  const handleUploadLogo = async () => {
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: true,
        aspect: [1, 1],
        quality: 0.8,
      });
      if (result.canceled || !result.assets?.[0]) return;

      setUploading(true);
      const asset = result.assets[0];

      // Read as blob and upload
      const response = await fetch(asset.uri);
      const blob = await response.blob();
      const formData = new FormData();
      formData.append('file', blob as any, 'logo.png');

      const uploadRes = await api.post(
        `/admin/stores/${user?.store_id}/upload-logo`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );

      if (uploadRes.data?.logo_url) {
        setStore((prev: any) => ({
          ...prev,
          logo_url: uploadRes.data.logo_url,
          logo_avatar_url: uploadRes.data.avatar_url || uploadRes.data.logo_avatar_url,
          logo_thumbnail_url: uploadRes.data.thumbnail_url,
        }));
        showToast('Logo updated!');
      }
    } catch (e) {
      console.error('Upload error:', e);
      Alert.alert('Error', 'Failed to upload logo');
    } finally {
      setUploading(false);
    }
  };

  // Show loading while auth is loading OR store is loading
  if (authLoading || loading) {
    return (
      <View style={styles.container}>
        <Text style={styles.loadingText}>Loading...</Text>
      </View>
    );
  }

  if (!store) {
    return (
      <View style={styles.container}>
        <SafeAreaView edges={['top']}>
          <View style={styles.header}>
            <TouchableOpacity onPress={() => router.back()}>
              <Ionicons name="chevron-back" size={24} color="#007AFF" />
            </TouchableOpacity>
            <Text style={styles.headerTitle}>Account Profile</Text>
            <View style={{ width: 60 }} />
          </View>
          <Text style={styles.noStoreText}>No account associated with your profile</Text>
        </SafeAreaView>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={{ flex: 1 }}>
        <View style={styles.header}>
          <TouchableOpacity style={styles.backButton} onPress={() => router.back()}>
            <Ionicons name="chevron-back" size={24} color="#007AFF" />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Account Profile</Text>
          {isAdmin && (
            <TouchableOpacity style={styles.saveButton} onPress={handleSave} disabled={saving}>
              <Text style={styles.saveButtonText}>{saving ? 'Saving...' : 'Save'}</Text>
            </TouchableOpacity>
          )}
        </View>

        <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
          {/* Logo Upload */}
          <Text style={styles.sectionTitle}>ACCOUNT LOGO</Text>
          <View style={styles.card}>
            <View style={styles.logoUploadRow}>
              <TouchableOpacity
                style={styles.logoUploadBox}
                onPress={isAdmin ? handleUploadLogo : undefined}
                disabled={uploading}
                data-testid="logo-upload-btn"
              >
                {uploading ? (
                  <ActivityIndicator size="small" color="#C9A962" />
                ) : store.logo_url ? (
                  <Image source={{ uri: store.logo_url }} style={styles.logoPreview} resizeMode="contain" />
                ) : (
                  <View style={styles.logoPlaceholder}>
                    <Ionicons name="camera" size={28} color="#6E6E73" />
                  </View>
                )}
              </TouchableOpacity>
              <View style={styles.logoUploadInfo}>
                <Text style={styles.logoUploadTitle}>
                  {store.logo_url ? 'Change Logo' : 'Upload Logo'}
                </Text>
                <Text style={styles.logoUploadHint}>Square image, max 5MB{'\n'}Used on cards, review pages & emails</Text>
                {isAdmin && (
                  <TouchableOpacity style={styles.logoUploadBtn} onPress={handleUploadLogo} disabled={uploading}>
                    <Ionicons name="cloud-upload" size={16} color="#007AFF" />
                    <Text style={styles.logoUploadBtnText}>{uploading ? 'Uploading...' : 'Choose Image'}</Text>
                  </TouchableOpacity>
                )}
              </View>
            </View>
            {store.logo_avatar_url && (
              <View style={styles.avatarPreviewRow}>
                <Image source={{ uri: store.logo_avatar_url }} style={styles.avatarPreview} />
                <Text style={styles.avatarPreviewLabel}>Avatar (auto-generated)</Text>
              </View>
            )}
          </View>

          {/* Basic Info */}
          <Text style={styles.sectionTitle}>BASIC INFO</Text>
          <View style={styles.card}>
            <Text style={styles.label}>Account Name</Text>
            <TextInput
              style={styles.input}
              value={store.name || ''}
              onChangeText={(text) => updateField('name', text)}
              editable={isAdmin}
              placeholder="Account Name"
              placeholderTextColor="#8E8E93"
            />
            
            <Text style={styles.label}>Phone</Text>
            <TextInput
              style={styles.input}
              value={store.phone || ''}
              onChangeText={(text) => updateField('phone', text)}
              editable={isAdmin}
              placeholder="(555) 123-4567"
              placeholderTextColor="#8E8E93"
              keyboardType="phone-pad"
            />
            
            <Text style={styles.label}>Website</Text>
            <TextInput
              style={styles.input}
              value={store.website || ''}
              onChangeText={(text) => updateField('website', text)}
              editable={isAdmin}
              placeholder="https://yourstore.com"
              placeholderTextColor="#8E8E93"
              autoCapitalize="none"
            />
            
            <Text style={styles.label}>Address</Text>
            <TextInput
              style={styles.input}
              value={store.address || ''}
              onChangeText={(text) => updateField('address', text)}
              editable={isAdmin}
              placeholder="123 Main St"
              placeholderTextColor="#8E8E93"
            />
            
            <View style={styles.row}>
              <View style={{ flex: 2 }}>
                <Text style={styles.label}>City</Text>
                <TextInput
                  style={styles.input}
                  value={store.city || ''}
                  onChangeText={(text) => updateField('city', text)}
                  editable={isAdmin}
                  placeholder="City"
                  placeholderTextColor="#8E8E93"
                />
              </View>
              <View style={{ flex: 1, marginLeft: 12 }}>
                <Text style={styles.label}>State</Text>
                <TextInput
                  style={styles.input}
                  value={store.state || ''}
                  onChangeText={(text) => updateField('state', text)}
                  editable={isAdmin}
                  placeholder="CO"
                  placeholderTextColor="#8E8E93"
                  maxLength={2}
                  autoCapitalize="characters"
                />
              </View>
            </View>
          </View>

          {/* Branding */}
          <Text style={styles.sectionTitle}>BRANDING</Text>
          <View style={styles.card}>
            <Text style={styles.label}>Logo URL</Text>
            <TextInput
              style={styles.input}
              value={store.logo_url || ''}
              onChangeText={(text) => updateField('logo_url', text)}
              editable={isAdmin}
              placeholder="https://yourstore.com/logo.png"
              placeholderTextColor="#8E8E93"
              autoCapitalize="none"
            />
            
            <Text style={styles.label}>Primary Color</Text>
            <TextInput
              style={styles.input}
              value={store.primary_color || '#007AFF'}
              onChangeText={(text) => updateField('primary_color', text)}
              editable={isAdmin}
              placeholder="#007AFF"
              placeholderTextColor="#8E8E93"
            />
          </View>

          {/* Business Hours */}
          <Text style={styles.sectionTitle}>BUSINESS HOURS</Text>
          <Text style={styles.sectionDesc}>AI won't schedule appointments during closed hours</Text>
          <View style={styles.card}>
            {DAYS.map((day) => {
              const hours = store.business_hours?.[day];
              const isClosed = !hours;
              
              return (
                <View key={day} style={styles.dayRow}>
                  <Text style={styles.dayName}>{day.charAt(0).toUpperCase() + day.slice(1)}</Text>
                  
                  {isAdmin && (
                    <TouchableOpacity 
                      style={[styles.closedToggle, isClosed && styles.closedToggleActive]}
                      onPress={() => toggleDayClosed(day)}
                    >
                      <Text style={[styles.closedText, isClosed && styles.closedTextActive]}>
                        {isClosed ? 'Closed' : 'Open'}
                      </Text>
                    </TouchableOpacity>
                  )}
                  
                  {!isClosed ? (
                    <View style={styles.hoursInputs}>
                      <TextInput
                        style={styles.timeInput}
                        value={hours?.open || '09:00'}
                        onChangeText={(text) => updateHours(day, 'open', text)}
                        editable={isAdmin}
                        placeholder="09:00"
                        placeholderTextColor="#8E8E93"
                      />
                      <Text style={styles.timeSeparator}>-</Text>
                      <TextInput
                        style={styles.timeInput}
                        value={hours?.close || '18:00'}
                        onChangeText={(text) => updateHours(day, 'close', text)}
                        editable={isAdmin}
                        placeholder="18:00"
                        placeholderTextColor="#8E8E93"
                      />
                    </View>
                  ) : (
                    !isAdmin && <Text style={styles.closedLabel}>Closed</Text>
                  )}
                </View>
              );
            })}
          </View>

          {/* Social Media */}
          <Text style={styles.sectionTitle}>SOCIAL MEDIA</Text>
          <Text style={styles.sectionDesc}>Links shown on your review page</Text>
          <View style={styles.card}>
            {[
              { key: 'facebook', icon: 'logo-facebook', color: '#1877F2', name: 'Facebook' },
              { key: 'instagram', icon: 'logo-instagram', color: '#E4405F', name: 'Instagram' },
              { key: 'twitter', icon: 'logo-twitter', color: '#1DA1F2', name: 'Twitter/X' },
              { key: 'youtube', icon: 'logo-youtube', color: '#FF0000', name: 'YouTube' },
              { key: 'tiktok', icon: 'logo-tiktok', color: '#000000', name: 'TikTok' },
              { key: 'linkedin', icon: 'logo-linkedin', color: '#0A66C2', name: 'LinkedIn' },
            ].map((social) => (
              <View key={social.key} style={styles.socialRow}>
                <View style={[styles.socialIcon, { backgroundColor: social.color + '20' }]}>
                  <Ionicons name={social.icon as any} size={20} color={social.color} />
                </View>
                <TextInput
                  style={styles.socialInput}
                  value={store.social_links?.[social.key] || ''}
                  onChangeText={(text) => updateSocial(social.key, text)}
                  editable={isAdmin}
                  placeholder={`${social.name} URL`}
                  placeholderTextColor="#8E8E93"
                  autoCapitalize="none"
                />
              </View>
            ))}
          </View>

          {/* Review Page Link */}
          <Text style={styles.sectionTitle}>PUBLIC REVIEW PAGE</Text>
          <View style={styles.card}>
            <Text style={styles.reviewLinkLabel}>Store URL Slug</Text>
            <View style={styles.slugRow}>
              <Text style={styles.slugPrefix}>app.imosapp.com/review/</Text>
              <TextInput
                style={styles.slugInput}
                value={store.slug || ''}
                onChangeText={(text) => {
                  const cleaned = text.toLowerCase().replace(/[^a-z0-9-]/g, '-').replace(/--+/g, '-');
                  setStore({ ...store, slug: cleaned });
                }}
                placeholder="your-store-name"
                placeholderTextColor="#6E6E73"
                autoCapitalize="none"
                data-testid="store-slug-input"
              />
            </View>
            <Text style={styles.slugHint}>Lowercase letters, numbers, and dashes only</Text>

            <Text style={[styles.reviewLinkLabel, { marginTop: 16 }]}>Share this link with customers:</Text>
            <View style={styles.reviewLinkBox}>
              <Text style={styles.reviewLinkUrl} numberOfLines={1}>
                {`https://app.imosapp.com/review/${store.slug || store._id}`}
              </Text>
              <TouchableOpacity 
                style={styles.copyButton}
                onPress={async () => {
                  const url = `https://app.imosapp.com/review/${store.slug || store._id}`;
                  await Clipboard.setStringAsync(url);
                  showToast('Review page link copied to clipboard');
                }}
              >
                <Ionicons name="copy-outline" size={20} color="#007AFF" />
              </TouchableOpacity>
            </View>
            <TouchableOpacity 
              style={styles.previewButton}
              onPress={() => {
                router.push(`/review/${store.slug || store._id}`);
              }}
            >
              <Ionicons name="eye-outline" size={18} color="#FFF" />
              <Text style={styles.previewButtonText}>Preview Review Page</Text>
            </TouchableOpacity>
          </View>

          {/* GMB Sync Placeholder */}
          <Text style={styles.sectionTitle}>GOOGLE MY BUSINESS</Text>
          <View style={styles.card}>
            <View style={styles.gmbPlaceholder}>
              <Ionicons name="logo-google" size={32} color="#4285F4" />
              <Text style={styles.gmbTitle}>Sync from Google</Text>
              <Text style={styles.gmbDesc}>
                Automatically import your business hours and info from Google My Business
              </Text>
              <TouchableOpacity 
                style={styles.gmbButton}
                onPress={() => {
                  Alert.alert(
                    'Coming Soon',
                    'Google My Business sync will be available in a future update. For now, please enter your hours manually above.',
                    [{ text: 'OK' }]
                  );
                }}
              >
                <Text style={styles.gmbButtonText}>Connect Google Account</Text>
              </TouchableOpacity>
            </View>
          </View>

          <View style={{ height: 40 }} />
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
  },
  loadingText: {
    color: '#FFF',
    textAlign: 'center',
    marginTop: 100,
  },
  noStoreText: {
    color: '#8E8E93',
    textAlign: 'center',
    marginTop: 100,
    fontSize: 16,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#1C1C1E',
  },
  backButton: {
    width: 60,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  saveButton: {
    width: 60,
    alignItems: 'flex-end',
  },
  saveButtonText: {
    fontSize: 17,
    color: '#007AFF',
    fontWeight: '600',
  },
  content: {
    flex: 1,
    padding: 16,
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: '#8E8E93',
    marginBottom: 8,
    marginTop: 16,
    letterSpacing: 0.5,
  },
  sectionDesc: {
    fontSize: 12,
    color: '#8E8E93',
    marginBottom: 12,
  },
  card: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
  },
  logoUploadRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
  },
  logoUploadBox: {
    width: 80,
    height: 80,
    borderRadius: 16,
    backgroundColor: '#111',
    borderWidth: 1,
    borderColor: '#2C2C2E',
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  logoPreview: {
    width: 80,
    height: 80,
    borderRadius: 16,
  },
  logoPlaceholder: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  logoUploadInfo: {
    flex: 1,
  },
  logoUploadTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 4,
  },
  logoUploadHint: {
    fontSize: 12,
    color: '#6E6E73',
    lineHeight: 17,
    marginBottom: 10,
  },
  logoUploadBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#007AFF15',
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 8,
    alignSelf: 'flex-start',
  },
  logoUploadBtnText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#007AFF',
  },
  avatarPreviewRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginTop: 14,
    paddingTop: 14,
    borderTopWidth: 1,
    borderTopColor: '#2C2C2E',
  },
  avatarPreview: {
    width: 36,
    height: 36,
    borderRadius: 8,
  },
  avatarPreviewLabel: {
    fontSize: 12,
    color: '#6E6E73',
  },
  label: {
    fontSize: 13,
    color: '#8E8E93',
    marginBottom: 6,
    marginTop: 12,
  },
  input: {
    backgroundColor: '#2C2C2E',
    borderRadius: 10,
    padding: 14,
    fontSize: 15,
    color: '#FFF',
  },
  row: {
    flexDirection: 'row',
  },
  dayRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  dayName: {
    fontSize: 15,
    color: '#FFF',
    width: 100,
  },
  closedToggle: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
    backgroundColor: '#34C75920',
    marginRight: 12,
  },
  closedToggleActive: {
    backgroundColor: '#FF3B3020',
  },
  closedText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#34C759',
  },
  closedTextActive: {
    color: '#FF3B30',
  },
  closedLabel: {
    fontSize: 14,
    color: '#FF3B30',
    marginLeft: 'auto',
  },
  hoursInputs: {
    flexDirection: 'row',
    alignItems: 'center',
    marginLeft: 'auto',
  },
  timeInput: {
    backgroundColor: '#2C2C2E',
    borderRadius: 8,
    padding: 8,
    fontSize: 14,
    color: '#FFF',
    width: 65,
    textAlign: 'center',
  },
  timeSeparator: {
    color: '#8E8E93',
    marginHorizontal: 8,
  },
  socialRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  socialIcon: {
    width: 36,
    height: 36,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  socialInput: {
    flex: 1,
    backgroundColor: '#2C2C2E',
    borderRadius: 10,
    padding: 12,
    fontSize: 14,
    color: '#FFF',
  },
  reviewLinkLabel: {
    fontSize: 14,
    color: '#8E8E93',
    marginBottom: 12,
  },
  slugRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 10,
    paddingHorizontal: 12,
    borderWidth: 1,
    borderColor: '#2C2C2E',
  },
  slugPrefix: {
    fontSize: 12,
    color: '#6E6E73',
  },
  slugInput: {
    flex: 1,
    fontSize: 15,
    color: '#FFF',
    fontWeight: '600',
    paddingVertical: 12,
    paddingHorizontal: 4,
  },
  slugHint: {
    fontSize: 11,
    color: '#6E6E73',
    marginTop: 6,
    marginBottom: 4,
  },
  reviewLinkBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#2C2C2E',
    borderRadius: 10,
    padding: 12,
  },
  reviewLinkUrl: {
    flex: 1,
    fontSize: 14,
    color: '#007AFF',
  },
  copyButton: {
    padding: 8,
  },
  previewButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#007AFF',
    borderRadius: 10,
    padding: 14,
    marginTop: 12,
  },
  previewButtonText: {
    color: '#FFF',
    fontSize: 15,
    fontWeight: '600',
    marginLeft: 8,
  },
  gmbPlaceholder: {
    alignItems: 'center',
    paddingVertical: 20,
  },
  gmbTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
    marginTop: 12,
  },
  gmbDesc: {
    fontSize: 14,
    color: '#8E8E93',
    textAlign: 'center',
    marginTop: 8,
    paddingHorizontal: 20,
    lineHeight: 20,
  },
  gmbButton: {
    backgroundColor: '#4285F420',
    borderRadius: 10,
    paddingHorizontal: 20,
    paddingVertical: 12,
    marginTop: 16,
    borderWidth: 1,
    borderColor: '#4285F4',
  },
  gmbButtonText: {
    color: '#4285F4',
    fontSize: 15,
    fontWeight: '600',
  },
});
