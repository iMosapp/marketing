import React, { useState } from 'react';
import { View, Text, TouchableOpacity, TextInput } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { GOLD, tid } from '../inbox/ownership';
import { newContactFromMemoHref } from './memoLinks';

export const fmtLen = (s: number) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`;
const when = (iso: string) => { const d = new Date(iso); return isNaN(d.getTime()) ? '' : d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }); };

type Props = { memo: any; colors: any; playing: boolean; onPlay: () => void; onAttach: (suggested?: any) => void; onDelete: () => void; onRename: (title: string) => void; onTag: () => void; tagColor: (t: string) => string };

// One memo: play, title (tap to rename), Jessi's summary, transcript on demand, tags, and (while unattached) who it might be about + attach.
export const MemoCard = ({ memo, colors, playing, onPlay, onAttach, onDelete, onRename, onTag, tagColor }: Props) => {
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(memo.title || '');
  const commit = () => { setEditing(false); if (draft.trim() !== (memo.title || '')) onRename(draft.trim()); };
  const attached = !!memo.contact_id;
  return (
    <View style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 14, gap: 10 }} {...tid(`memo-card-${memo.id}`)}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
        <TouchableOpacity onPress={onPlay} style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: playing ? GOLD : GOLD + '22', alignItems: 'center', justifyContent: 'center' }} {...tid(`memo-play-${memo.id}`)}>
          <Ionicons name={playing ? 'pause' : 'play'} size={20} color={playing ? '#111' : GOLD} style={playing ? undefined : { marginLeft: 2 }} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          {editing ? (
            <TextInput value={draft} onChangeText={setDraft} onBlur={commit} onSubmitEditing={commit} autoFocus maxLength={60} placeholder="Name this memo" placeholderTextColor={colors.textSecondary}
              style={{ fontSize: 15, fontWeight: '800', color: colors.text, borderBottomWidth: 1, borderBottomColor: GOLD, paddingVertical: 2 }} {...tid(`memo-title-input-${memo.id}`)} />
          ) : (
            <TouchableOpacity onPress={() => { setDraft(memo.title || ''); setEditing(true); }} {...tid(`memo-title-${memo.id}`)}>
              <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }} numberOfLines={1}>{memo.title || 'Untitled memo'}</Text>
            </TouchableOpacity>
          )}
          <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }}>{when(memo.created_at)} · {fmtLen(memo.duration || 0)}</Text>
        </View>
        {!attached ? <TouchableOpacity onPress={onDelete} hitSlop={8} {...tid(`memo-delete-${memo.id}`)}><Ionicons name="trash-outline" size={18} color={colors.textSecondary} /></TouchableOpacity> : null}
      </View>
      {attached ? (
        <TouchableOpacity onPress={() => router.push(`/contact/${memo.contact_id}` as any)} style={{ flexDirection: 'row', alignItems: 'center', gap: 8, padding: 10, borderRadius: 12, backgroundColor: GOLD + '14', borderWidth: 1, borderColor: GOLD + '55' }} {...tid(`memo-filed-${memo.id}`)}>
          <Ionicons name={memo.kind === 'conversation' ? 'people' : 'person'} size={16} color={GOLD} />
          <Text style={{ flex: 1, fontSize: 13, color: colors.text }} numberOfLines={1}>
            <Text style={{ fontWeight: '800' }}>{memo.contact_name || 'Contact'}</Text>
            <Text style={{ color: colors.textSecondary }}> · filed as {memo.kind === 'conversation' ? 'a recorded conversation' : 'a voice memo'}{memo.attached_at ? ` · ${when(memo.attached_at)}` : ''}</Text>
          </Text>
          <Ionicons name="chevron-forward" size={15} color={GOLD} />
        </TouchableOpacity>
      ) : null}
      {memo.summary ? <Text style={{ fontSize: 14, lineHeight: 20, color: colors.text }} {...tid(`memo-summary-${memo.id}`)}>{memo.summary}</Text>
        : memo.transcript ? <Text style={{ fontSize: 13, lineHeight: 18, color: colors.textSecondary }} numberOfLines={open ? undefined : 2}>{memo.transcript}</Text>
        : <Text style={{ fontSize: 13, color: colors.textSecondary, fontStyle: 'italic' }}>No words were heard in this one.</Text>}
      {memo.transcript && memo.summary ? (
        <TouchableOpacity onPress={() => setOpen(o => !o)} {...tid(`memo-transcript-toggle-${memo.id}`)}>
          <Text style={{ fontSize: 12, fontWeight: '700', color: GOLD }}>{open ? 'Hide transcript' : 'Read the transcript'}</Text>
        </TouchableOpacity>
      ) : null}
      {open && memo.summary ? <Text style={{ fontSize: 13, lineHeight: 18, color: colors.textSecondary }} {...tid(`memo-transcript-${memo.id}`)}>{memo.transcript}</Text> : null}
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 6 }} {...tid(`memo-tags-${memo.id}`)}>
        {(memo.tags || []).map((t: string) => (
          <View key={t} style={{ flexDirection: 'row', alignItems: 'center', gap: 5, height: 26, paddingHorizontal: 9, borderRadius: 13, backgroundColor: tagColor(t) + '22', borderWidth: 1, borderColor: tagColor(t) + '88' }} {...tid(`memo-tag-${memo.id}-${t}`)}>
            <View style={{ width: 7, height: 7, borderRadius: 4, backgroundColor: tagColor(t) }} />
            <Text style={{ fontSize: 12, fontWeight: '700', color: colors.text }}>{t}</Text>
          </View>
        ))}
        <TouchableOpacity onPress={onTag} style={{ flexDirection: 'row', alignItems: 'center', gap: 4, height: 26, paddingHorizontal: 9, borderRadius: 13, borderWidth: 1, borderColor: colors.border, borderStyle: 'dashed' }} {...tid(`memo-tag-btn-${memo.id}`)}>
          <Ionicons name="pricetag-outline" size={12} color={colors.textSecondary} />
          <Text style={{ fontSize: 12, fontWeight: '700', color: colors.textSecondary }}>{memo.tags?.length ? 'Edit tags' : 'Add tag'}</Text>
        </TouchableOpacity>
      </View>
      {!attached && memo.suggested_contacts?.length ? (
        <View style={{ gap: 6 }} {...tid(`memo-suggestions-${memo.id}`)}>
          <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6 }}>JESSI THINKS THIS IS ABOUT</Text>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
            {memo.suggested_contacts.map((s: any) => (
              <TouchableOpacity key={s.contact_id} onPress={() => onAttach(s)} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingLeft: 8, paddingRight: 12, height: 34, borderRadius: 17, backgroundColor: GOLD + '1A', borderWidth: 1, borderColor: GOLD + '77' }} {...tid(`memo-suggest-${memo.id}-${s.contact_id}`)}>
                <Ionicons name="sparkles" size={13} color={GOLD} />
                <Text style={{ fontSize: 13, fontWeight: '700', color: colors.text }}>{s.name}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      ) : null}
      {!attached && memo.new_people?.length ? (
        <View style={{ gap: 6 }} {...tid(`memo-people-${memo.id}`)}>
          <Text style={{ fontSize: 12, color: colors.textSecondary }}>Jessi heard {memo.new_people.map((p: any) => p.name).slice(0, 3).join(', ')}, but nobody in your contacts matches yet.</Text>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
            {memo.new_people.map((p: any, i: number) => (
              <TouchableOpacity key={`${p.name}-${i}`} onPress={() => router.push(newContactFromMemoHref(memo.id, p) as any)} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingLeft: 10, paddingRight: 12, height: 34, borderRadius: 17, borderWidth: 1, borderColor: GOLD + '99', backgroundColor: colors.bg }} {...tid(`memo-create-${memo.id}-${i}`)}>
                <Ionicons name="person-add" size={13} color={GOLD} />
                <Text style={{ fontSize: 13, fontWeight: '700', color: colors.text }}>Add {p.name}{p.company ? <Text style={{ fontWeight: '500', color: colors.textSecondary }}> · {p.company}</Text> : null}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      ) : null}
      {!attached ? (
        <TouchableOpacity onPress={() => onAttach()} style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, height: 42, borderRadius: 12, backgroundColor: GOLD }} {...tid(`memo-attach-${memo.id}`)}>
          <Ionicons name="person-add" size={16} color="#111" />
          <Text style={{ fontSize: 14, fontWeight: '800', color: '#111' }}>Attach to a contact</Text>
        </TouchableOpacity>
      ) : null}
    </View>
  );
};
