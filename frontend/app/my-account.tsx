import React, { useState, useCallback, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Image,
  ActivityIndicator,
  Platform,
  Linking,
  TextInput,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import { useAuthStore } from '../store/authStore';
import { useThemeStore } from '../store/themeStore';
import { showSimpleAlert, showConfirm } from '../services/alert';
import { WebModal } from '../components/WebModal';
import api from '../services/api';

const PROD_BASE = 'https://app.imosapp.com';

export default function MyAccountScreen() {
  const router = useRouter();
  const { user, setUser } = useAuthStore();
  const colors = useThemeStore((s) => s.colors);
  const [uploading, setUploading] = useState(false);
  const [photoUrl, setPhotoUrl] = useState(user?.photo_url || null);
  const [copiedLink, setCopiedLink] = useState(false);
  const [storeSlug, setStoreSlug] = useState<string | null>(null);
  const [showShareModal, setShowShareModal] = useState(false);
  const [activityPeriod, setActivityPeriod] = useState('month');
  const [activityData, setActivityData] = useState<any>(null);
  const [activityLoading, setActivityLoading] = useState(false);
  const [activityExpanded, setActivityExpanded] = useState(true);
  const [customStartDate, setCustomStartDate] = useState('');
  const [customEndDate, setCustomEndDate] = useState('');
  const [showDatePicker, setShowDatePicker] = useState(false);

  const loadActivity = useCallback(async (period: string, startDate?: string, endDate?: string) => {
    if (!user?._id) return;
    setActivityLoading(true);
    try {
      let url = `/reports/user-activity/${user._id}?period=${period}`;
      if (period === 'custom' && startDate && endDate) {
        url += `&start_date=${startDate}&end_date=${endDate}`;
      }
      const res = await api.get(url);
      setActivityData(res.data);
    } catch (e) {
      console.error('Failed to load activity:', e);
    } finally {
      setActivityLoading(false);
    }
  }, [user?._id]);

  useEffect(() => {
    if (activityPeriod === 'custom' && customStartDate && customEndDate) {
      loadActivity(activityPeriod, customStartDate, customEndDate);
    } else if (activityPeriod !== 'custom') {
      loadActivity(activityPeriod);
    }
  }, [activityPeriod, customStartDate, customEndDate, loadActivity]);

  // Refresh user data when screen focuses
  useFocusEffect(
    useCallback(() => {
      if (user?._id) {
        refreshUserData();
      }
      // Use store_slug from user data (set at login), or fetch it
      if (user?.store_slug) {
        setStoreSlug(user.store_slug);
      } else if (user?.store_id) {
        fetchStoreSlug();
      }
    }, [user?._id, user?.store_slug, user?.store_id])
  );

  const fetchStoreSlug = async () => {
    try {
      const res = await api.get(`/admin/stores/${user?.store_id}`, {
        headers: { 'X-User-ID': user?._id }
      });
      const slug = res.data?.slug;
      if (slug) {
        setStoreSlug(slug);
      } else if (res.data?.name) {
        // Auto-generate from name
        const generated = res.data.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
        setStoreSlug(generated);
      }
    } catch (e) {}
  };

  const getReviewUrl = () => {
    if (!storeSlug) return '';
    const spParam = user?._id ? `?sp=${user._id}` : '';
    return `${PROD_BASE}/review/${storeSlug}${spParam}`;
  };

  const handleCopyReviewLink = async () => {
    const url = getReviewUrl();
    try {
      if (Platform.OS === 'web') {
        if (navigator.clipboard) {
          await navigator.clipboard.writeText(url);
        } else {
          const ta = document.createElement('textarea');
          ta.value = url;
          ta.style.position = 'fixed';
          ta.style.opacity = '0';
          document.body.appendChild(ta);
          ta.select();
          document.execCommand('copy');
          document.body.removeChild(ta);
        }
      }
    } catch {
      try {
        const ta = document.createElement('textarea');
        ta.value = url;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
      } catch {}
    }
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2500);
  };

  const handleShareViaSMS = () => {
    const url = getReviewUrl();
    const msg = `Hey! We'd love your feedback. Leave us a review here: ${url}`;
    if (Platform.OS === 'web') {
      const a = document.createElement('a');
      a.href = `sms:?body=${encodeURIComponent(msg)}`;
      a.target = '_self';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } else {
      Linking.openURL(`sms:?body=${encodeURIComponent(msg)}`);
    }
    setShowShareModal(false);
  };

  const handleShareViaEmail = () => {
    const url = getReviewUrl();
    const subject = 'We\'d love your feedback!';
    const body = `Hi!\n\nThank you for your business. We'd really appreciate it if you could take a moment to leave us a review:\n\n${url}\n\nThank you!`;
    if (Platform.OS === 'web') {
      const a = document.createElement('a');
      a.href = `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
      a.target = '_self';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } else {
      Linking.openURL(`mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`);
    }
    setShowShareModal(false);
  };

  const handlePreviewReviewPage = () => {
    const slug = storeSlug || 'my-store';
    router.push(`/review/${slug}` as any);
    setShowShareModal(false);
  };

  const refreshUserData = async () => {
    try {
      const response = await api.get(`/users/${user?._id}`);
      if (response.data) {
        setPhotoUrl(response.data.photo_url || null);
      }
    } catch (error) {
      console.error('Error refreshing user data:', error);
    }
  };

  const pickImage = async () => {
    try {
      // On web, use native file input for better compatibility
      if (Platform.OS === 'web') {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/*';
        input.onchange = async (e: any) => {
          const file = e.target.files[0];
          if (file) {
            setUploading(true);
            const reader = new FileReader();
            reader.onloadend = async () => {
              const base64Data = reader.result as string;
              await uploadPhotoBase64(base64Data);
            };
            reader.onerror = () => {
              setUploading(false);
              showSimpleAlert('Error', 'Failed to read image file');
            };
            reader.readAsDataURL(file);
          }
        };
        input.click();
        return;
      }

      // Request permissions (native only)
      const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (status !== 'granted') {
        showSimpleAlert('Permission Required', 'Please allow access to your photo library to upload a profile picture.');
        return;
      }

      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: true,
        aspect: [1, 1],
        quality: 0.8,
        base64: true,
      });

      if (!result.canceled && result.assets[0]) {
        await uploadPhoto(result.assets[0]);
      }
    } catch (error) {
      console.error('Error picking image:', error);
      showSimpleAlert('Error', 'Failed to select image');
    }
  };

  // Upload photo from base64 string (for web)
  const uploadPhotoBase64 = async (base64Data: string) => {
    if (!user?._id) return;

    try {
      // Upload to backend
      const response = await api.patch(`/users/${user._id}`, {
        photo_url: base64Data,
      });

      if (response.data) {
        setPhotoUrl(base64Data);
        // Update user in store
        setUser({ ...user, photo_url: base64Data });
        showSimpleAlert('Success', 'Profile photo updated!');
      }
    } catch (error) {
      console.error('Error uploading photo:', error);
      showSimpleAlert('Error', 'Failed to upload photo. Please try again.');
    } finally {
      setUploading(false);
    }
  };

  const takePhoto = async () => {
    try {
      const { status } = await ImagePicker.requestCameraPermissionsAsync();
      if (status !== 'granted') {
        showSimpleAlert('Permission Required', 'Please allow camera access to take a profile picture.');
        return;
      }

      const result = await ImagePicker.launchCameraAsync({
        allowsEditing: true,
        aspect: [1, 1],
        quality: 0.8,
        base64: true,
      });

      if (!result.canceled && result.assets[0]) {
        await uploadPhoto(result.assets[0]);
      }
    } catch (error) {
      console.error('Error taking photo:', error);
      showSimpleAlert('Error', 'Failed to take photo');
    }
  };

  const uploadPhoto = async (asset: ImagePicker.ImagePickerAsset) => {
    if (!user?._id) return;

    setUploading(true);
    try {
      // Convert to base64 data URL
      const base64Data = `data:image/jpeg;base64,${asset.base64}`;
      
      // Upload to backend
      const response = await api.patch(`/users/${user._id}`, {
        photo_url: base64Data,
      });

      if (response.data) {
        setPhotoUrl(base64Data);
        // Update user in store
        setUser({ ...user, photo_url: base64Data });
        showSimpleAlert('Success', 'Profile photo updated!');
      }
    } catch (error) {
      console.error('Error uploading photo:', error);
      showSimpleAlert('Error', 'Failed to upload photo. Please try again.');
    } finally {
      setUploading(false);
    }
  };

  const removePhoto = () => {
    showConfirm(
      'Remove Photo',
      'Are you sure you want to remove your profile photo?',
      async () => {
        if (!user?._id) return;
        
        setUploading(true);
        try {
          await api.patch(`/users/${user._id}`, {
            photo_url: null,
          });
          setPhotoUrl(null);
          setUser({ ...user, photo_url: null });
          showSimpleAlert('Done', 'Profile photo removed');
        } catch (error) {
          showSimpleAlert('Error', 'Failed to remove photo');
        } finally {
          setUploading(false);
        }
      }
    );
  };

  const showPhotoOptions = () => {
    if (Platform.OS === 'web') {
      // On web, just use the file picker
      pickImage();
    } else {
      // On native, show options
      showConfirm(
        'Change Profile Photo',
        'Choose how to update your photo',
        () => takePhoto(),
        () => pickImage(),
        'Take Photo',
        'Choose from Library'
      );
    }
  };

  const getInitials = () => {
    if (!user?.name) return '?';
    return user.name
      .split(' ')
      .map((n) => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  const settingsItems = [
    {
      icon: 'shield-checkmark',
      title: 'Security',
      subtitle: 'Password, Face ID settings',
      color: '#FF3B30',
      onPress: () => router.push('/settings/security'),
    },
    {
      icon: 'notifications',
      title: 'Notifications',
      subtitle: 'Manage alerts & sounds',
      color: '#FF9500',
      onPress: () => showSimpleAlert('Notifications', 'Feature coming soon'),
    },
    {
      icon: 'color-palette',
      title: 'Brand Kit',
      subtitle: 'Colors & email branding',
      color: '#34C759',
      onPress: () => router.push('/settings/brand-kit'),
    },
    {
      icon: 'calendar',
      title: 'Calendar',
      subtitle: 'Connect Google Calendar',
      color: '#007AFF',
      onPress: () => router.push('/settings/calendar'),
    },
    {
      icon: 'git-network',
      title: 'Integrations',
      subtitle: 'API keys & webhooks',
      color: '#5856D6',
      onPress: () => router.push('/settings/integrations'),
    },
  ];

  const upgradeItems = [
    {
      icon: 'rocket',
      title: 'Upgrade Plan',
      subtitle: 'Unlock more features',
      color: '#FFD60A',
      onPress: () => showSimpleAlert('Upgrade', 'Contact support to upgrade your plan'),
    },
    {
      icon: 'gift',
      title: 'Refer a Friend',
      subtitle: 'Earn rewards for referrals',
      color: '#FF2D55',
      onPress: () => showSimpleAlert('Referrals', 'Referral program coming soon'),
    },
  ];

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.bg }]} edges={['top']}>
      {/* Header */}
      <View style={[styles.header, { borderBottomColor: colors.border }]}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton} data-testid="back-button">
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={[styles.headerTitle, { color: colors.text }]}>My Account</Text>
        <View style={{ width: 28 }} />
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent}>
        {/* Profile Photo Section */}
        <View style={[styles.photoSection, { borderBottomColor: colors.border }]}>
          <TouchableOpacity 
            style={styles.photoContainer} 
            onPress={showPhotoOptions}
            disabled={uploading}
            data-testid="profile-photo-button"
          >
            {uploading ? (
              <View style={styles.photoPlaceholder}>
                <ActivityIndicator size="large" color="#007AFF" />
              </View>
            ) : photoUrl ? (
              <Image source={{ uri: photoUrl }} style={styles.profilePhoto} />
            ) : (
              <View style={styles.photoPlaceholder}>
                <Text style={styles.photoInitials}>{getInitials()}</Text>
              </View>
            )}
            <View style={[styles.cameraButton, { borderColor: colors.bg }]}>
              <Ionicons name="camera" size={16} color="#FFF" />
            </View>
          </TouchableOpacity>
          
          <Text style={[styles.userName, { color: colors.text }]}>{user?.name || 'Guest'}</Text>
          <Text style={[styles.userEmail, { color: colors.textSecondary }]}>{user?.email || ''}</Text>
          
          {user?.role && user.role !== 'user' && (
            <View style={styles.roleBadge}>
              <Ionicons name="shield-checkmark" size={14} color="#34C759" />
              <Text style={styles.roleText}>
                {user.role === 'super_admin' ? 'Super Admin' : 
                 user.role === 'org_admin' ? 'Org Admin' : 
                 user.role === 'store_manager' ? 'Manager' : 'User'}
              </Text>
            </View>
          )}

          {/* Photo action buttons - only show when photo exists */}
          {photoUrl && (
            <View style={styles.photoActions}>
              <TouchableOpacity style={styles.photoActionBtn} onPress={showPhotoOptions}>
                <Ionicons name="refresh" size={18} color="#007AFF" />
                <Text style={styles.photoActionText}>Change</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.photoActionBtn} onPress={removePhoto}>
                <Ionicons name="trash" size={18} color="#FF3B30" />
                <Text style={[styles.photoActionText, { color: '#FF3B30' }]}>Remove</Text>
              </TouchableOpacity>
            </View>
          )}
        </View>

        {/* Quick Actions - Tile Rows */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.textTertiary }]}>Quick Actions</Text>
          <View style={styles.tileRow}>
            <TouchableOpacity
              style={[styles.tileBtnThird, { backgroundColor: colors.card }]}
              onPress={() => router.push('/settings/store-profile' as any)}
              data-testid="quick-action-account-setup"
            >
              <View style={[styles.tileIcon, { backgroundColor: '#34C75920' }]}>
                <Ionicons name="storefront" size={20} color="#34C759" />
              </View>
              <Text style={[styles.tileLabel, { color: colors.textSecondary }]}>Account Setup</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.tileBtnThird, { backgroundColor: colors.card }]}
              onPress={() => router.push('/settings/brand-kit' as any)}
              data-testid="quick-action-brand-kit"
            >
              <View style={[styles.tileIcon, { backgroundColor: '#C9A96220' }]}>
                <Ionicons name="color-palette" size={20} color="#C9A962" />
              </View>
              <Text style={[styles.tileLabel, { color: colors.textSecondary }]}>Brand Kit</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.tileBtnThird, { backgroundColor: colors.card }]}
              onPress={() => router.push('/settings/review-links' as any)}
              data-testid="quick-action-review-links"
            >
              <View style={[styles.tileIcon, { backgroundColor: '#FFD60A20' }]}>
                <Ionicons name="star" size={20} color="#FFD60A" />
              </View>
              <Text style={[styles.tileLabel, { color: colors.textSecondary }]}>Review Links</Text>
            </TouchableOpacity>
          </View>
          <View style={[styles.tileRow, { marginTop: 8 }]}>
            <TouchableOpacity
              style={[styles.tileBtnThird, { backgroundColor: colors.card }]}
              onPress={() => router.push('/admin/brand-assets' as any)}
              data-testid="quick-action-brand-assets"
            >
              <View style={[styles.tileIcon, { backgroundColor: '#AF52DE20' }]}>
                <Ionicons name="images" size={20} color="#AF52DE" />
              </View>
              <Text style={[styles.tileLabel, { color: colors.textSecondary }]}>Brand Assets</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.tileBtnThird, { backgroundColor: colors.card }]}
              onPress={() => router.push('/settings/review-approvals' as any)}
              data-testid="quick-action-review-approvals"
            >
              <View style={[styles.tileIcon, { backgroundColor: '#AF52DE20' }]}>
                <Ionicons name="chatbubbles" size={20} color="#FF9500" />
              </View>
              <Text style={[styles.tileLabel, { color: colors.textSecondary }]}>Approvals</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.tileBtnThird}
              onPress={() => router.push('/settings/my-profile' as any)}
              data-testid="quick-action-edit-digital-card"
            >
              <View style={[styles.tileIcon, { backgroundColor: '#007AFF20' }]}>
                <Ionicons name="create" size={20} color="#007AFF" />
              </View>
              <Text style={styles.tileLabel}>Edit Card</Text>
            </TouchableOpacity>
          </View>

          {/* Leaderboard Quick Action */}
          <TouchableOpacity
            style={[styles.shareReviewBtn, { borderColor: '#FFD70030' }]}
            onPress={() => router.push('/leaderboard')}
            data-testid="quick-action-leaderboard"
          >
            <Ionicons name="trophy" size={18} color="#FFD700" />
            <Text style={[styles.shareReviewBtnText, { color: '#FFD700' }]}>Leaderboard</Text>
            <Ionicons name="arrow-forward" size={16} color="#FFD700" />
          </TouchableOpacity>
        </View>

        {/* My Activity Dashboard */}
        <View style={styles.section}>
          <TouchableOpacity
            style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}
            onPress={() => setActivityExpanded(!activityExpanded)}
            data-testid="activity-toggle"
          >
            <Text style={styles.sectionTitle}>My Activity</Text>
            <Ionicons name={activityExpanded ? 'chevron-up' : 'chevron-down'} size={18} color="#8E8E93" />
          </TouchableOpacity>

          {activityExpanded && (
            <View>
              {/* Period Selector */}
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 14 }}>
                <View style={{ flexDirection: 'row', gap: 6 }}>
                  {[
                    { key: 'today', label: 'Today' },
                    { key: 'week', label: 'This Week' },
                    { key: 'month', label: 'This Month' },
                    { key: 'year', label: 'This Year' },
                    { key: 'all_time', label: 'All Time' },
                    { key: 'custom', label: 'Custom' },
                  ].map(p => (
                    <TouchableOpacity
                      key={p.key}
                      onPress={() => {
                        setActivityPeriod(p.key);
                        if (p.key === 'custom') {
                          setShowDatePicker(true);
                        } else {
                          setShowDatePicker(false);
                        }
                      }}
                      style={{
                        paddingHorizontal: 14,
                        paddingVertical: 7,
                        borderRadius: 18,
                        backgroundColor: activityPeriod === p.key ? '#C9A962' : '#1C1C1E',
                      }}
                      data-testid={`activity-period-${p.key}`}
                    >
                      <Text style={{
                        fontSize: 13,
                        fontWeight: '600',
                        color: activityPeriod === p.key ? '#000' : '#8E8E93',
                      }}>{p.label}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </ScrollView>

              {/* Custom Date Range Picker */}
              {showDatePicker && activityPeriod === 'custom' && (
                <View style={{
                  backgroundColor: '#1C1C1E',
                  borderRadius: 12,
                  padding: 14,
                  marginBottom: 14,
                  gap: 10,
                }}>
                  <Text style={{ fontSize: 12, fontWeight: '700', color: '#8E8E93', letterSpacing: 0.5, textTransform: 'uppercase' }}>
                    Custom Date Range
                  </Text>
                  <View style={{ flexDirection: 'row', gap: 10 }}>
                    <View style={{ flex: 1 }}>
                      <Text style={{ fontSize: 11, color: '#6E6E73', marginBottom: 4 }}>Start Date</Text>
                      {Platform.OS === 'web' ? (
                        <input
                          type="date"
                          value={customStartDate}
                          onChange={(e: any) => setCustomStartDate(e.target.value)}
                          data-testid="custom-start-date"
                          style={{
                            backgroundColor: '#2C2C2E',
                            color: '#FFF',
                            border: '1px solid #3A3A3C',
                            borderRadius: 8,
                            padding: '10px 12px',
                            fontSize: 14,
                            width: '100%',
                            colorScheme: 'dark',
                          }}
                        />
                      ) : (
                        <TextInput
                          style={{
                            backgroundColor: '#2C2C2E',
                            borderRadius: 8,
                            padding: 10,
                            color: '#FFF',
                            fontSize: 14,
                            borderWidth: 1,
                            borderColor: '#3A3A3C',
                          }}
                          placeholder="YYYY-MM-DD"
                          placeholderTextColor="#6E6E73"
                          value={customStartDate}
                          onChangeText={setCustomStartDate}
                          data-testid="custom-start-date"
                        />
                      )}
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={{ fontSize: 11, color: '#6E6E73', marginBottom: 4 }}>End Date</Text>
                      {Platform.OS === 'web' ? (
                        <input
                          type="date"
                          value={customEndDate}
                          onChange={(e: any) => setCustomEndDate(e.target.value)}
                          data-testid="custom-end-date"
                          style={{
                            backgroundColor: '#2C2C2E',
                            color: '#FFF',
                            border: '1px solid #3A3A3C',
                            borderRadius: 8,
                            padding: '10px 12px',
                            fontSize: 14,
                            width: '100%',
                            colorScheme: 'dark',
                          }}
                        />
                      ) : (
                        <TextInput
                          style={{
                            backgroundColor: '#2C2C2E',
                            borderRadius: 8,
                            padding: 10,
                            color: '#FFF',
                            fontSize: 14,
                            borderWidth: 1,
                            borderColor: '#3A3A3C',
                          }}
                          placeholder="YYYY-MM-DD"
                          placeholderTextColor="#6E6E73"
                          value={customEndDate}
                          onChangeText={setCustomEndDate}
                          data-testid="custom-end-date"
                        />
                      )}
                    </View>
                  </View>
                  {customStartDate && customEndDate && (
                    <Text style={{ fontSize: 12, color: '#C9A962', textAlign: 'center' }}>
                      Showing data from {customStartDate} to {customEndDate}
                    </Text>
                  )}
                </View>
              )}

              {activityLoading ? (
                <View style={{ padding: 24, alignItems: 'center' }}>
                  <ActivityIndicator size="small" color="#C9A962" />
                </View>
              ) : activityData ? (
                <View>
                  {/* Summary Banner */}
                  <View style={{
                    backgroundColor: '#1C1C1E',
                    borderRadius: 12,
                    padding: 16,
                    marginBottom: 10,
                    flexDirection: 'row',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                  }}>
                    <View>
                      <Text style={{ fontSize: 28, fontWeight: '800', color: '#FFF' }}>
                        {activityData.summary?.total_touchpoints || 0}
                      </Text>
                      <Text style={{ fontSize: 13, color: '#8E8E93', marginTop: 2 }}>Total Touchpoints</Text>
                    </View>
                    {activityData.summary?.trend_pct !== 0 && activityData.summary?.prev_total > 0 && (
                      <View style={{
                        flexDirection: 'row',
                        alignItems: 'center',
                        gap: 4,
                        backgroundColor: activityData.summary.trend_pct > 0 ? '#34C75920' : '#FF3B3020',
                        paddingHorizontal: 10,
                        paddingVertical: 5,
                        borderRadius: 12,
                      }}>
                        <Ionicons
                          name={activityData.summary.trend_pct > 0 ? 'trending-up' : 'trending-down'}
                          size={16}
                          color={activityData.summary.trend_pct > 0 ? '#34C759' : '#FF3B30'}
                        />
                        <Text style={{
                          fontSize: 13,
                          fontWeight: '700',
                          color: activityData.summary.trend_pct > 0 ? '#34C759' : '#FF3B30',
                        }}>
                          {activityData.summary.trend_pct > 0 ? '+' : ''}{activityData.summary.trend_pct}%
                        </Text>
                      </View>
                    )}
                  </View>

                  {/* Category Grid */}
                  <View style={{ flexDirection: 'row', gap: 8, marginBottom: 8 }}>
                    <View style={[actStyles.statCard, { backgroundColor: colors.card }]}>
                      <View style={[actStyles.statIcon, { backgroundColor: '#007AFF20' }]}>
                        <Ionicons name="chatbubble" size={18} color="#007AFF" />
                      </View>
                      <Text style={[actStyles.statNum, { color: colors.text }]}>{activityData.communication?.texts_sent || 0}</Text>
                      <Text style={[actStyles.statLabel, { color: colors.textTertiary }]}>Texts Sent</Text>
                    </View>
                    <View style={[actStyles.statCard, { backgroundColor: colors.card }]}>
                      <View style={[actStyles.statIcon, { backgroundColor: '#5856D620' }]}>
                        <Ionicons name="mail" size={18} color="#5856D6" />
                      </View>
                      <Text style={[actStyles.statNum, { color: colors.text }]}>{activityData.communication?.emails_sent || 0}</Text>
                      <Text style={[actStyles.statLabel, { color: colors.textTertiary }]}>Emails Sent</Text>
                    </View>
                    <View style={[actStyles.statCard, { backgroundColor: colors.card }]}>
                      <View style={[actStyles.statIcon, { backgroundColor: '#34C75920' }]}>
                        <Ionicons name="call" size={18} color="#34C759" />
                      </View>
                      <Text style={[actStyles.statNum, { color: colors.text }]}>{activityData.communication?.calls_placed || 0}</Text>
                      <Text style={[actStyles.statLabel, { color: colors.textTertiary }]}>Calls</Text>
                    </View>
                  </View>

                  <View style={{ flexDirection: 'row', gap: 8, marginBottom: 8 }}>
                    <View style={[actStyles.statCard, { backgroundColor: colors.card }]}>
                      <View style={[actStyles.statIcon, { backgroundColor: '#C9A96220' }]}>
                        <Ionicons name="person-circle" size={18} color="#C9A962" />
                      </View>
                      <Text style={[actStyles.statNum, { color: colors.text }]}>{activityData.sharing?.digital_cards || 0}</Text>
                      <Text style={[actStyles.statLabel, { color: colors.textTertiary }]}>Cards Shared</Text>
                    </View>
                    <View style={[actStyles.statCard, { backgroundColor: colors.card }]}>
                      <View style={[actStyles.statIcon, { backgroundColor: '#FFD60A20' }]}>
                        <Ionicons name="star" size={18} color="#FFD60A" />
                      </View>
                      <Text style={[actStyles.statNum, { color: colors.text }]}>{activityData.sharing?.review_links || 0}</Text>
                      <Text style={[actStyles.statLabel, { color: colors.textTertiary }]}>Reviews Shared</Text>
                    </View>
                    <View style={[actStyles.statCard, { backgroundColor: colors.card }]}>
                      <View style={[actStyles.statIcon, { backgroundColor: '#FF950020' }]}>
                        <Ionicons name="gift" size={18} color="#FF9500" />
                      </View>
                      <Text style={[actStyles.statNum, { color: colors.text }]}>{activityData.sharing?.congrats_cards || 0}</Text>
                      <Text style={[actStyles.statLabel, { color: colors.textTertiary }]}>Congrats Sent</Text>
                    </View>
                  </View>

                  {/* Engagement & Contacts Row */}
                  <View style={{ flexDirection: 'row', gap: 8 }}>
                    <View style={[actStyles.statCard, { flex: 1 }]}>
                      <View style={[actStyles.statIcon, { backgroundColor: '#FF375F20' }]}>
                        <Ionicons name="finger-print" size={18} color="#FF375F" />
                      </View>
                      <Text style={[actStyles.statNum, { color: colors.text }]}>{activityData.engagement?.total_clicks + (activityData.engagement?.review_clicks || 0) || 0}</Text>
                      <Text style={[actStyles.statLabel, { color: colors.textTertiary }]}>Link Clicks</Text>
                    </View>
                    <View style={[actStyles.statCard, { flex: 1 }]}>
                      <View style={[actStyles.statIcon, { backgroundColor: '#30D15820' }]}>
                        <Ionicons name="people" size={18} color="#30D158" />
                      </View>
                      <Text style={[actStyles.statNum, { color: colors.text }]}>{activityData.contacts?.new_contacts || 0}</Text>
                      <Text style={[actStyles.statLabel, { color: colors.textTertiary }]}>New Contacts</Text>
                    </View>
                  </View>

                  {/* Click-Through Rates by Content Type */}
                  {activityData.ctr && (
                    <View style={{ marginTop: 14 }}>
                      <Text style={{ fontSize: 14, fontWeight: '700', color: '#FFF', marginBottom: 10 }}>
                        Click-Through Rates
                      </Text>
                      {[
                        { key: 'digital_card', label: 'Digital Cards', icon: 'person-circle' as const, color: '#C9A962' },
                        { key: 'review_link', label: 'Review Links', icon: 'star' as const, color: '#FFD60A' },
                        { key: 'congrats_card', label: 'Congrats Cards', icon: 'gift' as const, color: '#FF9500' },
                      ].map(item => {
                        const data = activityData.ctr[item.key];
                        if (!data || data.sent === 0) return null;
                        return (
                          <View key={item.key} style={{
                            backgroundColor: '#1C1C1E',
                            borderRadius: 12,
                            padding: 14,
                            marginBottom: 8,
                          }}>
                            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                                <Ionicons name={item.icon} size={16} color={item.color} />
                                <Text style={{ fontSize: 14, fontWeight: '600', color: '#FFF' }}>{item.label}</Text>
                              </View>
                              <View style={{
                                backgroundColor: data.ctr > 0 ? '#34C75920' : '#3A3A3C',
                                paddingHorizontal: 10,
                                paddingVertical: 3,
                                borderRadius: 10,
                              }}>
                                <Text style={{
                                  fontSize: 13,
                                  fontWeight: '700',
                                  color: data.ctr > 0 ? '#34C759' : '#8E8E93',
                                }}>
                                  {Math.min(data.ctr, 100)}% CTR
                                </Text>
                              </View>
                            </View>
                            {/* Stats row */}
                            <View style={{ flexDirection: 'row', gap: 16 }}>
                              <View style={{ flex: 1 }}>
                                <Text style={{ fontSize: 11, color: '#6E6E73', marginBottom: 2 }}>Sent</Text>
                                <Text style={{ fontSize: 16, fontWeight: '700', color: '#FFF' }}>{data.sent}</Text>
                              </View>
                              <View style={{ flex: 1 }}>
                                <Text style={{ fontSize: 11, color: '#6E6E73', marginBottom: 2 }}>Clicks</Text>
                                <Text style={{ fontSize: 16, fontWeight: '700', color: '#FFF' }}>{data.clicks}</Text>
                              </View>
                              <View style={{ flex: 1 }}>
                                <Text style={{ fontSize: 11, color: '#6E6E73', marginBottom: 2 }}>via SMS</Text>
                                <Text style={{ fontSize: 16, fontWeight: '700', color: '#007AFF' }}>{data.by_channel?.sms || 0}</Text>
                              </View>
                              <View style={{ flex: 1 }}>
                                <Text style={{ fontSize: 11, color: '#6E6E73', marginBottom: 2 }}>via Email</Text>
                                <Text style={{ fontSize: 16, fontWeight: '700', color: '#5856D6' }}>{data.by_channel?.email || 0}</Text>
                              </View>
                            </View>
                          </View>
                        );
                      })}
                    </View>
                  )}
                </View>
              ) : null}
            </View>
          )}
        </View>

        {/* Upgrade Section */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Upgrade & Rewards</Text>
          <View style={[styles.menuList, { backgroundColor: colors.card }]}>
            {upgradeItems.map((item, index) => (
              <TouchableOpacity 
                key={index} 
                style={[styles.menuItem, { borderBottomColor: colors.border }, index === upgradeItems.length - 1 && { borderBottomWidth: 0 }]}
                onPress={item.onPress}
              >
                <View style={[styles.menuIcon, { backgroundColor: `${item.color}20` }]}>
                  <Ionicons name={item.icon as any} size={22} color={item.color} />
                </View>
                <View style={styles.menuContent}>
                  <Text style={[styles.menuTitle, { color: colors.text }]}>{item.title}</Text>
                  <Text style={[styles.menuSubtitle, { color: colors.textSecondary }]}>{item.subtitle}</Text>
                </View>
                <Ionicons name="chevron-forward" size={20} color={colors.textTertiary} />
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Settings */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.textTertiary }]}>Settings</Text>
          <View style={[styles.menuList, { backgroundColor: colors.card }]}>
            {settingsItems.map((item, index) => (
              <TouchableOpacity 
                key={index} 
                style={[styles.menuItem, { borderBottomColor: colors.border }, index === settingsItems.length - 1 && { borderBottomWidth: 0 }]}
                onPress={item.onPress}
              >
                <View style={[styles.menuIcon, { backgroundColor: `${item.color}20` }]}>
                  <Ionicons name={item.icon as any} size={22} color={item.color} />
                </View>
                <View style={styles.menuContent}>
                  <Text style={[styles.menuTitle, { color: colors.text }]}>{item.title}</Text>
                  <Text style={[styles.menuSubtitle, { color: colors.textSecondary }]}>{item.subtitle}</Text>
                </View>
                <Ionicons name="chevron-forward" size={20} color={colors.textTertiary} />
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Account Info */}
        <View style={[styles.accountInfo, { backgroundColor: colors.card }]}>
          <View style={[styles.infoRow, { borderBottomColor: colors.border }]}>
            <Text style={[styles.infoLabel, { color: colors.textSecondary }]}>Phone</Text>
            <Text style={[styles.infoValue, { color: colors.text }]}>{user?.mvpline_number || 'Not assigned'}</Text>
          </View>
          <View style={[styles.infoRow, { borderBottomColor: colors.border }]}>
            <Text style={[styles.infoLabel, { color: colors.textSecondary }]}>Organization</Text>
            <Text style={[styles.infoValue, { color: colors.text }]}>{user?.organization_name || 'Independent'}</Text>
          </View>
          <View style={[styles.infoRow, { borderBottomColor: colors.border }]}>
            <Text style={[styles.infoLabel, { color: colors.textSecondary }]}>Store</Text>
            <Text style={[styles.infoValue, { color: colors.text }]}>{user?.store_name || 'N/A'}</Text>
          </View>
        </View>
      </ScrollView>

      {/* Share Review Link Modal */}
      <WebModal visible={showShareModal} animationType="slide" presentationStyle="pageSheet" onRequestClose={() => setShowShareModal(false)}>
        <View style={shareStyles.modal}>
          <View style={shareStyles.header}>
            <TouchableOpacity onPress={() => setShowShareModal(false)}>
              <Ionicons name="close" size={24} color="#8E8E93" />
            </TouchableOpacity>
            <Text style={shareStyles.headerTitle}>Share Review Link</Text>
            <View style={{ width: 24 }} />
          </View>

          {/* Link Preview */}
          <View style={shareStyles.linkBox}>
            <Ionicons name="link" size={18} color="#FFD60A" />
            <Text style={shareStyles.linkText} numberOfLines={2}>
              {getReviewUrl() || 'Loading store link...'}
            </Text>
          </View>

          {!storeSlug && (
            <TouchableOpacity onPress={() => { setShowShareModal(false); router.push('/settings/store-profile' as any); }}>
              <Text style={{ color: '#FF9500', fontSize: 13, textAlign: 'center', marginTop: 12, paddingHorizontal: 16, textDecorationLine: 'underline' }}>
                Store slug not set. Tap here to configure in Store Profile.
              </Text>
            </TouchableOpacity>
          )}

          {/* Action Buttons */}
          <View style={shareStyles.actions}>
            <TouchableOpacity style={shareStyles.actionBtn} onPress={handleCopyReviewLink} data-testid="share-copy-btn">
              <View style={[shareStyles.actionIcon, { backgroundColor: '#FF950020' }]}>
                <Ionicons name={copiedLink ? 'checkmark' : 'copy-outline'} size={24} color={copiedLink ? '#34C759' : '#FF9500'} />
              </View>
              <Text style={shareStyles.actionLabel}>{copiedLink ? 'Copied!' : 'Copy Link'}</Text>
            </TouchableOpacity>

            <TouchableOpacity style={shareStyles.actionBtn} onPress={handleShareViaSMS} data-testid="share-sms-btn">
              <View style={[shareStyles.actionIcon, { backgroundColor: '#34C75920' }]}>
                <Ionicons name="chatbubble-outline" size={24} color="#34C759" />
              </View>
              <Text style={shareStyles.actionLabel}>Text</Text>
            </TouchableOpacity>

            <TouchableOpacity style={shareStyles.actionBtn} onPress={handleShareViaEmail} data-testid="share-email-btn">
              <View style={[shareStyles.actionIcon, { backgroundColor: '#007AFF20' }]}>
                <Ionicons name="mail-outline" size={24} color="#007AFF" />
              </View>
              <Text style={shareStyles.actionLabel}>Email</Text>
            </TouchableOpacity>

            <TouchableOpacity style={shareStyles.actionBtn} onPress={handlePreviewReviewPage} data-testid="share-preview-btn">
              <View style={[shareStyles.actionIcon, { backgroundColor: '#5856D620' }]}>
                <Ionicons name="eye-outline" size={24} color="#5856D6" />
              </View>
              <Text style={shareStyles.actionLabel}>Preview</Text>
            </TouchableOpacity>
          </View>

          {/* Quick message hint */}
          <Text style={shareStyles.hint}>
            Tap Text or Email to send with a pre-written message asking for a review.
          </Text>
        </View>
      </WebModal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#1C1C1E',
  },
  backButton: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFF',
  },
  scrollContent: {
    paddingBottom: 32,
  },
  photoSection: {
    alignItems: 'center',
    paddingVertical: 24,
    borderBottomWidth: 1,
    borderBottomColor: '#1C1C1E',
  },
  photoContainer: {
    position: 'relative',
    marginBottom: 16,
  },
  profilePhoto: {
    width: 120,
    height: 120,
    borderRadius: 28,
    borderWidth: 3,
    borderColor: '#007AFF',
  },
  photoPlaceholder: {
    width: 120,
    height: 120,
    borderRadius: 28,
    backgroundColor: '#007AFF',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 3,
    borderColor: '#007AFF',
  },
  photoInitials: {
    fontSize: 40,
    fontWeight: '700',
    color: '#FFF',
  },
  cameraButton: {
    position: 'absolute',
    bottom: 4,
    right: 4,
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#007AFF',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 3,
    borderColor: '#000',
  },
  userName: {
    fontSize: 24,
    fontWeight: '700',
    color: '#FFF',
    marginBottom: 4,
  },
  userEmail: {
    fontSize: 16,
    color: '#8E8E93',
    marginBottom: 8,
  },
  roleBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#34C75920',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
    marginTop: 4,
  },
  roleText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#34C759',
  },
  photoActions: {
    flexDirection: 'row',
    gap: 16,
    marginTop: 16,
  },
  photoActionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 16,
    paddingVertical: 8,
    backgroundColor: '#1C1C1E',
    borderRadius: 20,
  },
  photoActionText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#007AFF',
  },
  section: {
    marginTop: 24,
    paddingHorizontal: 16,
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#8E8E93',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 12,
  },
  tileRow: {
    flexDirection: 'row',
    gap: 8,
  },
  tileBtnThird: {
    flex: 1,
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
    gap: 8,
  },
  tileIcon: {
    width: 40,
    height: 40,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  tileLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: '#8E8E93',
    textAlign: 'center',
  },
  shareReviewBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    marginTop: 10,
    backgroundColor: '#FFD60A15',
    borderRadius: 12,
    paddingVertical: 14,
    borderWidth: 1,
    borderColor: '#FFD60A30',
  },
  shareReviewBtnText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFD60A',
  },
  menuList: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    overflow: 'hidden',
  },
  menuItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  menuIcon: {
    width: 36,
    height: 36,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  menuContent: {
    flex: 1,
  },
  menuTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 2,
  },
  menuSubtitle: {
    fontSize: 13,
    color: '#8E8E93',
  },
  accountInfo: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  infoLabel: {
    fontSize: 14,
    color: '#8E8E93',
  },
  infoValue: {
    fontSize: 14,
    fontWeight: '600',
    color: '#FFF',
  },
});

const actStyles = StyleSheet.create({
  statCard: {
    flex: 1,
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 12,
    alignItems: 'center',
    gap: 6,
  },
  statIcon: {
    width: 36,
    height: 36,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  statNum: {
    fontSize: 22,
    fontWeight: '800',
    color: '#FFF',
  },
  statLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: '#8E8E93',
    textAlign: 'center',
  },
});


const shareStyles = StyleSheet.create({
  modal: {
    flex: 1,
    backgroundColor: '#000',
    paddingTop: 8,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#1C1C1E',
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  linkBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: '#1C1C1E',
    marginHorizontal: 16,
    marginTop: 24,
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#2C2C2E',
  },
  linkText: {
    flex: 1,
    fontSize: 14,
    color: '#FFF',
    fontFamily: Platform.OS === 'web' ? 'monospace' : undefined,
  },
  actions: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    marginTop: 32,
    paddingHorizontal: 16,
  },
  actionBtn: {
    alignItems: 'center',
    gap: 8,
  },
  actionIcon: {
    width: 56,
    height: 56,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  actionLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: '#8E8E93',
  },
  hint: {
    fontSize: 13,
    color: '#6E6E73',
    textAlign: 'center',
    marginTop: 32,
    paddingHorizontal: 32,
    lineHeight: 18,
  },
});
