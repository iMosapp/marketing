/**
 * ProfileGallery.tsx — Personal photo gallery for My Presence.
 * Lets users upload, view, and delete their own photos.
 * Tap any photo to open a full-screen viewer with swipe navigation.
 */

import React, { useState, useEffect, useRef } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView,
  ActivityIndicator, Modal, Dimensions, Platform,
} from 'react-native';
import { Image } from 'expo-image';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import api from '../../services/api';
import { showSimpleAlert, showConfirm } from '../../services/alert';
import { resolvePhotoUrl } from '../../utils/photoUrl';

const { width: SCREEN_W } = Dimensions.get('window');

interface GalleryPhoto {
  photo_id: string;
  photo_url: string;
  thumbnail_url: string;
  created_at: string;
}

interface Props {
  userId: string;
  colors: Record<string, string>;
  onSetProfilePhoto?: (photoUrl: string) => void;
}

export function ProfileGallery({ userId, colors, onSetProfilePhoto }: Props) {
  const [photos, setPhotos] = useState<GalleryPhoto[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [viewerIndex, setViewerIndex] = useState(-1);
  const scrollRef = useRef<ScrollView>(null);

  // ── Load ──────────────────────────────────────────────────────────────────
  async function load() {
    try {
      const res = await api.get(`/profile/${userId}/gallery`);
      setPhotos(res.data?.photos || []);
    } catch {}
    setLoading(false);
  }
  useEffect(() => { load(); }, [userId]);

  // ── Upload ────────────────────────────────────────────────────────────────
  function handleAdd() {
    if (Platform.OS !== 'web') {
      showSimpleAlert('Upload', 'Photo upload is available on the web version.');
      return;
    }
    // Synchronous trigger — no awaits before input.click() on iOS Safari
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.style.position = 'fixed';
    input.style.top = '-9999px';
    input.style.opacity = '0';
    document.body.appendChild(input);
    input.onchange = async (e: any) => {
      const file = e.target.files?.[0];
      try { document.body.removeChild(input); } catch {}
      if (!file) return;
      setUploading(true);
      try {
        const fd = new FormData();
        fd.append('file', file);
        const res = await api.post(`/profile/${userId}/gallery`, fd, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
        if (res.data?.photo_url) {
          setPhotos(prev => [
            { photo_id: res.data.photo_id, photo_url: res.data.photo_url, thumbnail_url: res.data.thumbnail_url, created_at: new Date().toISOString() },
            ...prev,
          ]);
        }
      } catch (err: any) {
        showSimpleAlert('Error', err?.response?.data?.detail || 'Upload failed');
      } finally {
        setUploading(false);
      }
    };
    input.addEventListener('cancel', () => { try { document.body.removeChild(input); } catch {} });
    input.click();
  }

  // ── Set as profile photo ─────────────────────────────────────────────────
  async function handleSetAsProfile(photo: GalleryPhoto) {
    try {
      await api.patch(`/users/${userId}`, { photo_url: photo.photo_url });
      onSetProfilePhoto?.(photo.photo_url);
      setViewerIndex(-1);
      showSimpleAlert('Done', 'Profile photo updated! Your new photo is live everywhere.');
    } catch {
      showSimpleAlert('Error', 'Could not update profile photo.');
    }
  }

  // ── Delete ────────────────────────────────────────────────────────────────
  function handleDelete(photo: GalleryPhoto) {
    showConfirm('Delete Photo', 'Remove this photo from your gallery?', async () => {
      try {
        await api.delete(`/profile/${userId}/gallery/${photo.photo_id}`);
        setPhotos(prev => prev.filter(p => p.photo_id !== photo.photo_id));
        setViewerIndex(-1);
      } catch {
        showSimpleAlert('Error', 'Could not delete photo.');
      }
    });
  }

  // ── Viewer ────────────────────────────────────────────────────────────────
  function openViewer(idx: number) {
    setViewerIndex(idx);
    setTimeout(() => {
      scrollRef.current?.scrollTo({ x: idx * SCREEN_W, animated: false });
    }, 80);
  }

  // ── Render ────────────────────────────────────────────────────────────────
  const tileSize = Math.floor((Math.min(SCREEN_W, 400) - 32 - 8) / 3);

  return (
    <View style={s.section} data-testid="profile-gallery">
      <View style={s.header}>
        <Ionicons name="images-outline" size={18} color="#C9A962" />
        <Text style={[s.title, { color: colors.text }]}>My Photos</Text>
        <TouchableOpacity
          style={[s.addBtn, { backgroundColor: '#C9A96220', borderColor: '#C9A96240' }]}
          onPress={handleAdd}
          disabled={uploading}
          data-testid="gallery-add-btn"
        >
          {uploading
            ? <ActivityIndicator size="small" color="#C9A962" />
            : <><Ionicons name="add" size={16} color="#C9A962" /><Text style={{ fontSize: 14, color: '#C9A962', fontWeight: '600', marginLeft: 2 }}>Add</Text></>
          }
        </TouchableOpacity>
      </View>

      {loading ? (
        <ActivityIndicator color="#C9A962" style={{ marginTop: 16 }} />
      ) : photos.length === 0 ? (
        <TouchableOpacity
          style={[s.emptyState, { borderColor: colors.border, backgroundColor: colors.card }]}
          onPress={handleAdd}
          data-testid="gallery-empty-btn"
        >
          <Ionicons name="camera-outline" size={28} color={colors.textTertiary} />
          <Text style={[s.emptyText, { color: colors.textTertiary }]}>Add photos to your gallery</Text>
          <Text style={[s.emptyHint, { color: colors.textTertiary }]}>Headshots, events, team photos</Text>
        </TouchableOpacity>
      ) : (
        <View style={s.grid}>
          {photos.map((photo, idx) => (
            <TouchableOpacity
              key={photo.photo_id}
              onPress={() => openViewer(idx)}
              style={[s.tile, { width: tileSize, height: tileSize }]}
              activeOpacity={0.85}
              data-testid={`gallery-tile-${idx}`}
            >
              <Image
                source={{ uri: resolvePhotoUrl(photo.thumbnail_url) || '' }}
                style={{ width: tileSize, height: tileSize }}
                contentFit="cover"
                placeholder={null}
              />
            </TouchableOpacity>
          ))}
        </View>
      )}

      {/* Full-screen viewer */}
      <Modal visible={viewerIndex >= 0} animationType="fade" transparent={false} onRequestClose={() => setViewerIndex(-1)}>
        <SafeAreaView style={s.viewerContainer}>
          {/* Top bar */}
          <View style={s.viewerHeader}>
            <TouchableOpacity onPress={() => setViewerIndex(-1)} style={s.viewerBtn}>
              <Ionicons name="close" size={24} color="#FFF" />
            </TouchableOpacity>
            <Text style={s.viewerCount}>
              {viewerIndex >= 0 ? `${viewerIndex + 1} of ${photos.length}` : ''}
            </Text>
            <TouchableOpacity
              onPress={() => viewerIndex >= 0 && handleDelete(photos[viewerIndex])}
              style={[s.viewerBtn, { backgroundColor: '#FF3B30' }]}
              data-testid="gallery-viewer-delete"
            >
              <Ionicons name="trash-outline" size={20} color="#FFF" />
            </TouchableOpacity>
          </View>

          {/* Bottom action bar */}
          <View style={s.viewerActions}>
            {/* Set as Profile Photo */}
            <TouchableOpacity
              style={s.setProfileBtn}
              onPress={() => viewerIndex >= 0 && handleSetAsProfile(photos[viewerIndex])}
              data-testid="gallery-set-profile-btn"
            >
              <Ionicons name="person-circle-outline" size={18} color="#fff" />
              <Text style={s.setProfileText}>Set as Profile Photo</Text>
            </TouchableOpacity>
          </View>
          <ScrollView
            ref={scrollRef}
            horizontal
            pagingEnabled
            showsHorizontalScrollIndicator={false}
            scrollEventThrottle={16}
            onScroll={(e) => {
              const idx = Math.round(e.nativeEvent.contentOffset.x / SCREEN_W);
              if (idx >= 0 && idx < photos.length && idx !== viewerIndex) {
                setViewerIndex(idx);
              }
            }}
            style={{ flex: 1 }}
          >
            {photos.map((photo, i) => (
              <View key={photo.photo_id} style={{ width: SCREEN_W, flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#000' }}>
                <Image
                  source={{ uri: resolvePhotoUrl(photo.photo_url) || '' }}
                  style={{ width: SCREEN_W, height: SCREEN_W }}
                  contentFit="contain"
                  placeholder={null}
                  transition={200}
                />
              </View>
            ))}
          </ScrollView>
        </SafeAreaView>
      </Modal>
    </View>
  );
}

const s = StyleSheet.create({
  section: { marginTop: 24, paddingHorizontal: 16 },
  header: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 14 },
  title: { fontSize: 17, fontWeight: '700', flex: 1 },
  addBtn: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 20, borderWidth: 1, gap: 2 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 4 },
  tile: { borderRadius: 8, overflow: 'hidden', backgroundColor: '#111' },
  emptyState: { alignItems: 'center', padding: 28, borderRadius: 14, borderWidth: 1, borderStyle: 'dashed', gap: 6 },
  emptyText: { fontSize: 16, fontWeight: '600' },
  emptyHint: { fontSize: 13 },
  viewerActions: { paddingHorizontal: 16, paddingBottom: 8 },
  setProfileBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#C9A962', paddingVertical: 13, borderRadius: 12 },
  setProfileText: { fontSize: 16, fontWeight: '700', color: '#fff' },
  viewerContainer: { flex: 1, backgroundColor: '#000' },
  viewerHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 12, paddingHorizontal: 16 },
  viewerBtn: { width: 40, height: 40, borderRadius: 20, backgroundColor: 'rgba(255,255,255,0.15)', alignItems: 'center', justifyContent: 'center' },
  viewerCount: { fontSize: 16, fontWeight: '600', color: '#FFF' },
});
