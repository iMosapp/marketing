import { useEffect, useRef, useState } from 'react';
import { Platform } from 'react-native';
import { resolvePhotoUrl } from '../utils/photoUrl';

// One memo plays at a time (web Audio element or expo-av); tapping the playing one stops it.
export const useMemoPlayer = (onError: (msg: string) => void) => {
  const [playingId, setPlayingId] = useState<string | null>(null);
  const soundRef = useRef<any>(null);
  const audioRef = useRef<any>(null);
  const stop = async () => {
    if (soundRef.current) { try { await soundRef.current.unloadAsync(); } catch {} soundRef.current = null; }
    if (audioRef.current) { try { audioRef.current.pause(); } catch {} audioRef.current = null; }
    setPlayingId(null);
  };
  useEffect(() => () => { stop(); }, []);
  const play = async (m: any) => {
    const wasPlaying = playingId === m.id;
    await stop();
    if (wasPlaying) return;
    const url = m.audio_url?.startsWith('http') ? m.audio_url : resolvePhotoUrl(m.audio_url) || m.audio_url;
    try {
      if (Platform.OS === 'web') {
        const a = new (globalThis as any).Audio(url);
        a.onended = () => setPlayingId(null);
        a.onerror = () => { setPlayingId(null); onError('Could not play that memo'); };
        await a.play(); audioRef.current = a;
      } else {
        const { Audio } = await import('expo-av');
        await Audio.setAudioModeAsync({ allowsRecordingIOS: false, playsInSilentModeIOS: true });
        const { sound } = await Audio.Sound.createAsync({ uri: url }, { shouldPlay: true }, (st: any) => { if (st.didJustFinish) { setPlayingId(null); soundRef.current = null; } });
        soundRef.current = sound;
      }
      setPlayingId(m.id);
    } catch { onError('Could not play that memo'); }
  };
  return { playingId, play, stop };
};
