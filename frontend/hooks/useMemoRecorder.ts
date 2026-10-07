import { useEffect, useRef, useState } from 'react';
import { Platform } from 'react-native';
import api from '../services/api';

export const MEMO_MAX_SECONDS = 45 * 60;

// Low-bitrate mono AAC, same profile as recorded conversations: 45 minutes stays near 10 MB.
const options = (Audio: any) => ({
  isMeteringEnabled: false,
  android: { extension: '.m4a', outputFormat: Audio.AndroidOutputFormat.MPEG_4, audioEncoder: Audio.AndroidAudioEncoder.AAC, sampleRate: 22050, numberOfChannels: 1, bitRate: 32000 },
  ios: { extension: '.m4a', outputFormat: Audio.IOSOutputFormat.MPEG4AAC, audioQuality: Audio.IOSAudioQuality.MEDIUM, sampleRate: 22050, numberOfChannels: 1, bitRate: 32000, linearPCMBitDepth: 16, linearPCMIsBigEndian: false, linearPCMIsFloat: false },
  web: { mimeType: 'audio/webm', bitsPerSecond: 32000 },
});

type Opts = { userId?: string; path?: string; maxSeconds?: number; onSaved: (memo: any) => void; onError: (msg: string) => void };

// Records a stand-alone voice memo (web + native via expo-av) and uploads it in base64 pieces to /voice-memos, or to `path` (same chunk protocol).
export function useMemoRecorder({ userId, path, maxSeconds = MEMO_MAX_SECONDS, onSaved, onError }: Opts) {
  const target = path || (userId ? `/voice-memos/${userId}/chunk` : undefined);
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [saving, setSaving] = useState<string | null>(null);
  const recRef = useRef<any>(null);
  const timerRef = useRef<any>(null);
  const secondsRef = useRef(0);
  const keepAwakeRef = useRef<(() => void) | null>(null);

  useEffect(() => () => { if (timerRef.current) clearInterval(timerRef.current); keepAwakeRef.current?.(); }, []);

  const start = async () => {
    if (recording || saving) return;
    try {
      const { Audio } = await import('expo-av');
      const { status } = await Audio.requestPermissionsAsync();
      if (status !== 'granted') { onError('Microphone access is needed to record.'); return; }
      await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true, staysActiveInBackground: true });
      const { recording: rec } = await Audio.Recording.createAsync(options(Audio));
      recRef.current = rec;
      try {
        const ka = await import('expo-keep-awake');
        await ka.activateKeepAwakeAsync('memo-recorder');
        keepAwakeRef.current = () => ka.deactivateKeepAwake('memo-recorder');
      } catch { /* optional */ }
      secondsRef.current = 0; setSeconds(0); setRecording(true);
      timerRef.current = setInterval(() => {
        secondsRef.current += 1; setSeconds(secondsRef.current);
        if (secondsRef.current >= maxSeconds) stop();
      }, 1000);
    } catch (e) { onError('Could not start recording.'); }
  };

  const stop = async () => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    keepAwakeRef.current?.(); keepAwakeRef.current = null;
    const rec = recRef.current;
    recRef.current = null;
    setRecording(false);
    if (!rec || !target) return;
    const duration = secondsRef.current;
    try {
      await rec.stopAndUnloadAsync();
      try { const { Audio } = await import('expo-av'); await Audio.setAudioModeAsync({ allowsRecordingIOS: false, playsInSilentModeIOS: true }); } catch {}
      const uri = rec.getURI();
      if (!uri) return;
      if (duration < 3) { onError('Too short to save.'); return; }
      setSaving('Uploading…');
      let b64: string;
      let contentType = 'audio/mp4';
      if (Platform.OS === 'web') {
        const blob = await fetch(uri).then(r => r.blob());
        contentType = blob.type || 'audio/webm';
        b64 = await new Promise<string>((res, rej) => { const fr = new FileReader(); fr.onload = () => res(String(fr.result).split(',')[1] || ''); fr.onerror = rej; fr.readAsDataURL(blob); });
      } else {
        const { File: ExpoFile } = await import('expo-file-system');
        b64 = await new ExpoFile(uri).base64();
      }
      const PIECE = 500_000;
      const total = Math.max(1, Math.ceil(b64.length / PIECE));
      const uploadId = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
      let last: any = null;
      for (let i = 0; i < total; i++) {
        setSaving(i === total - 1 ? 'Jessi is listening…' : `Uploading ${Math.round(((i + 1) / total) * 100)}%`);
        const res = await api.post(target, { upload_id: uploadId, index: i, total, data: b64.slice(i * PIECE, (i + 1) * PIECE), content_type: contentType, duration }, { timeout: 180000 });
        last = res.data;
      }
      onSaved(last);
    } catch (e: any) {
      onError(e?.response?.data?.detail || 'Could not save the memo.');
    } finally {
      setSaving(null); secondsRef.current = 0; setSeconds(0);
    }
  };

  return { recording, seconds, saving, start, stop };
}
