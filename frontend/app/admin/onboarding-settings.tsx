import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  Alert,
  Platform,
  KeyboardAvoidingView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';

// Color palette for branding
const COLOR_OPTIONS = [
  { name: 'Gold', value: '#C9A962' },
  { name: 'Blue', value: '#007AFF' },
  { name: 'Green', value: '#34C759' },
  { name: 'Purple', value: '#AF52DE' },
  { name: 'Red', value: '#FF3B30' },
  { name: 'Orange', value: '#FF9500' },
  { name: 'Pink', value: '#FF2D55' },
  { name: 'Teal', value: '#5AC8FA' },
];

export default function OnboardingSettingsScreen() {
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [settings, setSettings] = useState<any>(null);
  const [placeholders, setPlaceholders] = useState<any[]>([]);
  const [previewText, setPreviewText] = useState('');
  const [showPreview, setShowPreview] = useState(false);
  const [activePreviewField, setActivePreviewField] = useState('');
  const [hasChanges, setHasChanges] = useState(false);
  
  const isSuperAdmin = user?.role === 'super_admin';
  
  useFocusEffect(
    useCallback(() => {
      loadSettings();
      loadPlaceholders();
    }, [])
  );
  
  const loadSettings = async () => {
    try {
      setLoading(true);
      // Super admins load global settings
      const res = await api.get('/onboarding-settings/global');
      setSettings(res.data);
    } catch (error) {
      console.error('Failed to load settings:', error);
      Alert.alert('Error', 'Failed to load onboarding settings');
    } finally {
      setLoading(false);
    }
  };
  
  const loadPlaceholders = async () => {
    try {
      const res = await api.get('/onboarding-settings/placeholders');
      setPlaceholders(res.data.placeholders || []);
    } catch (error) {
      console.error('Failed to load placeholders:', error);
    }
  };
  
  const handleSave = async () => {
    try {
      setSaving(true);
      await api.put('/onboarding-settings/global', settings);
      setHasChanges(false);
      Alert.alert('Success', 'Onboarding settings saved!');
    } catch (error) {
      console.error('Failed to save settings:', error);
      Alert.alert('Error', 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };
  
  const updateMessage = (key: string, value: string) => {
    setSettings((prev: any) => ({
      ...prev,
      messages: {
        ...prev.messages,
        [key]: value,
      },
    }));
    setHasChanges(true);
  };
  
  const updateAppLink = (key: string, value: string) => {
    setSettings((prev: any) => ({
      ...prev,
      app_links: {
        ...prev.app_links,
        [key]: value,
      },
    }));
    setHasChanges(true);
  };
  
  const updateBranding = (key: string, value: string) => {
    setSettings((prev: any) => ({
      ...prev,
      branding: {
        ...prev.branding,
        [key]: value,
      },
    }));
    setHasChanges(true);
  };
  
  const updateToggle = (key: string, value: boolean) => {
    setSettings((prev: any) => ({
      ...prev,
      [key]: value,
    }));
    setHasChanges(true);
  };
  
  const previewMessage = async (field: string) => {
    const template = settings?.messages?.[field] || '';
    if (!template) return;
    
    try {
      const res = await api.post('/onboarding-settings/preview-message', {
        template,
      });
      setPreviewText(res.data.preview);
      setActivePreviewField(field);
      setShowPreview(true);
    } catch (error) {
      console.error('Failed to preview message:', error);
    }
  };
  
  const insertPlaceholder = (placeholder: string, field: string) => {
    const currentValue = settings?.messages?.[field] || '';
    updateMessage(field, currentValue + placeholder);
  };
  
  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#C9A962" />
        </View>
      </SafeAreaView>
    );
  }
  
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Onboarding Settings</Text>
        <TouchableOpacity
          style={[styles.saveButton, !hasChanges && styles.saveButtonDisabled]}
          onPress={handleSave}
          disabled={!hasChanges || saving}
        >
          {saving ? (
            <ActivityIndicator size="small" color="#FFF" />
          ) : (
            <Text style={[styles.saveButtonText, !hasChanges && styles.saveButtonTextDisabled]}>
              {hasChanges ? 'Save' : 'Saved'}
            </Text>
          )}
        </TouchableOpacity>
      </View>
      
      <KeyboardAvoidingView 
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={{ flex: 1 }}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 0 : 20}
      >
        <ScrollView 
          contentContainerStyle={[styles.content, { paddingBottom: 150 }]} 
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
        {/* Inherited Status */}
        {settings?.inherited_from && settings.inherited_from !== 'defaults' && (
          <View style={styles.inheritedBanner}>
            <Ionicons name="information-circle" size={18} color="#007AFF" />
            <Text style={styles.inheritedText}>
              Inherited from {settings.inherited_from}
            </Text>
          </View>
        )}
        
        {/* SMS MESSAGES Section */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons name="chatbubble-ellipses" size={22} color="#C9A962" />
            <Text style={styles.sectionTitle}>SMS Messages</Text>
          </View>
          <Text style={styles.sectionDescription}>
            Customize the automated messages sent during onboarding
          </Text>
          
          {/* Welcome SMS */}
          <View style={styles.inputGroup}>
            <View style={styles.inputLabelRow}>
              <Text style={styles.inputLabel}>Welcome SMS</Text>
              <TouchableOpacity onPress={() => previewMessage('welcome_sms')}>
                <Ionicons name="eye-outline" size={20} color="#8E8E93" />
              </TouchableOpacity>
            </View>
            <TextInput
              style={styles.textArea}
              multiline
              numberOfLines={3}
              value={settings?.messages?.welcome_sms || ''}
              onChangeText={(text) => updateMessage('welcome_sms', text)}
              placeholder="Welcome message sent to new admins..."
              placeholderTextColor="#6E6E73"
            />
            <Text style={styles.charCount}>
              {settings?.messages?.welcome_sms?.length || 0}/160 chars
            </Text>
          </View>
          
          {/* Training Complete SMS */}
          <View style={styles.inputGroup}>
            <View style={styles.inputLabelRow}>
              <Text style={styles.inputLabel}>Training Complete SMS</Text>
              <TouchableOpacity onPress={() => previewMessage('training_complete_sms')}>
                <Ionicons name="eye-outline" size={20} color="#8E8E93" />
              </TouchableOpacity>
            </View>
            <TextInput
              style={styles.textArea}
              multiline
              numberOfLines={3}
              value={settings?.messages?.training_complete_sms || ''}
              onChangeText={(text) => updateMessage('training_complete_sms', text)}
              placeholder="Message sent when training is completed..."
              placeholderTextColor="#6E6E73"
            />
          </View>
          
          {/* Team Invite SMS */}
          <View style={styles.inputGroup}>
            <View style={styles.inputLabelRow}>
              <Text style={styles.inputLabel}>Team Invite SMS</Text>
              <TouchableOpacity onPress={() => previewMessage('team_invite_sms')}>
                <Ionicons name="eye-outline" size={20} color="#8E8E93" />
              </TouchableOpacity>
            </View>
            <TextInput
              style={styles.textArea}
              multiline
              numberOfLines={3}
              value={settings?.messages?.team_invite_sms || ''}
              onChangeText={(text) => updateMessage('team_invite_sms', text)}
              placeholder="Message sent when inviting team members..."
              placeholderTextColor="#6E6E73"
            />
          </View>
          
          {/* Team Welcome SMS */}
          <View style={styles.inputGroup}>
            <View style={styles.inputLabelRow}>
              <Text style={styles.inputLabel}>Team Member Welcome SMS</Text>
              <TouchableOpacity onPress={() => previewMessage('team_welcome_sms')}>
                <Ionicons name="eye-outline" size={20} color="#8E8E93" />
              </TouchableOpacity>
            </View>
            <TextInput
              style={styles.textArea}
              multiline
              numberOfLines={3}
              value={settings?.messages?.team_welcome_sms || ''}
              onChangeText={(text) => updateMessage('team_welcome_sms', text)}
              placeholder="Welcome message for team members..."
              placeholderTextColor="#6E6E73"
            />
          </View>
          
          {/* Placeholders Reference */}
          <View style={styles.placeholdersBox}>
            <Text style={styles.placeholdersTitle}>Available Placeholders</Text>
            <View style={styles.placeholdersList}>
              {placeholders.map((p, i) => (
                <View key={i} style={styles.placeholderItem}>
                  <Text style={styles.placeholderKey}>{p.key}</Text>
                  <Text style={styles.placeholderDesc}>{p.description}</Text>
                </View>
              ))}
            </View>
          </View>
        </View>
        
        {/* APP LINKS Section */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons name="link" size={22} color="#007AFF" />
            <Text style={styles.sectionTitle}>App Links</Text>
          </View>
          <Text style={styles.sectionDescription}>
            Links for app downloads and web access
          </Text>
          
          <View style={styles.inputGroup}>
            <Text style={styles.inputLabel}>App Store URL</Text>
            <TextInput
              style={styles.textInput}
              value={settings?.app_links?.app_store_url || ''}
              onChangeText={(text) => updateAppLink('app_store_url', text)}
              placeholder="https://apps.apple.com/app/..."
              placeholderTextColor="#6E6E73"
              autoCapitalize="none"
              keyboardType="url"
            />
          </View>
          
          <View style={styles.inputGroup}>
            <Text style={styles.inputLabel}>Google Play URL</Text>
            <TextInput
              style={styles.textInput}
              value={settings?.app_links?.google_play_url || ''}
              onChangeText={(text) => updateAppLink('google_play_url', text)}
              placeholder="https://play.google.com/store/apps/..."
              placeholderTextColor="#6E6E73"
              autoCapitalize="none"
              keyboardType="url"
            />
          </View>
          
          <View style={styles.inputGroup}>
            <Text style={styles.inputLabel}>Web App URL</Text>
            <TextInput
              style={styles.textInput}
              value={settings?.app_links?.web_app_url || ''}
              onChangeText={(text) => updateAppLink('web_app_url', text)}
              placeholder="https://app.yourdomain.com"
              placeholderTextColor="#6E6E73"
              autoCapitalize="none"
              keyboardType="url"
            />
          </View>
        </View>
        
        {/* BRANDING Section */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons name="color-palette" size={22} color="#AF52DE" />
            <Text style={styles.sectionTitle}>Branding</Text>
          </View>
          <Text style={styles.sectionDescription}>
            Customize colors used in onboarding screens
          </Text>
          
          <View style={styles.inputGroup}>
            <Text style={styles.inputLabel}>Company Name</Text>
            <TextInput
              style={styles.textInput}
              value={settings?.branding?.company_name || ''}
              onChangeText={(text) => updateBranding('company_name', text)}
              placeholder="Your Company Name"
              placeholderTextColor="#6E6E73"
            />
          </View>
          
          <View style={styles.inputGroup}>
            <Text style={styles.inputLabel}>Primary Color</Text>
            <View style={styles.colorPicker}>
              {COLOR_OPTIONS.map((color) => (
                <TouchableOpacity
                  key={color.value}
                  style={[
                    styles.colorOption,
                    { backgroundColor: color.value },
                    settings?.branding?.primary_color === color.value && styles.colorOptionSelected,
                  ]}
                  onPress={() => updateBranding('primary_color', color.value)}
                >
                  {settings?.branding?.primary_color === color.value && (
                    <Ionicons name="checkmark" size={16} color="#FFF" />
                  )}
                </TouchableOpacity>
              ))}
            </View>
          </View>
          
          <View style={styles.inputGroup}>
            <Text style={styles.inputLabel}>Accent Color</Text>
            <View style={styles.colorPicker}>
              {COLOR_OPTIONS.map((color) => (
                <TouchableOpacity
                  key={color.value}
                  style={[
                    styles.colorOption,
                    { backgroundColor: color.value },
                    settings?.branding?.accent_color === color.value && styles.colorOptionSelected,
                  ]}
                  onPress={() => updateBranding('accent_color', color.value)}
                >
                  {settings?.branding?.accent_color === color.value && (
                    <Ionicons name="checkmark" size={16} color="#FFF" />
                  )}
                </TouchableOpacity>
              ))}
            </View>
          </View>
          
          <View style={styles.inputGroup}>
            <Text style={styles.inputLabel}>Logo URL</Text>
            <TextInput
              style={styles.textInput}
              value={settings?.branding?.logo_url || ''}
              onChangeText={(text) => updateBranding('logo_url', text)}
              placeholder="https://example.com/logo.png"
              placeholderTextColor="#6E6E73"
              autoCapitalize="none"
              keyboardType="url"
            />
          </View>
        </View>
        
        {/* AUTOMATION Section */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons name="flash" size={22} color="#FF9500" />
            <Text style={styles.sectionTitle}>Automation</Text>
          </View>
          <Text style={styles.sectionDescription}>
            Control automatic behaviors during onboarding
          </Text>
          
          <TouchableOpacity
            style={styles.toggleRow}
            onPress={() => updateToggle('training_required', !settings?.training_required)}
          >
            <View style={styles.toggleInfo}>
              <Text style={styles.toggleLabel}>Training Required</Text>
              <Text style={styles.toggleDescription}>
                New users must complete training before full access
              </Text>
            </View>
            <View style={[
              styles.toggle,
              settings?.training_required && styles.toggleActive
            ]}>
              <View style={[
                styles.toggleThumb,
                settings?.training_required && styles.toggleThumbActive
              ]} />
            </View>
          </TouchableOpacity>
          
          <TouchableOpacity
            style={styles.toggleRow}
            onPress={() => updateToggle('auto_send_welcome_sms', !settings?.auto_send_welcome_sms)}
          >
            <View style={styles.toggleInfo}>
              <Text style={styles.toggleLabel}>Auto-Send Welcome SMS</Text>
              <Text style={styles.toggleDescription}>
                Automatically send welcome message when account is created
              </Text>
            </View>
            <View style={[
              styles.toggle,
              settings?.auto_send_welcome_sms && styles.toggleActive
            ]}>
              <View style={[
                styles.toggleThumb,
                settings?.auto_send_welcome_sms && styles.toggleThumbActive
              ]} />
            </View>
          </TouchableOpacity>
          
          <TouchableOpacity
            style={styles.toggleRow}
            onPress={() => updateToggle('auto_send_team_invite', !settings?.auto_send_team_invite)}
          >
            <View style={styles.toggleInfo}>
              <Text style={styles.toggleLabel}>Auto-Send Team Invite</Text>
              <Text style={styles.toggleDescription}>
                Prompt user to invite team after completing training
              </Text>
            </View>
            <View style={[
              styles.toggle,
              settings?.auto_send_team_invite && styles.toggleActive
            ]}>
              <View style={[
                styles.toggleThumb,
                settings?.auto_send_team_invite && styles.toggleThumbActive
              ]} />
            </View>
          </TouchableOpacity>
        </View>
        
        <View style={{ height: 40 }} />
        </ScrollView>
      </KeyboardAvoidingView>
      
      {/* Preview Modal */}
      {showPreview && (
        <View style={styles.previewOverlay}>
          <View style={styles.previewModal}>
            <View style={styles.previewHeader}>
              <Text style={styles.previewTitle}>Message Preview</Text>
              <TouchableOpacity onPress={() => setShowPreview(false)}>
                <Ionicons name="close-circle" size={28} color="#8E8E93" />
              </TouchableOpacity>
            </View>
            <View style={styles.previewPhone}>
              <View style={styles.previewBubble}>
                <Text style={styles.previewText}>{previewText}</Text>
              </View>
            </View>
            <Text style={styles.previewNote}>
              This is how the message will appear to recipients
            </Text>
          </View>
        </View>
      )}
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
    borderBottomColor: '#1C1C1E',
  },
  backButton: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  saveButton: {
    backgroundColor: '#34C759',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 16,
    minWidth: 70,
    alignItems: 'center',
  },
  saveButtonDisabled: {
    backgroundColor: '#2C2C2E',
  },
  saveButtonText: {
    color: '#FFF',
    fontSize: 15,
    fontWeight: '600',
  },
  saveButtonTextDisabled: {
    color: '#8E8E93',
  },
  content: {
    padding: 16,
  },
  inheritedBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(0,122,255,0.1)',
    padding: 12,
    borderRadius: 10,
    marginBottom: 16,
    gap: 8,
  },
  inheritedText: {
    color: '#007AFF',
    fontSize: 14,
  },
  section: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 6,
  },
  sectionTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  sectionDescription: {
    fontSize: 13,
    color: '#8E8E93',
    marginBottom: 16,
  },
  inputGroup: {
    marginBottom: 16,
  },
  inputLabelRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  inputLabel: {
    fontSize: 14,
    fontWeight: '500',
    color: '#FFF',
    marginBottom: 8,
  },
  textInput: {
    backgroundColor: '#2C2C2E',
    borderRadius: 10,
    padding: 14,
    fontSize: 15,
    color: '#FFF',
    borderWidth: 1,
    borderColor: '#3C3C3E',
  },
  textArea: {
    backgroundColor: '#2C2C2E',
    borderRadius: 10,
    padding: 14,
    fontSize: 15,
    color: '#FFF',
    borderWidth: 1,
    borderColor: '#3C3C3E',
    minHeight: 80,
    textAlignVertical: 'top',
  },
  charCount: {
    fontSize: 12,
    color: '#8E8E93',
    textAlign: 'right',
    marginTop: 4,
  },
  placeholdersBox: {
    backgroundColor: 'rgba(201,169,98,0.1)',
    borderRadius: 10,
    padding: 12,
    marginTop: 8,
  },
  placeholdersTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: '#C9A962',
    marginBottom: 8,
  },
  placeholdersList: {
    gap: 6,
  },
  placeholderItem: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
  },
  placeholderKey: {
    fontSize: 12,
    fontWeight: '600',
    color: '#FFF',
    backgroundColor: '#3C3C3E',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  placeholderDesc: {
    fontSize: 12,
    color: '#8E8E93',
    flex: 1,
  },
  colorPicker: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  colorOption: {
    width: 40,
    height: 40,
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
  },
  colorOptionSelected: {
    borderWidth: 3,
    borderColor: '#FFF',
  },
  toggleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  toggleInfo: {
    flex: 1,
    marginRight: 16,
  },
  toggleLabel: {
    fontSize: 15,
    fontWeight: '500',
    color: '#FFF',
    marginBottom: 4,
  },
  toggleDescription: {
    fontSize: 13,
    color: '#8E8E93',
  },
  toggle: {
    width: 51,
    height: 31,
    borderRadius: 16,
    backgroundColor: '#3C3C3E',
    justifyContent: 'center',
    padding: 2,
  },
  toggleActive: {
    backgroundColor: '#34C759',
  },
  toggleThumb: {
    width: 27,
    height: 27,
    borderRadius: 14,
    backgroundColor: '#FFF',
  },
  toggleThumbActive: {
    alignSelf: 'flex-end',
  },
  previewOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0,0,0,0.8)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  previewModal: {
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    padding: 20,
    width: '100%',
    maxWidth: 360,
  },
  previewHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  previewTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  previewPhone: {
    backgroundColor: '#2C2C2E',
    borderRadius: 20,
    padding: 16,
    marginBottom: 12,
  },
  previewBubble: {
    backgroundColor: '#34C759',
    borderRadius: 16,
    borderBottomRightRadius: 4,
    padding: 12,
    maxWidth: '90%',
    alignSelf: 'flex-end',
  },
  previewText: {
    color: '#FFF',
    fontSize: 15,
    lineHeight: 21,
  },
  previewNote: {
    fontSize: 12,
    color: '#8E8E93',
    textAlign: 'center',
  },
});
