import React, {
  useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  TextInput,
  ActivityIndicator,
  Alert,
  Image,
  KeyboardAvoidingView,
  Platform,
  Keyboard,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';
import { useToast } from '../../components/common/Toast';

// Pre-built themes - just tap to select!
const THEMES = [
  { id: 'gold', name: 'Luxury Gold', bg: '#1A1A1A', accent: '#C9A962', text: '#FFFFFF' },
  { id: 'blue', name: 'Classic Blue', bg: '#0A1628', accent: '#3B82F6', text: '#FFFFFF' },
  { id: 'green', name: 'Fresh Green', bg: '#0F1F1A', accent: '#10B981', text: '#FFFFFF' },
  { id: 'purple', name: 'Royal Purple', bg: '#1A0F28', accent: '#8B5CF6', text: '#FFFFFF' },
  { id: 'red', name: 'Bold Red', bg: '#1F0A0A', accent: '#EF4444', text: '#FFFFFF' },
  { id: 'light', name: 'Clean Light', bg: '#F8FAFC', accent: '#0F172A', text: '#1E293B' },
];

// Pre-built headlines - just tap to select!
const HEADLINES = [
  'Thank You!',
  'Congratulations!',
  'Welcome to the Family!',
  'We Appreciate You!',
  'You Made Our Day!',
];

export default function CongratsTemplateScreen() {
  const router = useRouter();
  const { user } = useAuthStore();
const { showToast } = useToast();
    const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  
  // Template settings
  const [selectedTheme, setSelectedTheme] = useState(THEMES[0]);
  const [headline, setHeadline] = useState('Thank You!');
  const [message, setMessage] = useState('Thank you for choosing us, {customer_name}! We truly appreciate your business.');
  
  useEffect(() => {
    loadTemplate();
  }, []);

  const loadTemplate = async () => {
    try {
      const storeId = user?.store_id || 'default';
      const response = await api.get(`/congrats/template/${storeId}`);
      if (response.data.exists) {
        const t = response.data.template;
        setHeadline(t.headline || 'Thank You!');
        setMessage(t.message || 'Thank you for choosing us, {customer_name}!');
        // Find matching theme or use first one
        const matchingTheme = THEMES.find(
          th => th.bg === t.background_color && th.accent === t.accent_color
        ) || THEMES[0];
        setSelectedTheme(matchingTheme);
      }
    } catch (error) {
      console.error('Error loading template:', error);
    } finally {
      setLoading(false);
    }
  };

  const saveTemplate = async () => {
    setSaving(true);
    try {
      const storeId = user?.store_id || 'default';
      await api.post(`/congrats/template/${storeId}`, {
        headline,
        message,
        background_color: selectedTheme.bg,
        accent_color: selectedTheme.accent,
        text_color: selectedTheme.text,
      });
      showToast('Your congrats card template has been updated.');
    } catch (error) {
      Alert.alert('Error', 'Failed to save template');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#C9A962" />
      </View>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={24} color="#FFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Congrats Card Style</Text>
        <TouchableOpacity onPress={saveTemplate} disabled={saving} style={styles.saveButton}>
          {saving ? (
            <ActivityIndicator size="small" color="#000" />
          ) : (
            <Text style={styles.saveButtonText}>Save</Text>
          )}
        </TouchableOpacity>
      </View>

      <KeyboardAvoidingView 
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={{ flex: 1 }}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 20}
      >
        <ScrollView 
          style={styles.content} 
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={{ paddingBottom: 200 }}
        >
        {/* Live Preview */}
        <View style={[styles.previewCard, { backgroundColor: selectedTheme.bg }]}>
          <Text style={[styles.previewHeadline, { color: selectedTheme.accent }]}>
            {headline}
          </Text>
          <View style={[styles.previewPhoto, { borderColor: selectedTheme.accent }]}>
            <Ionicons name="person" size={40} color={selectedTheme.accent} />
          </View>
          <Text style={[styles.previewName, { color: selectedTheme.text }]}>
            Customer Name
          </Text>
          <Text style={[styles.previewMessage, { color: selectedTheme.text }]}>
            {message.replace('{customer_name}', 'Customer Name').replace('{salesman_name}', user?.name || 'You')}
          </Text>
        </View>

        {/* Pick a Theme */}
        <Text style={styles.sectionTitle}>Pick a Color Theme</Text>
        <View style={styles.themesGrid}>
          {THEMES.map((theme) => (
            <TouchableOpacity
              key={theme.id}
              style={[
                styles.themeOption,
                { backgroundColor: theme.bg, borderColor: theme.accent },
                selectedTheme.id === theme.id && styles.themeOptionSelected,
              ]}
              onPress={() => setSelectedTheme(theme)}
            >
              <View style={[styles.themeAccent, { backgroundColor: theme.accent }]} />
              <Text style={[styles.themeName, { color: theme.text }]}>{theme.name}</Text>
              {selectedTheme.id === theme.id && (
                <Ionicons name="checkmark-circle" size={24} color={theme.accent} style={styles.themeCheck} />
              )}
            </TouchableOpacity>
          ))}
        </View>

        {/* Pick a Headline */}
        <Text style={styles.sectionTitle}>Pick a Headline</Text>
        <View style={styles.headlinesContainer}>
          {HEADLINES.map((h) => (
            <TouchableOpacity
              key={h}
              style={[
                styles.headlineOption,
                headline === h && styles.headlineOptionSelected,
              ]}
              onPress={() => setHeadline(h)}
            >
              <Text style={[
                styles.headlineText,
                headline === h && styles.headlineTextSelected,
              ]}>
                {h}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Custom Headline */}
        <Text style={styles.sectionTitle}>Or Type Your Own</Text>
        <TextInput
          style={styles.customInput}
          value={headline}
          onChangeText={setHeadline}
          placeholder="Your headline..."
          placeholderTextColor="#6E6E73"
          maxLength={30}
        />

        {/* Message */}
        <Text style={styles.sectionTitle}>Thank You Message</Text>
        <Text style={styles.sectionHint}>Use {'{customer_name}'} to auto-fill their name</Text>
        <TextInput
          style={[styles.customInput, styles.messageInput]}
          value={message}
          onChangeText={setMessage}
          placeholder="Thank you message..."
          placeholderTextColor="#6E6E73"
          multiline
          numberOfLines={3}
          maxLength={200}
        />

        <View style={{ height: 50 }} />
        </ScrollView>
      </KeyboardAvoidingView>
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
    backgroundColor: '#000',
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
    backgroundColor: '#C9A962',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
    minWidth: 60,
    alignItems: 'center',
  },
  saveButtonText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#000',
  },
  content: {
    flex: 1,
    padding: 16,
  },
  previewCard: {
    borderRadius: 16,
    padding: 24,
    alignItems: 'center',
    marginBottom: 24,
  },
  previewHeadline: {
    fontSize: 28,
    fontWeight: '700',
    marginBottom: 16,
  },
  previewPhoto: {
    width: 80,
    height: 80,
    borderRadius: 18,
    borderWidth: 3,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#2C2C2E',
    marginBottom: 12,
  },
  previewName: {
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 8,
  },
  previewMessage: {
    fontSize: 14,
    textAlign: 'center',
    opacity: 0.9,
    lineHeight: 20,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 12,
    marginTop: 8,
  },
  sectionHint: {
    fontSize: 13,
    color: '#8E8E93',
    marginBottom: 12,
    marginTop: -8,
  },
  themesGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    marginBottom: 16,
  },
  themeOption: {
    width: '47%',
    padding: 16,
    borderRadius: 12,
    borderWidth: 2,
    position: 'relative',
  },
  themeOptionSelected: {
    borderWidth: 3,
  },
  themeAccent: {
    width: 40,
    height: 8,
    borderRadius: 4,
    marginBottom: 8,
  },
  themeName: {
    fontSize: 14,
    fontWeight: '500',
  },
  themeCheck: {
    position: 'absolute',
    top: 8,
    right: 8,
  },
  headlinesContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
    marginBottom: 16,
  },
  headlineOption: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    backgroundColor: '#1C1C1E',
    borderRadius: 20,
    borderWidth: 2,
    borderColor: 'transparent',
  },
  headlineOptionSelected: {
    backgroundColor: '#C9A96230',
    borderColor: '#C9A962',
  },
  headlineText: {
    fontSize: 14,
    color: '#8E8E93',
    fontWeight: '500',
  },
  headlineTextSelected: {
    color: '#C9A962',
  },
  customInput: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 14,
    fontSize: 16,
    color: '#FFF',
    marginBottom: 16,
  },
  messageInput: {
    minHeight: 100,
    textAlignVertical: 'top',
  },
});
