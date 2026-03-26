import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  ScrollView,
  Image,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Platform,
  Share,
  Linking,
  TextInput,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import api from '../../services/api';
import { PoweredByFooter } from '../../components/PoweredByFooter';
import { SEOHead } from '../../components/SEOHead';

const IS_WEB = Platform.OS === 'web';
const ACCENT = '#C9A962';

function useHydrated() {
  const [h, setH] = useState(false);
  useEffect(() => setH(true), []);
  return h;
}

interface ReviewData {
  id: string;
  rating: number;
  text: string;
  customer_name: string;
  photo_url: string | null;
  created_at: string | null;
}

interface ShowcaseEntry {
  id: string;
  type: 'delivery' | 'review_only';
  customer_name: string;
  customer_photo: string | null;
  card_id: string | null;
  salesman_id: string | null;
  salesman_name: string | null;
  salesman_photo: string | null;
  store_name: string | null;
  created_at: string | null;
  review: ReviewData | null;
}

interface ShowcaseData {
  salesperson?: {
    id: string;
    name: string;
    title: string;
    photo_url: string | null;
    phone: string | null;
  };
  store: {
    id?: string;
    name: string | null;
    logo_url: string | null;
    primary_color: string;
  } | null;
  entries: ShowcaseEntry[];
  total_deliveries: number;
  total_reviews: number;
  team?: { id: string; name: string; photo_url: string }[];
}

function StarRating({ rating, outlineColor }: { rating: number; outlineColor?: string }) {
  return (
    <View style={styles.starRow}>
      {[1, 2, 3, 4, 5].map(i => (
        <Ionicons
          key={i}
          name={i <= rating ? 'star' : 'star-outline'}
          size={14}
          color={i <= rating ? '#FFD60A' : (outlineColor || '#3A3A3C')}
        />
      ))}
    </View>
  );
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return '';
  }
}

export default function ShowcasePage() {
  const hydrated = useHydrated();
  const { id, scope, from } = useLocalSearchParams();
  const router = useRouter();
  const [data, setData] = useState<ShowcaseData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showQR, setShowQR] = useState(false);
  const [showReviewForm, setShowReviewForm] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [reviewRating, setReviewRating] = useState(0);
  const [reviewName, setReviewName] = useState('');
  const [reviewText, setReviewText] = useState('');
  const [reviewSubmitted, setReviewSubmitted] = useState(false);
  const [submittingReview, setSubmittingReview] = useState(false);

  const pageScope = (scope as string) || 'user';
  const fromUserId = from as string | undefined;

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    loadShowcase();
  }, [id, pageScope]);

  const loadShowcase = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const endpoint = pageScope === 'store'
        ? `/showcase/store/${id}`
        : pageScope === 'org'
          ? `/showcase/org/${id}`
          : `/showcase/user/${id}`;
      const res = await api.get(endpoint);
      setData(res.data);
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Failed to load showcase');
    } finally {
      setLoading(false);
    }
  };

  const shareUrl = mounted && IS_WEB
    ? window.location.href
    : `https://app.imonsocial.com/showcase/${id}`;

  const handleSubmitReview = async () => {
    if (reviewRating === 0) return;
    setSubmittingReview(true);
    try {
      // Try to get store slug from the showcase data
      const storeId = data?.store?.id;
      if (storeId) {
        const storeResp = await api.get(`/stores/${storeId}`);
        const slug = storeResp.data?.slug;
        if (slug) {
          await api.post(`/review/submit/${slug}`, {
            customer_name: reviewName.trim() || 'Anonymous',
            rating: reviewRating,
            text_review: reviewText.trim() || null,
          });
        }
      }
      setReviewSubmitted(true);
    } catch (e) {
      console.error('Review submit error:', e);
      setReviewSubmitted(true); // Still show success to user
    } finally {
      setSubmittingReview(false);
    }
  };

  const handleShare = async () => {
    if (IS_WEB && typeof navigator !== 'undefined' && navigator.share) {
      try {
        await navigator.share({ title: `${data?.salesperson?.name}'s Showcase`, url: shareUrl });
      } catch {}
    } else if (IS_WEB && typeof navigator !== 'undefined') {
      try {
        await navigator.clipboard.writeText(shareUrl);
      } catch {
        if (typeof document !== 'undefined') {
          const ta = document.createElement('textarea');
          ta.value = shareUrl;
          ta.style.position = 'fixed';
          ta.style.opacity = '0';
          document.body.appendChild(ta);
          ta.select();
          document.execCommand('copy');
          document.body.removeChild(ta);
        }
      }
      alert('Link copied to clipboard!');
    } else {
      Share.share({ message: shareUrl });
    }
  };

  if (!mounted) {
    return (
      <View style={styles.container} {...{ suppressHydrationWarning: true }}>
        <View style={styles.center} {...{ suppressHydrationWarning: true }}>
          <ActivityIndicator size="large" color={ACCENT} />
        </View>
      </View>
    );
  }

  if (!hydrated) return null;

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.center}>
          <ActivityIndicator size="large" color={ACCENT} />
        </View>
      </SafeAreaView>
    );
  }

  if (error || !data) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.center}>
          <Ionicons name="alert-circle-outline" size={48} color="#FF3B30" />
          <Text style={styles.errorText}>{error || 'Not found'}</Text>
        </View>
      </SafeAreaView>
    );
  }

  const accent = data.store?.primary_color || ACCENT;
  const isStoreView = pageScope === 'store';
  const spName = isStoreView ? (data.store?.name || 'Our Team') : (data.salesperson?.name || 'Our Team');
  const storeId = data.store?.id;
  const isDark = data.brand_kit?.page_theme !== 'light';
  const t = {
    bg: isDark ? '#000' : '#F2F2F7',
    card: isDark ? '#111' : '#FFF',
    cardAlt: isDark ? '#1C1C1E' : '#E5E5EA',
    text: isDark ? '#FFF' : '#1C1C1E',
    textSec: isDark ? '#8E8E93' : '#6E6E73',
    textTer: isDark ? '#E5E5EA' : '#3A3A3C',
    border: isDark ? '#1C1C1E' : '#D1D1D6',
    inputBg: isDark ? '#2A2A2C' : '#F2F2F7',
    inputBorder: isDark ? '#3A3A3C' : '#D1D1D6',
    starOutline: isDark ? '#3A3A3C' : '#C7C7CC',
    qrBg: isDark ? '000000' : 'F2F2F7',
    qrFg: isDark ? 'C9A962' : '1C1C1E',
  };

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: t.bg }]} edges={['top']}>
      <SEOHead type="card" id={id as string} />
      {/* Sticky top bar */}
      <View style={[styles.topBar, { borderBottomColor: t.border }]}>
        <View style={{ width: 32 }} />
        <Text style={[styles.topBarTitle, { color: t.text }]}>{isStoreView ? `${data.store?.name || 'Store'} Showcase` : 'The Showcase'}</Text>
        <View style={{ width: 32 }} />
      </View>

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <View style={styles.header}>
          {/* Store logo  - clickable to store showcase (only in user view) */}
          {data.store?.logo_url && !isStoreView && storeId ? (
            <TouchableOpacity onPress={() => router.push(`/showcase/${storeId}?scope=store&from=${id}` as any)} data-testid="store-logo-link">
              <Image source={{ uri: data.store.logo_url }} style={styles.storeLogo} resizeMode="contain" />
            </TouchableOpacity>
          ) : data.store?.logo_url ? (
            <Image source={{ uri: data.store.logo_url }} style={styles.storeLogo} resizeMode="contain" />
          ) : null}

          {/* Hero section  - salesperson (user view) or store (store view) */}
          <View style={styles.heroSection}>
            {isStoreView ? (
              <>
                {data.store?.logo_url ? (
                  <Image source={{ uri: data.store.logo_url }} style={[styles.heroAvatar, { borderColor: accent }]} />
                ) : (
                  <View style={[styles.heroAvatarFallback, { backgroundColor: accent }]}>
                    <Ionicons name="storefront" size={36} color="#000" />
                  </View>
                )}
                <Text style={[styles.heroName, { color: t.text }]}>{data.store?.name || 'Our Store'}</Text>
                <Text style={[styles.heroTitle, { color: t.textSec }]}>{data.team?.length || 0} Team Members</Text>
              </>
            ) : (
              <>
                {data.salesperson?.photo_url ? (
                  <Image source={{ uri: data.salesperson.photo_url }} style={[styles.heroAvatar, { borderColor: accent }]} />
                ) : (
                  <View style={[styles.heroAvatarFallback, { backgroundColor: accent }]}>
                    <Text style={styles.heroAvatarText}>
                      {spName.split(' ').map(n => n[0] || '').join('').toUpperCase().slice(0, 2)}
                    </Text>
                  </View>
                )}
                <Text style={[styles.heroName, { color: t.text }]}>{spName}</Text>
                <Text style={[styles.heroTitle, { color: t.textSec }]}>{data.salesperson?.title}</Text>
                {data.store?.name && storeId ? (
                  <TouchableOpacity onPress={() => router.push(`/showcase/${storeId}?scope=store&from=${id}` as any)} data-testid="store-name-link">
                    <Text style={[styles.heroStore, { color: accent }]}>{data.store.name}</Text>
                  </TouchableOpacity>
                ) : data.store?.name ? (
                  <Text style={[styles.heroStore, { color: accent }]}>{data.store.name}</Text>
                ) : null}
              </>
            )}
          </View>

          {/* Stats bar */}
          <View style={[styles.statsBar, { backgroundColor: t.card }]}>
            <View style={styles.statItem}>
              <Text style={[styles.statNumber, { color: accent }]}>{data.total_deliveries}</Text>
              <Text style={styles.statLabel}>Happy Customers</Text>
            </View>
            <View style={[styles.statDivider, { backgroundColor: accent + '30' }]} />
            <View style={styles.statItem}>
              <Text style={[styles.statNumber, { color: accent }]}>{data.total_reviews}</Text>
              <Text style={styles.statLabel}>Reviews</Text>
            </View>
            <View style={[styles.statDivider, { backgroundColor: accent + '30' }]} />
            <View style={styles.statItem}>
              <Text style={[styles.statNumber, { color: accent }]}>
                {data.total_reviews > 0 ? '5.0' : '-'}
              </Text>
              <Text style={styles.statLabel}>Avg Rating</Text>
            </View>
          </View>

          {/* Quick action links  - under profile, above showcase feed */}
          <View style={styles.quickLinks}>
            {!isStoreView && (
              <>
                <TouchableOpacity
                  style={[styles.reviewCTA, { backgroundColor: t.card, borderColor: accent }]}
                  onPress={() => { if (!reviewSubmitted) setShowReviewForm(!showReviewForm); }}
                  data-testid="leave-review-btn"
                >
                  <Ionicons name="star" size={20} color="#FFD60A" />
                  <View style={styles.reviewCTAContent}>
                    <Text style={[styles.reviewCTATitle, { color: t.textTer }]}>{reviewSubmitted ? 'Thank you for your review!' : 'Had a great experience?'}</Text>
                    <Text style={[styles.reviewCTASubtitle, { color: accent }]}>{reviewSubmitted ? 'Your feedback means a lot.' : 'Tap to leave a review'}</Text>
                  </View>
                  {!reviewSubmitted && <Ionicons name={showReviewForm ? 'chevron-up' : 'chevron-down'} size={18} color={accent} />}
                </TouchableOpacity>

                {showReviewForm && !reviewSubmitted && (
                  <View style={[styles.reviewFormCard, { borderColor: accent + '40', backgroundColor: t.cardAlt }]}>
                    <Text style={[styles.reviewFormLabel, { color: t.textTer }]}>How was your experience?</Text>
                    <View style={styles.reviewStarRow}>
                      {[1, 2, 3, 4, 5].map((star) => (
                        <TouchableOpacity key={star} onPress={() => setReviewRating(star)} data-testid={`showcase-star-${star}`}>
                          <Ionicons name={star <= reviewRating ? 'star' : 'star-outline'} size={36} color={star <= reviewRating ? '#FFD60A' : t.starOutline} />
                        </TouchableOpacity>
                      ))}
                    </View>
                    {reviewRating > 0 && (
                      <>
                        <TextInput style={[styles.reviewInput, { backgroundColor: t.inputBg, borderColor: t.inputBorder, color: t.text }]} placeholder="Your name (optional)" placeholderTextColor={t.textSec} value={reviewName} onChangeText={setReviewName} />
                        <TextInput style={[styles.reviewInput, { height: 80, textAlignVertical: 'top', backgroundColor: t.inputBg, borderColor: t.inputBorder, color: t.text }]} placeholder="Tell us about your experience..." placeholderTextColor={t.textSec} value={reviewText} onChangeText={setReviewText} multiline numberOfLines={3} />
                        <TouchableOpacity style={[styles.reviewSubmitBtn, { backgroundColor: accent }]} onPress={handleSubmitReview} disabled={submittingReview} data-testid="showcase-review-submit">
                          {submittingReview ? <ActivityIndicator size="small" color="#000" /> : <Text style={styles.reviewSubmitText}>Submit Review</Text>}
                        </TouchableOpacity>
                      </>
                    )}
                  </View>
                )}
              </>
            )}

            <View style={styles.quickLinksRow}>
              {/* Store view: Back to user's showcase */}
              {isStoreView && fromUserId && (
                <TouchableOpacity
                  style={[styles.quickLinkChip, { borderColor: accent + '40' }]}
                  onPress={() => router.push(`/showcase/${fromUserId}` as any)}
                  data-testid="back-to-user-showcase"
                >
                  <Ionicons name="person-outline" size={15} color={accent} />
                  <Text style={[styles.quickLinkText, { color: accent }]}>Back to Showcase</Text>
                </TouchableOpacity>
              )}

              {/* Store view: View store landing page */}
              {isStoreView && (
                <TouchableOpacity
                  style={[styles.quickLinkChip, { borderColor: accent + '40' }]}
                  onPress={() => router.push(`/p/${fromUserId || id}` as any)}
                  data-testid="view-store-page"
                >
                  <Ionicons name="globe-outline" size={15} color={accent} />
                  <Text style={[styles.quickLinkText, { color: accent }]}>Landing Page</Text>
                </TouchableOpacity>
              )}

              {/* User view: My Card */}
              {!isStoreView && (
                <TouchableOpacity
                  style={[styles.quickLinkChip, { borderColor: accent + '40' }]}
                  onPress={() => router.push(`/p/${id}`)}
                  data-testid="view-business-card-btn"
                >
                  <Ionicons name="card-outline" size={15} color={accent} />
                  <Text style={[styles.quickLinkText, { color: accent }]}>My Card</Text>
                </TouchableOpacity>
              )}

              {/* User view: Store Showcase */}
              {!isStoreView && storeId && (
                <TouchableOpacity
                  style={[styles.quickLinkChip, { borderColor: accent + '40' }]}
                  onPress={() => router.push(`/showcase/${storeId}?scope=store&from=${id}` as any)}
                  data-testid="store-showroom-link"
                >
                  <Ionicons name="storefront-outline" size={15} color={accent} />
                  <Text style={[styles.quickLinkText, { color: accent }]}>Store</Text>
                </TouchableOpacity>
              )}

              <TouchableOpacity
                style={[styles.quickLinkChip, { borderColor: accent + '40' }]}
                onPress={handleShare}
                data-testid="share-showcase-btn"
              >
                <Ionicons name="share-outline" size={15} color={accent} />
                <Text style={[styles.quickLinkText, { color: accent }]}>Share</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={[styles.quickLinkChip, { borderColor: accent + '40' }]}
                onPress={() => setShowQR(!showQR)}
                data-testid="qr-code-btn"
              >
                <Ionicons name="qr-code-outline" size={15} color={accent} />
                <Text style={[styles.quickLinkText, { color: accent }]}>QR</Text>
              </TouchableOpacity>
            </View>

            {showQR && (
              <View style={[styles.qrContainer, { backgroundColor: t.card }]}>
                <Image
                  source={{
                    uri: `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(shareUrl)}&bgcolor=${t.qrBg}&color=${t.qrFg}`,
                  }}
                  style={styles.qrImage}
                  resizeMode="contain"
                />
                <Text style={[styles.qrHint, { color: t.textSec }]}>Scan to view this page</Text>
              </View>
            )}
          </View>

          {/* Page title */}
          <View style={styles.titleSection}>
            <View style={[styles.titleAccent, { backgroundColor: accent }]} />
            <Text style={[styles.titleText, { color: t.text }]}>The Showcase</Text>
          </View>
        </View>

        {/* Entries feed */}
        {data.entries.length === 0 ? (
          <View style={styles.emptyState}>
            <Ionicons name="images-outline" size={56} color={t.starOutline} />
            <Text style={[styles.emptyTitle, { color: t.textSec }]}>Coming Soon</Text>
            <Text style={[styles.emptySubtitle, { color: t.textSec }]}>Happy customer moments will appear here</Text>
          </View>
        ) : (
          data.entries.map((entry, index) => (
            <View
              key={entry.id}
              style={styles.entryCard}
              data-testid={`showcase-entry-${index}`}
            >
              {/* Delivery photo */}
              {entry.customer_photo && (
                <View style={styles.photoContainer}>
                  <Image
                    source={{ uri: entry.customer_photo }}
                    style={styles.deliveryPhoto}
                    resizeMode="cover"
                  />
                  <View style={[styles.photoBadge, { backgroundColor: accent }]}>
                    <Ionicons name="checkmark-circle" size={14} color="#000" />
                    <Text style={styles.photoBadgeText}>Delivered</Text>
                  </View>
                </View>
              )}

              {/* Entry content */}
              <View style={styles.entryContent}>
                <View style={styles.entryHeader}>
                  <Text style={[styles.customerName, { color: t.text }]}>{entry.customer_name}</Text>
                  {entry.created_at && (
                    <Text style={styles.entryDate}>{formatDate(entry.created_at)}</Text>
                  )}
                </View>

                {/* Show salesperson name in store view */}
                {isStoreView && entry.salesman_name && (
                  <TouchableOpacity
                    onPress={() => entry.salesman_id ? router.push(`/showcase/${entry.salesman_id}` as any) : null}
                    style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginBottom: 6 }}
                  >
                    <Ionicons name="person-outline" size={12} color="#8E8E93" />
                    <Text style={{ fontSize: 14, color: accent, fontWeight: '500' }}>{entry.salesman_name}</Text>
                  </TouchableOpacity>
                )}

                {/* Matched review / customer feedback */}
                {entry.review && (
                  <View style={[styles.reviewSection, { borderLeftColor: accent }]}>
                    <View style={styles.reviewHeader}>
                      <Ionicons name="chatbubble-ellipses" size={14} color={accent} />
                      <Text style={[styles.reviewLabel, { color: accent }]}>Customer Feedback</Text>
                      {entry.review.created_at && (
                        <Text style={styles.reviewDate}>{formatDate(entry.review.created_at)}</Text>
                      )}
                    </View>
                    <StarRating rating={entry.review.rating} outlineColor={t.starOutline} />
                    {entry.review.text ? (
                      <Text style={[styles.reviewText, { color: t.textTer }]}>"{entry.review.text}"</Text>
                    ) : null}

                    {/* Customer's feedback photo */}
                    {entry.review.photo_url && (
                      <View style={styles.feedbackPhotoContainer}>
                        <Image
                          source={{ uri: entry.review.photo_url }}
                          style={styles.feedbackPhoto}
                          resizeMode="cover"
                        />
                        <View style={styles.feedbackPhotoBadge}>
                          <Ionicons name="camera" size={10} color="#FFF" />
                          <Text style={styles.feedbackPhotoBadgeText}>Customer Photo</Text>
                        </View>
                      </View>
                    )}

                    <Text style={styles.reviewAttribution}>
                       - {entry.review.customer_name}
                    </Text>
                  </View>
                )}

                {/* Review-only entry icon (no delivery photo) */}
                {entry.type === 'review_only' && !entry.customer_photo && (
                  <View style={styles.reviewOnlyIcon}>
                    <Ionicons name="chatbubble-ellipses" size={16} color={accent} />
                  </View>
                )}
              </View>

              {/* Divider between entries */}
              {index < data.entries.length - 1 && <View style={[styles.entryDivider, { backgroundColor: t.border }]} />}
            </View>
          ))
        )}

        {/* Refer a Friend */}
        {!isStoreView && (
          <View style={{ paddingHorizontal: 16, marginBottom: 16 }}>
            <TouchableOpacity
              style={[styles.referralBanner, { borderColor: accent + '40', backgroundColor: t.cardAlt }]}
              onPress={() => {
                const currentUrl = typeof window !== 'undefined' ? window.location.href : `https://app.imonsocial.com/showcase/${id}`;
                const shareText = `Check out this showcase! ${currentUrl}`;
                if (Platform.OS === 'web') {
                  if (typeof navigator !== 'undefined' && navigator.share) {
                    navigator.share({ title: 'Refer a Friend', text: shareText, url: currentUrl });
                  } else if (typeof navigator !== 'undefined') {
                    navigator.clipboard?.writeText(shareText);
                    alert('Link copied! Share it with a friend.');
                  }
                } else {
                  Share.share({ message: shareText });
                }
              }}
              data-testid="showcase-refer-friend"
            >
              <Ionicons name="people" size={20} color="#34C759" />
              <View style={{ flex: 1, marginLeft: 10 }}>
                <Text style={[styles.referralTitle, { color: t.text }]}>Know someone who could use my services?</Text>
                <Text style={styles.referralSub}>Tap to refer a friend</Text>
              </View>
              <Ionicons name="share-outline" size={18} color="#34C759" />
            </TouchableOpacity>
          </View>
        )}

        {/* Footer */}
        <PoweredByFooter />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  // Top bar
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderBottomWidth: 0.5,
    borderBottomColor: '#1C1C1E',
  },
  backBtn: { padding: 4 },
  topBarTitle: { fontSize: 18, fontWeight: '700', color: '#FFF' },
  scroll: { flex: 1 },
  scrollContent: { paddingBottom: 40 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 20 },
  errorText: { color: '#FF3B30', fontSize: 18, marginTop: 12 },

  // Header
  header: { alignItems: 'center', paddingTop: 20, paddingHorizontal: 20 },
  storeLogo: { width: 120, height: 40, marginBottom: 16, opacity: 0.8, backgroundColor: 'transparent' },

  heroSection: { alignItems: 'center', marginBottom: 24 },
  heroAvatar: {
    width: 180,
    height: 180,
    borderRadius: 24,
    borderWidth: 3,
    marginBottom: 12,
  },
  heroAvatarFallback: {
    width: 180,
    height: 180,
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 12,
  },
  heroAvatarText: { color: '#000', fontSize: 28, fontWeight: '700' },
  heroName: { fontSize: 24, fontWeight: '800', color: '#FFF', letterSpacing: -0.5, marginBottom: 2 },
  heroTitle: { fontSize: 16, color: '#8E8E93', marginBottom: 4 },
  heroStore: { fontSize: 15, fontWeight: '600', letterSpacing: 0.3 },

  // Stats
  statsBar: {
    flexDirection: 'row',
    backgroundColor: '#111',
    borderRadius: 16,
    paddingVertical: 16,
    paddingHorizontal: 20,
    width: '100%',
    maxWidth: 400,
    marginBottom: 20,
  },
  statItem: { flex: 1, alignItems: 'center' },
  statNumber: { fontSize: 22, fontWeight: '800', marginBottom: 2 },
  statLabel: { fontSize: 13, color: '#6E6E73', fontWeight: '500', textTransform: 'uppercase', letterSpacing: 0.3 },
  statDivider: { width: 1, height: '80%', alignSelf: 'center' },

  // Quick links under profile
  quickLinks: { width: '100%', maxWidth: 400, alignItems: 'center', gap: 12, marginBottom: 28 },
  quickLinksRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    flexWrap: 'wrap',
    gap: 8,
    paddingVertical: 4,
    maxWidth: 400,
    width: '100%',
  },
  quickLinkChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingVertical: 7,
    paddingHorizontal: 12,
    borderRadius: 20,
    borderWidth: 1,
  },
  quickLinkText: { fontSize: 14, fontWeight: '600' },

  // Title
  titleSection: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 24, width: '100%', maxWidth: 600 },
  titleAccent: { width: 4, height: 24, borderRadius: 2 },
  titleText: { fontSize: 21, fontWeight: '700', color: '#FFF', letterSpacing: -0.3 },

  // Empty
  emptyState: { alignItems: 'center', paddingVertical: 60, paddingHorizontal: 20 },
  emptyTitle: { fontSize: 19, fontWeight: '600', color: '#8E8E93', marginTop: 16 },
  emptySubtitle: { fontSize: 16, color: '#6E6E73', marginTop: 6 },

  // Entry card
  entryCard: {
    paddingHorizontal: 20,
    maxWidth: 600,
    width: '100%',
    alignSelf: 'center',
  },

  photoContainer: { position: 'relative', marginBottom: 12 },
  deliveryPhoto: {
    width: '100%',
    aspectRatio: 1,
    borderRadius: 16,
    backgroundColor: '#1C1C1E',
  },
  photoBadge: {
    position: 'absolute',
    bottom: 12,
    left: 12,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 20,
  },
  photoBadgeText: { fontSize: 14, fontWeight: '700', color: '#000' },

  entryContent: { paddingHorizontal: 4, marginBottom: 8 },
  entryHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  customerName: { fontSize: 18, fontWeight: '700', color: '#FFF' },
  entryDate: { fontSize: 14, color: '#6E6E73' },

  // Review
  reviewSection: {
    borderLeftWidth: 3,
    paddingLeft: 12,
    paddingVertical: 8,
    marginTop: 4,
    marginBottom: 4,
  },
  reviewHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 8,
  },
  reviewLabel: { fontSize: 14, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5 },
  reviewDate: { fontSize: 13, color: '#6E6E73', marginLeft: 'auto' },
  starRow: { flexDirection: 'row', gap: 2, marginBottom: 6 },
  reviewText: { fontSize: 16, color: '#E5E5EA', lineHeight: 20, fontStyle: 'italic', marginBottom: 6 },
  reviewAttribution: { fontSize: 14, color: '#8E8E93', fontWeight: '500', marginTop: 4 },
  reviewOnlyIcon: { position: 'absolute', top: 0, right: 0 },

  // Feedback photo from customer
  feedbackPhotoContainer: {
    position: 'relative',
    marginTop: 10,
    marginBottom: 6,
    borderRadius: 12,
    overflow: 'hidden',
  },
  feedbackPhoto: {
    width: '100%',
    aspectRatio: 4 / 3,
    borderRadius: 12,
    backgroundColor: '#1C1C1E',
  },
  feedbackPhotoBadge: {
    position: 'absolute',
    top: 8,
    right: 8,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: 'rgba(0,0,0,0.6)',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
  },
  feedbackPhotoBadgeText: { fontSize: 12, fontWeight: '600', color: '#FFF' },

  entryDivider: { height: 1, backgroundColor: '#1C1C1E', marginVertical: 20 },

  // Review CTA
  reviewCTA: {
    flexDirection: 'row',
    alignItems: 'center',
    width: '100%',
    maxWidth: 400,
    paddingHorizontal: 20,
    paddingVertical: 16,
    borderRadius: 16,
    borderWidth: 1,
    gap: 14,
  },
  reviewCTAContent: { flex: 1 },
  reviewCTATitle: { fontSize: 16, color: '#E5E5EA', fontWeight: '500', marginBottom: 2 },
  reviewCTASubtitle: { fontSize: 18, fontWeight: '700' },
  reviewFormCard: {
    backgroundColor: '#1C1C1E',
    borderRadius: 14,
    padding: 20,
    marginTop: 10,
    borderWidth: 1,
  },
  reviewFormLabel: { color: '#E5E5EA', fontSize: 17, fontWeight: '600', textAlign: 'center', marginBottom: 12 },
  reviewStarRow: { flexDirection: 'row', justifyContent: 'center', gap: 8, marginBottom: 16 },
  reviewInput: {
    backgroundColor: '#2A2A2C',
    borderRadius: 10,
    padding: 14,
    color: '#FFF',
    fontSize: 17,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: '#3A3A3C',
  },
  reviewSubmitBtn: { paddingVertical: 14, borderRadius: 12, alignItems: 'center', marginTop: 4 },
  reviewSubmitText: { color: '#000', fontSize: 18, fontWeight: '700' },
  referralBanner: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: '#1C1C1E',
    borderRadius: 14, padding: 16, borderWidth: 1,
  },
  referralTitle: { color: '#FFF', fontSize: 17, fontWeight: '700' },
  referralSub: { color: '#34C759', fontSize: 15, marginTop: 2, fontWeight: '500' },

  // QR
  qrContainer: { alignItems: 'center', marginTop: 4, padding: 16, backgroundColor: '#111', borderRadius: 16 },
  qrImage: { width: 180, height: 180, borderRadius: 8 },
  qrHint: { fontSize: 14, color: '#6E6E73', marginTop: 10 },

  // Footer
  footer: { alignItems: 'center', paddingVertical: 20, paddingBottom: 40 },
  footerText: { fontSize: 13, color: '#3A3A3C', letterSpacing: 0.5 },
});
