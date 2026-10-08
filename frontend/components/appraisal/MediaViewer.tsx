import React, { useEffect, useRef, useState } from 'react';
import { View, Text, TouchableOpacity, Image, Modal, FlatList, ScrollView, Platform, useWindowDimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Video, ResizeMode } from 'expo-av';
import { tid } from '../inbox/ownership';
import { resolvePhotoUrl } from '../../utils/photoUrl';
import { SourceTag } from './shared';

type Props = { colors: any; media: any[]; index: number | null; onClose: () => void };
const when = (iso?: string) => (iso ? new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '');

// Full-screen look at a photo or video on the appraisal: swipe between them, pinch to zoom (native), who sent it and when.
export const MediaViewer = ({ colors, media, index, onClose }: Props) => {
  const { width, height } = useWindowDimensions();
  const [at, setAt] = useState(index ?? 0);
  const list = useRef<FlatList>(null);
  useEffect(() => { if (index != null) setAt(index); }, [index]);
  if (index == null || !media.length) return null;
  const m = media[Math.min(at, media.length - 1)];
  const go = (d: number) => { const n = Math.max(0, Math.min(media.length - 1, at + d)); setAt(n); list.current?.scrollToIndex({ index: n, animated: true }); };
  return (
    <Modal visible transparent animationType="fade" onRequestClose={onClose}>
      <View style={{ flex: 1, backgroundColor: '#000000F2' }} {...tid('media-viewer')}>
        <FlatList
          ref={list} data={media} horizontal pagingEnabled showsHorizontalScrollIndicator={false} keyExtractor={(x) => x.id} initialScrollIndex={index}
          getItemLayout={(_, i) => ({ length: width, offset: width * i, index: i })}
          onMomentumScrollEnd={(e) => setAt(Math.round(e.nativeEvent.contentOffset.x / width))}
          renderItem={({ item }) => <Slide item={item} width={width} height={height} onClose={onClose} />}
        />
        <View pointerEvents="box-none" style={{ position: 'absolute', left: 0, right: 0, top: 0, paddingTop: Platform.OS === 'web' ? 16 : 54, paddingHorizontal: 16, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
          <Text style={{ fontSize: 13, fontWeight: '800', color: '#FFFFFFCC' }} {...tid('media-viewer-counter')}>{at + 1} / {media.length}</Text>
          <TouchableOpacity onPress={onClose} style={{ width: 38, height: 38, borderRadius: 19, backgroundColor: '#FFFFFF22', alignItems: 'center', justifyContent: 'center' }} {...tid('media-viewer-close')}>
            <Ionicons name="close" size={22} color="#fff" />
          </TouchableOpacity>
        </View>
        <View pointerEvents="box-none" style={{ position: 'absolute', left: 0, right: 0, bottom: 0, paddingBottom: Platform.OS === 'web' ? 20 : 40, paddingHorizontal: 20, alignItems: 'center', gap: 8 }}>
          <Text style={{ fontSize: 16, fontWeight: '800', color: '#fff', textAlign: 'center' }} {...tid('media-viewer-caption')}>{m.role_label || m.name}</Text>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap', justifyContent: 'center' }}>
            <SourceTag source={m.source} colors={colors} />
            <Text style={{ fontSize: 12, color: '#FFFFFFAA' }}>{m.uploaded_by_name ? `${m.uploaded_by_name} · ` : ''}{when(m.uploaded_at)}</Text>
          </View>
          {m.reading?.value != null ? <Text style={{ fontSize: 12, color: '#FFFFFFAA' }} {...tid('media-viewer-reading')}>Jessi read {m.reading.label || m.reading.value}</Text> : null}
        </View>
        {media.length > 1 && Platform.OS === 'web' ? (
          <>
            {at > 0 ? <TouchableOpacity onPress={() => go(-1)} style={{ position: 'absolute', left: 12, top: '50%', marginTop: -22, width: 44, height: 44, borderRadius: 22, backgroundColor: '#FFFFFF22', alignItems: 'center', justifyContent: 'center' }} {...tid('media-viewer-prev')}><Ionicons name="chevron-back" size={24} color="#fff" /></TouchableOpacity> : null}
            {at < media.length - 1 ? <TouchableOpacity onPress={() => go(1)} style={{ position: 'absolute', right: 12, top: '50%', marginTop: -22, width: 44, height: 44, borderRadius: 22, backgroundColor: '#FFFFFF22', alignItems: 'center', justifyContent: 'center' }} {...tid('media-viewer-next')}><Ionicons name="chevron-forward" size={24} color="#fff" /></TouchableOpacity> : null}
          </>
        ) : null}
      </View>
    </Modal>
  );
};

const Slide = ({ item: m, width, height, onClose }: { item: any; width: number; height: number; onClose: () => void }) => {
  const uri = resolvePhotoUrl(m.url || m.thumb_url) || '';
  const box = { width, height };
  if (m.kind === 'video' && m.url) {
    return (
      <View style={[box, { alignItems: 'center', justifyContent: 'center' }]} {...tid(`media-slide-${m.id}`)}>
        <Video source={{ uri }} style={{ width, height: height * 0.7 }} useNativeControls resizeMode={ResizeMode.CONTAIN} shouldPlay={false} />
      </View>
    );
  }
  return (
    <ScrollView style={box} contentContainerStyle={{ width, height }} maximumZoomScale={4} minimumZoomScale={1} centerContent bouncesZoom showsHorizontalScrollIndicator={false} showsVerticalScrollIndicator={false} {...tid(`media-slide-${m.id}`)}>
      <TouchableOpacity activeOpacity={1} onPress={onClose} style={{ width, height, alignItems: 'center', justifyContent: 'center' }}>
        {uri ? (
          <View style={{ width, height: height * 0.78 }}>
            {m.thumb_url && m.url ? <Image source={{ uri: resolvePhotoUrl(m.thumb_url) || '' }} style={{ position: 'absolute', left: 0, top: 0, width, height: height * 0.78 }} resizeMode="contain" blurRadius={1} /> : null}
            <Image source={{ uri }} style={{ width, height: height * 0.78 }} resizeMode="contain" />
          </View>
        ) : <Text style={{ color: '#FFFFFFAA' }}>The original was removed after Jessi finished with it.</Text>}
      </TouchableOpacity>
    </ScrollView>
  );
};
