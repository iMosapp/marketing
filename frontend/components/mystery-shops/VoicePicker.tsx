import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useToast } from '../common/Toast';
import { Chip, GOLD, tid } from './shared';
import { useSamplePlayer } from './samplePlayer';

type Voice = { id: string; name: string; accent: string; tone: string };
type Pools = { female: Voice[]; male: Voice[]; configured: boolean; reason?: string | null };
let poolsPromise: Promise<Pools> | null = null;
const loadPools = () => (poolsPromise ||= api.get('/shop-clients/voices').then(r => r.data).catch(() => { poolsPromise = null; return { female: [], male: [], configured: false, reason: 'Could not load the voices' }; }));

type Props = { gender: 'female' | 'male'; value: string; onChange: (v: string) => void; persona: any; industry?: string; department?: string; colors: any };

// The exact GPT-Live voice a challenge will use: play each one saying the persona's opening line, pick one to lock it in.
export const VoicePicker = ({ gender, value, onChange, persona, industry, department, colors }: Props) => {
  const { showToast } = useToast();
  const [pools, setPools] = useState<Pools | null>(null);
  const { busy, playing, play } = useSamplePlayer();
  useEffect(() => { loadPools().then(setPools); }, []);

  const hear = async (v: Voice) => {
    try {
      await play(v.id, async () => (await api.post('/shop-clients/voices/sample', { voice: v.id, persona, industry, department }, { timeout: 50000 })).data.url);
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not play that voice right now', 'error'); }
  };

  const voices = pools?.[gender] || [];
  const named = (id: string | null) => voices.find(v => v.id === id)?.name || id;
  const hint = pools && !pools.configured ? (pools.reason || "Hearing a voice needs the server's OpenAI key.")
    : busy ? `Recording ${named(busy)} saying the opening line. About ten seconds the first time, instant after that.`
    : value ? `Every call with this shopper uses ${named(value)}. Tap play to hear the opening line in that voice.`
    : 'Tap play to hear each voice say the opening line. Pick one to lock it in, or let it vary between calls.';
  return (
    <View style={{ gap: 6 }} {...tid('voice-picker')}>
      <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
        <Chip label="Let it vary" small active={!value} onPress={() => onChange('')} colors={colors} testID="voice-pick-any" />
        {voices.map(v => {
          const on = value === v.id;
          const ink = on ? '#111' : colors.text;
          return (
            <View key={v.id} style={{ flexDirection: 'row', alignItems: 'center', height: 28, borderRadius: 14, borderWidth: 1, borderColor: on ? GOLD : colors.border, backgroundColor: on ? GOLD : colors.card, paddingLeft: 10 }} {...tid(`voice-row-${v.id}`)}>
              <TouchableOpacity onPress={() => onChange(v.id)} style={{ height: 28, justifyContent: 'center' }} {...tid(`voice-pick-${v.id}`)}>
                <Text style={{ fontSize: 12, fontWeight: '800', color: ink }}>{v.name}<Text style={{ fontWeight: '500', color: on ? '#333' : colors.textSecondary }}> · {v.accent}</Text></Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={() => hear(v)} disabled={!!busy} style={{ paddingHorizontal: 7, height: 28, justifyContent: 'center' }} {...tid(`voice-play-${v.id}`)}>
                {busy === v.id ? <ActivityIndicator size="small" color={on ? '#111' : GOLD} /> : <Ionicons name={playing === v.id ? 'stop-circle' : 'play-circle'} size={19} color={on ? '#111' : GOLD} />}
              </TouchableOpacity>
            </View>
          );
        })}
        {!pools && <ActivityIndicator size="small" color={GOLD} />}
      </View>
      <Text style={{ fontSize: 11.5, color: colors.textSecondary }} {...tid('voice-picker-hint')}>{hint}</Text>
    </View>
  );
};
