import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  TextInput,
  Modal,
  Alert,
  ActivityIndicator,
  Platform,
  KeyboardAvoidingView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { templatesAPI } from '../../services/api';
import { useAuthStore } from '../../store/authStore';
import VoiceInput from '../../components/VoiceInput';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useThemeStore } from '../../store/themeStore';
interface Template {
  _id: string;
  name: string;
  content: string;
  category: string;
  is_default: boolean;
  usage_count: number;
}

const CATEGORIES = [
  { id: 'general', name: 'General', icon: 'document-text', color: '#8E8E93' },
  { id: 'greeting', name: 'Greeting', icon: 'hand-right', color: '#007AFF' },
  { id: 'follow_up', name: 'Follow Up', icon: 'refresh', color: '#34C759' },
  { id: 'appointment', name: 'Appointment', icon: 'calendar', color: '#FF9500' },
  { id: 'thank_you', name: 'Thank You', icon: 'heart', color: '#FF2D55' },
  { id: 'review_request', name: 'Review Request', icon: 'star', color: '#FFD60A' },
  { id: 'training_video', name: 'Training Video', icon: 'play-circle', color: '#AF52DE' },
  { id: 'referral', name: 'Referral', icon: 'people', color: '#5AC8FA' },
  { id: 'sold', name: 'Sold', icon: 'trophy', color: '#C9A962' },
  { id: 'review', name: 'Review', icon: 'star-half', color: '#FFD60A' },
];

export default function TemplatesSettings() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { user } = useAuthStore();
  const insets = useSafeAreaInsets();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<Template | null>(null);
  const [formName, setFormName] = useState('');
  const [formContent, setFormContent] = useState('');
  const [formCategory, setFormCategory] = useState('general');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (user?._id) {
      loadTemplates();
    }
  }, [user?._id]);

  const loadTemplates = async () => {
    if (!user?._id) return;
    try {
      setLoading(true);
      const data = await templatesAPI.getAll(user._id);
      setTemplates(data);
    } catch (error) {
      console.error('Error loading templates:', error);
      Alert.alert('Error', 'Failed to load templates');
    } finally {
      setLoading(false);
    }
  };

  const openCreateModal = () => {
    setEditingTemplate(null);
    setFormName('');
    setFormContent('');
    setFormCategory('general');
    setShowModal(true);
  };

  const openEditModal = (template: Template) => {
    setEditingTemplate(template);
    setFormName(template.name);
    setFormContent(template.content);
    setFormCategory(template.category);
    setShowModal(true);
  };

  const handleSave = async () => {
    if (!user?._id) return;
    if (!formName.trim() || !formContent.trim()) {
      Alert.alert('Error', 'Please fill in all fields');
      return;
    }

    try {
      setSaving(true);
      if (editingTemplate) {
        await templatesAPI.update(user._id, editingTemplate._id, {
          name: formName,
          content: formContent,
          category: formCategory,
        });
      } else {
        await templatesAPI.create(user._id, {
          name: formName,
          content: formContent,
          category: formCategory,
        });
      }
      setShowModal(false);
      loadTemplates();
    } catch (error: any) {
      console.error('Error saving template:', error);
      Alert.alert('Error', error.response?.data?.detail || 'Failed to save template');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (template: Template) => {
    if (template.is_default) {
      if (Platform.OS === 'web') {
        window.alert('Default templates cannot be deleted');
      } else {
        Alert.alert('Cannot Delete', 'Default templates cannot be deleted');
      }
      return;
    }

    const doDelete = async () => {
      if (!user?._id) return;
      try {
        await templatesAPI.delete(user._id, template._id);
        loadTemplates();
      } catch (error) {
        console.error('Error deleting template:', error);
        if (Platform.OS === 'web') {
          window.alert('Failed to delete template');
        } else {
          Alert.alert('Error', 'Failed to delete template');
        }
      }
    };

    if (Platform.OS === 'web') {
      if (window.confirm(`Are you sure you want to delete "${template.name}"?`)) {
        await doDelete();
      }
    } else {
      Alert.alert(
        'Delete Template',
        `Are you sure you want to delete "${template.name}"?`,
        [
          { text: 'Cancel', style: 'cancel' },
          { text: 'Delete', style: 'destructive', onPress: doDelete },
        ]
      );
    }
  };

  const getCategoryInfo = (categoryId: string) => {
    return CATEGORIES.find(c => c.id === categoryId) || CATEGORIES[0];
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#007AFF" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity
          style={styles.backButton}
          onPress={() => router.back()}
        >
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Message Templates</Text>
        <TouchableOpacity
          style={styles.addButton}
          onPress={openCreateModal}
        >
          <Ionicons name="add" size={28} color="#007AFF" />
        </TouchableOpacity>
      </View>

      {/* Info Banner */}
      <View style={styles.infoBanner}>
        <Ionicons name="information-circle" size={20} color="#007AFF" />
        <Text style={styles.infoText}>
          Use {'{name}'} in your templates to auto-fill the contact's name
        </Text>
      </View>

      {/* Templates List */}
      <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
        {templates.map((template) => {
          const category = getCategoryInfo(template.category);
          return (
            <TouchableOpacity
              key={template._id}
              style={styles.templateCard}
              onPress={() => openEditModal(template)}
              activeOpacity={0.7}
            >
              <View style={styles.templateHeader}>
                <View style={styles.templateIconContainer}>
                  <Ionicons
                    name={category.icon as any}
                    size={20}
                    color={category.color}
                  />
                </View>
                <View style={styles.templateInfo}>
                  <Text style={styles.templateName}>{template.name}</Text>
                  <Text style={styles.templateCategory}>{category.name}</Text>
                </View>
                <View style={styles.templateActions}>
                  {template.is_default && (
                    <View style={styles.defaultBadge}>
                      <Text style={styles.defaultBadgeText}>Default</Text>
                    </View>
                  )}
                  {!template.is_default && (
                    <TouchableOpacity
                      style={styles.deleteButton}
                      onPress={() => handleDelete(template)}
                    >
                      <Ionicons name="trash-outline" size={20} color="#FF3B30" />
                    </TouchableOpacity>
                  )}
                </View>
              </View>
              <Text style={styles.templateContent} numberOfLines={2}>
                {template.content}
              </Text>
              {template.usage_count > 0 && (
                <Text style={styles.usageCount}>
                  Used {template.usage_count} time{template.usage_count !== 1 ? 's' : ''}
                </Text>
              )}
            </TouchableOpacity>
          );
        })}

        {/* Create New Template Card */}
        <TouchableOpacity
          style={styles.createCard}
          onPress={openCreateModal}
        >
          <Ionicons name="add-circle-outline" size={32} color="#007AFF" />
          <Text style={styles.createText}>Create New Template</Text>
        </TouchableOpacity>

        <View style={{ height: 40 }} />
      </ScrollView>

      {/* Create/Edit Modal */}
      <Modal
        visible={showModal}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setShowModal(false)}
      >
        <KeyboardAvoidingView 
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={{ flex: 1 }}
          keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 20}
        >
          <View style={[styles.modalContainer, { paddingTop: insets.top }]}>
            {/* Ask Jessi bar — stays visible in the modal */}
            <View style={[styles.jessiBar, { backgroundColor: colors.surface || '#F2F2F7' }]}>
              <Text style={{ fontSize: 14, color: colors.textSecondary }}>Have questions? Ask Jessi</Text>
            </View>

            <View style={styles.modalHeader}>
              <TouchableOpacity onPress={() => setShowModal(false)}>
                <Text style={styles.cancelButton}>Cancel</Text>
              </TouchableOpacity>
              <Text style={styles.modalTitle}>
                {editingTemplate ? 'Edit Template' : 'New Template'}
              </Text>
              <TouchableOpacity onPress={handleSave} disabled={saving}>
                {saving ? (
                  <ActivityIndicator size="small" color="#007AFF" />
                ) : (
                  <Text style={styles.saveButton}>Save</Text>
                )}
              </TouchableOpacity>
            </View>

            <ScrollView 
              style={styles.modalContent}
              keyboardShouldPersistTaps="handled"
              contentContainerStyle={{ paddingBottom: 150 }}
            >
            {/* Name Input */}
            <Text style={styles.inputLabel}>Template Name</Text>
            <TextInput
              style={styles.input}
              value={formName}
              onChangeText={setFormName}
              placeholder="e.g., Quick Follow Up"
              placeholderTextColor={colors.textSecondary}
            />

            {/* Category Selector */}
            <Text style={styles.inputLabel}>Category</Text>
            <View style={styles.categoryGrid}>
              {CATEGORIES.map((cat) => (
                <TouchableOpacity
                  key={cat.id}
                  style={[
                    styles.categoryChip,
                    formCategory === cat.id && styles.categoryChipActive,
                    { borderColor: cat.color }
                  ]}
                  onPress={() => setFormCategory(cat.id)}
                >
                  <Ionicons
                    name={cat.icon as any}
                    size={16}
                    color={formCategory === cat.id ? '#FFF' : cat.color}
                  />
                  <Text
                    style={[
                      styles.categoryChipText,
                      formCategory === cat.id && styles.categoryChipTextActive,
                    ]}
                  >
                    {cat.name}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            {/* Content Input */}
            <View style={styles.contentLabelRow}>
              <Text style={styles.inputLabel}>Message Content</Text>
              <VoiceInput
                onTranscription={(text) => setFormContent((prev) => prev + ' ' + text)}
                size="small"
                color={colors.textSecondary}
              />
            </View>
            <TextInput
              style={[styles.input, styles.contentInput]}
              value={formContent}
              onChangeText={setFormContent}
              placeholder="Hi {name}! I wanted to reach out..."
              placeholderTextColor={colors.textSecondary}
              multiline
              textAlignVertical="top"
            />

            {/* Variable Helper */}
            <View style={styles.variableHelper}>
              <Text style={styles.variableLabel}>Available Variables:</Text>
              <TouchableOpacity
                style={styles.variableChip}
                onPress={() => setFormContent(formContent + '{name}')}
              >
                <Text style={styles.variableChipText}>{'{name}'}</Text>
              </TouchableOpacity>
            </View>
          </ScrollView>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </View>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.bg,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingTop: Platform.OS === 'ios' ? 60 : 20,
    paddingHorizontal: 16,
    paddingBottom: 16,
    backgroundColor: colors.bg,
    borderBottomWidth: 1,
    borderBottomColor: colors.card,
  },
  backButton: {
    width: 40,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  addButton: {
    width: 40,
    alignItems: 'flex-end',
  },
  infoBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    marginHorizontal: 16,
    marginTop: 16,
    padding: 12,
    borderRadius: 10,
    gap: 8,
  },
  infoText: {
    flex: 1,
    fontSize: 15,
    color: colors.textSecondary,
  },
  content: {
    flex: 1,
    paddingHorizontal: 16,
    paddingTop: 16,
  },
  templateCard: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
  },
  templateHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  templateIconContainer: {
    width: 36,
    height: 36,
    borderRadius: 8,
    backgroundColor: colors.surface,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  templateInfo: {
    flex: 1,
  },
  templateName: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  templateCategory: {
    fontSize: 15,
    color: colors.textSecondary,
    marginTop: 2,
  },
  templateActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  defaultBadge: {
    backgroundColor: colors.surface,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  defaultBadgeText: {
    fontSize: 13,
    color: colors.textSecondary,
    fontWeight: '500',
  },
  deleteButton: {
    padding: 4,
  },
  templateContent: {
    fontSize: 16,
    color: colors.textSecondary,
    lineHeight: 20,
  },
  usageCount: {
    fontSize: 14,
    color: '#6E6E73',
    marginTop: 8,
  },
  createCard: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 24,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.surface,
    borderStyle: 'dashed',
  },
  createText: {
    fontSize: 17,
    color: '#007AFF',
    marginTop: 8,
    fontWeight: '500',
  },
  modalContainer: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  jessiBar: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 4,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.card,
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingTop: 12,
    paddingHorizontal: 16,
    paddingBottom: 16,
    borderBottomWidth: 1,
    borderBottomColor: colors.card,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  cancelButton: {
    fontSize: 18,
    color: '#007AFF',
  },
  saveButton: {
    fontSize: 18,
    color: '#007AFF',
    fontWeight: '600',
  },
  modalContent: {
    flex: 1,
    padding: 16,
  },
  inputLabel: {
    fontSize: 15,
    color: colors.textSecondary,
    marginBottom: 8,
    marginTop: 16,
  },
  contentLabelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: 16,
    marginBottom: 8,
  },
  input: {
    backgroundColor: colors.card,
    borderRadius: 10,
    padding: 14,
    fontSize: 18,
    color: colors.text,
  },
  contentInput: {
    height: 150,
    paddingTop: 14,
  },
  categoryGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  categoryChip: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1,
    backgroundColor: colors.card,
    gap: 6,
  },
  categoryChipActive: {
    backgroundColor: '#007AFF',
    borderColor: '#007AFF',
  },
  categoryChipText: {
    fontSize: 15,
    color: colors.textSecondary,
  },
  categoryChipTextActive: {
    color: colors.text,
  },
  variableHelper: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 16,
    gap: 8,
  },
  variableLabel: {
    fontSize: 15,
    color: colors.textSecondary,
  },
  variableChip: {
    backgroundColor: colors.surface,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
  },
  variableChipText: {
    fontSize: 15,
    color: '#007AFF',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
});
