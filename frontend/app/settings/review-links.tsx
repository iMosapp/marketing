import React, {
  useState, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Alert,
  Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';
import { useToast } from '../../components/common/Toast';
import { showAlert } from '../../services/alert';

import { useThemeStore } from '../../store/themeStore';
interface ReviewLinks {
  google: string | null;
  yelp: string | null;
  facebook: string | null;
  dealerrater: string | null;
  cars_com: string | null;
  custom: { name: string; url: string }[];
}

const REVIEW_PLATFORMS = [
  { key: 'google', name: 'Google Reviews', icon: 'logo-google', color: '#4285F4' },
  { key: 'yelp', name: 'Yelp', icon: 'star', color: '#FF1A1A' },
  { key: 'facebook', name: 'Facebook', icon: 'logo-facebook', color: '#1877F2' },
  { key: 'dealerrater', name: 'DealerRater', icon: 'car', color: '#00A0D2' },
  { key: 'cars_com', name: 'Cars.com', icon: 'car-sport', color: '#5C2D91' },
];

export default function ReviewLinksScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { user } = useAuthStore();
const { showToast } = useToast();
    const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [links, setLinks] = useState<ReviewLinks>({
    google: null,
    yelp: null,
    facebook: null,
    dealerrater: null,
    cars_com: null,
    custom: [],
  });
  const [newCustomName, setNewCustomName] = useState('');
  const [newCustomUrl, setNewCustomUrl] = useState('');
  const [isStoreAdmin, setIsStoreAdmin] = useState(false);

  useEffect(() => {
    loadReviewLinks();
  }, []);

  const loadReviewLinks = async () => {
    if (!user) return;
    try {
      // Check if user is store admin or higher
      const canEdit = ['super_admin', 'org_admin', 'store_manager'].includes(user.role || '');
      setIsStoreAdmin(canEdit);

      // Get store review links
      const response = await api.get(`/admin/users/${user._id}/store-review-links`);
      setLinks(response.data);
    } catch (error) {
      console.error('Error loading review links:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!user?.store_id) {
      showAlert('Error', 'No store associated with your account');
      return;
    }

    setSaving(true);
    try {
      await api.put(`/admin/stores/${user.store_id}/review-links`, links);
      showToast('Review links updated successfully');
    } catch (error) {
      showAlert('Error', 'Failed to save review links');
    } finally {
      setSaving(false);
    }
  };

  const updateLink = (key: string, value: string) => {
    setLinks(prev => ({ ...prev, [key]: value || null }));
  };

  const addCustomLink = () => {
    if (!newCustomName.trim() || !newCustomUrl.trim()) {
      showAlert('Error', 'Please enter both name and URL');
      return;
    }
    setLinks(prev => ({
      ...prev,
      custom: [...prev.custom, { name: newCustomName.trim(), url: newCustomUrl.trim() }],
    }));
    setNewCustomName('');
    setNewCustomUrl('');
  };

  const removeCustomLink = (index: number) => {
    setLinks(prev => ({
      ...prev,
      custom: prev.custom.filter((_, i) => i !== index),
    }));
  };

  const openLink = (url: string | null) => {
    if (url) {
      Linking.openURL(url);
    }
  };

  const copyLink = (url: string | null) => {
    if (url) {
      // In a real app, use Clipboard API
      showAlert('Link Copied!', url);
    }
  };

  if (loading) {
    return (
      <View style={styles.container}>
        <Text style={styles.loadingText}>Loading...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={{ flex: 1 }}>
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity style={styles.backButton} onPress={() => router.back()}>
            <Ionicons name="chevron-back" size={24} color="#007AFF" />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Account Review Links</Text>
          {isStoreAdmin && (
            <TouchableOpacity style={styles.saveButton} onPress={handleSave} disabled={saving}>
              <Text style={styles.saveButtonText}>{saving ? 'Saving...' : 'Save'}</Text>
            </TouchableOpacity>
          )}
        </View>

        <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
          {/* Info Banner */}
          <View style={styles.infoBanner}>
            <Ionicons name="information-circle" size={20} color="#007AFF" />
            <Text style={styles.infoText}>
              {isStoreAdmin 
                ? 'These review links are shared with all users at your store. Edit the URLs below.'
                : 'These are your store\'s review links. Contact your manager to update them.'}
            </Text>
          </View>

          {/* Standard Platforms */}
          <Text style={styles.sectionTitle}>REVIEW PLATFORMS</Text>
          
          {REVIEW_PLATFORMS.map((platform) => (
            <View key={platform.key} style={styles.linkCard}>
              <View style={[styles.platformIcon, { backgroundColor: platform.color + '20' }]}>
                <Ionicons name={platform.icon as any} size={24} color={platform.color} />
              </View>
              <View style={styles.linkContent}>
                <Text style={styles.platformName}>{platform.name}</Text>
                {isStoreAdmin ? (
                  <TextInput
                    style={styles.linkInput}
                    value={links[platform.key as keyof ReviewLinks] as string || ''}
                    onChangeText={(text) => updateLink(platform.key, text)}
                    placeholder="Paste review link here..."
                    placeholderTextColor={colors.textSecondary}
                    autoCapitalize="none"
                    autoCorrect={false}
                  />
                ) : (
                  <Text style={styles.linkUrl} numberOfLines={1}>
                    {links[platform.key as keyof ReviewLinks] || 'Not set'}
                  </Text>
                )}
              </View>
              {links[platform.key as keyof ReviewLinks] && (
                <View style={styles.linkActions}>
                  <TouchableOpacity 
                    style={styles.actionButton}
                    onPress={() => openLink(links[platform.key as keyof ReviewLinks] as string)}
                  >
                    <Ionicons name="open-outline" size={20} color="#007AFF" />
                  </TouchableOpacity>
                  <TouchableOpacity 
                    style={styles.actionButton}
                    onPress={() => copyLink(links[platform.key as keyof ReviewLinks] as string)}
                  >
                    <Ionicons name="copy-outline" size={20} color="#007AFF" />
                  </TouchableOpacity>
                </View>
              )}
            </View>
          ))}

          {/* Custom Links */}
          <Text style={[styles.sectionTitle, { marginTop: 24 }]}>CUSTOM REVIEW SITES</Text>
          
          {links.custom.map((custom, index) => (
            <View key={index} style={styles.linkCard}>
              <View style={[styles.platformIcon, { backgroundColor: '#FF9500' + '20' }]}>
                <Ionicons name="link" size={24} color="#FF9500" />
              </View>
              <View style={styles.linkContent}>
                <Text style={styles.platformName}>{custom.name}</Text>
                <Text style={styles.linkUrl} numberOfLines={1}>{custom.url}</Text>
              </View>
              <View style={styles.linkActions}>
                <TouchableOpacity 
                  style={styles.actionButton}
                  onPress={() => openLink(custom.url)}
                >
                  <Ionicons name="open-outline" size={20} color="#007AFF" />
                </TouchableOpacity>
                {isStoreAdmin && (
                  <TouchableOpacity 
                    style={styles.actionButton}
                    onPress={() => removeCustomLink(index)}
                  >
                    <Ionicons name="trash-outline" size={20} color="#FF3B30" />
                  </TouchableOpacity>
                )}
              </View>
            </View>
          ))}

          {/* Add Custom Link (Admin Only) */}
          {isStoreAdmin && (
            <View style={styles.addCustomSection}>
              <Text style={styles.addCustomLabel}>Add Custom Review Site</Text>
              <TextInput
                style={styles.addInput}
                value={newCustomName}
                onChangeText={setNewCustomName}
                placeholder="Site name (e.g., Edmunds)"
                placeholderTextColor={colors.textSecondary}
              />
              <TextInput
                style={styles.addInput}
                value={newCustomUrl}
                onChangeText={setNewCustomUrl}
                placeholder="Review page URL"
                placeholderTextColor={colors.textSecondary}
                autoCapitalize="none"
                autoCorrect={false}
              />
              <TouchableOpacity style={styles.addButton} onPress={addCustomLink}>
                <Ionicons name="add" size={20} color={colors.text} />
                <Text style={styles.addButtonText}>Add Review Site</Text>
              </TouchableOpacity>
            </View>
          )}

          <View style={{ height: 40 }} />
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  loadingText: {
    color: colors.text,
    textAlign: 'center',
    marginTop: 100,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingTop: 28,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.card,
  },
  backButton: {
    width: 60,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  saveButton: {
    width: 60,
    alignItems: 'flex-end',
  },
  saveButtonText: {
    fontSize: 18,
    color: '#007AFF',
    fontWeight: '600',
  },
  content: {
    flex: 1,
    padding: 16,
  },
  infoBanner: {
    flexDirection: 'row',
    backgroundColor: '#007AFF15',
    borderRadius: 12,
    padding: 16,
    marginBottom: 24,
    gap: 12,
  },
  infoText: {
    flex: 1,
    fontSize: 16,
    color: colors.textSecondary,
    lineHeight: 20,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 12,
    letterSpacing: 0.5,
  },
  linkCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginBottom: 8,
    gap: 12,
  },
  platformIcon: {
    width: 48,
    height: 48,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  linkContent: {
    flex: 1,
  },
  platformName: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 4,
  },
  linkInput: {
    fontSize: 16,
    color: colors.text,
    backgroundColor: colors.surface,
    borderRadius: 8,
    padding: 10,
    marginTop: 4,
  },
  linkUrl: {
    fontSize: 15,
    color: colors.textSecondary,
  },
  linkActions: {
    flexDirection: 'row',
    gap: 8,
  },
  actionButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  addCustomSection: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginTop: 8,
  },
  addCustomLabel: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 12,
  },
  addInput: {
    backgroundColor: colors.surface,
    borderRadius: 10,
    padding: 14,
    fontSize: 17,
    color: colors.text,
    marginBottom: 12,
  },
  addButton: {
    flexDirection: 'row',
    backgroundColor: '#007AFF',
    borderRadius: 10,
    padding: 14,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  addButtonText: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
});
