import React, { useState } from 'react';
import { View, Text, TouchableOpacity, Image, Linking } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useThemeStore } from '../../store/themeStore';
import { GOLD, GREEN, RED, RADIUS, SPACE, TYPE, tid, tint } from '../ui/tokens';
import { OnbEvent, STAGE_LABEL, ThreadLine, when } from './shared';

/** Every stage in order, a check + timestamp on the ones that happened, the current one in gold. */
export const StepTimeline = ({ states, steps, current, paused }: { states: string[]; steps: Record<string, string>; current: string; paused: boolean }) => {
  const { colors } = useThemeStore();
  const idx = states.indexOf(current);
  return (
    <View {...tid('jessi-onb-timeline')}>
      {states.map((s, i) => {
        const done = i < idx || (i === idx && ['FIRST_SUCCESS', 'ONBOARDING_COMPLETE'].includes(s));
        const now = i === idx && !done;
        const color = done ? GREEN : now ? (paused ? RED : GOLD) : colors.textTertiary;
        return (
          <View key={s} style={{ flexDirection: 'row', alignItems: 'center', gap: SPACE.md, paddingVertical: 7 }} {...tid(`jessi-onb-step-${s}`)}>
            <View style={{ width: 22, alignItems: 'center' }}>
              {i > 0 && <View style={{ position: 'absolute', top: -14, width: 2, height: 14, backgroundColor: done || now ? tint(GREEN, 0.5) : colors.border }} />}
              <View style={{ width: 18, height: 18, borderRadius: 9, backgroundColor: done ? GREEN : now ? color : 'transparent', borderWidth: done || now ? 0 : 1.5, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }}>
                {done ? <Ionicons name="checkmark" size={12} color="#000" /> : now ? <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: '#000' }} /> : null}
              </View>
            </View>
            <Text style={{ flex: 1, fontSize: TYPE.sub, fontWeight: now ? '800' : '600', color: done || now ? colors.text : colors.textTertiary }}>{STAGE_LABEL[s] || s}</Text>
            <Text style={{ fontSize: TYPE.caption, color: colors.textTertiary }}>{steps[s] ? when(steps[s]) : ''}</Text>
          </View>
        );
      })}
    </View>
  );
};

/** The SMS thread between Jessi and the new user, newest at the bottom. */
export const SmsThread = ({ thread }: { thread: ThreadLine[] }) => {
  const { colors } = useThemeStore();
  if (!thread.length) return <Text style={{ fontSize: TYPE.sub, color: colors.textTertiary, padding: SPACE.lg }} {...tid('jessi-onb-thread-empty')}>Nothing sent yet.</Text>;
  return (
    <View style={{ padding: SPACE.md, gap: 8 }} {...tid('jessi-onb-thread')}>
      {thread.map((t, i) => {
        const me = t.role === 'jessi';
        return (
          <View key={i} style={{ alignSelf: me ? 'flex-end' : 'flex-start', maxWidth: '86%' }} {...tid(`jessi-onb-bubble-${i}`)}>
            <View style={{ backgroundColor: me ? GOLD : colors.surface, borderRadius: RADIUS.md, borderBottomRightRadius: me ? 4 : RADIUS.md, borderBottomLeftRadius: me ? RADIUS.md : 4, paddingHorizontal: 12, paddingVertical: 8 }}>
              {!!t.media?.length && t.media.map((m, k) => (
                m.endsWith('.vcf') ? (
                  <View key={k} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: t.text ? 6 : 0 }}><Ionicons name="person-circle" size={16} color="#000" /><Text style={{ fontSize: TYPE.caption, fontWeight: '700', color: '#000' }}>Contact card</Text></View>
                ) : <Image key={k} source={{ uri: m }} style={{ width: 160, height: 160, borderRadius: 8, marginBottom: t.text ? 6 : 0 }} />
              ))}
              {!!t.text && <Text style={{ fontSize: TYPE.body, color: me ? '#000' : colors.text, lineHeight: 20 }}>{t.text}</Text>}
            </View>
            <Text style={{ fontSize: 10, color: t.ok === false ? RED : colors.textTertiary, marginTop: 2, alignSelf: me ? 'flex-end' : 'flex-start' }}>
              {me ? (t.kind?.startsWith('admin:') ? t.kind.slice(6) || 'Admin' : 'Jessi') : 'Them'} · {when(t.at)}{t.ok === false ? ` · not delivered${t.error ? ` (${String(t.error).slice(0, 60)})` : ''}` : ''}
            </Text>
          </View>
        );
      })}
    </View>
  );
};

/** Audit log, folded by default. */
export const EventLog = ({ events }: { events: OnbEvent[] }) => {
  const { colors } = useThemeStore();
  const [open, setOpen] = useState(false);
  const rows = [...events].reverse();
  return (
    <View>
      <TouchableOpacity onPress={() => setOpen(!open)} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, padding: SPACE.lg }} {...tid('jessi-onb-events-toggle')}>
        <Ionicons name={open ? 'chevron-down' : 'chevron-forward'} size={14} color={colors.textSecondary} />
        <Text style={{ fontSize: TYPE.sub, fontWeight: '700', color: colors.textSecondary }}>{rows.length} events</Text>
      </TouchableOpacity>
      {open && rows.map((e, i) => (
        <View key={i} style={{ flexDirection: 'row', gap: 8, paddingHorizontal: SPACE.lg, paddingBottom: 8 }} {...tid(`jessi-onb-event-${i}`)}>
          <Text style={{ width: 92, fontSize: TYPE.caption, color: colors.textTertiary }}>{when(e.at)}</Text>
          <Text style={{ flex: 1, fontSize: TYPE.caption, color: colors.text }}>{(STAGE_LABEL[e.type] || e.type.replace(/_/g, ' ').toLowerCase())}{e.note ? ` · ${e.note}` : ''}</Text>
        </View>
      ))}
    </View>
  );
};

/** The 3 to 4 sentence "here's what I learned" + confirmation, and the interview transcript folded underneath. */
export const WriteUpCard = ({ summary, confirmed, interview, awaitingEmail }: { summary?: string | null; confirmed?: boolean; interview?: any; awaitingEmail?: boolean }) => {
  const { colors } = useThemeStore();
  const [open, setOpen] = useState(false);
  const turns: { role: string; text: string }[] = interview?.turns || [];
  return (
    <View style={{ padding: SPACE.lg, gap: SPACE.sm }} {...tid('jessi-onb-writeup')}>
      {summary ? (
        <>
          <Text style={{ fontSize: TYPE.body, color: colors.text, lineHeight: 21 }} {...tid('jessi-onb-summary')}>{summary}</Text>
          <Text style={{ fontSize: TYPE.caption, fontWeight: '700', color: confirmed ? GREEN : GOLD }} {...tid('jessi-onb-summary-status')}>{confirmed ? 'Confirmed by them' : 'Waiting for YEP or a correction'}</Text>
        </>
      ) : <Text style={{ fontSize: TYPE.sub, color: colors.textTertiary }}>No write-up yet. It appears after the setup call.</Text>}
      {awaitingEmail && <Text style={{ fontSize: TYPE.caption, fontWeight: '700', color: GOLD }} {...tid('jessi-onb-awaiting-email')}>Jessi asked for their login email.</Text>}
      {!!interview && (
        <View style={{ marginTop: 4 }}>
          <TouchableOpacity onPress={() => setOpen(!open)} style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }} {...tid('jessi-onb-transcript-toggle')}>
            <Ionicons name={open ? 'chevron-down' : 'chevron-forward'} size={14} color={colors.textSecondary} />
            <Text style={{ fontSize: TYPE.sub, fontWeight: '700', color: colors.textSecondary }}>Call {interview.status}{interview.elapsed_s ? ` · ${Math.round(interview.elapsed_s / 60)} min` : ''} · {turns.length} turns</Text>
          </TouchableOpacity>
          {open && turns.map((t, i) => (
            <Text key={i} style={{ fontSize: TYPE.caption, color: t.role === 'rep' ? colors.text : colors.textSecondary, marginTop: 6, lineHeight: 17 }}>
              <Text style={{ fontWeight: '800' }}>{t.role === 'rep' ? 'Them: ' : 'Jessi: '}</Text>{t.text}
            </Text>
          ))}
          {open && !!interview.recording_url && (
            <TouchableOpacity onPress={() => Linking.openURL(interview.recording_url)} style={{ marginTop: 8 }} {...tid('jessi-onb-recording')}>
              <Text style={{ fontSize: TYPE.sub, fontWeight: '700', color: GOLD }}>Play recording</Text>
            </TouchableOpacity>
          )}
        </View>
      )}
    </View>
  );
};
