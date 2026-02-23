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
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { tagsAPI } from '../../services/api';
import { useAuthStore } from '../../store/authStore';

interface Tag {
  _id: string;
  name: string;
  color: string;
  icon: string;
  contact_count: number;
}

const TAG_COLORS = [
  "#FF3B30", "#FF9500", "#FFCC00", "#34C759", "#007AFF",
  "#5856D6", "#AF52DE", "#FF2D55", "#00C7BE", "#8E8E93",
];

const TAG_ICONS = [
  { id: "pricetag", name: "Tag" },
  { id: "flame", name: "Hot" },
  { id: "star", name: "Star" },
  { id: "heart", name: "Heart" },
  { id: "person-add", name: "New" },
  { id: "refresh", name: "Follow Up" },
  { id: "construct", name: "Service" },
  { id: "car", name: "Vehicle" },
  { id: "cash", name: "Money" },
  { id: "warning", name: "Alert" },
  { id: "checkmark-circle", name: "Done" },
  { id: "time", name: "Time" },
];

export default function TagsSettings() {
  const router = useRouter();
  const { user } = useAuthStore();
  const [tags, setTags] = useState<Tag[]>([]);
  const [pendingTags, setPendingTags] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingTag, setEditingTag] = useState<Tag | null>(null);
  const [formName, setFormName] = useState('');
  const [formColor, setFormColor] = useState(TAG_COLORS[0]);
  const [formIcon, setFormIcon] = useState('pricetag');
  const [saving, setSaving] = useState(false);
  
  const isAdmin = user?.role === 'super_admin' || user?.role === 'org_admin' || user?.role === 'admin';
  const isInOrg = !!user?.org_id;

  useEffect(() => {
    if (user?._id) {
      loadTags();
      if (isAdmin && isInOrg) {
        loadPendingTags();
      }
    }
  }, [user?._id]);

  const loadTags = async () => {
    if (!user?._id) return;
    try {
      setLoading(true);
      const data = await tagsAPI.getAll(user._id);
      setTags(data);
    } catch (error) {
      console.error('Error loading tags:', error);
      Alert.alert('Error', 'Failed to load tags');
    } finally {
      setLoading(false);
    }
  };
  
  const loadPendingTags = async () => {
    if (!user?._id) return;
    try {
      const data = await tagsAPI.getPending(user._id);
      setPendingTags(data);
    } catch (error) {
      console.error('Error loading pending tags:', error);
    }
  };
  
  const handleApprove = async (tagId: string) => {
    if (!user?._id) return;
    try {
      await tagsAPI.approve(user._id, tagId);
      loadTags();
      loadPendingTags();
    } catch (error) {
      console.error('Error approving tag:', error);
      Alert.alert('Error', 'Failed to approve tag');
    }
  };
  
  const handleReject = (tag: any) => {
    Alert.alert(
      'Reject Tag',
      `Are you sure you want to reject "${tag.name}"?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Reject',
          style: 'destructive',
          onPress: async () => {
            if (!user?._id) return;
            try {
              await tagsAPI.reject(user._id, tag._id);
              loadPendingTags();
            } catch (error) {
              console.error('Error rejecting tag:', error);
              Alert.alert('Error', 'Failed to reject tag');
            }
          },
        },
      ]
    );
  };

  const openCreateModal = () => {
    setEditingTag(null);
    setFormName('');
    setFormColor(TAG_COLORS[0]);
    setFormIcon('pricetag');
    setShowModal(true);
  };

  const openEditModal = (tag: Tag) => {
    setEditingTag(tag);
    setFormName(tag.name);
    setFormColor(tag.color);
    setFormIcon(tag.icon);
    setShowModal(true);
  };

  const handleSave = async () => {
    if (!user?._id) return;
    if (!formName.trim()) {
      Alert.alert('Error', 'Please enter a tag name');
      return;
    }

    try {
      setSaving(true);
      if (editingTag) {
        await tagsAPI.update(user._id, editingTag._id, {
          name: formName,
          color: formColor,
          icon: formIcon,
        });
      } else {
        await tagsAPI.create(user._id, {
          name: formName,
          color: formColor,
          icon: formIcon,
        });
      }
      setShowModal(false);
      loadTags();
    } catch (error: any) {
      console.error('Error saving tag:', error);
      Alert.alert('Error', error.response?.data?.detail || 'Failed to save tag');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = (tag: Tag) => {
    Alert.alert(
      'Delete Tag',
      `Are you sure you want to delete "${tag.name}"? This will remove it from ${tag.contact_count} contacts.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            if (!user?._id) return;
            try {
              await tagsAPI.delete(user._id, tag._id);
              loadTags();
            } catch (error) {
              console.error('Error deleting tag:', error);
              Alert.alert('Error', 'Failed to delete tag');
            }
          },
        },
      ]
    );
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
        <TouchableOpacity style={styles.backButton} onPress={() => router.back()}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Contact Tags</Text>
        <TouchableOpacity style={styles.addButton} onPress={openCreateModal}>
          <Ionicons name="add" size={28} color="#007AFF" />
        </TouchableOpacity>
      </View>

      {/* Info Banner */}
      <View style={styles.infoBanner}>
        <Ionicons name="information-circle" size={20} color="#007AFF" />
        <Text style={styles.infoText}>
          {isInOrg 
            ? 'Tags are shared across your organization. New tags require admin approval.'
            : 'Tags help you organize contacts into groups for easy filtering and campaigns'}
        </Text>
      </View>
      
      {/* Pending Tags Section (Admin Only) */}
      {isAdmin && pendingTags.length > 0 && (
        <View style={styles.pendingSection}>
          <View style={styles.pendingHeader}>
            <Ionicons name="time" size={20} color="#FF9500" />
            <Text style={styles.pendingTitle}>Pending Approval ({pendingTags.length})</Text>
          </View>
          {pendingTags.map((tag) => (
            <View key={tag._id} style={styles.pendingCard}>
              <View style={[styles.tagIcon, { backgroundColor: tag.color + '20' }]}>
                <Ionicons name={tag.icon || 'pricetag'} size={22} color={tag.color} />
              </View>
              <View style={styles.pendingInfo}>
                <Text style={styles.tagName}>{tag.name}</Text>
                <Text style={styles.pendingCreator}>Requested by {tag.creator_name}</Text>
              </View>
              <View style={styles.pendingActions}>
                <TouchableOpacity
                  style={styles.approveButton}
                  onPress={() => handleApprove(tag._id)}
                >
                  <Ionicons name="checkmark" size={20} color="#FFF" />
                </TouchableOpacity>
                <TouchableOpacity
                  style={styles.rejectButton}
                  onPress={() => handleReject(tag)}
                >
                  <Ionicons name="close" size={20} color="#FFF" />
                </TouchableOpacity>
              </View>
            </View>
          ))}
        </View>
      )}

      {/* Tags List */}
      <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
        {tags.map((tag) => (
          <TouchableOpacity
            key={tag._id}
            style={styles.tagCard}
            onPress={() => openEditModal(tag)}
            activeOpacity={0.7}
          >
            <View style={[styles.tagIcon, { backgroundColor: tag.color + '20' }]}>
              <Ionicons name={tag.icon as any} size={22} color={tag.color} />
            </View>
            <View style={styles.tagInfo}>
              <Text style={styles.tagName}>{tag.name}</Text>
              <Text style={styles.tagCount}>
                {tag.contact_count} contact{tag.contact_count !== 1 ? 's' : ''}
              </Text>
            </View>
            <View style={[styles.colorDot, { backgroundColor: tag.color }]} />
            <TouchableOpacity
              style={styles.deleteButton}
              onPress={() => handleDelete(tag)}
            >
              <Ionicons name="trash-outline" size={20} color="#FF3B30" />
            </TouchableOpacity>
          </TouchableOpacity>
        ))}

        {/* Create New Tag Card */}
        <TouchableOpacity style={styles.createCard} onPress={openCreateModal}>
          <Ionicons name="add-circle-outline" size={32} color="#007AFF" />
          <Text style={styles.createText}>Create New Tag</Text>
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
        <View style={styles.modalContainer}>
          <View style={styles.modalHeader}>
            <TouchableOpacity onPress={() => setShowModal(false)}>
              <Text style={styles.cancelButton}>Cancel</Text>
            </TouchableOpacity>
            <Text style={styles.modalTitle}>
              {editingTag ? 'Edit Tag' : 'New Tag'}
            </Text>
            <TouchableOpacity onPress={handleSave} disabled={saving}>
              {saving ? (
                <ActivityIndicator size="small" color="#007AFF" />
              ) : (
                <Text style={styles.saveButton}>Save</Text>
              )}
            </TouchableOpacity>
          </View>

          <ScrollView style={styles.modalContent}>
            {/* Preview */}
            <View style={styles.previewContainer}>
              <View style={[styles.previewTag, { backgroundColor: formColor + '20' }]}>
                <Ionicons name={formIcon as any} size={18} color={formColor} />
                <Text style={[styles.previewText, { color: formColor }]}>
                  {formName || 'Tag Name'}
                </Text>
              </View>
            </View>

            {/* Name Input */}
            <Text style={styles.inputLabel}>Tag Name</Text>
            <TextInput
              style={styles.input}
              value={formName}
              onChangeText={setFormName}
              placeholder="e.g., Premium Customer"
              placeholderTextColor="#8E8E93"
              maxLength={30}
            />

            {/* Color Selector */}
            <Text style={styles.inputLabel}>Color</Text>
            <View style={styles.colorGrid}>
              {TAG_COLORS.map((color) => (
                <TouchableOpacity
                  key={color}
                  style={[
                    styles.colorOption,
                    { backgroundColor: color },
                    formColor === color && styles.colorOptionSelected,
                  ]}
                  onPress={() => setFormColor(color)}
                >
                  {formColor === color && (
                    <Ionicons name="checkmark" size={18} color="#FFF" />
                  )}
                </TouchableOpacity>
              ))}
            </View>

            {/* Icon Selector */}
            <Text style={styles.inputLabel}>Icon</Text>
            <View style={styles.iconGrid}>
              {TAG_ICONS.map((icon) => (
                <TouchableOpacity
                  key={icon.id}
                  style={[
                    styles.iconOption,
                    formIcon === icon.id && styles.iconOptionSelected,
                  ]}
                  onPress={() => setFormIcon(icon.id)}
                >
                  <Ionicons
                    name={icon.id as any}
                    size={24}
                    color={formIcon === icon.id ? '#007AFF' : '#8E8E93'}
                  />
                  <Text
                    style={[
                      styles.iconLabel,
                      formIcon === icon.id && styles.iconLabelSelected,
                    ]}
                  >
                    {icon.name}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          </ScrollView>
        </View>
      </Modal>
    </View>
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
    backgroundColor: '#000',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingTop: Platform.OS === 'ios' ? 60 : 20,
    paddingHorizontal: 16,
    paddingBottom: 16,
    backgroundColor: '#000',
    borderBottomWidth: 1,
    borderBottomColor: '#1C1C1E',
  },
  backButton: {
    width: 40,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  addButton: {
    width: 40,
    alignItems: 'flex-end',
  },
  infoBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    marginHorizontal: 16,
    marginTop: 16,
    padding: 12,
    borderRadius: 10,
    gap: 8,
  },
  infoText: {
    flex: 1,
    fontSize: 13,
    color: '#8E8E93',
  },
  pendingSection: {
    marginHorizontal: 16,
    marginTop: 16,
  },
  pendingHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
  },
  pendingTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FF9500',
  },
  pendingCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: '#FF9500',
    borderStyle: 'dashed',
  },
  pendingInfo: {
    flex: 1,
  },
  pendingCreator: {
    fontSize: 12,
    color: '#FF9500',
    marginTop: 2,
  },
  pendingActions: {
    flexDirection: 'row',
    gap: 8,
  },
  approveButton: {
    width: 36,
    height: 36,
    borderRadius: 8,
    backgroundColor: '#34C759',
    justifyContent: 'center',
    alignItems: 'center',
  },
  rejectButton: {
    width: 36,
    height: 36,
    borderRadius: 8,
    backgroundColor: '#FF3B30',
    justifyContent: 'center',
    alignItems: 'center',
  },
  content: {
    flex: 1,
    paddingHorizontal: 16,
    paddingTop: 16,
  },
  tagCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
  },
  tagIcon: {
    width: 44,
    height: 44,
    borderRadius: 10,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  tagInfo: {
    flex: 1,
  },
  tagName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  tagCount: {
    fontSize: 13,
    color: '#8E8E93',
    marginTop: 2,
  },
  colorDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    marginRight: 12,
  },
  deleteButton: {
    padding: 8,
  },
  createCard: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 24,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: '#2C2C2E',
    borderStyle: 'dashed',
    marginTop: 4,
  },
  createText: {
    fontSize: 15,
    color: '#007AFF',
    marginTop: 8,
    fontWeight: '500',
  },
  modalContainer: {
    flex: 1,
    backgroundColor: '#000',
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingTop: Platform.OS === 'ios' ? 20 : 20,
    paddingHorizontal: 16,
    paddingBottom: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#1C1C1E',
  },
  modalTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  cancelButton: {
    fontSize: 17,
    color: '#007AFF',
  },
  saveButton: {
    fontSize: 17,
    color: '#007AFF',
    fontWeight: '600',
  },
  modalContent: {
    flex: 1,
    padding: 16,
  },
  previewContainer: {
    alignItems: 'center',
    paddingVertical: 24,
    borderBottomWidth: 1,
    borderBottomColor: '#1C1C1E',
    marginBottom: 16,
  },
  previewTag: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 20,
    gap: 8,
  },
  previewText: {
    fontSize: 16,
    fontWeight: '600',
  },
  inputLabel: {
    fontSize: 13,
    color: '#8E8E93',
    marginBottom: 8,
    marginTop: 16,
  },
  input: {
    backgroundColor: '#1C1C1E',
    borderRadius: 10,
    padding: 14,
    fontSize: 16,
    color: '#FFF',
  },
  colorGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  colorOption: {
    width: 44,
    height: 44,
    borderRadius: 22,
    justifyContent: 'center',
    alignItems: 'center',
  },
  colorOptionSelected: {
    borderWidth: 3,
    borderColor: '#FFF',
  },
  iconGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  iconOption: {
    width: 70,
    height: 70,
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 2,
    borderColor: 'transparent',
  },
  iconOptionSelected: {
    borderColor: '#007AFF',
    backgroundColor: '#007AFF20',
  },
  iconLabel: {
    fontSize: 10,
    color: '#8E8E93',
    marginTop: 4,
  },
  iconLabelSelected: {
    color: '#007AFF',
  },
});
