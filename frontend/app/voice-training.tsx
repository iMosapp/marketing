import React, { useState, useRef, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  Animated,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { Audio } from 'expo-av';
import * as Haptics from 'expo-haptics';
import { useAuthStore } from '../store/authStore';
import { showSimpleAlert } from '../services/alert';
import api from '../services/api';

const IS_WEB = Platform.OS === 'web';

interface ExtractedInfo {
  bio?: string;
  hobbies?: string[];
  interests?: string[];
  specialties?: string[];
  family_info?: string;
  hometown?: string;
  fun_facts?: string[];
  years_experience?: string;
  personal_motto?: string;
}

const PROMPTS = [
  {
    id: 'intro',
    icon: 'person',
    title: 'Tell me about yourself',
    prompt: "Just talk naturally - tell me about who you are, what you do, and what makes you great at your job.",
    examples: ["I'm Forest, I've been selling cars for 15 years...", "I love helping people find their perfect vehicle..."],
  },
  {
    id: 'hobbies',
    icon: 'bicycle',
    title: 'Your hobbies & interests',
    prompt: "What do you like to do outside of work? Any hobbies, sports, or things you're passionate about?",
    examples: ["I ride Harleys on weekends...", "I'm really into fishing and camping..."],
  },
  {
    id: 'family',
    icon: 'people',
    title: 'Family & personal life',
    prompt: "Tell me about your family, pets, or anything personal you'd like customers to know.",
    examples: ["I've got 3 kids who keep me busy...", "My dog Rocky comes to work with me sometimes..."],
  },
  {
    id: 'expertise',
    icon: 'trophy',
    title: 'Your expertise',
    prompt: "What are you really good at? Any specialties or achievements you're proud of?",
    examples: ["I'm the top truck specialist in the region...", "I've won dealer of the year 3 times..."],
  },
];

export default function VoiceTrainingScreen() {
  const router = useRouter();
  const { user } = useAuthStore();
  
  const [currentPromptIndex, setCurrentPromptIndex] = useState(0);
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [extractedInfo, setExtractedInfo] = useState<ExtractedInfo>({});
  const [allTranscripts, setAllTranscripts] = useState<string[]>([]);
  const [showResults, setShowResults] = useState(false);
  const [saving, setSaving] = useState(false);
  
  const recordingRef = useRef<Audio.Recording | null>(null);
  const pulseAnim = useRef(new Animated.Value(1)).current;
  
  // Pulse animation
  React.useEffect(() => {
    if (isRecording) {
      Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, { toValue: 1.2, duration: 500, useNativeDriver: true }),
          Animated.timing(pulseAnim, { toValue: 1, duration: 500, useNativeDriver: true }),
        ])
      ).start();
    } else {
      pulseAnim.setValue(1);
    }
  }, [isRecording]);

  const startRecording = async () => {
    try {
      const { granted } = await Audio.requestPermissionsAsync();
      if (!granted) {
        showSimpleAlert('Permission Required', 'Please allow microphone access to use voice training.');
        return;
      }

      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });

      const recordingOptions = IS_WEB 
        ? {
            ...Audio.RecordingOptionsPresets.HIGH_QUALITY,
            isMeteringEnabled: false,
            web: { mimeType: 'audio/webm;codecs=opus', bitsPerSecond: 128000 },
          }
        : {
            ...Audio.RecordingOptionsPresets.HIGH_QUALITY,
            isMeteringEnabled: true,
          };

      const { recording } = await Audio.Recording.createAsync(recordingOptions);
      recordingRef.current = recording;
      setIsRecording(true);
      setTranscript('');
      
      if (!IS_WEB) {
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
      }
    } catch (error) {
      console.error('Failed to start recording:', error);
      showSimpleAlert('Error', 'Could not start recording. Please try again.');
    }
  };

  const stopRecording = async () => {
    if (!recordingRef.current) return;

    try {
      setIsRecording(false);
      setIsProcessing(true);

      const recording = recordingRef.current;
      recordingRef.current = null;
      
      await recording.stopAndUnloadAsync();
      const uri = recording.getURI();

      if (uri) {
        await processRecording(uri);
      }
    } catch (error) {
      console.error('Failed to stop recording:', error);
      setIsProcessing(false);
    }
  };

  const processRecording = async (audioUri: string) => {
    try {
      // Create form data for transcription
      const formData = new FormData();
      
      if (IS_WEB) {
        const response = await fetch(audioUri);
        const blob = await response.blob();
        formData.append('file', blob, 'recording.webm');
      } else {
        formData.append('file', {
          uri: audioUri,
          type: 'audio/m4a',
          name: 'recording.m4a',
        } as any);
      }
      
      formData.append('user_id', user?._id || '');

      // Transcribe
      const transcribeRes = await api.post('/voice/transcribe', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 30000,
      });

      const text = transcribeRes.data.text || transcribeRes.data.transcription || '';
      
      if (!text) {
        showSimpleAlert('No Speech Detected', "I didn't catch that. Please try again.");
        setIsProcessing(false);
        return;
      }

      setTranscript(text);
      setAllTranscripts(prev => [...prev, text]);

      // Extract structured info using AI
      const extractRes = await api.post('/jessie/extract-profile', {
        user_id: user?._id,
        text: text,
        context: PROMPTS[currentPromptIndex].id,
      }, { timeout: 30000 });

      if (extractRes.data.extracted) {
        setExtractedInfo(prev => ({
          ...prev,
          ...extractRes.data.extracted,
        }));
      }

      if (!IS_WEB) {
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      }
    } catch (error) {
      console.error('Processing failed:', error);
      showSimpleAlert('Error', 'Could not process recording. Please try again.');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleNext = () => {
    if (currentPromptIndex < PROMPTS.length - 1) {
      setCurrentPromptIndex(prev => prev + 1);
      setTranscript('');
    } else {
      setShowResults(true);
    }
  };

  const handleSkip = () => {
    if (currentPromptIndex < PROMPTS.length - 1) {
      setCurrentPromptIndex(prev => prev + 1);
      setTranscript('');
    } else {
      setShowResults(true);
    }
  };

  const handleSaveToProfile = async () => {
    if (!user?._id) return;
    
    setSaving(true);
    try {
      // Get current persona settings
      const currentRes = await api.get(`/users/${user._id}/persona`);
      const current = currentRes.data || {};

      // Merge extracted info with current settings
      const updated = {
        ...current,
        bio: extractedInfo.bio || current.bio,
        hobbies: [...new Set([...(current.hobbies || []), ...(extractedInfo.hobbies || [])])],
        interests: [...new Set([...(current.interests || []), ...(extractedInfo.interests || [])])],
        specialties: [...new Set([...(current.specialties || []), ...(extractedInfo.specialties || [])])],
        family_info: extractedInfo.family_info || current.family_info,
        hometown: extractedInfo.hometown || current.hometown,
        fun_facts: [...new Set([...(current.fun_facts || []), ...(extractedInfo.fun_facts || [])])],
        years_experience: extractedInfo.years_experience || current.years_experience,
        personal_motto: extractedInfo.personal_motto || current.personal_motto,
      };

      // Save to backend
      await api.put(`/users/${user._id}/persona`, updated);

      if (!IS_WEB) {
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      }
      
      showSimpleAlert('Saved!', 'Your AI has been trained with your voice input.');
      router.back();
    } catch (error) {
      console.error('Save failed:', error);
      showSimpleAlert('Error', 'Could not save. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const currentPrompt = PROMPTS[currentPromptIndex];

  if (showResults) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
            <Ionicons name="chevron-back" size={28} color="#007AFF" />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Training Complete</Text>
          <View style={{ width: 28 }} />
        </View>

        <ScrollView style={styles.resultsScroll} contentContainerStyle={styles.resultsContent}>
          <View style={styles.successIcon}>
            <Ionicons name="checkmark-circle" size={80} color="#34C759" />
          </View>
          
          <Text style={styles.successTitle}>Great job!</Text>
          <Text style={styles.successSubtitle}>
            Here's what I learned about you:
          </Text>

          {extractedInfo.bio && (
            <View style={styles.resultCard}>
              <View style={styles.resultHeader}>
                <Ionicons name="person" size={20} color="#007AFF" />
                <Text style={styles.resultLabel}>Bio</Text>
              </View>
              <Text style={styles.resultValue}>{extractedInfo.bio}</Text>
            </View>
          )}

          {extractedInfo.hobbies && extractedInfo.hobbies.length > 0 && (
            <View style={styles.resultCard}>
              <View style={styles.resultHeader}>
                <Ionicons name="bicycle" size={20} color="#FF9500" />
                <Text style={styles.resultLabel}>Hobbies</Text>
              </View>
              <View style={styles.tagsContainer}>
                {extractedInfo.hobbies.map((hobby, i) => (
                  <View key={i} style={styles.tag}>
                    <Text style={styles.tagText}>{hobby}</Text>
                  </View>
                ))}
              </View>
            </View>
          )}

          {extractedInfo.interests && extractedInfo.interests.length > 0 && (
            <View style={styles.resultCard}>
              <View style={styles.resultHeader}>
                <Ionicons name="heart" size={20} color="#FF2D55" />
                <Text style={styles.resultLabel}>Interests</Text>
              </View>
              <View style={styles.tagsContainer}>
                {extractedInfo.interests.map((interest, i) => (
                  <View key={i} style={styles.tag}>
                    <Text style={styles.tagText}>{interest}</Text>
                  </View>
                ))}
              </View>
            </View>
          )}

          {extractedInfo.specialties && extractedInfo.specialties.length > 0 && (
            <View style={styles.resultCard}>
              <View style={styles.resultHeader}>
                <Ionicons name="trophy" size={20} color="#C9A962" />
                <Text style={styles.resultLabel}>Specialties</Text>
              </View>
              <View style={styles.tagsContainer}>
                {extractedInfo.specialties.map((specialty, i) => (
                  <View key={i} style={styles.tag}>
                    <Text style={styles.tagText}>{specialty}</Text>
                  </View>
                ))}
              </View>
            </View>
          )}

          {extractedInfo.family_info && (
            <View style={styles.resultCard}>
              <View style={styles.resultHeader}>
                <Ionicons name="people" size={20} color="#5856D6" />
                <Text style={styles.resultLabel}>Family</Text>
              </View>
              <Text style={styles.resultValue}>{extractedInfo.family_info}</Text>
            </View>
          )}

          {extractedInfo.fun_facts && extractedInfo.fun_facts.length > 0 && (
            <View style={styles.resultCard}>
              <View style={styles.resultHeader}>
                <Ionicons name="sparkles" size={20} color="#34C759" />
                <Text style={styles.resultLabel}>Fun Facts</Text>
              </View>
              {extractedInfo.fun_facts.map((fact, i) => (
                <Text key={i} style={styles.funFact}>• {fact}</Text>
              ))}
            </View>
          )}

          <TouchableOpacity 
            style={styles.saveButton}
            onPress={handleSaveToProfile}
            disabled={saving}
          >
            {saving ? (
              <ActivityIndicator color="#000" />
            ) : (
              <>
                <Ionicons name="checkmark" size={24} color="#000" />
                <Text style={styles.saveButtonText}>Save to My AI Profile</Text>
              </>
            )}
          </TouchableOpacity>

          <TouchableOpacity 
            style={styles.skipButton}
            onPress={() => router.back()}
          >
            <Text style={styles.skipButtonText}>Maybe later</Text>
          </TouchableOpacity>
        </ScrollView>
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
        <Text style={styles.headerTitle}>Train Your AI</Text>
        <View style={{ width: 28 }} />
      </View>

      {/* Progress */}
      <View style={styles.progressContainer}>
        {PROMPTS.map((_, i) => (
          <View 
            key={i} 
            style={[
              styles.progressDot,
              i === currentPromptIndex && styles.progressDotActive,
              i < currentPromptIndex && styles.progressDotComplete,
            ]} 
          />
        ))}
      </View>

      {/* Main Content */}
      <View style={styles.content}>
        {/* Prompt Card */}
        <View style={styles.promptCard}>
          <View style={[styles.promptIcon, { backgroundColor: '#007AFF20' }]}>
            <Ionicons name={currentPrompt.icon as any} size={32} color="#007AFF" />
          </View>
          <Text style={styles.promptTitle}>{currentPrompt.title}</Text>
          <Text style={styles.promptText}>{currentPrompt.prompt}</Text>
          
          <View style={styles.examplesContainer}>
            <Text style={styles.examplesLabel}>Examples:</Text>
            {currentPrompt.examples.map((ex, i) => (
              <Text key={i} style={styles.exampleText}>"{ex}"</Text>
            ))}
          </View>
        </View>

        {/* Transcript */}
        {transcript && (
          <View style={styles.transcriptCard}>
            <Ionicons name="chatbubble-ellipses" size={18} color="#34C759" />
            <Text style={styles.transcriptText}>{transcript}</Text>
          </View>
        )}

        {/* Recording Button */}
        <View style={styles.recordingContainer}>
          {isProcessing ? (
            <View style={styles.processingContainer}>
              <ActivityIndicator size="large" color="#007AFF" />
              <Text style={styles.processingText}>Listening and learning...</Text>
            </View>
          ) : (
            <>
              <Animated.View style={{ transform: [{ scale: pulseAnim }] }}>
                <TouchableOpacity
                  style={[
                    styles.recordButton,
                    isRecording && styles.recordButtonActive,
                  ]}
                  onPress={isRecording ? stopRecording : startRecording}
                >
                  <Ionicons 
                    name={isRecording ? 'stop' : 'mic'} 
                    size={40} 
                    color="#FFF" 
                  />
                </TouchableOpacity>
              </Animated.View>
              <Text style={styles.recordHint}>
                {isRecording ? 'Tap to stop recording' : 'Tap to start talking'}
              </Text>
            </>
          )}
        </View>

        {/* Action Buttons */}
        {transcript && !isProcessing && (
          <View style={styles.actionButtons}>
            <TouchableOpacity style={styles.nextButton} onPress={handleNext}>
              <Text style={styles.nextButtonText}>
                {currentPromptIndex < PROMPTS.length - 1 ? 'Next Question' : 'See Results'}
              </Text>
              <Ionicons name="arrow-forward" size={20} color="#FFF" />
            </TouchableOpacity>
          </View>
        )}

        {!transcript && !isRecording && !isProcessing && (
          <TouchableOpacity style={styles.skipLink} onPress={handleSkip}>
            <Text style={styles.skipLinkText}>Skip this question</Text>
          </TouchableOpacity>
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#1C1C1E',
  },
  backButton: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFF',
  },
  progressContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 16,
  },
  progressDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: '#3A3A3C',
  },
  progressDotActive: {
    backgroundColor: '#007AFF',
    width: 24,
  },
  progressDotComplete: {
    backgroundColor: '#34C759',
  },
  content: {
    flex: 1,
    padding: 20,
  },
  promptCard: {
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    padding: 24,
    alignItems: 'center',
  },
  promptIcon: {
    width: 64,
    height: 64,
    borderRadius: 32,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  promptTitle: {
    fontSize: 22,
    fontWeight: '700',
    color: '#FFF',
    marginBottom: 8,
    textAlign: 'center',
  },
  promptText: {
    fontSize: 16,
    color: '#8E8E93',
    textAlign: 'center',
    lineHeight: 24,
  },
  examplesContainer: {
    marginTop: 20,
    width: '100%',
  },
  examplesLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: '#6E6E73',
    textTransform: 'uppercase',
    marginBottom: 8,
  },
  exampleText: {
    fontSize: 14,
    color: '#8E8E93',
    fontStyle: 'italic',
    marginBottom: 4,
  },
  transcriptCard: {
    flexDirection: 'row',
    backgroundColor: '#34C75920',
    borderRadius: 12,
    padding: 16,
    marginTop: 16,
    gap: 12,
    alignItems: 'flex-start',
  },
  transcriptText: {
    flex: 1,
    fontSize: 15,
    color: '#FFF',
    lineHeight: 22,
  },
  recordingContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 40,
  },
  recordButton: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: '#007AFF',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#007AFF',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.5,
    shadowRadius: 20,
  },
  recordButtonActive: {
    backgroundColor: '#FF3B30',
    shadowColor: '#FF3B30',
  },
  recordHint: {
    fontSize: 14,
    color: '#8E8E93',
    marginTop: 16,
  },
  processingContainer: {
    alignItems: 'center',
    gap: 16,
  },
  processingText: {
    fontSize: 16,
    color: '#007AFF',
    fontWeight: '500',
  },
  actionButtons: {
    marginTop: 20,
  },
  nextButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#007AFF',
    padding: 16,
    borderRadius: 12,
    gap: 8,
  },
  nextButtonText: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  skipLink: {
    alignItems: 'center',
    marginTop: 20,
  },
  skipLinkText: {
    fontSize: 15,
    color: '#8E8E93',
  },
  // Results Screen
  resultsScroll: {
    flex: 1,
  },
  resultsContent: {
    padding: 20,
    paddingBottom: 40,
  },
  successIcon: {
    alignItems: 'center',
    marginBottom: 16,
  },
  successTitle: {
    fontSize: 28,
    fontWeight: '700',
    color: '#FFF',
    textAlign: 'center',
    marginBottom: 8,
  },
  successSubtitle: {
    fontSize: 16,
    color: '#8E8E93',
    textAlign: 'center',
    marginBottom: 24,
  },
  resultCard: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
  },
  resultHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 10,
  },
  resultLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: '#8E8E93',
    textTransform: 'uppercase',
  },
  resultValue: {
    fontSize: 15,
    color: '#FFF',
    lineHeight: 22,
  },
  tagsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  tag: {
    backgroundColor: '#2C2C2E',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
  },
  tagText: {
    fontSize: 14,
    color: '#FFF',
  },
  funFact: {
    fontSize: 15,
    color: '#FFF',
    lineHeight: 22,
    marginBottom: 4,
  },
  saveButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#34C759',
    padding: 18,
    borderRadius: 12,
    gap: 10,
    marginTop: 24,
  },
  saveButtonText: {
    fontSize: 17,
    fontWeight: '600',
    color: '#000',
  },
  skipButton: {
    alignItems: 'center',
    marginTop: 16,
    padding: 12,
  },
  skipButtonText: {
    fontSize: 15,
    color: '#8E8E93',
  },
});
