import React, { useState, useMemo, useRef, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Animated,
  Dimensions,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { getOnboardingSlidesForRole, ORG_ADMIN_SLIDES, STORE_MANAGER_SLIDES, SALESPERSON_SLIDES } from '../onboarding/slideLibraries';
import { OnboardingSlide } from '../onboarding/types';

const { width } = Dimensions.get('window');

const ROLE_OPTIONS = [
  { id: 'super_admin', label: 'Super Admin', icon: 'shield', color: '#FF3B30', description: 'Full platform access, org management', slideCount: ORG_ADMIN_SLIDES.length },
  { id: 'org_admin', label: 'Org Admin', icon: 'business', color: '#007AFF', description: 'Organization oversight, store management', slideCount: ORG_ADMIN_SLIDES.length },
  { id: 'store_manager', label: 'Store Manager', icon: 'storefront', color: '#34C759', description: 'Team leadership, store performance', slideCount: STORE_MANAGER_SLIDES.length },
  { id: 'user', label: 'Salesperson', icon: 'person', color: '#FF9500', description: 'RMS tools, AI assistant, customer mgmt', slideCount: SALESPERSON_SLIDES.length },
  { id: 'individual', label: 'Individual', icon: 'person-circle', color: '#AF52DE', description: 'Independent user, no org affiliation', slideCount: SALESPERSON_SLIDES.length },
];

export default function OnboardingPreviewScreen() {
  const router = useRouter();
  const [selectedRole, setSelectedRole] = useState<string | null>(null);
  const [currentSlide, setCurrentSlide] = useState(0);
  const fadeAnim = useRef(new Animated.Value(1)).current;

  const slides = useMemo(() => {
    if (!selectedRole) return [];
    return getOnboardingSlidesForRole(selectedRole);
  }, [selectedRole]);

  const slide = slides[currentSlide];
  const progress = slides.length > 0 ? (currentSlide + 1) / slides.length : 0;

  const animateToSlide = (newIndex: number) => {
    Animated.timing(fadeAnim, { toValue: 0, duration: 100, useNativeDriver: true }).start(() => {
      setCurrentSlide(newIndex);
      Animated.timing(fadeAnim, { toValue: 1, duration: 150, useNativeDriver: true }).start();
    });
  };

  const handleNext = () => {
    if (currentSlide < slides.length - 1) animateToSlide(currentSlide + 1);
  };

  const handleBack = () => {
    if (currentSlide > 0) animateToSlide(currentSlide - 1);
  };

  const exitPreview = () => {
    setSelectedRole(null);
    setCurrentSlide(0);
  };

  // Role Selection Screen
  if (!selectedRole) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backBtn} data-testid="back-button">
            <Ionicons name="chevron-back" size={28} color="#007AFF" />
          </TouchableOpacity>
          <View style={styles.headerCenter}>
            <Text style={styles.headerTitle}>Onboarding Preview</Text>
            <Text style={styles.headerSubtitle}>See what each role experiences</Text>
          </View>
          <View style={{ width: 36 }} />
        </View>

        <ScrollView contentContainerStyle={styles.roleScrollContent}>
          <View style={styles.infoCard}>
            <Ionicons name="eye-outline" size={24} color="#C9A962" />
            <View style={{ flex: 1 }}>
              <Text style={styles.infoTitle}>Preview Mode</Text>
              <Text style={styles.infoDesc}>Walk through the exact onboarding experience each role sees when they first sign up. No data will be created or modified.</Text>
            </View>
          </View>

          {ROLE_OPTIONS.map((role) => (
            <TouchableOpacity
              key={role.id}
              style={styles.roleCard}
              onPress={() => { setSelectedRole(role.id); setCurrentSlide(0); }}
              activeOpacity={0.7}
              data-testid={`role-${role.id}`}
            >
              <View style={[styles.roleIcon, { backgroundColor: `${role.color}20` }]}>
                <Ionicons name={role.icon as any} size={24} color={role.color} />
              </View>
              <View style={styles.roleInfo}>
                <Text style={styles.roleName}>{role.label}</Text>
                <Text style={styles.roleDesc}>{role.description}</Text>
                <Text style={styles.roleSlideCount}>{role.slideCount} onboarding steps</Text>
              </View>
              <View style={styles.playBtn}>
                <Ionicons name="play" size={18} color="#C9A962" />
              </View>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </SafeAreaView>
    );
  }

  // Slide Walkthrough Screen
  const currentRoleOption = ROLE_OPTIONS.find(r => r.id === selectedRole);

  return (
    <View style={styles.previewContainer}>
      {slide && (
        <LinearGradient colors={slide.bgGradient as any} style={StyleSheet.absoluteFill} />
      )}

      <SafeAreaView style={styles.previewSafe} edges={['top']}>
        {/* Preview Banner */}
        <View style={styles.previewBanner}>
          <TouchableOpacity onPress={exitPreview} style={styles.exitBtn} data-testid="exit-preview">
            <Ionicons name="close" size={20} color="#FFF" />
          </TouchableOpacity>
          <View style={styles.previewBannerCenter}>
            <View style={[styles.previewBadge, { backgroundColor: `${currentRoleOption?.color}30` }]}>
              <Ionicons name={currentRoleOption?.icon as any} size={14} color={currentRoleOption?.color} />
              <Text style={[styles.previewBadgeText, { color: currentRoleOption?.color }]}>{currentRoleOption?.label}</Text>
            </View>
            <Text style={styles.previewLabel}>PREVIEW MODE</Text>
          </View>
          <View style={{ width: 36 }} />
        </View>

        {/* Progress Bar */}
        <View style={styles.progressRow}>
          <View style={styles.progressTrack}>
            <View style={[styles.progressFill, { width: `${progress * 100}%` }]} />
          </View>
          <Text style={styles.progressText}>{currentSlide + 1}/{slides.length}</Text>
        </View>
      </SafeAreaView>

      {/* Slide Content */}
      {slide && (
        <ScrollView contentContainerStyle={styles.slideScroll} showsVerticalScrollIndicator={false}>
          <Animated.View style={[styles.slideContent, { opacity: fadeAnim }]}>
            {/* Icon */}
            <View style={[styles.iconCircle, { backgroundColor: `${slide.iconColor}15` }]}>
              <Ionicons name={slide.icon as any} size={48} color={slide.iconColor} />
            </View>

            {/* Title */}
            <Text style={styles.slideTitle}>{slide.title}</Text>
            {slide.subtitle && (
              <Text style={[styles.slideSubtitle, { color: slide.iconColor }]}>{slide.subtitle}</Text>
            )}
            <Text style={styles.slideDesc}>{slide.description}</Text>

            {/* Slide Type Badge */}
            <View style={styles.typeBadge}>
              <Text style={styles.typeBadgeText}>
                {slide.type === 'welcome' ? 'Welcome' :
                 slide.type === 'feature' ? 'Feature Tour' :
                 slide.type === 'ai_setup' ? 'AI Setup' :
                 slide.type === 'interactive' ? 'Interactive' :
                 slide.type === 'team_invite' ? 'Team Invite Step' :
                 slide.type === 'complete' ? 'Completion' : slide.type}
              </Text>
            </View>

            {/* Benefits */}
            {slide.benefits && (
              <View style={styles.benefitsList}>
                {slide.benefits.map((b, i) => (
                  <View key={i} style={styles.benefitRow}>
                    <Ionicons name="checkmark-circle" size={18} color="#34C759" />
                    <Text style={styles.benefitText}>{b}</Text>
                  </View>
                ))}
              </View>
            )}

            {/* Interactive Type Info */}
            {slide.interactiveType && (
              <View style={styles.interactiveNote}>
                <Ionicons name="hand-left-outline" size={18} color="#FF9500" />
                <Text style={styles.interactiveNoteText}>
                  {slide.interactiveType === 'choice' ? 'User picks a communication style' :
                   slide.interactiveType === 'multi_input' ? 'User fills in profile fields' :
                   slide.interactiveType === 'import' ? 'User can import contacts' :
                   slide.interactiveType === 'team_invite' ? `User invites their ${slide.inviteTitle || 'team'}` :
                   'Interactive step'}
                </Text>
              </View>
            )}

            {/* Demo Component Info */}
            {slide.demoComponent && (
              <View style={styles.demoNote}>
                <Ionicons name="phone-portrait-outline" size={18} color="#007AFF" />
                <Text style={styles.demoNoteText}>Live demo shown: {
                  slide.demoComponent === 'ai_clone' ? 'AI Chat Assistant' :
                  slide.demoComponent === 'ai_suggestions' ? 'AI Response Suggestions' :
                  slide.demoComponent === 'congrats_card' ? 'Congrats Card Builder' :
                  slide.demoComponent === 'digital_card' ? 'Digital Business Card' :
                  slide.demoComponent === 'voice_to_text' ? 'Voice-to-Text Demo' :
                  slide.demoComponent === 'campaigns' ? 'Campaign Timeline' :
                  slide.demoComponent === 'analytics' ? 'Analytics Dashboard' :
                  slide.demoComponent
                }</Text>
              </View>
            )}

            {/* Choices Info */}
            {slide.choices && (
              <View style={styles.choicesPreview}>
                <Text style={styles.choicesLabel}>Options presented:</Text>
                {slide.choices.map((c, i) => (
                  <View key={i} style={styles.choiceRow}>
                    <Ionicons name={c.icon as any} size={16} color={slide.iconColor} />
                    <Text style={styles.choiceText}>{c.label}  - {c.description}</Text>
                  </View>
                ))}
              </View>
            )}

            {/* Input Fields Info */}
            {slide.inputFields && (
              <View style={styles.fieldsPreview}>
                <Text style={styles.choicesLabel}>Fields presented:</Text>
                {slide.inputFields.map((f, i) => (
                  <View key={i} style={styles.fieldRow}>
                    <Ionicons name="create-outline" size={16} color="#8E8E93" />
                    <Text style={styles.fieldText}>{f.label}: <Text style={styles.fieldPlaceholder}>{f.placeholder}</Text></Text>
                  </View>
                ))}
              </View>
            )}
          </Animated.View>
        </ScrollView>
      )}

      {/* Navigation */}
      <SafeAreaView edges={['bottom']} style={styles.navBar}>
        <View style={styles.navRow}>
          <TouchableOpacity
            style={[styles.navBtn, currentSlide === 0 && { opacity: 0.3 }]}
            onPress={handleBack}
            disabled={currentSlide === 0}
            data-testid="prev-slide"
          >
            <Ionicons name="chevron-back" size={22} color="#FFF" />
            <Text style={styles.navBtnText}>Back</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.navBtnPrimary, currentSlide === slides.length - 1 && { backgroundColor: '#34C759' }]}
            onPress={currentSlide === slides.length - 1 ? exitPreview : handleNext}
            data-testid="next-slide"
          >
            <Text style={styles.navBtnPrimaryText}>
              {currentSlide === slides.length - 1 ? 'Done' : 'Next'}
            </Text>
            <Ionicons
              name={currentSlide === slides.length - 1 ? 'checkmark' : 'chevron-forward'}
              size={18}
              color="#000"
            />
          </TouchableOpacity>
        </View>

        {/* Dots */}
        <View style={styles.dotsRow}>
          {slides.map((_, i) => (
            <TouchableOpacity key={i} onPress={() => animateToSlide(i)}>
              <View style={[
                styles.dot,
                i === currentSlide && styles.dotActive,
                i < currentSlide && styles.dotDone,
              ]} />
            </TouchableOpacity>
          ))}
        </View>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#1C1C1E',
  },
  backBtn: { padding: 4 },
  headerCenter: { flex: 1, alignItems: 'center' },
  headerTitle: { fontSize: 17, fontWeight: '600', color: '#FFF' },
  headerSubtitle: { fontSize: 12, color: '#6E6E73', marginTop: 2 },
  roleScrollContent: { padding: 16, paddingBottom: 40 },
  infoCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
    backgroundColor: '#C9A96212',
    borderRadius: 12,
    padding: 14,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#C9A96230',
  },
  infoTitle: { fontSize: 15, fontWeight: '600', color: '#C9A962', marginBottom: 4 },
  infoDesc: { fontSize: 13, color: '#8E8E93', lineHeight: 19 },
  roleCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 14,
    padding: 16,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: '#2C2C2E',
  },
  roleIcon: { width: 48, height: 48, borderRadius: 14, alignItems: 'center', justifyContent: 'center', marginRight: 14 },
  roleInfo: { flex: 1 },
  roleName: { fontSize: 16, fontWeight: '600', color: '#FFF' },
  roleDesc: { fontSize: 13, color: '#8E8E93', marginTop: 2 },
  roleSlideCount: { fontSize: 12, color: '#6E6E73', marginTop: 4 },
  playBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#C9A96218',
    alignItems: 'center',
    justifyContent: 'center',
  },
  // Preview Screen
  previewContainer: { flex: 1 },
  previewSafe: { zIndex: 10 },
  previewBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  exitBtn: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: 'rgba(255,255,255,0.15)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  previewBannerCenter: { flex: 1, alignItems: 'center' },
  previewBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
  },
  previewBadgeText: { fontSize: 13, fontWeight: '600' },
  previewLabel: { fontSize: 10, color: 'rgba(255,255,255,0.5)', fontWeight: '700', letterSpacing: 1, marginTop: 3 },
  progressRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingTop: 8,
    gap: 12,
  },
  progressTrack: {
    flex: 1,
    height: 4,
    backgroundColor: 'rgba(255,255,255,0.2)',
    borderRadius: 2,
    overflow: 'hidden',
  },
  progressFill: { height: '100%', backgroundColor: '#C9A962', borderRadius: 2 },
  progressText: { color: 'rgba(255,255,255,0.6)', fontSize: 13, fontWeight: '500' },
  // Slide
  slideScroll: { flexGrow: 1, paddingBottom: 20 },
  slideContent: { alignItems: 'center', paddingHorizontal: 24, paddingTop: 24 },
  iconCircle: {
    width: 88,
    height: 88,
    borderRadius: 44,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 18,
  },
  slideTitle: { fontSize: 22, fontWeight: '700', color: '#FFF', textAlign: 'center', marginBottom: 4 },
  slideSubtitle: { fontSize: 14, fontWeight: '600', textAlign: 'center', marginBottom: 10 },
  slideDesc: { fontSize: 14, color: 'rgba(255,255,255,0.85)', textAlign: 'center', lineHeight: 21, maxWidth: 340, marginBottom: 16 },
  typeBadge: {
    backgroundColor: 'rgba(255,255,255,0.1)',
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: 8,
    marginBottom: 16,
  },
  typeBadgeText: { fontSize: 11, color: 'rgba(255,255,255,0.6)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.5 },
  benefitsList: { width: '100%', maxWidth: 340, gap: 8 },
  benefitRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  benefitText: { fontSize: 14, color: '#FFF', fontWeight: '500', flex: 1 },
  interactiveNote: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: 'rgba(255,149,0,0.12)',
    borderRadius: 10,
    padding: 12,
    marginTop: 16,
    width: '100%',
    maxWidth: 340,
  },
  interactiveNoteText: { fontSize: 13, color: '#FF9500', flex: 1 },
  demoNote: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: 'rgba(0,122,255,0.12)',
    borderRadius: 10,
    padding: 12,
    marginTop: 12,
    width: '100%',
    maxWidth: 340,
  },
  demoNoteText: { fontSize: 13, color: '#007AFF', flex: 1 },
  choicesPreview: { width: '100%', maxWidth: 340, marginTop: 16 },
  choicesLabel: { fontSize: 13, fontWeight: '600', color: '#8E8E93', marginBottom: 8 },
  choiceRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  choiceText: { fontSize: 13, color: 'rgba(255,255,255,0.8)', flex: 1 },
  fieldsPreview: { width: '100%', maxWidth: 340, marginTop: 16 },
  fieldRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 8, marginBottom: 6 },
  fieldText: { fontSize: 13, color: 'rgba(255,255,255,0.8)', flex: 1 },
  fieldPlaceholder: { color: 'rgba(255,255,255,0.4)', fontStyle: 'italic' },
  // Nav
  navBar: { paddingHorizontal: 20, paddingBottom: 8, backgroundColor: 'rgba(0,0,0,0.3)' },
  navRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 },
  navBtn: { flexDirection: 'row', alignItems: 'center', paddingVertical: 12, paddingHorizontal: 8, minWidth: 80 },
  navBtnText: { color: '#FFF', fontSize: 16, marginLeft: 4 },
  navBtnPrimary: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#C9A962',
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 24,
    gap: 4,
  },
  navBtnPrimaryText: { color: '#000', fontSize: 16, fontWeight: '600' },
  dotsRow: { flexDirection: 'row', justifyContent: 'center', gap: 5 },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: 'rgba(255,255,255,0.3)' },
  dotActive: { backgroundColor: '#C9A962', width: 16 },
  dotDone: { backgroundColor: '#34C759' },
});
