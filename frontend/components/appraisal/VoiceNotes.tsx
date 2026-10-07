import React from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { GOLD, tid, errText } from '../inbox/ownership';
import { showConfirm } from '../../services/alert';
import { useMemoRecorder } from '../../hooks/useMemoRecorder';
import { useMemoPlayer } from '../../hooks/useMemoPlayer';

type Props = { colors: any; appraisal: any; onSaved?: (appraisal: any) => void; showToast?: (m: string, t?: any, d?: number) => void; readOnly?: boolean };
const VOICE_MAX_SECONDS = 5 * 60;
const RED = '#FF3B30';
const fmt = (s: number) => `${Math.floor(s / 60)}:${String(Math.round(s) % 60).padStart(2, '0')}`;
const when = (iso?: string) => (iso ? new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '');

// Talk about the car instead of typing: tap, speak, tap. Jessi types it into the appraisal notes; the clip stays for playback.
export const VoiceNoteRecorder = ({ colors, appraisal, onSaved, showToast }: Props) => {
  const rec = useMemoRecorder({
    path: `/appraisals/${appraisal.id}/voice-note/chunk`, maxSeconds: VOICE_MAX_SECONDS,
    onSaved: (r) => { onSaved?.(r.appraisal); showToast?.(r.voice_note?.transcribed ? 'Got it. Added to the notes.' : 'Saved the clip. Jessi could not make out the words, so it is kept as audio.', r.voice_note?.transcribed ? 'success' : 'info', 3500); },
    onError: (m) => showToast?.(m, 'error', 4000),
  });
  const busy = !!rec.saving;
  return (
    <TouchableOpacity onPress={rec.recording ? rec.stop : rec.start} disabled={busy} activeOpacity={0.85} {...tid(rec.recording ? 'voice-note-stop' : 'voice-note-record')}
      style={{ flexDirection: 'row', alignItems: 'center', gap: 14, minHeight: 64, paddingHorizontal: 16, paddingVertical: 12, borderRadius: 16, backgroundColor: colors.card, borderWidth: 1, borderColor: rec.recording ? RED : colors.border, opacity: busy ? 0.7 : 1 }}>
      <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: rec.recording ? RED + '22' : GOLD + '1F', alignItems: 'center', justifyContent: 'center' }}>
        {busy ? <ActivityIndicator color={GOLD} /> : <Ionicons name={rec.recording ? 'stop' : 'mic'} size={20} color={rec.recording ? RED : GOLD} />}
      </View>
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 16, fontWeight: '800', color: rec.recording ? RED : colors.text }} {...tid('voice-note-label')}>
          {busy ? rec.saving : rec.recording ? `Recording ${fmt(rec.seconds)} · tap to stop` : 'Record a note about this car'}
        </Text>
        <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }}>{rec.recording ? 'Dents, tires, smells, service history, anything you noticed.' : 'Talk instead of typing. Jessi types it into the notes.'}</Text>
      </View>
    </TouchableOpacity>
  );
};

// Every clip on the appraisal (rep and customer) with playback and the words Jessi heard. Reps can remove their own; the desk reads only.
export const VoiceNoteList = ({ colors, appraisal, onSaved, showToast, readOnly }: Props) => {
  const notes: any[] = appraisal.voice_notes || [];
  const player = useMemoPlayer((m) => showToast?.(m, 'error', 3000));
  if (!notes.length) return null;
  const remove = (v: any) => showConfirm('Remove this voice note?', 'Its words come out of the notes too.', async () => {
    try { const r = (await api.delete(`/appraisals/${appraisal.id}/voice-note/${v.id}`)).data; onSaved?.(r.appraisal); }
    catch (e) { showToast?.(errText(e, 'Could not remove it'), 'error'); }
  });
  return (
    <View style={{ gap: 8 }} {...tid('voice-notes')}>
      <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6 }}>VOICE NOTES · {notes.length}</Text>
      {notes.map((v) => {
        const customer = v.by === 'customer';
        return (
          <View key={v.id} style={{ flexDirection: 'row', gap: 10, padding: 12, borderRadius: 14, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border }} {...tid(`voice-note-${v.id}`)}>
            <TouchableOpacity onPress={() => player.play(v)} style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: GOLD + '1F', alignItems: 'center', justifyContent: 'center' }} {...tid(`voice-note-play-${v.id}`)}>
              <Ionicons name={player.playingId === v.id ? 'pause' : 'play'} size={16} color={GOLD} />
            </TouchableOpacity>
            <View style={{ flex: 1, gap: 3 }}>
              <Text style={{ fontSize: 11.5, fontWeight: '800', color: customer ? '#5AC8FA' : GOLD }}>{customer ? `${v.by_name || 'Customer'} · customer` : v.by_name || 'Rep'} · {fmt(v.duration || 0)} · {when(v.created_at)}</Text>
              <Text style={{ fontSize: 13.5, color: v.transcript ? colors.text : colors.textSecondary, lineHeight: 19, fontStyle: v.transcript ? 'normal' : 'italic' }} {...tid(`voice-note-text-${v.id}`)}>{v.transcript || 'No words could be made out. Listen to the clip.'}</Text>
            </View>
            {!readOnly ? (
              <TouchableOpacity onPress={() => remove(v)} hitSlop={8} {...tid(`voice-note-delete-${v.id}`)}><Ionicons name="trash-outline" size={16} color={colors.textSecondary} /></TouchableOpacity>
            ) : null}
          </View>
        );
      })}
    </View>
  );
};

export const VoiceNotes = (p: Props) => (
  <View style={{ gap: 10 }}>
    {!p.readOnly ? <VoiceNoteRecorder {...p} /> : null}
    <VoiceNoteList {...p} />
  </View>
);
