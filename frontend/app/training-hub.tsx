import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { Audio } from 'expo-av';
import { useAuthStore } from '../store/authStore';
import api from '../services/api';
import { showSimpleAlert } from '../services/alert';

const IS_WEB = Platform.OS === 'web';

interface TrainingTopic {
  id: string;
  icon: string;
  iconColor: string;
  title: string;
  description: string;
  duration?: string;
  category: string;
  route?: string;
  content?: string;
}

const TRAINING_TOPICS: TrainingTopic[] = [
  // Getting Started
  {
    id: 'getting-started',
    icon: 'rocket',
    iconColor: '#FF9500',
    title: 'Getting Started with iMos',
    description: 'Learn the basics and set up your account',
    duration: '5 min',
    category: 'Getting Started',
    content: 'Welcome to iMos! This guide will walk you through setting up your profile, understanding the main features, and making your first connection with a customer.',
  },
  {
    id: 'profile-setup',
    icon: 'person-circle',
    iconColor: '#5856D6',
    title: 'Setting Up Your Profile',
    description: 'Create your digital business card',
    duration: '3 min',
    category: 'Getting Started',
    route: '/settings/my-profile',
    content: 'Your digital card is your first impression. Add a professional photo, write a compelling bio, and link your social media to make it easy for customers to connect with you.',
  },
  // Messaging
  {
    id: 'inbox-basics',
    icon: 'mail',
    iconColor: '#007AFF',
    title: 'Inbox & Conversations',
    description: 'Manage customer messages like a pro',
    duration: '4 min',
    category: 'Messaging',
    content: 'The inbox is your command center. Learn to switch between SMS and email modes, use AI suggestions, and manage multiple conversations efficiently.',
  },
  {
    id: 'templates',
    icon: 'document-text',
    iconColor: '#34C759',
    title: 'Using Message Templates',
    description: 'Save time with pre-written messages',
    duration: '3 min',
    category: 'Messaging',
    route: '/settings/templates',
    content: 'Templates let you respond faster with consistent, professional messages. Create templates for common scenarios like follow-ups, greetings, and appointment confirmations.',
  },
  {
    id: 'voice-to-text',
    icon: 'mic',
    iconColor: '#FF3B30',
    title: 'Voice-to-Text Messaging',
    description: 'Speak your messages instead of typing',
    duration: '2 min',
    category: 'Messaging',
    content: 'Tap the microphone icon in any message compose area to speak your message. The AI will transcribe it accurately, saving you time on long messages.',
  },
  // AI Features
  {
    id: 'jessi-ai',
    icon: 'sparkles',
    iconColor: '#C9A962',
    title: 'Using Jessi AI Assistant',
    description: 'Get AI help for any task',
    duration: '5 min',
    category: 'AI Features',
    route: '/jessie',
    content: 'Jessi is your personal AI assistant. Ask questions, get help drafting messages, or let Jessi suggest responses to customers based on conversation context.',
  },
  {
    id: 'ai-suggestions',
    icon: 'bulb',
    iconColor: '#FFD60A',
    title: 'AI Message Suggestions',
    description: 'Let AI help craft perfect responses',
    duration: '3 min',
    category: 'AI Features',
    content: 'When viewing a conversation, watch for the AI suggestion bar. It analyzes the conversation and suggests contextually appropriate responses you can use or modify.',
  },
  {
    id: 'voice-training',
    icon: 'recording',
    iconColor: '#AF52DE',
    title: 'Voice Training Your AI',
    description: 'Train AI to sound like you',
    duration: '5 min',
    category: 'AI Features',
    route: '/voice-training',
    content: 'The AI learns your personality through voice training. Just talk naturally about yourself, and the AI will adapt to match your communication style.',
  },
  // Sales Tools
  {
    id: 'congrats-cards',
    icon: 'gift',
    iconColor: '#FF2D55',
    title: 'Congrats Cards',
    description: 'Celebrate customer purchases',
    duration: '3 min',
    category: 'Sales Tools',
    content: 'After a sale, send a beautiful congrats card with the customer\'s photo. They can download it, share on social media, and leave reviews - all from one link!',
  },
  {
    id: 'review-links',
    icon: 'star',
    iconColor: '#FFD60A',
    title: 'Getting Customer Reviews',
    description: 'Build your reputation with reviews',
    duration: '3 min',
    category: 'Sales Tools',
    route: '/settings/review-links',
    content: 'Set up your review links to make it easy for satisfied customers to leave reviews on Google, Facebook, or other platforms.',
  },
  {
    id: 'lead-management',
    icon: 'funnel',
    iconColor: '#5AC8FA',
    title: 'Managing Leads',
    description: 'Track and convert leads effectively',
    duration: '5 min',
    category: 'Sales Tools',
    content: 'Learn how to tag leads, set follow-up reminders, and use the lead routing system to never miss an opportunity.',
  },
  // Campaigns
  {
    id: 'sms-campaigns',
    icon: 'chatbubbles',
    iconColor: '#FF9500',
    title: 'SMS Campaigns',
    description: 'Automated text follow-ups',
    duration: '4 min',
    category: 'Campaigns',
    route: '/campaigns',
    content: 'Set up automated SMS campaigns to nurture leads over time. Schedule messages, add personalization, and track engagement.',
  },
  {
    id: 'email-campaigns',
    icon: 'mail-unread',
    iconColor: '#AF52DE',
    title: 'Email Campaigns',
    description: 'Professional email sequences',
    duration: '4 min',
    category: 'Campaigns',
    route: '/campaigns/email',
    content: 'Create branded email campaigns with your logo and colors. Perfect for longer-form content and professional follow-ups.',
  },
  // Team Features
  {
    id: 'team-chat',
    icon: 'people',
    iconColor: '#34C759',
    title: 'Team Communication',
    description: 'Chat with your team internally',
    duration: '3 min',
    category: 'Team Features',
    route: '/team',
    content: 'Use the Team tab for internal communication. Create channels for different topics, mention team members, and keep customer info separate from team discussions.',
  },
];

export default function TrainingHubScreen() {
  const router = useRouter();
  const { user } = useAuthStore();
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedTopic, setExpandedTopic] = useState<string | null>(null);
  const [askingQuestion, setAskingQuestion] = useState(false);
  const [voiceQuestion, setVoiceQuestion] = useState('');
  const [aiResponse, setAiResponse] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  const recordingRef = React.useRef<Audio.Recording | null>(null);

  // Filter topics by search
  const filteredTopics = searchQuery
    ? TRAINING_TOPICS.filter(t => 
        t.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        t.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
        t.category.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : TRAINING_TOPICS;

  // Group by category
  const groupedTopics = filteredTopics.reduce((acc, topic) => {
    if (!acc[topic.category]) acc[topic.category] = [];
    acc[topic.category].push(topic);
    return acc;
  }, {} as Record<string, TrainingTopic[]>);

  const handleTopicPress = (topic: TrainingTopic) => {
    if (topic.route) {
      router.push(topic.route as any);
    } else {
      setExpandedTopic(expandedTopic === topic.id ? null : topic.id);
    }
  };

  const startVoiceQuestion = async () => {
    try {
      const { granted } = await Audio.requestPermissionsAsync();
      if (!granted) {
        showSimpleAlert('Permission Required', 'Please allow microphone access');
        return;
      }

      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });

      const { recording } = await Audio.Recording.createAsync(
        Audio.RecordingOptionsPresets.HIGH_QUALITY
      );
      recordingRef.current = recording;
      setIsRecording(true);
    } catch (error) {
      console.error('Recording error:', error);
    }
  };

  const stopVoiceQuestion = async () => {
    if (!recordingRef.current) return;

    setIsRecording(false);
    setProcessing(true);

    try {
      const recording = recordingRef.current;
      recordingRef.current = null;
      
      await recording.stopAndUnloadAsync();
      const uri = recording.getURI();

      if (uri) {
        // Transcribe
        const formData = new FormData();
        if (IS_WEB) {
          const response = await fetch(uri);
          const blob = await response.blob();
          formData.append('file', blob, 'question.webm');
        } else {
          formData.append('file', { uri, type: 'audio/m4a', name: 'question.m4a' } as any);
        }
        formData.append('user_id', user?._id || '');

        const transcribeRes = await api.post('/voice/transcribe', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
          timeout: 30000,
        });

        const question = transcribeRes.data.text || transcribeRes.data.transcription || '';
        if (question) {
          setVoiceQuestion(question);
          await getAIHelp(question);
        }
      }
    } catch (error) {
      console.error('Error processing voice:', error);
      showSimpleAlert('Error', 'Could not process your question');
    } finally {
      setProcessing(false);
    }
  };

  const getAIHelp = async (question: string) => {
    setProcessing(true);
    try {
      const response = await api.post('/jessie/chat', {
        user_id: user?._id,
        message: `The user is asking for help with iMos CRM. Here's their question: "${question}"\n\nPlease provide a helpful, concise answer explaining how to accomplish this in iMos. If it involves a specific feature, mention where to find it in the app.`,
        context: 'training_help',
      }, { timeout: 30000 });

      setAiResponse(response.data.response || response.data.message || 'Let me help you with that...');
    } catch (error) {
      console.error('AI help error:', error);
      setAiResponse('Sorry, I had trouble processing that. Try asking in a different way.');
    } finally {
      setProcessing(false);
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Training Hub</Text>
        <View style={{ width: 28 }} />
      </View>

      <ScrollView style={styles.content} contentContainerStyle={styles.scrollContent}>
        {/* Voice Help Section */}
        <View style={styles.voiceHelpSection}>
          <View style={styles.voiceHelpHeader}>
            <Ionicons name="help-circle" size={28} color="#C9A962" />
            <View style={styles.voiceHelpText}>
              <Text style={styles.voiceHelpTitle}>Need Help?</Text>
              <Text style={styles.voiceHelpSubtitle}>Ask anything about iMos by voice or text</Text>
            </View>
          </View>
          
          <View style={styles.askContainer}>
            <TextInput
              style={styles.askInput}
              placeholder="Type your question..."
              placeholderTextColor="#6E6E73"
              value={voiceQuestion}
              onChangeText={setVoiceQuestion}
              multiline
            />
            <View style={styles.askButtons}>
              <TouchableOpacity
                style={[styles.voiceButton, isRecording && styles.voiceButtonActive]}
                onPress={isRecording ? stopVoiceQuestion : startVoiceQuestion}
                disabled={processing}
              >
                <Ionicons 
                  name={isRecording ? 'stop' : 'mic'} 
                  size={24} 
                  color="#FFF" 
                />
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.askButton, !voiceQuestion.trim() && styles.askButtonDisabled]}
                onPress={() => voiceQuestion.trim() && getAIHelp(voiceQuestion)}
                disabled={!voiceQuestion.trim() || processing}
              >
                {processing ? (
                  <ActivityIndicator size="small" color="#FFF" />
                ) : (
                  <Ionicons name="arrow-forward" size={20} color="#FFF" />
                )}
              </TouchableOpacity>
            </View>
          </View>

          {/* AI Response */}
          {aiResponse && (
            <View style={styles.aiResponseContainer}>
              <View style={styles.aiResponseHeader}>
                <Ionicons name="sparkles" size={18} color="#C9A962" />
                <Text style={styles.aiResponseLabel}>Jessi's Answer</Text>
              </View>
              <Text style={styles.aiResponseText}>{aiResponse}</Text>
              <TouchableOpacity 
                style={styles.clearButton}
                onPress={() => { setAiResponse(''); setVoiceQuestion(''); }}
              >
                <Ionicons name="close-circle" size={16} color="#8E8E93" />
                <Text style={styles.clearButtonText}>Clear</Text>
              </TouchableOpacity>
            </View>
          )}
        </View>

        {/* Search */}
        <View style={styles.searchContainer}>
          <Ionicons name="search" size={20} color="#8E8E93" />
          <TextInput
            style={styles.searchInput}
            placeholder="Search training topics..."
            placeholderTextColor="#6E6E73"
            value={searchQuery}
            onChangeText={setSearchQuery}
          />
          {searchQuery && (
            <TouchableOpacity onPress={() => setSearchQuery('')}>
              <Ionicons name="close-circle" size={20} color="#8E8E93" />
            </TouchableOpacity>
          )}
        </View>

        {/* Topics */}
        {Object.entries(groupedTopics).map(([category, topics]) => (
          <View key={category} style={styles.categorySection}>
            <Text style={styles.categoryTitle}>{category}</Text>
            {topics.map(topic => (
              <TouchableOpacity
                key={topic.id}
                style={styles.topicCard}
                onPress={() => handleTopicPress(topic)}
                activeOpacity={0.7}
              >
                <View style={[styles.topicIcon, { backgroundColor: `${topic.iconColor}20` }]}>
                  <Ionicons 
                    name={topic.icon as any} 
                    size={24} 
                    color={topic.iconColor} 
                  />
                </View>
                <View style={styles.topicContent}>
                  <Text style={styles.topicTitle}>{topic.title}</Text>
                  <Text style={styles.topicDescription}>{topic.description}</Text>
                  {expandedTopic === topic.id && topic.content && (
                    <View style={styles.expandedContent}>
                      <Text style={styles.expandedText}>{topic.content}</Text>
                    </View>
                  )}
                </View>
                <View style={styles.topicMeta}>
                  {topic.duration && (
                    <Text style={styles.topicDuration}>{topic.duration}</Text>
                  )}
                  <Ionicons 
                    name={topic.route ? 'chevron-forward' : (expandedTopic === topic.id ? 'chevron-up' : 'chevron-down')} 
                    size={18} 
                    color="#8E8E93" 
                  />
                </View>
              </TouchableOpacity>
            ))}
          </View>
        ))}

        <View style={{ height: 40 }} />
      </ScrollView>
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
  content: {
    flex: 1,
  },
  scrollContent: {
    padding: 16,
  },
  voiceHelpSection: {
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    padding: 20,
    marginBottom: 20,
  },
  voiceHelpHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginBottom: 16,
  },
  voiceHelpText: {
    flex: 1,
  },
  voiceHelpTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#FFF',
  },
  voiceHelpSubtitle: {
    fontSize: 13,
    color: '#8E8E93',
    marginTop: 2,
  },
  askContainer: {
    flexDirection: 'row',
    gap: 12,
    alignItems: 'flex-end',
  },
  askInput: {
    flex: 1,
    backgroundColor: '#2C2C2E',
    borderRadius: 12,
    padding: 14,
    color: '#FFF',
    fontSize: 15,
    minHeight: 48,
    maxHeight: 100,
  },
  askButtons: {
    flexDirection: 'row',
    gap: 8,
  },
  voiceButton: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: '#007AFF',
    alignItems: 'center',
    justifyContent: 'center',
  },
  voiceButtonActive: {
    backgroundColor: '#FF3B30',
  },
  askButton: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: '#34C759',
    alignItems: 'center',
    justifyContent: 'center',
  },
  askButtonDisabled: {
    backgroundColor: '#3A3A3C',
  },
  aiResponseContainer: {
    marginTop: 16,
    backgroundColor: '#2C2C2E',
    borderRadius: 12,
    padding: 16,
  },
  aiResponseHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 10,
  },
  aiResponseLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: '#C9A962',
  },
  aiResponseText: {
    fontSize: 15,
    color: '#FFF',
    lineHeight: 22,
  },
  clearButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: 12,
  },
  clearButtonText: {
    fontSize: 13,
    color: '#8E8E93',
  },
  searchContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    gap: 10,
    marginBottom: 20,
  },
  searchInput: {
    flex: 1,
    fontSize: 16,
    color: '#FFF',
  },
  categorySection: {
    marginBottom: 24,
  },
  categoryTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#8E8E93',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 12,
  },
  topicCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginBottom: 10,
    gap: 14,
  },
  topicIcon: {
    width: 48,
    height: 48,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  topicContent: {
    flex: 1,
  },
  topicTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 4,
  },
  topicDescription: {
    fontSize: 13,
    color: '#8E8E93',
  },
  topicMeta: {
    alignItems: 'flex-end',
    gap: 4,
  },
  topicDuration: {
    fontSize: 12,
    color: '#6E6E73',
  },
  expandedContent: {
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#2C2C2E',
  },
  expandedText: {
    fontSize: 14,
    color: '#FFF',
    lineHeight: 22,
  },
});
