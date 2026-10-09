import React, { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { useThemeStore } from '../store/themeStore';
type Topic = { kind: string | null; label: string | null; switched?: boolean; forced?: boolean; episodes?: { kind: string; label: string; current: boolean }[] };

interface AISuggestionProps {
  suggestion: string;
  intent?: string;
  topic?: Topic | null;
  onChangeTopic?: (kind: string) => void;
  onAccept: () => void;
  onEdit: () => void;
  onDismiss: () => void;
}

export default function AISuggestion({
  suggestion,
  intent,
  topic,
  onChangeTopic,
  onAccept,
  onEdit,
  onDismiss,
}: AISuggestionProps) {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const [pickTopic, setPickTopic] = useState(false);
  const others = (topic?.episodes || []).filter(e => !e.current);
  const seen = new Set<string>();
  const alternatives = others.filter(e => (seen.has(e.kind) ? false : (seen.add(e.kind), true)));
  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Ionicons name="sparkles" size={16} color="#34C759" />
          <Text style={styles.headerText}>Jessi suggests:</Text>
        </View>
        <TouchableOpacity onPress={onDismiss} testID="ai-suggestion-dismiss" dataSet={{ testid: 'ai-suggestion-dismiss' } as any}>
          <Ionicons name="close" size={20} color={colors.textSecondary} />
        </TouchableOpacity>
      </View>
      
      {intent && (
        <View style={styles.intentTag}>
          <Ionicons name="flag" size={12} color="#FF9500" />
          <Text style={styles.intentText}>
            Detected: {intent.replace('_', ' ')}
          </Text>
        </View>
      )}
      
      {!!topic?.label && (
        <View style={{ marginBottom: 8, gap: 6 }}>
          <TouchableOpacity
            onPress={() => alternatives.length && setPickTopic(v => !v)}
            style={styles.topicTag}
            testID="ai-suggestion-topic"
            dataSet={{ testid: 'ai-suggestion-topic' } as any}
            activeOpacity={alternatives.length ? 0.7 : 1}
          >
            <Ionicons name="pricetag-outline" size={12} color={colors.textSecondary} />
            <Text style={styles.topicText} numberOfLines={1}>
              Replying about: {topic.label}{topic.switched ? ' (they changed the subject)' : ''}
            </Text>
            {alternatives.length > 0 && <Ionicons name={pickTopic ? 'chevron-up' : 'chevron-down'} size={12} color={colors.textSecondary} />}
          </TouchableOpacity>
          {pickTopic && alternatives.length > 0 && (
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }} testID="ai-suggestion-topic-options" dataSet={{ testid: 'ai-suggestion-topic-options' } as any}>
              <Text style={{ fontSize: 12, color: colors.textSecondary, alignSelf: 'center' }}>No, this is about:</Text>
              {alternatives.map(e => (
                <TouchableOpacity
                  key={e.kind}
                  onPress={() => { setPickTopic(false); onChangeTopic && onChangeTopic(e.kind); }}
                  style={styles.topicOption}
                  testID={`ai-suggestion-topic-${e.kind}`}
                  dataSet={{ testid: `ai-suggestion-topic-${e.kind}` } as any}
                >
                  <Text style={{ fontSize: 12, color: colors.text, fontWeight: '600' }} numberOfLines={1}>{e.label}</Text>
                </TouchableOpacity>
              ))}
            </View>
          )}
        </View>
      )}

      <View style={styles.suggestionBox}>
        <Text style={styles.suggestionText}>{suggestion}</Text>
      </View>
      
      <View style={styles.actions}>
        <TouchableOpacity style={styles.dismissButton} onPress={onDismiss}>
          <Text style={styles.dismissButtonText}>Dismiss</Text>
        </TouchableOpacity>
        
        <TouchableOpacity style={styles.editButton} onPress={onEdit}>
          <Ionicons name="create-outline" size={16} color="#007AFF" />
          <Text style={styles.editButtonText}>Edit</Text>
        </TouchableOpacity>
        
        <TouchableOpacity style={styles.acceptButton} onPress={onAccept}>
          <Ionicons name="send" size={16} color={colors.text} />
          <Text style={styles.acceptButtonText}>Send</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 12,
    marginHorizontal: 16,
    marginBottom: 8,
    borderWidth: 2,
    borderColor: '#34C75940',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  headerText: {
    fontSize: 15,
    fontWeight: '700',
    color: '#34C759',
  },
  intentTag: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FF950020',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
    gap: 4,
    marginBottom: 8,
    alignSelf: 'flex-start',
  },
  intentText: {
    fontSize: 13,
    color: '#FF9500',
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  topicTag: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    backgroundColor: colors.surface,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
    gap: 5,
    maxWidth: '100%',
  },
  topicText: {
    fontSize: 12,
    color: colors.textSecondary,
    fontWeight: '600',
    flexShrink: 1,
  },
  topicOption: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: colors.border,
    maxWidth: 260,
  },
  suggestionBox: {
    backgroundColor: colors.surface,
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
  },
  suggestionText: {
    fontSize: 16,
    color: colors.text,
    lineHeight: 21,
  },
  actions: {
    flexDirection: 'row',
    gap: 8,
  },
  dismissButton: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 8,
    backgroundColor: colors.surface,
    alignItems: 'center',
  },
  dismissButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  editButton: {
    flex: 1,
    flexDirection: 'row',
    paddingVertical: 10,
    borderRadius: 8,
    backgroundColor: '#007AFF20',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
  },
  editButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#007AFF',
  },
  acceptButton: {
    flex: 1,
    flexDirection: 'row',
    paddingVertical: 10,
    borderRadius: 8,
    backgroundColor: '#34C759',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
  },
  acceptButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
});
