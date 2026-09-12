import React, { useEffect, useRef, useState } from 'react';
import { View, Text, TouchableOpacity, Modal, Platform, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';

const GOLD = '#C9A962';
const RED = '#FF3B30';
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });
const MAX_SECONDS = 45 * 60;

// Low-bitrate mono AAC: a 45-minute walk-around stays around 10 MB (Whisper's cap is 25 MB)
const convoOptions = (Audio: any) => ({
  isMeteringEnabled: false,
  android: { extension: '.m4a', outputFormat: Audio.AndroidOutputFormat.MPEG_4, audioEncoder: Audio.AndroidAudioEncoder.AAC, sampleRate: 22050, numberOfChannels: 1, bitRate: 32000 },
  ios: { extension: '.m4a', outputFormat: Audio.IOSOutputFormat.MPEG4AAC, audioQuality: Audio.IOSAudioQuality.MEDIUM, sampleRate: 22050, numberOfChannels: 1, bitRate: 32000, linearPCMBitDepth: 16, linearPCMIsBigEndian: false, linearPCMIsFloat: false },
  web: { mimeType: 'audio/webm', bitsPerSecond: 32000 },
});

const fmt = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;

type TriggerState = { live: boolean; recording: boolean; seconds: number; label: string; onPress: () => void };
type Props = {
  userId: string; contactId: string; contactFirst: string; colors: any; onSaved?: (note: any) => void; onRecordingChange?: (on: boolean) => void;
  memoRecording?: boolean; onStartMemo?: () => void; onStopMemo?: () => void; pillStyle?: any; labelStyle?: any;
  renderTrigger?: (s: TriggerState) => React.ReactNode; inline?: boolean;
};

// One "Record" pill for both a quick voice memo (3 min, just you) and a full in-person conversation (45 min, transcribed + summarized, Jessi can cite it).
export const ConversationRecorder = ({ userId, contactId, contactFirst, colors, onSaved, onRecordingChange, memoRecording, onStartMemo, onStopMemo, pillStyle, labelStyle, renderTrigger, inline }: Props) => {
  const [chooser, setChooser] = useState(false);
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [saving, setSaving] = useState<string | null>(null);
  const [result, setResult] = useState<any | null>(null);
  const recRef = useRef<any>(null);
  const timerRef = useRef<any>(null);
  const keepAwakeRef = useRef<(() => void) | null>(null);

  useEffect(() => () => { if (timerRef.current) clearInterval(timerRef.current); keepAwakeRef.current?.(); }, []);

  const start = async () => {
    setChooser(false);
    try {
      const { Audio } = await import('expo-av');
      const { status } = await Audio.requestPermissionsAsync();
      if (status !== 'granted') { setSaving('Microphone access is needed to record'); setTimeout(() => setSaving(null), 2500); return; }
      await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true, staysActiveInBackground: true });
      const { recording: rec } = await Audio.Recording.createAsync(convoOptions(Audio));
      recRef.current = rec;
      try {
        const ka = await import('expo-keep-awake');
        await ka.activateKeepAwakeAsync('convo-recorder');
        keepAwakeRef.current = () => ka.deactivateKeepAwake('convo-recorder');
      } catch { /* keep-awake optional */ }
      setSeconds(0); setRecording(true); onRecordingChange?.(true);
      timerRef.current = setInterval(() => setSeconds(s => {
        if (s + 1 >= MAX_SECONDS) { stop(); }
        return s + 1;
      }), 1000);
    } catch (e) { setSaving('Could not start recording'); setTimeout(() => setSaving(null), 2500); }
  };

  const stop = async () => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    keepAwakeRef.current?.(); keepAwakeRef.current = null;
    const rec = recRef.current;
    recRef.current = null;
    setRecording(false); onRecordingChange?.(false);
    if (!rec) return;
    const duration = seconds;
    try {
      await rec.stopAndUnloadAsync();
      const uri = rec.getURI();
      if (!uri) return;
      if (duration < 5) { setSaving('Too short to save'); setTimeout(() => setSaving(null), 2000); return; }
      setSaving('Uploading recording…');
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
        setSaving(total > 1 ? `Uploading ${Math.round(((i + 1) / total) * 100)}%…` : 'Uploading recording…');
        if (i === total - 1) setSaving('Transcribing and summarizing…');
        const res = await api.post(`/voice-notes/${userId}/${contactId}/chunk`, {
          upload_id: uploadId, index: i, total, data: b64.slice(i * PIECE, (i + 1) * PIECE), content_type: contentType, duration, kind: 'conversation',
        }, { timeout: 180000 });
        last = res.data;
      }
      setSaving(null);
      setResult(last);
      onSaved?.(last);
    } catch (e: any) {
      setSaving(e?.response?.data?.detail || 'Could not save the recording');
      setTimeout(() => setSaving(null), 3500);
    }
  };

  const live = recording || !!memoRecording;
  const onPillPress = () => { if (recording) stop(); else if (memoRecording) onStopMemo?.(); else setChooser(true); };
  const textColor = colors.textPrimary || colors.text;
  const label = recording ? `Stop ${fmt(seconds)}` : memoRecording ? 'Stop' : 'Record';
  const overlay = inline ? {} : { position: 'absolute' as const, left: 0, right: 0, top: 0, zIndex: 50 };
  const savingPos = inline ? { marginHorizontal: 16, marginBottom: 8 } : { position: 'absolute' as const, left: 16, right: 16, top: 8, zIndex: 60 };
  return (
    <>
      {recording && (
        <View style={[overlay, { backgroundColor: RED, paddingVertical: 8, paddingHorizontal: 16, flexDirection: 'row', alignItems: 'center', gap: 10 }, inline && { marginHorizontal: 16, marginBottom: 10, borderRadius: 12 }]} {...tid('recording-banner')}>
          <View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: '#fff' }} />
          <Text style={{ flex: 1, color: '#fff', fontWeight: '800', fontSize: 13 }}>Recording conversation with {contactFirst} · {fmt(seconds)}</Text>
          <TouchableOpacity onPress={stop} style={{ backgroundColor: '#fff', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 5 }} {...tid('recording-stop-btn')}>
            <Text style={{ color: RED, fontWeight: '800', fontSize: 12 }}>Stop & save</Text>
          </TouchableOpacity>
        </View>
      )}

      {!!saving && (
        <View style={[savingPos, { backgroundColor: colors.card, borderRadius: 12, padding: 12, flexDirection: 'row', alignItems: 'center', gap: 10, borderWidth: 1, borderColor: GOLD }]} {...tid('recording-saving')}>
          <ActivityIndicator size="small" color={GOLD} /><Text style={{ flex: 1, color: textColor, fontSize: 13, fontWeight: '600' }}>{saving}</Text>
        </View>
      )}

      {renderTrigger ? renderTrigger({ live, recording, seconds, label, onPress: onPillPress }) : (
        <TouchableOpacity onPress={onPillPress} activeOpacity={0.8}
          style={[pillStyle, { backgroundColor: live ? RED : colors.surface || colors.card }]}
          {...tid('record-conversation-btn')}>
          <Ionicons name={live ? 'stop' : 'mic'} size={15} color={live ? '#fff' : GOLD} />
          <Text style={[labelStyle, { color: live ? '#fff' : textColor }]} numberOfLines={1}>{label}</Text>
        </TouchableOpacity>
      )}

      <Modal visible={chooser} transparent animationType="fade" onRequestClose={() => setChooser(false)}>
        <TouchableOpacity style={{ flex: 1, backgroundColor: '#00000088', justifyContent: 'flex-end' }} activeOpacity={1} onPress={() => setChooser(false)}>
          <View style={{ backgroundColor: colors.background || colors.bg, borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 18, paddingBottom: Platform.OS === 'ios' ? 34 : 18, gap: 10 }} {...tid('record-chooser')}>
            <Text style={{ fontSize: 17, fontWeight: '800', color: textColor }}>What are you recording?</Text>
            {!!onStartMemo && (
              <TouchableOpacity onPress={() => { setChooser(false); onStartMemo(); }} activeOpacity={0.85}
                style={{ flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderRadius: 16, backgroundColor: colors.surface || colors.card, borderWidth: 1, borderColor: colors.border }} {...tid('record-memo-btn')}>
                <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: GOLD + '22', alignItems: 'center', justifyContent: 'center' }}><Ionicons name="mic" size={20} color={GOLD} /></View>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 15, fontWeight: '800', color: textColor }}>Voice memo <Text style={{ fontSize: 12, fontWeight: '600', color: colors.textSecondary }}>· up to 3 min</Text></Text>
                  <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17, marginTop: 2 }}>A quick note to yourself about {contactFirst}. Transcribed into the profile.</Text>
                </View>
                <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
              </TouchableOpacity>
            )}
            <TouchableOpacity onPress={start} activeOpacity={0.85}
              style={{ flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderRadius: 16, backgroundColor: RED + '14', borderWidth: 1, borderColor: RED + '66' }} {...tid('record-start-btn')}>
              <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: RED, alignItems: 'center', justifyContent: 'center' }}><Ionicons name="people" size={20} color="#fff" /></View>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 15, fontWeight: '800', color: textColor }}>Record conversation <Text style={{ fontSize: 12, fontWeight: '600', color: colors.textSecondary }}>· up to 45 min</Text></Text>
                <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17, marginTop: 2 }}>Walk-around, desk talk or speaker call with {contactFirst}. Jessi transcribes it, writes a summary with commitments and can cite it later.</Text>
              </View>
              <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
            </TouchableOpacity>
            <Text style={{ fontSize: 12, color: colors.textSecondary, fontStyle: 'italic', textAlign: 'center' }}>Tell the customer you're recording. Keep the screen on until you tap Stop.</Text>
            <TouchableOpacity onPress={() => setChooser(false)} style={{ alignItems: 'center', padding: 8 }} {...tid('record-cancel-btn')}><Text style={{ color: colors.textSecondary, fontWeight: '700' }}>Cancel</Text></TouchableOpacity>
          </View>
        </TouchableOpacity>
      </Modal>

      <Modal visible={!!result} transparent animationType="slide" onRequestClose={() => setResult(null)}>
        <View style={{ flex: 1, backgroundColor: '#00000088', justifyContent: 'flex-end' }}>
          <View style={{ backgroundColor: colors.background || colors.bg, borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 18, gap: 10, maxHeight: '75%' }} {...tid('recording-result')}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <Ionicons name="checkmark-circle" size={22} color="#34C759" />
              <Text style={{ flex: 1, fontSize: 17, fontWeight: '800', color: colors.textPrimary || colors.text }}>Conversation saved ({fmt(Math.round(result?.duration || 0))})</Text>
              <TouchableOpacity onPress={() => setResult(null)} {...tid('recording-result-close')}><Ionicons name="close" size={24} color={colors.textPrimary || colors.text} /></TouchableOpacity>
            </View>
            {result?.summary ? (
              <View style={{ backgroundColor: GOLD + '14', borderLeftWidth: 3, borderLeftColor: GOLD, borderRadius: 12, padding: 12 }}>
                <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 1, marginBottom: 6 }}>SUMMARY</Text>
                <Text style={{ fontSize: 14, color: colors.textPrimary || colors.text, lineHeight: 20 }}>{result.summary}</Text>
              </View>
            ) : (
              <Text style={{ fontSize: 13, color: colors.textSecondary }}>{result?.transcript ? 'Transcript saved. Summary was not available.' : 'Saved. The audio could not be transcribed (was anyone talking?).'}</Text>
            )}
            <Text style={{ fontSize: 12, color: colors.textSecondary }}>Saved to {contactFirst}'s record. Ask Jessi about it any time.</Text>
          </View>
        </View>
      </Modal>
    </>
  );
};
