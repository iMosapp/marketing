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
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { emailAPI } from '../../services/api';
import { useAuthStore } from '../../store/authStore';

interface EmailTemplate {
  _id: string;
  name: string;
  subject: string;
  html_content: string;
  category: string;
  is_default: boolean;
  usage_count?: number;
}

const CATEGORIES = [
  { id: 'general', name: 'General', icon: 'document-text', color: '#8E8E93' },
  { id: 'greeting', name: 'Greeting', icon: 'hand-right', color: '#007AFF' },
  { id: 'follow_up', name: 'Follow Up', icon: 'refresh', color: '#34C759' },
  { id: 'digital_card', name: 'Digital Card', icon: 'card', color: '#5856D6' },
  { id: 'review_request', name: 'Review Request', icon: 'star', color: '#FFD60A' },
  { id: 'photo_share', name: 'Photo Share', icon: 'image', color: '#FF9500' },
];

export default function EmailTemplatesSettings() {
  const router = useRouter();
  const { user } = useAuthStore();
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<EmailTemplate | null>(null);
  const [formName, setFormName] = useState('');
  const [formSubject, setFormSubject] = useState('');
  const [formContent, setFormContent] = useState('');
  const [formCategory, setFormCategory] = useState('general');
  const [saving, setSaving] = useState(false);
  const [showPreview, setShowPreview] = useState(false);

  useEffect(() => {
    loadTemplates();
  }, [user?._id]);

  const loadTemplates = async () => {
    if (!user?._id) {
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const data = await emailAPI.getTemplates(user._id);
      setTemplates(data);
    } catch (error) {
      console.error('Error loading templates:', error);
      Alert.alert('Error', 'Failed to load email templates');
    } finally {
      setLoading(false);
    }
  };

  const openCreateModal = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setEditingTemplate(null);
    setFormName('');
    setFormSubject('');
    setFormContent('');
    setFormCategory('general');
    setShowModal(true);
  };

  const openEditModal = (template: EmailTemplate) => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setEditingTemplate(template);
    setFormName(template.name);
    setFormSubject(template.subject);
    setFormContent(template.html_content);
    setFormCategory(template.category);
    setShowModal(true);
  };

  const handleSave = async () => {
    if (!formName.trim() || !formSubject.trim() || !formContent.trim()) {
      Alert.alert('Error', 'Please fill in all fields');
      return;
    }

    if (!user?._id) return;

    try {
      setSaving(true);
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);

      if (editingTemplate) {
        await emailAPI.updateTemplate(user._id, editingTemplate._id, {
          name: formName,
          subject: formSubject,
          html_content: formContent,
          category: formCategory,
        });
      } else {
        await emailAPI.createTemplate(user._id, {
          name: formName,
          subject: formSubject,
          html_content: formContent,
          category: formCategory,
        });
      }

      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      setShowModal(false);
      loadTemplates();
    } catch (error) {
      console.error('Error saving template:', error);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      Alert.alert('Error', 'Failed to save template');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = (template: EmailTemplate) => {
    if (template.is_default) {
      Alert.alert('Cannot Delete', 'Default templates cannot be deleted');
      return;
    }

    Alert.alert(
      'Delete Template',
      `Are you sure you want to delete "${template.name}"?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
              await emailAPI.deleteTemplate(user!._id, template._id);
              loadTemplates();
            } catch (error) {
              Alert.alert('Error', 'Failed to delete template');
            }
          },
        },
      ]
    );
  };

  const getCategoryInfo = (categoryId: string) => {
    return CATEGORIES.find((c) => c.id === categoryId) || CATEGORIES[0];
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Email Templates</Text>
        <TouchableOpacity onPress={openCreateModal} style={styles.addButton}>
          <Ionicons name="add-circle" size={28} color="#007AFF" />
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        {/* Placeholders Info */}
        <View style={styles.infoCard}>
          <Ionicons name="information-circle" size={20} color="#007AFF" />
          <Text style={styles.infoText}>
            Use placeholders like {'{name}'}, {'{sender_name}'}, {'{card_link}'}, {'{review_link}'} in your templates. 
            They'll be replaced with actual values when sending.
          </Text>
        </View>

        {/* Templates List */}
        {templates.length === 0 ? (
          <View style={styles.emptyContainer}>
            <Ionicons name="mail-outline" size={64} color="#2C2C2E" />
            <Text style={styles.emptyText}>No email templates yet</Text>
            <Text style={styles.emptySubtext}>
              Create templates to quickly send professional emails
            </Text>
          </View>
        ) : (
          templates.map((template) => {
            const category = getCategoryInfo(template.category);
            return (
              <TouchableOpacity
                key={template._id}
                style={styles.templateCard}
                onPress={() => openEditModal(template)}
                onLongPress={() => handleDelete(template)}
              >
                <View style={[styles.categoryBadge, { backgroundColor: `${category.color}20` }]}>
                  <Ionicons name={category.icon as any} size={16} color={category.color} />
                </View>
                <View style={styles.templateInfo}>
                  <Text style={styles.templateName}>{template.name}</Text>
                  <Text style={styles.templateSubject} numberOfLines={1}>
                    Subject: {template.subject}
                  </Text>
                  <Text style={styles.templatePreview} numberOfLines={2}>
                    {template.html_content.replace(/<[^>]*>/g, '').substring(0, 100)}...
                  </Text>
                </View>
                {template.is_default && (
                  <View style={styles.defaultBadge}>
                    <Text style={styles.defaultBadgeText}>Default</Text>
                  </View>
                )}
                <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
              </TouchableOpacity>
            );
          })
        )}
      </ScrollView>

      {/* Edit/Create Modal */}
      <Modal visible={showModal} animationType="slide" presentationStyle="pageSheet">
        <SafeAreaView style={styles.modalContainer}>
          <KeyboardAvoidingView 
            behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
            style={{ flex: 1 }}
          >
            <View style={styles.modalHeader}>
              <TouchableOpacity onPress={() => setShowModal(false)}>
                <Text style={styles.modalCancel}>Cancel</Text>
              </TouchableOpacity>
              <Text style={styles.modalTitle}>
                {editingTemplate ? 'Edit Template' : 'New Template'}
              </Text>
              <TouchableOpacity onPress={handleSave} disabled={saving}>
                {saving ? (
                  <ActivityIndicator size="small" color="#007AFF" />
                ) : (
                  <Text style={styles.modalSave}>Save</Text>
                )}
              </TouchableOpacity>
            </View>

            <ScrollView style={styles.modalContent} keyboardShouldPersistTaps="handled">
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Template Name</Text>
                <TextInput
                  style={styles.input}
                  placeholder="e.g., Welcome Email"
                  placeholderTextColor="#8E8E93"
                  value={formName}
                  onChangeText={setFormName}
                />
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Email Subject</Text>
                <TextInput
                  style={styles.input}
                  placeholder="e.g., Welcome to {company_name}!"
                  placeholderTextColor="#8E8E93"
                  value={formSubject}
                  onChangeText={setFormSubject}
                />
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Category</Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                  <View style={styles.categoryOptions}>
                    {CATEGORIES.map((cat) => (
                      <TouchableOpacity
                        key={cat.id}
                        style={[
                          styles.categoryOption,
                          formCategory === cat.id && styles.categoryOptionSelected,
                          formCategory === cat.id && { borderColor: cat.color },
                        ]}
                        onPress={() => setFormCategory(cat.id)}
                      >
                        <Ionicons
                          name={cat.icon as any}
                          size={16}
                          color={formCategory === cat.id ? cat.color : '#8E8E93'}
                        />
                        <Text
                          style={[
                            styles.categoryOptionText,
                            formCategory === cat.id && { color: cat.color },
                          ]}
                        >
                          {cat.name}
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </ScrollView>
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Email Content (HTML)</Text>
                <TextInput
                  style={[styles.input, styles.textArea]}
                  placeholder="Enter your email HTML content here..."
                  placeholderTextColor="#8E8E93"
                  value={formContent}
                  onChangeText={setFormContent}
                  multiline
                  numberOfLines={10}
                  textAlignVertical="top"
                />
              </View>

              <View style={styles.placeholdersInfo}>
                <Text style={styles.placeholdersTitle}>Available Placeholders:</Text>
                <Text style={styles.placeholder}>{'{name}'} - Recipient's name</Text>
                <Text style={styles.placeholder}>{'{sender_name}'} - Your name</Text>
                <Text style={styles.placeholder}>{'{company_name}'} - Company name</Text>
                <Text style={styles.placeholder}>{'{card_link}'} - Digital card URL</Text>
                <Text style={styles.placeholder}>{'{review_link}'} - Review page URL</Text>
                <Text style={styles.placeholder}>{'{photos}'} - Photo gallery HTML</Text>
              </View>
            </ScrollView>
          </KeyboardAvoidingView>
        </SafeAreaView>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  backButton: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  addButton: {
    padding: 4,
  },
  content: {
    padding: 16,
    paddingBottom: 40,
  },
  infoCard: {
    flexDirection: 'row',
    backgroundColor: '#007AFF20',
    borderRadius: 12,
    padding: 16,
    gap: 12,
    marginBottom: 24,
    alignItems: 'flex-start',
  },
  infoText: {
    flex: 1,
    fontSize: 14,
    color: '#007AFF',
    lineHeight: 20,
  },
  emptyContainer: {
    alignItems: 'center',
    paddingVertical: 60,
  },
  emptyText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFF',
    marginTop: 16,
  },
  emptySubtext: {
    fontSize: 14,
    color: '#8E8E93',
    marginTop: 8,
    textAlign: 'center',
  },
  templateCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    gap: 12,
  },
  categoryBadge: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  templateInfo: {
    flex: 1,
  },
  templateName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 4,
  },
  templateSubject: {
    fontSize: 13,
    color: '#8E8E93',
    marginBottom: 4,
  },
  templatePreview: {
    fontSize: 12,
    color: '#6E6E73',
    lineHeight: 16,
  },
  defaultBadge: {
    backgroundColor: '#34C75920',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
  },
  defaultBadgeText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#34C759',
  },

  // Modal Styles
  modalContainer: {
    flex: 1,
    backgroundColor: '#000',
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  modalCancel: {
    fontSize: 16,
    color: '#8E8E93',
  },
  modalTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  modalSave: {
    fontSize: 16,
    fontWeight: '600',
    color: '#007AFF',
  },
  modalContent: {
    flex: 1,
    padding: 16,
  },
  inputGroup: {
    marginBottom: 20,
  },
  inputLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: '#8E8E93',
    marginBottom: 8,
  },
  input: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    fontSize: 16,
    color: '#FFF',
    borderWidth: 1,
    borderColor: '#2C2C2E',
  },
  textArea: {
    height: 200,
    textAlignVertical: 'top',
  },
  categoryOptions: {
    flexDirection: 'row',
    gap: 8,
    paddingVertical: 4,
  },
  categoryOption: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 20,
    gap: 6,
    borderWidth: 2,
    borderColor: 'transparent',
  },
  categoryOptionSelected: {
    backgroundColor: '#2C2C2E',
  },
  categoryOptionText: {
    fontSize: 14,
    color: '#8E8E93',
  },
  placeholdersInfo: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginTop: 12,
  },
  placeholdersTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 12,
  },
  placeholder: {
    fontSize: 13,
    color: '#8E8E93',
    marginBottom: 6,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
});
