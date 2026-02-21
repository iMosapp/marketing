import React, { useState, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Dimensions,
  Animated,
  ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';

const { width } = Dimensions.get('window');

type SlideType = 'welcome' | 'feature' | 'ai_setup' | 'interactive' | 'action' | 'complete';

interface OnboardingSlide {
  id: string;
  type: SlideType;
  title: string;
  subtitle?: string;
  description: string;
  icon: string;
  iconColor: string;
  bgGradient: string[];
  benefits?: string[];
  interactiveType?: 'choice' | 'input' | 'multi_input' | 'import';
  previewNote?: string;
}

const SLIDES: OnboardingSlide[] = [
  {
    id: 'welcome',
    type: 'welcome',
    title: 'Welcome to MVPLine!',
    subtitle: 'Your Virtual Partner Line',
    description: 'You\'re about to unlock something incredible - a personal AI assistant that works 24/7, sounds just like YOU, and helps you close more deals.',
    icon: 'rocket',
    iconColor: '#C9A962',
    bgGradient: ['#1A1A2E', '#16213E'],
    benefits: ['Never miss a lead again', 'AI that talks like YOU', 'Close deals while you sleep'],
  },
  {
    id: 'ai_intro',
    type: 'feature',
    title: 'Meet Your AI Clone',
    subtitle: 'The Magic Behind MVPLine',
    description: 'Your Virtual Assistant isn\'t just any chatbot. It learns YOUR personality, YOUR style, and responds to customers as if it\'s really you.',
    icon: 'sparkles',
    iconColor: '#AF52DE',
    bgGradient: ['#1A0F2E', '#2D1B4E'],
    benefits: ['Customers think they\'re talking to YOU', 'Never sounds robotic or generic', 'Gets smarter the more you use it'],
  },
  {
    id: 'ai_style',
    type: 'ai_setup',
    title: 'How Do You Talk?',
    subtitle: 'Set Your Communication Style',
    description: 'Help your AI match your vibe. Are you formal and professional, or casual and friendly?',
    icon: 'chatbubble-ellipses',
    iconColor: '#007AFF',
    bgGradient: ['#0F1A2E', '#1A2E4E'],
    interactiveType: 'choice',
    previewNote: 'User selects: Professional, Friendly & Warm, High Energy, or Laid Back',
  },
  {
    id: 'ai_bio',
    type: 'ai_setup',
    title: 'Tell Us About You',
    subtitle: 'The Secret Sauce',
    description: 'The more your AI knows, the more natural it sounds. Customers will swear they\'re talking to the real you!',
    icon: 'person',
    iconColor: '#FFD60A',
    bgGradient: ['#2E2A1A', '#1A1A1A'],
    interactiveType: 'multi_input',
    previewNote: 'User enters: Hobbies, Family Info, Fun Facts about themselves',
  },
  {
    id: 'ai_greeting',
    type: 'ai_setup',
    title: 'Your AI Introduction',
    subtitle: 'How Should Your VA Introduce Itself?',
    description: 'When a customer texts and you\'re busy, your AI jumps in. How should it greet them?',
    icon: 'hand-right',
    iconColor: '#34C759',
    bgGradient: ['#0F2E1A', '#1A2E1A'],
    interactiveType: 'choice',
    previewNote: 'User selects greeting style: As Your Assistant, As Your Team, or Helpful & Direct',
  },
  {
    id: 'ai_suggestions',
    type: 'feature',
    title: 'AI-Powered Responses',
    subtitle: 'Never Stuck on What to Say',
    description: 'Your AI suggests perfect responses based on the conversation. One tap and you\'re done - or customize it your way.',
    icon: 'bulb',
    iconColor: '#FF9500',
    bgGradient: ['#2E1F0F', '#1A1A1A'],
    benefits: ['Perfect responses in seconds', 'Sounds like YOU wrote it', 'Edit or send instantly'],
  },
  {
    id: 'congrats_cards',
    type: 'feature',
    title: 'Congrats Cards',
    subtitle: 'Make Every Customer Feel Special',
    description: 'Snap a photo with your customer, create a beautiful thank-you card, and send it instantly. They\'ll share it on social media - free advertising!',
    icon: 'gift',
    iconColor: '#FF2D55',
    bgGradient: ['#2E0F1A', '#1A1A1A'],
    benefits: ['Beautiful branded cards', 'Customers share on social', 'Free word-of-mouth marketing'],
  },
  {
    id: 'digital_card',
    type: 'feature',
    title: 'Digital Business Card',
    subtitle: 'Always in Their Pocket',
    description: 'One QR code, all your info. Customers scan it and have your contact, reviews, and referral link saved forever. No more lost cards!',
    icon: 'qr-code',
    iconColor: '#5856D6',
    bgGradient: ['#1A0F2E', '#1A1A2E'],
    benefits: ['Professional online presence', 'Reviews & referrals built-in', 'One scan saves everything'],
  },
  {
    id: 'voice_to_text',
    type: 'feature',
    title: 'Voice-to-Text Magic',
    subtitle: 'Talk, Don\'t Type',
    description: 'Tap the mic and speak naturally. Your words become perfectly written messages. Reply to customers between appointments or on the go!',
    icon: 'mic',
    iconColor: '#FF3B30',
    bgGradient: ['#2E0F0F', '#1A1A1A'],
    benefits: ['Hands-free messaging', 'Perfect transcription', 'Reply while driving (safely!)'],
  },
  {
    id: 'campaigns',
    type: 'feature',
    title: 'Automated Campaigns',
    subtitle: 'Set It and Forget It',
    description: 'After a sale, your AI automatically follows up - Day 1 check-in, Day 7 referral ask, Day 75 service reminder. You close deals, we handle follow-up.',
    icon: 'rocket',
    iconColor: '#007AFF',
    bgGradient: ['#0F1A2E', '#1A2E4E'],
    benefits: ['Automatic follow-ups', 'Birthday & holiday messages', 'Never forget a customer'],
  },
  {
    id: 'import_contacts',
    type: 'action',
    title: 'Import Your Contacts',
    subtitle: 'Bring Your Network',
    description: 'Import your entire phone contact list in seconds. Your AI will help you stay connected with everyone.',
    icon: 'people-circle',
    iconColor: '#34C759',
    bgGradient: ['#0F2E1A', '#1A2E1A'],
    interactiveType: 'import',
    previewNote: 'User can import contacts or skip to do later',
    benefits: ['One-tap import', 'Organize with tags', 'Never lose a contact'],
  },
  {
    id: 'analytics',
    type: 'feature',
    title: 'See Your MVP at Work',
    subtitle: 'Incredible Analytics',
    description: 'Watch your AI assistant in action! See how many leads it captured, messages it sent, and deals it helped close - all while you were busy.',
    icon: 'analytics',
    iconColor: '#5AC8FA',
    bgGradient: ['#0F1A2E', '#1A2E3E'],
    benefits: ['Messages sent while you slept', 'Leads captured automatically', 'ROI you can actually see'],
  },
  {
    id: 'complete',
    type: 'complete',
    title: 'You\'re All Set!',
    subtitle: 'Time to Close Some Deals',
    description: 'Your AI assistant is ready to work. The more you use MVPLine, the smarter it gets. Go show your customers what you\'re made of!',
    icon: 'checkmark-circle',
    iconColor: '#34C759',
    bgGradient: ['#0F2E1A', '#1A1A1A'],
    benefits: ['AI trained on YOUR style', 'All features unlocked', 'Support team ready to help'],
  },
];

export default function TrainingPreviewScreen() {
  const router = useRouter();
  const [currentIndex, setCurrentIndex] = useState(0);
  const fadeAnim = useRef(new Animated.Value(1)).current;
  
  const currentSlide = SLIDES[currentIndex];
  const isLastSlide = currentIndex === SLIDES.length - 1;
  const isFirstSlide = currentIndex === 0;
  const progress = (currentIndex + 1) / SLIDES.length;

  const animateToSlide = (newIndex: number) => {
    Animated.timing(fadeAnim, {
      toValue: 0,
      duration: 100,
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
    if (!isLastSlide) {
      animateToSlide(currentIndex + 1);
    }
  };

  const handleBack = () => {
    if (currentIndex > 0) {
      animateToSlide(currentIndex - 1);
    }
  };

  const renderBenefits = () => {
    if (!currentSlide.benefits) return null;
    return (
      <View style={styles.benefitsContainer}>
        {currentSlide.benefits.map((benefit, index) => (
          <View key={index} style={styles.benefitRow}>
            <Ionicons name="checkmark-circle" size={18} color="#34C759" />
            <Text style={styles.benefitText}>{benefit}</Text>
          </View>
        ))}
      </View>
    );
  };

  const renderPreviewNote = () => {
    if (!currentSlide.previewNote) return null;
    return (
      <View style={styles.previewNoteContainer}>
        <Ionicons name="information-circle" size={18} color="#8E8E93" />
        <Text style={styles.previewNoteText}>{currentSlide.previewNote}</Text>
      </View>
    );
  };

  const getSlideTypeLabel = () => {
    switch (currentSlide.type) {
      case 'welcome': return 'WELCOME';
      case 'feature': return 'FEATURE HIGHLIGHT';
      case 'ai_setup': return 'AI PERSONA SETUP (REQUIRED)';
      case 'action': return 'ACTION STEP';
      case 'complete': return 'COMPLETION';
      default: return '';
    }
  };

  return (
    <View style={styles.container}>
      <LinearGradient
        colors={currentSlide.bgGradient as any}
        style={StyleSheet.absoluteFill}
      />
      
      {/* Preview Mode Banner */}
      <SafeAreaView style={styles.safeArea} edges={['top']}>
        <View style={styles.previewBanner}>
          <Ionicons name="eye" size={16} color="#FFF" />
          <Text style={styles.previewBannerText}>ADMIN PREVIEW</Text>
          <TouchableOpacity style={styles.exitButton} onPress={() => router.back()}>
            <Text style={styles.exitButtonText}>Exit</Text>
            <Ionicons name="close" size={18} color="#FFF" />
          </TouchableOpacity>
        </View>
        
        {/* Progress Bar */}
        <View style={styles.progressContainer}>
          <View style={styles.progressTrack}>
            <Animated.View style={[styles.progressFill, { width: `${progress * 100}%` }]} />
          </View>
          <Text style={styles.progressText}>{currentIndex + 1}/{SLIDES.length}</Text>
        </View>

        {/* Slide Type Label */}
        <View style={styles.slideTypeContainer}>
          <Text style={[styles.slideTypeLabel, { color: currentSlide.iconColor }]}>
            {getSlideTypeLabel()}
          </Text>
        </View>
      </SafeAreaView>

      {/* Slide Content */}
      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        <Animated.View style={[styles.slideContent, { opacity: fadeAnim }]}>
          {/* Icon */}
          <View style={[styles.iconContainer, { backgroundColor: `${currentSlide.iconColor}15` }]}>
            <Ionicons name={currentSlide.icon as any} size={50} color={currentSlide.iconColor} />
          </View>

          {/* Title */}
          <Text style={styles.title}>{currentSlide.title}</Text>
          {currentSlide.subtitle && (
            <Text style={[styles.subtitle, { color: currentSlide.iconColor }]}>
              {currentSlide.subtitle}
            </Text>
          )}

          {/* Description */}
          <Text style={styles.description}>{currentSlide.description}</Text>

          {/* Preview Note for Interactive Slides */}
          {renderPreviewNote()}

          {/* Benefits */}
          {renderBenefits()}
        </Animated.View>
      </ScrollView>

      {/* Slide Thumbnails */}
      <View style={styles.thumbnailsWrapper}>
        <ScrollView 
          horizontal 
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.thumbnailsContainer}
        >
          {SLIDES.map((slide, index) => (
            <TouchableOpacity
              key={slide.id}
              style={[
                styles.thumbnail,
                index === currentIndex && styles.thumbnailActive,
                slide.type === 'ai_setup' && styles.thumbnailRequired,
              ]}
              onPress={() => animateToSlide(index)}
            >
              <Ionicons 
                name={slide.icon as any} 
                size={16} 
                color={index === currentIndex ? slide.iconColor : '#8E8E93'} 
              />
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>

      {/* Navigation */}
      <SafeAreaView edges={['bottom']} style={styles.navContainer}>
        <View style={styles.navButtons}>
          <TouchableOpacity 
            style={[styles.navButton, isFirstSlide && styles.navButtonDisabled]} 
            onPress={handleBack}
            disabled={isFirstSlide}
          >
            <Ionicons name="chevron-back" size={24} color={isFirstSlide ? '#3A3A3C' : '#FFF'} />
            <Text style={[styles.navButtonText, isFirstSlide && styles.navButtonTextDisabled]}>Back</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.navButton, isLastSlide && styles.navButtonDisabled]}
            onPress={handleNext}
            disabled={isLastSlide}
          >
            <Text style={[styles.navButtonText, isLastSlide && styles.navButtonTextDisabled]}>Next</Text>
            <Ionicons name="chevron-forward" size={24} color={isLastSlide ? '#3A3A3C' : '#FFF'} />
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
  },
  safeArea: {
    zIndex: 10,
  },
  previewBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FF9500',
    paddingVertical: 8,
    paddingHorizontal: 16,
    gap: 8,
  },
  previewBannerText: {
    color: '#FFF',
    fontSize: 13,
    fontWeight: '700',
    letterSpacing: 1,
    flex: 1,
  },
  exitButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(0,0,0,0.2)',
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 16,
    gap: 4,
  },
  exitButtonText: {
    color: '#FFF',
    fontSize: 14,
    fontWeight: '600',
  },
  progressContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingTop: 12,
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
  slideTypeContainer: {
    alignItems: 'center',
    paddingTop: 10,
  },
  slideTypeLabel: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1,
  },
  scrollContent: {
    flexGrow: 1,
    paddingBottom: 20,
  },
  slideContent: {
    flex: 1,
    alignItems: 'center',
    paddingHorizontal: 24,
    paddingTop: 24,
  },
  iconContainer: {
    width: 90,
    height: 90,
    borderRadius: 45,
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
  subtitle: {
    fontSize: 15,
    fontWeight: '600',
    textAlign: 'center',
    marginBottom: 14,
  },
  description: {
    fontSize: 14,
    color: 'rgba(255,255,255,0.85)',
    textAlign: 'center',
    lineHeight: 21,
    maxWidth: 340,
    marginBottom: 16,
  },
  previewNoteContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255,255,255,0.08)',
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 10,
    gap: 8,
    marginBottom: 16,
  },
  previewNoteText: {
    fontSize: 13,
    color: '#8E8E93',
    flex: 1,
    fontStyle: 'italic',
  },
  benefitsContainer: {
    width: '100%',
    maxWidth: 320,
    gap: 8,
  },
  benefitRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  benefitText: {
    fontSize: 14,
    color: '#FFF',
    fontWeight: '500',
  },
  thumbnailsWrapper: {
    paddingVertical: 8,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255,255,255,0.1)',
  },
  thumbnailsContainer: {
    paddingHorizontal: 16,
    gap: 8,
  },
  thumbnail: {
    width: 36,
    height: 36,
    borderRadius: 8,
    backgroundColor: 'rgba(255,255,255,0.1)',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 8,
  },
  thumbnailActive: {
    backgroundColor: 'rgba(255,255,255,0.2)',
    borderWidth: 2,
    borderColor: '#C9A962',
  },
  thumbnailRequired: {
    borderWidth: 1,
    borderColor: 'rgba(255,149,0,0.5)',
  },
  navContainer: {
    paddingHorizontal: 20,
    paddingBottom: 10,
  },
  navButtons: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: 8,
  },
  navButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    paddingHorizontal: 14,
    gap: 4,
  },
  navButtonDisabled: {
    opacity: 0.4,
  },
  navButtonText: {
    color: '#FFF',
    fontSize: 15,
    fontWeight: '500',
  },
  navButtonTextDisabled: {
    color: '#3A3A3C',
  },
});
