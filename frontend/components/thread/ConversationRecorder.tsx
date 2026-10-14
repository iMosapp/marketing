import React, { useEffect, useRef, useState } from 'react';
import { View, Text, TouchableOpacity, Modal, Platform, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRecordingStore, fmtClock } from '../../store/recordingStore';
import { useToast } from '../common/Toast';

const GOLD = '#C9A962';
const RED = '#FF3B30';
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });

type TriggerState = { live: boolean; recording: boolean; seconds: number; label: string; busy: boolean; onPress: () => void };
type Props = {
  userId: string; contactId: string; contactFirst: string; colors: any; onSaved?: (note: any) => void; onRecordingChange?: (on: boolean) => void;
  memoRecording?: boolean; onStartMemo?: () => void; onStopMemo?: () => void; pillStyle?: any; labelStyle?: any;
  renderTrigger?: (s: TriggerState) => React.ReactNode;
};

// One "Record" pill for both a quick voice memo (3 min, just you) and a full in-person conversation (45 min, transcribed + summarized,
// Jessi can cite it). The conversation itself runs in recordingStore, so it keeps going (and stays stoppable from the red bar) when
// the rep leaves this screen.
export const ConversationRecorder = ({ userId, contactId, contactFirst, colors, onSaved, onRecordingChange, memoRecording, onStartMemo, onStopMemo, pillStyle, labelStyle, renderTrigger }: Props) => {
  const [chooser, setChooser] = useState(false);
  const { showToast } = useToast();
  const session = useRecordingStore(s => s.session);
  const storeRecording = useRecordingStore(s => s.recording);
  const seconds = useRecordingStore(s => s.seconds);
  const saving = useRecordingStore(s => s.saving);
  const failed = useRecordingStore(s => s.failed);
  const lastSaved = useRecordingStore(s => s.lastSaved);
  const startStore = useRecordingStore(s => s.start);
  const stop = useRecordingStore(s => s.stop);

  const mine = !!session && session.contactId === contactId;
  const recording = storeRecording && mine;
  const busy = !!saving && mine;
  const otherActive = (storeRecording || !!saving) && !mine;

  useEffect(() => { onRecordingChange?.(recording); }, [recording]); // eslint-disable-line react-hooks/exhaustive-deps

  // A save that finished for this contact (even one started before this screen mounted) refreshes the caller once.
  const seenRef = useRef(lastSaved?.at || 0);
  useEffect(() => {
    if (!lastSaved || lastSaved.at === seenRef.current) return;
    seenRef.current = lastSaved.at;
    if (lastSaved.contactId === contactId) onSaved?.(lastSaved.note);
  }, [lastSaved, contactId]); // eslint-disable-line react-hooks/exhaustive-deps

  const start = async () => {
    setChooser(false);
    const r = await startStore({ userId, contactId, contactFirst });
    if (r === 'denied') showToast('Mic access needed', 'error');
    else if (r === 'failed') showToast('Could not start recording', 'error');
    else if (r === 'busy') {
      const st = useRecordingStore.getState();
      showToast(st.failed ? 'Retry or discard the unsaved recording on the bar first.' : `Still recording with ${st.session?.contactFirst || 'someone else'}. Stop & save that first.`, 'warning');
    }
  };

  const live = recording || !!memoRecording;
  const onPillPress = () => {
    if (busy) return;
    if (recording) stop();
    else if (memoRecording) onStopMemo?.();
    else if (failed) showToast('Retry or discard the unsaved recording on the bar first.', 'warning');
    else if (otherActive) showToast(`Still recording with ${session?.contactFirst || 'someone else'}. Tap Stop & save on the red bar first.`, 'warning');
    else setChooser(true);
  };
  const textColor = colors.textPrimary || colors.text;
  const label = busy ? 'Saving…' : recording ? fmtClock(seconds) : memoRecording ? 'Stop' : 'Record';
  return (
    <>
      {renderTrigger ? renderTrigger({ live, recording, seconds, label, busy, onPress: onPillPress }) : (
        <TouchableOpacity onPress={onPillPress} activeOpacity={0.8} disabled={busy}
          style={[pillStyle, { backgroundColor: live ? RED : busy ? GOLD + '22' : colors.surface || colors.card }, busy && { borderWidth: 1, borderColor: GOLD + '99' }]}
          {...tid('record-conversation-btn')}>
          {busy ? <ActivityIndicator size="small" color={GOLD} /> : <Ionicons name={live ? 'stop' : 'mic'} size={15} color={live ? '#fff' : GOLD} />}
          <Text style={[labelStyle, { color: live ? '#fff' : busy ? GOLD : textColor }]} numberOfLines={1}>{label}</Text>
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
            <Text style={{ fontSize: 12, color: colors.textSecondary, fontStyle: 'italic', textAlign: 'center' }}>Tell the customer you're recording. A red bar stays on screen until you tap Stop & save, wherever you go in the app.</Text>
            <TouchableOpacity onPress={() => setChooser(false)} style={{ alignItems: 'center', padding: 8 }} {...tid('record-cancel-btn')}><Text style={{ color: colors.textSecondary, fontWeight: '700' }}>Cancel</Text></TouchableOpacity>
          </View>
        </TouchableOpacity>
      </Modal>
    </>
  );
};
