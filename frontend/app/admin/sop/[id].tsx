import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  Animated,
  Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { useAuthStore } from '../../../store/authStore';
import api from '../../../services/api';

import { useThemeStore } from '../../../store/themeStore';
export default function SOPDetailScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const user = useAuthStore((state) => state.user);
  
  const [sop, setSop] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [currentStep, setCurrentStep] = useState(0);
  const [isCompleted, setIsCompleted] = useState(false);
  const [nextSop, setNextSop] = useState<any>(null);
  
  const scrollRef = useRef<ScrollView>(null);
  const progressAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    loadSOP();
    loadNextSOP();
  }, [id]);

  useEffect(() => {
    if (sop?.steps?.length) {
      Animated.timing(progressAnim, {
        toValue: ((currentStep + 1) / sop.steps.length) * 100,
        duration: 300,
        useNativeDriver: false,
      }).start();
    }
  }, [currentStep, sop]);

  const loadSOP = async () => {
    try {
      const headers = { 'X-User-ID': user?._id };
      const res = await api.get(`/sop/${id}`, { headers });
      setSop(res.data);
      setCurrentStep(res.data.current_step || 0);
      setIsCompleted(res.data.is_completed || false);
    } catch (error) {
      console.error('Failed to load SOP:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const loadNextSOP = async () => {
    try {
      const headers = { 'X-User-ID': user?._id };
      const res = await api.get('/sop/', { headers });
      const sops = res.data;
      
      // Find the current SOP's index and get the next one
      const currentIndex = sops.findIndex((s: any) => s._id === id);
      if (currentIndex >= 0 && currentIndex < sops.length - 1) {
        // Find next incomplete SOP
        const nextIncomplete = sops.slice(currentIndex + 1).find((s: any) => !s.is_completed);
        if (nextIncomplete) {
          setNextSop(nextIncomplete);
        }
      }
    } catch (error) {
      console.error('Failed to load next SOP:', error);
    }
  };

  const updateProgress = async (step: number, completed: boolean = false) => {
    try {
      const headers = { 'X-User-ID': user?._id };
      await api.post(`/sop/${id}/progress?current_step=${step}&completed=${completed}`, {}, { headers });
      
      if (completed) {
        setIsCompleted(true);
      }
    } catch (error) {
      console.error('Failed to update progress:', error);
    }
  };

  const handleNextStep = () => {
    if (!sop?.steps?.length) return;
    
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    
    if (currentStep < sop.steps.length - 1) {
      const nextStep = currentStep + 1;
      setCurrentStep(nextStep);
      updateProgress(nextStep);
      scrollRef.current?.scrollTo({ y: 0, animated: true });
    } else if (!isCompleted) {
      // Mark as completed
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      updateProgress(currentStep, true);
    } else {
      // Already completed - navigate to next SOP or back to list
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
      if (nextSop) {
        router.replace(`/admin/sop/${nextSop._id}` as any);
      } else {
        router.back();
      }
    }
  };

  const handlePrevStep = () => {
    if (currentStep > 0) {
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
      setCurrentStep(currentStep - 1);
      scrollRef.current?.scrollTo({ y: 0, animated: true });
    }
  };

  const handleLink = (url: string) => {
    if (url.startsWith('/')) {
      router.push(url as any);
    } else {
      Linking.openURL(url);
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
        </View>
      </SafeAreaView>
    );
  }

  if (!sop) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.errorContainer}>
          <Ionicons name="alert-circle" size={64} color="#FF3B30" />
          <Text style={styles.errorText}>SOP not found</Text>
          <TouchableOpacity onPress={() => router.back()} style={styles.backButtonAlt}>
            <Text style={styles.backButtonText}>Go Back</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  const step = sop.steps?.[currentStep];
  const isLastStep = currentStep === (sop.steps?.length || 0) - 1;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <View style={styles.headerCenter}>
          <Text style={styles.headerTitle} numberOfLines={1}>{sop.title}</Text>
          <Text style={styles.headerSubtitle}>
            Step {currentStep + 1} of {sop.steps?.length || 0}
          </Text>
        </View>
        <View style={{ width: 40 }} />
      </View>
      
      {/* Progress Bar */}
      <View style={styles.progressContainer}>
        <Animated.View
          style={[
            styles.progressBar,
            {
              width: progressAnim.interpolate({
                inputRange: [0, 100],
                outputRange: ['0%', '100%'],
              }),
            },
          ]}
        />
      </View>
      
      {/* Step Content */}
      <ScrollView
        ref={scrollRef}
        style={styles.content}
        contentContainerStyle={styles.contentContainer}
        showsVerticalScrollIndicator={false}
      >
        {step && (
          <>
            {/* Step Title */}
            <View style={styles.stepHeader}>
              <View style={styles.stepNumber}>
                <Text style={styles.stepNumberText}>{step.order}</Text>
              </View>
              <Text style={styles.stepTitle}>{step.title}</Text>
            </View>
            
            {/* Step Description */}
            <Text style={styles.stepDescription}>{step.description}</Text>
            
            {/* Tip Box */}
            {step.tip && (
              <View style={styles.tipBox}>
                <Ionicons name="bulb" size={20} color="#FFD60A" />
                <Text style={styles.tipText}>{step.tip}</Text>
              </View>
            )}
            
            {/* Warning Box */}
            {step.warning && (
              <View style={styles.warningBox}>
                <Ionicons name="warning" size={20} color="#FF3B30" />
                <Text style={styles.warningText}>{step.warning}</Text>
              </View>
            )}
            
            {/* Link Button */}
            {step.link_url && (
              <TouchableOpacity
                style={styles.linkButton}
                onPress={() => handleLink(step.link_url)}
              >
                <Ionicons name="open-outline" size={18} color="#007AFF" />
                <Text style={styles.linkButtonText}>
                  {step.link_text || 'Open Link'}
                </Text>
              </TouchableOpacity>
            )}
          </>
        )}
        
        {/* Related SOPs */}
        {isLastStep && sop.related_sops_details?.length > 0 && (
          <View style={styles.relatedSection}>
            <Text style={styles.relatedTitle}>Related Training</Text>
            {sop.related_sops_details.map((related: any) => (
              <TouchableOpacity
                key={related._id}
                style={styles.relatedCard}
                onPress={() => router.push(`/admin/sop/${related._id}`)}
              >
                <Ionicons name="document-text" size={20} color={colors.textSecondary} />
                <Text style={styles.relatedText}>{related.title}</Text>
                <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
              </TouchableOpacity>
            ))}
          </View>
        )}
        
        {/* Completion */}
        {isCompleted && isLastStep && (
          <View style={styles.completionBox}>
            <Ionicons name="checkmark-circle" size={48} color="#34C759" />
            <Text style={styles.completionTitle}>Training Complete!</Text>
            <Text style={styles.completionText}>
              You've finished reading this SOP
            </Text>
          </View>
        )}
      </ScrollView>
      
      {/* Navigation Buttons */}
      <View style={styles.navigation}>
        <TouchableOpacity
          style={[styles.navButton, styles.navButtonSecondary, currentStep === 0 && styles.navButtonDisabled]}
          onPress={handlePrevStep}
          disabled={currentStep === 0}
        >
          <Ionicons name="chevron-back" size={20} color={currentStep === 0 ? colors.borderLight : '#FFF'} />
          <Text style={[styles.navButtonText, currentStep === 0 && styles.navButtonTextDisabled]}>
            Previous
          </Text>
        </TouchableOpacity>
        
        <TouchableOpacity
          style={[styles.navButton, styles.navButtonPrimary]}
          onPress={handleNextStep}
        >
          <Text style={styles.navButtonTextPrimary}>
            {isLastStep 
              ? (isCompleted 
                  ? (nextSop ? 'Continue' : 'Done') 
                  : 'Complete')
              : 'Next'}
          </Text>
          <Ionicons
            name={isLastStep 
              ? (isCompleted 
                  ? (nextSop ? 'arrow-forward' : 'checkmark') 
                  : 'checkmark-circle') 
              : 'chevron-forward'}
            size={20}
            color={colors.text}
          />
        </TouchableOpacity>
      </View>
    </SafeAreaView>
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
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 40,
  },
  errorText: {
    fontSize: 19,
    color: colors.textSecondary,
    marginTop: 16,
    marginBottom: 24,
  },
  backButtonAlt: {
    paddingHorizontal: 24,
    paddingVertical: 12,
    backgroundColor: '#007AFF',
    borderRadius: 8,
  },
  backButtonText: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '600',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.card,
  },
  backButton: {
    padding: 4,
    width: 40,
  },
  headerCenter: {
    flex: 1,
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  headerSubtitle: {
    fontSize: 14,
    color: colors.textSecondary,
    marginTop: 2,
  },
  progressContainer: {
    height: 3,
    backgroundColor: colors.card,
  },
  progressBar: {
    height: 3,
    backgroundColor: '#007AFF',
  },
  content: {
    flex: 1,
  },
  contentContainer: {
    padding: 20,
    paddingBottom: 40,
  },
  stepHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 20,
  },
  stepNumber: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#007AFF',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  stepNumberText: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.text,
  },
  stepTitle: {
    fontSize: 22,
    fontWeight: '700',
    color: colors.text,
    flex: 1,
  },
  stepDescription: {
    fontSize: 18,
    color: '#E5E5E7',
    lineHeight: 26,
    marginBottom: 20,
  },
  tipBox: {
    flexDirection: 'row',
    backgroundColor: '#FFD60A15',
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#FFD60A30',
  },
  tipText: {
    fontSize: 16,
    color: '#FFD60A',
    marginLeft: 12,
    flex: 1,
    lineHeight: 22,
  },
  warningBox: {
    flexDirection: 'row',
    backgroundColor: '#FF3B3015',
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#FF3B3030',
  },
  warningText: {
    fontSize: 16,
    color: '#FF3B30',
    marginLeft: 12,
    flex: 1,
    lineHeight: 22,
  },
  linkButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#007AFF20',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 8,
    alignSelf: 'flex-start',
    marginBottom: 16,
  },
  linkButtonText: {
    fontSize: 17,
    color: '#007AFF',
    fontWeight: '600',
    marginLeft: 8,
  },
  relatedSection: {
    marginTop: 32,
    paddingTop: 24,
    borderTopWidth: 1,
    borderTopColor: colors.card,
  },
  relatedTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 12,
  },
  relatedCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    padding: 16,
    borderRadius: 10,
    marginBottom: 8,
  },
  relatedText: {
    fontSize: 17,
    color: colors.text,
    flex: 1,
    marginLeft: 12,
  },
  completionBox: {
    alignItems: 'center',
    marginTop: 32,
    paddingTop: 32,
    borderTopWidth: 1,
    borderTopColor: colors.card,
  },
  completionTitle: {
    fontSize: 22,
    fontWeight: '700',
    color: '#34C759',
    marginTop: 16,
  },
  completionText: {
    fontSize: 17,
    color: colors.textSecondary,
    marginTop: 8,
  },
  navigation: {
    flexDirection: 'row',
    padding: 16,
    gap: 12,
    borderTopWidth: 1,
    borderTopColor: colors.card,
  },
  navButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
    borderRadius: 10,
    gap: 6,
  },
  navButtonPrimary: {
    backgroundColor: '#007AFF',
  },
  navButtonSecondary: {
    backgroundColor: colors.card,
  },
  navButtonDisabled: {
    opacity: 0.5,
  },
  navButtonText: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  navButtonTextPrimary: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  navButtonTextDisabled: {
    color: colors.borderLight,
  },
});
