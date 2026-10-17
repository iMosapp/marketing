import React, { useState } from 'react';
import { View, Text, TouchableOpacity, TextInput } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { CallRecordingPlayer } from '../CallRecordingPlayer';
import { resolvePhotoUrl } from '../../utils/photoUrl';
import { VoiceIdBadge } from '../calls/VoiceIdBadge';

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
export const RecordedConversationCard = ({ note, colors, onDelete, onRename }: { note: any; colors: any; onDelete?: (id: string) => void; onRename?: (id: string, title: string) => void }) => {
  const [showTranscript, setShowTranscript] = useState(false);
  const [showPlayer, setShowPlayer] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(note.title || '');
  const url = resolvePhotoUrl(note.audio_url) || note.audio_url;
  const highlights: any[] = note.highlights || [];
  const heading = note.title || 'Recorded conversation';
  const commit = () => { setEditing(false); const t = draft.trim().slice(0, 60); if (t !== (note.title || '')) onRename?.(note.id, t); };
  return (
    <View style={{ backgroundColor: colors.card, borderRadius: 14, padding: 14, marginBottom: 12, borderWidth: 1, borderColor: GOLD + '44' }} {...tid(`recorded-convo-${note.id}`)}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 8 }}>
        <View style={{ width: 38, height: 38, borderRadius: 19, backgroundColor: GOLD + '22', alignItems: 'center', justifyContent: 'center' }}>
          <Ionicons name="people" size={17} color={GOLD} />
        </View>
        <View style={{ flex: 1 }}>
          {editing ? (
            <TextInput value={draft} onChangeText={setDraft} autoFocus maxLength={60} placeholder="Tahoe walk-around" placeholderTextColor={colors.textSecondary}
              onBlur={commit} onSubmitEditing={commit} returnKeyType="done"
              style={{ color: colors.text, fontWeight: '700', fontSize: 15, paddingVertical: 2, borderBottomWidth: 1, borderBottomColor: GOLD }}
              {...tid(`recorded-convo-title-input-${note.id}`)} />
          ) : (
            <TouchableOpacity onPress={() => onRename && (setDraft(note.title || ''), setEditing(true))} disabled={!onRename} style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }} {...tid(`recorded-convo-title-${note.id}`)}>
              <Text style={{ color: colors.text, fontWeight: '700', fontSize: 15, flexShrink: 1 }} numberOfLines={1}>{heading}</Text>
              {!!onRename && <Ionicons name="pencil" size={12} color={colors.textSecondary} />}
            </TouchableOpacity>
          )}
          <Text style={{ color: colors.textSecondary, fontSize: 12, marginTop: 1 }}>
            {note.title ? 'Recorded conversation · ' : ''}{note.duration ? `${fmtDur(note.duration)} · ` : ''}{note.created_at ? new Date(note.created_at).toLocaleString() : ''} · in person
          </Text>
          <VoiceIdBadge item={note} id={`convo-${note.id}`} style={{ marginTop: 5 }} />
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

      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
        {note.transcript ? (
          <TouchableOpacity onPress={() => setShowTranscript(t => !t)} style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }} {...tid(`recorded-convo-transcript-${note.id}`)}>
            <Ionicons name={showTranscript ? 'chevron-up' : 'document-text-outline'} size={14} color={colors.accent || GOLD} />
            <Text style={{ color: colors.accent || GOLD, fontSize: 13, fontWeight: '600' }}>{showTranscript ? 'Hide transcript' : 'Read transcript'}</Text>
          </TouchableOpacity>
        ) : <View />}
        {!!onDelete && (
          <TouchableOpacity onPress={() => onDelete(note.id)} hitSlop={8} style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }} {...tid(`recorded-convo-delete-${note.id}`)}>
            <Ionicons name="trash-outline" size={14} color="#FF3B30" />
            <Text style={{ color: '#FF3B30', fontSize: 13, fontWeight: '600' }}>Delete</Text>
          </TouchableOpacity>
        )}
      </View>
      {showTranscript && (
        <Text style={{ color: colors.textSecondary, fontSize: 13, lineHeight: 19, marginTop: 8 }} selectable>{note.transcript}</Text>
      )}
    </View>
  );
};
