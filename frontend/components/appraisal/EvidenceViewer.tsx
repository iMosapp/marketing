import React from 'react';
import { View, Text, TouchableOpacity, Image, Modal, useWindowDimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { tid } from '../inbox/ownership';
import { resolvePhotoUrl } from '../../utils/photoUrl';
import { SourceTag } from './shared';

type Props = { colors: any; evidence: any | null; onClose: () => void };

// Full-size evidence frame with where it came from: "Video: customer_walkaround.mov · 00:27 · Customer sent".
export const EvidenceViewer = ({ colors, evidence: ev, onClose }: Props) => {
  const { width, height } = useWindowDimensions();
  if (!ev) return null;
  return (
    <Modal visible transparent animationType="fade" onRequestClose={onClose}>
      <TouchableOpacity activeOpacity={1} onPress={onClose} style={{ flex: 1, backgroundColor: '#000000EE', alignItems: 'center', justifyContent: 'center', padding: 16 }} {...tid('evidence-viewer')}>
        <Image source={{ uri: resolvePhotoUrl(ev.url || ev.thumb_url) || '' }} style={{ width: width - 32, height: Math.min(height * 0.6, (width - 32) * 0.75), borderRadius: 12 }} resizeMode="contain" />
        <View style={{ marginTop: 14, alignItems: 'center', gap: 6 }}>
          <Text style={{ fontSize: 15, fontWeight: '800', color: '#fff' }} {...tid('evidence-caption')}>{ev.media_kind === 'video' ? `Video: ${ev.media_name}` : ev.media_name}{ev.timestamp_label ? `  ·  ${ev.timestamp_label}` : ''}</Text>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <SourceTag source={ev.media_source} colors={colors} />
            {ev.areas?.length ? <Text style={{ fontSize: 12, color: '#FFFFFFAA' }}>{ev.areas.map((a: string) => a.replace(/_/g, ' ')).join(', ')}</Text> : null}
          </View>
        </View>
        <TouchableOpacity onPress={onClose} style={{ position: 'absolute', top: 54, right: 20, width: 36, height: 36, borderRadius: 18, backgroundColor: '#FFFFFF22', alignItems: 'center', justifyContent: 'center' }} {...tid('evidence-close')}>
          <Ionicons name="close" size={20} color="#fff" />
        </TouchableOpacity>
      </TouchableOpacity>
    </Modal>
  );
};
