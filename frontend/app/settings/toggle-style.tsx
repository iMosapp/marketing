import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { useAuthStore } from '../../store/authStore';
import { emailAPI } from '../../services/api';
import MessageModeToggle, { ToggleStyle, MessageMode } from '../../components/MessageModeToggle';

import { useThemeStore } from '../../store/themeStore';
const TOGGLE_STYLES: { id: ToggleStyle; name: string; description: string }[] = [
  { 
    id: 'pill', 
    name: 'Pill Toggle', 
    description: 'Compact pill-shaped toggle in the header' 
  },
  { 
    id: 'fab', 
    name: 'Floating Button', 
    description: 'Floating action button that changes icon' 
  },
  { 
    id: 'tabs', 
    name: 'Tab Style', 
    description: 'Tab-style switcher with underline indicator' 
  },
  { 
    id: 'segmented', 
    name: 'Segmented Control', 
    description: 'iOS-style segmented control' 
  },
];

export default function ToggleStyleSettings() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { user } = useAuthStore();
  const [selectedStyle, setSelectedStyle] = useState<ToggleStyle>('pill');
  const [defaultMode, setDefaultMode] = useState<MessageMode>('sms');
  const [previewMode, setPreviewMode] = useState<MessageMode>('sms');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadPreferences();
  }, [user?._id]);

  const loadPreferences = async () => {
    if (!user?._id) {
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const prefs = await emailAPI.getPreferences(user._id);
      setSelectedStyle(prefs.toggle_style || 'pill');
      setDefaultMode(prefs.default_mode || 'sms');
    } catch (error) {
      console.error('Error loading preferences:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectStyle = async (style: ToggleStyle) => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setSelectedStyle(style);
    await savePreferences(style, defaultMode);
  };

  const handleSetDefaultMode = async (mode: MessageMode) => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setDefaultMode(mode);
    await savePreferences(selectedStyle, mode);
  };

  const savePreferences = async (style: ToggleStyle, mode: MessageMode) => {
    if (!user?._id) return;
    try {
      setSaving(true);
      await emailAPI.updatePreferences(user._id, {
        toggle_style: style,
        default_mode: mode,
      });
    } catch (error) {
      console.error('Error saving preferences:', error);
    } finally {
      setSaving(false);
    }
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
        <Text style={styles.headerTitle}>Message Mode Toggle</Text>
        <View style={styles.headerRight}>
          {saving && <ActivityIndicator size="small" color="#007AFF" />}
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        {/* Preview Section */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Preview</Text>
          <View style={[
            styles.previewContainer,
            previewMode === 'email' && styles.previewContainerEmail
          ]}>
            <Text style={[
              styles.previewLabel,
              previewMode === 'email' && styles.previewLabelEmail
            ]}>
              {previewMode === 'sms' ? 'SMS Mode (Dark)' : 'Email Mode (Light)'}
            </Text>
            <View style={styles.previewToggle}>
              <MessageModeToggle
                mode={previewMode}
                onModeChange={setPreviewMode}
                style={selectedStyle}
              />
            </View>
            <Text style={[
              styles.previewHint,
              previewMode === 'email' && styles.previewHintEmail
            ]}>
              Tap the toggle to preview mode switching
            </Text>
          </View>
        </View>

        {/* Toggle Style Selection */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Choose Toggle Style</Text>
          <Text style={styles.sectionSubtitle}>
            Select how you want to switch between SMS and Email modes in your inbox
          </Text>

          {TOGGLE_STYLES.map((style) => (
            <TouchableOpacity
              key={style.id}
              style={[
                styles.styleOption,
                selectedStyle === style.id && styles.styleOptionSelected,
              ]}
              onPress={() => handleSelectStyle(style.id)}
              activeOpacity={0.7}
            >
              <View style={styles.styleOptionContent}>
                <View style={styles.styleOptionHeader}>
                  <Text style={styles.styleOptionName}>{style.name}</Text>
                  {selectedStyle === style.id && (
                    <Ionicons name="checkmark-circle" size={24} color="#007AFF" />
                  )}
                </View>
                <Text style={styles.styleOptionDescription}>{style.description}</Text>
                
                {/* Mini preview of the toggle style */}
                <View style={styles.miniPreview}>
                  <MessageModeToggle
                    mode="sms"
                    onModeChange={() => {}}
                    style={style.id}
                  />
                </View>
              </View>
            </TouchableOpacity>
          ))}
        </View>

        {/* Default Mode Selection */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Default Mode</Text>
          <Text style={styles.sectionSubtitle}>
            Choose which mode to start with when you open the inbox
          </Text>

          <View style={styles.defaultModeOptions}>
            <TouchableOpacity
              style={[
                styles.defaultModeOption,
                defaultMode === 'sms' && styles.defaultModeOptionSelected,
              ]}
              onPress={() => handleSetDefaultMode('sms')}
              activeOpacity={0.7}
            >
              <Ionicons 
                name="paper-plane" 
                size={24} 
                color={defaultMode === 'sms' ? '#007AFF' : colors.textSecondary} 
              />
              <Text style={[
                styles.defaultModeText,
                defaultMode === 'sms' && styles.defaultModeTextSelected,
              ]}>
                SMS (Dark Mode)
              </Text>
              {defaultMode === 'sms' && (
                <Ionicons name="checkmark-circle" size={20} color="#007AFF" />
              )}
            </TouchableOpacity>

            <TouchableOpacity
              style={[
                styles.defaultModeOption,
                defaultMode === 'email' && styles.defaultModeOptionSelected,
              ]}
              onPress={() => handleSetDefaultMode('email')}
              activeOpacity={0.7}
            >
              <Ionicons 
                name="mail" 
                size={24} 
                color={defaultMode === 'email' ? '#007AFF' : colors.textSecondary} 
              />
              <Text style={[
                styles.defaultModeText,
                defaultMode === 'email' && styles.defaultModeTextSelected,
              ]}>
                Email (Light Mode)
              </Text>
              {defaultMode === 'email' && (
                <Ionicons name="checkmark-circle" size={20} color="#007AFF" />
              )}
            </TouchableOpacity>
          </View>
        </View>

        {/* Info Section */}
        <View style={styles.infoSection}>
          <Ionicons name="information-circle" size={20} color={colors.textSecondary} />
          <Text style={styles.infoText}>
            When in Email mode, the inbox switches to light mode so you can easily tell 
            which mode you're in. SMS sends text messages, Email sends branded HTML emails.
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
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
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.surface,
  },
  backButton: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: colors.text,
  },
  headerRight: {
    width: 40,
    alignItems: 'flex-end',
  },
  content: {
    padding: 16,
    paddingBottom: 40,
  },
  section: {
    marginBottom: 32,
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 8,
  },
  sectionSubtitle: {
    fontSize: 14,
    color: colors.textSecondary,
    marginBottom: 16,
    lineHeight: 20,
  },
  
  // Preview Section
  previewContainer: {
    backgroundColor: colors.card,
    borderRadius: 16,
    padding: 24,
    alignItems: 'center',
  },
  previewContainerEmail: {
    backgroundColor: colors.bg,
  },
  previewLabel: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 20,
  },
  previewLabelEmail: {
    color: colors.text,
  },
  previewToggle: {
    marginBottom: 16,
  },
  previewHint: {
    fontSize: 13,
    color: colors.textSecondary,
  },
  previewHintEmail: {
    color: '#6E6E73',
  },

  // Style Options
  styleOption: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderWidth: 2,
    borderColor: 'transparent',
  },
  styleOptionSelected: {
    borderColor: '#007AFF',
    backgroundColor: '#007AFF10',
  },
  styleOptionContent: {},
  styleOptionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  styleOptionName: {
    fontSize: 17,
    fontWeight: '600',
    color: colors.text,
  },
  styleOptionDescription: {
    fontSize: 14,
    color: colors.textSecondary,
    marginBottom: 16,
  },
  miniPreview: {
    alignItems: 'flex-start',
  },

  // Default Mode Options
  defaultModeOptions: {
    gap: 12,
  },
  defaultModeOption: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    gap: 12,
    borderWidth: 2,
    borderColor: 'transparent',
  },
  defaultModeOptionSelected: {
    borderColor: '#007AFF',
    backgroundColor: '#007AFF10',
  },
  defaultModeText: {
    flex: 1,
    fontSize: 16,
    color: colors.text,
  },
  defaultModeTextSelected: {
    fontWeight: '600',
  },

  // Info Section
  infoSection: {
    flexDirection: 'row',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    gap: 12,
    alignItems: 'flex-start',
  },
  infoText: {
    flex: 1,
    fontSize: 14,
    color: colors.textSecondary,
    lineHeight: 20,
  },
});
