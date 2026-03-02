import React, { useState, useRef, useEffect, useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Dimensions,
  Animated,
  TextInput,
  ScrollView,
  ActivityIndicator,
  Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';
import { getOnboardingSlidesForRole } from './slideLibraries';
import { OnboardingSlide } from './types';

import { useThemeStore } from '../../store/themeStore';
const { width } = Dimensions.get('window');

// ============================================
// FEATURE DEMO COMPONENTS
// ============================================

// AI Suggested Responses Demo
const AISuggestionsDemo = () => {
  const [showSuggestion, setShowSuggestion] = useState(false);
  
  useEffect(() => {
    const timer = setTimeout(() => setShowSuggestion(true), 800);
    return () => clearTimeout(timer);
  }, []);
  
  return (
    <View style={demoStyles.phoneFrame}>
      <View style={demoStyles.chatContainer}>
        {/* Customer message */}
        <View style={demoStyles.customerBubble}>
          <Text style={demoStyles.customerText}>Hi! I'm interested in the 2024 Tahoe. Is it still available?</Text>
        </View>
        
        {/* AI Suggestion */}
        {showSuggestion && (
          <Animated.View style={demoStyles.aiSuggestionBox}>
            <View style={demoStyles.aiHeader}>
              <Ionicons name="sparkles" size={14} color="#AF52DE" />
              <Text style={demoStyles.aiLabel}>AI Suggested Response</Text>
            </View>
            <Text style={demoStyles.aiSuggestionText}>
              Hey! Yes, the Tahoe is still here and looking great! When would you like to come check it out? I'm free this afternoon or tomorrow morning.
            </Text>
            <View style={demoStyles.aiActions}>
              <TouchableOpacity style={demoStyles.sendButton}>
                <Text style={demoStyles.sendButtonText}>Send</Text>
              </TouchableOpacity>
              <TouchableOpacity style={demoStyles.editButton}>
                <Text style={demoStyles.editButtonText}>Edit</Text>
              </TouchableOpacity>
            </View>
          </Animated.View>
        )}
      </View>
    </View>
  );
};

// Congrats Card Demo
const CongratsCardDemo = () => {
  return (
    <View style={demoStyles.phoneFrame}>
      <LinearGradient colors={['#1a1a2e', '#16213e']} style={demoStyles.congratsCard}>
        <Text style={demoStyles.congratsHeadline}>CONGRATULATIONS!</Text>
        <View style={demoStyles.customerPhotoCircle}>
          <Ionicons name="person" size={32} color="#C9A962" />
        </View>
        <Text style={demoStyles.customerName}>Jessica Miller</Text>
        <Text style={demoStyles.congratsMessage}>
          On your new 2024 Chevrolet Tahoe!
        </Text>
        <View style={demoStyles.salesmanInfo}>
          <Text style={demoStyles.salesmanName}> - John Smith</Text>
          <Text style={demoStyles.dealership}>Premier Auto Group</Text>
        </View>
        <View style={demoStyles.shareIcons}>
          <Ionicons name="logo-facebook" size={20} color="#4267B2" />
          <Ionicons name="logo-instagram" size={20} color="#E1306C" />
          <Ionicons name="logo-twitter" size={20} color="#1DA1F2" />
        </View>
      </LinearGradient>
    </View>
  );
};

// Digital Business Card Demo
const DigitalCardDemo = () => {
  return (
    <View style={demoStyles.phoneFrame}>
      <View style={demoStyles.businessCard}>
        <View style={demoStyles.cardHeader}>
          <View style={demoStyles.profileCircle}>
            <Ionicons name="person" size={28} color={'#FFFFFF'} />
          </View>
          <View>
            <Text style={demoStyles.cardName}>John Smith</Text>
            <Text style={demoStyles.cardTitle}>Sales Consultant</Text>
          </View>
        </View>
        <View style={demoStyles.qrContainer}>
          <View style={demoStyles.qrCode}>
            <Ionicons name="qr-code" size={60} color={'#FFFFFF'} />
          </View>
          <Text style={demoStyles.qrLabel}>Scan to save contact</Text>
        </View>
        <View style={demoStyles.cardActions}>
          <View style={demoStyles.cardActionBtn}>
            <Ionicons name="call" size={18} color="#34C759" />
            <Text style={demoStyles.cardActionText}>Call</Text>
          </View>
          <View style={demoStyles.cardActionBtn}>
            <Ionicons name="chatbubble" size={18} color="#007AFF" />
            <Text style={demoStyles.cardActionText}>Text</Text>
          </View>
          <View style={demoStyles.cardActionBtn}>
            <Ionicons name="star" size={18} color="#FFD60A" />
            <Text style={demoStyles.cardActionText}>Review</Text>
          </View>
        </View>
      </View>
    </View>
  );
};

// Voice-to-Text Demo
const VoiceToTextDemo = () => {
  const pulseAnim = useRef(new Animated.Value(1)).current;
  
  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, { toValue: 1.2, duration: 500, useNativeDriver: true }),
        Animated.timing(pulseAnim, { toValue: 1, duration: 500, useNativeDriver: true }),
      ])
    ).start();
  }, []);
  
  return (
    <View style={demoStyles.phoneFrame}>
      <View style={demoStyles.voiceContainer}>
        <Animated.View style={[demoStyles.micButton, { transform: [{ scale: pulseAnim }] }]}>
          <Ionicons name="mic" size={32} color={'#FFFFFF'} />
        </Animated.View>
        <Text style={demoStyles.voiceStatus}>Listening...</Text>
        <View style={demoStyles.transcriptBox}>
          <Text style={demoStyles.transcriptText}>
            "Hey thanks for reaching out about the truck. I can get you a great deal on that F-150. When can you come in?"
          </Text>
        </View>
        <View style={demoStyles.waveform}>
          {[...Array(12)].map((_, i) => (
            <View key={i} style={[demoStyles.waveBar, { height: 10 + Math.random() * 25 }]} />
          ))}
        </View>
      </View>
    </View>
  );
};

// Campaigns Demo
const CampaignsDemo = () => {
  return (
    <View style={demoStyles.phoneFrame}>
      <View style={demoStyles.campaignContainer}>
        <Text style={demoStyles.campaignTitle}>Post-Sale Follow Up</Text>
        <View style={demoStyles.timelineContainer}>
          <View style={demoStyles.timelineItem}>
            <View style={[demoStyles.timelineDot, { backgroundColor: '#34C759' }]} />
            <View style={demoStyles.timelineContent}>
              <Text style={demoStyles.timelineDay}>Day 0</Text>
              <Text style={demoStyles.timelineText}>Welcome & Thank You</Text>
            </View>
            <Ionicons name="checkmark-circle" size={18} color="#34C759" />
          </View>
          <View style={demoStyles.timelineLine} />
          <View style={demoStyles.timelineItem}>
            <View style={[demoStyles.timelineDot, { backgroundColor: '#007AFF' }]} />
            <View style={demoStyles.timelineContent}>
              <Text style={demoStyles.timelineDay}>Day 3</Text>
              <Text style={demoStyles.timelineText}>How's the new ride?</Text>
            </View>
            <Ionicons name="time" size={18} color="#8E8E93" />
          </View>
          <View style={demoStyles.timelineLine} />
          <View style={demoStyles.timelineItem}>
            <View style={[demoStyles.timelineDot, { backgroundColor: '#FF9500' }]} />
            <View style={demoStyles.timelineContent}>
              <Text style={demoStyles.timelineDay}>Day 7</Text>
              <Text style={demoStyles.timelineText}>Referral Request</Text>
            </View>
            <Ionicons name="time" size={18} color="#8E8E93" />
          </View>
          <View style={demoStyles.timelineLine} />
          <View style={demoStyles.timelineItem}>
            <View style={[demoStyles.timelineDot, { backgroundColor: '#AF52DE' }]} />
            <View style={demoStyles.timelineContent}>
              <Text style={demoStyles.timelineDay}>Day 75</Text>
              <Text style={demoStyles.timelineText}>Service Reminder</Text>
            </View>
            <Ionicons name="time" size={18} color="#8E8E93" />
          </View>
        </View>
      </View>
    </View>
  );
};

// Analytics Demo
const AnalyticsDemo = () => {
  return (
    <View style={demoStyles.phoneFrame}>
      <View style={demoStyles.analyticsContainer}>
        <Text style={demoStyles.analyticsTitle}>Your Stats This Week</Text>
        <View style={demoStyles.statRow}>
          <View style={demoStyles.statCard}>
            <Ionicons name="chatbubbles" size={20} color="#007AFF" />
            <Text style={demoStyles.statNumber}>47</Text>
            <Text style={demoStyles.statLabel}>Messages Sent</Text>
          </View>
          <View style={demoStyles.statCard}>
            <Ionicons name="sparkles" size={20} color="#AF52DE" />
            <Text style={demoStyles.statNumber}>23</Text>
            <Text style={demoStyles.statLabel}>AI Responses</Text>
          </View>
        </View>
        <View style={demoStyles.statRow}>
          <View style={demoStyles.statCard}>
            <Ionicons name="people" size={20} color="#34C759" />
            <Text style={demoStyles.statNumber}>8</Text>
            <Text style={demoStyles.statLabel}>Leads Captured</Text>
          </View>
          <View style={demoStyles.statCard}>
            <Ionicons name="time" size={20} color="#FF9500" />
            <Text style={demoStyles.statNumber}>4.2h</Text>
            <Text style={demoStyles.statLabel}>Time Saved</Text>
          </View>
        </View>
        <View style={demoStyles.insightBox}>
          <Ionicons name="trending-up" size={16} color="#34C759" />
          <Text style={demoStyles.insightText}>Your AI handled 23 messages while you were with customers!</Text>
        </View>
      </View>
    </View>
  );
};

// AI Clone Demo
const AICloneDemo = () => {
  const [messageIndex, setMessageIndex] = useState(0);
  const messages = [
    { from: 'customer', text: "Hey, is the blue Silverado still available?" },
    { from: 'ai', text: "Hey! Yes it is! That truck is a beauty. I'm with another customer right now but I'd love to show it to you. What time works for you today?" },
  ];
  
  useEffect(() => {
    if (messageIndex < messages.length) {
      const timer = setTimeout(() => setMessageIndex(prev => prev + 1), 1200);
      return () => clearTimeout(timer);
    }
  }, [messageIndex]);
  
  return (
    <View style={demoStyles.phoneFrame}>
      <View style={demoStyles.chatContainer}>
        {messages.slice(0, messageIndex).map((msg, i) => (
          <View key={i} style={msg.from === 'customer' ? demoStyles.customerBubble : demoStyles.aiBubble}>
            {msg.from === 'ai' && (
              <View style={demoStyles.aiIndicator}>
                <Ionicons name="sparkles" size={10} color="#AF52DE" />
                <Text style={demoStyles.aiIndicatorText}>AI Assistant</Text>
              </View>
            )}
            <Text style={msg.from === 'customer' ? demoStyles.customerText : demoStyles.aiText}>{msg.text}</Text>
          </View>
        ))}
        {messageIndex < messages.length && (
          <View style={demoStyles.typingIndicator}>
            <View style={demoStyles.typingDot} />
            <View style={demoStyles.typingDot} />
            <View style={demoStyles.typingDot} />
          </View>
        )}
      </View>
    </View>
  );
};

// Birthday Card Demo
const BirthdayCardDemo = () => (
  <View style={demoStyles.phoneFrame}>
    <View style={{ borderRadius: 16, padding: 16, alignItems: 'center' }}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-around', width: '100%', marginBottom: 8 }}>
        {['#FF6B8A', '#FFD700', '#00CED1', '#FF8C00', '#9370DB'].map((c, i) => (
          <View key={i} style={{ width: 6 + (i%2)*2, height: 6 + (i%2)*2, borderRadius: 10, backgroundColor: c }} />
        ))}
      </View>
      <Text style={{ color: '#FF6B8A', fontSize: 18, fontWeight: '800', marginBottom: 10 }}>Happy Birthday!</Text>
      <View style={{ width: 56, height: 56, borderRadius: 28, backgroundColor: 'rgba(255,107,138,0.2)', borderWidth: 2, borderColor: '#FF6B8A', justifyContent: 'center', alignItems: 'center', marginBottom: 8 }}>
        <Ionicons name="person" size={28} color="#FF6B8A" />
      </View>
      <Text style={{ color: '#FFFFFF', fontSize: 15, fontWeight: '700', marginBottom: 4 }}>Sarah Johnson</Text>
      <Text style={{ color: 'rgba(255,255,255,0.7)', fontSize: 12, textAlign: 'center', marginBottom: 10 }}>Wishing you a wonderful birthday!</Text>
      <View style={{ flexDirection: 'row', gap: 12 }}>
        <Ionicons name="chatbubble" size={16} color="#34C759" />
        <Ionicons name="mail" size={16} color="#007AFF" />
        <Ionicons name="share-social" size={16} color="#FF9500" />
      </View>
    </View>
  </View>
);

// Review Page Demo
const ReviewPageDemo = () => (
  <View style={demoStyles.phoneFrame}>
    <View style={{ padding: 12 }}>
      <View style={{ alignItems: 'center', marginBottom: 10 }}>
        <Text style={{ color: '#FFD60A', fontSize: 14, fontWeight: '700', marginBottom: 6 }}>Leave a Review</Text>
        <View style={{ flexDirection: 'row', gap: 4, marginBottom: 8 }}>
          {[1,2,3,4,5].map(i => (
            <Ionicons key={i} name="star" size={20} color="#FFD60A" />
          ))}
        </View>
      </View>
      <View style={{ gap: 6 }}>
        {[
          { name: 'Google', icon: 'logo-google' as const, color: '#4285F4' },
          { name: 'Facebook', icon: 'logo-facebook' as const, color: '#1877F2' },
          { name: 'Yelp', icon: 'star' as const, color: '#FF1A1A' },
        ].map(r => (
          <View key={r.name} style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: 'rgba(255,255,255,0.08)', borderRadius: 8, padding: 10, gap: 10 }}>
            <Ionicons name={r.icon} size={18} color={r.color} />
            <Text style={{ color: '#FFFFFF', fontSize: 13, flex: 1 }}>Leave a {r.name} Review</Text>
            <Ionicons name="chevron-forward" size={14} color="#8E8E93" />
          </View>
        ))}
      </View>
    </View>
  </View>
);

// Showroom Demo
const ShowroomDemo = () => (
  <View style={demoStyles.phoneFrame}>
    <View style={{ padding: 10 }}>
      <Text style={{ color: '#007AFF', fontSize: 13, fontWeight: '700', textAlign: 'center', marginBottom: 10 }}>My Showcase</Text>
      <View style={{ flexDirection: 'row', gap: 6 }}>
        {[{ color: '#C9A962', label: 'Congrats' }, { color: '#FF6B8A', label: 'Birthday' }, { color: '#5856D6', label: 'Featured' }].map(card => (
          <View key={card.label} style={{ flex: 1, backgroundColor: 'rgba(255,255,255,0.08)', borderRadius: 8, padding: 8, alignItems: 'center' }}>
            <View style={{ width: 32, height: 32, borderRadius: 8, backgroundColor: `${card.color}30`, justifyContent: 'center', alignItems: 'center', marginBottom: 4 }}>
              <Ionicons name="images" size={16} color={card.color} />
            </View>
            <Text style={{ color: '#FFFFFF', fontSize: 9, fontWeight: '600' }}>{card.label}</Text>
          </View>
        ))}
      </View>
      <View style={{ flexDirection: 'row', gap: 6, marginTop: 8 }}>
        <View style={{ flex: 1, backgroundColor: 'rgba(52,199,89,0.1)', borderRadius: 6, padding: 6, alignItems: 'center' }}>
          <Ionicons name="chatbubble" size={12} color="#34C759" />
          <Text style={{ color: '#34C759', fontSize: 9, marginTop: 2 }}>Text Link</Text>
        </View>
        <View style={{ flex: 1, backgroundColor: 'rgba(0,122,255,0.1)', borderRadius: 6, padding: 6, alignItems: 'center' }}>
          <Ionicons name="mail" size={12} color="#007AFF" />
          <Text style={{ color: '#007AFF', fontSize: 9, marginTop: 2 }}>Email</Text>
        </View>
        <View style={{ flex: 1, backgroundColor: 'rgba(255,149,0,0.1)', borderRadius: 6, padding: 6, alignItems: 'center' }}>
          <Ionicons name="copy" size={12} color="#FF9500" />
          <Text style={{ color: '#FF9500', fontSize: 9, marginTop: 2 }}>Copy</Text>
        </View>
      </View>
    </View>
  </View>
);

// Quick Actions Demo
const QuickActionsDemo = () => (
  <View style={demoStyles.phoneFrame}>
    <View style={{ padding: 10 }}>
      <Text style={{ color: '#FF9500', fontSize: 13, fontWeight: '700', textAlign: 'center', marginBottom: 10 }}>Quick Actions</Text>
      <View style={{ gap: 6 }}>
        {[
          { icon: 'chatbubble' as const, label: 'Send SMS', color: '#34C759' },
          { icon: 'mail' as const, label: 'Send Email', color: '#007AFF' },
          { icon: 'gift' as const, label: 'Congrats Card', color: '#C9A962' },
          { icon: 'star' as const, label: 'Review Invite', color: '#FFD60A' },
          { icon: 'card' as const, label: 'Digital Card', color: '#5856D6' },
        ].map(a => (
          <View key={a.label} style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: 'rgba(255,255,255,0.08)', borderRadius: 8, padding: 10, gap: 10 }}>
            <View style={{ width: 28, height: 28, borderRadius: 14, backgroundColor: `${a.color}20`, justifyContent: 'center', alignItems: 'center' }}>
              <Ionicons name={a.icon} size={14} color={a.color} />
            </View>
            <Text style={{ color: '#FFFFFF', fontSize: 13, flex: 1 }}>{a.label}</Text>
            <Ionicons name="chevron-forward" size={14} color="#8E8E93" />
          </View>
        ))}
      </View>
    </View>
  </View>
);

// ============================================
// MAIN COMPONENT
// ============================================

export default function OnboardingScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { user, updateUser } = useAuthStore();
  const [currentIndex, setCurrentIndex] = useState(0);
  const [completing, setCompleting] = useState(false);
  const fadeAnim = useRef(new Animated.Value(1)).current;
  
  // Get role-based slides
  const SLIDES = useMemo(() => {
    const role = user?.role || 'user';
    return getOnboardingSlidesForRole(role);
  }, [user?.role]);
  
  // User inputs
  const [communicationStyle, setCommunicationStyle] = useState('friendly');
  const [aiGreeting, setAiGreeting] = useState('assistant');
  const [bioInputs, setBioInputs] = useState({
    hobbies: '',
    family: '',
    fun_facts: '',
  });
  
  // Profile verification inputs (pre-filled from user data)
  const [profileInputs, setProfileInputs] = useState({
    name: '',
    title: '',
    bio: '',
  });
  
  // Team invite state
  const [teamInvites, setTeamInvites] = useState<{name: string; email: string; phone: string}[]>([
    { name: '', email: '', phone: '' },
  ]);
  const [sendingInvites, setSendingInvites] = useState(false);
  const [invitesSent, setInvitesSent] = useState(false);
  
  // Pre-fill profile inputs with user data
  useEffect(() => {
    if (user) {
      setProfileInputs({
        name: user.name || '',
        title: user.persona?.title || '',
        bio: user.persona?.bio || '',
      });
    }
  }, [user]);
  
  const currentSlide = SLIDES[currentIndex];
  const isLastSlide = currentIndex === SLIDES.length - 1;
  const progress = (currentIndex + 1) / SLIDES.length;

  const animateToSlide = (newIndex: number) => {
    Animated.timing(fadeAnim, {
      toValue: 0,
      duration: 120,
      useNativeDriver: true,
    }).start(() => {
      setCurrentIndex(newIndex);
      Animated.timing(fadeAnim, {
        toValue: 1,
        duration: 200,
        useNativeDriver: true,
      }).start();
    });
  };

  const handleNext = () => {
    if (isLastSlide) {
      completeOnboarding();
    } else {
      animateToSlide(currentIndex + 1);
    }
  };

  const handleBack = () => {
    if (currentIndex > 0) {
      animateToSlide(currentIndex - 1);
    }
  };

  const handleSkipToEnd = () => {
    const aiSetupIndex = SLIDES.findIndex(s => s.type === 'ai_setup');
    if (currentIndex < aiSetupIndex) {
      animateToSlide(aiSetupIndex);
    }
  };

  const canProceed = () => {
    // All slides can proceed - we want users to move quickly through the tour
    // The only validation is on AI style choices which are pre-selected
    return true;
  };

  const completeOnboarding = async () => {
    setCompleting(true);
    try {
      await api.post('/auth/complete-onboarding', {
        user_id: user?._id,
        // Profile verification data
        name: profileInputs.name || user?.name,
        title: profileInputs.title,
        bio: profileInputs.bio,
        // AI persona data
        communication_style: communicationStyle,
        ai_greeting_style: aiGreeting,
        hobbies: bioInputs.hobbies,
        family_info: bioInputs.family,
        fun_facts: bioInputs.fun_facts,
      });
      
      updateUser({ 
        onboarding_complete: true,
        name: profileInputs.name || user?.name,
      });
      router.replace('/(tabs)/inbox');
    } catch (error) {
      console.error('Failed to complete onboarding:', error);
      router.replace('/(tabs)/inbox');
    } finally {
      setCompleting(false);
    }
  };

  const renderDemoComponent = () => {
    if (!currentSlide.demoComponent) return null;
    
    switch (currentSlide.demoComponent) {
      case 'ai_clone': return <AICloneDemo />;
      case 'ai_suggestions': return <AISuggestionsDemo />;
      case 'congrats_card': return <CongratsCardDemo />;
      case 'digital_card': return <DigitalCardDemo />;
      case 'voice_to_text': return <VoiceToTextDemo />;
      case 'campaigns': return <CampaignsDemo />;
      case 'analytics': return <AnalyticsDemo />;
      case 'DigitalCardDemo': return <DigitalCardDemo />;
      case 'CongratsCardDemo': return <CongratsCardDemo />;
      case 'BirthdayCardDemo': return <BirthdayCardDemo />;
      case 'ReviewPageDemo': return <ReviewPageDemo />;
      case 'ShowroomDemo': return <ShowroomDemo />;
      case 'QuickActionsDemo': return <QuickActionsDemo />;
      case 'CampaignsDemo': return <CampaignsDemo />;
      default: return null;
    }
  };

  const renderBenefits = () => {
    if (!currentSlide.benefits) return null;
    
    return (
      <View style={styles.benefitsContainer}>
        {currentSlide.benefits.map((benefit, index) => (
          <View key={index} style={styles.benefitRow}>
            <Ionicons name="checkmark-circle" size={20} color="#34C759" />
            <Text style={styles.benefitText}>{benefit}</Text>
          </View>
        ))}
      </View>
    );
  };

  const renderQuickWinBadge = () => {
    if (currentSlide.type !== 'quick_win' || !currentSlide.quickWinNumber) return null;
    return (
      <View style={styles.quickWinBadge}>
        <Ionicons name="flash" size={12} color="#FFD60A" />
        <Text style={styles.quickWinBadgeText}>Quick Win #{currentSlide.quickWinNumber}</Text>
      </View>
    );
  };

  const renderTryItButton = () => {
    if (!currentSlide.tryItRoute) return null;
    return (
      <TouchableOpacity
        style={styles.tryItButton}
        onPress={() => {
          // Save progress and navigate to feature
          router.push(currentSlide.tryItRoute as any);
        }}
        data-testid={`onboarding-try-${currentSlide.id}`}
      >
        <Ionicons name="play-circle" size={18} color={colors.text} />
        <Text style={styles.tryItButtonText}>{currentSlide.tryItLabel || 'Try It Now'}</Text>
      </TouchableOpacity>
    );
  };

  const renderChecklist = () => {
    if (currentSlide.type !== 'checklist' || !currentSlide.checklistItems) return null;
    return (
      <ScrollView style={styles.checklistContainer} showsVerticalScrollIndicator={false}>
        {currentSlide.checklistItems.map((item, index) => (
          <TouchableOpacity
            key={item.id}
            style={styles.checklistItem}
            activeOpacity={0.7}
            data-testid={`checklist-${item.id}`}
          >
            <View style={[styles.checklistIcon, { backgroundColor: `${item.iconColor}20` }]}>
              <Ionicons name={item.icon as any} size={20} color={item.iconColor} />
            </View>
            <View style={styles.checklistContent}>
              <Text style={styles.checklistLabel}>{item.label}</Text>
              <Text style={styles.checklistDescription}>{item.description}</Text>
            </View>
            <View style={styles.checklistArrow}>
              <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
            </View>
          </TouchableOpacity>
        ))}
      </ScrollView>
    );
  };

  const renderChoices = () => {
    if (!currentSlide.choices) return null;
    
    const selectedValue = currentSlide.id === 'ai_style' ? communicationStyle : aiGreeting;
    const setSelected = currentSlide.id === 'ai_style' ? setCommunicationStyle : setAiGreeting;
    
    return (
      <ScrollView style={styles.choicesContainer} showsVerticalScrollIndicator={false}>
        {currentSlide.choices.map((choice) => (
          <TouchableOpacity
            key={choice.id}
            style={[
              styles.choiceCard,
              selectedValue === choice.id && styles.choiceCardSelected,
            ]}
            onPress={() => setSelected(choice.id)}
            activeOpacity={0.7}
          >
            <View style={[styles.choiceIconContainer, { backgroundColor: `${currentSlide.iconColor}20` }]}>
              <Ionicons name={choice.icon as any} size={24} color={currentSlide.iconColor} />
            </View>
            <View style={styles.choiceContent}>
              <Text style={styles.choiceLabel}>{choice.label}</Text>
              <Text style={styles.choiceDescription}>{choice.description}</Text>
            </View>
            {selectedValue === choice.id && (
              <Ionicons name="checkmark-circle" size={24} color="#34C759" />
            )}
          </TouchableOpacity>
        ))}
      </ScrollView>
    );
  };

  const renderMultiInput = () => {
    if (!currentSlide.inputFields) return null;
    
    // Determine which state to use based on slide id
    const isProfileVerify = currentSlide.id === 'verify_profile';
    const inputState = isProfileVerify ? profileInputs : bioInputs;
    const setInputState = isProfileVerify 
      ? (updater: any) => setProfileInputs(prev => ({ ...prev, ...updater }))
      : (updater: any) => setBioInputs(prev => ({ ...prev, ...updater }));
    
    return (
      <ScrollView style={styles.inputsContainer} showsVerticalScrollIndicator={false}>
        {currentSlide.inputFields.map((field) => (
          <View key={field.key} style={styles.inputGroup}>
            <Text style={styles.inputLabel}>{field.label}</Text>
            <TextInput
              style={[styles.textInput, field.multiline && styles.textInputMultiline]}
              placeholder={field.placeholder}
              placeholderTextColor="#6E6E73"
              value={inputState[field.key as keyof typeof inputState] || ''}
              onChangeText={(text) => {
                if (isProfileVerify) {
                  setProfileInputs(prev => ({ ...prev, [field.key]: text }));
                } else {
                  setBioInputs(prev => ({ ...prev, [field.key]: text }));
                }
              }}
              multiline={field.multiline}
              maxLength={field.multiline ? 300 : 100}
            />
          </View>
        ))}
        <Text style={styles.inputHint}>
          {isProfileVerify 
            ? 'Review and update your info - this powers your business card!'
            : 'This info helps your AI sound more like YOU!'}
        </Text>
      </ScrollView>
    );
  };

  // Add a new team member input row
  const addTeamMember = () => {
    setTeamInvites([...teamInvites, { name: '', email: '', phone: '' }]);
  };

  // Remove a team member input row
  const removeTeamMember = (index: number) => {
    if (teamInvites.length > 1) {
      setTeamInvites(teamInvites.filter((_, i) => i !== index));
    }
  };

  // Update a team member field
  const updateTeamMember = (index: number, field: string, value: string) => {
    const updated = [...teamInvites];
    updated[index] = { ...updated[index], [field]: value };
    setTeamInvites(updated);
  };

  // Send team invites
  const sendTeamInvites = async () => {
    const validInvites = teamInvites.filter(i => i.name && (i.email || i.phone));
    if (validInvites.length === 0) {
      handleNext();
      return;
    }

    setSendingInvites(true);
    try {
      for (const invite of validInvites) {
        await api.post('/admin/users/create', {
          name: invite.name,
          email: invite.email || undefined,
          phone: invite.phone || undefined,
          role: currentSlide.inviteRole || 'user',
          organization_id: user?.organization_id,
          store_id: currentSlide.inviteRole === 'user' ? user?.store_id : undefined,
          send_invite: true,
        });
      }
      setInvitesSent(true);
      setTimeout(() => {
        handleNext();
      }, 1500);
    } catch (error) {
      console.error('Error sending invites:', error);
      // Still allow proceeding
      handleNext();
    } finally {
      setSendingInvites(false);
    }
  };

  const renderTeamInvite = () => {
    const inviteTitle = currentSlide.inviteTitle || 'Team Member';
    
    return (
      <ScrollView style={styles.teamInviteContainer} showsVerticalScrollIndicator={false}>
        <View style={styles.teamInviteHeader}>
          <Ionicons name="people-circle" size={48} color={currentSlide.iconColor} />
          <Text style={styles.teamInviteTitle}>Add Your {inviteTitle}s</Text>
          <Text style={styles.teamInviteSubtitle}>
            Enter their details below. They'll receive an invite to join.
          </Text>
        </View>

        {teamInvites.map((member, index) => (
          <View key={index} style={styles.teamMemberCard}>
            <View style={styles.teamMemberHeader}>
              <Text style={styles.teamMemberNumber}>{inviteTitle} {index + 1}</Text>
              {teamInvites.length > 1 && (
                <TouchableOpacity onPress={() => removeTeamMember(index)}>
                  <Ionicons name="close-circle" size={24} color="#FF3B30" />
                </TouchableOpacity>
              )}
            </View>
            <TextInput
              style={styles.teamInput}
              placeholder="Full Name"
              placeholderTextColor="#6E6E73"
              value={member.name}
              onChangeText={(text) => updateTeamMember(index, 'name', text)}
            />
            <TextInput
              style={styles.teamInput}
              placeholder="Email Address"
              placeholderTextColor="#6E6E73"
              keyboardType="email-address"
              autoCapitalize="none"
              value={member.email}
              onChangeText={(text) => updateTeamMember(index, 'email', text)}
            />
            <TextInput
              style={styles.teamInput}
              placeholder="Phone Number"
              placeholderTextColor="#6E6E73"
              keyboardType="phone-pad"
              value={member.phone}
              onChangeText={(text) => updateTeamMember(index, 'phone', text)}
            />
          </View>
        ))}

        <TouchableOpacity style={styles.addMemberButton} onPress={addTeamMember}>
          <Ionicons name="add-circle" size={24} color="#007AFF" />
          <Text style={styles.addMemberText}>Add Another {inviteTitle}</Text>
        </TouchableOpacity>

        {invitesSent && (
          <View style={styles.inviteSuccessMessage}>
            <Ionicons name="checkmark-circle" size={24} color="#34C759" />
            <Text style={styles.inviteSuccessText}>Invites sent successfully!</Text>
          </View>
        )}

        {currentSlide.skipable && (
          <TouchableOpacity onPress={handleNext} style={styles.skipInviteLink}>
            <Text style={styles.skipInviteLinkText}>Skip for now - I'll invite them later</Text>
          </TouchableOpacity>
        )}
      </ScrollView>
    );
  };

  const renderActionButton = () => {
    if (!currentSlide.actionButton) return null;
    
    return (
      <View style={styles.actionButtonContainer}>
        <TouchableOpacity
          style={styles.actionButton}
          onPress={() => router.push(currentSlide.actionButton!.route as any)}
        >
          <Ionicons name="cloud-upload" size={20} color={colors.text} />
          <Text style={styles.actionButtonText}>{currentSlide.actionButton.label}</Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={handleNext} style={styles.skipLink}>
          <Text style={styles.skipLinkText}>I'll do this later</Text>
        </TouchableOpacity>
      </View>
    );
  };

  const renderInteractiveContent = () => {
    if (currentSlide.interactiveType === 'choice') {
      return renderChoices();
    }
    if (currentSlide.interactiveType === 'multi_input') {
      return renderMultiInput();
    }
    if (currentSlide.interactiveType === 'import') {
      return renderActionButton();
    }
    if (currentSlide.interactiveType === 'team_invite' || currentSlide.type === 'team_invite') {
      return renderTeamInvite();
    }
    return null;
  };

  return (
    <View style={styles.container}>
      <LinearGradient
        colors={currentSlide.bgGradient as any}
        style={StyleSheet.absoluteFill}
      />
      
      <SafeAreaView style={styles.safeArea} edges={['top']}>
        {/* Progress Bar */}
        <View style={styles.progressContainer}>
          <View style={styles.progressTrack}>
            <Animated.View style={[styles.progressFill, { width: `${progress * 100}%` }]} />
          </View>
          <Text style={styles.progressText}>{currentIndex + 1}/{SLIDES.length}</Text>
        </View>

        {/* Skip Button */}
        {currentSlide.type === 'feature' && currentIndex < 2 && (
          <TouchableOpacity style={styles.skipButton} onPress={handleSkipToEnd}>
            <Text style={styles.skipText}>Skip to Setup</Text>
          </TouchableOpacity>
        )}
      </SafeAreaView>

      {/* Slide Content */}
      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        <Animated.View style={[styles.slideContent, { opacity: fadeAnim }]}>
          {/* Icon - only show for non-demo slides */}
          {!currentSlide.demoComponent && (
            <View style={[styles.iconContainer, { backgroundColor: `${currentSlide.iconColor}15` }]}>
              <Ionicons name={currentSlide.icon as any} size={56} color={currentSlide.iconColor} />
            </View>
          )}

          {/* Title */}
          {currentSlide.id === 'welcome' ? (
            <View style={styles.welcomeTitleContainer}>
              <Text style={styles.title}>Welcome to </Text>
              <Image 
                source={require('../../assets/images/imos-logo-white-v3.png')}
                style={styles.welcomeLogo}
                resizeMode="contain"
              />
              <Text style={styles.title}>!</Text>
            </View>
          ) : (
            <Text style={styles.title}>{currentSlide.title}</Text>
          )}
          {currentSlide.subtitle && (
            currentSlide.id === 'ai_intro' ? (
              <View style={styles.subtitleWithLogoContainer}>
                <Text style={[styles.subtitle, { color: currentSlide.iconColor }]}>The Magic Behind </Text>
                <Image 
                  source={require('../../assets/images/imos-logo-white-v3.png')}
                  style={styles.subtitleLogo}
                  resizeMode="contain"
                />
              </View>
            ) : (
              <Text style={[styles.subtitle, { color: currentSlide.iconColor }]}>
                {currentSlide.subtitle}
              </Text>
            )
          )}

          {/* Quick Win Badge */}
          {renderQuickWinBadge()}

          {/* Description */}
          <Text style={styles.description}>{currentSlide.description}</Text>

          {/* Demo Component */}
          {renderDemoComponent()}

          {/* Benefits */}
          {currentSlide.type !== 'ai_setup' && !currentSlide.demoComponent && currentSlide.type !== 'checklist' && renderBenefits()}

          {/* Benefits below demo for quick_win slides */}
          {currentSlide.type === 'quick_win' && currentSlide.demoComponent && renderBenefits()}

          {/* Try It Now button for quick win slides */}
          {renderTryItButton()}

          {/* Checklist */}
          {renderChecklist()}

          {/* Interactive Content */}
          {renderInteractiveContent()}
        </Animated.View>
      </ScrollView>

      {/* Navigation */}
      <SafeAreaView edges={['bottom']} style={styles.navContainer}>
        <View style={styles.navButtons}>
          {currentIndex > 0 ? (
            <TouchableOpacity style={styles.backButton} onPress={handleBack}>
              <Ionicons name="chevron-back" size={24} color={colors.text} />
              <Text style={styles.backButtonText}>Back</Text>
            </TouchableOpacity>
          ) : (
            <View style={styles.backButton} />
          )}

          <TouchableOpacity
            style={[
              styles.nextButton,
              !canProceed() && styles.nextButtonDisabled,
              isLastSlide && styles.completeButton,
              currentSlide.type === 'team_invite' && styles.sendInvitesButton,
            ]}
            onPress={currentSlide.type === 'team_invite' ? sendTeamInvites : handleNext}
            disabled={!canProceed() || completing || sendingInvites}
          >
            {completing || sendingInvites ? (
              <ActivityIndicator size="small" color={colors.text} />
            ) : (
              <>
                <Text style={[styles.nextButtonText, isLastSlide && styles.completeButtonText]}>
                  {isLastSlide ? "Let's Go!" : currentSlide.type === 'team_invite' ? 'Send Invites & Continue' : 'Continue'}
                </Text>
                {!isLastSlide && currentSlide.type !== 'team_invite' && <Ionicons name="chevron-forward" size={20} color={colors.text} />}
                {currentSlide.type === 'team_invite' && <Ionicons name="paper-plane" size={18} color={colors.text} style={{ marginLeft: 6 }} />}
              </>
            )}
          </TouchableOpacity>
        </View>

        {/* Progress Dots */}
        <View style={styles.dotsContainer}>
          {SLIDES.map((_, index) => (
            <View
              key={index}
              style={[
                styles.dot,
                index === currentIndex && styles.dotActive,
                index < currentIndex && styles.dotComplete,
              ]}
            />
          ))}
        </View>
      </SafeAreaView>
    </View>
  );
}

// ============================================
// DEMO STYLES
// ============================================

const demoStyles = StyleSheet.create({
  phoneFrame: {
    width: width - 64,
    maxWidth: 320,
    backgroundColor: 'rgba(0,0,0,0.3)',
    borderRadius: 20,
    padding: 12,
    marginTop: 16,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.1)',
  },
  chatContainer: {
    gap: 10,
  },
  customerBubble: {
    backgroundColor: '#2C2C2E',
    borderRadius: 16,
    borderBottomLeftRadius: 4,
    padding: 12,
    maxWidth: '85%',
    alignSelf: 'flex-start',
  },
  customerText: {
    color: '#FFFFFF',
    fontSize: 14,
    lineHeight: 20,
  },
  aiBubble: {
    backgroundColor: 'rgba(175,82,222,0.15)',
    borderRadius: 16,
    borderBottomRightRadius: 4,
    padding: 12,
    maxWidth: '85%',
    alignSelf: 'flex-end',
  },
  aiText: {
    color: '#FFFFFF',
    fontSize: 14,
    lineHeight: 20,
  },
  aiIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginBottom: 6,
  },
  aiIndicatorText: {
    color: '#AF52DE',
    fontSize: 10,
    fontWeight: '600',
  },
  typingIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    padding: 12,
    alignSelf: 'flex-end',
  },
  typingDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#8E8E93',
  },
  aiSuggestionBox: {
    backgroundColor: 'rgba(175,82,222,0.1)',
    borderRadius: 12,
    padding: 12,
    borderWidth: 1,
    borderColor: 'rgba(175,82,222,0.3)',
  },
  aiHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 8,
  },
  aiLabel: {
    color: '#AF52DE',
    fontSize: 11,
    fontWeight: '600',
  },
  aiSuggestionText: {
    color: '#FFFFFF',
    fontSize: 13,
    lineHeight: 19,
    marginBottom: 10,
  },
  aiActions: {
    flexDirection: 'row',
    gap: 8,
  },
  sendButton: {
    backgroundColor: '#34C759',
    paddingVertical: 6,
    paddingHorizontal: 16,
    borderRadius: 14,
  },
  sendButtonText: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '600',
  },
  editButton: {
    backgroundColor: 'rgba(255,255,255,0.1)',
    paddingVertical: 6,
    paddingHorizontal: 16,
    borderRadius: 14,
  },
  editButtonText: {
    color: '#FFFFFF',
    fontSize: 13,
  },
  // Congrats Card
  congratsCard: {
    borderRadius: 16,
    padding: 20,
    alignItems: 'center',
  },
  congratsHeadline: {
    color: '#C9A962',
    fontSize: 18,
    fontWeight: '800',
    letterSpacing: 2,
    marginBottom: 12,
  },
  customerPhotoCircle: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: 'rgba(201,169,98,0.2)',
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 2,
    borderColor: '#C9A962',
    marginBottom: 10,
  },
  customerName: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 4,
  },
  congratsMessage: {
    color: 'rgba(255,255,255,0.8)',
    fontSize: 13,
    textAlign: 'center',
    marginBottom: 12,
  },
  salesmanInfo: {
    alignItems: 'center',
    marginBottom: 12,
  },
  salesmanName: {
    color: '#C9A962',
    fontSize: 13,
    fontWeight: '600',
  },
  dealership: {
    color: 'rgba(255,255,255,0.5)',
    fontSize: 11,
  },
  shareIcons: {
    flexDirection: 'row',
    gap: 16,
  },
  // Digital Card
  businessCard: {
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    padding: 16,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginBottom: 16,
  },
  profileCircle: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: '#007AFF',
    justifyContent: 'center',
    alignItems: 'center',
  },
  cardName: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  cardTitle: {
    color: '#8E8E93',
    fontSize: 13,
  },
  qrContainer: {
    alignItems: 'center',
    marginBottom: 16,
  },
  qrCode: {
    width: 80,
    height: 80,
    backgroundColor: '#1C1C1E',
    borderRadius: 8,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 8,
  },
  qrLabel: {
    color: '#8E8E93',
    fontSize: 11,
  },
  cardActions: {
    flexDirection: 'row',
    justifyContent: 'space-around',
  },
  cardActionBtn: {
    alignItems: 'center',
    gap: 4,
  },
  cardActionText: {
    color: '#8E8E93',
    fontSize: 11,
  },
  // Voice to Text
  voiceContainer: {
    alignItems: 'center',
    paddingVertical: 10,
  },
  micButton: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: '#FF3B30',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 12,
  },
  voiceStatus: {
    color: '#FF3B30',
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 12,
  },
  transcriptBox: {
    backgroundColor: 'rgba(255,255,255,0.1)',
    borderRadius: 12,
    padding: 12,
    marginBottom: 12,
  },
  transcriptText: {
    color: '#FFFFFF',
    fontSize: 13,
    lineHeight: 19,
    fontStyle: 'italic',
  },
  waveform: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    height: 35,
    gap: 3,
  },
  waveBar: {
    width: 4,
    backgroundColor: '#FF3B30',
    borderRadius: 2,
  },
  // Campaigns
  campaignContainer: {
    padding: 4,
  },
  campaignTitle: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 12,
    textAlign: 'center',
  },
  timelineContainer: {
    paddingLeft: 8,
  },
  timelineItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  timelineDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  timelineContent: {
    flex: 1,
  },
  timelineDay: {
    color: '#8E8E93',
    fontSize: 10,
    fontWeight: '600',
  },
  timelineText: {
    color: '#FFFFFF',
    fontSize: 12,
  },
  timelineLine: {
    width: 2,
    height: 16,
    backgroundColor: 'rgba(255,255,255,0.2)',
    marginLeft: 4,
  },
  // Analytics
  analyticsContainer: {
    padding: 4,
  },
  analyticsTitle: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 12,
    textAlign: 'center',
  },
  statRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 8,
  },
  statCard: {
    flex: 1,
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderRadius: 10,
    padding: 10,
    alignItems: 'center',
  },
  statNumber: {
    color: '#FFFFFF',
    fontSize: 20,
    fontWeight: '700',
    marginTop: 4,
  },
  statLabel: {
    color: '#8E8E93',
    fontSize: 10,
    marginTop: 2,
  },
  insightBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: 'rgba(52,199,89,0.1)',
    borderRadius: 8,
    padding: 10,
    marginTop: 4,
  },
  insightText: {
    color: '#34C759',
    fontSize: 11,
    flex: 1,
  },
});

// ============================================
// MAIN STYLES
// ============================================

const getStyles = (colors: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  safeArea: {
    zIndex: 10,
  },
  progressContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingTop: 10,
    gap: 12,
  },
  progressTrack: {
    flex: 1,
    height: 4,
    backgroundColor: 'rgba(255,255,255,0.2)',
    borderRadius: 2,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    backgroundColor: '#C9A962',
    borderRadius: 2,
  },
  progressText: {
    color: 'rgba(255,255,255,0.6)',
    fontSize: 13,
    fontWeight: '500',
  },
  skipButton: {
    position: 'absolute',
    top: 12,
    right: 20,
    paddingVertical: 6,
    paddingHorizontal: 12,
    backgroundColor: 'rgba(255,255,255,0.1)',
    borderRadius: 16,
  },
  skipText: {
    color: 'rgba(255,255,255,0.7)',
    fontSize: 13,
    fontWeight: '500',
  },
  scrollContent: {
    flexGrow: 1,
    paddingBottom: 20,
  },
  slideContent: {
    flex: 1,
    alignItems: 'center',
    paddingHorizontal: 24,
    paddingTop: 30,
  },
  iconContainer: {
    width: 100,
    height: 100,
    borderRadius: 50,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 20,
  },
  title: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.text,
    textAlign: 'center',
    marginBottom: 6,
  },
  welcomeTitleContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 6,
  },
  welcomeLogo: {
    width: 70,
    height: 28,
    marginHorizontal: 4,
  },
  subtitleWithLogoContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
  },
  subtitleLogo: {
    width: 50,
    height: 20,
  },
  subtitle: {
    fontSize: 15,
    fontWeight: '600',
    textAlign: 'center',
    marginBottom: 12,
  },
  description: {
    fontSize: 14,
    color: 'rgba(255,255,255,0.85)',
    textAlign: 'center',
    lineHeight: 21,
    maxWidth: 340,
    marginBottom: 16,
  },
  benefitsContainer: {
    width: '100%',
    maxWidth: 340,
    gap: 10,
    marginTop: 8,
  },
  benefitRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  benefitText: {
    fontSize: 15,
    color: colors.text,
    fontWeight: '500',
  },
  choicesContainer: {
    width: '100%',
    maxHeight: 280,
    marginTop: 8,
  },
  choiceCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderRadius: 14,
    padding: 14,
    marginBottom: 10,
    borderWidth: 2,
    borderColor: 'transparent',
  },
  choiceCardSelected: {
    borderColor: '#34C759',
    backgroundColor: 'rgba(52,199,89,0.1)',
  },
  choiceIconContainer: {
    width: 44,
    height: 44,
    borderRadius: 22,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  choiceContent: {
    flex: 1,
  },
  choiceLabel: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 2,
  },
  choiceDescription: {
    fontSize: 13,
    color: 'rgba(255,255,255,0.6)',
  },
  inputsContainer: {
    width: '100%',
    maxHeight: 320,
    marginTop: 8,
  },
  inputGroup: {
    marginBottom: 16,
  },
  inputLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 8,
  },
  textInput: {
    backgroundColor: 'rgba(255,255,255,0.1)',
    borderRadius: 12,
    padding: 14,
    fontSize: 15,
    color: colors.text,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.15)',
  },
  textInputMultiline: {
    minHeight: 80,
    textAlignVertical: 'top',
  },
  inputHint: {
    fontSize: 13,
    color: 'rgba(255,255,255,0.5)',
    textAlign: 'center',
    marginTop: 8,
    fontStyle: 'italic',
  },
  actionButtonContainer: {
    width: '100%',
    alignItems: 'center',
    marginTop: 16,
    gap: 16,
  },
  actionButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#34C759',
    paddingVertical: 16,
    paddingHorizontal: 32,
    borderRadius: 30,
    gap: 8,
    width: '100%',
    maxWidth: 280,
  },
  actionButtonText: {
    color: colors.text,
    fontSize: 17,
    fontWeight: '600',
  },
  skipLink: {
    padding: 8,
  },
  skipLinkText: {
    color: 'rgba(255,255,255,0.6)',
    fontSize: 14,
  },
  navContainer: {
    paddingHorizontal: 20,
    paddingBottom: 10,
    backgroundColor: 'rgba(0,0,0,0.3)',
  },
  navButtons: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  backButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 8,
    minWidth: 80,
  },
  backButtonText: {
    color: colors.text,
    fontSize: 16,
    marginLeft: 4,
  },
  nextButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#C9A962',
    paddingVertical: 14,
    paddingHorizontal: 24,
    borderRadius: 28,
    gap: 4,
  },
  nextButtonDisabled: {
    opacity: 0.5,
  },
  nextButtonText: {
    color: colors.text,
    fontSize: 16,
    fontWeight: '600',
  },
  completeButton: {
    backgroundColor: '#34C759',
    paddingHorizontal: 32,
  },
  completeButtonText: {
    color: colors.text,
  },
  dotsContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 6,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: 'rgba(255,255,255,0.3)',
  },
  dotActive: {
    backgroundColor: '#C9A962',
    width: 18,
  },
  dotComplete: {
    backgroundColor: '#34C759',
  },
  // Team Invite Styles
  teamInviteContainer: {
    width: '100%',
    maxHeight: 400,
    marginTop: 16,
  },
  // Quick Win styles
  quickWinBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: 'rgba(255,214,10,0.15)',
    paddingVertical: 4,
    paddingHorizontal: 12,
    borderRadius: 20,
    marginBottom: 10,
  },
  quickWinBadgeText: {
    color: '#FFD60A',
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  tryItButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: 'rgba(0,122,255,0.9)',
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 24,
    marginTop: 16,
    width: '100%',
    maxWidth: 280,
  },
  tryItButtonText: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '600',
  },
  // Checklist styles
  checklistContainer: {
    width: '100%',
    maxHeight: 380,
    marginTop: 8,
  },
  checklistItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderRadius: 14,
    padding: 14,
    marginBottom: 8,
    gap: 12,
  },
  checklistIcon: {
    width: 40,
    height: 40,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  checklistContent: {
    flex: 1,
  },
  checklistLabel: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '600',
    marginBottom: 2,
  },
  checklistDescription: {
    color: 'rgba(255,255,255,0.6)',
    fontSize: 12,
  },
  checklistArrow: {
    paddingLeft: 4,
  },
  teamInviteHeader: {
    alignItems: 'center',
    marginBottom: 20,
  },
  teamInviteTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.text,
    marginTop: 12,
  },
  teamInviteSubtitle: {
    fontSize: 14,
    color: 'rgba(255,255,255,0.7)',
    marginTop: 4,
    textAlign: 'center',
  },
  teamMemberCard: {
    backgroundColor: 'rgba(255,255,255,0.1)',
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.1)',
  },
  teamMemberHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  teamMemberNumber: {
    fontSize: 14,
    fontWeight: '600',
    color: '#C9A962',
  },
  teamInput: {
    backgroundColor: 'rgba(0,0,0,0.3)',
    borderRadius: 10,
    padding: 12,
    fontSize: 15,
    color: colors.text,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.1)',
  },
  addMemberButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#007AFF',
    borderStyle: 'dashed',
    gap: 8,
    marginTop: 4,
  },
  addMemberText: {
    color: '#007AFF',
    fontSize: 15,
    fontWeight: '500',
  },
  inviteSuccessMessage: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(52, 199, 89, 0.2)',
    padding: 12,
    borderRadius: 12,
    marginTop: 16,
    gap: 8,
  },
  inviteSuccessText: {
    color: '#34C759',
    fontSize: 15,
    fontWeight: '600',
  },
  skipInviteLink: {
    alignItems: 'center',
    padding: 16,
    marginTop: 8,
  },
  skipInviteLinkText: {
    color: 'rgba(255,255,255,0.5)',
    fontSize: 14,
    textDecorationLine: 'underline',
  },
  sendInvitesButton: {
    backgroundColor: '#007AFF',
    paddingHorizontal: 20,
  },
});
