import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Image,
  ActivityIndicator,
  Share,
  Platform,
  Linking,
  TextInput,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import api from '../../services/api';
import { trackCustomerAction } from '../../services/tracking';
import { PoweredByFooter } from '../../components/PoweredByFooter';

interface CongratsCardData {
  card_id: string;
  customer_name: string;
  customer_photo: string;
  headline: string;
  message: string;
  custom_message?: string;
  footer_text?: string;
  salesman_id?: string;
  salesman?: {
    name: string;
    photo?: string;
    title: string;
    phone?: string;
    email?: string;
  };
  store?: {
    name: string;
    logo?: string;
  };
  style: {
    background_color: string;
    accent_color: string;
    text_color: string;
  };
  created_at?: string;
}

export default function CongratsCardPage() {
  const { cardId, preview, cid } = useLocalSearchParams();
  const router = useRouter();
  const [cardData, setCardData] = useState<CongratsCardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const cardRef = useRef<View>(null);
  const [showReviewForm, setShowReviewForm] = useState(false);
  const [reviewRating, setReviewRating] = useState(0);
  const [reviewName, setReviewName] = useState('');
  const [reviewText, setReviewText] = useState('');
  const [reviewSubmitted, setReviewSubmitted] = useState(preview === 'reviewed');
  const [submittingReview, setSubmittingReview] = useState(false);
  const [hasExistingConsent, setHasExistingConsent] = useState(false); // show banner by default, hide after consent check

  // Tracking helper — fires for every customer CTA click
  const track = (action: string, extra?: Record<string, any>) => {
    if (cardData?.salesman_id) {
      const cardType = (cardData as any)?.card_type || 'congrats';
      trackCustomerAction(cardType, action, {
        salesperson_id: cardData.salesman_id,
        contact_id: (cid as string) || undefined,
        customer_phone: (cardData as any)?.customer_phone,
        customer_name: cardData?.customer_name,
        card_id: cardId as string,
        ...extra,
      });
    }
  };

  useEffect(() => {
    loadCardData();
  }, [cardId]);

  // Check if customer already opted in (one-time consent)
  useEffect(() => {
    if (!cardData?.salesman_id) return;
    const checkConsent = async () => {
      try {
        const phone = (cardData as any)?.customer_phone || '';
        const res = await api.get(`/opt-in/check-consent?salesman_id=${cardData.salesman_id}&customer_phone=${encodeURIComponent(phone)}`);
        setHasExistingConsent(res.data?.has_consent ?? false);
      } catch {
        // If check fails, show the banner (safe default)
      }
    };
    checkConsent();
  }, [cardData?.salesman_id]);

  const loadCardData = async () => {
    try {
      const response = await api.get(`/congrats/card/${cardId}`);
      setCardData(response.data);
      // Pre-fetch store slug for the review link
      if (response.data?.salesman_id) {
        try {
          const userResp = await api.get(`/auth/user/${response.data.salesman_id}`);
          setStoreSlug(userResp.data?.store?.slug || null);
        } catch {}
        try {
          const lpResp = await api.get(`/linkpage/user/${response.data.salesman_id}`);
          setLinkPageUsername(lpResp.data?.username || null);
        } catch {}
      }
    } catch (err: any) {
      console.error('Error loading card:', err);
      setError(err.response?.data?.detail || 'Card not found');
    } finally {
      setLoading(false);
    }
  };

  const trackAction = async (action: 'download' | 'share') => {
    try {
      await api.post(`/congrats/card/${cardId}/track`, { action });
    } catch (err) {
      console.log('Tracking error:', err);
    }
  };

  const [storeSlug, setStoreSlug] = useState<string | null>(null);
  const [linkPageUsername, setLinkPageUsername] = useState<string | null>(null);

  const handleSubmitReview = async () => {
    if (reviewRating === 0 || !cardData?.salesman_id) return;
    setSubmittingReview(true);
    track('internal_review_submitted', { metadata: { rating: reviewRating } });
    try {
      // Get the store slug to submit review
      const userResp = await api.get(`/auth/user/${cardData.salesman_id}`);
      const slug = userResp.data?.store?.slug;
      setStoreSlug(slug || null);
      if (slug) {
        await api.post(`/review/submit/${slug}`, {
          customer_name: reviewName.trim() || cardData.customer_name || 'Anonymous',
          rating: reviewRating,
          text_review: reviewText.trim() || null,
        });
      }
      setReviewSubmitted(true);
    } catch (e) {
      console.error('Review submit error:', e);
    } finally {
      setSubmittingReview(false);
    }
  };

  const handleDownload = async () => {
    await trackAction('download');
    const imageUrl = `${api.defaults.baseURL}/congrats/card/${cardId}/image`;
    
    if (Platform.OS === 'web') {
      // Try Web Share API first (works on mobile browsers for "Save Image" to camera roll)
      try {
        const resp = await fetch(imageUrl);
        const blob = await resp.blob();
        const file = new File([blob], `card-${cardId}.png`, { type: 'image/png' });
        if (navigator.share && navigator.canShare && navigator.canShare({ files: [file] })) {
          await navigator.share({ files: [file], title: cardData?.headline || 'Card' });
          return;
        }
      } catch {}
      
      // Fallback: direct download
      const a = document.createElement('a');
      a.href = imageUrl;
      a.download = `card-${cardId}.png`;
      a.target = '_self';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } else {
      Linking.openURL(imageUrl);
    }
  };

  const handleShare = async (platform?: string) => {
    await trackAction('share');
    
    // Always use the tracked short URL for sharing
    const shareUrl = cardData?.short_url || 
      (Platform.OS === 'web' ? window.location.href : `https://app.imonsocial.com/congrats/${cardId}`);
    
    const shareText = `${cardData?.headline || 'Check this out!'} — from ${cardData?.salesman?.name || cardData?.store_name || 'us'}`;
    
    if (platform) {
      let url = '';
      switch (platform) {
        case 'facebook':
          url = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(shareUrl)}`;
          break;
        case 'twitter':
          url = `https://twitter.com/intent/tweet?text=${encodeURIComponent(shareText)}&url=${encodeURIComponent(shareUrl)}`;
          break;
        case 'linkedin':
          url = `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(shareUrl)}`;
          break;
        case 'instagram':
          // Download the card image first, then instruct to share
          await handleDownload();
          alert('Card saved! Now open Instagram, create a new post or story, and select the card from your gallery.');
          return;
      }
      // Use native share sheet if available, otherwise open in same window
      if (Platform.OS === 'web' && navigator.share) {
        try { await navigator.share({ url: shareUrl, text: shareText }); } catch {}
      } else if (Platform.OS === 'web') {
        window.location.href = url;
      } else {
        Linking.openURL(url);
      }
    } else {
      if (Platform.OS !== 'web') {
        Share.share({
          message: `${shareText}\n${shareUrl}`,
        });
      }
    }
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#C9A962" />
        <Text style={styles.loadingText}>Loading your card...</Text>
      </View>
    );
  }

  if (error || !cardData) {
    return (
      <View style={styles.errorContainer}>
        <Ionicons name="sad-outline" size={64} color="#8E8E93" />
        <Text style={styles.errorTitle}>Card Not Found</Text>
        <Text style={styles.errorText}>{error || 'This card may have expired or been removed.'}</Text>
      </View>
    );
  }

  const { style } = cardData;

  return (
    <ScrollView 
      style={[styles.container, { backgroundColor: style.background_color }]}
      contentContainerStyle={styles.contentContainer}
    >
      {/* Card Content */}
      <View ref={cardRef} style={styles.cardWrapper}>
        {/* Store Logo → links to company website */}
        {cardData.store?.logo && (
          <TouchableOpacity 
            style={styles.storeLogoContainer}
            onPress={() => cardData.store?.website && Linking.openURL(cardData.store.website)}
            disabled={!cardData.store?.website}
            data-testid="store-logo-link"
          >
            <Image source={{ uri: cardData.store.logo }} style={styles.storeLogo} />
          </TouchableOpacity>
        )}

        {/* Headline */}
        <Text style={[styles.headline, { color: style.accent_color }]}>
          {cardData.headline}
        </Text>

        {/* Customer Photo */}
        <View style={[styles.photoContainer, { borderColor: style.accent_color }]}>
          <Image source={{ uri: cardData.customer_photo }} style={styles.customerPhoto} />
        </View>

        {/* Customer Name */}
        <Text style={[styles.customerName, { color: style.text_color }]}>
          {cardData.customer_name}
        </Text>

        {/* Message */}
        <Text style={[styles.message, { color: style.text_color }]}>
          {cardData.message}
        </Text>

        {/* Custom Message */}
        {cardData.custom_message && (
          <Text style={[styles.customMessage, { color: style.text_color }]}>
            "{cardData.custom_message}"
          </Text>
        )}

        {/* Divider */}
        <View style={[styles.divider, { backgroundColor: style.accent_color }]} />

        {/* Salesman Info → links to digital business card */}
        {cardData.salesman && (
          <TouchableOpacity 
            style={styles.salesmanContainer}
            onPress={() => {
              track('salesman_card_clicked');
              cardData.salesman_id && Linking.openURL(`${api.defaults.baseURL?.replace('/api', '')}/card/${cardData.salesman_id}`);
            }}
            data-testid="salesman-card-link"
          >
            {cardData.salesman.photo && (
              <Image source={{ uri: cardData.salesman.photo }} style={styles.salesmanPhoto} />
            )}
            <View style={styles.salesmanInfo}>
              <Text style={[styles.salesmanName, { color: style.text_color }]}>
                {cardData.salesman.name}
              </Text>
              <Text style={[styles.salesmanTitle, { color: style.accent_color }]}>
                {cardData.salesman.title}
              </Text>
              {cardData.store?.name && (
                <Text style={[styles.storeName, { color: '#8E8E93' }]}>
                  {cardData.store.name}
                </Text>
              )}
            </View>
          </TouchableOpacity>
        )}

        {/* Footer */}
        {cardData.footer_text && (
          <Text style={[styles.footerText, { color: '#8E8E93' }]}>
            {cardData.footer_text}
          </Text>
        )}
      </View>

      {/* Quick Links  - under salesman info */}
      {cardData.salesman_id && (
        <View style={styles.quickLinksSection}>
          {/* Quick Links  - under salesman info */}
          {reviewSubmitted ? (
            /* After internal review: nudge toward public/online review page */
            <TouchableOpacity
              style={[styles.reviewCTA, { borderColor: '#34C759', backgroundColor: '#34C75910' }]}
              onPress={() => {
                track('online_review_clicked');
                if (storeSlug) {
                  Linking.openURL(`${api.defaults.baseURL?.replace('/api', '')}/review/${storeSlug}?sp=${cardData.salesman_id}`);
                }
              }}
              data-testid="card-online-review-btn"
            >
              <Ionicons name="globe-outline" size={22} color="#34C759" />
              <View style={{ flex: 1 }}>
                <Text style={styles.reviewCTATitle}>Thanks! Want to share it online?</Text>
                <Text style={[styles.reviewCTASubtitle, { color: '#34C759' }]}>Leave an online review — it means the world</Text>
              </View>
              <Ionicons name="open-outline" size={18} color="#34C759" />
            </TouchableOpacity>
          ) : (
            /* Before review: show internal review form */
            <>
              <TouchableOpacity
                style={[styles.reviewCTA, { borderColor: style.accent_color }]}
                onPress={() => setShowReviewForm(!showReviewForm)}
                data-testid="card-leave-review-btn"
              >
                <Ionicons name="star" size={20} color="#FFD60A" />
                <View style={{ flex: 1 }}>
                  <Text style={styles.reviewCTATitle}>Had a great experience?</Text>
                  <Text style={[styles.reviewCTASubtitle, { color: style.accent_color }]}>Tap to leave a review</Text>
                </View>
                <Ionicons name={showReviewForm ? 'chevron-up' : 'chevron-down'} size={18} color={style.accent_color} />
              </TouchableOpacity>

              {showReviewForm && (
                <View style={[styles.reviewFormCard, { borderColor: style.accent_color + '40' }]}>
                  <Text style={styles.reviewFormLabel}>How was your experience?</Text>
                  <View style={styles.starRow}>
                    {[1, 2, 3, 4, 5].map((star) => (
                      <TouchableOpacity key={star} onPress={() => setReviewRating(star)} data-testid={`congrats-star-${star}`}>
                        <Ionicons name={star <= reviewRating ? 'star' : 'star-outline'} size={36} color={star <= reviewRating ? '#FFD60A' : '#555'} />
                      </TouchableOpacity>
                    ))}
                  </View>
                  {reviewRating > 0 && (
                    <>
                      <TextInput style={styles.reviewInput} placeholder="Your name (optional)" placeholderTextColor="#888" value={reviewName} onChangeText={setReviewName} />
                      <TextInput style={[styles.reviewInput, { height: 80, textAlignVertical: 'top' }]} placeholder="Tell us about your experience..." placeholderTextColor="#888" value={reviewText} onChangeText={setReviewText} multiline numberOfLines={3} />
                      <TouchableOpacity style={[styles.reviewSubmitBtn, { backgroundColor: style.accent_color }]} onPress={handleSubmitReview} disabled={submittingReview} data-testid="congrats-review-submit">
                        {submittingReview ? <ActivityIndicator size="small" color="#000" /> : <Text style={styles.reviewSubmitText}>Submit Review</Text>}
                      </TouchableOpacity>
                    </>
                  )}
                </View>
              )}
            </>
          )}

          {/* Quick link row — mirrors the composer's "Share Your Stuff" (minus VCF) */}
          <View style={styles.quickLinksRow}>
            <TouchableOpacity
              style={styles.quickLinkItem}
              onPress={() => {
                track('my_card_clicked');
                Linking.openURL(`${api.defaults.baseURL?.replace('/api', '')}/card/${cardData.salesman_id}`);
              }}
              data-testid="card-view-profile-btn"
            >
              <Ionicons name="card-outline" size={18} color={style.accent_color} />
              <Text style={[styles.quickLinkText, { color: style.accent_color }]}>My Card</Text>
            </TouchableOpacity>

            <View style={styles.quickLinkDivider} />

            <TouchableOpacity
              style={styles.quickLinkItem}
              onPress={() => {
                track('my_page_clicked');
                Linking.openURL(`${api.defaults.baseURL?.replace('/api', '')}/p/${cardData.salesman_id}`);
              }}
              data-testid="card-view-landing-btn"
            >
              <Ionicons name="globe-outline" size={18} color={style.accent_color} />
              <Text style={[styles.quickLinkText, { color: style.accent_color }]}>My Page</Text>
            </TouchableOpacity>

            <View style={styles.quickLinkDivider} />

            <TouchableOpacity
              style={styles.quickLinkItem}
              onPress={() => {
                track('showcase_clicked');
                Linking.openURL(`${api.defaults.baseURL?.replace('/api', '')}/showcase/${cardData.salesman_id}`);
              }}
              data-testid="card-view-showcase-btn"
            >
              <Ionicons name="images-outline" size={18} color={style.accent_color} />
              <Text style={[styles.quickLinkText, { color: style.accent_color }]}>Showcase</Text>
            </TouchableOpacity>

            {linkPageUsername && (
              <>
                <View style={styles.quickLinkDivider} />
                <TouchableOpacity
                  style={styles.quickLinkItem}
                  onPress={() => {
                    track('links_clicked');
                    Linking.openURL(`${api.defaults.baseURL?.replace('/api', '')}/l/${linkPageUsername}`);
                  }}
                  data-testid="card-view-linkpage-btn"
                >
                  <Ionicons name="link-outline" size={18} color={style.accent_color} />
                  <Text style={[styles.quickLinkText, { color: style.accent_color }]}>Links</Text>
                </TouchableOpacity>
              </>
            )}
          </View>
        </View>
      )}

      {/* Action Buttons */}
      <View style={styles.actionsSection}>
        <Text style={styles.actionsTitle}>Share Your Experience</Text>
        
        {/* Download Button */}
        <TouchableOpacity
          style={[styles.downloadButton, { backgroundColor: style.accent_color }]}
          onPress={handleDownload}
        >
          <Ionicons name="download-outline" size={22} color="#000" />
          <Text style={styles.downloadButtonText}>Save Card to Photos</Text>
        </TouchableOpacity>

        {/* Social Share Buttons */}
        <View style={styles.socialButtons}>
          <TouchableOpacity
            style={[styles.socialButton, { backgroundColor: '#1877F2' }]}
            onPress={() => handleShare('facebook')}
          >
            <Ionicons name="logo-facebook" size={24} color="#FFF" />
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.socialButton, { backgroundColor: '#1DA1F2' }]}
            onPress={() => handleShare('twitter')}
          >
            <Ionicons name="logo-twitter" size={24} color="#FFF" />
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.socialButton, { backgroundColor: '#E4405F' }]}
            onPress={() => handleShare('instagram')}
          >
            <Ionicons name="logo-instagram" size={24} color="#FFF" />
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.socialButton, { backgroundColor: '#0A66C2' }]}
            onPress={() => handleShare('linkedin')}
          >
            <Ionicons name="logo-linkedin" size={24} color="#FFF" />
          </TouchableOpacity>
        </View>

        {/* Generic Share */}
        {Platform.OS !== 'web' && (
          <TouchableOpacity
            style={styles.moreShareButton}
            onPress={() => handleShare()}
          >
            <Ionicons name="share-outline" size={20} color="#8E8E93" />
            <Text style={styles.moreShareText}>More sharing options</Text>
          </TouchableOpacity>
        )}
      </View>

      {/* Opt-in CTA — only show if customer hasn't already consented */}
      {cardData.salesman_id && !hasExistingConsent && (
        <TouchableOpacity
          style={[styles.referralBanner, { borderColor: (style?.accent_color || '#C9A962') + '40' }]}
          onPress={() => {
            track('opt_in_clicked');
            router.push(`/opt-in/${cardId}` as any);
          }}
          data-testid="congrats-opt-in-btn"
        >
          <Ionicons name="star" size={20} color={style?.accent_color || '#C9A962'} />
          <View style={{ flex: 1, marginLeft: 10 }}>
            <Text style={styles.referralTitle}>Want to be featured?</Text>
            <Text style={[styles.referralSub, { color: style?.accent_color || '#C9A962' }]}>Opt in to appear on {cardData.salesman?.name?.split(' ')[0] || 'our'}'s showcase &amp; social media</Text>
          </View>
          <Ionicons name="chevron-forward" size={18} color={style?.accent_color || '#C9A962'} />
        </TouchableOpacity>
      )}

      {/* Refer a Friend */}
      <TouchableOpacity
        style={[styles.referralBanner, { borderColor: (style?.accent_color || '#C9A962') + '40' }]}
        onPress={async () => {
          const salespersonName = cardData.salesman?.name || 'this amazing person';
          const referText = `Check out ${salespersonName}!`;
          let referUrl = typeof window !== 'undefined' ? window.location.href : '';

          // Get a tracked referral short URL pointing to the salesperson's digital card
          if (cardData.salesman_id) {
            try {
              const res = await api.post(`/congrats/referral-link/${cardData.salesman_id}`, null, {
                params: { card_id: cardData.card_id || '' }
              });
              if (res.data?.short_url) {
                referUrl = res.data.short_url;
              }
            } catch (e) {
              console.log('Referral link fallback to page URL');
            }
          }

          if (Platform.OS === 'web') {
            if (typeof navigator !== 'undefined' && navigator.share) {
              navigator.share({ title: 'Refer a Friend', text: referText, url: referUrl });
            } else if (typeof navigator !== 'undefined') {
              navigator.clipboard?.writeText(`${referText} ${referUrl}`);
              alert('Link copied! Share it with a friend.');
            }
          } else {
            Share.share({ message: `${referText} ${referUrl}` });
          }

          // Track the referral click
          track('card_refer_clicked');
        }}
        data-testid="congrats-refer-friend"
      >
        <Ionicons name="people" size={20} color="#34C759" />
        <View style={{ flex: 1, marginLeft: 10 }}>
          <Text style={styles.referralTitle}>Know someone who could use my services?</Text>
          <Text style={styles.referralSub}>Tap to refer a friend</Text>
        </View>
        <Ionicons name="share-outline" size={18} color="#34C759" />
      </TouchableOpacity>

      <PoweredByFooter light />
      <View style={{ height: 40 }} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  contentContainer: {
    padding: 20,
    alignItems: 'center',
  },
  backBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    alignSelf: 'flex-start', paddingVertical: 8, paddingHorizontal: 4, marginBottom: 8,
  },
  backBtnText: { fontSize: 16, fontWeight: '600', color: '#FFF' },
  loadingContainer: {
    flex: 1,
    backgroundColor: '#000',
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    color: '#8E8E93',
    marginTop: 16,
    fontSize: 16,
  },
  errorContainer: {
    flex: 1,
    backgroundColor: '#000',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  errorTitle: {
    color: '#FFF',
    fontSize: 24,
    fontWeight: '600',
    marginTop: 16,
  },
  errorText: {
    color: '#8E8E93',
    fontSize: 16,
    textAlign: 'center',
    marginTop: 8,
  },
  cardWrapper: {
    width: '100%',
    maxWidth: 400,
    alignItems: 'center',
    paddingVertical: 30,
  },
  storeLogoContainer: {
    marginBottom: 20,
  },
  storeLogo: {
    width: 120,
    height: 60,
    resizeMode: 'contain',
    backgroundColor: 'transparent',
  },
  headline: {
    fontSize: 36,
    fontWeight: '700',
    textAlign: 'center',
    marginBottom: 24,
  },
  photoContainer: {
    width: 180,
    height: 180,
    borderRadius: 24,
    borderWidth: 4,
    overflow: 'hidden',
    marginBottom: 20,
  },
  customerPhoto: {
    width: '100%',
    height: '100%',
    resizeMode: 'cover',
  },
  customerName: {
    fontSize: 28,
    fontWeight: '600',
    textAlign: 'center',
    marginBottom: 16,
  },
  message: {
    fontSize: 18,
    textAlign: 'center',
    lineHeight: 28,
    paddingHorizontal: 20,
    marginBottom: 16,
  },
  customMessage: {
    fontSize: 16,
    fontStyle: 'italic',
    textAlign: 'center',
    opacity: 0.9,
    paddingHorizontal: 20,
    marginBottom: 20,
  },
  divider: {
    width: 60,
    height: 3,
    borderRadius: 2,
    marginVertical: 24,
  },
  salesmanContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
  },
  salesmanPhoto: {
    width: 56,
    height: 56,
    borderRadius: 28,
    marginRight: 16,
  },
  salesmanInfo: {
    alignItems: 'flex-start',
  },
  salesmanName: {
    fontSize: 18,
    fontWeight: '600',
  },
  salesmanTitle: {
    fontSize: 14,
    marginTop: 2,
  },
  storeName: {
    fontSize: 13,
    marginTop: 2,
  },
  footerText: {
    fontSize: 14,
    textAlign: 'center',
    marginTop: 24,
  },
  actionsSection: {
    width: '100%',
    maxWidth: 400,
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    padding: 24,
    marginTop: 16,
    alignItems: 'center',
  },
  actionsTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 20,
  },
  downloadButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
    paddingHorizontal: 32,
    borderRadius: 12,
    gap: 8,
    width: '100%',
    marginBottom: 20,
  },
  downloadButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#000',
  },
  socialButtons: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 16,
  },
  socialButton: {
    width: 50,
    height: 50,
    borderRadius: 25,
    justifyContent: 'center',
    alignItems: 'center',
  },
  moreShareButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 12,
  },
  moreShareText: {
    color: '#8E8E93',
    fontSize: 14,
  },
  // Quick links section (under salesman info)
  quickLinksSection: {
    width: '100%',
    maxWidth: 400,
    alignItems: 'center',
    gap: 12,
    marginTop: 24,
  },
  reviewCTA: {
    flexDirection: 'row',
    alignItems: 'center',
    width: '100%',
    paddingHorizontal: 20,
    paddingVertical: 16,
    borderRadius: 16,
    borderWidth: 1,
    backgroundColor: '#1C1C1E',
    gap: 14,
  },
  reviewCTATitle: { fontSize: 14, color: '#E5E5EA', fontWeight: '500', marginBottom: 2 },
  reviewCTASubtitle: { fontSize: 16, fontWeight: '700' },
  reviewFormCard: {
    backgroundColor: '#1C1C1E',
    borderRadius: 14,
    padding: 20,
    marginTop: 10,
    width: '100%',
    borderWidth: 1,
  },
  reviewFormLabel: { color: '#E5E5EA', fontSize: 15, fontWeight: '600', textAlign: 'center', marginBottom: 12 },
  starRow: { flexDirection: 'row', justifyContent: 'center', gap: 8, marginBottom: 16 },
  reviewInput: {
    backgroundColor: '#2A2A2C',
    borderRadius: 10,
    padding: 14,
    color: '#FFF',
    fontSize: 15,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: '#3A3A3C',
  },
  reviewSubmitBtn: {
    paddingVertical: 14,
    borderRadius: 12,
    alignItems: 'center',
    marginTop: 4,
  },
  reviewSubmitText: { color: '#000', fontSize: 16, fontWeight: '700' },
  referralBanner: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: '#1C1C1E',
    borderRadius: 14, padding: 16, width: '100%', borderWidth: 1, marginTop: 16,
  },
  referralTitle: { color: '#FFF', fontSize: 15, fontWeight: '700' },
  referralSub: { color: '#34C759', fontSize: 13, marginTop: 2, fontWeight: '500' },
  quickLinksRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
    paddingVertical: 4,
  },
  quickLinkItem: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingVertical: 6, paddingHorizontal: 4 },
  quickLinkText: { fontSize: 12, fontWeight: '600' },
  quickLinkDivider: { width: 1, height: 18, backgroundColor: '#2C2C2E' },
});
