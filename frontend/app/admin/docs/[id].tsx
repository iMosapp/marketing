import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  Animated,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { useAuthStore } from '../../../store/authStore';
import api from '../../../services/api';

import { useThemeStore } from '../../../store/themeStore';
const CATEGORY_COLORS: Record<string, string> = {
  security: '#FF3B30',
  company_policy: '#5856D6',
  legal: '#007AFF',
  training: '#34C759',
  integrations: '#FF9500',
};

export default function DocViewerScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const user = useAuthStore((state) => state.user);

  const [doc, setDoc] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [currentSlide, setCurrentSlide] = useState(0);

  const scrollRef = useRef<ScrollView>(null);
  const progressAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    loadDoc();
  }, [id]);

  useEffect(() => {
    if (doc?.slides?.length) {
      Animated.timing(progressAnim, {
        toValue: ((currentSlide + 1) / doc.slides.length) * 100,
        duration: 300,
        useNativeDriver: false,
      }).start();
    }
  }, [currentSlide, doc]);

  const loadDoc = async () => {
    try {
      const headers = { 'X-User-ID': user?._id };
      const res = await api.get(`/docs/${id}`, { headers });
      setDoc(res.data);
    } catch (error) {
      console.error('Failed to load doc:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleNext = () => {
    if (!doc?.slides?.length) return;
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    if (currentSlide < doc.slides.length - 1) {
      setCurrentSlide(currentSlide + 1);
      scrollRef.current?.scrollTo({ y: 0, animated: true });
    } else {
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      router.back();
    }
  };

  const handlePrev = () => {
    if (currentSlide > 0) {
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
      setCurrentSlide(currentSlide - 1);
      scrollRef.current?.scrollTo({ y: 0, animated: true });
    }
  };

  const jumpToSlide = (index: number) => {
    setCurrentSlide(index);
    scrollRef.current?.scrollTo({ y: 0, animated: true });
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

  if (!doc) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.errorContainer}>
          <Ionicons name="alert-circle" size={64} color="#FF3B30" />
          <Text style={styles.errorText}>Document not found</Text>
          <TouchableOpacity onPress={() => router.back()} style={styles.errorButton}>
            <Text style={styles.errorButtonText}>Go Back</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  const slide = doc.slides?.[currentSlide];
  const isLastSlide = currentSlide === (doc.slides?.length || 0) - 1;
  const accentColor = CATEGORY_COLORS[doc.category] || '#007AFF';

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton} data-testid="doc-back-btn">
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <View style={styles.headerCenter}>
          <Text style={styles.headerTitle} numberOfLines={1}>{doc.title}</Text>
          <Text style={styles.headerSubtitle}>
            {currentSlide + 1} of {doc.slides?.length || 0}
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
              backgroundColor: accentColor,
              width: progressAnim.interpolate({
                inputRange: [0, 100],
                outputRange: ['0%', '100%'],
              }),
            },
          ]}
        />
      </View>

      {/* Slide Dots */}
      <View style={styles.dotsContainer}>
        {doc.slides?.map((_: any, i: number) => (
          <TouchableOpacity
            key={i}
            onPress={() => jumpToSlide(i)}
            style={[
              styles.dot,
              i === currentSlide && { backgroundColor: accentColor, width: 20 },
            ]}
          />
        ))}
      </View>

      {/* Slide Content */}
      <ScrollView
        ref={scrollRef}
        style={styles.content}
        contentContainerStyle={styles.contentContainer}
        showsVerticalScrollIndicator={false}
      >
        {slide && (
          <>
            {/* Slide Title */}
            <View style={styles.slideHeader}>
              <View style={[styles.slideNumber, { backgroundColor: accentColor }]}>
                <Text style={styles.slideNumberText}>{slide.order}</Text>
              </View>
              <Text style={styles.slideTitle}>{slide.title}</Text>
            </View>

            {/* Slide Description */}
            <View style={styles.slideDescriptionContainer}>
              {slide.description.split('\n').map((line: string, lineIdx: number) => {
                // Parse bold text: **text**
                const parts = line.split(/(\*\*[^*]+\*\*)/g);
                if (line.trim() === '') return <View key={lineIdx} style={{ height: 12 }} />;
                return (
                  <Text key={lineIdx} style={styles.slideDescription}>
                    {parts.map((part: string, partIdx: number) => {
                      if (part.startsWith('**') && part.endsWith('**')) {
                        return <Text key={partIdx} style={styles.boldText}>{part.slice(2, -2)}</Text>;
                      }
                      if (part.startsWith('```') || part.endsWith('```')) {
                        const code = part.replace(/```/g, '').trim();
                        if (!code) return null;
                        return <Text key={partIdx} style={styles.codeText}>{code}</Text>;
                      }
                      return part;
                    })}
                  </Text>
                );
              })}
            </View>

            {/* Tip Box */}
            {slide.tip && (
              <View style={styles.tipBox}>
                <Ionicons name="bulb" size={20} color="#FFD60A" />
                <Text style={styles.tipText}>{slide.tip}</Text>
              </View>
            )}

            {/* Warning Box */}
            {slide.warning && (
              <View style={styles.warningBox}>
                <Ionicons name="warning" size={20} color="#FF3B30" />
                <Text style={styles.warningText}>{slide.warning}</Text>
              </View>
            )}

            {/* Link Button */}
            {slide.link_url && (
              <TouchableOpacity style={styles.linkButton} onPress={() => router.push(slide.link_url)}>
                <Ionicons name="open-outline" size={18} color="#007AFF" />
                <Text style={styles.linkButtonText}>{slide.link_text || 'Open Link'}</Text>
              </TouchableOpacity>
            )}

            {/* End-of-doc info */}
            {isLastSlide && (
              <View style={styles.endBox}>
                <Ionicons name="checkmark-circle" size={40} color={accentColor} />
                <Text style={styles.endTitle}>End of Document</Text>
                {doc.version && (
                  <Text style={styles.endMeta}>Version {doc.version}</Text>
                )}
                {doc.last_reviewed && (
                  <Text style={styles.endMeta}>
                    Last reviewed: {new Date(doc.last_reviewed).toLocaleDateString()}
                  </Text>
                )}
                {doc.slug === 'imos-nda' && (
                  <TouchableOpacity
                    style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#007AFF', paddingVertical: 14, paddingHorizontal: 24, borderRadius: 12, marginTop: 16 }}
                    onPress={() => router.push('/admin/nda/create')}
                    data-testid="nda-prepare-send-btn"
                  >
                    <Ionicons name="send" size={18} color={colors.text} />
                    <Text style={{ fontSize: 15, fontWeight: '600', color: colors.text }}>Prepare & Send NDA</Text>
                  </TouchableOpacity>
                )}
              </View>
            )}
          </>
        )}
      </ScrollView>

      {/* Navigation */}
      <View style={styles.navigation}>
        <TouchableOpacity
          style={[styles.navButton, styles.navButtonSecondary, currentSlide === 0 && styles.navButtonDisabled]}
          onPress={handlePrev}
          disabled={currentSlide === 0}
          data-testid="doc-prev-btn"
        >
          <Ionicons name="chevron-back" size={20} color={currentSlide === 0 ? colors.borderLight : '#FFF'} />
          <Text style={[styles.navButtonText, currentSlide === 0 && styles.navButtonTextDisabled]}>
            Previous
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.navButton, { backgroundColor: accentColor }]}
          onPress={handleNext}
          data-testid="doc-next-btn"
        >
          <Text style={styles.navButtonTextPrimary}>
            {isLastSlide ? 'Done' : 'Next'}
          </Text>
          <Ionicons
            name={isLastSlide ? 'checkmark' : 'chevron-forward'}
            size={20}
            color={colors.text}
          />
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  errorContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingHorizontal: 40 },
  errorText: { fontSize: 18, color: colors.textSecondary, marginTop: 16, marginBottom: 24 },
  errorButton: { paddingHorizontal: 24, paddingVertical: 12, backgroundColor: '#007AFF', borderRadius: 8 },
  errorButtonText: { color: colors.text, fontSize: 16, fontWeight: '600' },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.card,
  },
  backButton: { padding: 4, width: 40 },
  headerCenter: { flex: 1, alignItems: 'center' },
  headerTitle: { fontSize: 16, fontWeight: '600', color: colors.text },
  headerSubtitle: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  progressContainer: { height: 3, backgroundColor: colors.card },
  progressBar: { height: 3 },
  dotsContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 12,
    gap: 6,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.surface,
  },
  content: { flex: 1 },
  contentContainer: { padding: 20, paddingBottom: 40 },
  slideHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: 20 },
  slideNumber: {
    width: 36,
    height: 36,
    borderRadius: 18,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  slideNumberText: { fontSize: 16, fontWeight: '700', color: colors.text },
  slideTitle: { fontSize: 22, fontWeight: '700', color: colors.text, flex: 1 },
  slideDescriptionContainer: { marginBottom: 20 },
  slideDescription: { fontSize: 16, color: '#E5E5E7', lineHeight: 26 },
  boldText: { fontWeight: '700', color: colors.text },
  codeText: { fontFamily: 'monospace', backgroundColor: colors.card, color: '#FF9500', fontSize: 13, paddingHorizontal: 4 },
  tipBox: {
    flexDirection: 'row',
    backgroundColor: '#FFD60A15',
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#FFD60A30',
  },
  tipText: { fontSize: 14, color: '#FFD60A', marginLeft: 12, flex: 1, lineHeight: 22 },
  warningBox: {
    flexDirection: 'row',
    backgroundColor: '#FF3B3015',
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#FF3B3030',
  },
  warningText: { fontSize: 14, color: '#FF3B30', marginLeft: 12, flex: 1, lineHeight: 22 },
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
  linkButtonText: { fontSize: 15, color: '#007AFF', fontWeight: '600', marginLeft: 8 },
  endBox: {
    alignItems: 'center',
    marginTop: 32,
    paddingTop: 32,
    borderTopWidth: 1,
    borderTopColor: colors.card,
  },
  endTitle: { fontSize: 20, fontWeight: '700', color: colors.text, marginTop: 12 },
  endMeta: { fontSize: 13, color: colors.textSecondary, marginTop: 4 },
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
  navButtonSecondary: { backgroundColor: colors.card },
  navButtonDisabled: { opacity: 0.5 },
  navButtonText: { fontSize: 16, fontWeight: '600', color: colors.text },
  navButtonTextPrimary: { fontSize: 16, fontWeight: '600', color: colors.text },
  navButtonTextDisabled: { color: colors.borderLight },
});
