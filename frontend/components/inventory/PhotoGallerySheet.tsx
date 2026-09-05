import React, { useState } from 'react';
import { View, Text, Modal, Pressable, TouchableOpacity, ActivityIndicator, StyleSheet } from 'react-native';
import { Image } from 'expo-image';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import api from '../../services/api';
import { resolvePhotoUrl } from '../../utils/photoUrl';

const GOLD = '#C9A962';
export const MAX_PHOTOS = 6;

type Photo = { full_path: string; thumb_url: string };
type Props = {
  visible: boolean;
  userId: string;
  item: any | null;
  colors: any;
  onClose: () => void;
  onChanged: (itemId: string, photos: Photo[]) => void;
  onError: (msg: string) => void;
};

export const pickPhotoBase64 = async (): Promise<string | null> => {
  const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ImagePicker.MediaTypeOptions.Images, quality: 0.7, base64: true, allowsEditing: true, aspect: [4, 3] });
  if (result.canceled || !result.assets?.[0]?.base64) return null;
  return `data:image/jpeg;base64,${result.assets[0].base64}`;
};

export const PhotoGallerySheet = ({ visible, userId, item, colors, onClose, onChanged, onError }: Props) => {
  const [busy, setBusy] = useState<string | null>(null);
  if (!item) return null;
  const photos: Photo[] = item.photos || [];
  const base = `/inventory/${userId}/${item._id}/photo`;

  const run = async (key: string, fn: () => Promise<any>) => {
    setBusy(key);
    try { const r = await fn(); onChanged(item._id, r.data.photos || []); }
    catch (e: any) { onError(e?.response?.data?.detail || 'Could not update photos. Please try again.'); }
    finally { setBusy(null); }
  };
  const add = async () => {
    const photo = await pickPhotoBase64();
    if (photo) await run('add', () => api.post(base, { photo }));
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={st.backdrop} onPress={onClose} testID="gallery-backdrop" />
      <View style={[st.sheet, { backgroundColor: colors.card }]} testID="gallery-sheet">
        <View style={st.handle} />
        <Text style={[st.title, { color: colors.text }]} numberOfLines={1}>{item.name}</Text>
        <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 2 }} testID="gallery-count">
          {photos.length} of {MAX_PHOTOS} photos · Jessi texts the first {Math.min(3, Math.max(photos.length, 1))} when a customer asks about this car
        </Text>
        <View style={st.grid}>
          {photos.map((p, i) => (
            <View key={p.full_path} style={st.cell} testID={`gallery-photo-${i}`}>
              <TouchableOpacity onPress={() => i > 0 && run(`cover-${i}`, () => api.put(`${base}/${i}/cover`))} disabled={i === 0 || !!busy} activeOpacity={0.8}>
                <Image source={{ uri: resolvePhotoUrl(p.thumb_url) || '' }} style={[st.img, { backgroundColor: colors.surface }, i === 0 && { borderWidth: 2, borderColor: GOLD }]} contentFit="cover" />
                {busy === `cover-${i}` ? <View style={st.busy}><ActivityIndicator color="#fff" /></View> : null}
              </TouchableOpacity>
              <TouchableOpacity onPress={() => run(`del-${i}`, () => api.delete(`${base}/${i}`))} style={st.del} hitSlop={6} disabled={!!busy} testID={`gallery-delete-${i}`}>
                <Ionicons name="close" size={12} color="#fff" />
              </TouchableOpacity>
              <Text style={{ fontSize: 10, fontWeight: '700', color: i === 0 ? GOLD : colors.textTertiary || colors.textSecondary, marginTop: 4, textAlign: 'center' }}>
                {i === 0 ? 'COVER' : i < 3 ? `SENT #${i + 1}` : 'EXTRA'}
              </Text>
            </View>
          ))}
          {photos.length < MAX_PHOTOS ? (
            <View style={st.cell}>
              <TouchableOpacity onPress={add} disabled={!!busy} style={[st.img, st.addTile, { borderColor: colors.border, backgroundColor: colors.surface }]} testID="gallery-add">
                {busy === 'add' ? <ActivityIndicator color={GOLD} /> : <><Ionicons name="add" size={22} color={colors.textSecondary} /><Text style={{ fontSize: 10, color: colors.textSecondary }}>Add</Text></>}
              </TouchableOpacity>
            </View>
          ) : null}
        </View>
        <Text style={{ fontSize: 11, color: colors.textTertiary || colors.textSecondary, marginTop: 8 }}>Tap a photo to make it the cover. The cover is always the first picture Jessi sends.</Text>
        <TouchableOpacity onPress={onClose} style={[st.done, { backgroundColor: GOLD }]} testID="gallery-done">
          <Text style={{ color: '#000', fontWeight: '800', fontSize: 15 }}>Done</Text>
        </TouchableOpacity>
      </View>
    </Modal>
  );
};

const st = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.55)' },
  sheet: { borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 20, paddingBottom: 34 },
  handle: { alignSelf: 'center', width: 40, height: 4, borderRadius: 2, backgroundColor: 'rgba(255,255,255,0.18)', marginBottom: 14 },
  title: { fontSize: 18, fontWeight: '800' },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginTop: 16 },
  cell: { width: 92 },
  img: { width: 92, height: 92, borderRadius: 12 },
  busy: { ...StyleSheet.absoluteFillObject, borderRadius: 12, backgroundColor: 'rgba(0,0,0,0.45)', alignItems: 'center', justifyContent: 'center' },
  del: { position: 'absolute', top: -6, right: -6, width: 22, height: 22, borderRadius: 11, backgroundColor: '#FF3B30', alignItems: 'center', justifyContent: 'center', borderWidth: 2, borderColor: '#0B0B0D' },
  addTile: { borderWidth: 1, borderStyle: 'dashed', alignItems: 'center', justifyContent: 'center', gap: 2 },
  done: { alignItems: 'center', justifyContent: 'center', borderRadius: 14, paddingVertical: 14, marginTop: 16 },
});
