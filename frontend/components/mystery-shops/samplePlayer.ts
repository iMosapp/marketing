import { useCallback, useEffect, useRef, useState } from 'react';
import { Audio } from 'expo-av';
import { API_BASE_URL } from '../../services/api';

// One shopper sample plays at a time anywhere in the app; starting another stops the current one.
let current: { sound: Audio.Sound; onStop: () => void } | null = null;
const stopCurrent = async () => { const c = current; current = null; if (c) { c.onStop(); try { await c.sound.unloadAsync(); } catch {} } };

export const useSamplePlayer = () => {
  const [busy, setBusy] = useState<string | null>(null);
  const [playing, setPlaying] = useState<string | null>(null);
  const mine = useRef(false);
  useEffect(() => () => { if (mine.current) stopCurrent(); }, []);
  const stop = useCallback(async () => { if (mine.current) await stopCurrent(); else setPlaying(null); }, []);
  // fetchPath does the (server-cached) request and returns the wav path; key is the button that should show the stop icon
  const play = useCallback(async (key: string, fetchPath: () => Promise<string>) => {
    if (playing === key) { await stop(); return; }
    await stopCurrent();
    setBusy(key);
    try {
      const path = await fetchPath();
      await Audio.setAudioModeAsync({ playsInSilentModeIOS: true, allowsRecordingIOS: false }).catch(() => {});
      const { sound } = await Audio.Sound.createAsync({ uri: `${API_BASE_URL}${path}` }, { shouldPlay: true }, st => {
        if (st.isLoaded && st.didJustFinish) { mine.current = false; if (current?.sound === sound) current = null; setPlaying(null); sound.unloadAsync().catch(() => {}); }
      });
      mine.current = true;
      current = { sound, onStop: () => { mine.current = false; setPlaying(null); } };
      setPlaying(key);
    } finally { setBusy(null); }
  }, [playing, stop]);
  return { busy, playing, play, stop };
};
