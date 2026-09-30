import React, { useState } from 'react';
import { Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useToast } from '../common/Toast';
import { GOLD, tid } from './shared';
import { useSamplePlayer } from './samplePlayer';

type Props = { challengeId: string; size?: number; testID?: string };

// Quick listen from a challenge card: the voice a shop with this challenge would get, saying its opening line.
export const VoicePlayButton = ({ challengeId, size = 30, testID }: Props) => {
  const { showToast } = useToast();
  const { busy, playing, play } = useSamplePlayer();
  const [label, setLabel] = useState<string | null>(null);
  const go = async () => {
    try {
      await play(challengeId, async () => {
        const r = await api.post(`/shop-clients/challenges/${challengeId}/voice-sample`, {}, { timeout: 50000 });
        setLabel(r.data.voice_label);
        return r.data.url;
      });
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not play that voice right now', 'error'); }
  };
  const on = playing === challengeId;
  return (
    <TouchableOpacity onPress={go} disabled={!!busy} hitSlop={6} style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4, height: size, minWidth: size, paddingHorizontal: label ? 9 : 0, borderRadius: size / 2, backgroundColor: on ? GOLD : GOLD + '22' }} {...tid(testID || `challenge-voice-play-${challengeId}`)}>
      {busy === challengeId ? <ActivityIndicator size="small" color={GOLD} /> : <Ionicons name={on ? 'stop' : 'play'} size={Math.round(size * 0.5)} color={on ? '#111' : GOLD} style={on ? undefined : { marginLeft: 2 }} />}
      {!!label && <Text style={{ fontSize: 11, fontWeight: '800', color: on ? '#111' : GOLD }} {...tid(`challenge-voice-label-${challengeId}`)}>{label}</Text>}
    </TouchableOpacity>
  );
};
