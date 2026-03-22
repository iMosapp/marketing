import React, { useState, useMemo, useRef, useEffect } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView, Animated,
  Platform, useWindowDimensions,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { ImosHeader, ImosFooter } from './_components';
import { getOnboardingSlidesForRole, ORG_ADMIN_SLIDES, STORE_MANAGER_SLIDES, SALESPERSON_SLIDES } from '../onboarding/slideLibraries';
import type { OnboardingSlide } from '../onboarding/types';

const ROLE_OPTIONS = [
  { id: 'super_admin', label: 'Super Admin', icon: 'shield', color: '#FF3B30', description: 'Full platform access, org management', slideCount: ORG_ADMIN_SLIDES.length },
  { id: 'org_admin', label: 'Org Admin', icon: 'business', color: '#007AFF', description: 'Organization oversight, store management', slideCount: ORG_ADMIN_SLIDES.length },
  { id: 'store_manager', label: 'Store Manager', icon: 'storefront', color: '#34C759', description: 'Team leadership, store performance', slideCount: STORE_MANAGER_SLIDES.length },
  { id: 'user', label: 'Salesperson', icon: 'person', color: '#FF9500', description: 'RMS tools, AI assistant, customer mgmt', slideCount: SALESPERSON_SLIDES.length },
  { id: 'individual', label: 'Individual', icon: 'person-circle', color: '#AF52DE', description: 'Independent user, no org affiliation', slideCount: SALESPERSON_SLIDES.length },
];

export default function OnboardingPreviewScreen() {
  const router = useRouter();
  const { width: screenW } = useWindowDimensions();
  const isDesktop = screenW > 768;
  const maxW = isDesktop ? 700 : undefined;
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

  const handleNext = () => { if (currentSlide < slides.length - 1) animateToSlide(currentSlide + 1); };
  const handleBack = () => { if (currentSlide > 0) animateToSlide(currentSlide - 1); };
  const exitPreview = () => { setSelectedRole(null); setCurrentSlide(0); };

  // Keyboard nav for desktop
  useEffect(() => {
    if (Platform.OS !== 'web' || !selectedRole) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight') handleNext();
      if (e.key === 'ArrowLeft') handleBack();
      if (e.key === 'Escape') exitPreview();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [selectedRole, currentSlide, slides.length]);

  // Role selection screen
  if (!selectedRole) {
    return (
      <View style={s.container}>
        <ImosHeader />
        <ScrollView contentContainerStyle={s.scroll} showsVerticalScrollIndicator={false}>
          <View style={maxW ? { maxWidth: maxW, alignSelf: 'center', width: '100%' } : undefined}>

            <View style={s.titleSection}>
              <Text style={s.label}>ONBOARDING</Text>
              <Text style={[s.title, isDesktop && { fontSize: 36 }]}>Onboarding Preview</Text>
              <Text style={s.subtitle}>Walk through the exact onboarding experience each role sees when they first sign up.</Text>
            </View>

            <View style={s.infoCard}>
              <Ionicons name="eye-outline" size={24} color="#007AFF" />
              <View style={{ flex: 1 }}>
                <Text style={s.infoTitle}>Preview Mode</Text>
                <Text style={s.infoDesc}>No data will be created or modified. See exactly what your team experiences.</Text>
              </View>
            </View>

            <View style={isDesktop ? s.roleGridDesktop : undefined}>
              {ROLE_OPTIONS.map((role) => (
                <TouchableOpacity
                  key={role.id}
                  style={[s.roleCard, isDesktop && { width: '48%' }]}
                  onPress={() => { setSelectedRole(role.id); setCurrentSlide(0); }}
                  activeOpacity={0.7}
                  data-testid={`role-${role.id}`}
                >
                  <View style={[s.roleIcon, { backgroundColor: `${role.color}20` }]}>
                    <Ionicons name={role.icon as any} size={24} color={role.color} />
                  </View>
                  <View style={s.roleInfo}>
                    <Text style={s.roleName}>{role.label}</Text>
                    <Text style={s.roleDesc}>{role.description}</Text>
                    <Text style={s.roleSlideCount}>{role.slideCount} onboarding steps</Text>
                  </View>
                  <View style={s.playBtn}>
                    <Ionicons name="play" size={18} color="#007AFF" />
                  </View>
                </TouchableOpacity>
              ))}
            </View>

          </View>
          <ImosFooter />
        </ScrollView>
      </View>
    );
  }

  // Slide walkthrough screen (fullscreen, no header/footer)
  const currentRoleOption = ROLE_OPTIONS.find(r => r.id === selectedRole);

  return (
    <View style={s.previewContainer}>
      {slide && <LinearGradient colors={slide.bgGradient as any} style={StyleSheet.absoluteFill} />}

      {/* Preview Banner */}
      <View style={[s.previewBanner, { paddingTop: Platform.OS === 'web' ? 20 : 56 }]}>
        <TouchableOpacity onPress={exitPreview} style={s.exitBtn} data-testid="exit-preview">
          <Ionicons name="close" size={20} color="#1D1D1F" />
        </TouchableOpacity>
        <View style={s.previewBannerCenter}>
          <View style={[s.previewBadge, { backgroundColor: `${currentRoleOption?.color}30` }]}>
            <Ionicons name={currentRoleOption?.icon as any} size={14} color={currentRoleOption?.color} />
            <Text style={[s.previewBadgeText, { color: currentRoleOption?.color }]}>{currentRoleOption?.label}</Text>
          </View>
          <Text style={s.previewLabel}>PREVIEW MODE</Text>
        </View>
        <View style={{ width: 36 }} />
      </View>

      {/* Progress */}
      <View style={s.progressRow}>
        <View style={s.progressTrack}>
          <View style={[s.progressFill, { width: `${progress * 100}%` }]} />
        </View>
        <Text style={s.progressText}>{currentSlide + 1}/{slides.length}</Text>
      </View>

      {/* Slide Content */}
      {slide && (
        <ScrollView contentContainerStyle={s.slideScroll} showsVerticalScrollIndicator={false}>
          <Animated.View style={[s.slideContent, { opacity: fadeAnim }, isDesktop && { maxWidth: 640, alignSelf: 'center', width: '100%' }]}>
            <View style={[s.iconCircle, { backgroundColor: `${slide.iconColor}15` }]}>
              <Ionicons name={slide.icon as any} size={48} color={slide.iconColor} />
            </View>
            <Text style={s.slideTitle}>{slide.title}</Text>
            {slide.subtitle && <Text style={[s.slideSubtitle, { color: slide.iconColor }]}>{slide.subtitle}</Text>}
            <Text style={s.slideDesc}>{slide.description}</Text>

            <View style={s.typeBadge}>
              <Text style={s.typeBadgeText}>
                {slide.type === 'welcome' ? 'Welcome' : slide.type === 'feature' ? 'Feature Tour' : slide.type === 'ai_setup' ? 'AI Setup' : slide.type === 'interactive' ? 'Interactive' : slide.type === 'team_invite' ? 'Team Invite' : slide.type === 'complete' ? 'Completion' : slide.type}
              </Text>
            </View>

            {slide.benefits && (
              <View style={s.benefitsList}>
                {slide.benefits.map((b: string, i: number) => (
                  <View key={i} style={s.benefitRow}>
                    <Ionicons name="checkmark-circle" size={18} color="#34C759" />
                    <Text style={s.benefitText}>{b}</Text>
                  </View>
                ))}
              </View>
            )}

            {slide.interactiveType && (
              <View style={s.interactiveNote}>
                <Ionicons name="hand-left-outline" size={18} color="#FF9500" />
                <Text style={s.interactiveNoteText}>
                  {slide.interactiveType === 'choice' ? 'User picks a communication style' : slide.interactiveType === 'multi_input' ? 'User fills in profile fields' : slide.interactiveType === 'import' ? 'User can import contacts' : slide.interactiveType === 'team_invite' ? `User invites their ${slide.inviteTitle || 'team'}` : 'Interactive step'}
                </Text>
              </View>
            )}

            {slide.demoComponent && (
              <View style={s.demoNote}>
                <Ionicons name="phone-portrait-outline" size={18} color="#007AFF" />
                <Text style={s.demoNoteText}>Live demo: {slide.demoComponent === 'ai_clone' ? 'AI Chat Assistant' : slide.demoComponent === 'ai_suggestions' ? 'AI Response Suggestions' : slide.demoComponent === 'congrats_card' ? 'Congrats Card Builder' : slide.demoComponent === 'digital_card' ? 'Digital Business Card' : slide.demoComponent === 'voice_to_text' ? 'Voice-to-Text' : slide.demoComponent === 'campaigns' ? 'Campaign Timeline' : slide.demoComponent === 'analytics' ? 'Analytics Dashboard' : slide.demoComponent}</Text>
              </View>
            )}

            {slide.choices && (
              <View style={s.choicesPreview}>
                <Text style={s.choicesLabel}>Options presented:</Text>
                {slide.choices.map((c: any, i: number) => (
                  <View key={i} style={s.choiceRow}>
                    <Ionicons name={c.icon as any} size={16} color={slide.iconColor} />
                    <Text style={s.choiceText}>{c.label}  - {c.description}</Text>
                  </View>
                ))}
              </View>
            )}

            {slide.inputFields && (
              <View style={s.choicesPreview}>
                <Text style={s.choicesLabel}>Fields presented:</Text>
                {slide.inputFields.map((f: any, i: number) => (
                  <View key={i} style={s.choiceRow}>
                    <Ionicons name="create-outline" size={16} color="#8E8E93" />
                    <Text style={s.choiceText}>{f.label}: <Text style={{ color: '#AEAEB2', fontStyle: 'italic' }}>{f.placeholder}</Text></Text>
                  </View>
                ))}
              </View>
            )}
          </Animated.View>
        </ScrollView>
      )}

      {/* Navigation */}
      <View style={s.navBar}>
        <View style={s.navRow}>
          <TouchableOpacity style={[s.navBtn, currentSlide === 0 && { opacity: 0.3 }]} onPress={handleBack} disabled={currentSlide === 0} data-testid="prev-slide">
            <Ionicons name="chevron-back" size={22} color="#1D1D1F" />
            <Text style={s.navBtnText}>Back</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[s.navBtnPrimary, currentSlide === slides.length - 1 && { backgroundColor: '#34C759' }]} onPress={currentSlide === slides.length - 1 ? exitPreview : handleNext} data-testid="next-slide">
            <Text style={s.navBtnPrimaryText}>{currentSlide === slides.length - 1 ? 'Done' : 'Next'}</Text>
            <Ionicons name={currentSlide === slides.length - 1 ? 'checkmark' : 'chevron-forward'} size={18} color="#000" />
          </TouchableOpacity>
        </View>
        <View style={s.dotsRow}>
          {slides.map((_: any, i: number) => (
            <TouchableOpacity key={i} onPress={() => animateToSlide(i)}>
              <View style={[s.dot, i === currentSlide && s.dotActive, i < currentSlide && s.dotDone]} />
            </TouchableOpacity>
          ))}
        </View>
        {Platform.OS === 'web' && <Text style={s.keyHint}>Use arrow keys to navigate</Text>}
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  scroll: { paddingBottom: 0 },
  titleSection: { alignItems: 'center', paddingTop: 40, paddingBottom: 24, paddingHorizontal: 20 },
  label: { fontSize: 13, fontWeight: '700', color: '#007AFF', letterSpacing: 2, marginBottom: 12 },
  title: { fontSize: 28, fontWeight: '800', color: '#1D1D1F', marginBottom: 8, textAlign: 'center' },
  subtitle: { fontSize: 17, color: '#8E8E93', textAlign: 'center', lineHeight: 22, maxWidth: 420 },
  infoCard: { flexDirection: 'row', alignItems: 'flex-start', gap: 12, backgroundColor: '#007AFF12', borderRadius: 12, padding: 14, marginHorizontal: 16, marginBottom: 20, borderWidth: 1, borderColor: '#007AFF30' },
  infoTitle: { fontSize: 17, fontWeight: '600', color: '#007AFF', marginBottom: 4 },
  infoDesc: { fontSize: 15, color: '#8E8E93', lineHeight: 19 },
  roleGridDesktop: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, paddingHorizontal: 16 },
  roleCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#F5F5F7', borderRadius: 14, padding: 16, marginBottom: 10, marginHorizontal: 16, borderWidth: 1, borderColor: 'rgba(0,0,0,0.06)' },
  roleIcon: { width: 48, height: 48, borderRadius: 14, alignItems: 'center', justifyContent: 'center', marginRight: 14 },
  roleInfo: { flex: 1 },
  roleName: { fontSize: 18, fontWeight: '600', color: '#1D1D1F' },
  roleDesc: { fontSize: 15, color: '#8E8E93', marginTop: 2 },
  roleSlideCount: { fontSize: 14, color: '#6E6E73', marginTop: 4 },
  playBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: '#007AFF18', alignItems: 'center', justifyContent: 'center' },
  // Slide preview
  previewContainer: { flex: 1, backgroundColor: '#FFFFFF' },
  previewBanner: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 8, zIndex: 10 },
  exitBtn: { width: 32, height: 32, borderRadius: 16, backgroundColor: 'rgba(0,0,0,0.06)', alignItems: 'center', justifyContent: 'center' },
  previewBannerCenter: { flex: 1, alignItems: 'center' },
  previewBadge: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  previewBadgeText: { fontSize: 15, fontWeight: '600' },
  previewLabel: { fontSize: 12, color: '#86868B', fontWeight: '700', letterSpacing: 1, marginTop: 3 },
  progressRow: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 20, paddingTop: 8, gap: 12 },
  progressTrack: { flex: 1, height: 4, backgroundColor: 'rgba(0,0,0,0.06)', borderRadius: 2, overflow: 'hidden' },
  progressFill: { height: '100%', backgroundColor: '#007AFF', borderRadius: 2 },
  progressText: { color: '#6E6E73', fontSize: 15, fontWeight: '500' },
  slideScroll: { flexGrow: 1, paddingBottom: 20 },
  slideContent: { alignItems: 'center', paddingHorizontal: 24, paddingTop: 24 },
  iconCircle: { width: 88, height: 88, borderRadius: 44, alignItems: 'center', justifyContent: 'center', marginBottom: 18 },
  slideTitle: { fontSize: 22, fontWeight: '700', color: '#1D1D1F', textAlign: 'center', marginBottom: 4 },
  slideSubtitle: { fontSize: 16, fontWeight: '600', textAlign: 'center', marginBottom: 10 },
  slideDesc: { fontSize: 16, color: '#3A3A3C', textAlign: 'center', lineHeight: 21, maxWidth: 340, marginBottom: 16 },
  typeBadge: { backgroundColor: 'rgba(0,0,0,0.06)', paddingHorizontal: 12, paddingVertical: 5, borderRadius: 8, marginBottom: 16 },
  typeBadgeText: { fontSize: 13, color: '#6E6E73', fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.5 },
  benefitsList: { width: '100%', maxWidth: 340, gap: 8 },
  benefitRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  benefitText: { fontSize: 16, color: '#1D1D1F', fontWeight: '500', flex: 1 },
  interactiveNote: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: 'rgba(255,149,0,0.12)', borderRadius: 10, padding: 12, marginTop: 16, width: '100%', maxWidth: 340 },
  interactiveNoteText: { fontSize: 15, color: '#FF9500', flex: 1 },
  demoNote: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: 'rgba(0,122,255,0.12)', borderRadius: 10, padding: 12, marginTop: 12, width: '100%', maxWidth: 340 },
  demoNoteText: { fontSize: 15, color: '#007AFF', flex: 1 },
  choicesPreview: { width: '100%', maxWidth: 340, marginTop: 16 },
  choicesLabel: { fontSize: 15, fontWeight: '600', color: '#8E8E93', marginBottom: 8 },
  choiceRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  choiceText: { fontSize: 15, color: '#3A3A3C', flex: 1 },
  navBar: { paddingHorizontal: 20, paddingBottom: Platform.OS === 'web' ? 20 : 40, backgroundColor: '#FFFFFF', borderTopWidth: 1, borderTopColor: '#F0F0F5' },
  navRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 },
  navBtn: { flexDirection: 'row', alignItems: 'center', paddingVertical: 12, paddingHorizontal: 8, minWidth: 80 },
  navBtnText: { color: '#1D1D1F', fontSize: 18, marginLeft: 4 },
  navBtnPrimary: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', backgroundColor: '#007AFF', paddingVertical: 12, paddingHorizontal: 24, borderRadius: 24, gap: 4 },
  navBtnPrimaryText: { color: '#FFF', fontSize: 18, fontWeight: '600' },
  dotsRow: { flexDirection: 'row', justifyContent: 'center', gap: 5 },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: 'rgba(0,0,0,0.08)' },
  dotActive: { backgroundColor: '#007AFF', width: 16 },
  dotDone: { backgroundColor: '#34C759' },
  keyHint: { textAlign: 'center', fontSize: 13, color: '#D1D1D6', marginTop: 8 },
});
