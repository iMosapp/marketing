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
import { showAlert } from '../../services/alert';
import { JESSI_BAR_HEIGHT } from '../../components/JessieFloatingChat';

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
  // Personal info
  bio: string;
  hobbies: string[];
  family_info: string;
  hometown: string;
  fun_facts: string[];
  years_experience: string;
  personal_motto: string;
  // New: from AI clone document
  vehicles: string;         // What they drive/own — makes AI sound human
  never_say: string;        // Phrases/things they would never say
  custom_phrases: string;   // Things they always say
  ideal_customer: string;   // Who they serve best
  scheduling_link: string;  // e.g. Calendly / HubSpot meetings link
  payment_link: string;     // Venmo, CashApp, etc.
  key_links: string;        // Other important URLs (comma-separated)
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
  const [currentStep, setCurrentStep] = useState(1);
  const TOTAL_STEPS = 5;
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
    bio: '',
    hobbies: [],
    family_info: '',
    hometown: '',
    fun_facts: [],
    years_experience: '',
    personal_motto: '',
    // New fields
    vehicles: '',
    never_say: '',
    custom_phrases: '',
    ideal_customer: '',
    scheduling_link: '',
    payment_link: '',
    key_links: '',
  });
  const [newKeyword, setNewKeyword] = useState('');
  const [newInterest, setNewInterest] = useState('');
  const [newSpecialty, setNewSpecialty] = useState('');
  const [newHobby, setNewHobby] = useState('');
  const [newFunFact, setNewFunFact] = useState('');
  const [generatedBio, setGeneratedBio] = useState('');
  const [retraining, setRetraining] = useState(false);

  useEffect(() => {
    loadSettings();
  }, [user?._id]);

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
      showToast('Your profile has been saved!');
      // Always navigate back to My Presence after saving
      router.replace('/my-account' as any);
    } catch (error) {
      console.error('Error saving persona:', error);
      showAlert('Error', 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  const handleRetrain = async () => {
    if (!user?._id) return;
    try {
      setRetraining(true);
      // Save settings first
      await api.put(`/users/${user._id}/persona`, settings);
      // Generate AI bio
      const res = await api.post(`/profile/${user._id}/generate-bio`, {
        name: user.name,
        title: user.title,
        hobbies: settings.hobbies,
        family_info: settings.family_info,
        hometown: settings.hometown,
        years_experience: settings.years_experience,
        fun_facts: settings.fun_facts,
        personal_motto: settings.personal_motto,
      });
      if (res.data?.bio) {
        // Strip em dashes from AI output
        const cleanBio = res.data.bio.replace(/—/g, ',');
        setGeneratedBio(cleanBio);
        showToast('AI bio generated! Review it below.');
      }
    } catch (error: any) {
      console.error('Error retraining:', error);
      showAlert('Error', error?.response?.data?.detail || 'Failed to generate bio');
    } finally {
      setRetraining(false);
    }
  };

  const handleAcceptBio = async () => {
    if (!user?._id || !generatedBio) return;
    setSettings(prev => ({ ...prev, bio: generatedBio }));
    try {
      await api.put(`/users/${user._id}/persona`, { ...settings, bio: generatedBio });
      showToast('AI bio saved as your About You');
    } catch (error) {
      console.error('Error saving bio:', error);
    }
    setGeneratedBio('');
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

  const STEP_LABELS = ['Your Story', 'Your World', 'Your Voice', 'Your Tools', 'Final Touches'];

  const goNext = () => { if (currentStep < TOTAL_STEPS) setCurrentStep(currentStep + 1); };
  const goBack = () => { if (currentStep > 1) setCurrentStep(currentStep - 1); };

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
        <TouchableOpacity style={styles.backButton} onPress={() => { if (currentStep > 1) goBack(); else router.back(); }}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Build Your Profile</Text>
        <TouchableOpacity style={styles.saveButton} onPress={handleSave} disabled={saving}>
          {saving ? (
            <ActivityIndicator size="small" color="#007AFF" />
          ) : (
            <Text style={styles.saveButtonText}>Save</Text>
          )}
        </TouchableOpacity>
      </View>

      {/* Progress Bar */}
      <View style={styles.progressContainer}>
        <View style={styles.progressBarTrack}>
          <View style={[styles.progressBarFill, { width: `${(currentStep / TOTAL_STEPS) * 100}%` }]} />
        </View>
        <Text style={styles.progressLabel}>Step {currentStep} of {TOTAL_STEPS} — {STEP_LABELS[currentStep - 1]}</Text>
      </View>

      <ScrollView style={styles.content} showsVerticalScrollIndicator={false} key={`step-${currentStep}`}>

        {/* ═══════ STEP 1: Your Story ═══════ */}
        {currentStep === 1 && (
          <>
            {/* WHY banner */}
            <View style={styles.whyBanner}>
              <Ionicons name="information-circle" size={20} color="#C9A962" />
              <Text style={styles.whyText}>
                Your story shows up on your <Text style={styles.whyHighlight}>Digital Card, Link Page, and Landing Page</Text> — it's how customers get to know you before they ever meet you.
              </Text>
            </View>

            <Text style={styles.stepTitle}>Tell us about yourself</Text>
            <Text style={styles.stepSubtitle}>Write it like you're talking to a customer. Be real, be you.</Text>

            {/* Bio */}
            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>About You</Text>
              <Text style={styles.fieldHint}>Write your story in your own words. Who are you? What drives you?</Text>
              <View style={[styles.voiceInputRow, { alignItems: 'stretch' }]}>
                <TextInput
                  style={[styles.addInput, styles.bioInput]}
                  value={settings.bio}
                  onChangeText={(text) => setSettings(prev => ({ ...prev, bio: text }))}
                  placeholder="e.g., I've been in auto sales for 15 years, started as a lot porter..."
                  placeholderTextColor={colors.textSecondary}
                  multiline
                  numberOfLines={10}
                  scrollEnabled={true}
                />
                <VoiceInput
                  onTranscription={(text) => setSettings(prev => ({ ...prev, bio: prev.bio ? prev.bio + ' ' + text : text }))}
                  size="small"
                  style={{ marginLeft: 8 }}
                />
              </View>
            </View>

            {/* Family */}
            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>Family</Text>
              <View style={styles.voiceInputRow}>
                <TextInput
                  style={[styles.addInput, { flex: 1, minHeight: 80, textAlignVertical: 'top', paddingTop: 12 }]}
                  value={settings.family_info}
                  onChangeText={(text) => setSettings(prev => ({ ...prev, family_info: text }))}
                  placeholder="e.g., Married with 2 kids, dog named Max"
                  placeholderTextColor={colors.textSecondary}
                  multiline
                  numberOfLines={3}
                />
                <VoiceInput
                  onTranscription={(text) => setSettings(prev => ({ ...prev, family_info: prev.family_info ? prev.family_info + ' ' + text : text }))}
                  size="small"
                />
              </View>
            </View>

            {/* Hometown */}
            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>Hometown</Text>
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
            </View>

            {/* Years in Business */}
            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>Years in the Business</Text>
              <TextInput
                style={[styles.addInput, { minHeight: 60, textAlignVertical: 'top', paddingTop: 12 }]}
                value={settings.years_experience}
                onChangeText={(text) => setSettings(prev => ({ ...prev, years_experience: text }))}
                placeholder="e.g., 15 years in automotive sales"
                placeholderTextColor={colors.textSecondary}
                multiline
                numberOfLines={2}
              />
            </View>

            {/* Motto */}
            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>Your Motto / Catchphrase</Text>
              <View style={styles.voiceInputRow}>
                <TextInput
                  style={[styles.addInput, { flex: 1 }]}
                  value={settings.personal_motto}
                  onChangeText={(text) => setSettings(prev => ({ ...prev, personal_motto: text }))}
                  placeholder='"Treat every customer like family"'
                  placeholderTextColor={colors.textSecondary}
                />
                <VoiceInput
                  onTranscription={(text) => setSettings(prev => ({ ...prev, personal_motto: prev.personal_motto ? prev.personal_motto + ' ' + text : text }))}
                  size="small"
                />
              </View>
            </View>
          </>
        )}

        {/* ═══════ STEP 2: Your World ═══════ */}
        {currentStep === 2 && (
          <>
            {/* WHY banner */}
            <View style={styles.whyBanner}>
              <Ionicons name="information-circle" size={20} color="#C9A962" />
              <Text style={styles.whyText}>
                The more specific you are, the more <Text style={styles.whyHighlight}>authentic your profile feels</Text> to customers. These details make you relatable — not just another salesperson.
              </Text>
            </View>

            <Text style={styles.stepTitle}>What makes you, you?</Text>
            <Text style={styles.stepSubtitle}>Your lifestyle, interests, and the things customers connect with.</Text>

            {/* What you drive / own */}
            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>What Do You Drive / Own?</Text>
              <Text style={styles.fieldHint}>Your vehicle(s), toys, gear — whatever says something about you. This makes your profile feel like a real person, not a sales bot.</Text>
              <View style={styles.voiceInputRow}>
                <TextInput
                  style={[styles.addInput, { flex: 1, minHeight: 80, textAlignVertical: 'top', paddingTop: 12 }]}
                  value={settings.vehicles}
                  onChangeText={(text) => setSettings(prev => ({ ...prev, vehicles: text }))}
                  placeholder={'e.g., I drive a 2021 Jeep Gladiator on 40" tires. I also have two Harleys — a Road Glide ST and a Low Rider S. Nothing I own stays stock for more than a week.'}
                  placeholderTextColor={colors.textSecondary}
                  multiline
                  numberOfLines={4}
                />
                <VoiceInput
                  onTranscription={(text) => setSettings(prev => ({ ...prev, vehicles: prev.vehicles ? prev.vehicles + ' ' + text : text }))}
                  size="small"
                />
              </View>
            </View>

            {/* Hobbies */}
            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>Hobbies & Interests</Text>
              <Text style={styles.fieldHint}>What do you do outside of work?</Text>
              <View style={styles.chipContainer}>
                {(settings.hobbies || []).map((hobby) => (
                  <View key={hobby} style={[styles.chip, { backgroundColor: '#FF9500' }]}>
                    <Text style={styles.chipText}>{hobby}</Text>
                    <TouchableOpacity onPress={() => setSettings(prev => ({ ...prev, hobbies: prev.hobbies.filter(h => h !== hobby) }))}>
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
                  onSubmitEditing={() => { if (newHobby.trim()) { setSettings(prev => ({ ...prev, hobbies: [...(prev.hobbies || []), newHobby.trim()] })); setNewHobby(''); } }}
                />
                <TouchableOpacity style={styles.addButton} onPress={() => { if (newHobby.trim()) { setSettings(prev => ({ ...prev, hobbies: [...(prev.hobbies || []), newHobby.trim()] })); setNewHobby(''); } }}>
                  <Ionicons name="add" size={24} color="#007AFF" />
                </TouchableOpacity>
              </View>
            </View>

            {/* Fun Facts */}
            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>Fun Facts About You</Text>
              <Text style={styles.fieldHint}>Unique things that make you memorable</Text>
              <View style={styles.chipContainer}>
                {(settings.fun_facts || []).map((fact, index) => (
                  <View key={index} style={[styles.chip, { backgroundColor: '#AF52DE', maxWidth: '100%' }]}>
                    <Text style={[styles.chipText, { flexShrink: 1 }]}>{fact}</Text>
                    <TouchableOpacity onPress={() => setSettings(prev => ({ ...prev, fun_facts: prev.fun_facts.filter((_, i) => i !== index) }))}>
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
                  onSubmitEditing={() => { if (newFunFact.trim()) { setSettings(prev => ({ ...prev, fun_facts: [...(prev.fun_facts || []), newFunFact.trim()] })); setNewFunFact(''); } }}
                />
                <TouchableOpacity style={styles.addButton} onPress={() => { if (newFunFact.trim()) { setSettings(prev => ({ ...prev, fun_facts: [...(prev.fun_facts || []), newFunFact.trim()] })); setNewFunFact(''); } }}>
                  <Ionicons name="add" size={24} color="#007AFF" />
                </TouchableOpacity>
              </View>
            </View>

            {/* Specialties */}
            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>Your Specialties</Text>
              <Text style={styles.fieldHint}>Help your AI understand what you specialize in</Text>
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

            {/* Retrain + Generated Bio */}
            <TouchableOpacity 
              style={[styles.saveButtonLarge, { backgroundColor: '#34C759', marginBottom: 12, opacity: retraining ? 0.6 : 1 }]}
              onPress={handleRetrain}
              disabled={retraining}
            >
              {retraining ? (
                <ActivityIndicator size="small" color={colors.text} style={{ marginRight: 8 }} />
              ) : (
                <Ionicons name="sparkles" size={20} color={colors.text} style={{ marginRight: 8 }} />
              )}
              <Text style={styles.saveButtonLargeText}>{retraining ? 'Generating...' : 'Generate AI Bio From My Info'}</Text>
            </TouchableOpacity>
            {generatedBio ? (
              <View style={{ backgroundColor: colors.card, borderRadius: 12, padding: 16, marginBottom: 16, borderWidth: 1, borderColor: '#34C759' }}>
                <Text style={{ fontSize: 14, fontWeight: '600', color: '#34C759', marginBottom: 10 }}>AI-GENERATED BIO (PREVIEW)</Text>
                <TextInput
                  style={[styles.addInput, { height: 200, textAlignVertical: 'top', marginBottom: 12, lineHeight: 22, paddingTop: 14 }]}
                  value={generatedBio}
                  onChangeText={setGeneratedBio}
                  multiline
                  numberOfLines={8}
                  scrollEnabled={true}
                />
                <View style={{ flexDirection: 'row', gap: 10 }}>
                  <TouchableOpacity
                    style={{ flex: 1, backgroundColor: '#34C759', borderRadius: 10, padding: 12, alignItems: 'center' }}
                    onPress={handleAcceptBio}
                  >
                    <Text style={{ color: '#fff', fontWeight: '600', fontSize: 17 }}>Use This Bio</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={{ flex: 1, backgroundColor: colors.card, borderRadius: 10, padding: 12, alignItems: 'center', borderWidth: 1, borderColor: colors.textSecondary }}
                    onPress={() => setGeneratedBio('')}
                  >
                    <Text style={{ color: colors.textSecondary, fontWeight: '600', fontSize: 17 }}>Dismiss</Text>
                  </TouchableOpacity>
                </View>
              </View>
            ) : null}
          </>
        )}

        {/* ═══════ STEP 3: Your Voice ═══════ */}
        {currentStep === 3 && (
          <>
            {/* WHY banner */}
            <View style={styles.whyBanner}>
              <Ionicons name="information-circle" size={20} color="#C9A962" />
              <Text style={styles.whyText}>
                When Jessi responds to your customers, she'll match <Text style={styles.whyHighlight}>your tone, your style, your way</Text>. The more specific you are, the more it actually sounds like you.
              </Text>
            </View>

            <Text style={styles.stepTitle}>How do you communicate?</Text>
            <Text style={styles.stepSubtitle}>Your style, your vibe — not a corporate bot.</Text>

            {/* Preview */}
            <View style={styles.previewCard}>
              <Text style={styles.previewLabel}>Preview Message</Text>
              <View style={styles.previewBubble}>
                <Text style={styles.previewText}>
                  {settings.greeting_style.replace('{name}', 'Sarah')} Thanks for reaching out about the SUV!
                  {settings.emoji_usage !== 'never' ? ' \uD83D\uDE97' : ''} I'd love to help you find the perfect vehicle.
                  {settings.signature ? `\n\n${settings.signature}` : ''}
                </Text>
              </View>
            </View>

            {/* Tone */}
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>YOUR STYLE</Text>
              <View style={styles.optionGrid}>
                {TONE_OPTIONS.map((option) => (
                  <TouchableOpacity
                    key={option.id}
                    style={[styles.toneOption, settings.tone === option.id && styles.toneOptionSelected]}
                    onPress={() => setSettings(prev => ({ ...prev, tone: option.id as any }))}
                  >
                    <Ionicons name={option.icon as any} size={24} color={settings.tone === option.id ? '#007AFF' : colors.textSecondary} />
                    <Text style={[styles.toneLabel, settings.tone === option.id && styles.toneLabelSelected]}>{option.label}</Text>
                    <Text style={styles.toneDesc}>{option.desc}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>

            {/* Emoji */}
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>EMOJI USAGE</Text>
              <View style={styles.optionRow}>
                {EMOJI_OPTIONS.map((option) => (
                  <TouchableOpacity key={option.id} style={[styles.emojiOption, settings.emoji_usage === option.id && styles.emojiOptionSelected]} onPress={() => setSettings(prev => ({ ...prev, emoji_usage: option.id as any }))}>
                    <Text style={[styles.emojiLabel, settings.emoji_usage === option.id && styles.emojiLabelSelected]}>{option.label}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>

            {/* Humor */}
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>HUMOR LEVEL</Text>
              <View style={styles.optionRow}>
                {HUMOR_OPTIONS.map((option) => (
                  <TouchableOpacity key={option.id} style={[styles.humorOption, settings.humor_level === option.id && styles.humorOptionSelected]} onPress={() => setSettings(prev => ({ ...prev, humor_level: option.id as any }))}>
                    <Text style={[styles.humorLabel, settings.humor_level === option.id && styles.humorLabelSelected]}>{option.label}</Text>
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
                  <TouchableOpacity key={option.id} style={[styles.lengthOption, settings.response_length === option.id && styles.lengthOptionSelected]} onPress={() => setSettings(prev => ({ ...prev, response_length: option.id as any }))}>
                    <Text style={[styles.lengthLabel, settings.response_length === option.id && styles.lengthLabelSelected]}>{option.label}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>

            {/* Things you NEVER say */}
            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>Things You Never Say</Text>
              <Text style={styles.fieldHint}>Phrases, words, or attitudes you'd never use with a customer. Jessi won't use them either.</Text>
              <View style={styles.voiceInputRow}>
                <TextInput
                  style={[styles.addInput, { flex: 1, minHeight: 80, textAlignVertical: 'top', paddingTop: 12 }]}
                  value={settings.never_say}
                  onChangeText={(text) => setSettings(prev => ({ ...prev, never_say: text }))}
                  placeholder={'e.g., I never use em dashes, never say "just an AI", never over-apologize, never use corporate speak'}
                  placeholderTextColor={colors.textSecondary}
                  multiline
                  numberOfLines={4}
                />
                <VoiceInput
                  onTranscription={(text) => setSettings(prev => ({ ...prev, never_say: prev.never_say ? prev.never_say + ' ' + text : text }))}
                  size="small"
                />
              </View>
            </View>

            {/* Your go-to phrases */}
            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>Your Go-To Phrases</Text>
              <Text style={styles.fieldHint}>Things you actually say. Expressions, catchphrases, how you sign off — whatever makes you sound like you.</Text>
              <View style={styles.voiceInputRow}>
                <TextInput
                  style={[styles.addInput, { flex: 1, minHeight: 80, textAlignVertical: 'top', paddingTop: 12 }]}
                  value={settings.custom_phrases}
                  onChangeText={(text) => setSettings(prev => ({ ...prev, custom_phrases: text }))}
                  placeholder={'e.g., I always say "let me wrap up what I\'m doing quick", I end texts with "- Forest", I use "I appreciate you" a lot'}
                  placeholderTextColor={colors.textSecondary}
                  multiline
                  numberOfLines={4}
                />
                <VoiceInput
                  onTranscription={(text) => setSettings(prev => ({ ...prev, custom_phrases: prev.custom_phrases ? prev.custom_phrases + ' ' + text : text }))}
                  size="small"
                />
              </View>
            </View>
          </>
        )}

        {/* ═══════ STEP 4: Your Tools ═══════ */}
        {currentStep === 4 && (
          <>
            {/* WHY banner */}
            <View style={styles.whyBanner}>
              <Ionicons name="information-circle" size={20} color="#C9A962" />
              <Text style={styles.whyText}>
                When customers ask to schedule, pay, or learn more, Jessi can <Text style={styles.whyHighlight}>share your links instantly</Text> — no you required.
              </Text>
            </View>

            <Text style={styles.stepTitle}>Your links and tools</Text>
            <Text style={styles.stepSubtitle}>The stuff Jessi can share on your behalf when customers need it.</Text>

            {/* Who is your ideal customer */}
            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>Who Do You Serve Best?</Text>
              <Text style={styles.fieldHint}>Describe your ideal customer. Jessi uses this to personalize conversations and qualify leads.</Text>
              <View style={styles.voiceInputRow}>
                <TextInput
                  style={[styles.addInput, { flex: 1, minHeight: 80, textAlignVertical: 'top', paddingTop: 12 }]}
                  value={settings.ideal_customer}
                  onChangeText={(text) => setSettings(prev => ({ ...prev, ideal_customer: text }))}
                  placeholder={'e.g., First-time car buyers, families looking for SUVs, people who value the experience more than just the price'}
                  placeholderTextColor={colors.textSecondary}
                  multiline
                  numberOfLines={4}
                />
                <VoiceInput
                  onTranscription={(text) => setSettings(prev => ({ ...prev, ideal_customer: prev.ideal_customer ? prev.ideal_customer + ' ' + text : text }))}
                  size="small"
                />
              </View>
            </View>

            {/* Scheduling link */}
            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>Your Scheduling Link</Text>
              <Text style={styles.fieldHint}>Calendly, HubSpot, Google Calendar — wherever customers can book time with you.</Text>
              <TextInput
                style={styles.addInput}
                value={settings.scheduling_link}
                onChangeText={(text) => setSettings(prev => ({ ...prev, scheduling_link: text }))}
                placeholder="https://meetings.hubspot.com/yourname"
                placeholderTextColor={colors.textSecondary}
                keyboardType="url"
                autoCapitalize="none"
              />
            </View>

            {/* Payment link */}
            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>Your Payment Link (optional)</Text>
              <Text style={styles.fieldHint}>Venmo, CashApp, Stripe — wherever customers pay you directly.</Text>
              <TextInput
                style={styles.addInput}
                value={settings.payment_link}
                onChangeText={(text) => setSettings(prev => ({ ...prev, payment_link: text }))}
                placeholder="https://venmo.com/u/yourhandle"
                placeholderTextColor={colors.textSecondary}
                keyboardType="url"
                autoCapitalize="none"
              />
            </View>

            {/* Other key links */}
            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>Other Key Links (optional)</Text>
              <Text style={styles.fieldHint}>Any other URLs Jessi might need — product pages, forms, resources. Separate with commas.</Text>
              <TextInput
                style={[styles.addInput, { minHeight: 80, textAlignVertical: 'top', paddingTop: 12 }]}
                value={settings.key_links}
                onChangeText={(text) => setSettings(prev => ({ ...prev, key_links: text }))}
                placeholder="https://example.com/form, https://example.com/pricing"
                placeholderTextColor={colors.textSecondary}
                multiline
                numberOfLines={3}
                autoCapitalize="none"
              />
            </View>
          </>
        )}

        {/* ═══════ STEP 5: Final Touches ═══════ */}
        {currentStep === 5 && (
          <>
            {/* WHY banner */}
            <View style={styles.whyBanner}>
              <Ionicons name="information-circle" size={20} color="#34C759" />
              <Text style={styles.whyText}>
                Almost done! Set your <Text style={styles.whyHighlight}>greeting, signature, and alert keywords</Text> — then hit Save to activate your full profile.
              </Text>
            </View>

            <Text style={styles.stepTitle}>Final details</Text>
            <Text style={styles.stepSubtitle}>How Jessi opens conversations and what flags your attention.</Text>

            {/* Greeting & Signature */}
            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>Greeting Style</Text>
              <TextInput
                style={styles.input}
                value={settings.greeting_style}
                onChangeText={(text) => setSettings(prev => ({ ...prev, greeting_style: text }))}
                placeholder="Hi {name}!"
                placeholderTextColor={colors.textSecondary}
              />
              <Text style={styles.inputHint}>Use {'{name}'} to insert the contact's name</Text>
            </View>
            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>Signature (optional)</Text>
              <TextInput
                style={styles.input}
                value={settings.signature}
                onChangeText={(text) => setSettings(prev => ({ ...prev, signature: text }))}
                placeholder="- Your Name, Title"
                placeholderTextColor={colors.textSecondary}
              />
            </View>
            <View style={[styles.switchRow, { marginBottom: 24 }]}>
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

            {/* Escalation Keywords */}
            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>Escalation Keywords</Text>
              <Text style={styles.fieldHint}>AI will flag conversations containing these words for your attention</Text>
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

            {/* Final Save */}
            <TouchableOpacity 
              style={[styles.saveButtonLarge, { backgroundColor: '#007AFF', marginBottom: 16, opacity: saving ? 0.6 : 1 }]}
              onPress={handleSave}
              disabled={saving}
              data-testid="save-persona-final"
            >
              {saving ? (
                <ActivityIndicator size="small" color="#FFF" style={{ marginRight: 8 }} />
              ) : (
                <Ionicons name="checkmark-circle" size={20} color="#FFF" style={{ marginRight: 8 }} />
              )}
              <Text style={[styles.saveButtonLargeText, { color: '#FFF' }]}>{saving ? 'Saving...' : 'Save Everything'}</Text>
            </TouchableOpacity>
          </>
        )}

        <View style={{ height: 40 }} />
      </ScrollView>

      {/* Bottom Navigation */}
      <View style={styles.navBar}>
        {currentStep > 1 ? (
          <TouchableOpacity style={styles.navBackBtn} onPress={goBack} data-testid="wizard-back-btn">
            <Ionicons name="chevron-back" size={20} color="#007AFF" />
            <Text style={styles.navBackText}>Back</Text>
          </TouchableOpacity>
        ) : <View style={{ width: 80 }} />}
        <Text style={styles.navDots}>
          {Array.from({ length: TOTAL_STEPS }, (_, i) => i + 1 === currentStep ? '\u25CF' : '\u25CB').join('  ')}
        </Text>
        {currentStep < TOTAL_STEPS ? (
          <TouchableOpacity style={styles.navNextBtn} onPress={goNext} data-testid="wizard-next-btn">
            <Text style={styles.navNextText}>Next</Text>
            <Ionicons name="chevron-forward" size={20} color="#FFF" />
          </TouchableOpacity>
        ) : <View style={{ width: 80 }} />}
      </View>
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
    paddingTop: (Platform.OS === 'ios' ? 82 : 40) + JESSI_BAR_HEIGHT,
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
  previewCard: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginBottom: 24,
  },
  previewLabel: {
    fontSize: 14,
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
    fontSize: 16,
    lineHeight: 20,
  },
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 12,
  },
  sectionDesc: {
    fontSize: 15,
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
    fontSize: 17,
    fontWeight: '600',
    color: colors.text,
    marginTop: 8,
  },
  toneLabelSelected: {
    color: '#007AFF',
  },
  toneDesc: {
    fontSize: 14,
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
    fontSize: 15,
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
    fontSize: 15,
    color: colors.text,
    fontWeight: '600',
  },
  humorLabelSelected: {
    color: '#007AFF',
  },
  humorDesc: {
    fontSize: 13,
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
    fontSize: 15,
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
    fontSize: 16,
    color: colors.textSecondary,
    marginBottom: 8,
  },
  input: {
    backgroundColor: colors.card,
    borderRadius: 10,
    padding: 14,
    fontSize: 18,
    color: colors.text,
  },
  inputHint: {
    fontSize: 14,
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
    fontSize: 17,
    color: colors.text,
    fontWeight: '500',
    flex: 1,
  },
  switchHint: {
    fontSize: 14,
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
    fontSize: 16,
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
    fontSize: 17,
    color: colors.text,
  },
  bioInput: {
    height: 240,
    textAlignVertical: 'top',
    lineHeight: 22,
    paddingTop: 14,
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
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  progressContainer: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: colors.bg,
    borderBottomWidth: 1,
    borderBottomColor: colors.card,
  },
  progressBarTrack: {
    height: 4,
    backgroundColor: colors.card,
    borderRadius: 2,
    overflow: 'hidden',
    marginBottom: 8,
  },
  progressBarFill: {
    height: '100%',
    backgroundColor: '#007AFF',
    borderRadius: 2,
  },
  progressLabel: {
    fontSize: 14,
    color: colors.textSecondary,
    fontWeight: '500',
  },
  stepTitle: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 6,
  },
  stepSubtitle: {
    fontSize: 15,
    color: colors.textSecondary,
    marginBottom: 24,
    lineHeight: 21,
  },
  whyBanner: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    backgroundColor: '#C9A96215',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#C9A96230',
    padding: 14,
    marginBottom: 20,
  },
  whyText: {
    flex: 1,
    fontSize: 14,
    color: colors.textSecondary,
    lineHeight: 20,
  },
  whyHighlight: {
    color: '#C9A962',
    fontWeight: '600',
  },
  fieldGroup: {
    marginBottom: 20,
  },
  fieldLabel: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 8,
  },
  fieldHint: {
    fontSize: 14,
    color: colors.textSecondary,
    marginBottom: 10,
  },
  navBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    paddingBottom: Platform.OS === 'ios' ? 28 : 12,
    backgroundColor: colors.bg,
    borderTopWidth: 1,
    borderTopColor: colors.card,
  },
  navBackBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    width: 80,
  },
  navBackText: {
    fontSize: 17,
    color: '#007AFF',
    fontWeight: '500',
  },
  navDots: {
    fontSize: 14,
    color: colors.textSecondary,
    letterSpacing: 2,
  },
  navNextBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#007AFF',
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 10,
    width: 80,
    justifyContent: 'center',
  },
  navNextText: {
    fontSize: 17,
    color: '#FFF',
    fontWeight: '600',
  },
});
