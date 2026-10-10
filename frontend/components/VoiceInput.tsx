import React, { useState, useRef, useEffect } from 'react';
import {
  Text,
  TouchableOpacity,
  StyleSheet,
  Platform,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Audio } from 'expo-av';
import api from '../services/api';
import { showSimpleAlert } from '../services/alert';

import { useThemeStore } from '../store/themeStore';
const IS_WEB = Platform.OS === 'web';
const MAX_SECONDS = 180;
const RED = '#FF3B30';

interface VoiceInputProps {
  onTranscription: (text: string) => void;
  size?: 'small' | 'medium' | 'large';
  color?: string;
  style?: any;
  disabled?: boolean;
}

type WebRec = { rec: MediaRecorder; stream: MediaStream; chunks: Blob[]; mime: string };

const webMime = () => ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4'].find(m => (globalThis as any).MediaRecorder?.isTypeSupported?.(m)) || '';
const extFor = (mime: string) => (mime.includes('mp4') ? 'mp4' : 'webm');
const clock = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;

/**
 * Reusable voice-to-text button. Tap to start, tap to stop; the clip goes to /voice/transcribe (Whisper).
 * Web records with MediaRecorder (webm/opus, or mp4 on Safari) and holds the recording until you stop it or 3 minutes pass.
 * Native records with expo-av. Recording state lives in refs so timers and re-renders cannot lose a take.
 */
export default function VoiceInput({
  onTranscription,
  size = 'medium',
  color = '#8E8E93',
  style,
  disabled = false,
}: VoiceInputProps) {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const recordingRef = useRef<Audio.Recording | null>(null);
  const webRef = useRef<WebRec | null>(null);
  const timerRef = useRef<any>(null);
  const startedAt = useRef(0);

  const iconSize = size === 'small' ? 18 : size === 'large' ? 28 : 22;
  const buttonSize = size === 'small' ? 32 : size === 'large' ? 48 : 40;

  useEffect(() => () => { clearInterval(timerRef.current); webRef.current?.stream.getTracks().forEach(t => t.stop()); recordingRef.current?.stopAndUnloadAsync().catch(() => {}); }, []);

  const startClock = (onLimit: () => void) => {
    startedAt.current = Date.now();
    setElapsed(0);
    clearInterval(timerRef.current);
    timerRef.current = setInterval(() => {
      const s = Math.floor((Date.now() - startedAt.current) / 1000);
      setElapsed(s);
      if (s >= MAX_SECONDS) onLimit();
    }, 500);
  };
  const stopClock = () => { clearInterval(timerRef.current); timerRef.current = null; };

  const transcribe = async (file: any) => {
    setIsTranscribing(true);
    try {
      const formData = new FormData();
      formData.append('file', file.blob || file, file.name);
      const response = await api.post('/voice/transcribe', formData, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 90000 });
      if (response.data.success && response.data.text) onTranscription(response.data.text);
      else showSimpleAlert('Nothing heard', response.data.error || 'Try again a little closer to the mic.');
    } catch (error: any) {
      console.error('Transcription error:', error);
      showSimpleAlert('Could not transcribe', error?.response?.data?.detail || 'Check the connection and try again.');
    } finally {
      setIsTranscribing(false);
    }
  };

  // ── web: MediaRecorder ──
  const stopWeb = (): Promise<Blob | null> => new Promise(resolve => {
    const m = webRef.current;
    webRef.current = null;
    stopClock();
    setIsRecording(false);
    if (!m) return resolve(null);
    const finish = () => {
      m.stream.getTracks().forEach(t => t.stop());
      resolve(m.chunks.length ? new Blob(m.chunks, { type: m.mime }) : null);
    };
    if (m.rec.state === 'inactive') finish();
    else { m.rec.onstop = finish; try { m.rec.stop(); } catch { finish(); } }
  });
  const finishWeb = async () => {
    const blob = await stopWeb();
    if (!blob || blob.size < 1000) { showSimpleAlert('Nothing recorded', 'The clip was empty. Tap the mic, speak, then tap the red square to stop.'); return; }
    await transcribe({ blob, name: `recording.${extFor(blob.type)}` });
  };
  const startWeb = async () => {
    if (!navigator.mediaDevices?.getUserMedia || !(globalThis as any).MediaRecorder) { showSimpleAlert('Microphone unavailable', 'This browser cannot record audio. Try Chrome, Edge, Firefox or Safari 14.1+.'); return; }
    let stream: MediaStream;
    try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
    catch (e: any) { showSimpleAlert('Microphone blocked', e?.name === 'NotAllowedError' ? 'Allow the microphone for this site in the address bar, then try again.' : 'No microphone was found.'); return; }
    let rec: MediaRecorder;
    const mime = webMime();
    try { rec = new MediaRecorder(stream, mime ? { mimeType: mime, audioBitsPerSecond: 128000 } : undefined); }
    catch (e) { stream.getTracks().forEach(t => t.stop()); throw e; }
    const m: WebRec = { rec, stream, chunks: [], mime: rec.mimeType || mime || 'audio/webm' };
    rec.ondataavailable = ev => { if (ev.data && ev.data.size) m.chunks.push(ev.data); };
    rec.onerror = () => { stopWeb(); showSimpleAlert('Recording stopped', 'The browser interrupted the microphone. Try again.'); };
    webRef.current = m;
    rec.start(1000);
    setIsRecording(true);
    startClock(() => { void finishWeb(); });
  };

  // ── native: expo-av ──
  const stopNative = async () => {
    const rec = recordingRef.current;
    recordingRef.current = null;
    stopClock();
    setIsRecording(false);
    if (!rec) return;
    await rec.stopAndUnloadAsync();
    const uri = rec.getURI();
    if (uri) await transcribe({ uri, type: 'audio/m4a', name: 'recording.m4a' });
  };
  const startNative = async () => {
    const { status } = await Audio.requestPermissionsAsync();
    if (status !== 'granted') { showSimpleAlert('Microphone needed', 'Allow the microphone in Settings to dictate.'); return; }
    await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true });
    const recording = new Audio.Recording();
    await recording.prepareToRecordAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY);
    await recording.startAsync();
    recordingRef.current = recording;
    setIsRecording(true);
    startClock(() => { void stopNative(); });
  };

  const handlePress = async () => {
    if (disabled || isTranscribing) return;
    try {
      const active = IS_WEB ? !!webRef.current : !!recordingRef.current;
      if (active) await (IS_WEB ? finishWeb() : stopNative());
      else await (IS_WEB ? startWeb() : startNative());
    } catch (error) {
      console.error('Recording error:', error);
      stopClock();
      setIsRecording(false);
      setIsTranscribing(false);
      recordingRef.current = null;
      webRef.current?.stream.getTracks().forEach(t => t.stop());
      webRef.current = null;
      showSimpleAlert('Recording failed', IS_WEB ? 'Could not access the microphone. Check the site permission in your browser.' : 'Could not record audio.');
    }
  };

  const icon = isTranscribing
    ? <ActivityIndicator size="small" color={color} />
    : isRecording
      ? <Text style={{ fontSize: size === 'small' ? 9.5 : 11, fontWeight: '800', color: '#fff', fontVariant: ['tabular-nums'] }} testID="voice-input-timer">{clock(elapsed)}</Text>
      : <Ionicons name="mic" size={iconSize} color={color} />;
  const title = isRecording ? 'Recording. Tap to stop and transcribe' : isTranscribing ? 'Transcribing' : 'Tap to dictate';

  if (IS_WEB) {
    return (
      <button
        type="button"
        onClick={handlePress}
        disabled={disabled || isTranscribing}
        data-testid="voice-input-btn"
        data-state={isRecording ? 'recording' : isTranscribing ? 'transcribing' : 'idle'}
        title={title}
        aria-label={title}
        style={{
          width: buttonSize,
          height: buttonSize,
          padding: 0,
          borderRadius: buttonSize / 2,
          border: 'none',
          background: isRecording ? RED : isTranscribing ? 'transparent' : color + '1A',
          cursor: disabled || isTranscribing ? 'not-allowed' : 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          opacity: disabled ? 0.5 : 1,
          transition: 'background-color 150ms ease',
          animation: isRecording ? 'voice-pulse 1.2s ease-in-out infinite' : undefined,
          ...style,
        }}
      >
        {icon}
        <style>{'@keyframes voice-pulse{0%,100%{box-shadow:0 0 0 0 rgba(255,59,48,.45)}50%{box-shadow:0 0 0 7px rgba(255,59,48,0)}}'}</style>
      </button>
    );
  }

  return (
    <TouchableOpacity
      style={[styles.button, { width: buttonSize, height: buttonSize, borderRadius: buttonSize / 2, backgroundColor: isRecording ? RED : color + '1A' }, style]}
      onPress={handlePress}
      disabled={disabled || isTranscribing}
      accessibilityLabel={title}
      testID="voice-input-btn"
    >
      {icon}
    </TouchableOpacity>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  button: {
    alignItems: 'center',
    justifyContent: 'center',
  },
});
