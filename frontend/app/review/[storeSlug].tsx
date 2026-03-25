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

function useHydrated() {
  const [h, setH] = useState(false);
  useEffect(() => setH(true), []);
  return h;
}

const REVIEW_PLATFORMS = [
  { key: 'google', name: 'Google', color: '#4285F4', bgColor: '#EBF3FF', letter: 'G' },
  { key: 'yelp', name: 'Yelp', color: '#D32323', bgColor: '#FFF0F0', letter: 'Y' },
  { key: 'facebook', name: 'Facebook', color: '#1877F2', bgColor: '#EFF4FE', letter: 'f' },
  { key: 'dealerrater', name: 'DealerRater', color: '#00A0E3', bgColor: '#EBF8FD', letter: 'DR' },
  { key: 'cars_com', name: 'Cars.com', color: '#8E44AD', bgColor: '#F5EEFA', letter: 'C' },
  { key: 'edmunds', name: 'Edmunds', color: '#1A73E8', bgColor: '#E8F0FE', letter: 'E' },
  { key: 'bbb', name: 'BBB', color: '#005A8C', bgColor: '#E6F0F7', letter: 'B' },
  { key: 'trustpilot', name: 'Trustpilot', color: '#00B67A', bgColor: '#E6F9F3', letter: 'T' },
];

export default function PublicReviewPage() {
  const hydrated = useHydrated();
  const { storeSlug, sp, cid } = useLocalSearchParams();
  const [loading, setLoading] = useState(true);
  const [storeData, setStoreData] = useState<any>(null);
  const [fbRating, setFbRating] = useState(0);
  const [fbName, setFbName] = useState('');
  const [fbText, setFbText] = useState('');
  const [fbSubmitted, setFbSubmitted] = useState(false);
  const [fbSubmitting, setFbSubmitting] = useState(false);

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

  const handlePlatformClick = async (platform: string, url: string | undefined) => {
    if (!url) return;
    track('review_link_clicked', { platform, url });
    try {
      await api.post(`/review/track-click/${storeSlug}`, {
        platform,
        salesperson_id: sp || null,
        url,
      });
    } catch {}
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

  if (!hydrated) return null;

  if (loading) {
    return (
      <View style={s.loadingContainer}>
        <ActivityIndicator size="large" color="#007AFF" />
      </View>
    );
  }

  if (!storeData) {
    return (
      <View style={s.errorContainer}>
        <View style={s.errorCard}>
          <Ionicons name="alert-circle-outline" size={48} color="#CBD5E1" />
          <Text style={s.errorTitle}>Page Not Found</Text>
          <Text style={s.errorText}>This review page doesn't exist or has been removed.</Text>
        </View>
      </View>
    );
  }

  const { store, review_links, salesperson, brand_kit } = storeData;
  const displayName = brand_kit?.company_name || store.name;
  const logoUrl = brand_kit?.logo_url || store.logo_url;
  const primaryColor = brand_kit?.primary_color || store.primary_color || '#007AFF';
  const bannerUrl = brand_kit?.banner_url || store.cover_image_url;

  // Show ALL platforms — configured ones are clickable, others shown for demo
  const configuredLinks = review_links || {};
  const customLinks = configuredLinks.custom || [];

  return (
    <View style={s.container}>
      <ScrollView contentContainerStyle={s.scrollContent} showsVerticalScrollIndicator={false}>
        <View style={s.pageWrapper}>

          {/* Clean header — white background, "Thank you for choosing" + logo */}
          <View style={s.heroClean} data-testid="review-hero-banner">
            <Text style={s.heroThankYou}>Thank you for choosing</Text>
            {logoUrl ? (
              Platform.OS === 'web' ? (
                <img src={logoUrl} style={{ height: 160, maxWidth: 320, objectFit: 'contain', display: 'block', marginTop: 8 } as any} />
              ) : (
                <Image source={{ uri: logoUrl }} style={{ height: 160, width: 320, marginTop: 8 }} resizeMode="contain" />
              )
            ) : (
              <Text style={s.heroStoreName}>{displayName}</Text>
            )}
          </View>

          {/* Main Review Card */}
          <View style={s.card} data-testid="review-page-card">
            {/* Invitation heading */}
            <View style={s.inviteSection}>
              {logoUrl && (
                <View style={s.inviteLogo}>
                  {Platform.OS === 'web' ? (
                    <img src={logoUrl} style={{ width: 28, height: 28, objectFit: 'contain', display: 'block' } as any} />
                  ) : (
                    <Image source={{ uri: logoUrl }} style={{ width: 28, height: 28 }} resizeMode="contain" />
                  )}
                </View>
              )}
              <Text style={s.inviteLabel}>{displayName}</Text>
            </View>

            <Text style={s.inviteTitle} data-testid="review-store-name">
              {displayName} has invited you to review their business
            </Text>
            <Text style={s.inviteSubtitle}>
              Submit your review on Google, or select a different review site
            </Text>

            {salesperson?.name && (
              <View style={s.spBadge}>
                <Ionicons name="person-circle-outline" size={15} color="#64748B" />
                <Text style={s.spBadgeText}>Assisted by {salesperson.name}</Text>
              </View>
            )}

            {/* Primary CTA — Google */}
            {(() => {
              const googleUrl = configuredLinks.google;
              return (
                <TouchableOpacity
                  style={[s.primaryBtn, { backgroundColor: '#4285F4' }]}
                  onPress={() => handlePlatformClick('google', googleUrl)}
                  activeOpacity={0.8}
                  data-testid="review-link-google"
                >
                  <View style={s.primaryBtnIcon}>
                    <Text style={{ fontSize: 18, fontWeight: '700', color: '#4285F4' }}>G</Text>
                  </View>
                  <Text style={s.primaryBtnText}>Continue with Google</Text>
                </TouchableOpacity>
              );
            })()}

            {/* Divider */}
            <View style={s.orRow}>
              <View style={s.orLine} />
              <Text style={s.orText}>or select a different site</Text>
              <View style={s.orLine} />
            </View>

            {/* All Platform Tiles */}
            <View style={s.platformGrid}>
              {REVIEW_PLATFORMS.filter(p => p.key !== 'google').map((platform) => {
                const url = configuredLinks[platform.key];
                const isConfigured = !!url?.trim();
                return (
                  <TouchableOpacity
                    key={platform.key}
                    style={[s.platformTile, !isConfigured && s.platformTileDisabled]}
                    onPress={() => isConfigured ? handlePlatformClick(platform.key, url) : null}
                    activeOpacity={isConfigured ? 0.7 : 1}
                    data-testid={`review-link-${platform.key}`}
                  >
                    <View style={[s.platformIcon, { backgroundColor: isConfigured ? platform.bgColor : '#F1F5F9' }]}>
                      <Text style={{ fontSize: platform.letter.length > 1 ? 12 : 16, fontWeight: '800', color: isConfigured ? platform.color : '#94A3B8' }}>
                        {platform.letter}
                      </Text>
                    </View>
                    <Text style={[s.platformName, !isConfigured && { color: '#94A3B8' }]}>{platform.name}</Text>
                    {!isConfigured && <Text style={s.comingSoon}>Coming soon</Text>}
                  </TouchableOpacity>
                );
              })}

              {customLinks.map((link: { name: string; url: string }, i: number) => (
                <TouchableOpacity
                  key={`custom-${i}`}
                  style={s.platformTile}
                  onPress={() => handlePlatformClick(`custom_${link.name}`, link.url)}
                  activeOpacity={0.7}
                  data-testid={`review-custom-${i}`}
                >
                  <View style={[s.platformIcon, { backgroundColor: '#F1F5F9' }]}>
                    <Ionicons name="link" size={18} color="#475569" />
                  </View>
                  <Text style={s.platformName}>{link.name}</Text>
                </TouchableOpacity>
              ))}
            </View>

            {/* Store Info */}
            {(store.phone || store.website) && (
              <View style={s.storeInfo}>
                {store.phone && (
                  <TouchableOpacity style={s.storeInfoRow} onPress={() => Linking.openURL(`tel:${store.phone}`)} data-testid="review-store-phone">
                    <Ionicons name="call-outline" size={13} color="#94A3B8" />
                    <Text style={s.storeInfoText}>{store.phone}</Text>
                  </TouchableOpacity>
                )}
                {store.website && (
                  <TouchableOpacity style={s.storeInfoRow} onPress={() => Linking.openURL(store.website)} data-testid="review-store-website">
                    <Ionicons name="globe-outline" size={13} color="#94A3B8" />
                    <Text style={s.storeInfoText}>{store.website.replace(/^https?:\/\//, '')}</Text>
                  </TouchableOpacity>
                )}
                {store.address && (
                  <View style={s.storeInfoRow}>
                    <Ionicons name="location-outline" size={13} color="#94A3B8" />
                    <Text style={s.storeInfoText}>
                      {store.address}{store.city ? `, ${store.city}` : ''}{store.state ? `, ${store.state}` : ''}
                    </Text>
                  </View>
                )}
              </View>
            )}
          </View>

          {/* Direct Feedback Card */}
          <View style={s.feedbackCard} data-testid="feedback-section">
            {fbSubmitted ? (
              <View style={s.fbSuccess}>
                <Ionicons name="checkmark-circle" size={36} color="#22C55E" />
                <Text style={s.fbSuccessTitle}>Thank you!</Text>
                <Text style={s.fbSuccessText}>Your feedback has been submitted.</Text>
              </View>
            ) : (
              <>
                <Text style={s.fbHeading}>Or leave us direct feedback</Text>
                <View style={s.starRow} data-testid="feedback-stars">
                  {[1, 2, 3, 4, 5].map((star) => (
                    <TouchableOpacity key={star} onPress={() => setFbRating(star)} data-testid={`fb-star-${star}`}>
                      <Ionicons name={star <= fbRating ? 'star' : 'star-outline'} size={32} color={star <= fbRating ? '#FBBF24' : '#CBD5E1'} />
                    </TouchableOpacity>
                  ))}
                </View>
                {fbRating > 0 && (
                  <>
                    <TextInput style={s.fbInput} placeholder="Your name (optional)" placeholderTextColor="#94A3B8" value={fbName} onChangeText={setFbName} data-testid="fb-name-input" />
                    <TextInput style={[s.fbInput, { height: 80, textAlignVertical: 'top', paddingTop: 14 }]} placeholder="Tell us about your experience..." placeholderTextColor="#94A3B8" value={fbText} onChangeText={setFbText} multiline numberOfLines={3} data-testid="fb-text-input" />
                    <TouchableOpacity style={[s.fbSubmitBtn, { backgroundColor: primaryColor }]} onPress={handleSubmitFeedback} disabled={fbSubmitting} data-testid="fb-submit-btn">
                      {fbSubmitting ? <ActivityIndicator size="small" color="#FFF" /> : <Text style={s.fbSubmitText}>Submit Feedback</Text>}
                    </TouchableOpacity>
                  </>
                )}
              </>
            )}
          </View>

          <PoweredByFooter />
        </View>
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  loadingContainer: { flex: 1, backgroundColor: '#FFFFFF', justifyContent: 'center', alignItems: 'center' },
  errorContainer: { flex: 1, backgroundColor: '#FFFFFF', justifyContent: 'center', alignItems: 'center', padding: 20 },
  errorCard: { backgroundColor: '#FFF', borderRadius: 16, padding: 40, alignItems: 'center', maxWidth: 360, width: '100%' },
  errorTitle: { fontSize: 19, fontWeight: '600', color: '#1E293B', marginTop: 16 },
  errorText: { fontSize: 16, color: '#94A3B8', marginTop: 6, textAlign: 'center' },

  scrollContent: { flexGrow: 1, alignItems: 'center', paddingTop: 0, paddingBottom: 48, paddingHorizontal: 16, ...(Platform.OS === 'web' ? { minHeight: '100vh' as any } : {}) },
  pageWrapper: { width: '100%', maxWidth: 440, alignItems: 'center' },

  // Clean header
  heroClean: { width: '100%', alignItems: 'center', paddingTop: 32, paddingBottom: 24, backgroundColor: '#FFFFFF' },
  heroThankYou: { fontSize: 17, color: '#64748B', fontWeight: '500' },
  heroStoreName: { fontSize: 24, fontWeight: '800', color: '#0F172A', marginTop: 8 },

  // Main card
  card: { backgroundColor: '#FFF', borderRadius: 20, paddingTop: 24, paddingBottom: 28, paddingHorizontal: 24, width: '100%', zIndex: 1, ...(Platform.OS === 'web' ? { boxShadow: '0 2px 12px rgba(0,0,0,0.08)' } : { shadowColor: '#000', shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.08, shadowRadius: 16, elevation: 4 }) },

  inviteSection: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, marginBottom: 12 },
  inviteLogo: { width: 28, height: 28 },
  inviteLabel: { fontSize: 14, fontWeight: '600', color: '#64748B' },
  inviteTitle: { fontSize: 22, fontWeight: '800', color: '#0F172A', textAlign: 'center', lineHeight: 28, letterSpacing: -0.3 },
  inviteSubtitle: { fontSize: 15, color: '#64748B', textAlign: 'center', marginTop: 8, lineHeight: 20 },
  spBadge: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', marginTop: 10, gap: 5, backgroundColor: '#F8FAFC', paddingHorizontal: 12, paddingVertical: 5, borderRadius: 20, alignSelf: 'center' },
  spBadgeText: { fontSize: 13, color: '#64748B' },

  // Primary CTA
  primaryBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', borderRadius: 28, paddingVertical: 14, marginTop: 24, gap: 10 },
  primaryBtnIcon: { width: 28, height: 28, borderRadius: 14, backgroundColor: '#FFF', alignItems: 'center', justifyContent: 'center' },
  primaryBtnText: { fontSize: 17, fontWeight: '700', color: '#FFF' },

  // Or divider
  orRow: { flexDirection: 'row', alignItems: 'center', marginVertical: 20, gap: 12 },
  orLine: { flex: 1, height: 1, backgroundColor: '#E2E8F0' },
  orText: { fontSize: 13, color: '#94A3B8', fontWeight: '500' },

  // Platform grid
  platformGrid: { gap: 10 },
  platformTile: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#FFF', borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 14, paddingVertical: 13, paddingHorizontal: 16, ...(Platform.OS === 'web' ? { cursor: 'pointer' as any } : {}) },
  platformTileDisabled: { opacity: 0.55, ...(Platform.OS === 'web' ? { cursor: 'default' as any } : {}) },
  platformIcon: { width: 38, height: 38, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  platformName: { flex: 1, fontSize: 16, fontWeight: '600', color: '#1E293B', marginLeft: 14 },
  comingSoon: { fontSize: 11, fontWeight: '600', color: '#94A3B8', backgroundColor: '#F1F5F9', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },

  // Store info
  storeInfo: { marginTop: 24, paddingTop: 18, borderTopWidth: 1, borderTopColor: '#F1F5F9', gap: 6 },
  storeInfoRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 5 },
  storeInfoText: { fontSize: 14, color: '#94A3B8' },

  // Feedback
  feedbackCard: { backgroundColor: '#FFF', borderRadius: 20, paddingVertical: 24, paddingHorizontal: 24, width: '100%', marginTop: 14, ...(Platform.OS === 'web' ? { boxShadow: '0 2px 12px rgba(0,0,0,0.08)' } : { shadowColor: '#000', shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.08, shadowRadius: 16, elevation: 4 }) },
  fbHeading: { fontSize: 16, fontWeight: '600', color: '#334155', textAlign: 'center', marginBottom: 14 },
  starRow: { flexDirection: 'row', justifyContent: 'center', gap: 6, marginBottom: 12 },
  fbInput: { backgroundColor: '#F8FAFC', borderRadius: 10, padding: 14, fontSize: 16, color: '#1E293B', borderWidth: 1, borderColor: '#E2E8F0', marginBottom: 10 },
  fbSubmitBtn: { borderRadius: 10, paddingVertical: 14, alignItems: 'center', marginTop: 4 },
  fbSubmitText: { fontSize: 17, fontWeight: '600', color: '#FFF' },
  fbSuccess: { alignItems: 'center', paddingVertical: 12 },
  fbSuccessTitle: { fontSize: 19, fontWeight: '700', color: '#1E293B', marginTop: 10 },
  fbSuccessText: { fontSize: 16, color: '#64748B', marginTop: 4 },
});
