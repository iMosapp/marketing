import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { useThemeStore } from '../store/themeStore';
interface AISuggestionProps {
  suggestion: string;
  intent?: string;
  onAccept: () => void;
  onEdit: () => void;
  onDismiss: () => void;
}

export default function AISuggestion({
  suggestion,
  intent,
  onAccept,
  onEdit,
  onDismiss,
}: AISuggestionProps) {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Ionicons name="sparkles" size={16} color="#34C759" />
          <Text style={styles.headerText}>MVP suggests:</Text>
        </View>
        <TouchableOpacity onPress={onDismiss}>
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
    fontSize: 13,
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
    fontSize: 11,
    color: '#FF9500',
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  suggestionBox: {
    backgroundColor: colors.surface,
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
  },
  suggestionText: {
    fontSize: 15,
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
    fontSize: 14,
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
    fontSize: 14,
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
    fontSize: 14,
    fontWeight: '600',
    color: colors.text,
  },
});
