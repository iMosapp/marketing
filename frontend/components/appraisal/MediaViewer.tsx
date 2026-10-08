import React, { useEffect, useRef, useState } from 'react';
import { View, Text, TouchableOpacity, Image, Modal, FlatList, ScrollView, Platform, TextInput, ActivityIndicator, useWindowDimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Video, ResizeMode } from 'expo-av';
import { GOLD, tid } from '../inbox/ownership';
import { resolvePhotoUrl } from '../../utils/photoUrl';
import { SourceTag } from './shared';
import { MarkupLayer, MARKUP_RED, fitRect, useImageSize, type Stroke } from './MarkupCanvas';

export type MarkupPayload = { strokes: Stroke[]; note: string };
type Props = { colors: any; media: any[]; index: number | null; onClose: () => void; canMarkup?: boolean; onMarkup?: (item: any, payload: MarkupPayload) => Promise<void> };
const when = (iso?: string) => (iso ? new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '');

// Full-screen look at a photo or video on the appraisal: swipe between them, pinch to zoom (native), who sent it and when.
// With canMarkup a manager can draw on the photo (circle the dent), add a line, and send it back to the rep.
export const MediaViewer = ({ colors, media, index, onClose, canMarkup, onMarkup }: Props) => {
  const { width, height } = useWindowDimensions();
  const [at, setAt] = useState(index ?? 0);
  const [drawing, setDrawing] = useState(false);
  const [strokes, setStrokes] = useState<Stroke[]>([]);
  const [note, setNote] = useState('');
  const [sending, setSending] = useState(false);
  const list = useRef<FlatList>(null);
  useEffect(() => { if (index != null) setAt(index); }, [index]);
  useEffect(() => { if (index == null) { setDrawing(false); setStrokes([]); setNote(''); } }, [index]);
  if (index == null || !media.length) return null;
  const m = media[Math.min(at, media.length - 1)];
  const go = (d: number) => { const n = Math.max(0, Math.min(media.length - 1, at + d)); setAt(n); list.current?.scrollToIndex({ index: n, animated: true }); };
  const stop = () => { setDrawing(false); setStrokes([]); setNote(''); };
  const send = async () => {
    if (!onMarkup || strokes.length === 0) return;
    setSending(true);
    try { await onMarkup(m, { strokes, note: note.trim() }); stop(); } finally { setSending(false); }
  };
  const lastMark = m.markups?.length ? m.markups[m.markups.length - 1] : null;
  return (
    <Modal visible transparent animationType="fade" onRequestClose={drawing ? stop : onClose}>
      <View style={{ flex: 1, backgroundColor: '#000000F2' }} {...tid('media-viewer')}>
        <FlatList
          ref={list} data={media} horizontal pagingEnabled showsHorizontalScrollIndicator={false} keyExtractor={(x) => x.id} initialScrollIndex={index} scrollEnabled={!drawing}
          getItemLayout={(_, i) => ({ length: width, offset: width * i, index: i })}
          onMomentumScrollEnd={(e) => setAt(Math.round(e.nativeEvent.contentOffset.x / width))}
          renderItem={({ item }) => <Slide item={item} width={width} height={height} onClose={drawing ? () => {} : onClose} drawing={drawing && item.id === m.id} strokes={item.id === m.id ? strokes : []} onStrokes={setStrokes} />}
        />
        <View pointerEvents="box-none" style={{ position: 'absolute', left: 0, right: 0, top: 0, paddingTop: Platform.OS === 'web' ? 16 : 54, paddingHorizontal: 16, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
          <Text style={{ fontSize: 13, fontWeight: '800', color: '#FFFFFFCC' }} {...tid('media-viewer-counter')}>{at + 1} / {media.length}</Text>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            {canMarkup && onMarkup && m.kind !== 'video' && m.url && !drawing ? (
              <TouchableOpacity onPress={() => setDrawing(true)} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, height: 38, paddingHorizontal: 14, borderRadius: 19, backgroundColor: MARKUP_RED }} {...tid('media-viewer-markup')}>
                <Ionicons name="brush" size={15} color="#fff" /><Text style={{ fontSize: 13, fontWeight: '800', color: '#fff' }}>Mark up</Text>
              </TouchableOpacity>
            ) : null}
            <TouchableOpacity onPress={drawing ? stop : onClose} style={{ width: 38, height: 38, borderRadius: 19, backgroundColor: '#FFFFFF22', alignItems: 'center', justifyContent: 'center' }} {...tid('media-viewer-close')}>
              <Ionicons name="close" size={22} color="#fff" />
            </TouchableOpacity>
          </View>
        </View>
        {drawing ? (
          <View style={{ position: 'absolute', left: 0, right: 0, bottom: 0, paddingBottom: Platform.OS === 'web' ? 20 : 36, paddingHorizontal: 16, gap: 10 }} {...tid('media-viewer-markup-bar')}>
            <Text style={{ fontSize: 13, fontWeight: '700', color: '#fff', textAlign: 'center' }}>{strokes.length ? `${strokes.length} stroke${strokes.length === 1 ? '' : 's'} · draw more or send` : 'Draw on the photo: circle the dent, underline the scratch.'}</Text>
            <TextInput value={note} onChangeText={setNote} placeholder="A line for the rep (optional)" placeholderTextColor="#FFFFFF77" maxLength={300}
              style={{ height: 44, borderRadius: 12, paddingHorizontal: 14, backgroundColor: '#FFFFFF1A', color: '#fff', fontSize: 14, borderWidth: 1, borderColor: '#FFFFFF33' }} {...tid('media-viewer-markup-note-input')} />
            <View style={{ flexDirection: 'row', gap: 8 }}>
              <TouchableOpacity onPress={() => setStrokes(s => s.slice(0, -1))} disabled={!strokes.length} style={{ height: 44, paddingHorizontal: 14, borderRadius: 12, backgroundColor: '#FFFFFF22', alignItems: 'center', justifyContent: 'center', opacity: strokes.length ? 1 : 0.4 }} {...tid('media-viewer-markup-undo')}>
                <Ionicons name="arrow-undo" size={18} color="#fff" />
              </TouchableOpacity>
              <TouchableOpacity onPress={() => setStrokes([])} disabled={!strokes.length} style={{ height: 44, paddingHorizontal: 14, borderRadius: 12, backgroundColor: '#FFFFFF22', alignItems: 'center', justifyContent: 'center', opacity: strokes.length ? 1 : 0.4 }} {...tid('media-viewer-markup-clear')}>
                <Text style={{ fontSize: 13, fontWeight: '800', color: '#fff' }}>Clear</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={stop} style={{ height: 44, paddingHorizontal: 14, borderRadius: 12, backgroundColor: '#FFFFFF22', alignItems: 'center', justifyContent: 'center' }} {...tid('media-viewer-markup-cancel')}>
                <Text style={{ fontSize: 13, fontWeight: '800', color: '#fff' }}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={send} disabled={!strokes.length || sending} style={{ flex: 1, height: 44, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6, opacity: strokes.length && !sending ? 1 : 0.5 }} {...tid('media-viewer-markup-send')}>
                {sending ? <ActivityIndicator color="#0B0B0D" size="small" /> : <Ionicons name="paper-plane" size={15} color="#0B0B0D" />}<Text style={{ fontSize: 14, fontWeight: '800', color: '#0B0B0D' }}>Send to rep</Text>
              </TouchableOpacity>
            </View>
          </View>
        ) : (
          <View pointerEvents="box-none" style={{ position: 'absolute', left: 0, right: 0, bottom: 0, paddingBottom: Platform.OS === 'web' ? 20 : 40, paddingHorizontal: 20, alignItems: 'center', gap: 8 }}>
            <Text style={{ fontSize: 16, fontWeight: '800', color: '#fff', textAlign: 'center' }} {...tid('media-viewer-caption')}>{m.role_label || m.name}</Text>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap', justifyContent: 'center' }}>
              <SourceTag source={m.source} colors={colors} />
              <Text style={{ fontSize: 12, color: '#FFFFFFAA' }}>{m.uploaded_by_name ? `${m.uploaded_by_name} · ` : ''}{when(m.uploaded_at)}</Text>
            </View>
            {m.reading?.value != null ? <Text style={{ fontSize: 12, color: '#FFFFFFAA' }} {...tid('media-viewer-reading')}>Jessi read {m.reading.label || m.reading.value}</Text> : null}
            {lastMark ? (
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, maxWidth: 560 }} {...tid('media-viewer-markup-note')}>
                <Ionicons name="brush" size={13} color={MARKUP_RED} />
                <Text style={{ fontSize: 13, color: '#fff', textAlign: 'center' }} numberOfLines={3}><Text style={{ fontWeight: '800' }}>{lastMark.by_name}</Text>{lastMark.note ? `: ${lastMark.note}` : ' marked this up'}{m.markups.length > 1 ? ` · ${m.markups.length} markups` : ''} · {when(lastMark.created_at)}</Text>
              </View>
            ) : null}
          </View>
        )}
        {media.length > 1 && Platform.OS === 'web' && !drawing ? (
          <>
            {at > 0 ? <TouchableOpacity onPress={() => go(-1)} style={{ position: 'absolute', left: 12, top: '50%', marginTop: -22, width: 44, height: 44, borderRadius: 22, backgroundColor: '#FFFFFF22', alignItems: 'center', justifyContent: 'center' }} {...tid('media-viewer-prev')}><Ionicons name="chevron-back" size={24} color="#fff" /></TouchableOpacity> : null}
            {at < media.length - 1 ? <TouchableOpacity onPress={() => go(1)} style={{ position: 'absolute', right: 12, top: '50%', marginTop: -22, width: 44, height: 44, borderRadius: 22, backgroundColor: '#FFFFFF22', alignItems: 'center', justifyContent: 'center' }} {...tid('media-viewer-next')}><Ionicons name="chevron-forward" size={24} color="#fff" /></TouchableOpacity> : null}
          </>
        ) : null}
      </View>
    </Modal>
  );
};

type SlideProps = { item: any; width: number; height: number; onClose: () => void; drawing?: boolean; strokes?: Stroke[]; onStrokes?: (s: Stroke[]) => void };

const Slide = ({ item: m, width, height, onClose, drawing, strokes = [], onStrokes }: SlideProps) => {
  const uri = resolvePhotoUrl(m.url || m.thumb_url) || '';
  const box = { width, height };
  const imgBox = { width, height: height * 0.78 };
  const nat = useImageSize(m.kind === 'video' ? undefined : uri);
  const rect = fitRect(imgBox.width, imgBox.height, nat?.w, nat?.h);
  if (m.kind === 'video' && m.url) {
    return (
      <View style={[box, { alignItems: 'center', justifyContent: 'center' }]} {...tid(`media-slide-${m.id}`)}>
        <Video source={{ uri }} style={{ width, height: height * 0.7 }} useNativeControls resizeMode={ResizeMode.CONTAIN} shouldPlay={false} />
      </View>
    );
  }
  return (
    <ScrollView style={box} contentContainerStyle={{ width, height }} maximumZoomScale={drawing ? 1 : 4} minimumZoomScale={1} scrollEnabled={!drawing} centerContent bouncesZoom showsHorizontalScrollIndicator={false} showsVerticalScrollIndicator={false} {...tid(`media-slide-${m.id}`)}>
      <TouchableOpacity activeOpacity={1} onPress={onClose} disabled={drawing} style={{ width, height, alignItems: 'center', justifyContent: 'center' }}>
        {uri ? (
          <View style={imgBox}>
            {m.thumb_url && m.url ? <Image source={{ uri: resolvePhotoUrl(m.thumb_url) || '' }} style={{ position: 'absolute', left: 0, top: 0, ...imgBox }} resizeMode="contain" blurRadius={1} /> : null}
            <Image source={{ uri }} style={imgBox} resizeMode="contain" />
            {(m.markups?.length || drawing) ? <MarkupLayer rect={rect} markups={m.markups || []} strokes={strokes} drawing={drawing} onStrokesChange={onStrokes} testId={`markup-layer-${m.id}`} /> : null}
          </View>
        ) : <Text style={{ color: '#FFFFFFAA' }}>The original was removed after Jessi finished with it.</Text>}
      </TouchableOpacity>
    </ScrollView>
  );
};
