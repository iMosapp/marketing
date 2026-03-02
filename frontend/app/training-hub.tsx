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
  Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { Audio } from 'expo-av';
import { useAuthStore } from '../store/authStore';
import { useThemeStore } from '../store/themeStore';
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
  videoUrl?: string;
  steps?: string[];
}

const TRAINING_TOPICS: TrainingTopic[] = [
  // Getting Started
  {
    id: 'getting-started',
    icon: 'rocket',
    iconColor: '#FF9500',
    title: 'Getting Started with iMOs',
    description: 'Learn the basics and set up your account',
    duration: '5 min',
    category: 'Getting Started',
    videoUrl: '',
    content: 'Welcome to iMOs! This guide will walk you through setting up your profile, understanding the main features, and making your first connection with a customer.',
    steps: [
      'Log in to your iMOs account using the credentials provided by your admin.',
      'Complete your profile by adding your photo, bio, and contact information.',
      'Explore the four main tabs: Inbox, Contacts, Keypad, and More.',
      'Send your first message to a customer from the Contacts tab.',
    ],
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
    videoUrl: '',
    content: 'Your digital card is your first impression. Add a professional photo, write a compelling bio, and link your social media to make it easy for customers to connect with you.',
    steps: [
      'Go to More > My Digital Card.',
      'Upload a professional headshot photo.',
      'Write a short bio that highlights your experience.',
      'Add your social media links and review page URLs.',
      'Share your card link in your email signature.',
    ],
  },
  {
    id: 'adding-contacts',
    icon: 'people',
    iconColor: '#34C759',
    title: 'Adding & Managing Contacts',
    description: 'Build your customer database from day one',
    duration: '4 min',
    category: 'Getting Started',
    videoUrl: '',
    content: 'Your contacts are the heart of iMOs. Learn how to add contacts manually, import from CSV, and organize them with tags for targeted follow-ups.',
    steps: [
      'Tap the + button on the Contacts tab to add a new contact.',
      'Fill in their name, phone, and email.',
      'Use the Import feature to bulk-upload contacts from a CSV file.',
      'Add tags like "VIP", "Hot Lead", or "Service Due" to organize contacts.',
    ],
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
    videoUrl: '',
    content: 'The inbox is your command center. Learn to send SMS and email, use AI suggestions, and manage multiple conversations efficiently.',
    steps: [
      'Open the Inbox tab to see all your conversations.',
      'Tap any conversation to view the full thread.',
      'Use the compose bar at the bottom to type and send messages.',
      'Toggle between SMS and Email modes using the icons.',
      'Look for AI outcome badges (Hot Lead, Appt Set) to prioritize.',
    ],
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
    videoUrl: '',
    content: 'Templates let you respond faster with consistent, professional messages. Create templates for common scenarios like follow-ups, greetings, and appointment confirmations.',
    steps: [
      'Go to More > Message Templates to create templates.',
      'Use variables like {first_name} for personalization.',
      'In any conversation, tap the template icon to insert one.',
      'Create templates for: greetings, follow-ups, appointment confirmations, and thank-you messages.',
    ],
  },
  {
    id: 'voice-to-text',
    icon: 'mic',
    iconColor: '#FF3B30',
    title: 'Voice-to-Text Messaging',
    description: 'Speak your messages instead of typing',
    duration: '2 min',
    category: 'Messaging',
    videoUrl: '',
    content: 'Tap the microphone icon in any message compose area to speak your message. The AI will transcribe it accurately, saving you time on long messages.',
    steps: [
      'Open any conversation thread.',
      'Tap and hold the microphone icon to start recording.',
      'Speak your message naturally.',
      'Release to stop recording - AI transcribes it instantly.',
      'Review and edit before hitting send.',
    ],
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
    videoUrl: '',
    content: 'Jessi is your personal AI assistant. Ask questions, get help drafting messages, or let Jessi suggest responses to customers based on conversation context.',
    steps: [
      'Go to More > Ask Jessi to open the AI assistant.',
      'Type or speak your question about any iMOs feature.',
      'Ask Jessi to draft messages for specific customer situations.',
      'Use Jessi to get tips on sales techniques and follow-up strategies.',
    ],
  },
  {
    id: 'ai-suggestions',
    icon: 'bulb',
    iconColor: '#FFD60A',
    title: 'AI Message Suggestions',
    description: 'Let AI help craft perfect responses',
    duration: '3 min',
    category: 'AI Features',
    videoUrl: '',
    content: 'When viewing a conversation, watch for the AI suggestion bar. It analyzes the conversation and suggests contextually appropriate responses you can use or modify.',
    steps: [
      'Open any conversation to see AI-powered suggestions.',
      'Tap the magic wand icon for response suggestions.',
      'AI considers the full conversation context to suggest responses.',
      'Edit the suggestion to add your personal touch before sending.',
    ],
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
    videoUrl: '',
    content: 'The AI learns your personality through voice training. Just talk naturally about yourself, and the AI will adapt to match your communication style.',
    steps: [
      'Go to More > Voice Training to start.',
      'Record yourself talking naturally about your work and personality.',
      'The AI analyzes your speaking style, vocabulary, and tone.',
      'Future AI suggestions will match how you actually communicate.',
    ],
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
    videoUrl: '',
    content: "After a sale, send a beautiful congrats card with the customer's photo. They can download it, share on social media, and leave reviews - all from one link!",
    steps: [
      'Open a customer conversation after a sale.',
      'Tap the gift/card icon to create a Congrats Card.',
      "Add the customer's photo (take one with them!).",
      'Customize your message and send it.',
      'The customer gets a shareable card they can post on social media.',
    ],
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
    videoUrl: '',
    content: 'Set up your review links to make it easy for satisfied customers to leave reviews on Google, Facebook, or other platforms.',
    steps: [
      'Go to More > Review Links to configure your review pages.',
      'Add your Google Business, Facebook, and other review URLs.',
      'After every positive interaction, share your review link.',
      'Congrats Cards automatically include a review prompt.',
    ],
  },
  {
    id: 'lead-management',
    icon: 'funnel',
    iconColor: '#5AC8FA',
    title: 'Managing Leads',
    description: 'Track and convert leads effectively',
    duration: '5 min',
    category: 'Sales Tools',
    videoUrl: '',
    content: 'Learn how to tag leads, set follow-up reminders, and use the lead routing system to never miss an opportunity.',
    steps: [
      'New leads appear in your Inbox with a "New Lead" badge.',
      'Respond within 5 minutes for the best conversion rate.',
      'Tag leads appropriately: Hot Lead, Warm, Appointment Set, etc.',
      'Set a follow-up task if you can\'t close immediately.',
      'Use Nurture Campaigns to automate long-term follow-ups.',
    ],
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
    videoUrl: '',
    content: 'Set up automated SMS campaigns to nurture leads over time. Schedule messages, add personalization, and track engagement.',
    steps: [
      'Go to Campaigns from the More menu.',
      'Tap "Create Campaign" and choose SMS type.',
      'Write your message sequence (e.g., Day 1, Day 3, Day 7).',
      'Set the trigger (tag-based, date-based, or manual enrollment).',
      'Activate and monitor from the Campaign Dashboard.',
    ],
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
    videoUrl: '',
    content: 'Create branded email campaigns with your logo and colors. Perfect for longer-form content and professional follow-ups.',
    steps: [
      'Go to Campaigns > Email Campaigns.',
      'Choose a template or start from scratch.',
      'Add your content, images, and personalization variables.',
      'Set the sending schedule and target audience.',
      'Preview and activate the campaign.',
    ],
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
    videoUrl: '',
    content: 'Use the Team tab for internal communication. Create channels for different topics, mention team members, and keep customer info separate from team discussions.',
    steps: [
      'Open the Team tab from the bottom navigation.',
      'Browse existing channels or create a new one.',
      'Use channels for topics like "Deals", "Questions", "Announcements".',
      'Tag team members with @ mentions for direct attention.',
    ],
  },
  {
    id: 'admin-panel',
    icon: 'shield-checkmark',
    iconColor: '#5856D6',
    title: 'Admin Panel Overview',
    description: 'For managers: manage your team and reports',
    duration: '5 min',
    category: 'Team Features',
    route: '/admin',
    videoUrl: '',
    content: 'The Admin Panel gives managers tools to oversee their team, view performance metrics, approve users, and manage organizational settings.',
    steps: [
      'Go to More > Admin Panel.',
      'View the dashboard for key metrics and recent activity.',
      'Manage team members: add, edit roles, or deactivate accounts.',
      'Check Leaderboards to track team performance.',
      'Access Training & SOPs to manage internal documentation.',
    ],
  },
];

// Video embed component for web
const VideoEmbed = ({ url }: { url: string }) => {
  // Empty URL - show "coming soon" placeholder
  if (!url) {
    return (
      <View style={styles.videoPlaceholder}>
        <View style={[styles.playButton, { backgroundColor: '#3A3A3C' }]}>
          <Ionicons name="videocam" size={28} color="#8E8E93" />
        </View>
        <Text style={styles.videoPlaceholderText}>Training video coming soon</Text>
      </View>
    );
  }

  if (!IS_WEB) {
    return (
      <TouchableOpacity
        style={styles.videoPlaceholder}
        onPress={() => Linking.openURL(url.replace('/embed/', '/watch?v='))}
      >
        <View style={styles.playButton}>
          <Ionicons name="play" size={32} color="#FFF" />
        </View>
        <Text style={styles.videoPlaceholderText}>Tap to watch video</Text>
      </TouchableOpacity>
    );
  }

  return (
    <View style={styles.videoContainer}>
      <iframe
        src={url}
        style={{ width: '100%', height: '100%', border: 'none', borderRadius: 12 } as any}
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowFullScreen
      />
    </View>
  );
};

export default function TrainingHubScreen() {
  const router = useRouter();
  const { user } = useAuthStore();
  const colors = useThemeStore(s => s.colors);
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedTopic, setExpandedTopic] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [voiceQuestion, setVoiceQuestion] = useState('');
  const [aiResponse, setAiResponse] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  const recordingRef = React.useRef<Audio.Recording | null>(null);

  const categories = [...new Set(TRAINING_TOPICS.map(t => t.category))];

  // Filter topics by search and category
  const filteredTopics = TRAINING_TOPICS.filter(t => {
    const matchesSearch = !searchQuery ||
      t.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.category.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCategory = !selectedCategory || t.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  // Group by category
  const groupedTopics = filteredTopics.reduce((acc, topic) => {
    if (!acc[topic.category]) acc[topic.category] = [];
    acc[topic.category].push(topic);
    return acc;
  }, {} as Record<string, TrainingTopic[]>);

  const handleTopicPress = (topic: TrainingTopic) => {
    setExpandedTopic(expandedTopic === topic.id ? null : topic.id);
  };

  const startVoiceQuestion = async () => {
    try {
      const { granted } = await Audio.requestPermissionsAsync();
      if (!granted) {
        showSimpleAlert('Permission Required', 'Please allow microphone access');
        return;
      }
      await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true });
      const { recording } = await Audio.Recording.createAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY);
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
        message: `The user is asking for help with iMOs Relationship Management System. Here's their question: "${question}"\n\nPlease provide a helpful, concise answer explaining how to accomplish this in iMOs. If it involves a specific feature, mention where to find it in the app.`,
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
    <SafeAreaView style={[styles.container, { backgroundColor: colors.bg }]} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton} data-testid="training-hub-back">
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
              <Text style={styles.voiceHelpSubtitle}>Ask anything about iMOs by voice or text</Text>
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
              data-testid="training-ask-input"
            />
            <View style={styles.askButtons}>
              <TouchableOpacity
                style={[styles.voiceButton, isRecording && styles.voiceButtonActive]}
                onPress={isRecording ? stopVoiceQuestion : startVoiceQuestion}
                disabled={processing}
                data-testid="training-voice-btn"
              >
                <Ionicons name={isRecording ? 'stop' : 'mic'} size={24} color="#FFF" />
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.askButton, !voiceQuestion.trim() && styles.askButtonDisabled]}
                onPress={() => voiceQuestion.trim() && getAIHelp(voiceQuestion)}
                disabled={!voiceQuestion.trim() || processing}
                data-testid="training-ask-submit"
              >
                {processing ? (
                  <ActivityIndicator size="small" color="#FFF" />
                ) : (
                  <Ionicons name="arrow-forward" size={20} color="#FFF" />
                )}
              </TouchableOpacity>
            </View>
          </View>

          {aiResponse ? (
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
          ) : null}
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
            data-testid="training-search"
          />
          {searchQuery ? (
            <TouchableOpacity onPress={() => setSearchQuery('')}>
              <Ionicons name="close-circle" size={20} color="#8E8E93" />
            </TouchableOpacity>
          ) : null}
        </View>

        {/* Category Filter */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.categoryFilterRow}
        >
          <TouchableOpacity
            style={[styles.categoryChip, !selectedCategory && styles.categoryChipActive]}
            onPress={() => setSelectedCategory(null)}
          >
            <Text style={[styles.categoryChipText, !selectedCategory && styles.categoryChipTextActive]}>All</Text>
          </TouchableOpacity>
          {categories.map(cat => (
            <TouchableOpacity
              key={cat}
              style={[styles.categoryChip, selectedCategory === cat && styles.categoryChipActive]}
              onPress={() => setSelectedCategory(selectedCategory === cat ? null : cat)}
            >
              <Text style={[styles.categoryChipText, selectedCategory === cat && styles.categoryChipTextActive]}>{cat}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        {/* Topics */}
        {Object.entries(groupedTopics).map(([category, topics]) => (
          <View key={category} style={styles.categorySection}>
            <Text style={styles.categoryTitle}>{category}</Text>
            {topics.map(topic => {
              const isExpanded = expandedTopic === topic.id;
              return (
                <View key={topic.id}>
                  <TouchableOpacity
                    style={[styles.topicCard, isExpanded && styles.topicCardExpanded]}
                    onPress={() => handleTopicPress(topic)}
                    activeOpacity={0.7}
                    data-testid={`training-topic-${topic.id}`}
                  >
                    <View style={[styles.topicIcon, { backgroundColor: `${topic.iconColor}20` }]}>
                      <Ionicons name={topic.icon as any} size={24} color={topic.iconColor} />
                    </View>
                    <View style={styles.topicContent}>
                      <Text style={styles.topicTitle}>{topic.title}</Text>
                      <Text style={styles.topicDescription}>{topic.description}</Text>
                    </View>
                    <View style={styles.topicMeta}>
                      {topic.videoUrl ? (
                        <View style={styles.videoBadge}>
                          <Ionicons name="videocam" size={12} color="#FF2D55" />
                        </View>
                      ) : null}
                      {topic.duration ? <Text style={styles.topicDuration}>{topic.duration}</Text> : null}
                      <Ionicons name={isExpanded ? 'chevron-up' : 'chevron-down'} size={18} color="#8E8E93" />
                    </View>
                  </TouchableOpacity>
                  
                  {/* Expanded Content */}
                  {isExpanded ? (
                    <View style={styles.expandedPanel}>
                      {/* Video */}
                      {topic.videoUrl ? <VideoEmbed url={topic.videoUrl} /> : null}
                      
                      {/* Text Content */}
                      {topic.content ? <Text style={styles.expandedText}>{topic.content}</Text> : null}
                      
                      {/* Steps */}
                      {topic.steps && topic.steps.length > 0 ? (
                        <View style={styles.stepsContainer}>
                          <Text style={styles.stepsTitle}>Quick Steps</Text>
                          {topic.steps.map((step, idx) => (
                            <View key={idx} style={styles.stepRow}>
                              <View style={styles.stepBullet}>
                                <Text style={styles.stepBulletText}>{idx + 1}</Text>
                              </View>
                              <Text style={styles.stepText}>{step}</Text>
                            </View>
                          ))}
                        </View>
                      ) : null}
                      
                      {/* Go To Feature Button */}
                      {topic.route ? (
                        <TouchableOpacity
                          style={styles.goToButton}
                          onPress={() => router.push(topic.route as any)}
                          data-testid={`training-goto-${topic.id}`}
                        >
                          <Ionicons name="open-outline" size={16} color="#007AFF" />
                          <Text style={styles.goToButtonText}>Open in App</Text>
                        </TouchableOpacity>
                      ) : null}
                    </View>
                  ) : null}
                </View>
              );
            })}
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
    backgroundColor: undefined,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: undefined,
  },
  backButton: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: undefined,
  },
  content: {
    flex: 1,
  },
  scrollContent: {
    padding: 16,
  },
  // Voice Help
  voiceHelpSection: {
    backgroundColor: undefined,
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
  voiceHelpText: { flex: 1 },
  voiceHelpTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: undefined,
  },
  voiceHelpSubtitle: {
    fontSize: 13,
    color: undefined,
    marginTop: 2,
  },
  askContainer: {
    flexDirection: 'row',
    gap: 12,
    alignItems: 'flex-end',
  },
  askInput: {
    flex: 1,
    backgroundColor: undefined,
    borderRadius: 12,
    padding: 14,
    color: undefined,
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
    backgroundColor: undefined,
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
    color: undefined,
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
    color: undefined,
  },
  // Search
  searchContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: undefined,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    gap: 10,
    marginBottom: 12,
  },
  searchInput: {
    flex: 1,
    fontSize: 16,
    color: undefined,
  },
  // Category Filter
  categoryFilterRow: {
    flexDirection: 'row',
    gap: 8,
    paddingBottom: 16,
  },
  categoryChip: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    backgroundColor: undefined,
    borderRadius: 20,
  },
  categoryChipActive: {
    backgroundColor: '#007AFF',
  },
  categoryChipText: {
    fontSize: 13,
    fontWeight: '500',
    color: undefined,
  },
  categoryChipTextActive: {
    color: undefined,
  },
  // Category Section
  categorySection: {
    marginBottom: 24,
  },
  categoryTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: undefined,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 12,
  },
  // Topic Card
  topicCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: undefined,
    borderRadius: 12,
    padding: 16,
    marginBottom: 10,
    gap: 14,
  },
  topicCardExpanded: {
    borderBottomLeftRadius: 0,
    borderBottomRightRadius: 0,
    marginBottom: 0,
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
    color: undefined,
    marginBottom: 4,
  },
  topicDescription: {
    fontSize: 13,
    color: undefined,
  },
  topicMeta: {
    alignItems: 'flex-end',
    gap: 4,
  },
  topicDuration: {
    fontSize: 12,
    color: '#6E6E73',
  },
  videoBadge: {
    backgroundColor: '#FF2D5520',
    borderRadius: 10,
    width: 22,
    height: 22,
    alignItems: 'center',
    justifyContent: 'center',
  },
  // Expanded Panel
  expandedPanel: {
    backgroundColor: undefined,
    borderBottomLeftRadius: 12,
    borderBottomRightRadius: 12,
    paddingHorizontal: 16,
    paddingBottom: 20,
    marginBottom: 10,
    borderTopWidth: 1,
    borderTopColor: '#2C2C2E',
  },
  expandedText: {
    fontSize: 14,
    color: '#E5E5E7',
    lineHeight: 22,
    marginTop: 16,
  },
  // Video
  videoContainer: {
    width: '100%',
    aspectRatio: 16 / 9,
    borderRadius: 12,
    overflow: 'hidden',
    marginTop: 16,
    backgroundColor: undefined,
  },
  videoPlaceholder: {
    width: '100%',
    aspectRatio: 16 / 9,
    borderRadius: 12,
    backgroundColor: undefined,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 16,
  },
  playButton: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: '#FF2D55',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 8,
  },
  videoPlaceholderText: {
    fontSize: 13,
    color: undefined,
  },
  // Steps
  stepsContainer: {
    marginTop: 16,
    backgroundColor: undefined,
    borderRadius: 12,
    padding: 16,
  },
  stepsTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#C9A962',
    marginBottom: 12,
  },
  stepRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: 10,
    gap: 10,
  },
  stepBullet: {
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: '#007AFF30',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 1,
  },
  stepBulletText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#007AFF',
  },
  stepText: {
    flex: 1,
    fontSize: 14,
    color: '#E5E5E7',
    lineHeight: 20,
  },
  // Go To Button
  goToButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#007AFF20',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 8,
    alignSelf: 'flex-start',
    marginTop: 16,
    gap: 8,
  },
  goToButtonText: {
    fontSize: 14,
    color: '#007AFF',
    fontWeight: '600',
  },
});
