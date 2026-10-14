import React from 'react';
import { View, Text, TouchableOpacity, Modal, Platform, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, GREEN, tid } from '../scripts/shared';
import { useThemeStore } from '../../store/themeStore';
import { useRecordingStore, fmtClock } from '../../store/recordingStore';
import { fmtDue } from '../contact/RecordedConversationCard';

// "Conversation saved" sheet: summary + the tasks Jessi added. Global, so it shows wherever the rep is when the upload finishes.
export const RecordingResultSheet = () => {
  const { colors } = useThemeStore();
  const result = useRecordingStore(s => s.result);
  const dismiss = useRecordingStore(s => s.dismissResult);
  const note = result?.note;
  const who = result?.contactFirst || 'the customer';
  return (
    <Modal visible={!!result} transparent animationType="slide" onRequestClose={dismiss}>
      <View style={{ flex: 1, backgroundColor: '#00000088', justifyContent: 'flex-end' }}>
        <View style={{ backgroundColor: colors.bg, borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 18, paddingBottom: Platform.OS === 'ios' ? 30 : 18, gap: 10, maxHeight: '80%' }} {...tid('recording-result')}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
            <Ionicons name="checkmark-circle" size={22} color={GREEN} />
            <Text style={{ flex: 1, fontSize: 17, fontWeight: '800', color: colors.text }} numberOfLines={1}>{note?.title ? `${note.title} saved` : `Conversation saved (${fmtClock(Math.round(note?.duration || 0))})`}</Text>
            <TouchableOpacity onPress={dismiss} hitSlop={8} {...tid('recording-result-close')}><Ionicons name="close" size={24} color={colors.text} /></TouchableOpacity>
          </View>
          <ScrollView style={{ flexGrow: 0 }} contentContainerStyle={{ gap: 10 }}>
            {note?.summary ? (
              <View style={{ backgroundColor: GOLD + '14', borderLeftWidth: 3, borderLeftColor: GOLD, borderRadius: 12, padding: 12 }}>
                <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 1, marginBottom: 6 }}>SUMMARY</Text>
                <Text style={{ fontSize: 14, color: colors.text, lineHeight: 20 }}>{note.summary}</Text>
              </View>
            ) : (
              <Text style={{ fontSize: 13, color: colors.textSecondary }}>{note?.transcript ? 'Transcript saved. Summary was not available.' : 'Saved. The audio could not be transcribed (was anyone talking?).'}</Text>
            )}
            {!!note?.tasks?.length && (
              <View style={{ backgroundColor: colors.card, borderRadius: 12, padding: 12, gap: 8 }} {...tid('recording-result-tasks')}>
                <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 1 }}>ADDED TO YOUR TASKS</Text>
                {note.tasks.map((t: any) => (
                  <View key={t.id} style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 8 }}>
                    <Ionicons name="checkbox-outline" size={16} color={GOLD} style={{ marginTop: 1 }} />
                    <View style={{ flex: 1 }}>
                      <Text style={{ fontSize: 14, fontWeight: '600', color: colors.text }}>{t.title}</Text>
                      <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 1 }}>{fmtDue(t.due_date, t.has_time)}</Text>
                    </View>
                  </View>
                ))}
              </View>
            )}
            {!!note?.transcript && !note?.tasks?.length && (
              <Text style={{ fontSize: 12, color: colors.textSecondary, fontStyle: 'italic' }}>No commitments heard, so no tasks were added.</Text>
            )}
          </ScrollView>
          <Text style={{ fontSize: 12, color: colors.textSecondary }}>Saved to {who}'s record (Calls tab). Ask Jessi about it any time.</Text>
        </View>
      </View>
    </Modal>
  );
};
