/**
 * ProfilePhotoUpload.tsx — Self-contained profile photo upload component.
 *
 * Handles: web file picker, native camera/library, upload progress,
 * error states. Uses the proper multipart pipeline (WebP, thumbnails, CDN).
 */

import React, { useState } from 'react';
import {
  View, Text, TouchableOpacity, ActivityIndicator, StyleSheet, Platform,
} from 'react-native';
import { Image } from 'expo-image';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import api from '../../services/api';
import { showSimpleAlert, showConfirm } from '../../services/alert';
import { resolveUserPhotoUrlHiRes } from '../../utils/photoUrl';
import { User } from '../../types';

interface Props {
  user: User;
  colors: Record<string, string>;
  onPhotoUpdated: (newPhotoUrl: string | null) => void;
}

export function ProfilePhotoUpload({ user, colors, onPhotoUpdated }: Props) {
  const [uploading, setUploading] = useState(false);

  // ── Helpers ──────────────────────────────────────────────────────────────
  async function uploadFile(file: File | { uri: string; name: string; type: string }) {
    const formData = new FormData();
    formData.append('file', file as any);
    const res = await api.post(`/profile/${user._id}/photo`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data?.photo_url as string | null;
  }

  // ── Web: file input ───────────────────────────────────────────────────────
  function pickWeb() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.onchange = async (e: any) => {
      const file = e.target.files?.[0];
      if (!file) return;
      setUploading(true);
      try {
        const url = await uploadFile(file);
        if (url) onPhotoUpdated(url);
        else showSimpleAlert('Error', 'Upload succeeded but no URL was returned.');
      } catch (err: any) {
        showSimpleAlert('Error', err?.response?.data?.detail || 'Failed to upload photo.');
      } finally {
        setUploading(false);
      }
    };
    input.click();
  }

  // ── Native: library ───────────────────────────────────────────────────────
  async function pickLibrary() {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') {
      showSimpleAlert('Permission Required', 'Allow photo library access to upload a profile picture.');
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: true,
      aspect: [1, 1],
      quality: 0.85,
    });
    if (!result.canceled && result.assets[0]) {
      await uploadNativeAsset(result.assets[0]);
    }
  }

  // ── Native: camera ────────────────────────────────────────────────────────
  async function pickCamera() {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== 'granted') {
      showSimpleAlert('Permission Required', 'Allow camera access to take a profile picture.');
      return;
    }
    const result = await ImagePicker.launchCameraAsync({
      allowsEditing: true,
      aspect: [1, 1],
      quality: 0.85,
    });
    if (!result.canceled && result.assets[0]) {
      await uploadNativeAsset(result.assets[0]);
    }
  }

  async function uploadNativeAsset(asset: ImagePicker.ImagePickerAsset) {
    setUploading(true);
    try {
      const uri = asset.uri;
      const ext = uri.split('.').pop() || 'jpg';
      const file = { uri, name: `profile.${ext}`, type: `image/${ext}` };
      const url = await uploadFile(file);
      if (url) onPhotoUpdated(url);
    } catch (err: any) {
      showSimpleAlert('Error', err?.response?.data?.detail || 'Failed to upload photo.');
    } finally {
      setUploading(false);
    }
  }

  // ── Remove photo ──────────────────────────────────────────────────────────
  function handleRemove() {
    showConfirm(
      'Remove Photo',
      'Remove your profile photo?',
      async () => {
        setUploading(true);
        try {
          await api.patch(`/users/${user._id}`, { photo_url: null });
          onPhotoUpdated(null);
        } catch {
          showSimpleAlert('Error', 'Failed to remove photo.');
        } finally {
          setUploading(false);
        }
      },
    );
  }

  // ── Show options ──────────────────────────────────────────────────────────
  function handlePress() {
    if (Platform.OS === 'web') {
      pickWeb();
      return;
    }
    showConfirm(
      'Change Profile Photo',
      'Choose an option',
      pickLibrary,
      pickCamera,
      'Photo Library',
      'Take Photo',
    );
  }

  // Use hi-res thumbnail for the profile circle — avatar path is too small for retina screens
  const currentPhoto = resolveUserPhotoUrlHiRes(user);

  return (
    <View style={styles.container}>
      <TouchableOpacity onPress={handlePress} disabled={uploading} activeOpacity={0.8}>
        <View style={styles.avatarWrapper}>
          {uploading ? (
            <View style={styles.avatarPlaceholder}>
              <ActivityIndicator size="large" color={colors.accent} />
            </View>
          ) : currentPhoto ? (
            <Image
              source={{ uri: currentPhoto }}
              style={styles.avatarImage}
              contentFit="cover"
              placeholder={null}
            />
          ) : (
            /* Initials fallback — rounded square matching Hub style */
            <View style={[styles.avatarPlaceholder, { backgroundColor: colors.card }]}>
              <Text style={{ fontSize: 32, fontWeight: '700', color: colors.accent }}>
                {user.name?.split(' ').map((w: string) => w[0]).slice(0, 2).join('') || '?'}
              </Text>
            </View>
          )}
          <View style={[styles.editBadge, { backgroundColor: colors.accent }]}>
            <Ionicons name="camera" size={14} color="#fff" />
          </View>
        </View>
      </TouchableOpacity>

      {currentPhoto && !uploading && (
        <TouchableOpacity onPress={handleRemove} style={styles.removeButton}>
          <Text style={[styles.removeText, { color: '#FF3B30' }]}>Remove photo</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    marginBottom: 8,
  },
  avatarWrapper: {
    position: 'relative',
  },
  // Rounded square — matches the Hub profile card shape
  avatarImage: {
    width: 96,
    height: 96,
    borderRadius: 22,
    borderWidth: 2,
    borderColor: '#C9A962',
  },
  avatarPlaceholder: {
    width: 96,
    height: 96,
    borderRadius: 22,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 2,
    borderColor: '#C9A962',
  },
  editBadge: {
    position: 'absolute',
    bottom: -4,
    right: -4,
    width: 28,
    height: 28,
    borderRadius: 10,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 2,
    borderColor: '#000',
  },
  removeButton: {
    marginTop: 8,
  },
  removeText: {
    fontSize: 14,
    fontWeight: '500',
  },
});
