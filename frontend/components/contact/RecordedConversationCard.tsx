import React, { useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { CallRecordingPlayer } from '../CallRecordingPlayer';
import { resolvePhotoUrl } from '../../utils/photoUrl';

const GOLD = '#C9A962';
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });
const ACTION_ICON: Record<string, any> = { call: 'call', text: 'chatbubble', email: 'mail', appointment: 'calendar', task: 'checkbox' };

export const fmtDue = (iso?: string | null, hasTime?: boolean) => {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '';
  const day = d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
  return hasTime ? `${day} · ${d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}` : day;
};

const fmtDur = (s: number) => (s >= 60 ? `${Math.floor(s / 60)}m ${Math.round(s % 60)}s` : `${Math.round(s)}s`);

// A recorded in-person conversation on the Calls tab: summary, the follow-ups it created, play button, transcript.
export const RecordedConversationCard = ({ note, colors }: { note: any; colors: any }) => {
  const [showTranscript, setShowTranscript] = useState(false);
  const [showPlayer, setShowPlayer] = useState(false);
  const url = resolvePhotoUrl(note.audio_url) || note.audio_url;
  const highlights: any[] = note.highlights || [];
  return (
    <View style={{ backgroundColor: colors.card, borderRadius: 14, padding: 14, marginBottom: 12, borderWidth: 1, borderColor: GOLD + '44' }} {...tid(`recorded-convo-${note.id}`)}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 8 }}>
        <View style={{ width: 38, height: 38, borderRadius: 19, backgroundColor: GOLD + '22', alignItems: 'center', justifyContent: 'center' }}>
          <Ionicons name="people" size={17} color={GOLD} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={{ color: colors.text, fontWeight: '700', fontSize: 15 }}>Recorded conversation{note.duration ? ` · ${fmtDur(note.duration)}` : ''}</Text>
          <Text style={{ color: colors.textSecondary, fontSize: 12, marginTop: 1 }}>{note.created_at ? new Date(note.created_at).toLocaleString() : ''} · in person</Text>
        </View>
        <TouchableOpacity onPress={() => setShowPlayer(p => !p)} style={{ width: 38, height: 38, borderRadius: 19, backgroundColor: showPlayer ? GOLD : GOLD + '22', alignItems: 'center', justifyContent: 'center' }} {...tid(`recorded-convo-play-${note.id}`)}>
          <Ionicons name={showPlayer ? 'close' : 'play'} size={18} color={showPlayer ? '#111' : GOLD} />
        </TouchableOpacity>
      </View>

      {showPlayer && (
        <View style={{ marginBottom: 10 }} {...tid(`recorded-convo-player-${note.id}`)}>
          <CallRecordingPlayer url={url} tint={GOLD} textColor={colors.text} subColor={colors.textSecondary} trackColor={colors.border} />
        </View>
      )}

      {note.summary ? (
        <View style={{ backgroundColor: GOLD + '10', borderRadius: 10, padding: 10, marginBottom: 8, borderLeftWidth: 3, borderLeftColor: GOLD }}>
          <Text style={{ color: GOLD, fontSize: 12, fontWeight: '700', marginBottom: 5, letterSpacing: 0.8 }}>SUMMARY</Text>
          <Text style={{ color: colors.text, fontSize: 13, lineHeight: 19 }}>{note.summary}</Text>
        </View>
      ) : !note.transcript ? (
        <View style={{ backgroundColor: colors.surface, borderRadius: 10, padding: 10, marginBottom: 8 }}>
          <Text style={{ color: colors.textSecondary, fontSize: 12, fontStyle: 'italic' }}>No transcript for this recording (was anyone talking?).</Text>
        </View>
      ) : null}

      {highlights.length > 0 && (
        <View style={{ marginBottom: 8, gap: 6 }} {...tid(`recorded-convo-highlights-${note.id}`)}>
          <Text style={{ color: colors.textSecondary, fontSize: 11, fontWeight: '700', letterSpacing: 0.8 }}>FOLLOW-UPS ON YOUR LIST</Text>
          {highlights.map((h, i) => (
            <View key={i} style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 8 }}>
              <Ionicons name={ACTION_ICON[h.action] || 'checkbox'} size={14} color={GOLD} style={{ marginTop: 2 }} />
              <View style={{ flex: 1 }}>
                <Text style={{ color: colors.text, fontSize: 13, fontWeight: '600' }}>{h.title}</Text>
                {!!fmtDue(h.due_date, h.has_time) && <Text style={{ color: colors.textSecondary, fontSize: 11.5, marginTop: 1 }}>{fmtDue(h.due_date, h.has_time)}</Text>}
              </View>
            </View>
          ))}
        </View>
      )}

      {!!note.transcript && (
        <TouchableOpacity onPress={() => setShowTranscript(t => !t)} style={{ flexDirection: 'row', alignItems: 'center', gap: 4, alignSelf: 'flex-start' }} {...tid(`recorded-convo-transcript-${note.id}`)}>
          <Ionicons name={showTranscript ? 'chevron-up' : 'document-text-outline'} size={14} color={colors.accent || GOLD} />
          <Text style={{ color: colors.accent || GOLD, fontSize: 13, fontWeight: '600' }}>{showTranscript ? 'Hide transcript' : 'Read transcript'}</Text>
        </TouchableOpacity>
      )}
      {showTranscript && (
        <Text style={{ color: colors.textSecondary, fontSize: 13, lineHeight: 19, marginTop: 8 }} selectable>{note.transcript}</Text>
      )}
    </View>
  );
};
