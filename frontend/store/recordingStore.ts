import { Platform } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { create } from 'zustand';
import api from '../services/api';

// App-wide home for the long "record a conversation" flow: the native recorder lives here (not in a screen), so leaving the
// contact page, opening a thread or switching tabs never orphans a live mic. RecordingOverlay (mounted in _layout) shows it.
export type RecordingSession = { userId: string; contactId: string; contactFirst: string; startedAt: number };
export type SavedNote = { contactId: string; contactFirst: string; note: any; at: number };
export type FailedUpload = { uri: string; duration: number; session: RecordingSession; reason: string };
export type StartResult = 'started' | 'denied' | 'failed' | 'busy';

type S = {
  session: RecordingSession | null;
  recording: boolean;
  seconds: number;
  saving: string | null;
  result: SavedNote | null;
  failed: FailedUpload | null;
  lastSaved: SavedNote | null;
  error: string | null;
  start: (s: Omit<RecordingSession, 'startedAt'>) => Promise<StartResult>;
  stop: () => Promise<void>;
  retry: () => Promise<void>;
  discard: () => Promise<void>;
  abandon: () => Promise<void>;
  restorePending: (userId: string) => Promise<void>;
  dismissResult: () => void;
  clearError: () => void;
};

export const MAX_SECONDS = 45 * 60;
const MIN_SECONDS = 5;
const PIECE = 500_000;
const PENDING_KEY = 'recording.pending.';

let rec: any = null;
let timer: any = null;
let releaseKeepAwake: (() => void) | null = null;

// Low-bitrate mono AAC: a 45-minute walk-around stays around 10 MB (Whisper's cap is 25 MB)
const convoOptions = (Audio: any) => ({
  isMeteringEnabled: false,
  android: { extension: '.m4a', outputFormat: Audio.AndroidOutputFormat.MPEG_4, audioEncoder: Audio.AndroidAudioEncoder.AAC, sampleRate: 22050, numberOfChannels: 1, bitRate: 32000 },
  ios: { extension: '.m4a', outputFormat: Audio.IOSOutputFormat.MPEG4AAC, audioQuality: Audio.IOSAudioQuality.MEDIUM, sampleRate: 22050, numberOfChannels: 1, bitRate: 32000, linearPCMBitDepth: 16, linearPCMIsBigEndian: false, linearPCMIsFloat: false },
  web: { mimeType: 'audio/webm', bitsPerSecond: 32000 },
});

const readBase64 = async (uri: string): Promise<{ b64: string; contentType: string }> => {
  if (Platform.OS === 'web') {
    const blob = await fetch(uri).then(r => r.blob());
    const b64 = await new Promise<string>((res, rej) => { const fr = new FileReader(); fr.onload = () => res(String(fr.result).split(',')[1] || ''); fr.onerror = rej; fr.readAsDataURL(blob); });
    return { b64, contentType: blob.type || 'audio/webm' };
  }
  const { File: ExpoFile } = await import('expo-file-system');
  return { b64: await new ExpoFile(uri).base64(), contentType: 'audio/mp4' };
};

const dropFile = async (uri: string) => {
  try {
    if (Platform.OS === 'web') { URL.revokeObjectURL(uri); return; }
    const { File: ExpoFile } = await import('expo-file-system');
    new ExpoFile(uri).delete();
  } catch { /* already gone */ }
};

// Stops the timer, releases keep-awake and unloads the native recorder; returns its file uri (if any). Never throws.
const releaseMic = async (): Promise<string | null> => {
  if (timer) { clearInterval(timer); timer = null; }
  releaseKeepAwake?.(); releaseKeepAwake = null;
  const current = rec; rec = null;
  if (!current) return null;
  try { await current.stopAndUnloadAsync(); } catch { /* already stopped */ }
  try { return current.getURI() || null; } catch { return null; }
};

const reasonOf = (e: any) => (e?.response?.status === 404 ? 'That contact is not in your book' : e?.response?.data?.detail || (e?.message?.includes('Network') ? 'No connection' : 'Could not save the recording'));

export const useRecordingStore = create<S>((set, get) => ({
  session: null,
  recording: false,
  seconds: 0,
  saving: null,
  result: null,
  failed: null,
  lastSaved: null,
  error: null,

  start: async ({ userId, contactId, contactFirst }) => {
    if (get().recording || get().saving || get().failed) return 'busy';
    try {
      const { Audio } = await import('expo-av');
      const { status } = await Audio.requestPermissionsAsync();
      if (status !== 'granted') return 'denied';
      await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true, staysActiveInBackground: true });
      const created = await Audio.Recording.createAsync(convoOptions(Audio));
      rec = created.recording;
      try {
        const ka = await import('expo-keep-awake');
        await ka.activateKeepAwakeAsync('convo-recorder');
        releaseKeepAwake = () => ka.deactivateKeepAwake('convo-recorder');
      } catch { /* keep-awake optional */ }
      const startedAt = Date.now();
      set({ session: { userId, contactId, contactFirst, startedAt }, recording: true, seconds: 0, result: null, error: null });
      // Wall-clock based: JS timers pause while the app is backgrounded, the mic does not.
      timer = setInterval(() => {
        const s = Math.floor((Date.now() - startedAt) / 1000);
        set({ seconds: s });
        if (s >= MAX_SECONDS) get().stop();
      }, 1000);
      return 'started';
    } catch {
      const uri = await releaseMic();  // a half-created recorder must not keep the mic open
      if (uri) dropFile(uri);
      return 'failed';
    }
  },

  stop: async () => {
    const { session } = get();
    set({ recording: false });
    const uri = await releaseMic();
    if (!uri || !session) { set({ session: null }); return; }
    const duration = Math.min(MAX_SECONDS, Math.floor((Date.now() - session.startedAt) / 1000));
    if (duration < MIN_SECONDS) { dropFile(uri); set({ session: null, error: 'Too short to save' }); return; }
    await upload(uri, duration, session, set);
  },

  retry: async () => {
    const f = get().failed;
    if (!f || get().saving) return;
    set({ failed: null, session: f.session });
    await upload(f.uri, f.duration, f.session, set);
  },

  discard: async () => {
    const f = get().failed;
    set({ failed: null, session: null });
    if (f) dropFile(f.uri);
  },

  // Logout / account switch (including a forced 401 logout mid-conversation): free the mic, keep the audio on this phone
  // under the owner's id, and show nothing to the next person. The owner gets Retry / Discard back when they sign in again.
  abandon: async () => {
    const { failed, session, recording } = get();
    const uri = await releaseMic();
    set({ session: null, recording: false, seconds: 0, saving: null, result: null, failed: null, lastSaved: null, error: null });
    const keep: FailedUpload | null = uri && session && recording
      ? { uri, duration: Math.min(MAX_SECONDS, Math.floor((Date.now() - session.startedAt) / 1000)), session, reason: 'You were signed out before it could be saved' }
      : failed;
    if (!keep) { if (uri) dropFile(uri); return; }
    if (Platform.OS === 'web' || keep.duration < MIN_SECONDS) { dropFile(keep.uri); return; }  // blob URLs do not survive a reload
    try { await AsyncStorage.setItem(`${PENDING_KEY}${keep.session.userId}`, JSON.stringify(keep)); } catch { dropFile(keep.uri); }
  },

  restorePending: async (userId) => {
    try {
      const raw = await AsyncStorage.getItem(`${PENDING_KEY}${userId}`);
      if (!raw) return;
      await AsyncStorage.removeItem(`${PENDING_KEY}${userId}`);
      const keep = JSON.parse(raw) as FailedUpload;
      if (keep?.uri && keep.session?.userId === userId && !get().recording && !get().saving && !get().failed) set({ failed: keep });
    } catch { /* nothing to restore */ }
  },

  dismissResult: () => set({ result: null }),
  clearError: () => set({ error: null }),
}));

async function upload(uri: string, duration: number, session: RecordingSession, set: (p: Partial<S>) => void) {
  try {
    set({ saving: 'Uploading…' });
    const { b64, contentType } = await readBase64(uri);
    const total = Math.max(1, Math.ceil(b64.length / PIECE));
    const uploadId = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
    let last: any = null;
    for (let i = 0; i < total; i++) {
      set({ saving: i === total - 1 ? 'Transcribing…' : `Uploading ${Math.round(((i + 1) / total) * 100)}%` });
      const res = await api.post(`/voice-notes/${session.userId}/${session.contactId}/chunk`, {
        upload_id: uploadId, index: i, total, data: b64.slice(i * PIECE, (i + 1) * PIECE), content_type: contentType, duration, kind: 'conversation',
      }, { timeout: 180000 });
      last = res.data;
    }
    const saved: SavedNote = { contactId: session.contactId, contactFirst: session.contactFirst, note: last, at: Date.now() };
    dropFile(uri);
    set({ saving: null, session: null, result: saved, lastSaved: saved });
  } catch (e: any) {
    // The file stays on the device: the bar offers Retry / Discard instead of losing a 40-minute conversation.
    set({ saving: null, session: null, failed: { uri, duration, session, reason: reasonOf(e) } });
  }
}

export const fmtClock = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
