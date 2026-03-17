import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  TextInput,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAuthStore } from '../../../store/authStore';
import { useThemeStore } from '../../../store/themeStore';
import api from '../../../services/api';

function MarkdownRenderer({ content, colors }: { content: string; colors: any }) {
  const lines = content.split('\n');
  const elements: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    if (trimmed === '') {
      elements.push(<View key={i} style={{ height: 8 }} />);
      i++;
      continue;
    }

    if (trimmed.startsWith('# ') && !trimmed.startsWith('## ')) {
      elements.push(
        <Text key={i} style={{
          fontSize: 24, fontWeight: '800', color: colors.text,
          marginTop: 24, marginBottom: 8, letterSpacing: -0.3,
        }}>
          {trimmed.replace(/^# /, '')}
        </Text>
      );
      i++;
      continue;
    }

    if (trimmed.startsWith('## ')) {
      elements.push(
        <Text key={i} style={{
          fontSize: 18, fontWeight: '700', color: colors.text,
          marginTop: 20, marginBottom: 6,
        }}>
          {trimmed.replace(/^## /, '')}
        </Text>
      );
      i++;
      continue;
    }

    if (trimmed.startsWith('### ')) {
      elements.push(
        <Text key={i} style={{
          fontSize: 15, fontWeight: '700', color: '#AF52DE',
          marginTop: 16, marginBottom: 4,
        }}>
          {trimmed.replace(/^### /, '')}
        </Text>
      );
      i++;
      continue;
    }

    if (trimmed === '---') {
      elements.push(
        <View key={i} style={{
          height: 1, backgroundColor: colors.card,
          marginVertical: 16,
        }} />
      );
      i++;
      continue;
    }

    if (trimmed.startsWith('- ')) {
      const bulletText = trimmed.replace(/^- /, '');
      elements.push(
        <View key={i} style={{ flexDirection: 'row', paddingLeft: 8, marginBottom: 4 }}>
          <Text style={{ fontSize: 14, color: '#AF52DE', marginRight: 8, marginTop: 1 }}>*</Text>
          <Text style={{ fontSize: 14, color: colors.text, opacity: 0.85, lineHeight: 22, flex: 1 }}>
            {renderInlineMarkdown(bulletText, colors)}
          </Text>
        </View>
      );
      i++;
      continue;
    }

    if (trimmed.startsWith('  - ')) {
      const bulletText = trimmed.replace(/^\s+- /, '');
      elements.push(
        <View key={i} style={{ flexDirection: 'row', paddingLeft: 24, marginBottom: 3 }}>
          <Text style={{ fontSize: 12, color: colors.textSecondary, marginRight: 8 }}>-</Text>
          <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 20, flex: 1 }}>
            {renderInlineMarkdown(bulletText, colors)}
          </Text>
        </View>
      );
      i++;
      continue;
    }

    // Regular paragraph
    elements.push(
      <Text key={i} style={{
        fontSize: 14, color: colors.text, opacity: 0.85,
        lineHeight: 22, marginBottom: 4,
      }}>
        {renderInlineMarkdown(trimmed, colors)}
      </Text>
    );
    i++;
  }

  return <>{elements}</>;
}

function renderInlineMarkdown(text: string, colors: any): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((part, idx) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <Text key={idx} style={{ fontWeight: '700', color: colors.text }}>{part.slice(2, -2)}</Text>;
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <Text key={idx} style={{
          fontFamily: Platform.OS === 'web' ? 'monospace' : 'Courier',
          backgroundColor: colors.card,
          color: '#FF9500',
          fontSize: 12,
          paddingHorizontal: 4,
          borderRadius: 3,
        }}>
          {part.slice(1, -1)}
        </Text>
      );
    }
    return <Text key={idx}>{part}</Text>;
  });
}

export default function PRDScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const user = useAuthStore((state) => state.user);

  const [content, setContent] = useState('');
  const [editContent, setEditContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState('');
  const [hasChanges, setHasChanges] = useState(false);
  const scrollRef = useRef<ScrollView>(null);

  useEffect(() => {
    loadPRD();
  }, []);

  const loadPRD = async () => {
    try {
      const headers = { 'X-User-ID': user?._id };
      const res = await api.get('/docs/prd', { headers });
      const c = res.data.content || '';
      setContent(c);
      setEditContent(c);
      setLastUpdated(res.data.updated_at || '');
    } catch (error) {
      console.error('Failed to load PRD:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const headers = { 'X-User-ID': user?._id };
      const res = await api.put('/docs/prd', { content: editContent }, { headers });
      setContent(editContent);
      setLastUpdated(res.data.updated_at || new Date().toISOString());
      setEditing(false);
      setHasChanges(false);
    } catch (error) {
      console.error('Failed to save PRD:', error);
      alert('Failed to save. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    setEditContent(content);
    setEditing(false);
    setHasChanges(false);
  };

  const handleEditChange = (text: string) => {
    setEditContent(text);
    setHasChanges(text !== content);
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#AF52DE" />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton} data-testid="prd-back-btn">
          <Ionicons name="chevron-back" size={28} color="#AF52DE" />
        </TouchableOpacity>
        <View style={styles.headerCenter}>
          <Text style={styles.headerTitle}>Product Requirements</Text>
          {lastUpdated ? (
            <Text style={styles.headerSubtitle}>
              Updated {new Date(lastUpdated).toLocaleDateString('en-US', {
                month: 'short', day: 'numeric', year: 'numeric',
              })}
            </Text>
          ) : null}
        </View>
        {!editing ? (
          <TouchableOpacity
            onPress={() => setEditing(true)}
            style={styles.editButton}
            data-testid="prd-edit-btn"
          >
            <Ionicons name="create-outline" size={20} color="#AF52DE" />
          </TouchableOpacity>
        ) : (
          <View style={{ width: 40 }} />
        )}
      </View>

      {/* Edit/Save toolbar */}
      {editing && (
        <View style={styles.editToolbar}>
          <TouchableOpacity
            onPress={handleCancel}
            style={styles.cancelButton}
            data-testid="prd-cancel-btn"
          >
            <Text style={styles.cancelButtonText}>Cancel</Text>
          </TouchableOpacity>
          <View style={styles.editingBadge}>
            <View style={styles.editDot} />
            <Text style={styles.editingText}>Editing</Text>
          </View>
          <TouchableOpacity
            onPress={handleSave}
            disabled={saving || !hasChanges}
            style={[
              styles.saveButton,
              (!hasChanges || saving) && { opacity: 0.5 },
            ]}
            data-testid="prd-save-btn"
          >
            {saving ? (
              <ActivityIndicator size="small" color="#FFF" />
            ) : (
              <>
                <Ionicons name="checkmark" size={18} color="#FFF" />
                <Text style={styles.saveButtonText}>Save</Text>
              </>
            )}
          </TouchableOpacity>
        </View>
      )}

      {/* Content */}
      {editing ? (
        <ScrollView style={styles.editorScroll} ref={scrollRef}>
          <TextInput
            style={styles.editor}
            value={editContent}
            onChangeText={handleEditChange}
            multiline
            textAlignVertical="top"
            autoCapitalize="none"
            autoCorrect={false}
            scrollEnabled={false}
            data-testid="prd-editor-input"
          />
        </ScrollView>
      ) : (
        <ScrollView
          style={styles.viewerScroll}
          contentContainerStyle={styles.viewerContent}
          ref={scrollRef}
        >
          <MarkdownRenderer content={content} colors={colors} />
          <View style={{ height: 60 }} />
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.card,
  },
  backButton: { padding: 4, width: 40 },
  headerCenter: { flex: 1, alignItems: 'center' },
  headerTitle: { fontSize: 17, fontWeight: '700', color: colors.text },
  headerSubtitle: { fontSize: 11, color: colors.textSecondary, marginTop: 2 },
  editButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#AF52DE15',
    justifyContent: 'center',
    alignItems: 'center',
  },
  editToolbar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 10,
    backgroundColor: colors.card,
    borderBottomWidth: 1,
    borderBottomColor: '#2A2A2A',
  },
  cancelButton: {
    paddingHorizontal: 14,
    paddingVertical: 7,
    borderRadius: 8,
    backgroundColor: '#FF3B3020',
  },
  cancelButtonText: { fontSize: 14, fontWeight: '600', color: '#FF3B30' },
  editingBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  editDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#34C759',
  },
  editingText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#34C759',
  },
  saveButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
    backgroundColor: '#AF52DE',
  },
  saveButtonText: { fontSize: 14, fontWeight: '700', color: '#FFF' },
  editorScroll: { flex: 1 },
  editor: {
    flex: 1,
    padding: 16,
    fontSize: 14,
    fontFamily: Platform.OS === 'web' ? 'monospace' : 'Courier',
    color: colors.text,
    lineHeight: 22,
    minHeight: 800,
  },
  viewerScroll: { flex: 1 },
  viewerContent: { padding: 20, paddingBottom: 40 },
});
