import React, { useState, useRef, useEffect } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator, Pressable } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Audio } from 'expo-av';

const RATES = [1.0, 1.5, 2.0];

const fmt = (ms: number) => {
  const s = Math.max(0, Math.floor((ms || 0) / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
};

type Props = {
  url: string;
  tint?: string;
  textColor?: string;
  subColor?: string;
  trackColor?: string;
};

export const CallRecordingPlayer = ({
  url,
  tint = '#30D158',
  textColor = '#1C1C1E',
  subColor = '#8E8E93',
  trackColor = '#E5E5EA',
}: Props) => {
  const soundRef = useRef<Audio.Sound | null>(null);
  const [loading, setLoading] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [position, setPosition] = useState(0);
  const [duration, setDuration] = useState(0);
  const [rate, setRate] = useState(1.0);
  const [error, setError] = useState(false);
  const barWidth = useRef(1);
  const rateRef = useRef(1.0);

  useEffect(() => {
    return () => { soundRef.current?.unloadAsync().catch(() => {}); };
  }, []);

  const onStatus = (st: any) => {
    if (!st.isLoaded) return;
    setPosition(st.positionMillis || 0);
    if (st.durationMillis && isFinite(st.durationMillis)) setDuration(st.durationMillis);
    setPlaying(st.isPlaying);
    if (st.didJustFinish) {
      setPlaying(false);
      setPosition(0);
      soundRef.current?.setPositionAsync(0).catch(() => {});
      soundRef.current?.pauseAsync().catch(() => {});
    }
  };

  const togglePlay = async () => {
    try {
      if (!soundRef.current) {
        setLoading(true);
        setError(false);
        await Audio.setAudioModeAsync({ playsInSilentModeIOS: true, allowsRecordingIOS: false });
        const { sound } = await Audio.Sound.createAsync(
          { uri: url },
          { shouldPlay: true, rate: rateRef.current, shouldCorrectPitch: true, progressUpdateIntervalMillis: 400 },
          onStatus
        );
        soundRef.current = sound;
        setLoading(false);
        setPlaying(true);
        return;
      }
      const st: any = await soundRef.current.getStatusAsync();
      if (st.isLoaded && st.isPlaying) await soundRef.current.pauseAsync();
      else await soundRef.current.playAsync();
    } catch (e) {
      console.error('Recording playback failed:', e);
      setLoading(false);
      setError(true);
      soundRef.current = null;
    }
  };

  const cycleRate = async () => {
    const next = RATES[(RATES.indexOf(rate) + 1) % RATES.length];
    setRate(next);
    rateRef.current = next;
    try { if (soundRef.current) await soundRef.current.setRateAsync(next, true); } catch {}
  };

  const skip = async (deltaMs: number) => {
    if (!soundRef.current || !duration) return;
    const target = Math.min(Math.max(0, position + deltaMs), duration);
    try { await soundRef.current.setPositionAsync(target); setPosition(target); } catch {}
  };

  const seekTo = async (x: number) => {
    if (!soundRef.current || !duration) return;
    const pct = Math.min(Math.max(x / barWidth.current, 0), 1);
    const target = Math.floor(pct * duration);
    try { await soundRef.current.setPositionAsync(target); setPosition(target); } catch {}
  };

  if (error) {
    return (
      <TouchableOpacity onPress={togglePlay} style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }} data-testid="recording-retry-btn">
        <Ionicons name="refresh-circle" size={20} color="#FF9500" />
        <Text style={{ fontSize: 12, color: '#FF9500', fontWeight: '600' }}>Couldn't load recording — tap to retry</Text>
      </TouchableOpacity>
    );
  }

  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }} data-testid="call-recording-player">
      <TouchableOpacity
        onPress={togglePlay}
        style={{ width: 38, height: 38, borderRadius: 19, backgroundColor: tint, alignItems: 'center', justifyContent: 'center' }}
        data-testid="recording-play-btn"
      >
        {loading
          ? <ActivityIndicator size="small" color="#fff" />
          : <Ionicons name={playing ? 'pause' : 'play'} size={18} color="#fff" style={{ marginLeft: playing ? 0 : 2 }} />}
      </TouchableOpacity>

      <View style={{ flex: 1 }}>
        <Pressable
          onLayout={(e) => { barWidth.current = e.nativeEvent.layout.width || 1; }}
          onPress={(e: any) => seekTo(e.nativeEvent?.locationX ?? e.nativeEvent?.offsetX ?? 0)}
          style={{ height: 20, justifyContent: 'center' }}
          data-testid="recording-seek-bar"
        >
          <View style={{ height: 5, borderRadius: 3, backgroundColor: trackColor, overflow: 'hidden' }}>
            <View style={{ width: `${duration ? Math.min(100, (position / duration) * 100) : 0}%`, height: '100%', backgroundColor: tint }} />
          </View>
        </Pressable>
        <Text style={{ fontSize: 11, color: subColor, marginTop: 1 }} data-testid="recording-time-label">
          {fmt(position)} / {duration ? fmt(duration) : '--:--'}
        </Text>
      </View>

      <TouchableOpacity onPress={() => skip(-10000)} style={{ padding: 4 }} data-testid="recording-back-btn">
        <Ionicons name="play-back" size={16} color={subColor} />
      </TouchableOpacity>
      <TouchableOpacity onPress={() => skip(10000)} style={{ padding: 4 }} data-testid="recording-fwd-btn">
        <Ionicons name="play-forward" size={16} color={subColor} />
      </TouchableOpacity>

      <TouchableOpacity
        onPress={cycleRate}
        style={{ borderRadius: 8, paddingHorizontal: 8, paddingVertical: 5, backgroundColor: `${tint}20`, minWidth: 42, alignItems: 'center' }}
        data-testid="recording-speed-btn"
      >
        <Text style={{ fontSize: 12, fontWeight: '800', color: tint }}>{rate === 1 ? '1x' : `${rate}x`}</Text>
      </TouchableOpacity>
    </View>
  );
};
