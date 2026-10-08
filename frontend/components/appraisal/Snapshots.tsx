import React, { useState } from 'react';
import { View, Text, TouchableOpacity, Image, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, tid } from '../inbox/ownership';
import { resolvePhotoUrl } from '../../utils/photoUrl';
import { MediaViewer, type MarkupPayload } from './MediaViewer';
import { MarkupBadge } from './MarkupCanvas';

type Props = { colors: any; snapshots: any[]; media?: any[]; testPrefix?: string; onRetry?: (video: any) => void; size?: number; canMarkup?: boolean; onMarkup?: (item: any, payload: MarkupPayload) => Promise<void> };

// The stills Jessi pulled out of every walkaround video, as photos on the appraisal: a grid anyone can tap into full screen.
// While a video is still being worked on it says so; a failed pull offers a retry (rep only).
export const Snapshots = ({ colors, snapshots, media = [], testPrefix = 'snapshot', onRetry, size = 92, canMarkup, onMarkup }: Props) => {
  const [viewer, setViewer] = useState<number | null>(null);
  const videos = media.filter(m => m.kind === 'video');
  const extracting = videos.filter(m => m.frames_status === 'extracting');
  const failed = videos.filter(m => m.frames_status === 'failed' || (m.frames_status == null && !m.frame_count && m.original_available !== false));
  if (!snapshots.length && !extracting.length && !failed.length) return null;
  return (
    <View style={{ gap: 8 }} {...tid(`${testPrefix}s`)}>
      <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6 }}>WALK-AROUND SNAPSHOTS{snapshots.length ? ` · ${snapshots.length}` : ''}</Text>
      {extracting.length ? (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }} {...tid(`${testPrefix}s-extracting`)}>
          <ActivityIndicator color={GOLD} size="small" />
          <Text style={{ fontSize: 12.5, color: colors.textSecondary, flex: 1 }}>Pulling the sharpest frames out of {extracting.length === 1 ? (extracting[0].name || 'the video') : `${extracting.length} videos`}… they land here as photos.</Text>
        </View>
      ) : null}
      {failed.map(v => (
        <View key={v.id} style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }} {...tid(`${testPrefix}s-failed-${v.id}`)}>
          <Ionicons name="alert-circle" size={15} color="#FF9500" />
          <Text style={{ fontSize: 12.5, color: colors.textSecondary, flex: 1 }} numberOfLines={2}>{v.frames_status === 'failed' ? `Could not pull snapshots from ${v.name || 'the video'}${v.frames_error ? ` (${v.frames_error})` : ''}.` : `${v.name || 'This video'} has no snapshots yet.`}</Text>
          {onRetry ? (
            <TouchableOpacity onPress={() => onRetry(v)} style={{ paddingHorizontal: 10, paddingVertical: 6, borderRadius: 10, borderWidth: 1, borderColor: GOLD }} {...tid(`${testPrefix}s-retry-${v.id}`)}>
              <Text style={{ fontSize: 12, fontWeight: '800', color: GOLD }}>{v.frames_status === 'failed' ? 'Retry' : 'Pull snapshots'}</Text>
            </TouchableOpacity>
          ) : null}
        </View>
      ))}
      {snapshots.length ? (
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
          {snapshots.map((s: any, idx: number) => (
            <TouchableOpacity key={s.id} onPress={() => setViewer(idx)} activeOpacity={0.85} style={{ width: size, height: Math.round(size * 0.72), borderRadius: 10, overflow: 'hidden', backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.border }} {...tid(`${testPrefix}-${s.id}`)}>
              {s.thumb_url ? <Image source={{ uri: resolvePhotoUrl(s.thumb_url) || '' }} style={{ width: '100%', height: '100%' }} resizeMode="cover" /> : <Ionicons name="image" size={18} color={GOLD} />}
              {s.timestamp_label ? <View style={{ position: 'absolute', left: 4, bottom: 4, backgroundColor: '#000000AA', borderRadius: 5, paddingHorizontal: 5, paddingVertical: 1 }}><Text style={{ fontSize: 10, fontWeight: '700', color: '#fff' }}>{s.timestamp_label}</Text></View> : null}
              <MarkupBadge count={s.markups?.length} testId={`${testPrefix}-markup-${s.id}`} />
            </TouchableOpacity>
          ))}
        </View>
      ) : null}
      <MediaViewer colors={colors} media={snapshots} index={viewer} onClose={() => setViewer(null)} canMarkup={canMarkup} onMarkup={onMarkup} />
    </View>
  );
};
