import React from 'react';
import { View, Text, TouchableOpacity, Image } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, tid } from '../inbox/ownership';
import { resolvePhotoUrl } from '../../utils/photoUrl';
import { SourceTag } from './shared';

type Props = { colors: any; media: any[]; processed: string[]; onDelete: (m: any) => void; onOpen?: (m: any) => void; busy?: boolean };
const dur = (s?: number | null) => (s == null ? '' : `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`);

// Everything on the inspection, with where it came from and what Jessi pulled out of it.
export const InspectionMedia = ({ colors, media, processed, onDelete, onOpen, busy }: Props) => {
  const items = media.filter(m => m.role !== 'vin_photo');
  if (!items.length) return null;
  return (
    <View style={{ gap: 8 }} {...tid('inspect-media')}>
      <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6 }}>ON THIS INSPECTION · {items.length}</Text>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
        {items.map(m => {
          const done = processed.includes(m.id);
          return (
            <TouchableOpacity key={m.id} onPress={() => onOpen?.(m)} activeOpacity={0.85} style={{ width: 108, gap: 4 }} {...tid(`inspect-media-${m.id}`)}>
              <View style={{ width: 108, height: 80, borderRadius: 10, overflow: 'hidden', backgroundColor: colors.card, borderWidth: 1, borderColor: done ? GOLD + '88' : colors.border, alignItems: 'center', justifyContent: 'center' }}>
                {m.thumb_url ? <Image source={{ uri: resolvePhotoUrl(m.thumb_url) || '' }} style={{ width: '100%', height: '100%' }} resizeMode="cover" /> : <Ionicons name={m.kind === 'video' ? 'videocam' : 'image'} size={22} color={GOLD} />}
                {m.kind === 'video' ? (
                  <View style={{ position: 'absolute', left: 6, bottom: 6, flexDirection: 'row', alignItems: 'center', gap: 3, backgroundColor: '#000000AA', borderRadius: 6, paddingHorizontal: 5, paddingVertical: 2 }}>
                    <Ionicons name="play" size={9} color="#fff" /><Text style={{ fontSize: 10, fontWeight: '700', color: '#fff' }}>{dur(m.duration)}</Text>
                  </View>
                ) : null}
                {m.video_quality === 'poor' ? <View style={{ position: 'absolute', right: 6, top: 6, backgroundColor: '#FF9500', borderRadius: 6, paddingHorizontal: 5, paddingVertical: 2 }} {...tid(`inspect-media-poor-${m.id}`)}><Text style={{ fontSize: 9.5, fontWeight: '800', color: '#0B0B0D' }}>BLURRY</Text></View> : null}
                {!busy ? (
                  <TouchableOpacity onPress={() => onDelete(m)} hitSlop={8} style={{ position: 'absolute', right: 4, bottom: 4, width: 22, height: 22, borderRadius: 11, backgroundColor: '#000000AA', alignItems: 'center', justifyContent: 'center' }} {...tid(`inspect-media-delete-${m.id}`)}>
                    <Ionicons name="trash-outline" size={12} color="#fff" />
                  </TouchableOpacity>
                ) : null}
              </View>
              <Text style={{ fontSize: 11, fontWeight: '700', color: colors.text }} numberOfLines={1}>{m.kind === 'video' ? (m.frames_status === 'extracting' ? 'Pulling snapshots…' : m.frames_status === 'failed' ? 'No snapshots' : m.frame_count != null ? `${m.frame_count} snapshot${m.frame_count === 1 ? '' : 's'}` : 'Video') : m.areas?.length ? m.areas.slice(0, 2).map((a: string) => a.replace(/_/g, ' ')).join(', ') : m.role_label}</Text>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
                <SourceTag source={m.source} colors={colors} />
                {done ? <Ionicons name="checkmark-circle" size={13} color={GOLD} /> : null}
              </View>
            </TouchableOpacity>
          );
        })}
      </View>
    </View>
  );
};
