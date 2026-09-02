/**
 * QuickActionsRow — round one-tap actions under the contact hero.
 */
import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

const GOLD = '#C9A962';

export default function QuickActionsRow({ colors, isRecording, onText, onCall, onEmail, onNote, onTask, onSold, showSold = true }: any) {
  const actions: any[] = [
    { key: 'text', label: 'Text', icon: 'chatbubble', onPress: onText },
    { key: 'call', label: 'Call', icon: 'call', onPress: onCall },
    { key: 'email', label: 'Email', icon: 'mail', onPress: onEmail },
    { key: 'note', label: isRecording ? 'Stop' : 'Note', icon: isRecording ? 'stop' : 'mic', onPress: onNote, recording: isRecording },
    { key: 'task', label: 'Task', icon: 'checkbox', onPress: onTask },
  ];
  if (showSold && onSold) actions.push({ key: 'sold', label: 'Sold', icon: 'checkmark-circle', onPress: onSold, filled: true });

  return (
    <View style={{ flexDirection: 'row', justifyContent: 'space-around', marginHorizontal: 16, marginBottom: 12 }} testID="quick-actions-row" dataSet={{ testid: 'quick-actions-row' }}>
      {actions.map(a => (
        <TouchableOpacity
          key={a.key}
          onPress={a.onPress}
          activeOpacity={0.7}
          style={{ alignItems: 'center', gap: 5 }}
          testID={`qa-${a.key}-btn`}
          dataSet={{ testid: `qa-${a.key}-btn` }}
        >
          <View style={{
            width: 50, height: 50, borderRadius: 25,
            backgroundColor: a.recording ? '#FF3B30' : a.filled ? GOLD : colors.card,
            borderWidth: 1, borderColor: a.recording ? '#FF3B30' : a.filled ? GOLD : colors.border,
            alignItems: 'center', justifyContent: 'center',
          }}>
            <Ionicons name={a.icon as any} size={21} color={a.recording ? '#FFF' : a.filled ? '#000' : GOLD} />
          </View>
          <Text style={{ fontSize: 12, fontWeight: a.filled ? '800' : '600', color: a.recording ? '#FF3B30' : a.filled ? GOLD : colors.textSecondary }}>{a.label}</Text>
        </TouchableOpacity>
      ))}
    </View>
  );
}
