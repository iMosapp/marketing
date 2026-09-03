/**
 * leadChime — the distinct "new lead in the queue" sound.
 * Native: expo-av plays the bundled wav (also used by push via app.json sounds). Web: HTML5 Audio.
 * noteLeadQueueCount() lets pollers (Home strip, Inbox badge) chime when the unclaimed count grows.
 */
import { Platform } from 'react-native';

const CHIME = require('../assets/sounds/lead_chime.wav');
let lastPlayed = 0;
let lastCount: number | null = null;
let webAudio: any = null;

export async function playLeadChime() {
  const now = Date.now();
  if (now - lastPlayed < 4000) return;
  lastPlayed = now;
  try {
    if (Platform.OS === 'web') {
      if (typeof window === 'undefined' || typeof (window as any).Audio === 'undefined') return;
      const src = typeof CHIME === 'string' ? CHIME : CHIME?.uri || CHIME?.default;
      if (!src) return;
      webAudio = webAudio || new (window as any).Audio(src);
      webAudio.currentTime = 0;
      await webAudio.play();
      return;
    }
    const { Audio } = await import('expo-av');
    await Audio.setAudioModeAsync({ playsInSilentModeIOS: true });
    const { sound } = await Audio.Sound.createAsync(CHIME, { shouldPlay: true, volume: 1 });
    sound.setOnPlaybackStatusUpdate((st: any) => { if (st?.didJustFinish) sound.unloadAsync().catch(() => {}); });
  } catch {}
}

/** Call with the latest unclaimed-queue count; chimes only when it grows past what we've already seen. */
export function noteLeadQueueCount(count: number) {
  if (typeof count !== 'number' || isNaN(count)) return;
  if (lastCount !== null && count > lastCount) playLeadChime();
  lastCount = count;
}

export const isLeadPush = (data: any) => !!data && (data.sound === 'lead_chime.wav' || data.channelId === 'leads');
