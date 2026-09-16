/**
 * QuickActionsRow — the five things a rep does with a customer: Text, Call, Record, Task, Sold.
 * Email lives in the composer (SMS / Email switch), so it is not repeated here.
 */
import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

const GOLD = '#C9A962';

export default function QuickActionsRow({ colors, isRecording, noteLabel, onText, onCall, onNote, onTask, onSold, showSold = true }: any) {
  const actions: any[] = [
    { key: 'text', label: 'Text', icon: 'chatbubble', onPress: onText },
    { key: 'call', label: 'Call', icon: 'call', onPress: onCall },
    { key: 'note', label: noteLabel || (isRecording ? 'Stop' : 'Record'), icon: isRecording ? 'stop' : 'mic', onPress: onNote, recording: isRecording },
    { key: 'task', label: 'Task', icon: 'checkbox', onPress: onTask },
  ];
  if (showSold && onSold) actions.push({ key: 'sold', label: 'Sold', icon: 'trophy', onPress: onSold, filled: true });

  return (
    <View style={{ flexDirection: 'row', marginHorizontal: 16, marginBottom: 14 }} testID="quick-actions-row" dataSet={{ testid: 'quick-actions-row' }}>
      {actions.map(a => (
        <TouchableOpacity key={a.key} onPress={a.onPress} activeOpacity={0.7} style={{ flex: 1, alignItems: 'center', gap: 6 }} testID={`qa-${a.key}-btn`} dataSet={{ testid: `qa-${a.key}-btn` }}>
          <View style={{
            width: 48, height: 48, borderRadius: 24,
            backgroundColor: a.recording ? '#FF3B30' : a.filled ? GOLD : colors.card,
            borderWidth: 1, borderColor: a.recording ? '#FF3B30' : a.filled ? GOLD : colors.border,
            alignItems: 'center', justifyContent: 'center',
          }}>
            <Ionicons name={a.icon as any} size={20} color={a.recording ? '#FFF' : a.filled ? '#000' : colors.text} />
          </View>
          <Text style={{ fontSize: 12, fontWeight: a.filled ? '800' : '600', color: a.recording ? '#FF3B30' : a.filled ? GOLD : colors.textSecondary }}>{a.label}</Text>
        </TouchableOpacity>
      ))}
    </View>
  );
}
