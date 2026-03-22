import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Linking,
  Image,
  ActivityIndicator,
  Platform,
  TextInput,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams } from 'expo-router';
import api from '../../services/api';
import { trackCustomerAction } from '../../services/tracking';
import { PoweredByFooter } from '../../components/PoweredByFooter';

const REVIEW_PLATFORMS = [
  { key: 'google', name: 'Google', icon: 'logo-google', color: '#4285F4', bgColor: '#F0F5FF' },
  { key: 'yelp', name: 'Yelp', icon: 'star', color: '#D32323', bgColor: '#FFF0F0' },
  { key: 'facebook', name: 'Facebook', icon: 'logo-facebook', color: '#1877F2', bgColor: '#EFF4FE' },
  { key: 'dealerrater', name: 'DealerRater', icon: 'car-sport', color: '#00A0E3', bgColor: '#EBF8FD' },
  { key: 'cars_com', name: 'Cars.com', icon: 'car', color: '#8E44AD', bgColor: '#F5EEFA' },
];

export default function PublicReviewPage() {
  const { storeSlug, sp, cid } = useLocalSearchParams();
  const [loading, setLoading] = useState(true);
  const [storeData, setStoreData] = useState<any>(null);
  const [fbRating, setFbRating] = useState(0);
  const [fbName, setFbName] = useState('');
  const [fbText, setFbText] = useState('');
  const [fbSubmitted, setFbSubmitted] = useState(false);
  const [fbSubmitting, setFbSubmitting] = useState(false);

  // Tracking helper
  const track = (action: string, extra?: Record<string, any>) => {
    if (sp) {
      trackCustomerAction('review', action, {
        salesperson_id: sp as string,
        contact_id: (cid as string) || undefined,
        ...extra,
      });
    }
  };

  useEffect(() => {
    loadStoreData();
  }, [storeSlug]);

  const loadStoreData = async () => {
    try {
      const params = new URLSearchParams();
      if (sp) params.set('sp', sp as string);
      if (cid) params.set('cid', cid as string);
      const qs = params.toString() ? `?${params.toString()}` : '';
      const response = await api.get(`/review/page/${storeSlug}${qs}`);
      setStoreData(response.data);
    } catch (error) {
      console.error('Error loading store:', error);
    } finally {
      setLoading(false);
    }
  };

  const handlePlatformClick = async (platform: string, url: string) => {
    // Track the click via universal tracking
    track('review_link_clicked', { platform, url });
    // Also track via the legacy per-store endpoint
    try {
      await api.post(`/review/track-click/${storeSlug}`, {
        platform,
        salesperson_id: sp || null,
        url,
      });
    } catch (e) {
      // Don't block the redirect if tracking fails
    }
    // Use direct navigation on web to avoid popup blockers
    if (Platform.OS === 'web') {
      window.location.href = url;
    } else {
      Linking.openURL(url);
    }
  };

  const handleSubmitFeedback = async () => {
    if (fbRating === 0) return;
    setFbSubmitting(true);
    track('review_submitted', { metadata: { rating: fbRating } });
    try {
      await api.post(`/review/submit/${storeSlug}`, {
        customer_name: fbName.trim() || 'Anonymous',
        rating: fbRating,
        text_review: fbText.trim() || null,
        salesperson_id: sp || null,
        salesperson_name: storeData?.salesperson?.name || null,
      });
      setFbSubmitted(true);
    } catch (e) {
      console.error('Feedback error:', e);
    } finally {
      setFbSubmitting(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#007AFF" />
      </View>
    );
  }

  if (!storeData) {
    return (
      <View style={styles.errorContainer}>
        <View style={styles.errorCard}>
          <Ionicons name="alert-circle-outline" size={48} color="#CBD5E1" />
          <Text style={styles.errorTitle}>Page Not Found</Text>
          <Text style={styles.errorText}>This review page doesn't exist or has been removed.</Text>
        </View>
      </View>
    );
  }

  const { store, review_links, salesperson, brand_kit } = storeData;
  const displayName = brand_kit?.company_name || store.name;
  const logoUrl = brand_kit?.logo_url || store.logo_url;
  const primaryColor = brand_kit?.primary_color || store.primary_color || '#007AFF';

  const activeLinks = REVIEW_PLATFORMS.filter(
    p => review_links?.[p.key]?.trim()
  );
  const customLinks = review_links?.custom || [];

  return (
    <View style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.pageWrapper}>
          {/* Logo */}
          <View style={styles.logoSection}>
            {logoUrl ? (
              <Image
                source={{ uri: logoUrl }}
                style={styles.logo}
                resizeMode="contain"
                data-testid="review-page-logo"
              />
            ) : (
              <View style={[styles.logoPlaceholder, { backgroundColor: primaryColor + '15' }]}>
                <Ionicons name="business" size={32} color={primaryColor} />
              </View>
            )}
          </View>

          {/* Main Content Card */}
          <View style={styles.card} data-testid="review-page-card">
            <Text style={styles.storeName} data-testid="review-store-name">{displayName}</Text>
            <Text style={styles.subtitle}>
              We'd love your feedback! Tap a site below to leave a review.
            </Text>

            {salesperson?.name && (
              <View style={styles.salespersonBadge}>
                <Ionicons name="person-circle-outline" size={16} color="#64748B" />
                <Text style={styles.salespersonText}>Assisted by {salesperson.name}</Text>
              </View>
            )}

            {/* Divider */}
            <View style={styles.divider} />

            {/* Review Links */}
            <View style={styles.linksContainer}>
              {activeLinks.map((platform) => (
                <TouchableOpacity
                  key={platform.key}
                  style={styles.linkButton}
                  onPress={() => handlePlatformClick(platform.key, review_links[platform.key])}
                  activeOpacity={0.7}
                  data-testid={`review-link-${platform.key}`}
                >
                  <View style={[styles.linkIconBox, { backgroundColor: platform.bgColor }]}>
                    <Ionicons name={platform.icon as any} size={20} color={platform.color} />
                  </View>
                  <Text style={styles.linkText}>{platform.name}</Text>
                  <Ionicons name="arrow-forward" size={18} color="#94A3B8" />
                </TouchableOpacity>
              ))}

              {customLinks.map((link: { name: string; url: string }, i: number) => (
                <TouchableOpacity
                  key={`custom-${i}`}
                  style={styles.linkButton}
                  onPress={() => handlePlatformClick(`custom_${link.name}`, link.url)}
                  activeOpacity={0.7}
                  data-testid={`review-custom-${i}`}
                >
                  <View style={[styles.linkIconBox, { backgroundColor: '#F1F5F9' }]}>
                    <Ionicons name="link" size={20} color="#475569" />
                  </View>
                  <Text style={styles.linkText}>{link.name}</Text>
                  <Ionicons name="arrow-forward" size={18} color="#94A3B8" />
                </TouchableOpacity>
              ))}
            </View>

            {activeLinks.length === 0 && customLinks.length === 0 && (
              <View style={styles.emptyState}>
                <Ionicons name="link-outline" size={32} color="#CBD5E1" />
                <Text style={styles.emptyText}>No review links configured yet.</Text>
              </View>
            )}

            {/* Store Info */}
            {(store.phone || store.website) && (
              <View style={styles.storeInfo}>
                {store.phone && (
                  <TouchableOpacity
                    style={styles.storeInfoRow}
                    onPress={() => Linking.openURL(`tel:${store.phone}`)}
                    data-testid="review-store-phone"
                  >
                    <Ionicons name="call-outline" size={14} color="#94A3B8" />
                    <Text style={styles.storeInfoText}>{store.phone}</Text>
                  </TouchableOpacity>
                )}
                {store.website && (
                  <TouchableOpacity
                    style={styles.storeInfoRow}
                    onPress={() => Linking.openURL(store.website)}
                    data-testid="review-store-website"
                  >
                    <Ionicons name="globe-outline" size={14} color="#94A3B8" />
                    <Text style={styles.storeInfoText}>{store.website.replace(/^https?:\/\//, '')}</Text>
                  </TouchableOpacity>
                )}
                {store.address && (
                  <View style={styles.storeInfoRow}>
                    <Ionicons name="location-outline" size={14} color="#94A3B8" />
                    <Text style={styles.storeInfoText}>
                      {store.address}{store.city ? `, ${store.city}` : ''}{store.state ? `, ${store.state}` : ''}
                    </Text>
                  </View>
                )}
              </View>
            )}
          </View>

          {/* Direct Feedback Card */}
          <View style={styles.feedbackCard} data-testid="feedback-section">
            {fbSubmitted ? (
              <View style={styles.feedbackSuccess}>
                <Ionicons name="checkmark-circle" size={36} color="#22C55E" />
                <Text style={styles.feedbackSuccessTitle}>Thank you!</Text>
                <Text style={styles.feedbackSuccessText}>Your feedback has been submitted.</Text>
              </View>
            ) : (
              <>
                <Text style={styles.feedbackHeading}>Or leave us direct feedback</Text>
                <View style={styles.starRow} data-testid="feedback-stars">
                  {[1, 2, 3, 4, 5].map((star) => (
                    <TouchableOpacity key={star} onPress={() => setFbRating(star)} data-testid={`fb-star-${star}`}>
                      <Ionicons
                        name={star <= fbRating ? 'star' : 'star-outline'}
                        size={32}
                        color={star <= fbRating ? '#FBBF24' : '#CBD5E1'}
                      />
                    </TouchableOpacity>
                  ))}
                </View>

                {fbRating > 0 && (
                  <>
                    <TextInput
                      style={styles.feedbackInput}
                      placeholder="Your name (optional)"
                      placeholderTextColor="#94A3B8"
                      value={fbName}
                      onChangeText={setFbName}
                      data-testid="fb-name-input"
                    />
                    <TextInput
                      style={[styles.feedbackInput, styles.feedbackTextArea]}
                      placeholder="Tell us about your experience..."
                      placeholderTextColor="#94A3B8"
                      value={fbText}
                      onChangeText={setFbText}
                      multiline
                      numberOfLines={3}
                      data-testid="fb-text-input"
                    />
                    <TouchableOpacity
                      style={[styles.feedbackSubmitBtn, { backgroundColor: primaryColor }]}
                      onPress={handleSubmitFeedback}
                      disabled={fbSubmitting}
                      data-testid="fb-submit-btn"
                    >
                      {fbSubmitting ? (
                        <ActivityIndicator size="small" color="#FFF" />
                      ) : (
                        <Text style={styles.feedbackSubmitText}>Submit Feedback</Text>
                      )}
                    </TouchableOpacity>
                  </>
                )}
              </>
            )}
          </View>

          {/* Footer */}
          <PoweredByFooter />
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F8FAFC',
  },
  loadingContainer: {
    flex: 1,
    backgroundColor: '#F8FAFC',
    justifyContent: 'center',
    alignItems: 'center',
  },
  errorContainer: {
    flex: 1,
    backgroundColor: '#F8FAFC',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  errorCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 40,
    alignItems: 'center',
    maxWidth: 360,
    width: '100%',
    ...(Platform.OS === 'web' ? {
      boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
    } : {
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 1 },
      shadowOpacity: 0.06,
      shadowRadius: 3,
      elevation: 2,
    }),
  },
  errorTitle: {
    fontSize: 19,
    fontWeight: '600',
    color: '#1E293B',
    marginTop: 16,
  },
  errorText: {
    fontSize: 16,
    color: '#94A3B8',
    marginTop: 6,
    textAlign: 'center',
    lineHeight: 20,
  },
  scrollContent: {
    flexGrow: 1,
    alignItems: 'center',
    paddingVertical: 48,
    paddingHorizontal: 20,
    ...(Platform.OS === 'web' ? { minHeight: '100vh' } : {}),
  },
  pageWrapper: {
    width: '100%',
    maxWidth: 420,
    alignItems: 'center',
  },
  logoSection: {
    marginBottom: 24,
    alignItems: 'center',
  },
  logo: {
    width: 72,
    height: 72,
    borderRadius: 16,
    backgroundColor: 'transparent',
  },
  logoPlaceholder: {
    width: 72,
    height: 72,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  card: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    paddingVertical: 32,
    paddingHorizontal: 28,
    width: '100%',
    ...(Platform.OS === 'web' ? {
      boxShadow: '0 1px 4px rgba(0,0,0,0.06), 0 8px 24px rgba(0,0,0,0.04)',
    } : {
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 4 },
      shadowOpacity: 0.06,
      shadowRadius: 16,
      elevation: 4,
    }),
  },
  storeName: {
    fontSize: 22,
    fontWeight: '700',
    color: '#0F172A',
    textAlign: 'center',
    letterSpacing: -0.3,
  },
  subtitle: {
    fontSize: 17,
    color: '#64748B',
    textAlign: 'center',
    marginTop: 8,
    lineHeight: 22,
  },
  salespersonBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 12,
    gap: 6,
    backgroundColor: '#F8FAFC',
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 20,
    alignSelf: 'center',
  },
  salespersonText: {
    fontSize: 15,
    color: '#64748B',
  },
  divider: {
    height: 1,
    backgroundColor: '#F1F5F9',
    marginVertical: 24,
  },
  linksContainer: {
    gap: 10,
  },
  linkButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E2E8F0',
    borderRadius: 14,
    paddingVertical: 14,
    paddingHorizontal: 16,
    ...(Platform.OS === 'web' ? {
      cursor: 'pointer',
      transition: 'background-color 0.15s ease, border-color 0.15s ease',
    } : {}),
  },
  linkIconBox: {
    width: 40,
    height: 40,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  linkText: {
    flex: 1,
    fontSize: 18,
    fontWeight: '600',
    color: '#1E293B',
    marginLeft: 14,
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 32,
  },
  emptyText: {
    fontSize: 16,
    color: '#94A3B8',
    marginTop: 10,
  },
  storeInfo: {
    marginTop: 24,
    paddingTop: 20,
    borderTopWidth: 1,
    borderTopColor: '#F1F5F9',
    gap: 8,
  },
  storeInfoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
  },
  storeInfoText: {
    fontSize: 15,
    color: '#94A3B8',
  },
  feedbackCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    paddingVertical: 28,
    paddingHorizontal: 24,
    width: '100%',
    marginTop: 16,
    ...(Platform.OS === 'web' ? {
      boxShadow: '0 1px 4px rgba(0,0,0,0.06), 0 8px 24px rgba(0,0,0,0.04)',
    } : {
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 4 },
      shadowOpacity: 0.06,
      shadowRadius: 16,
      elevation: 4,
    }),
  },
  feedbackHeading: {
    fontSize: 17,
    fontWeight: '600',
    color: '#334155',
    textAlign: 'center',
    marginBottom: 16,
  },
  starRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 6,
    marginBottom: 12,
  },
  feedbackInput: {
    backgroundColor: '#F8FAFC',
    borderRadius: 10,
    padding: 14,
    fontSize: 17,
    color: '#1E293B',
    borderWidth: 1,
    borderColor: '#E2E8F0',
    marginBottom: 10,
  },
  feedbackTextArea: {
    height: 80,
    textAlignVertical: 'top',
    paddingTop: 14,
  },
  feedbackSubmitBtn: {
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 4,
  },
  feedbackSubmitText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFF',
  },
  feedbackSuccess: {
    alignItems: 'center',
    paddingVertical: 12,
  },
  feedbackSuccessTitle: {
    fontSize: 19,
    fontWeight: '700',
    color: '#1E293B',
    marginTop: 10,
  },
  feedbackSuccessText: {
    fontSize: 16,
    color: '#64748B',
    marginTop: 4,
  },
  footer: {
    flexDirection: 'row',
    marginTop: 32,
    alignItems: 'center',
  },
  footerText: {
    fontSize: 14,
    color: '#CBD5E1',
  },
  footerBrand: {
    fontWeight: '700',
    color: '#94A3B8',
  },
  footerUrl: {
    fontSize: 14,
    color: '#94A3B8',
  },
});
