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
  FlatList,
  Platform,
  KeyboardAvoidingView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { emailAPI } from '../../services/api';
import { useAuthStore } from '../../store/authStore';

interface EmailCampaign {
  _id: string;
  name: string;
  description?: string;
  subject: string;
  html_content: string;
  trigger_type: string;
  active: boolean;
  sent_count: number;
  open_count: number;
  click_count: number;
  created_at: string;
}

const TRIGGER_TYPES = [
  { id: 'manual', name: 'Manual Send', icon: 'hand-left', description: 'Send manually when needed' },
  { id: 'birthday', name: 'Birthday', icon: 'gift', description: 'Auto-send on contact birthday' },
  { id: 'anniversary', name: 'Anniversary', icon: 'calendar', description: 'Auto-send on purchase anniversary' },
  { id: 'follow_up', name: 'Follow Up', icon: 'refresh', description: 'Auto-send after set time period' },
];

export default function EmailCampaignsPage() {
  const router = useRouter();
  const { user } = useAuthStore();
  const [campaigns, setCampaigns] = useState<EmailCampaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingCampaign, setEditingCampaign] = useState<EmailCampaign | null>(null);
  const [formName, setFormName] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [formSubject, setFormSubject] = useState('');
  const [formContent, setFormContent] = useState('');
  const [formTriggerType, setFormTriggerType] = useState('manual');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadCampaigns();
  }, []);

  const loadCampaigns = async () => {
    if (!user?._id) return;
    try {
      setLoading(true);
      const data = await emailAPI.getCampaigns(user._id);
      setCampaigns(data);
    } catch (error) {
      console.error('Error loading campaigns:', error);
    } finally {
      setLoading(false);
    }
  };

  const openCreateModal = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setEditingCampaign(null);
    setFormName('');
    setFormDescription('');
    setFormSubject('');
    setFormContent('');
    setFormTriggerType('manual');
    setShowModal(true);
  };

  const openEditModal = (campaign: EmailCampaign) => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setEditingCampaign(campaign);
    setFormName(campaign.name);
    setFormDescription(campaign.description || '');
    setFormSubject(campaign.subject);
    setFormContent(campaign.html_content);
    setFormTriggerType(campaign.trigger_type);
    setShowModal(true);
  };

  const handleSave = async () => {
    if (!formName.trim() || !formSubject.trim() || !formContent.trim()) {
      Alert.alert('Error', 'Please fill in all required fields');
      return;
    }

    if (!user?._id) return;

    try {
      setSaving(true);
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);

      if (editingCampaign) {
        await emailAPI.updateCampaign(user._id, editingCampaign._id, {
          name: formName,
          description: formDescription,
          subject: formSubject,
          html_content: formContent,
          trigger_type: formTriggerType,
        });
      } else {
        await emailAPI.createCampaign(user._id, {
          name: formName,
          description: formDescription,
          subject: formSubject,
          html_content: formContent,
          trigger_type: formTriggerType,
        });
      }

      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      setShowModal(false);
      loadCampaigns();
    } catch (error) {
      console.error('Error saving campaign:', error);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      Alert.alert('Error', 'Failed to save campaign');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = (campaign: EmailCampaign) => {
    Alert.alert(
      'Delete Campaign',
      `Are you sure you want to delete "${campaign.name}"?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
              await emailAPI.deleteCampaign(user!._id, campaign._id);
              loadCampaigns();
            } catch (error) {
              Alert.alert('Error', 'Failed to delete campaign');
            }
          },
        },
      ]
    );
  };

  const toggleCampaignStatus = async (campaign: EmailCampaign) => {
    if (!user?._id) return;
    try {
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
      await emailAPI.updateCampaign(user._id, campaign._id, {
        active: !campaign.active,
      });
      loadCampaigns();
    } catch (error) {
      Alert.alert('Error', 'Failed to update campaign status');
    }
  };

  const getTriggerInfo = (triggerId: string) => {
    return TRIGGER_TYPES.find((t) => t.id === triggerId) || TRIGGER_TYPES[0];
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
        <Text style={styles.headerTitle}>Email Campaigns</Text>
        <TouchableOpacity onPress={openCreateModal} style={styles.addButton}>
          <Ionicons name="add-circle" size={28} color="#007AFF" />
        </TouchableOpacity>
      </View>

      {campaigns.length === 0 ? (
        <View style={styles.emptyContainer}>
          <View style={styles.emptyIcon}>
            <Ionicons name="mail-outline" size={64} color="#2C2C2E" />
          </View>
          <Text style={styles.emptyTitle}>No Email Campaigns</Text>
          <Text style={styles.emptySubtitle}>
            Create automated email campaigns to nurture your contacts
          </Text>
          <TouchableOpacity style={styles.createButton} onPress={openCreateModal}>
            <Ionicons name="add" size={20} color="#FFF" />
            <Text style={styles.createButtonText}>Create Campaign</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <FlatList
          data={campaigns}
          keyExtractor={(item) => item._id}
          contentContainerStyle={styles.listContent}
          renderItem={({ item }) => {
            const trigger = getTriggerInfo(item.trigger_type);
            return (
              <TouchableOpacity
                style={styles.campaignCard}
                onPress={() => openEditModal(item)}
                onLongPress={() => handleDelete(item)}
              >
                <View style={styles.campaignHeader}>
                  <View style={[styles.triggerBadge, { backgroundColor: item.active ? '#34C75920' : '#8E8E9320' }]}>
                    <Ionicons 
                      name={trigger.icon as any} 
                      size={16} 
                      color={item.active ? '#34C759' : '#8E8E93'} 
                    />
                  </View>
                  <View style={styles.campaignInfo}>
                    <Text style={styles.campaignName}>{item.name}</Text>
                    <Text style={styles.campaignSubject} numberOfLines={1}>
                      Subject: {item.subject}
                    </Text>
                  </View>
                  <TouchableOpacity
                    style={[styles.statusToggle, item.active && styles.statusToggleActive]}
                    onPress={() => toggleCampaignStatus(item)}
                  >
                    <Text style={[styles.statusText, item.active && styles.statusTextActive]}>
                      {item.active ? 'Active' : 'Paused'}
                    </Text>
                  </TouchableOpacity>
                </View>
                
                {item.description && (
                  <Text style={styles.campaignDescription} numberOfLines={2}>
                    {item.description}
                  </Text>
                )}
                
                <View style={styles.campaignStats}>
                  <View style={styles.statItem}>
                    <Ionicons name="paper-plane" size={14} color="#8E8E93" />
                    <Text style={styles.statValue}>{item.sent_count}</Text>
                    <Text style={styles.statLabel}>Sent</Text>
                  </View>
                  <View style={styles.statItem}>
                    <Ionicons name="eye" size={14} color="#8E8E93" />
                    <Text style={styles.statValue}>{item.open_count}</Text>
                    <Text style={styles.statLabel}>Opens</Text>
                  </View>
                  <View style={styles.statItem}>
                    <Ionicons name="finger-print" size={14} color="#8E8E93" />
                    <Text style={styles.statValue}>{item.click_count}</Text>
                    <Text style={styles.statLabel}>Clicks</Text>
                  </View>
                </View>
              </TouchableOpacity>
            );
          }}
        />
      )}

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
                {editingCampaign ? 'Edit Campaign' : 'New Campaign'}
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
                <Text style={styles.inputLabel}>Campaign Name *</Text>
                <TextInput
                  style={styles.input}
                  placeholder="e.g., Birthday Greetings"
                  placeholderTextColor="#8E8E93"
                  value={formName}
                  onChangeText={setFormName}
                />
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Description</Text>
                <TextInput
                  style={styles.input}
                  placeholder="Brief description of this campaign"
                  placeholderTextColor="#8E8E93"
                  value={formDescription}
                  onChangeText={setFormDescription}
                />
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Trigger Type</Text>
                <View style={styles.triggerOptions}>
                  {TRIGGER_TYPES.map((trigger) => (
                    <TouchableOpacity
                      key={trigger.id}
                      style={[
                        styles.triggerOption,
                        formTriggerType === trigger.id && styles.triggerOptionSelected,
                      ]}
                      onPress={() => setFormTriggerType(trigger.id)}
                    >
                      <Ionicons
                        name={trigger.icon as any}
                        size={20}
                        color={formTriggerType === trigger.id ? '#007AFF' : '#8E8E93'}
                      />
                      <Text style={[
                        styles.triggerOptionName,
                        formTriggerType === trigger.id && styles.triggerOptionNameSelected,
                      ]}>
                        {trigger.name}
                      </Text>
                      <Text style={styles.triggerOptionDesc}>{trigger.description}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Email Subject *</Text>
                <TextInput
                  style={styles.input}
                  placeholder="e.g., Happy Birthday, {name}!"
                  placeholderTextColor="#8E8E93"
                  value={formSubject}
                  onChangeText={setFormSubject}
                />
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Email Content (HTML) *</Text>
                <TextInput
                  style={[styles.input, styles.textArea]}
                  placeholder="Enter your email HTML content..."
                  placeholderTextColor="#8E8E93"
                  value={formContent}
                  onChangeText={setFormContent}
                  multiline
                  numberOfLines={8}
                  textAlignVertical="top"
                />
              </View>

              <View style={styles.placeholdersInfo}>
                <Text style={styles.placeholdersTitle}>Available Placeholders:</Text>
                <Text style={styles.placeholder}>{'{name}'} - Contact's name</Text>
                <Text style={styles.placeholder}>{'{sender_name}'} - Your name</Text>
                <Text style={styles.placeholder}>{'{company_name}'} - Company name</Text>
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
  listContent: {
    padding: 16,
  },
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 40,
  },
  emptyIcon: {
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: '#1C1C1E',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 24,
  },
  emptyTitle: {
    fontSize: 22,
    fontWeight: '700',
    color: '#FFF',
    marginBottom: 8,
  },
  emptySubtitle: {
    fontSize: 15,
    color: '#8E8E93',
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: 32,
  },
  createButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#007AFF',
    paddingVertical: 14,
    paddingHorizontal: 24,
    borderRadius: 12,
    gap: 8,
  },
  createButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  campaignCard: {
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
  },
  campaignHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  triggerBadge: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  campaignInfo: {
    flex: 1,
  },
  campaignName: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 2,
  },
  campaignSubject: {
    fontSize: 13,
    color: '#8E8E93',
  },
  statusToggle: {
    backgroundColor: '#2C2C2E',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
  },
  statusToggleActive: {
    backgroundColor: '#34C75920',
  },
  statusText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#8E8E93',
  },
  statusTextActive: {
    color: '#34C759',
  },
  campaignDescription: {
    fontSize: 14,
    color: '#8E8E93',
    marginTop: 12,
    lineHeight: 20,
  },
  campaignStats: {
    flexDirection: 'row',
    marginTop: 16,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: '#2C2C2E',
    gap: 24,
  },
  statItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  statValue: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFF',
  },
  statLabel: {
    fontSize: 13,
    color: '#8E8E93',
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
    height: 150,
    textAlignVertical: 'top',
  },
  triggerOptions: {
    gap: 8,
  },
  triggerOption: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    borderWidth: 2,
    borderColor: 'transparent',
  },
  triggerOptionSelected: {
    borderColor: '#007AFF',
    backgroundColor: '#007AFF10',
  },
  triggerOptionName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
    marginTop: 8,
  },
  triggerOptionNameSelected: {
    color: '#007AFF',
  },
  triggerOptionDesc: {
    fontSize: 13,
    color: '#8E8E93',
    marginTop: 4,
  },
  placeholdersInfo: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginTop: 12,
    marginBottom: 40,
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
