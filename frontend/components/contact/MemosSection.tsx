/**
 * MemosSection — record a voice memo + every memo for this contact, transcripts folded to three lines (tap to read it all).
 * Lives under History › Memos. Recorded in-person conversations show under History › Calls.
 */
import React, { useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { tid } from '../scripts/shared';
import { formatEventTime } from '../../utils/contactHelpers';

export default function MemosSection(props: any) {
  const {
    s, colors, voiceNotes = [], voiceNotesLoading, isRecording, recordingTime, uploadingVoiceNote,
    playingNoteId, startRecording, stopRecording, playVoiceNote, deleteVoiceNote, formatRecordingTime, maxRecordingSeconds,
  } = props;
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const memos = voiceNotes.filter((n: any) => n.kind !== 'conversation');

  return (
    <View style={[s.section, { paddingTop: 4 }]} {...tid('voice-notes-section')}>
      {isRecording ? (
        <View style={s.vnRecording} {...tid('voice-recording-indicator')}>
          <View style={s.vnRecordingDot} />
          <Text style={s.vnRecordingTime}>{formatRecordingTime(recordingTime)}</Text>
          <Text style={s.vnRecordingLimit}>/ {formatRecordingTime(maxRecordingSeconds)}</Text>
          <TouchableOpacity style={s.vnStopBtn} onPress={stopRecording} {...tid('stop-recording-btn')}>
            <Ionicons name="stop" size={18} color={colors.text} />
            <Text style={s.vnStopText}>Stop</Text>
          </TouchableOpacity>
        </View>
      ) : uploadingVoiceNote ? (
        <View style={s.vnRecording}>
          <ActivityIndicator size="small" color="#34C759" />
          <Text style={[s.vnRecordingTime, { marginLeft: 8 }]}>Saving & transcribing...</Text>
        </View>
      ) : (
        <TouchableOpacity style={s.vnRecordBtn} onPress={startRecording} {...tid('start-recording-btn')}>
          <Ionicons name="mic" size={20} color="#34C759" />
          <Text style={s.vnRecordText}>Record a voice memo</Text>
        </TouchableOpacity>
      )}

      {voiceNotesLoading ? (
        <ActivityIndicator size="small" color="#C9A962" style={{ marginTop: 12 }} />
      ) : memos.length === 0 ? (
        <Text style={{ fontSize: 13, color: colors.textTertiary, textAlign: 'center', marginTop: 18 }} {...tid('memos-empty')}>
          No memos yet. Say what you learned and Jessi remembers it for you.
        </Text>
      ) : (
        <View style={{ marginTop: 12 }}>
          {memos.map((note: any, i: number) => {
            const isPlaying = playingNoteId === note.id;
            const expanded = !!open[note.id];
            return (
              <View key={note.id} style={s.vnCard} {...tid(`voice-note-${i}`)}>
                <View style={s.vnCardHeader}>
                  <TouchableOpacity style={[s.vnPlayBtn, isPlaying && s.vnPlayBtnActive]} onPress={() => playVoiceNote(note.id, note.audio_url)} {...tid(`play-voice-note-${i}`)}>
                    <Ionicons name={isPlaying ? 'pause' : 'play'} size={16} color={isPlaying ? '#000' : '#34C759'} />
                  </TouchableOpacity>
                  <View style={{ flex: 1, marginLeft: 10 }}>
                    <Text style={s.vnCardDate}>{note.title || formatEventTime(note.created_at)}</Text>
                    <Text style={s.vnCardDuration}>{note.title ? `${formatEventTime(note.created_at)} · ` : ''}{formatRecordingTime(Math.round(note.duration || 0))}</Text>
                  </View>
                  <TouchableOpacity
                    onPress={(e: any) => { e.stopPropagation?.(); deleteVoiceNote(note.id); }}
                    style={{ padding: 12, margin: -8, zIndex: 10 }}
                    hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
                    {...tid(`delete-voice-note-${i}`)}
                  >
                    <Ionicons name="trash-outline" size={18} color="#FF3B30" />
                  </TouchableOpacity>
                </View>
                {note.transcript ? (
                  <TouchableOpacity activeOpacity={0.7} onPress={() => setOpen(o => ({ ...o, [note.id]: !o[note.id] }))} {...tid(`voice-note-transcript-${i}`)}>
                    <Text style={s.vnTranscript} numberOfLines={expanded ? undefined : 3}>{note.transcript}</Text>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 6 }}>
                      <Ionicons name="sparkles" size={11} color="#AF52DE" />
                      <Text style={{ fontSize: 11, color: '#AF52DE', fontStyle: 'italic', flex: 1 }}>Jessi learned from this memo</Text>
                      {note.transcript.length > 160 && <Text style={{ fontSize: 11, fontWeight: '700', color: colors.textSecondary }}>{expanded ? 'Less' : 'Read all'}</Text>}
                    </View>
                  </TouchableOpacity>
                ) : (
                  <Text style={[s.vnTranscript, { fontStyle: 'italic', color: colors.textTertiary }]}>Transcribing...</Text>
                )}
              </View>
            );
          })}
        </View>
      )}
    </View>
  );
}
