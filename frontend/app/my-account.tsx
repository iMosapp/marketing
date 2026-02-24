import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Image,
  ActivityIndicator,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import { useAuthStore } from '../store/authStore';
import { showSimpleAlert, showConfirm } from '../services/alert';
import api from '../services/api';

export default function MyAccountScreen() {
  const router = useRouter();
  const { user, setUser } = useAuthStore();
  const [uploading, setUploading] = useState(false);
  const [photoUrl, setPhotoUrl] = useState(user?.photo_url || null);

  // Refresh user data when screen focuses
  useFocusEffect(
    useCallback(() => {
      if (user?._id) {
        refreshUserData();
      }
    }, [user?._id])
  );

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
      // Request permissions
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

  const quickActions = [
    {
      icon: 'camera',
      title: 'Change Photo',
      subtitle: 'Update your profile picture',
      color: '#007AFF',
      onPress: showPhotoOptions,
    },
    {
      icon: 'card',
      title: 'My Digital Card',
      subtitle: 'Edit bio, socials & preview',
      color: '#5856D6',
      onPress: () => router.push('/settings/my-profile'),
    },
    {
      icon: 'mic',
      title: 'Voice Training',
      subtitle: 'Train AI with your voice',
      color: '#FF3B30',
      onPress: () => router.push('/voice-training'),
    },
    {
      icon: 'sparkles',
      title: 'Train Jessie AI',
      subtitle: 'Chat with your AI assistant',
      color: '#C9A962',
      onPress: () => router.push('/jessie'),
    },
  ];

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
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton} data-testid="back-button">
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>My Account</Text>
        <View style={{ width: 28 }} />
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent}>
        {/* Profile Photo Section */}
        <View style={styles.photoSection}>
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
            <View style={styles.cameraButton}>
              <Ionicons name="camera" size={16} color="#FFF" />
            </View>
          </TouchableOpacity>
          
          <Text style={styles.userName}>{user?.name || 'Guest'}</Text>
          <Text style={styles.userEmail}>{user?.email || ''}</Text>
          
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

          {/* Photo action buttons */}
          <View style={styles.photoActions}>
            {photoUrl ? (
              <>
                <TouchableOpacity style={styles.photoActionBtn} onPress={showPhotoOptions}>
                  <Ionicons name="refresh" size={18} color="#007AFF" />
                  <Text style={styles.photoActionText}>Change</Text>
                </TouchableOpacity>
                <TouchableOpacity style={styles.photoActionBtn} onPress={removePhoto}>
                  <Ionicons name="trash" size={18} color="#FF3B30" />
                  <Text style={[styles.photoActionText, { color: '#FF3B30' }]}>Remove</Text>
                </TouchableOpacity>
              </>
            ) : (
              <TouchableOpacity style={styles.photoActionBtn} onPress={showPhotoOptions}>
                <Ionicons name="add" size={18} color="#007AFF" />
                <Text style={styles.photoActionText}>Add Photo</Text>
              </TouchableOpacity>
            )}
          </View>
        </View>

        {/* Quick Actions */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Quick Actions</Text>
          <View style={styles.quickGrid}>
            {quickActions.map((item, index) => (
              <TouchableOpacity 
                key={index} 
                style={styles.quickCard}
                onPress={item.onPress}
                data-testid={`quick-action-${item.title.toLowerCase().replace(/\s/g, '-')}`}
              >
                <View style={[styles.quickIcon, { backgroundColor: `${item.color}20` }]}>
                  <Ionicons name={item.icon as any} size={24} color={item.color} />
                </View>
                <Text style={styles.quickTitle}>{item.title}</Text>
                <Text style={styles.quickSubtitle}>{item.subtitle}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Upgrade Section */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Upgrade & Rewards</Text>
          <View style={styles.menuList}>
            {upgradeItems.map((item, index) => (
              <TouchableOpacity 
                key={index} 
                style={[styles.menuItem, index === upgradeItems.length - 1 && { borderBottomWidth: 0 }]}
                onPress={item.onPress}
              >
                <View style={[styles.menuIcon, { backgroundColor: `${item.color}20` }]}>
                  <Ionicons name={item.icon as any} size={22} color={item.color} />
                </View>
                <View style={styles.menuContent}>
                  <Text style={styles.menuTitle}>{item.title}</Text>
                  <Text style={styles.menuSubtitle}>{item.subtitle}</Text>
                </View>
                <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Settings */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Settings</Text>
          <View style={styles.menuList}>
            {settingsItems.map((item, index) => (
              <TouchableOpacity 
                key={index} 
                style={[styles.menuItem, index === settingsItems.length - 1 && { borderBottomWidth: 0 }]}
                onPress={item.onPress}
              >
                <View style={[styles.menuIcon, { backgroundColor: `${item.color}20` }]}>
                  <Ionicons name={item.icon as any} size={22} color={item.color} />
                </View>
                <View style={styles.menuContent}>
                  <Text style={styles.menuTitle}>{item.title}</Text>
                  <Text style={styles.menuSubtitle}>{item.subtitle}</Text>
                </View>
                <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Account Info */}
        <View style={styles.accountInfo}>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Phone</Text>
            <Text style={styles.infoValue}>{user?.mvpline_number || 'Not assigned'}</Text>
          </View>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Organization</Text>
            <Text style={styles.infoValue}>{user?.organization_name || 'Independent'}</Text>
          </View>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Store</Text>
            <Text style={styles.infoValue}>{user?.store_name || 'N/A'}</Text>
          </View>
        </View>
      </ScrollView>
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
    borderRadius: 60,
    borderWidth: 3,
    borderColor: '#007AFF',
  },
  photoPlaceholder: {
    width: 120,
    height: 120,
    borderRadius: 60,
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
  quickGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  quickCard: {
    width: '48%',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    alignItems: 'flex-start',
  },
  quickIcon: {
    width: 44,
    height: 44,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
  },
  quickTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 4,
  },
  quickSubtitle: {
    fontSize: 12,
    color: '#8E8E93',
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
    marginTop: 24,
    marginHorizontal: 16,
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
