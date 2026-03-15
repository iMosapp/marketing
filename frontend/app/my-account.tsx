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
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as ImagePicker from 'expo-image-picker';
import { useAuthStore } from '../store/authStore';
import { useThemeStore } from '../store/themeStore';
import { showSimpleAlert, showConfirm } from '../services/alert';
import { WebModal } from '../components/WebModal';
import api from '../services/api';

const PROD_BASE = 'https://app.imonsocial.com';

export default function MyAccountScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { user, setUser } = useAuthStore();
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
  const [editingQuickActions, setEditingQuickActions] = useState(false);
  const [toolsExpanded, setToolsExpanded] = useState(false);

  // All available tools & settings — single source of truth, no duplication
  const ALL_TOOLS: { icon: string; label: string; color: string; route: string }[] = [
    { icon: 'storefront', label: 'Store Profile', color: '#34C759', route: '/settings/store-profile' },
    { icon: 'star', label: 'Review Links', color: '#FFD60A', route: '/settings/review-links' },
    { icon: 'chatbubbles', label: 'Showcase Approvals', color: '#FF9500', route: '/settings/showcase-approvals' },
    { icon: 'images', label: 'Brand Assets', color: '#AF52DE', route: '/admin/brand-assets' },
    { icon: 'link', label: 'Edit Link Page', color: '#C9A962', route: '/settings/link-page' },
    { icon: 'paper-plane', label: 'Send Card', color: '#32ADE6', route: '/settings/create-card' },
    { icon: 'sparkles', label: 'Ask Jessi', color: '#C9A962', route: '/jessie' },
    { icon: 'bar-chart', label: 'My Activity', color: '#5AC8FA', route: '/reports/activity' },
    { icon: 'checkmark-done', label: 'Tasks', color: '#34C759', route: '/tasks' },
    { icon: 'stats-chart', label: 'Analytics', color: '#34C759', route: '/analytics' },
    { icon: 'document-text', label: 'Templates', color: '#FFD60A', route: '/settings/templates' },
    { icon: 'trophy', label: 'Leaderboard', color: '#FFD700', route: '/admin/leaderboard' },
    { icon: 'school', label: 'Training Hub', color: '#FF9500', route: '/training-hub' },
    { icon: 'mail', label: 'Email Analytics', color: '#5856D6', route: '/settings/email-analytics' },
    { icon: 'calendar', label: 'Date Triggers', color: '#FF3B30', route: '/settings/date-triggers' },
  ];

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
      icon: 'calendar',
      title: 'Calendar',
      subtitle: 'Connect Google Calendar',
      color: '#007AFF',
      onPress: () => router.push('/settings/calendar'),
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
        <Text style={[styles.headerTitle, { color: colors.text }]}>My Presence</Text>
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
              <Ionicons name="camera" size={16} color={colors.text} />
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
              <TouchableOpacity style={[styles.photoActionBtn, { backgroundColor: colors.card }]} onPress={showPhotoOptions}>
                <Ionicons name="refresh" size={18} color="#007AFF" />
                <Text style={styles.photoActionText}>Change</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.photoActionBtn, { backgroundColor: colors.card }]} onPress={removePhoto}>
                <Ionicons name="trash" size={18} color="#FF3B30" />
                <Text style={[styles.photoActionText, { color: '#FF3B30' }]}>Remove</Text>
              </TouchableOpacity>
            </View>
          )}
        </View>

        {/* ====== MY PRESENCE — Everything you send out ====== */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.textTertiary }]}>My Presence</Text>
          <Text style={{ fontSize: 11, color: colors.textSecondary, marginBottom: 14, marginTop: -6, paddingHorizontal: 2 }}>
            Everything that represents you to customers
          </Text>

          {/* --- My Digital Card --- */}
          <View style={[styles.presenceCard, { backgroundColor: colors.card }]} data-testid="presence-digital-card">
            <TouchableOpacity
              style={[styles.previewPanel, { backgroundColor: '#007AFF08' }]}
              onPress={() => {
                const cardUrl = storeSlug ? `${PROD_BASE}/card/${user?._id}` : '';
                if (cardUrl && Platform.OS === 'web') {
                  window.open(cardUrl, '_blank');
                } else if (cardUrl) {
                  Linking.openURL(cardUrl);
                }
              }}
              activeOpacity={0.8}
              data-testid="card-preview-panel"
            >
              <View style={{ alignItems: 'center' }}>
                <View style={{ width: 52, height: 52, borderRadius: 26, backgroundColor: '#007AFF', alignItems: 'center', justifyContent: 'center', marginBottom: 8 }}>
                  {photoUrl ? (
                    <Image source={{ uri: photoUrl }} style={{ width: 52, height: 52, borderRadius: 26 }} />
                  ) : (
                    <Text style={{ color: '#fff', fontWeight: '700', fontSize: 20 }}>{getInitials()}</Text>
                  )}
                </View>
                <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text }}>{user?.name || 'Your Name'}</Text>
                <Text style={{ fontSize: 11, color: colors.textSecondary, marginTop: 2 }}>Sales Professional</Text>
                <View style={{ flexDirection: 'row', gap: 10, marginTop: 10 }}>
                  {[
                    { icon: 'call', color: '#34C759' },
                    { icon: 'mail', color: '#007AFF' },
                    { icon: 'chatbubble', color: '#FF9500' },
                    { icon: 'globe', color: '#5856D6' },
                  ].map((item, i) => (
                    <View key={i} style={{ width: 30, height: 30, borderRadius: 15, backgroundColor: `${item.color}15`, alignItems: 'center', justifyContent: 'center' }}>
                      <Ionicons name={item.icon as any} size={14} color={item.color} />
                    </View>
                  ))}
                </View>
              </View>
            </TouchableOpacity>
            <View style={styles.presenceHeader}>
              <View style={[styles.presenceIcon, { backgroundColor: '#007AFF20' }]}>
                <Ionicons name="card" size={20} color="#007AFF" />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={[styles.presenceTitle, { color: colors.text }]}>My Digital Card</Text>
                <Text style={[styles.presenceUrl, { color: colors.textTertiary }]} numberOfLines={1}>
                  {user?._id ? `${PROD_BASE}/card/${user._id}` : 'Configure in Account Setup'}
                </Text>
              </View>
            </View>
            <View style={styles.presenceActions}>
              <TouchableOpacity style={[styles.presenceBtn, { backgroundColor: '#007AFF15' }]} onPress={() => {
                const cardUrl = user?._id ? `${PROD_BASE}/card/${user._id}` : '';
                if (cardUrl && Platform.OS === 'web') {
                  window.open(cardUrl, '_blank');
                } else if (cardUrl) {
                  Linking.openURL(cardUrl);
                }
              }} data-testid="card-preview-btn">
                <Ionicons name="eye-outline" size={16} color="#007AFF" />
                <Text style={[styles.presenceBtnText, { color: '#007AFF' }]}>Preview</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.presenceBtn, { backgroundColor: '#34C75915' }]} onPress={() => router.push('/settings/store-profile' as any)} data-testid="card-edit-btn">
                <Ionicons name="create-outline" size={16} color="#34C759" />
                <Text style={[styles.presenceBtnText, { color: '#34C759' }]}>Edit</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.presenceBtn, { backgroundColor: '#FF950015' }]} onPress={() => {
                const url = user?._id ? `${PROD_BASE}/card/${user._id}` : '';
                if (url && Platform.OS === 'web' && navigator.clipboard) {
                  navigator.clipboard.writeText(url);
                  showSimpleAlert('Copied!', 'Digital card link copied to clipboard');
                }
              }} data-testid="card-copy-btn">
                <Ionicons name="copy-outline" size={16} color="#FF9500" />
                <Text style={[styles.presenceBtnText, { color: '#FF9500' }]}>Copy Link</Text>
              </TouchableOpacity>
            </View>
          </View>

          {/* --- My Showcase --- */}
          <View style={[styles.presenceCard, { backgroundColor: colors.card }]} data-testid="presence-showcase">
            <TouchableOpacity
              style={[styles.previewPanel, { backgroundColor: '#34C75908' }]}
              onPress={() => {
                const showcaseUrl = `${PROD_BASE}/showcase/${user?._id}`;
                if (Platform.OS === 'web') {
                  window.open(showcaseUrl, '_blank');
                } else {
                  Linking.openURL(showcaseUrl);
                }
              }}
              activeOpacity={0.8}
              data-testid="showcase-preview-panel"
            >
              <View style={{ alignItems: 'center' }}>
                <View style={{ flexDirection: 'row', gap: 4, marginBottom: 4 }}>
                  {['#007AFF20', '#34C75920', '#FF950020'].map((bg, i) => (
                    <View key={i} style={{ width: 50, height: 50, borderRadius: 8, backgroundColor: bg, alignItems: 'center', justifyContent: 'center' }}>
                      <Ionicons name="camera" size={16} color={['#007AFF', '#34C759', '#FF9500'][i]} />
                    </View>
                  ))}
                </View>
                <View style={{ flexDirection: 'row', gap: 4 }}>
                  {['#5856D620', '#FF2D5520', '#FFD60A20'].map((bg, i) => (
                    <View key={i} style={{ width: 50, height: 50, borderRadius: 8, backgroundColor: bg, alignItems: 'center', justifyContent: 'center' }}>
                      <Ionicons name="camera" size={16} color={['#5856D6', '#FF2D55', '#FFD60A'][i]} />
                    </View>
                  ))}
                </View>
                <Text style={{ fontSize: 10, color: colors.textSecondary, marginTop: 8 }}>Your public portfolio</Text>
              </View>
            </TouchableOpacity>
            <View style={styles.presenceHeader}>
              <View style={[styles.presenceIcon, { backgroundColor: '#34C75920' }]}>
                <Ionicons name="images" size={20} color="#34C759" />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={[styles.presenceTitle, { color: colors.text }]}>My Showcase</Text>
                <Text style={[styles.presenceUrl, { color: colors.textTertiary }]} numberOfLines={1}>
                  {storeSlug ? `${PROD_BASE}/showcase/${user?._id}` : 'Your happy customers page'}
                </Text>
              </View>
            </View>
            <View style={styles.presenceActions}>
              <TouchableOpacity style={[styles.presenceBtn, { backgroundColor: '#34C75915' }]} onPress={() => {
                const showcaseUrl = `${PROD_BASE}/showcase/${user?._id}`;
                if (Platform.OS === 'web') {
                  window.open(showcaseUrl, '_blank');
                } else {
                  Linking.openURL(showcaseUrl);
                }
              }} data-testid="showcase-preview-btn">
                <Ionicons name="eye-outline" size={16} color="#34C759" />
                <Text style={[styles.presenceBtnText, { color: '#34C759' }]}>Preview</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.presenceBtn, { backgroundColor: '#FF950015' }]} onPress={() => router.push('/showroom-manage' as any)} data-testid="showcase-manage-btn">
                <Ionicons name="settings-outline" size={16} color="#FF9500" />
                <Text style={[styles.presenceBtnText, { color: '#FF9500' }]}>Manage</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.presenceBtn, { backgroundColor: '#007AFF15' }]} onPress={() => router.push('/settings/showcase-approvals' as any)} data-testid="showcase-approve-btn">
                <Ionicons name="checkmark-circle-outline" size={16} color="#007AFF" />
                <Text style={[styles.presenceBtnText, { color: '#007AFF' }]}>Approve</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.presenceBtn, { backgroundColor: '#C9A96215' }]} onPress={() => {
                const url = `${PROD_BASE}/showcase/${user?._id}`;
                if (Platform.OS === 'web' && navigator.clipboard) {
                  navigator.clipboard.writeText(url);
                  showSimpleAlert('Copied!', 'Showcase link copied to clipboard');
                }
              }} data-testid="showcase-copy-btn">
                <Ionicons name="copy-outline" size={16} color="#C9A962" />
                <Text style={[styles.presenceBtnText, { color: '#C9A962' }]}>Copy Link</Text>
              </TouchableOpacity>
            </View>
          </View>

          {/* --- Review Link --- */}
          <View style={[styles.presenceCard, { backgroundColor: colors.card }]} data-testid="presence-review-link">
            <TouchableOpacity
              style={[styles.previewPanel, { backgroundColor: '#FFD60A08' }]}
              onPress={handlePreviewReviewPage}
              activeOpacity={0.8}
              data-testid="review-preview-panel"
            >
              <View style={{ alignItems: 'center' }}>
                <View style={{ flexDirection: 'row', gap: 4, marginBottom: 10 }}>
                  {[1,2,3,4,5].map(i => (
                    <Ionicons key={i} name="star" size={22} color="#FFD60A" />
                  ))}
                </View>
                <Text style={{ fontSize: 15, fontWeight: '600', color: colors.text }}>Rate Your Experience</Text>
                <View style={{ flexDirection: 'row', gap: 8, marginTop: 10 }}>
                  <View style={{ paddingHorizontal: 14, paddingVertical: 6, borderRadius: 8, backgroundColor: '#4285F415' }}>
                    <Text style={{ fontSize: 11, fontWeight: '600', color: '#4285F4' }}>Google</Text>
                  </View>
                  <View style={{ paddingHorizontal: 14, paddingVertical: 6, borderRadius: 8, backgroundColor: '#1877F215' }}>
                    <Text style={{ fontSize: 11, fontWeight: '600', color: '#1877F2' }}>Facebook</Text>
                  </View>
                  <View style={{ paddingHorizontal: 14, paddingVertical: 6, borderRadius: 8, backgroundColor: '#AF281415' }}>
                    <Text style={{ fontSize: 11, fontWeight: '600', color: '#AF2814' }}>Yelp</Text>
                  </View>
                </View>
              </View>
            </TouchableOpacity>
            <View style={styles.presenceHeader}>
              <View style={[styles.presenceIcon, { backgroundColor: '#FFD60A20' }]}>
                <Ionicons name="star" size={20} color="#FFD60A" />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={[styles.presenceTitle, { color: colors.text }]}>Review Link</Text>
                <Text style={[styles.presenceUrl, { color: colors.textTertiary }]} numberOfLines={1}>
                  {getReviewUrl() || 'Configure store slug first'}
                </Text>
              </View>
            </View>
            <View style={styles.presenceActions}>
              <TouchableOpacity style={[styles.presenceBtn, { backgroundColor: '#5856D615' }]} onPress={handlePreviewReviewPage} data-testid="review-preview-btn">
                <Ionicons name="eye-outline" size={16} color="#5856D6" />
                <Text style={[styles.presenceBtnText, { color: '#5856D6' }]}>Preview</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.presenceBtn, { backgroundColor: '#34C75915' }]} onPress={() => router.push('/settings/review-links' as any)} data-testid="review-edit-btn">
                <Ionicons name="create-outline" size={16} color="#34C759" />
                <Text style={[styles.presenceBtnText, { color: '#34C759' }]}>Edit Links</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.presenceBtn, { backgroundColor: '#FF950015' }]} onPress={handleCopyReviewLink} data-testid="review-copy-btn">
                <Ionicons name={copiedLink ? 'checkmark' : 'copy-outline'} size={16} color={copiedLink ? '#34C759' : '#FF9500'} />
                <Text style={[styles.presenceBtnText, { color: copiedLink ? '#34C759' : '#FF9500' }]}>{copiedLink ? 'Copied!' : 'Copy Link'}</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.presenceBtn, { backgroundColor: '#FFD60A15' }]} onPress={() => setShowShareModal(true)} data-testid="review-share-btn">
                <Ionicons name="share-outline" size={16} color="#FFD60A" />
                <Text style={[styles.presenceBtnText, { color: '#FFD60A' }]}>Share</Text>
              </TouchableOpacity>
            </View>
          </View>

          {/* --- My Link Page --- */}
          <View style={[styles.presenceCard, { backgroundColor: colors.card }]} data-testid="presence-link-page">
            <TouchableOpacity
              style={[styles.previewPanel, { backgroundColor: '#C9A96208' }]}
              onPress={() => {
                if (Platform.OS === 'web') {
                  window.open(`${PROD_BASE}/l/${user?._id}`, '_blank');
                } else {
                  Linking.openURL(`${PROD_BASE}/l/${user?._id}`);
                }
              }}
              activeOpacity={0.8}
              data-testid="linkpage-preview-panel"
            >
              <View style={{ alignItems: 'center', width: '100%', maxWidth: 200 }}>
                <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: '#C9A96230', alignItems: 'center', justifyContent: 'center', marginBottom: 10 }}>
                  <Ionicons name="person" size={18} color="#C9A962" />
                </View>
                {['Website', 'Instagram', 'Facebook'].map((label, i) => (
                  <View key={i} style={{ width: '100%', paddingVertical: 7, borderRadius: 20, backgroundColor: colors.bg, marginBottom: 4, alignItems: 'center' }}>
                    <Text style={{ fontSize: 11, fontWeight: '600', color: colors.textSecondary }}>{label}</Text>
                  </View>
                ))}
              </View>
            </TouchableOpacity>
            <View style={styles.presenceHeader}>
              <View style={[styles.presenceIcon, { backgroundColor: '#C9A96220' }]}>
                <Ionicons name="link" size={20} color="#C9A962" />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={[styles.presenceTitle, { color: colors.text }]}>My Link Page</Text>
                <Text style={[styles.presenceUrl, { color: colors.textTertiary }]} numberOfLines={1}>
                  {user?._id ? `${PROD_BASE}/l/${user._id}` : 'Your public link tree'}
                </Text>
              </View>
            </View>
            <View style={styles.presenceActions}>
              <TouchableOpacity style={[styles.presenceBtn, { backgroundColor: '#C9A96215' }]} onPress={() => {
                if (Platform.OS === 'web') {
                  window.open(`${PROD_BASE}/l/${user?._id}`, '_blank');
                } else {
                  Linking.openURL(`${PROD_BASE}/l/${user?._id}`);
                }
              }} data-testid="linkpage-preview-btn">
                <Ionicons name="eye-outline" size={16} color="#C9A962" />
                <Text style={[styles.presenceBtnText, { color: '#C9A962' }]}>Preview</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.presenceBtn, { backgroundColor: '#34C75915' }]} onPress={() => router.push('/settings/link-page' as any)} data-testid="linkpage-edit-btn">
                <Ionicons name="create-outline" size={16} color="#34C759" />
                <Text style={[styles.presenceBtnText, { color: '#34C759' }]}>Edit</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.presenceBtn, { backgroundColor: '#FF950015' }]} onPress={() => {
                const url = `${PROD_BASE}/l/${user?._id}`;
                if (Platform.OS === 'web' && navigator.clipboard) {
                  navigator.clipboard.writeText(url);
                  showSimpleAlert('Copied!', 'Link page URL copied to clipboard');
                }
              }} data-testid="linkpage-copy-btn">
                <Ionicons name="copy-outline" size={16} color="#FF9500" />
                <Text style={[styles.presenceBtnText, { color: '#FF9500' }]}>Copy Link</Text>
              </TouchableOpacity>
            </View>
          </View>

          {/* --- My Landing Page --- */}
          <View style={[styles.presenceCard, { backgroundColor: colors.card }]} data-testid="presence-landing-page">
            <TouchableOpacity
              style={[styles.previewPanel, { backgroundColor: '#AF52DE08' }]}
              onPress={() => {
                if (Platform.OS === 'web') {
                  window.open(`${PROD_BASE}/p/${user?._id}`, '_blank');
                } else {
                  Linking.openURL(`${PROD_BASE}/p/${user?._id}`);
                }
              }}
              activeOpacity={0.8}
              data-testid="landing-preview-panel"
            >
              <View style={{ alignItems: 'center' }}>
                <Ionicons name="globe-outline" size={30} color="#AF52DE" style={{ marginBottom: 6 }} />
                <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text }}>Welcome</Text>
                <Text style={{ fontSize: 11, color: colors.textSecondary, marginTop: 2, marginBottom: 10 }}>{user?.name || 'Your Name'}</Text>
                <View style={{ paddingHorizontal: 20, paddingVertical: 8, borderRadius: 20, backgroundColor: '#AF52DE' }}>
                  <Text style={{ fontSize: 11, fontWeight: '600', color: '#fff' }}>Get in Touch</Text>
                </View>
              </View>
            </TouchableOpacity>
            <View style={styles.presenceHeader}>
              <View style={[styles.presenceIcon, { backgroundColor: '#AF52DE20' }]}>
                <Ionicons name="globe-outline" size={20} color="#AF52DE" />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={[styles.presenceTitle, { color: colors.text }]}>My Landing Page</Text>
                <Text style={[styles.presenceUrl, { color: colors.textTertiary }]} numberOfLines={1}>
                  {user?._id ? `${PROD_BASE}/p/${user._id}` : 'Your personal landing page'}
                </Text>
              </View>
            </View>
            <View style={styles.presenceActions}>
              <TouchableOpacity style={[styles.presenceBtn, { backgroundColor: '#AF52DE15' }]} onPress={() => {
                if (Platform.OS === 'web') {
                  window.open(`${PROD_BASE}/p/${user?._id}`, '_blank');
                } else {
                  Linking.openURL(`${PROD_BASE}/p/${user?._id}`);
                }
              }} data-testid="landing-preview-btn">
                <Ionicons name="eye-outline" size={16} color="#AF52DE" />
                <Text style={[styles.presenceBtnText, { color: '#AF52DE' }]}>Preview</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.presenceBtn, { backgroundColor: '#34C75915' }]} onPress={() => router.push('/settings/store-profile' as any)} data-testid="landing-edit-btn">
                <Ionicons name="create-outline" size={16} color="#34C759" />
                <Text style={[styles.presenceBtnText, { color: '#34C759' }]}>Edit</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.presenceBtn, { backgroundColor: '#FF950015' }]} onPress={() => {
                const url = `${PROD_BASE}/p/${user?._id}`;
                if (Platform.OS === 'web' && navigator.clipboard) {
                  navigator.clipboard.writeText(url);
                  showSimpleAlert('Copied!', 'Landing page link copied to clipboard');
                }
              }} data-testid="landing-copy-btn">
                <Ionicons name="copy-outline" size={16} color="#FF9500" />
                <Text style={[styles.presenceBtnText, { color: '#FF9500' }]}>Copy Link</Text>
              </TouchableOpacity>
            </View>
          </View>

          {/* --- AI Persona & Voice — moved to My Profile section above --- */}
        </View>

        {/* ====== MY PROFILE — Top priority section ====== */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.textTertiary }]}>My Profile</Text>
          <View style={[styles.menuList, { backgroundColor: colors.card }]}>
            {[
              { icon: 'person', title: 'Edit Profile & Bio', subtitle: 'Name, bio, photo, social links', color: '#007AFF', route: '/settings/persona' },
              { icon: 'color-palette', title: 'My Brand Kit', subtitle: 'Colors, logo, page theme', color: '#C9A962', route: '/settings/brand-kit' },
              { icon: 'mic', title: 'Voice Training', subtitle: 'Train AI with your voice', color: '#FF3B30', route: '/voice-training' },
            ].map((item, index, arr) => (
              <TouchableOpacity
                key={item.title}
                style={[styles.menuItem, { borderBottomColor: colors.border }, index === arr.length - 1 && { borderBottomWidth: 0 }]}
                onPress={() => router.push(item.route as any)}
                data-testid={`profile-${item.title.toLowerCase().replace(/\s+/g, '-')}`}
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

        {/* ====== ALL TOOLS & SETTINGS — Collapsible, everything in one place ====== */}
        <View style={styles.section}>
          <TouchableOpacity 
            style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: toolsExpanded ? 10 : 0 }}
            onPress={() => setToolsExpanded(!toolsExpanded)}
            data-testid="tools-toggle"
          >
            <Text style={[styles.sectionTitle, { color: colors.textTertiary, marginBottom: 0 }]}>All Tools & Settings</Text>
            <Ionicons name={toolsExpanded ? 'chevron-up' : 'chevron-down'} size={20} color={colors.textTertiary} />
          </TouchableOpacity>

          {toolsExpanded && (
            <View style={[styles.menuList, { backgroundColor: colors.card }]}>
              {ALL_TOOLS.map((item, index, arr) => (
                <TouchableOpacity
                  key={item.label}
                  style={[styles.menuItem, { borderBottomColor: colors.border }, index === arr.length - 1 && { borderBottomWidth: 0 }]}
                  onPress={() => router.push(item.route as any)}
                  data-testid={`tool-${item.label.toLowerCase().replace(/\s+/g, '-')}`}
                >
                  <View style={[styles.menuIcon, { backgroundColor: `${item.color}20` }]}>
                    <Ionicons name={item.icon as any} size={22} color={item.color} />
                  </View>
                  <View style={styles.menuContent}>
                    <Text style={[styles.menuTitle, { color: colors.text }]}>{item.label}</Text>
                  </View>
                  <Ionicons name="chevron-forward" size={20} color={colors.textTertiary} />
                </TouchableOpacity>
              ))}
            </View>
          )}
        </View>

        {/* ====== PERSONAL SETTINGS ====== */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.textTertiary }]}>Personal Settings</Text>
          <View style={[styles.menuList, { backgroundColor: colors.card }]}>
            {[
              { icon: 'shield-checkmark', title: 'Security', subtitle: 'Password & Face ID', color: '#FF3B30', route: '/settings/security' },
              { icon: 'calendar', title: 'Calendar', subtitle: 'Connect Google Calendar', color: '#007AFF', route: '/settings/calendar' },
              { icon: 'download-outline', title: 'Install App', subtitle: 'Add to home screen', color: '#007AFF', action: 'install' },
            ].map((item, index, arr) => (
              <TouchableOpacity
                key={item.title}
                style={[styles.menuItem, { borderBottomColor: colors.border }, index === arr.length - 1 && { borderBottomWidth: 0 }]}
                onPress={() => {
                  if ((item as any).action === 'install') {
                    if (Platform.OS === 'web') window.open('/install.html', '_self');
                    else Linking.openURL('https://app.imonsocial.com/install.html');
                  } else {
                    router.push((item as any).route as any);
                  }
                }}
                data-testid={`settings-${item.title.toLowerCase().replace(/\s+/g, '-')}`}
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

        {/* ====== ACCOUNT INFO ====== */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.textTertiary }]}>Account Info</Text>
          <View style={[styles.accountInfo, { backgroundColor: colors.card }]}>
            {[
              { label: 'Phone', value: user?.mvpline_number || 'Not assigned' },
              { label: 'Organization', value: user?.organization_name || 'Independent' },
              { label: 'Store', value: user?.store_name || 'N/A' },
            ].map((item, i, arr) => (
              <View key={item.label} style={[styles.infoRow, { borderBottomColor: colors.border }, i === arr.length - 1 && { borderBottomWidth: 0 }]}>
                <Text style={[styles.infoLabel, { color: colors.textSecondary }]}>{item.label}</Text>
                <Text style={[styles.infoValue, { color: colors.text }]}>{item.value}</Text>
              </View>
            ))}
          </View>
        </View>

        <View style={{ height: 32 }} />
      </ScrollView>

      {/* Share Review Link Modal */}
      <WebModal visible={showShareModal} animationType="slide" presentationStyle="pageSheet" onRequestClose={() => setShowShareModal(false)}>
        <View style={shareStyles.modal}>
          <View style={shareStyles.header}>
            <TouchableOpacity onPress={() => setShowShareModal(false)}>
              <Ionicons name="close" size={24} color={colors.textSecondary} />
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

const getStyles = (colors: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: undefined,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: colors.card,
  },
  backButton: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: undefined,
  },
  scrollContent: {
    paddingBottom: 32,
  },
  photoSection: {
    alignItems: 'center',
    paddingVertical: 24,
    borderBottomWidth: 1,
    borderBottomColor: colors.card,
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
    color: undefined,
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
    borderColor: colors.border,
  },
  userName: {
    fontSize: 24,
    fontWeight: '700',
    color: undefined,
    marginBottom: 4,
  },
  userEmail: {
    fontSize: 16,
    color: undefined,
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
    backgroundColor: undefined,
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
    color: undefined,
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
    backgroundColor: undefined,
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
    color: undefined,
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
    backgroundColor: undefined,
    borderRadius: 12,
    overflow: 'hidden',
  },
  menuItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 14,
    borderBottomWidth: 1,
    borderBottomColor: undefined,
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
    color: undefined,
    marginBottom: 2,
  },
  menuSubtitle: {
    fontSize: 13,
    color: undefined,
  },
  accountInfo: {
    backgroundColor: undefined,
    borderRadius: 12,
    padding: 16,
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: undefined,
  },
  infoLabel: {
    fontSize: 14,
    color: undefined,
  },
  infoValue: {
    fontSize: 14,
    fontWeight: '600',
    color: undefined,
  },
  // Edit Quick Actions panel
  editPanel: {
    marginHorizontal: 16,
    marginBottom: 16,
    borderRadius: 14,
    borderWidth: 1,
    padding: 14,
  },
  editGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  editItem: {
    width: '23%',
    flexGrow: 1,
    flexBasis: '22%',
    borderRadius: 10,
    paddingVertical: 10,
    alignItems: 'center',
    gap: 4,
    borderWidth: 1,
    borderColor: 'transparent',
  },
  editIconBox: {
    width: 32,
    height: 32,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    position: 'relative' as const,
  },
  editBadge: {
    position: 'absolute' as const,
    top: -4,
    right: -4,
    width: 16,
    height: 16,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  editBadgeText: {
    fontSize: 9,
    fontWeight: '800',
    color: colors.text,
  },
  editLabel: {
    fontSize: 10,
    fontWeight: '600',
    textAlign: 'center' as const,
    paddingHorizontal: 2,
  },
  installBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 14,
    borderRadius: 14,
    borderWidth: 1,
    gap: 12,
  },
  presenceCard: {
    borderRadius: 16,
    overflow: 'hidden' as const,
    marginBottom: 16,
  },
  previewPanel: {
    paddingVertical: 20,
    alignItems: 'center' as const,
    justifyContent: 'center' as const,
    minHeight: 150,
  },
  presenceHeader: {
    flexDirection: 'row' as const,
    alignItems: 'center' as const,
    paddingHorizontal: 14,
    paddingTop: 10,
    paddingBottom: 6,
    gap: 12,
  },
  presenceIcon: {
    width: 36,
    height: 36,
    borderRadius: 10,
    alignItems: 'center' as const,
    justifyContent: 'center' as const,
  },
  presenceTitle: {
    fontSize: 16,
    fontWeight: '600' as const,
  },
  presenceUrl: {
    fontSize: 11,
    marginTop: 2,
  },
  presenceActions: {
    flexDirection: 'row' as const,
    flexWrap: 'wrap' as const,
    gap: 8,
    paddingHorizontal: 14,
    paddingBottom: 14,
    paddingTop: 4,
  },
  presenceBtn: {
    flexDirection: 'row' as const,
    alignItems: 'center' as const,
    gap: 5,
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 20,
  },
  presenceBtnText: {
    fontSize: 12,
    fontWeight: '600' as const,
  },
});

const actStyles = StyleSheet.create({
  statCard: {
    flex: 1,
    backgroundColor: undefined,
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
    color: undefined,
  },
  statLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: undefined,
    textAlign: 'center',
  },
});


const shareStyles = StyleSheet.create({
  modal: {
    flex: 1,
    backgroundColor: undefined,
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
    color: undefined,
  },
  linkBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: undefined,
    marginHorizontal: 16,
    marginTop: 24,
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: undefined,
  },
  linkText: {
    flex: 1,
    fontSize: 14,
    color: undefined,
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
    color: undefined,
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
