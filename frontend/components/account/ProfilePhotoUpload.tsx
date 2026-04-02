/**
 * ProfilePhotoUpload.tsx — Self-contained profile photo upload component.
 *
 * Handles: web file picker, native camera/library, upload progress,
 * error states. Uses the proper multipart pipeline (WebP, thumbnails, CDN).
 */

import React, { useState, useRef } from 'react';
import {
  View, Text, TouchableOpacity, ActivityIndicator, StyleSheet, Platform, Animated,
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

function formatBytes(bytes: number): string {
  if (!bytes || bytes === 0) return '';
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function ProfilePhotoUpload({ user, colors, onPhotoUpdated }: Props) {
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [fileSize, setFileSize] = useState('');
  const [localPreviewUrl, setLocalPreviewUrl] = useState<string | null>(null);
  const progressAnim = useRef(new Animated.Value(0)).current;

  function animateProgress(toValue: number) {
    Animated.timing(progressAnim, {
      toValue,
      duration: 200,
      useNativeDriver: false,
    }).start();
  }

  // ── Helpers ──────────────────────────────────────────────────────────────
  async function uploadFile(file: File | { uri: string; name: string; type: string }, sizeBytes?: number) {
    if (sizeBytes) setFileSize(formatBytes(sizeBytes));
    setUploadProgress(0);
    animateProgress(0);

    const formData = new FormData();
    formData.append('file', file as any);
    // Do NOT set Content-Type manually — let axios auto-set multipart/form-data; boundary=...
    const res = await api.post(`/profile/${user._id}/photo`, formData, {
      onUploadProgress: (evt: any) => {
        const pct = evt.progress != null ? Math.round(evt.progress * 100) : (evt.total ? Math.round((evt.loaded / evt.total) * 100) : 0);
        setUploadProgress(pct);
        animateProgress(pct);
      },
    });
    return res.data?.photo_url as string | null;
  }

  function handleSuccess(url: string) {
    setLocalPreviewUrl(url);
    onPhotoUpdated(url);
    setUploadProgress(0);
    setFileSize('');
  }

  function getErrorMsg(err: any, fallback: string): string {
    const detail = err?.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) return detail.map((d: any) => d.msg || String(d)).join(', ');
    return err?.message || fallback;
  }

  // ── Web: file input ───────────────────────────────────────────────────────
  function pickWeb() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.style.position = 'fixed';
    input.style.top = '-9999px';
    input.style.left = '-9999px';
    input.style.opacity = '0';
    document.body.appendChild(input);

    input.onchange = async (e: any) => {
      const file = e.target.files?.[0];
      try { document.body.removeChild(input); } catch {}
      if (!file) return;
      setUploading(true);
      try {
        const url = await uploadFile(file, file.size);
        if (url) handleSuccess(url);
        else showSimpleAlert('Error', 'Upload succeeded but no URL was returned.');
      } catch (err: any) {
        showSimpleAlert('Error', getErrorMsg(err, 'Failed to upload photo.'));
      } finally {
        setUploading(false);
        setUploadProgress(0);
        setFileSize('');
      }
    };
    input.addEventListener('cancel', () => {
      try { document.body.removeChild(input); } catch {}
    });
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
      const asset = result.assets[0];
      try {
        const ML = await import('expo-media-library');
        const perm = await ML.default.requestPermissionsAsync();
        if (perm.status === 'granted') await ML.default.saveToLibraryAsync(asset.uri);
      } catch {}
      await uploadNativeAsset(asset);
    }
  }

  async function uploadNativeAsset(asset: ImagePicker.ImagePickerAsset) {
    setUploading(true);
    try {
      const uri = asset.uri;
      const mimeType = (asset as any).mimeType || '';
      const isHeic = mimeType.includes('heic') || mimeType.includes('heif')
        || uri.toLowerCase().includes('.heic') || uri.toLowerCase().includes('.heif');
      const ext = isHeic ? 'jpg' : (uri.split('.').pop()?.toLowerCase() || 'jpg');
      const fileType = isHeic ? 'image/jpeg' : (mimeType || `image/${ext === 'jpg' ? 'jpeg' : ext}`);
      const sizeBytes = (asset as any).fileSize || 0;
      const file = { uri, name: `profile.${ext}`, type: fileType };
      const url = await uploadFile(file, sizeBytes);
      if (url) handleSuccess(url);
    } catch (err: any) {
      showSimpleAlert('Error', getErrorMsg(err, 'Failed to upload photo. Please try a JPEG or PNG file.'));
    } finally {
      setUploading(false);
      setUploadProgress(0);
      setFileSize('');
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

  const storePhoto = resolveUserPhotoUrlHiRes(user);
  const currentPhoto = localPreviewUrl || storePhoto;

  return (
    <View style={styles.container}>
      <TouchableOpacity onPress={handlePress} disabled={uploading} activeOpacity={0.8}>
        <View style={styles.avatarWrapper}>
          {currentPhoto ? (
            <Image
              source={{ uri: currentPhoto }}
              style={[styles.avatarImage, uploading && { opacity: 0.6 }]}
              contentFit="cover"
              placeholder={null}
              recyclingKey={currentPhoto}
            />
          ) : (
            <View style={[styles.avatarPlaceholder, { backgroundColor: colors.card }]}>
              <Text style={{ fontSize: 32, fontWeight: '700', color: colors.accent }}>
                {user.name?.split(' ').map((w: string) => w[0]).slice(0, 2).join('') || '?'}
              </Text>
            </View>
          )}

          {/* Upload overlay with progress */}
          {uploading && (
            <View style={styles.uploadOverlay}>
              <Text style={styles.progressPct}>{uploadProgress}%</Text>
              <View style={styles.progressTrack}>
                <Animated.View
                  style={[
                    styles.progressFill,
                    {
                      width: progressAnim.interpolate({
                        inputRange: [0, 100],
                        outputRange: ['0%', '100%'],
                      }),
                    },
                  ]}
                />
              </View>
            </View>
          )}

          <View style={[styles.editBadge, { backgroundColor: uploading ? '#444' : colors.accent }]}>
            {uploading
              ? <ActivityIndicator size="small" color="#fff" />
              : <Ionicons name="camera" size={14} color="#fff" />
            }
          </View>
        </View>
      </TouchableOpacity>

      {/* File size label */}
      {uploading && fileSize ? (
        <Text style={[styles.fileSizeText, { color: colors.textSecondary }]}>
          {uploadProgress < 100 ? `Uploading ${fileSize}...` : 'Processing...'}
        </Text>
      ) : currentPhoto && !uploading ? (
        <TouchableOpacity onPress={handleRemove} style={styles.removeButton}>
          <Text style={[styles.removeText, { color: '#FF3B30' }]}>Remove photo</Text>
        </TouchableOpacity>
      ) : null}
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
  uploadOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    borderRadius: 22,
    backgroundColor: 'rgba(0,0,0,0.65)',
    justifyContent: 'center',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 10,
  },
  progressPct: {
    color: '#C9A962',
    fontSize: 16,
    fontWeight: '700',
  },
  progressTrack: {
    width: '100%',
    height: 4,
    backgroundColor: 'rgba(255,255,255,0.2)',
    borderRadius: 2,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    backgroundColor: '#C9A962',
    borderRadius: 2,
  },
  editBadge: {
    position: 'absolute',
    bottom: -6,
    right: -6,
    width: 36,
    height: 36,
    borderRadius: 12,
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
  fileSizeText: {
    marginTop: 6,
    fontSize: 12,
    fontWeight: '500',
  },
});
