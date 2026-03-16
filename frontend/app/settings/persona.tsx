import React, {
  useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  TextInput,
  Alert,
  ActivityIndicator,
  Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';
import Toggle from '../../components/Toggle';
import VoiceInput from '../../components/VoiceInput';
import { useToast } from '../../components/common/Toast';

import { useThemeStore } from '../../store/themeStore';
interface PersonaSettings {
  tone: 'professional' | 'friendly' | 'casual' | 'formal';
  emoji_usage: 'never' | 'minimal' | 'moderate' | 'frequent';
  humor_level: 'none' | 'light' | 'moderate';
  response_length: 'brief' | 'balanced' | 'detailed';
  greeting_style: string;
  signature: string;
  auto_introduce: boolean;
  escalation_keywords: string[];
  interests: string[];
  specialties: string[];
  // Personal info for more realistic AI responses
  bio: string;
  hobbies: string[];
  family_info: string;
  hometown: string;
  fun_facts: string[];
  years_experience: string;
  personal_motto: string;
}

const TONE_OPTIONS = [
  { id: 'professional', label: 'Professional', icon: 'briefcase', desc: 'Business-appropriate' },
  { id: 'friendly', label: 'Friendly', icon: 'happy', desc: 'Warm & approachable' },
  { id: 'casual', label: 'Casual', icon: 'cafe', desc: 'Relaxed & informal' },
  { id: 'formal', label: 'Formal', icon: 'business', desc: 'Very professional' },
];

const EMOJI_OPTIONS = [
  { id: 'never', label: 'Never', count: 0 },
  { id: 'minimal', label: 'Minimal', count: 1 },
  { id: 'moderate', label: 'Moderate', count: 2 },
  { id: 'frequent', label: 'Frequent', count: 3 },
];

const HUMOR_OPTIONS = [
  { id: 'none', label: 'None', desc: 'Strictly business' },
  { id: 'light', label: 'Light', desc: 'Occasional wit' },
  { id: 'moderate', label: 'Moderate', desc: 'Playful when appropriate' },
];

const LENGTH_OPTIONS = [
  { id: 'brief', label: 'Brief', desc: '1-2 sentences' },
  { id: 'balanced', label: 'Balanced', desc: '2-3 sentences' },
  { id: 'detailed', label: 'Detailed', desc: 'Thorough responses' },
];

const DEFAULT_ESCALATION_KEYWORDS = ['urgent', 'emergency', 'complaint', 'refund', 'cancel', 'manager', 'supervisor'];

export default function PersonaSettings() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { user, updateUser } = useAuthStore();
const { showToast } = useToast();
    const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [settings, setSettings] = useState<PersonaSettings>({
    tone: 'friendly',
    emoji_usage: 'minimal',
    humor_level: 'light',
    response_length: 'balanced',
    greeting_style: 'Hi {name}!',
    signature: '',
    auto_introduce: true,
    escalation_keywords: DEFAULT_ESCALATION_KEYWORDS,
    interests: [],
    specialties: [],
    // Personal info defaults
    bio: '',
    hobbies: [],
    family_info: '',
    hometown: '',
    fun_facts: [],
    years_experience: '',
    personal_motto: '',
  });
  const [newKeyword, setNewKeyword] = useState('');
  const [newInterest, setNewInterest] = useState('');
  const [newSpecialty, setNewSpecialty] = useState('');
  const [newHobby, setNewHobby] = useState('');
  const [newFunFact, setNewFunFact] = useState('');

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    if (!user?._id) return;
    try {
      setLoading(true);
      const response = await api.get(`/users/${user._id}/persona`);
      if (response.data) {
        setSettings(prev => ({ ...prev, ...response.data }));
      }
    } catch (error) {
      console.log('No existing persona settings, using defaults');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!user?._id) return;
    try {
      setSaving(true);
      await api.put(`/users/${user._id}/persona`, settings);
      showToast('Your AI persona has been updated');
    } catch (error) {
      console.error('Error saving persona:', error);
      Alert.alert('Error', 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  const addKeyword = () => {
    const keyword = newKeyword.trim().toLowerCase();
    if (keyword && !settings.escalation_keywords.includes(keyword)) {
      setSettings(prev => ({
        ...prev,
        escalation_keywords: [...prev.escalation_keywords, keyword],
      }));
      setNewKeyword('');
    }
  };

  const removeKeyword = (keyword: string) => {
    setSettings(prev => ({
      ...prev,
      escalation_keywords: prev.escalation_keywords.filter(k => k !== keyword),
    }));
  };

  const addInterest = () => {
    const interest = newInterest.trim();
    if (interest && !settings.interests.includes(interest)) {
      setSettings(prev => ({
        ...prev,
        interests: [...prev.interests, interest],
      }));
      setNewInterest('');
    }
  };

  const removeInterest = (interest: string) => {
    setSettings(prev => ({
      ...prev,
      interests: prev.interests.filter(i => i !== interest),
    }));
  };

  const addSpecialty = () => {
    const specialty = newSpecialty.trim();
    if (specialty && !settings.specialties.includes(specialty)) {
      setSettings(prev => ({
        ...prev,
        specialties: [...prev.specialties, specialty],
      }));
      setNewSpecialty('');
    }
  };

  const removeSpecialty = (specialty: string) => {
    setSettings(prev => ({
      ...prev,
      specialties: prev.specialties.filter(s => s !== specialty),
    }));
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
        <Text style={styles.headerTitle}>AI Persona</Text>
        <TouchableOpacity style={styles.saveButton} onPress={handleSave} disabled={saving}>
          {saving ? (
            <ActivityIndicator size="small" color="#007AFF" />
          ) : (
            <Text style={styles.saveButtonText}>Save</Text>
          )}
        </TouchableOpacity>
      </View>

      <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
        {/* Preview Card */}
        <View style={styles.previewCard}>
          <Text style={styles.previewLabel}>Preview Message</Text>
          <View style={styles.previewBubble}>
            <Text style={styles.previewText}>
              {settings.greeting_style.replace('{name}', 'Sarah')} Thanks for reaching out about the SUV!
              {settings.emoji_usage !== 'never' ? ' 🚗' : ''} I'd love to help you find the perfect vehicle.
              {settings.signature ? `\n\n${settings.signature}` : ''}
            </Text>
          </View>
        </View>

        {/* Communication Tone */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>COMMUNICATION TONE</Text>
          <View style={styles.optionGrid}>
            {TONE_OPTIONS.map((option) => (
              <TouchableOpacity
                key={option.id}
                style={[
                  styles.toneOption,
                  settings.tone === option.id && styles.toneOptionSelected,
                ]}
                onPress={() => setSettings(prev => ({ ...prev, tone: option.id as any }))}
              >
                <Ionicons
                  name={option.icon as any}
                  size={24}
                  color={settings.tone === option.id ? '#007AFF' : colors.textSecondary}
                />
                <Text style={[styles.toneLabel, settings.tone === option.id && styles.toneLabelSelected]}>
                  {option.label}
                </Text>
                <Text style={styles.toneDesc}>{option.desc}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Emoji Usage */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>EMOJI USAGE</Text>
          <View style={styles.optionRow}>
            {EMOJI_OPTIONS.map((option) => (
              <TouchableOpacity
                key={option.id}
                style={[
                  styles.emojiOption,
                  settings.emoji_usage === option.id && styles.emojiOptionSelected,
                ]}
                onPress={() => setSettings(prev => ({ ...prev, emoji_usage: option.id as any }))}
              >
                <Text style={[styles.emojiLabel, settings.emoji_usage === option.id && styles.emojiLabelSelected]}>
                  {option.label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Humor Level */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>HUMOR LEVEL</Text>
          <View style={styles.optionRow}>
            {HUMOR_OPTIONS.map((option) => (
              <TouchableOpacity
                key={option.id}
                style={[
                  styles.humorOption,
                  settings.humor_level === option.id && styles.humorOptionSelected,
                ]}
                onPress={() => setSettings(prev => ({ ...prev, humor_level: option.id as any }))}
              >
                <Text style={[styles.humorLabel, settings.humor_level === option.id && styles.humorLabelSelected]}>
                  {option.label}
                </Text>
                <Text style={styles.humorDesc}>{option.desc}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Response Length */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>RESPONSE LENGTH</Text>
          <View style={styles.optionRow}>
            {LENGTH_OPTIONS.map((option) => (
              <TouchableOpacity
                key={option.id}
                style={[
                  styles.lengthOption,
                  settings.response_length === option.id && styles.lengthOptionSelected,
                ]}
                onPress={() => setSettings(prev => ({ ...prev, response_length: option.id as any }))}
              >
                <Text style={[styles.lengthLabel, settings.response_length === option.id && styles.lengthLabelSelected]}>
                  {option.label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Greeting & Signature */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>GREETING & SIGNATURE</Text>
          <View style={styles.inputGroup}>
            <Text style={styles.inputLabel}>Greeting Style</Text>
            <TextInput
              style={styles.input}
              value={settings.greeting_style}
              onChangeText={(text) => setSettings(prev => ({ ...prev, greeting_style: text }))}
              placeholder="Hi {name}!"
              placeholderTextColor={colors.textSecondary}
            />
            <Text style={styles.inputHint}>Use {'{name}'} to insert contact's name</Text>
          </View>
          <View style={styles.inputGroup}>
            <Text style={styles.inputLabel}>Signature (optional)</Text>
            <TextInput
              style={styles.input}
              value={settings.signature}
              onChangeText={(text) => setSettings(prev => ({ ...prev, signature: text }))}
              placeholder="- Your Name, Title"
              placeholderTextColor={colors.textSecondary}
            />
          </View>
          <View style={styles.switchRow}>
            <View style={{ flex: 1 }}>
              <Text style={styles.switchLabel}>Auto-introduce on first contact</Text>
              <Text style={styles.switchHint}>AI will introduce itself when messaging new leads</Text>
            </View>
            <Toggle
              value={settings.auto_introduce}
              onValueChange={(value) => setSettings(prev => ({ ...prev, auto_introduce: value }))}
              activeColor="#34C759"
            />
          </View>
        </View>

        {/* Escalation Keywords */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>ESCALATION KEYWORDS</Text>
          <Text style={styles.sectionDesc}>
            AI will flag conversations containing these words for your attention
          </Text>
          <View style={styles.chipContainer}>
            {settings.escalation_keywords.map((keyword) => (
              <View key={keyword} style={styles.chip}>
                <Text style={styles.chipText}>{keyword}</Text>
                <TouchableOpacity onPress={() => removeKeyword(keyword)}>
                  <Ionicons name="close-circle" size={18} color={colors.textSecondary} />
                </TouchableOpacity>
              </View>
            ))}
          </View>
          <View style={styles.addRow}>
            <TextInput
              style={styles.addInput}
              value={newKeyword}
              onChangeText={setNewKeyword}
              placeholder="Add keyword..."
              placeholderTextColor={colors.textSecondary}
              onSubmitEditing={addKeyword}
            />
            <TouchableOpacity style={styles.addButton} onPress={addKeyword}>
              <Ionicons name="add" size={24} color="#007AFF" />
            </TouchableOpacity>
          </View>
        </View>

        {/* Specialties */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>YOUR SPECIALTIES</Text>
          <Text style={styles.sectionDesc}>
            Help your AI understand what you specialize in
          </Text>
          <View style={styles.chipContainer}>
            {settings.specialties.map((specialty) => (
              <View key={specialty} style={[styles.chip, styles.chipGreen]}>
                <Text style={styles.chipText}>{specialty}</Text>
                <TouchableOpacity onPress={() => removeSpecialty(specialty)}>
                  <Ionicons name="close-circle" size={18} color={colors.textSecondary} />
                </TouchableOpacity>
              </View>
            ))}
          </View>
          <View style={styles.addRow}>
            <TextInput
              style={styles.addInput}
              value={newSpecialty}
              onChangeText={setNewSpecialty}
              placeholder="e.g., Trucks, Financing, Trade-ins..."
              placeholderTextColor={colors.textSecondary}
              onSubmitEditing={addSpecialty}
            />
            <TouchableOpacity style={styles.addButton} onPress={addSpecialty}>
              <Ionicons name="add" size={24} color="#007AFF" />
            </TouchableOpacity>
          </View>
        </View>

        {/* Personal Story Section - Train Your AI */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>📖 YOUR PERSONAL STORY</Text>
          <Text style={styles.sectionDesc}>
            Help your AI sound more like YOU. The more it knows, the more realistic and personal your automated messages will be.
          </Text>
          
          {/* Bio */}
          <Text style={[styles.sectionTitle, { marginTop: 16, fontSize: 12 }]}>ABOUT YOU</Text>
          <View style={styles.voiceInputRow}>
            <TextInput
              style={[styles.addInput, { minHeight: 280, textAlignVertical: 'top', flex: 1 }]}
              value={settings.bio}
              onChangeText={(text) => setSettings(prev => ({ ...prev, bio: text }))}
              placeholder="Tell us about yourself... e.g., I've been in auto sales for 15 years, started as a lot porter..."
              placeholderTextColor={colors.textSecondary}
              multiline
            />
            <VoiceInput
              onTranscription={(text) => setSettings(prev => ({ ...prev, bio: prev.bio ? prev.bio + ' ' + text : text }))}
              size="small"
              style={{ marginLeft: 8 }}
            />
          </View>
          
          {/* Years Experience */}
          <Text style={[styles.sectionTitle, { fontSize: 12 }]}>YEARS IN THE BUSINESS</Text>
          <TextInput
            style={[styles.addInput, { marginBottom: 16 }]}
            value={settings.years_experience}
            onChangeText={(text) => setSettings(prev => ({ ...prev, years_experience: text }))}
            placeholder="e.g., 15 years"
            placeholderTextColor={colors.textSecondary}
          />
          
          {/* Hometown */}
          <Text style={[styles.sectionTitle, { fontSize: 12 }]}>HOMETOWN / WHERE YOU'RE FROM</Text>
          <View style={styles.voiceInputRow}>
            <TextInput
              style={[styles.addInput, { flex: 1 }]}
              value={settings.hometown}
              onChangeText={(text) => setSettings(prev => ({ ...prev, hometown: text }))}
              placeholder="e.g., Born and raised in Dallas, TX"
              placeholderTextColor={colors.textSecondary}
            />
            <VoiceInput
              onTranscription={(text) => setSettings(prev => ({ ...prev, hometown: prev.hometown ? prev.hometown + ' ' + text : text }))}
              size="small"
            />
          </View>
          
          {/* Family Info */}
          <Text style={[styles.sectionTitle, { fontSize: 12 }]}>FAMILY</Text>
          <View style={styles.voiceInputRow}>
            <TextInput
              style={[styles.addInput, { flex: 1 }]}
              value={settings.family_info}
              onChangeText={(text) => setSettings(prev => ({ ...prev, family_info: text }))}
              placeholder="e.g., Married with 2 kids, dog named Max"
              placeholderTextColor={colors.textSecondary}
            />
            <VoiceInput
              onTranscription={(text) => setSettings(prev => ({ ...prev, family_info: prev.family_info ? prev.family_info + ' ' + text : text }))}
              size="small"
            />
          </View>
          
          {/* Personal Motto */}
          <Text style={[styles.sectionTitle, { fontSize: 12 }]}>YOUR MOTTO / CATCHPHRASE</Text>
          <View style={styles.voiceInputRow}>
            <TextInput
              style={[styles.addInput, { flex: 1 }]}
              value={settings.personal_motto}
              onChangeText={(text) => setSettings(prev => ({ ...prev, personal_motto: text }))}
              placeholder='e.g., "Treat every customer like family"'
              placeholderTextColor={colors.textSecondary}
            />
            <VoiceInput
              onTranscription={(text) => setSettings(prev => ({ ...prev, personal_motto: prev.personal_motto ? prev.personal_motto + ' ' + text : text }))}
              size="small"
            />
          </View>
          
          {/* Hobbies */}
          <Text style={[styles.sectionTitle, { fontSize: 12 }]}>HOBBIES & INTERESTS</Text>
          <Text style={[styles.sectionDesc, { fontSize: 12 }]}>
            What do you do outside of work? This helps build rapport.
          </Text>
          <View style={styles.chipContainer}>
            {(settings.hobbies || []).map((hobby) => (
              <View key={hobby} style={[styles.chip, { backgroundColor: '#FF9500' }]}>
                <Text style={styles.chipText}>{hobby}</Text>
                <TouchableOpacity onPress={() => setSettings(prev => ({ 
                  ...prev, 
                  hobbies: prev.hobbies.filter(h => h !== hobby) 
                }))}>
                  <Ionicons name="close-circle" size={18} color={colors.text} />
                </TouchableOpacity>
              </View>
            ))}
          </View>
          <View style={styles.addRow}>
            <TextInput
              style={styles.addInput}
              value={newHobby}
              onChangeText={setNewHobby}
              placeholder="e.g., Golf, Fishing, Cowboys fan..."
              placeholderTextColor={colors.textSecondary}
              onSubmitEditing={() => {
                if (newHobby.trim()) {
                  setSettings(prev => ({ ...prev, hobbies: [...(prev.hobbies || []), newHobby.trim()] }));
                  setNewHobby('');
                }
              }}
            />
            <TouchableOpacity style={styles.addButton} onPress={() => {
              if (newHobby.trim()) {
                setSettings(prev => ({ ...prev, hobbies: [...(prev.hobbies || []), newHobby.trim()] }));
                setNewHobby('');
              }
            }}>
              <Ionicons name="add" size={24} color="#007AFF" />
            </TouchableOpacity>
          </View>
          
          {/* Fun Facts */}
          <Text style={[styles.sectionTitle, { fontSize: 12, marginTop: 16 }]}>FUN FACTS ABOUT YOU</Text>
          <Text style={[styles.sectionDesc, { fontSize: 12 }]}>
            Unique things that make you memorable
          </Text>
          <View style={styles.chipContainer}>
            {(settings.fun_facts || []).map((fact, index) => (
              <View key={index} style={[styles.chip, { backgroundColor: '#AF52DE' }]}>
                <Text style={styles.chipText}>{fact}</Text>
                <TouchableOpacity onPress={() => setSettings(prev => ({ 
                  ...prev, 
                  fun_facts: prev.fun_facts.filter((_, i) => i !== index) 
                }))}>
                  <Ionicons name="close-circle" size={18} color={colors.text} />
                </TouchableOpacity>
              </View>
            ))}
          </View>
          <View style={styles.addRow}>
            <TextInput
              style={styles.addInput}
              value={newFunFact}
              onChangeText={setNewFunFact}
              placeholder="e.g., I once sold 50 cars in one month..."
              placeholderTextColor={colors.textSecondary}
              onSubmitEditing={() => {
                if (newFunFact.trim()) {
                  setSettings(prev => ({ ...prev, fun_facts: [...(prev.fun_facts || []), newFunFact.trim()] }));
                  setNewFunFact('');
                }
              }}
            />
            <TouchableOpacity style={styles.addButton} onPress={() => {
              if (newFunFact.trim()) {
                setSettings(prev => ({ ...prev, fun_facts: [...(prev.fun_facts || []), newFunFact.trim()] }));
                setNewFunFact('');
              }
            }}>
              <Ionicons name="add" size={24} color="#007AFF" />
            </TouchableOpacity>
          </View>
        </View>

        {/* Retrain Button */}
        <TouchableOpacity 
          style={[styles.saveButtonLarge, { backgroundColor: '#34C759', marginBottom: 16 }]}
          onPress={handleSave}
        >
          <Ionicons name="refresh" size={20} color={colors.text} style={{ marginRight: 8 }} />
          <Text style={styles.saveButtonLargeText}>Retrain My AI</Text>
        </TouchableOpacity>

        <View style={{ height: 40 }} />
      </ScrollView>
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
    width: 60,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: colors.text,
  },
  saveButton: {
    width: 60,
    alignItems: 'flex-end',
  },
  saveButtonText: {
    fontSize: 17,
    color: '#007AFF',
    fontWeight: '600',
  },
  content: {
    flex: 1,
    padding: 16,
  },
  previewCard: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginBottom: 24,
  },
  previewLabel: {
    fontSize: 12,
    color: colors.textSecondary,
    marginBottom: 12,
  },
  previewBubble: {
    backgroundColor: '#007AFF',
    borderRadius: 16,
    padding: 12,
    borderBottomRightRadius: 4,
  },
  previewText: {
    color: colors.text,
    fontSize: 14,
    lineHeight: 20,
  },
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 12,
  },
  sectionDesc: {
    fontSize: 13,
    color: '#6E6E73',
    marginBottom: 12,
  },
  optionGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  toneOption: {
    width: '48%',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 14,
    borderWidth: 2,
    borderColor: 'transparent',
  },
  toneOptionSelected: {
    borderColor: '#007AFF',
    backgroundColor: '#007AFF15',
  },
  toneLabel: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.text,
    marginTop: 8,
  },
  toneLabelSelected: {
    color: '#007AFF',
  },
  toneDesc: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 2,
  },
  optionRow: {
    flexDirection: 'row',
    gap: 8,
  },
  emojiOption: {
    flex: 1,
    backgroundColor: colors.card,
    borderRadius: 10,
    padding: 12,
    alignItems: 'center',
    borderWidth: 2,
    borderColor: 'transparent',
  },
  emojiOptionSelected: {
    borderColor: '#007AFF',
    backgroundColor: '#007AFF15',
  },
  emojiLabel: {
    fontSize: 13,
    color: colors.text,
    fontWeight: '500',
  },
  emojiLabelSelected: {
    color: '#007AFF',
  },
  humorOption: {
    flex: 1,
    backgroundColor: colors.card,
    borderRadius: 10,
    padding: 12,
    alignItems: 'center',
    borderWidth: 2,
    borderColor: 'transparent',
  },
  humorOptionSelected: {
    borderColor: '#007AFF',
    backgroundColor: '#007AFF15',
  },
  humorLabel: {
    fontSize: 13,
    color: colors.text,
    fontWeight: '600',
  },
  humorLabelSelected: {
    color: '#007AFF',
  },
  humorDesc: {
    fontSize: 11,
    color: colors.textSecondary,
    marginTop: 4,
    textAlign: 'center',
  },
  lengthOption: {
    flex: 1,
    backgroundColor: colors.card,
    borderRadius: 10,
    padding: 12,
    alignItems: 'center',
    borderWidth: 2,
    borderColor: 'transparent',
  },
  lengthOptionSelected: {
    borderColor: '#007AFF',
    backgroundColor: '#007AFF15',
  },
  lengthLabel: {
    fontSize: 13,
    color: colors.text,
    fontWeight: '500',
  },
  lengthLabelSelected: {
    color: '#007AFF',
  },
  inputGroup: {
    marginBottom: 16,
  },
  inputLabel: {
    fontSize: 14,
    color: colors.textSecondary,
    marginBottom: 8,
  },
  input: {
    backgroundColor: colors.card,
    borderRadius: 10,
    padding: 14,
    fontSize: 16,
    color: colors.text,
  },
  inputHint: {
    fontSize: 12,
    color: '#6E6E73',
    marginTop: 6,
  },
  switchRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 10,
    padding: 14,
    minHeight: 70,
  },
  switchLabel: {
    fontSize: 15,
    color: colors.text,
    fontWeight: '500',
    flex: 1,
  },
  switchHint: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 2,
    paddingRight: 60,
  },
  chipContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 12,
  },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: 16,
    paddingHorizontal: 12,
    paddingVertical: 6,
    gap: 6,
  },
  chipGreen: {
    backgroundColor: '#34C75920',
  },
  chipText: {
    fontSize: 14,
    color: colors.text,
  },
  addRow: {
    flexDirection: 'row',
    gap: 8,
  },
  voiceInputRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
    marginBottom: 16,
  },
  addInput: {
    flex: 1,
    backgroundColor: colors.card,
    borderRadius: 10,
    padding: 12,
    fontSize: 15,
    color: colors.text,
  },
  addButton: {
    width: 48,
    height: 48,
    backgroundColor: colors.card,
    borderRadius: 10,
    justifyContent: 'center',
    alignItems: 'center',
  },
  saveButtonLarge: {
    flexDirection: 'row',
    backgroundColor: '#007AFF',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  saveButtonLargeText: {
    fontSize: 17,
    fontWeight: '600',
    color: colors.text,
  },
});
