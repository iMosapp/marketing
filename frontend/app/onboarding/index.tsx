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
          <Text style={demoStyles.salesmanName}>— John Smith</Text>
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
            <Ionicons name="person" size={28} color="#FFF" />
          </View>
          <View>
            <Text style={demoStyles.cardName}>John Smith</Text>
            <Text style={demoStyles.cardTitle}>Sales Consultant</Text>
          </View>
        </View>
        <View style={demoStyles.qrContainer}>
          <View style={demoStyles.qrCode}>
            <Ionicons name="qr-code" size={60} color="#000" />
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
          <Ionicons name="mic" size={32} color="#FFF" />
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

// ============================================
// MAIN COMPONENT
// ============================================

export default function OnboardingScreen() {
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
          <Ionicons name="cloud-upload" size={20} color="#FFF" />
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

          {/* Description */}
          <Text style={styles.description}>{currentSlide.description}</Text>

          {/* Demo Component */}
          {renderDemoComponent()}

          {/* Benefits */}
          {currentSlide.type !== 'ai_setup' && !currentSlide.demoComponent && renderBenefits()}

          {/* Interactive Content */}
          {renderInteractiveContent()}
        </Animated.View>
      </ScrollView>

      {/* Navigation */}
      <SafeAreaView edges={['bottom']} style={styles.navContainer}>
        <View style={styles.navButtons}>
          {currentIndex > 0 ? (
            <TouchableOpacity style={styles.backButton} onPress={handleBack}>
              <Ionicons name="chevron-back" size={24} color="#FFF" />
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
            ]}
            onPress={handleNext}
            disabled={!canProceed() || completing}
          >
            {completing ? (
              <ActivityIndicator size="small" color="#000" />
            ) : (
              <>
                <Text style={[styles.nextButtonText, isLastSlide && styles.completeButtonText]}>
                  {isLastSlide ? "Let's Go!" : 'Continue'}
                </Text>
                {!isLastSlide && <Ionicons name="chevron-forward" size={20} color="#000" />}
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
    color: '#FFF',
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
    color: '#FFF',
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
    color: '#FFF',
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
    color: '#FFF',
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
    color: '#FFF',
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
    color: '#FFF',
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
    color: '#FFF',
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
    backgroundColor: '#FFF',
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
    color: '#FFF',
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
    color: '#FFF',
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
    color: '#FFF',
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
    color: '#FFF',
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
    color: '#FFF',
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

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
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
    color: '#FFF',
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
    color: '#FFF',
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
    color: '#FFF',
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
    color: '#FFF',
    marginBottom: 8,
  },
  textInput: {
    backgroundColor: 'rgba(255,255,255,0.1)',
    borderRadius: 12,
    padding: 14,
    fontSize: 15,
    color: '#FFF',
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
    color: '#FFF',
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
    color: '#FFF',
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
    color: '#000',
    fontSize: 16,
    fontWeight: '600',
  },
  completeButton: {
    backgroundColor: '#34C759',
    paddingHorizontal: 32,
  },
  completeButtonText: {
    color: '#FFF',
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
});
