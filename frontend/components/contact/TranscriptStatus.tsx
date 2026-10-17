// Transcript state on a voice note ("Transcribing again…" / "Couldn't transcribe · Retry") and who recorded it when it was a teammate.
import React from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

const AMBER = '#FF9500';
const GOLD = '#C9A962';
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } } as any);

type Props = { note: any; colors: any; onRetry?: (id: string) => void; retrying?: boolean; testPrefix: string };

export const TranscriptStatus = ({ note, colors, onRetry, retrying, testPrefix }: Props) => {
  const st = note?.transcript_status;
  if (st === 'retrying' || retrying) {
    return (
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 4 }} {...tid(`${testPrefix}-retrying-${note.id}`)}>
        <ActivityIndicator size="small" color={GOLD} />
        <Text style={{ fontSize: 13, color: colors.textSecondary, fontStyle: 'italic', flex: 1 }}>Transcribing again… Jessi keeps the audio and tries a few more times.</Text>
      </View>
    );
  }
  if (st !== 'failed') return null;
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, padding: 10, borderRadius: 10, backgroundColor: AMBER + '14', borderWidth: 1, borderColor: AMBER + '55' }} {...tid(`${testPrefix}-failed-${note.id}`)}>
      <Ionicons name="alert-circle-outline" size={16} color={AMBER} />
      <Text style={{ flex: 1, fontSize: 13, color: colors.text }}>Couldn't transcribe. Play it, or try again.</Text>
      {onRetry ? (
        <TouchableOpacity onPress={() => onRetry(note.id)} hitSlop={8} style={{ paddingHorizontal: 12, paddingVertical: 6, borderRadius: 999, backgroundColor: GOLD }} {...tid(`${testPrefix}-retry-${note.id}`)}>
          <Text style={{ fontSize: 12.5, fontWeight: '800', color: '#111' }}>Retry</Text>
        </TouchableOpacity>
      ) : null}
    </View>
  );
};

export const RecordedBy = ({ note, colors, testPrefix }: { note: any; colors: any; testPrefix: string }) =>
  note?.mine === false && note?.recorded_by ? (
    <Text style={{ fontSize: 11.5, color: colors.textSecondary, marginTop: 2 }} numberOfLines={1} {...tid(`${testPrefix}-recorded-by-${note.id}`)}>Recorded by {note.recorded_by}</Text>
  ) : null;
