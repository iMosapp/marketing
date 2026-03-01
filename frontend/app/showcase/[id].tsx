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
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import api from '../../services/api';

const IS_WEB = Platform.OS === 'web';
const ACCENT = '#C9A962';

interface ReviewData {
  id: string;
  rating: number;
  text: string;
  customer_name: string;
  created_at: string | null;
}

interface ShowcaseEntry {
  id: string;
  type: 'delivery' | 'review_only';
  customer_name: string;
  customer_photo: string | null;
  card_id: string | null;
  salesman_name: string | null;
  salesman_photo: string | null;
  store_name: string | null;
  created_at: string | null;
  review: ReviewData | null;
}

interface ShowcaseData {
  salesperson: {
    id: string;
    name: string;
    title: string;
    photo_url: string | null;
    phone: string | null;
  };
  store: {
    name: string | null;
    logo_url: string | null;
    primary_color: string;
  } | null;
  entries: ShowcaseEntry[];
  total_deliveries: number;
  total_reviews: number;
}

function StarRating({ rating }: { rating: number }) {
  return (
    <View style={styles.starRow}>
      {[1, 2, 3, 4, 5].map(i => (
        <Ionicons
          key={i}
          name={i <= rating ? 'star' : 'star-outline'}
          size={14}
          color={i <= rating ? '#FFD60A' : '#3A3A3C'}
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
  const { id, scope } = useLocalSearchParams();
  const router = useRouter();
  const [data, setData] = useState<ShowcaseData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showQR, setShowQR] = useState(false);

  const pageScope = (scope as string) || 'user';

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

  const shareUrl = IS_WEB
    ? window.location.href
    : `https://app.imosapp.com/showcase/${id}`;

  const handleShare = async () => {
    if (IS_WEB && navigator.share) {
      try {
        await navigator.share({ title: `${data?.salesperson?.name}'s Showroom`, url: shareUrl });
      } catch {}
    } else if (IS_WEB) {
      navigator.clipboard?.writeText(shareUrl);
      alert('Link copied to clipboard!');
    } else {
      Share.share({ message: shareUrl });
    }
  };

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
  const spName = data.salesperson?.name || 'Our Team';

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Sticky top bar with back + copy link */}
      <View style={styles.topBar}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn} data-testid="showroom-back-btn">
          <Ionicons name="chevron-back" size={24} color="#FFF" />
        </TouchableOpacity>
        <Text style={styles.topBarTitle}>The Showroom</Text>
        <TouchableOpacity onPress={handleShare} style={[styles.copyLinkBtn, { backgroundColor: accent }]} data-testid="showroom-copy-link">
          <Ionicons name="copy-outline" size={16} color="#000" />
          <Text style={styles.copyLinkText}>Copy Link</Text>
        </TouchableOpacity>
      </View>

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <View style={styles.header}>
          {/* Store logo */}
          {data.store?.logo_url && (
            <Image source={{ uri: data.store.logo_url }} style={styles.storeLogo} resizeMode="contain" />
          )}

          {/* Salesperson hero */}
          <View style={styles.heroSection}>
            {data.salesperson.photo_url ? (
              <Image source={{ uri: data.salesperson.photo_url }} style={[styles.heroAvatar, { borderColor: accent }]} />
            ) : (
              <View style={[styles.heroAvatarFallback, { backgroundColor: accent }]}>
                <Text style={styles.heroAvatarText}>
                  {spName.split(' ').map(n => n[0] || '').join('').toUpperCase().slice(0, 2)}
                </Text>
              </View>
            )}
            <Text style={styles.heroName}>{spName}</Text>
            <Text style={styles.heroTitle}>{data.salesperson.title}</Text>
            {data.store?.name && (
              <Text style={[styles.heroStore, { color: accent }]}>{data.store.name}</Text>
            )}
          </View>

          {/* Stats bar */}
          <View style={styles.statsBar}>
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

          {/* Page title */}
          <View style={styles.titleSection}>
            <View style={[styles.titleAccent, { backgroundColor: accent }]} />
            <Text style={styles.titleText}>The Showroom</Text>
          </View>
        </View>

        {/* Entries feed */}
        {data.entries.length === 0 ? (
          <View style={styles.emptyState}>
            <Ionicons name="images-outline" size={56} color="#3A3A3C" />
            <Text style={styles.emptyTitle}>Coming Soon</Text>
            <Text style={styles.emptySubtitle}>Happy customer moments will appear here</Text>
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
                  <Text style={styles.customerName}>{entry.customer_name}</Text>
                  {entry.created_at && (
                    <Text style={styles.entryDate}>{formatDate(entry.created_at)}</Text>
                  )}
                </View>

                {/* Matched review */}
                {entry.review && (
                  <View style={[styles.reviewSection, { borderLeftColor: accent }]}>
                    <StarRating rating={entry.review.rating} />
                    {entry.review.text ? (
                      <Text style={styles.reviewText}>"{entry.review.text}"</Text>
                    ) : null}
                    <Text style={styles.reviewAttribution}>
                      — {entry.review.customer_name}
                    </Text>
                  </View>
                )}

                {/* Review-only entry (no photo) */}
                {entry.type === 'review_only' && entry.review && (
                  <View style={styles.reviewOnlyIcon}>
                    <Ionicons name="chatbubble-ellipses" size={16} color={accent} />
                  </View>
                )}
              </View>

              {/* Divider between entries */}
              {index < data.entries.length - 1 && <View style={styles.entryDivider} />}
            </View>
          ))
        )}

        {/* Share section */}
        <View style={styles.shareSection}>
          {/* Leave a Review CTA */}
          <TouchableOpacity
            style={[styles.reviewCTA, { backgroundColor: '#111', borderColor: accent }]}
            onPress={() => router.push(`/p/${id}`)}
            data-testid="leave-review-btn"
          >
            <Ionicons name="star" size={20} color="#FFD60A" />
            <View style={styles.reviewCTAContent}>
              <Text style={styles.reviewCTATitle}>Had a great experience?</Text>
              <Text style={[styles.reviewCTASubtitle, { color: accent }]}>Leave a Review</Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color={accent} />
          </TouchableOpacity>

          {/* View Digital Business Card */}
          <TouchableOpacity
            style={styles.cardLink}
            onPress={() => router.push(`/p/${id}`)}
            data-testid="view-business-card-btn"
          >
            <Ionicons name="card-outline" size={18} color={accent} />
            <Text style={[styles.cardLinkText, { color: accent }]}>View My Digital Business Card</Text>
          </TouchableOpacity>

          {/* Divider */}
          <View style={{ height: 1, backgroundColor: '#1C1C1E', width: '80%', marginVertical: 8 }} />

          <TouchableOpacity
            style={[styles.shareButton, { backgroundColor: accent }]}
            onPress={handleShare}
            data-testid="share-showcase-btn"
          >
            <Ionicons name="share-outline" size={18} color="#000" />
            <Text style={styles.shareButtonText}>Share My Showroom</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.qrButton}
            onPress={() => setShowQR(!showQR)}
            data-testid="qr-code-btn"
          >
            <Ionicons name="qr-code-outline" size={18} color={accent} />
            <Text style={[styles.qrButtonText, { color: accent }]}>
              {showQR ? 'Hide' : 'Show'} QR Code
            </Text>
          </TouchableOpacity>

          {showQR && (
            <View style={styles.qrContainer}>
              <Image
                source={{
                  uri: `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(shareUrl)}&bgcolor=000000&color=C9A962`,
                }}
                style={styles.qrImage}
                resizeMode="contain"
              />
              <Text style={styles.qrHint}>Scan to view this page</Text>
            </View>
          )}
        </View>

        {/* Footer */}
        <View style={styles.footer}>
          <Text style={styles.footerText}>Powered by i'M On Social</Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  scroll: { flex: 1 },
  scrollContent: { paddingBottom: 40 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 20 },
  errorText: { color: '#FF3B30', fontSize: 16, marginTop: 12 },

  // Header
  header: { alignItems: 'center', paddingTop: 20, paddingHorizontal: 20 },
  storeLogo: { width: 120, height: 40, marginBottom: 16, opacity: 0.8, backgroundColor: 'transparent' },

  heroSection: { alignItems: 'center', marginBottom: 24 },
  heroAvatar: {
    width: 90,
    height: 90,
    borderRadius: 45,
    borderWidth: 3,
    marginBottom: 12,
  },
  heroAvatarFallback: {
    width: 90,
    height: 90,
    borderRadius: 45,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 12,
  },
  heroAvatarText: { color: '#000', fontSize: 28, fontWeight: '700' },
  heroName: { fontSize: 24, fontWeight: '800', color: '#FFF', letterSpacing: -0.5, marginBottom: 2 },
  heroTitle: { fontSize: 14, color: '#8E8E93', marginBottom: 4 },
  heroStore: { fontSize: 13, fontWeight: '600', letterSpacing: 0.3 },

  // Stats
  statsBar: {
    flexDirection: 'row',
    backgroundColor: '#111',
    borderRadius: 16,
    paddingVertical: 16,
    paddingHorizontal: 20,
    width: '100%',
    maxWidth: 400,
    marginBottom: 28,
  },
  statItem: { flex: 1, alignItems: 'center' },
  statNumber: { fontSize: 22, fontWeight: '800', marginBottom: 2 },
  statLabel: { fontSize: 11, color: '#6E6E73', fontWeight: '500', textTransform: 'uppercase', letterSpacing: 0.3 },
  statDivider: { width: 1, height: '80%', alignSelf: 'center' },

  // Title
  titleSection: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 24, width: '100%', maxWidth: 600 },
  titleAccent: { width: 4, height: 24, borderRadius: 2 },
  titleText: { fontSize: 20, fontWeight: '700', color: '#FFF', letterSpacing: -0.3 },

  // Empty
  emptyState: { alignItems: 'center', paddingVertical: 60, paddingHorizontal: 20 },
  emptyTitle: { fontSize: 18, fontWeight: '600', color: '#8E8E93', marginTop: 16 },
  emptySubtitle: { fontSize: 14, color: '#6E6E73', marginTop: 6 },

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
  photoBadgeText: { fontSize: 12, fontWeight: '700', color: '#000' },

  entryContent: { paddingHorizontal: 4, marginBottom: 8 },
  entryHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  customerName: { fontSize: 16, fontWeight: '700', color: '#FFF' },
  entryDate: { fontSize: 12, color: '#6E6E73' },

  // Review
  reviewSection: {
    borderLeftWidth: 3,
    paddingLeft: 12,
    paddingVertical: 8,
    marginTop: 4,
    marginBottom: 4,
  },
  starRow: { flexDirection: 'row', gap: 2, marginBottom: 6 },
  reviewText: { fontSize: 14, color: '#E5E5EA', lineHeight: 20, fontStyle: 'italic', marginBottom: 6 },
  reviewAttribution: { fontSize: 12, color: '#8E8E93', fontWeight: '500' },
  reviewOnlyIcon: { position: 'absolute', top: 0, right: 0 },

  entryDivider: { height: 1, backgroundColor: '#1C1C1E', marginVertical: 20 },

  // Share
  shareSection: { alignItems: 'center', paddingVertical: 32, paddingHorizontal: 20, gap: 12 },

  // Leave a Review CTA
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
  reviewCTATitle: { fontSize: 14, color: '#E5E5EA', fontWeight: '500', marginBottom: 2 },
  reviewCTASubtitle: { fontSize: 16, fontWeight: '700' },

  // Business card link
  cardLink: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 10,
  },
  cardLinkText: { fontSize: 14, fontWeight: '600' },

  shareButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 28,
    paddingVertical: 14,
    borderRadius: 30,
  },
  shareButtonText: { fontSize: 15, fontWeight: '700', color: '#000' },
  qrButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 20,
    paddingVertical: 10,
  },
  qrButtonText: { fontSize: 14, fontWeight: '600' },
  qrContainer: { alignItems: 'center', marginTop: 12, padding: 16, backgroundColor: '#111', borderRadius: 16 },
  qrImage: { width: 180, height: 180, borderRadius: 8 },
  qrHint: { fontSize: 12, color: '#6E6E73', marginTop: 10 },

  // Footer
  footer: { alignItems: 'center', paddingVertical: 20, paddingBottom: 40 },
  footerText: { fontSize: 11, color: '#3A3A3C', letterSpacing: 0.5 },
});
