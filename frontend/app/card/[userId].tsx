import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Image,
  ActivityIndicator,
  Linking,
  Platform,
  Animated,
  Dimensions,
  Share,
  Modal,
  TextInput,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Paths, File as ExpoFile } from 'expo-file-system';
import * as Sharing from 'expo-sharing';
import * as Clipboard from 'expo-clipboard';
import QRCode from 'react-native-qrcode-svg';
import api from '../../services/api';
import { trackCustomerAction } from '../../services/tracking';
import { useAuthStore } from '../../store/authStore';
import { PoweredByFooter } from '../../components/PoweredByFooter';
import { SEOHead } from '../../components/SEOHead';

// Web-safe URL opener  - Linking.openURL uses window.open('_blank')
// which popup blockers intercept for sms: and mailto: protocols.
// Using an anchor click or location.href is more reliable on web.
const openProtocolUrl = (url: string) => {
  if (Platform.OS === 'web' && typeof document !== 'undefined') {
    const a = document.createElement('a');
    a.href = url;
    a.target = '_self';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  } else {
    Linking.openURL(url);
  }
};

const { width: SCREEN_WIDTH } = Dimensions.get('window');
const CARD_WIDTH = SCREEN_WIDTH - 40;
const CARD_HEIGHT = 480;

// Theme palettes
type ThemePalette = {
  bg: string;
  card: string;
  cardBorder: string;
  text: string;
  textSecondary: string;
  textMuted: string;
  accent: string;
  divider: string;
  inputBg: string;
  inputBorder: string;
  overlay: string;
  surface: string;
  shadow: string;
};

const buildTheme = (mode: 'dark' | 'light', brandKit?: any): ThemePalette => {
  const accent = brandKit?.accent_color || brandKit?.primary_color || '#C9A962';
  if (mode === 'light') {
    return {
      bg: '#F8F7F4',
      card: '#FFFFFF',
      cardBorder: '#E8E4DC',
      text: '#1A1A1A',
      textSecondary: '#6B6B6B',
      textMuted: '#999999',
      accent,
      divider: accent,
      inputBg: '#F0EDE6',
      inputBorder: '#DDD8CE',
      overlay: 'rgba(0, 0, 0, 0.5)',
      surface: '#EDEAE3',
      shadow: accent,
    };
  }
  return {
    bg: '#0D0D0D',
    card: '#1A1A1A',
    cardBorder: '#333',
    text: '#FFFFFF',
    textSecondary: '#CCC',
    textMuted: '#888',
    accent,
    divider: accent,
    inputBg: '#111',
    inputBorder: '#2A2A2C',
    overlay: 'rgba(0, 0, 0, 0.7)',
    surface: '#2A2A2A',
    shadow: accent,
  };
};

// Social platform icons with brand colors
const SOCIAL_PLATFORMS = [
  { key: 'website', icon: 'globe-outline', color: '#34C759', baseUrl: '' },
  { key: 'facebook', icon: 'logo-facebook', color: '#1877F2', baseUrl: 'https://facebook.com/' },
  { key: 'instagram', icon: 'logo-instagram', color: '#E4405F', baseUrl: 'https://instagram.com/' },
  { key: 'twitter', icon: 'logo-twitter', color: '#1DA1F2', baseUrl: 'https://x.com/' },
  { key: 'linkedin', icon: 'logo-linkedin', color: '#0A66C2', baseUrl: 'https://linkedin.com/in/' },
  { key: 'youtube', icon: 'logo-youtube', color: '#FF0000', baseUrl: 'https://youtube.com/@' },
  { key: 'tiktok', icon: 'logo-tiktok', color: '#69C9D0', baseUrl: 'https://tiktok.com/@' },
];

export default function DigitalCardPage() {
  const router = useRouter();
  const { userId, campaign, contact, preview, cid } = useLocalSearchParams();
  const [loading, setLoading] = useState(true);
  const [cardData, setCardData] = useState<any>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [isFlipped, setIsFlipped] = useState(false);
  const [showShareModal, setShowShareModal] = useState(false);
  const [feedbackRating, setFeedbackRating] = useState(0);
  const [feedbackText, setFeedbackText] = useState('');
  const [feedbackName, setFeedbackName] = useState('');
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(preview === 'reviewed');
  const [submittingFeedback, setSubmittingFeedback] = useState(false);
  const [showReviewForm, setShowReviewForm] = useState(false);
  const [isOwner, setIsOwner] = useState(false);
  const [shareRecipientName, setShareRecipientName] = useState('');
  const [shareRecipientPhone, setShareRecipientPhone] = useState('');
  const [shareRecipientEmail, setShareRecipientEmail] = useState('');
  const [matchModalVisible, setMatchModalVisible] = useState(false);
  const [matchInfo, setMatchInfo] = useState<any>(null);
  const [pendingShareAction, setPendingShareAction] = useState<{platform: string; payload: any} | null>(null);
  const [mounted, setMounted] = useState(false);
  
  // Derive theme from brand kit
  const themeMode = (cardData?.brand_kit?.page_theme === 'light') ? 'light' : 'dark';
  const theme = buildTheme(themeMode, cardData?.brand_kit);
  const dynamicStyles = getDynamicStyles(theme);
  
  // Tracking context — only track when NOT the owner (customer viewing)
  const trackCtx = {
    salesperson_id: userId as string,
    contact_id: (cid as string) || undefined,
  };
  const track = (action: string, extra?: Record<string, any>) => {
    if (!isOwner) {
      trackCustomerAction('card', action, { ...trackCtx, ...extra });
    }
  };
  
  // Direct shareable link - always use production URL like congrats cards
  const cardUrl = `https://app.imonsocial.com/card/${userId}`;
  
  // Animation values
  const flipAnimation = useRef(new Animated.Value(0)).current;
  const qrRef = useRef<any>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    loadCardData();
    checkOwnership();
  }, [userId]);

  const checkOwnership = async () => {
    try {
      const user = useAuthStore.getState().user;
      if (user) {
        setIsOwner(user._id === userId || user.id === userId);
      }
    } catch {}
  };

  const loadCardData = async () => {
    try {
      const cidParam = cid ? `?cid=${cid}` : '';
      const response = await api.get(`/card/data/${userId}${cidParam}`);
      setCardData(response.data);
    } catch (error) {
      console.error('Error loading card:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitFeedback = async () => {
    if (feedbackRating === 0) return;
    setSubmittingFeedback(true);
    track('internal_review_submitted', { metadata: { rating: feedbackRating } });
    try {
      const storeSlug = cardData?.store?.slug || 'default';
      await api.post(`/review/submit/${storeSlug}`, {
        customer_name: feedbackName.trim() || 'Anonymous',
        rating: feedbackRating,
        text_review: feedbackText.trim() || null,
        salesperson_id: userId,
        salesperson_name: cardData?.user?.name,
      });
      setFeedbackSubmitted(true);
    } catch (e) {
      console.error('Feedback error:', e);
    } finally {
      setSubmittingFeedback(false);
    }
  };

  // Flip card animation
  const flipCard = () => {
    Animated.spring(flipAnimation, {
      toValue: isFlipped ? 0 : 1,
      friction: 8,
      tension: 10,
      useNativeDriver: true,
    }).start();
    setIsFlipped(!isFlipped);
  };

  // Interpolations for flip
  const frontInterpolate = flipAnimation.interpolate({
    inputRange: [0, 1],
    outputRange: ['0deg', '180deg'],
  });
  
  const backInterpolate = flipAnimation.interpolate({
    inputRange: [0, 1],
    outputRange: ['180deg', '360deg'],
  });

  const frontAnimatedStyle = {
    transform: [{ rotateY: frontInterpolate }],
  };
  
  const backAnimatedStyle = {
    transform: [{ rotateY: backInterpolate }],
  };

  const handleSaveContact = async () => {
    setSaving(true);
    track('vcard_saved');
    try {
      // Track the save + enroll in campaign if specified
      await api.post(`/card/save/${userId}`, {
        contact_id: contact,
        campaign_id: campaign,
      });

      if (Platform.OS === 'web' && typeof window !== 'undefined') {
        window.location.href = `/api/card/vcard/${userId}`;
      } else {
        // Native: Save and share using new Expo File System API
        const vcardResponse = await api.get(`/card/vcard/${userId}`);
        const { vcard, filename } = vcardResponse.data;
        const file = new ExpoFile(Paths.document, filename);
        await file.write(vcard);
        
        if (await Sharing.isAvailableAsync()) {
          await Sharing.shareAsync(file.uri, {
            mimeType: 'text/vcard',
            dialogTitle: 'Save Contact',
          });
        }
      }

      setSaved(true);
      setShowShareModal(false);
    } catch (error) {
      console.error('Error saving contact:', error);
    } finally {
      setSaving(false);
    }
  };

  // Share via link
  const handleShareLink = async () => {
    track('share_clicked', { platform: 'link' });
    try {
      const cardUrl = `https://app.imonsocial.com/card/${userId}`;
      if (Platform.OS === 'web') {
        if (typeof navigator !== 'undefined' && navigator.share) {
          await navigator.share({
            title: cardData?.user?.name ? `${cardData.user.name}'s Business Card` : 'My Business Card',
            text: 'Check out my digital business card:',
            url: cardUrl,
          });
        } else if (typeof navigator !== 'undefined') {
          await navigator.clipboard.writeText(cardUrl);
        }
      } else {
        await Share.share({
          message: `Check out my digital business card: ${cardUrl}`,
        });
      }
      setShowShareModal(false);
    } catch (error) {
      console.error('Error sharing link:', error);
    }
  };

  // Copy link to clipboard
  const handleCopyLink = async () => {
    track('share_clicked', { platform: 'copy_link' });
    try {
      const cardUrl = `https://app.imonsocial.com/card/${userId}`;
      await Clipboard.setStringAsync(cardUrl);
      if (Platform.OS === 'web') {
        alert('Link copied to clipboard!');
      }
      setShowShareModal(false);
    } catch (error) {
      console.error('Error copying link:', error);
    }
  };

  // Log contact event for share actions
  const logShareEvent = async (platform: string, forceAction?: string) => {
    const phone = shareRecipientPhone.trim();
    const email = shareRecipientEmail.trim();
    const name = shareRecipientName.trim();
    if (!phone && !email) return; // Nothing to log

    // Get current user ID from auth store
    const currentUserId = useAuthStore.getState().user?._id || '';
    if (!currentUserId) return;

    const payload: any = {
      phone, email, name,
      event_type: 'digital_card_shared',
      event_title: 'Digital Card Shared',
      event_description: `Shared digital card via ${platform}`,
      event_icon: 'card',
      event_color: '#C9A962',
    };
    if (forceAction) payload.force_action = forceAction;

    try {
      const res = await api.post(`/contacts/${currentUserId}/find-or-create-and-log`, payload);
      if (res.data.needs_confirmation) {
        setMatchInfo(res.data);
        setPendingShareAction({ platform, payload });
        setMatchModalVisible(true);
      }
    } catch (err) {
      console.error('Failed to log share event:', err);
    }
  };

  const resolveMatchAction = async (action: string) => {
    setMatchModalVisible(false);
    if (!pendingShareAction) return;
    const currentUserId = useAuthStore.getState().user?._id || '';
    if (!currentUserId) return;

    try {
      await api.post(`/contacts/${currentUserId}/find-or-create-and-log`, {
        ...pendingShareAction.payload,
        force_action: action,
      });
    } catch {}
    setMatchInfo(null);
    setPendingShareAction(null);
  };

  // Share via SMS
  const handleShareSMS = () => {
    track('share_clicked', { platform: 'sms' });
    const cardUrl = `https://app.imonsocial.com/card/${userId}`;
    const message = `Check out my digital business card: ${cardUrl}`;
    const phone = shareRecipientPhone.trim();
    const isApple = typeof navigator !== 'undefined' ? /iPad|iPhone|iPod|Macintosh/.test(navigator.userAgent) : false;
    const sep = isApple ? '&' : '?';
    const smsUrl = phone
      ? `sms:${phone}${sep}body=${encodeURIComponent(message)}`
      : `sms:${sep === '&' ? '&' : '?'}body=${encodeURIComponent(message)}`;
    openProtocolUrl(smsUrl);
    logShareEvent('sms');
    setShowShareModal(false);
    setShareRecipientName('');
    setShareRecipientPhone('');
    setShareRecipientEmail('');
  };

  // Share via Email
  const handleShareEmail = () => {
    track('share_clicked', { platform: 'email' });
    const cardUrl = `https://app.imonsocial.com/card/${userId}`;
    const subject = `${cardData?.user?.name || 'My'} Digital Business Card`;
    const body = `Hi!\n\nHere's my digital business card:\n${cardUrl}\n\nLooking forward to connecting!`;
    const email = shareRecipientEmail.trim();
    const mailto = email
      ? `mailto:${email}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`
      : `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    openProtocolUrl(mailto);
    logShareEvent('email');
    setShowShareModal(false);
    setShareRecipientName('');
    setShareRecipientPhone('');
    setShareRecipientEmail('');
  };

  // Share QR Code - uses short URL for cleaner sharing
  const handleShareQR = async () => {
    track('share_clicked', { platform: 'qr_code' });
    try {
      const cardUrl = `https://app.imonsocial.com/card/${userId}`;
      if (Platform.OS === 'web') {
        if (typeof navigator !== 'undefined' && navigator.share) {
          await navigator.share({
            title: cardData?.user?.name ? `${cardData.user.name}'s Business Card` : 'My Business Card',
            text: 'Check out my digital business card:',
            url: cardUrl,
          });
        } else if (typeof navigator !== 'undefined') {
          await navigator.clipboard.writeText(cardUrl);
        }
      } else {
        await Share.share({
          message: `Check out my digital business card: ${cardUrl}`,
        });
      }
    } catch (error) {
      console.error('Error sharing:', error);
    }
  };

  // Download QR as image (web only for now)
  const handleDownloadQR = async () => {
    if (Platform.OS === 'web' && typeof document !== 'undefined' && qrRef.current) {
      try {
        qrRef.current.toDataURL((dataUrl: string) => {
          const link = document.createElement('a');
          link.download = `${cardData?.user?.name || 'contact'}-qr.png`;
          link.href = dataUrl;
          link.click();
        });
      } catch (error) {
        console.error('Error downloading QR:', error);
      }
    } else {
      // On native, use share
      handleShareQR();
    }
  };

  const renderStars = (rating: number) => {
    return (
      <View style={styles.starsRow}>
        {[1, 2, 3, 4, 5].map((star) => (
          <Ionicons
            key={star}
            name={star <= rating ? 'star' : 'star-outline'}
            size={14}
            color="#FFD700"
          />
        ))}
      </View>
    );
  };

  if (!mounted || loading) {
    return (
      <View style={[styles.loadingContainer, { backgroundColor: '#0D0D0D' }]} {...{ suppressHydrationWarning: true }}>
        <ActivityIndicator size="large" color="#C9A962" />
      </View>
    );
  }

  if (!cardData) {
    return (
      <View style={[styles.errorContainer, { backgroundColor: '#0D0D0D' }]}>
        <Ionicons name="alert-circle" size={64} color="#FF3B30" />
        <Text style={styles.errorTitle}>Card Not Found</Text>
        <Text style={styles.errorText}>This digital card doesn't exist.</Text>
      </View>
    );
  }

  const { user, store, testimonials } = cardData;
  const partnerBrand = cardData.partner_branding;
  // QR code and share links use the direct production URL

  // Filter active social links
  const activeSocialLinks = SOCIAL_PLATFORMS.filter(
    p => user.social_links?.[p.key]
  );

  return (
    <View style={[styles.container, { backgroundColor: theme.bg }]}>
      <SEOHead type="card" id={userId as string} />
      <SafeAreaView edges={['top', 'bottom']} style={{ flex: 1 }}>
        {/* Header */}
        <View style={[styles.header, { borderBottomColor: theme.cardBorder }]}>
          <View style={{ width: 28 }} />
          <Text style={[styles.headerTitle, { color: theme.text }]}>My Digital Card</Text>
          <View style={{ width: 28 }} />
        </View>
        <ScrollView 
          style={styles.scrollView}
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          {/* Flip Card Container */}
          <View style={styles.cardContainer}>
            {/* Front of Card */}
            <Animated.View style={[
              styles.card,
              styles.cardFront,
              frontAnimatedStyle,
              { backgroundColor: theme.card, borderColor: theme.cardBorder, shadowColor: theme.shadow },
            ]}>
              {/* Flip indicator - top right corner */}
              <TouchableOpacity 
                style={styles.flipCorner} 
                onPress={flipCard}
                data-testid="flip-card-btn"
              >
                <View style={[styles.flipCornerInner, { backgroundColor: `${theme.accent}25` }]}>
                  <Ionicons name="qr-code" size={16} color={theme.accent} />
                </View>
                <View style={[styles.cornerFold, { borderRightColor: theme.accent }]} />
              </TouchableOpacity>

              {/* Cover Photo Banner — full-width at top of card */}
              {user.cover_photo_url ? (
                <View style={[styles.coverBanner, { overflow: 'hidden' }]}>
                  <Image
                    source={{ uri: user.cover_photo_url }}
                    style={StyleSheet.absoluteFill}
                    resizeMode="cover"
                  />
                  {/* Gradient fade to card background */}
                  <View style={styles.coverBannerGrad} />
                </View>
              ) : null}

              {/* Store Logo */}
              {store?.logo_url && (
                <Image 
                  source={{ uri: store.logo_url }} 
                  style={styles.storeLogo}
                  resizeMode="contain"
                />
              )}
              
              {/* Profile Photo */}
              <View style={styles.photoContainer}>
                {user.photo_url ? (
                  <Image 
                    source={{ uri: user.photo_url }} 
                    style={[styles.photo, { borderColor: theme.accent }]}
                  />
                ) : (
                  <View style={[styles.photoPlaceholder, { backgroundColor: theme.surface, borderColor: theme.accent }]}>
                    <Ionicons name="person" size={48} color={theme.textMuted} />
                  </View>
                )}
              </View>
              
              {/* Name & Title */}
              <Text style={[styles.userName, { color: theme.text }]}>{user.name}</Text>
              <Text style={[styles.userTitle, { color: theme.accent }]}>{user.title || 'Sales Professional'}</Text>
              
              {store?.name && (
                <Text style={[styles.storeName, { color: theme.textMuted }]}>{store.name}</Text>
              )}

              {/* Divider */}
              <View style={[styles.divider, { backgroundColor: theme.divider }]} />

              {/* Social Links */}
              {activeSocialLinks.length > 0 && (
                <View style={styles.socialRow}>
                  {activeSocialLinks.map((platform) => {
                    const username = user.social_links[platform.key];
                    let url;
                    if (username.startsWith('http')) {
                      url = username;
                    } else if (platform.key === 'website') {
                      url = `https://${username}`;
                    } else {
                      url = `${platform.baseUrl}${username}`;
                    }
                    return (
                      <TouchableOpacity
                        key={platform.key}
                        style={[styles.socialIcon, { backgroundColor: theme.surface }]}
                        onPress={() => {
                          track('social_clicked', { platform: platform.key, url });
                          Linking.openURL(url);
                        }}
                        data-testid={`social-${platform.key}`}
                      >
                        <Ionicons name={platform.icon as any} size={22} color={platform.color} />
                      </TouchableOpacity>
                    );
                  })}
                </View>
              )}
            </Animated.View>

            {/* Back of Card - QR Code */}
            <Animated.View style={[
              styles.card,
              styles.cardBack,
              backAnimatedStyle,
              { backgroundColor: theme.card, borderColor: theme.cardBorder, shadowColor: theme.shadow },
            ]}>
              {/* Flip back indicator - top right corner */}
              <TouchableOpacity 
                style={styles.flipCorner} 
                onPress={flipCard}
                data-testid="flip-back-btn"
              >
                <View style={[styles.flipCornerInner, { backgroundColor: `${theme.accent}25` }]}>
                  <Ionicons name="person" size={16} color={theme.accent} />
                </View>
                <View style={[styles.cornerFold, { borderRightColor: theme.accent }]} />
              </TouchableOpacity>

              <Text style={[styles.qrTitle, { color: theme.accent }]}>Scan to Connect</Text>
              
              <View style={styles.qrContainer}>
                <QRCode
                  value={cardUrl}
                  size={200}
                  color="#1A1A1A"
                  backgroundColor="#FFFFFF"
                  getRef={(ref) => (qrRef.current = ref)}
                />
              </View>

              <Text style={[styles.userName, { color: theme.text }]} numberOfLines={1}>{user.name}</Text>
              <Text style={[styles.userTitle, { color: theme.accent }]}>{user.title || 'Sales Professional'}</Text>

              {/* QR Action Buttons */}
              <View style={styles.qrActions}>
                <TouchableOpacity 
                  style={[styles.qrActionBtn, { backgroundColor: theme.accent }]}
                  onPress={handleShareQR}
                  data-testid="share-qr-btn"
                >
                  <Ionicons name="share-outline" size={20} color={themeMode === 'dark' ? '#FFF' : '#FFF'} />
                  <Text style={[styles.qrActionText, { color: themeMode === 'light' ? '#FFF' : '#1A1A1A' }]}>Share</Text>
                </TouchableOpacity>
                <TouchableOpacity 
                  style={[styles.qrActionBtn, { backgroundColor: theme.accent }]}
                  onPress={handleDownloadQR}
                  data-testid="download-qr-btn"
                >
                  <Ionicons name="download-outline" size={20} color={themeMode === 'dark' ? '#FFF' : '#FFF'} />
                  <Text style={[styles.qrActionText, { color: themeMode === 'light' ? '#FFF' : '#1A1A1A' }]}>Download</Text>
                </TouchableOpacity>
              </View>
            </Animated.View>
          </View>

          {/* Share Contact Button - Below Card */}
          <TouchableOpacity
            style={[dynamicStyles.saveButton, saved && dynamicStyles.saveButtonSaved]}
            onPress={isOwner ? () => setShowShareModal(true) : handleSaveContact}
            disabled={saving}
            data-testid="share-contact-btn"
          >
            {saved ? (
              <>
                <Ionicons name="checkmark-circle" size={22} color={themeMode === 'light' ? '#FFF' : '#1A1A1A'} />
                <Text style={dynamicStyles.saveButtonText}>{isOwner ? 'Contact Shared!' : 'Contact Saved!'}</Text>
              </>
            ) : saving ? (
              <>
                <ActivityIndicator size="small" color={themeMode === 'light' ? '#FFF' : '#1A1A1A'} />
                <Text style={dynamicStyles.saveButtonText}>Saving...</Text>
              </>
            ) : (
              <>
                <Ionicons name={isOwner ? "share-social" : "download-outline"} size={22} color={themeMode === 'light' ? '#FFF' : '#1A1A1A'} />
                <Text style={dynamicStyles.saveButtonText}>{isOwner ? 'Share My Contact' : 'Save My Contact'}</Text>
              </>
            )}
          </TouchableOpacity>

          {/* Quick Actions */}
          <View style={styles.quickActionsRow}>
            {user.phone && (
              <TouchableOpacity
                style={styles.quickActionButton}
                onPress={() => {
                  track('call_clicked', { url: `tel:${user.phone}` });
                  openProtocolUrl(`tel:${user.phone}`);
                }}
                data-testid="quick-call-btn"
              >
                <View style={[styles.quickActionIcon, { backgroundColor: theme.card, borderColor: theme.cardBorder }]}>
                  <Ionicons name="call" size={22} color="#34C759" />
                </View>
                <Text style={[styles.quickActionLabel, { color: theme.textMuted }]}>Call</Text>
              </TouchableOpacity>
            )}
            
            {user.phone && (
              <TouchableOpacity
                style={styles.quickActionButton}
                onPress={() => {
                  track('text_clicked', { url: `sms:${user.phone}` });
                  openProtocolUrl(`sms:${user.phone}`);
                }}
                data-testid="quick-text-btn"
              >
                <View style={[styles.quickActionIcon, { backgroundColor: theme.card, borderColor: theme.cardBorder }]}>
                  <Ionicons name="chatbubble" size={22} color="#007AFF" />
                </View>
                <Text style={[styles.quickActionLabel, { color: theme.textMuted }]}>Text</Text>
              </TouchableOpacity>
            )}
            
            {user.email && (
              <TouchableOpacity
                style={styles.quickActionButton}
                onPress={() => {
                  track('email_clicked', { url: `mailto:${user.email}` });
                  openProtocolUrl(`mailto:${user.email}`);
                }}
                data-testid="quick-email-btn"
              >
                <View style={[styles.quickActionIcon, { backgroundColor: theme.card, borderColor: theme.cardBorder }]}>
                  <Ionicons name="mail" size={22} color="#FF9500" />
                </View>
                <Text style={[styles.quickActionLabel, { color: theme.textMuted }]}>Email</Text>
              </TouchableOpacity>
            )}

            <TouchableOpacity
              style={styles.quickActionButton}
              onPress={flipCard}
              data-testid="quick-qr-btn"
            >
              <View style={[styles.quickActionIcon, { backgroundColor: theme.card, borderColor: theme.cardBorder }]}>
                <Ionicons name="qr-code" size={22} color={theme.accent} />
              </View>
              <Text style={[styles.quickActionLabel, { color: theme.textMuted }]}>QR Code</Text>
            </TouchableOpacity>
          </View>

          {/* Leave a Review */}
          <View style={styles.section}>
            {feedbackSubmitted ? (
              <TouchableOpacity 
                style={[dynamicStyles.reviewCTABanner, { borderColor: '#34C759', backgroundColor: '#34C75910' }]}
                onPress={() => {
                  track('online_review_clicked');
                  const slug = cardData?.store?.slug;
                  if (slug) {
                    router.push(`/review/${slug}?sp=${userId}` as any);
                  }
                }}
                data-testid="online-review-cta"
              >
                <Ionicons name="globe-outline" size={22} color="#34C759" />
                <View style={{ flex: 1, marginLeft: 12 }}>
                  <Text style={[styles.reviewCTABannerTitle, { color: theme.text }]}>Thanks! Want to share it online?</Text>
                  <Text style={[styles.reviewCTABannerSub, { color: '#34C759' }]}>Leave a Google review — it means the world</Text>
                </View>
                <Ionicons name="open-outline" size={20} color="#34C759" />
              </TouchableOpacity>
            ) : (
              <>
                <TouchableOpacity 
                  style={dynamicStyles.reviewCTABanner}
                  onPress={() => {
                    track('review_clicked');
                    setShowReviewForm(!showReviewForm);
                  }}
                  data-testid="leave-review-cta"
                >
                  <Ionicons name="star" size={22} color="#FFD60A" />
                  <View style={{ flex: 1, marginLeft: 12 }}>
                    <Text style={[styles.reviewCTABannerTitle, { color: theme.text }]}>Had a great experience?</Text>
                    <Text style={[styles.reviewCTABannerSub, { color: theme.accent }]}>Tap to leave a review</Text>
                  </View>
                  <Ionicons name={showReviewForm ? 'chevron-up' : 'chevron-down'} size={20} color={theme.accent} />
                </TouchableOpacity>

                {showReviewForm && (
                  <View style={dynamicStyles.feedbackCard}>
                    <Text style={[styles.feedbackLabel, { color: theme.textSecondary }]}>How was your experience?</Text>
                    <View style={styles.starRow} data-testid="feedback-stars">
                      {[1, 2, 3, 4, 5].map((star) => (
                        <TouchableOpacity key={star} onPress={() => setFeedbackRating(star)} data-testid={`star-${star}`}>
                          <Ionicons name={star <= feedbackRating ? 'star' : 'star-outline'} size={36} color={star <= feedbackRating ? '#FFD60A' : theme.cardBorder} />
                        </TouchableOpacity>
                      ))}
                    </View>
                    {feedbackRating > 0 && (
                      <>
                        <TextInput style={dynamicStyles.feedbackInput} placeholder="Your name (optional)" placeholderTextColor={theme.textMuted} value={feedbackName} onChangeText={setFeedbackName} data-testid="feedback-name" />
                        <TextInput style={[dynamicStyles.feedbackInput, styles.feedbackTextArea]} placeholder="Tell us about your experience..." placeholderTextColor={theme.textMuted} value={feedbackText} onChangeText={setFeedbackText} multiline numberOfLines={3} data-testid="feedback-text" />
                        <TouchableOpacity style={[dynamicStyles.feedbackSubmitBtn]} onPress={handleSubmitFeedback} disabled={submittingFeedback} data-testid="feedback-submit">
                          {submittingFeedback ? <ActivityIndicator size="small" color={themeMode === 'light' ? '#FFF' : '#000'} /> : <Text style={dynamicStyles.feedbackSubmitText}>Submit Review</Text>}
                        </TouchableOpacity>
                      </>
                    )}
                  </View>
                )}
              </>
            )}
          </View>

          {/* Refer a Friend */}
          <View style={styles.section}>
            <TouchableOpacity
              style={dynamicStyles.referralBanner}
              onPress={() => {
                track('refer_clicked');
                const currentHref = typeof window !== 'undefined' ? window.location.href : `https://app.imonsocial.com/card/${userId}`;
                const shareText = `Check out ${user.name || 'my contact'}! ${currentHref}`;
                if (Platform.OS === 'web') {
                  if (typeof navigator !== 'undefined' && navigator.share) {
                    navigator.share({ title: `Refer ${user.name}`, text: shareText, url: currentHref });
                  } else if (typeof navigator !== 'undefined') {
                    navigator.clipboard?.writeText(shareText);
                    alert('Link copied! Share it with a friend.');
                  }
                } else {
                  Share.share({ message: shareText });
                }
              }}
              data-testid="refer-friend-btn"
            >
              <Ionicons name="people" size={22} color="#34C759" />
              <View style={{ flex: 1, marginLeft: 12 }}>
                <Text style={[styles.referralBannerTitle, { color: theme.text }]}>Know someone who could use my services?</Text>
                <Text style={styles.referralBannerSub}>Tap to refer a friend</Text>
              </View>
              <Ionicons name="share-outline" size={20} color="#34C759" />
            </TouchableOpacity>
          </View>

          {/* Bio Section */}
          {user.bio && (
            <View style={styles.section}>
              <Text style={[styles.sectionTitle, { color: theme.accent }]}>About Me</Text>
              <View style={[dynamicStyles.infoCard]}>
                <Text style={[styles.bioText, { color: theme.textSecondary }]}>{user.bio}</Text>
              </View>
            </View>
          )}

          {/* Contact Info Section */}
          <View style={styles.section}>
            <Text style={[styles.sectionTitle, { color: theme.accent }]}>Contact Information</Text>
            <View style={dynamicStyles.infoCard}>
              {user.phone && (
                <View style={[styles.infoRow, { borderBottomColor: theme.surface }]}>
                  <Ionicons name="call-outline" size={20} color={theme.accent} />
                  <Text style={[styles.infoText, { color: theme.text }]}>{user.phone}</Text>
                </View>
              )}
              {user.email && (
                <View style={[styles.infoRow, { borderBottomColor: theme.surface }]}>
                  <Ionicons name="mail-outline" size={20} color={theme.accent} />
                  <Text style={[styles.infoText, { color: theme.text }]}>{user.email}</Text>
                </View>
              )}
              {store?.address && (
                <View style={[styles.infoRow, { borderBottomColor: theme.surface }]}>
                  <Ionicons name="location-outline" size={20} color={theme.accent} />
                  <Text style={[styles.infoText, { color: theme.text }]}>
                    {store.address}{store.city ? `, ${store.city}` : ''}{store.state ? `, ${store.state}` : ''}{store.zip_code ? ` ${store.zip_code}` : ''}
                  </Text>
                </View>
              )}
              {(store?.address || store?.city) && (
                <TouchableOpacity 
                  style={[styles.infoRow, { borderBottomColor: theme.surface }]}
                  onPress={() => {
                    const fullAddress = [store.address, store.city, store.state, store.zip_code].filter(Boolean).join(', ');
                    const encoded = encodeURIComponent(fullAddress);
                    track('directions_clicked', { address: fullAddress });
                    if (Platform.OS === 'ios') {
                      Linking.openURL(`maps://maps.apple.com/?q=${encoded}`).catch(() => {
                        Linking.openURL(`https://maps.google.com/maps?q=${encoded}`);
                      });
                    } else {
                      Linking.openURL(`geo:0,0?q=${encoded}`).catch(() => {
                        Linking.openURL(`https://maps.google.com/maps?q=${encoded}`);
                      });
                    }
                  }}
                  data-testid="directions-btn"
                >
                  <Ionicons name="navigate-outline" size={20} color={theme.accent} />
                  <Text style={[styles.infoText, styles.linkText, { color: theme.accent }]}>Get Directions</Text>
                </TouchableOpacity>
              )}
              {store?.website && (
                <TouchableOpacity 
                  style={[styles.infoRow, { borderBottomWidth: 0 }]}
                  onPress={() => {
                    const url = store.website.startsWith('http') ? store.website : `https://${store.website}`;
                    track('website_clicked', { url });
                    openProtocolUrl(url);
                  }}
                >
                  <Ionicons name="globe-outline" size={20} color={theme.accent} />
                  <Text style={[styles.infoText, styles.linkText, { color: theme.accent }]}>{store.website}</Text>
                </TouchableOpacity>
              )}
            </View>
          </View>

          {/* Testimonials */}
          {testimonials && testimonials.length > 0 && (
            <View style={styles.section}>
              <Text style={[styles.sectionTitle, { color: theme.accent }]}>What Customers Say</Text>
              {testimonials.map((t: any) => (
                <View key={t.id} style={dynamicStyles.testimonialCard}>
                  <View style={styles.testimonialHeader}>
                    <Text style={[styles.testimonialName, { color: theme.text }]}>{t.customer_name}</Text>
                    {renderStars(t.rating)}
                  </View>
                  {t.text && (
                    <Text style={[styles.testimonialText, { color: theme.textMuted }]}>"{t.text}"</Text>
                  )}
                </View>
              ))}
            </View>
          )}

          {/* Footer */}
          <PoweredByFooter />
        </ScrollView>
      </SafeAreaView>

      {/* Share Modal */}
      <Modal
        visible={showShareModal}
        transparent
        animationType="slide"
        onRequestClose={() => setShowShareModal(false)}
      >
        <TouchableOpacity 
          style={[styles.modalOverlay, { backgroundColor: theme.overlay }]}
          activeOpacity={1}
          onPress={() => setShowShareModal(false)}
        >
          <TouchableOpacity activeOpacity={1} onPress={() => {}}>
          <View style={dynamicStyles.shareModal}>
            <View style={dynamicStyles.shareModalHandle} />
            <Text style={[styles.shareModalTitle, { color: theme.text }]}>{isOwner ? 'Share My Contact' : 'Save My Contact'}</Text>
            <Text style={[styles.shareModalSubtitle, { color: theme.textMuted }]}>Choose how to share your digital card</Text>
            
            {/* Recipient Info */}
            {isOwner && (
              <View style={styles.recipientSection}>
                <Text style={[styles.recipientLabel, { color: theme.textMuted }]}>SEND TO (OPTIONAL)</Text>
                <TextInput
                  style={[dynamicStyles.recipientInput]}
                  placeholder="Recipient Name"
                  placeholderTextColor={theme.textMuted}
                  value={shareRecipientName}
                  onChangeText={setShareRecipientName}
                  data-testid="card-share-name"
                />
                <TextInput
                  style={[dynamicStyles.recipientInput]}
                  placeholder="Phone"
                  placeholderTextColor={theme.textMuted}
                  value={shareRecipientPhone}
                  onChangeText={setShareRecipientPhone}
                  keyboardType="phone-pad"
                  data-testid="card-share-phone"
                />
                <TextInput
                  style={[dynamicStyles.recipientInput]}
                  placeholder="Email"
                  placeholderTextColor={theme.textMuted}
                  value={shareRecipientEmail}
                  onChangeText={setShareRecipientEmail}
                  keyboardType="email-address"
                  autoCapitalize="none"
                  data-testid="card-share-email"
                />
              </View>
            )}
            
            <View style={styles.shareOptionsGrid}>
              <TouchableOpacity 
                style={styles.shareOption}
                onPress={handleShareLink}
                data-testid="share-via-link"
              >
                <View style={[styles.shareOptionIcon, { backgroundColor: '#007AFF20' }]}>
                  <Ionicons name="share-outline" size={24} color="#007AFF" />
                </View>
                <Text style={[styles.shareOptionText, { color: theme.text }]}>Share Link</Text>
              </TouchableOpacity>

              <TouchableOpacity 
                style={styles.shareOption}
                onPress={handleCopyLink}
                data-testid="copy-link"
              >
                <View style={[styles.shareOptionIcon, { backgroundColor: '#5856D620' }]}>
                  <Ionicons name="copy-outline" size={24} color="#5856D6" />
                </View>
                <Text style={[styles.shareOptionText, { color: theme.text }]}>Copy Link</Text>
              </TouchableOpacity>

              <TouchableOpacity 
                style={styles.shareOption}
                onPress={handleShareSMS}
                data-testid="share-via-sms"
              >
                <View style={[styles.shareOptionIcon, { backgroundColor: '#34C75920' }]}>
                  <Ionicons name="chatbubble-outline" size={24} color="#34C759" />
                </View>
                <Text style={[styles.shareOptionText, { color: theme.text }]}>Via Text</Text>
              </TouchableOpacity>

              <TouchableOpacity 
                style={styles.shareOption}
                onPress={handleShareEmail}
                data-testid="share-via-email"
              >
                <View style={[styles.shareOptionIcon, { backgroundColor: '#FF950020' }]}>
                  <Ionicons name="mail-outline" size={24} color="#FF9500" />
                </View>
                <Text style={[styles.shareOptionText, { color: theme.text }]}>Via Email</Text>
              </TouchableOpacity>

              <TouchableOpacity 
                style={styles.shareOption}
                onPress={handleSaveContact}
                disabled={saving}
                data-testid="download-vcard"
              >
                <View style={[styles.shareOptionIcon, { backgroundColor: `${theme.accent}20` }]}>
                  {saving ? (
                    <ActivityIndicator size="small" color={theme.accent} />
                  ) : (
                    <Ionicons name="download-outline" size={24} color={theme.accent} />
                  )}
                </View>
                <Text style={[styles.shareOptionText, { color: theme.text }]}>Save vCard</Text>
              </TouchableOpacity>

              <TouchableOpacity 
                style={styles.shareOption}
                onPress={() => { flipCard(); setShowShareModal(false); }}
                data-testid="show-qr-code"
              >
                <View style={[styles.shareOptionIcon, { backgroundColor: '#AF52DE20' }]}>
                  <Ionicons name="qr-code-outline" size={24} color="#AF52DE" />
                </View>
                <Text style={[styles.shareOptionText, { color: theme.text }]}>Show QR</Text>
              </TouchableOpacity>
            </View>

            <TouchableOpacity 
              style={dynamicStyles.shareModalCancel}
              onPress={() => setShowShareModal(false)}
            >
              <Text style={styles.shareModalCancelText}>Cancel</Text>
            </TouchableOpacity>
          </View>
          </TouchableOpacity>
        </TouchableOpacity>
      </Modal>

      {/* Contact Match Modal */}
      {matchModalVisible && matchInfo && (
        <View style={styles.matchOverlay}>
          <View style={[styles.matchModal, { backgroundColor: theme.card }]} data-testid="contact-match-modal">
            <View style={{ alignItems: 'center', marginBottom: 16 }}>
              <View style={{ width: 64, height: 64, borderRadius: 32, backgroundColor: '#FF950015', alignItems: 'center', justifyContent: 'center' }}>
                <Ionicons name="person-circle" size={44} color="#FF9500" />
              </View>
            </View>
            <Text style={[styles.matchTitle, { color: theme.text }]}>Contact Already Exists</Text>
            <Text style={[styles.matchSubtitle, { color: theme.textMuted }]}>A contact with this number already exists:</Text>
            <View style={[styles.matchCard, { backgroundColor: theme.surface }]}>
              <Text style={{ fontSize: 12, fontWeight: '700', color: theme.textMuted, letterSpacing: 1, marginBottom: 6 }}>EXISTING CONTACT</Text>
              <Text style={{ fontSize: 18, fontWeight: '600', color: theme.text }}>{matchInfo.existing_name}</Text>
              {matchInfo.phone ? <Text style={{ fontSize: 15, color: theme.textMuted, marginTop: 2 }}>{matchInfo.phone}</Text> : null}
            </View>
            <View style={{ flexDirection: 'row', alignItems: 'center', marginVertical: 12 }}>
              <View style={{ flex: 1, height: 1, backgroundColor: theme.cardBorder }} />
              <Text style={{ fontSize: 14, color: theme.textMuted, marginHorizontal: 12 }}>You entered</Text>
              <View style={{ flex: 1, height: 1, backgroundColor: theme.cardBorder }} />
            </View>
            <View style={[styles.matchCard, { backgroundColor: theme.surface, marginBottom: 20 }]}>
              <Text style={{ fontSize: 18, fontWeight: '600', color: '#FF9500' }}>{matchInfo.provided_name}</Text>
            </View>
            <TouchableOpacity style={[styles.matchActionBtn, { backgroundColor: theme.surface }]} onPress={() => resolveMatchAction('use_existing')} data-testid="match-use-existing">
              <Ionicons name="checkmark-circle" size={20} color="#34C759" />
              <Text style={[styles.matchActionText, { color: theme.text }]}>Use Existing Contact</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.matchActionBtn, { backgroundColor: theme.surface }]} onPress={() => resolveMatchAction('update_name')} data-testid="match-update-name">
              <Ionicons name="create" size={20} color="#007AFF" />
              <Text style={[styles.matchActionText, { color: theme.text }]}>Update to "{matchInfo.provided_name}"</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.matchActionBtn, { backgroundColor: theme.surface }]} onPress={() => resolveMatchAction('create_new')} data-testid="match-create-new">
              <Ionicons name="person-add" size={20} color="#FF9500" />
              <Text style={[styles.matchActionText, { color: theme.text }]}>Create New Contact</Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={() => { setMatchModalVisible(false); setMatchInfo(null); }} style={{ marginTop: 12, padding: 12, alignItems: 'center' }}>
              <Text style={{ fontSize: 17, color: theme.textMuted }}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}
    </View>
  );
}

// Dynamic styles that depend on theme
const getDynamicStyles = (theme: ThemePalette) => StyleSheet.create({
  saveButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: theme.accent,
    paddingVertical: 16,
    borderRadius: 16,
    marginBottom: 24,
    gap: 10,
  },
  saveButtonSaved: {
    backgroundColor: '#34C759',
  },
  saveButtonText: {
    color: theme.bg === '#0D0D0D' ? '#1A1A1A' : '#FFF',
    fontSize: 18,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  infoCard: {
    backgroundColor: theme.card,
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: theme.surface,
  },
  testimonialCard: {
    backgroundColor: theme.card,
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: theme.surface,
  },
  reviewCTABanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: theme.card,
    borderRadius: 14,
    padding: 16,
    borderWidth: 1,
    borderColor: `${theme.accent}40`,
  },
  referralBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: theme.card,
    borderRadius: 14,
    padding: 16,
    borderWidth: 1,
    borderColor: '#34C75940',
  },
  feedbackCard: {
    backgroundColor: theme.card,
    borderRadius: 12,
    padding: 20,
    marginTop: 10,
    borderWidth: 1,
    borderColor: theme.surface,
  },
  feedbackInput: {
    backgroundColor: theme.inputBg,
    borderRadius: 10,
    padding: 14,
    fontSize: 17,
    color: theme.text,
    borderWidth: 1,
    borderColor: theme.inputBorder,
    marginBottom: 10,
  },
  feedbackSubmitBtn: {
    backgroundColor: theme.accent,
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 4,
  },
  feedbackSubmitText: {
    fontSize: 18,
    fontWeight: '600',
    color: theme.bg === '#0D0D0D' ? '#000' : '#FFF',
  },
  shareModal: {
    backgroundColor: theme.card,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 24,
    paddingBottom: 40,
  },
  shareModalHandle: {
    width: 40,
    height: 4,
    backgroundColor: theme.cardBorder,
    borderRadius: 2,
    alignSelf: 'center',
    marginBottom: 20,
  },
  shareModalCancel: {
    marginTop: 24,
    paddingVertical: 16,
    backgroundColor: theme.surface,
    borderRadius: 12,
  },
  recipientInput: {
    backgroundColor: theme.inputBg,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 12,
    fontSize: 16,
    color: theme.text,
    borderWidth: 1.5,
    borderColor: theme.cardBorder,
    minWidth: 0,
  },
});

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
  },
  backButton: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 19,
    fontWeight: '600',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    color: '#FFF',
    marginTop: 16,
    fontSize: 18,
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  errorTitle: {
    color: '#FFF',
    fontSize: 21,
    fontWeight: '600',
    marginTop: 16,
  },
  errorText: {
    color: '#8E8E93',
    fontSize: 18,
    marginTop: 8,
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    paddingBottom: 40,
    paddingHorizontal: 20,
  },
  // Flip Card Styles
  cardContainer: {
    width: CARD_WIDTH,
    height: CARD_HEIGHT,
    alignSelf: 'center',
    marginTop: 20,
    marginBottom: 24,
  },
  card: {
    width: CARD_WIDTH,
    height: CARD_HEIGHT,
    borderRadius: 24,
    padding: 24,
    alignItems: 'center',
    justifyContent: 'center',
    backfaceVisibility: 'hidden',
    position: 'absolute',
    borderWidth: 1,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 12,
    elevation: 8,
  },
  cardFront: {
    zIndex: 1,
  },
  cardBack: {
    zIndex: 0,
  },
  // Flip corner indicator
  flipCorner: {
    position: 'absolute',
    top: 0,
    right: 0,
    width: 50,
    height: 50,
    zIndex: 10,
  },
  flipCornerInner: {
    position: 'absolute',
    top: 8,
    right: 8,
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  cornerFold: {
    position: 'absolute',
    top: 0,
    right: 0,
    width: 0,
    height: 0,
    borderStyle: 'solid',
    borderRightWidth: 24,
    borderTopWidth: 24,
    borderTopColor: 'transparent',
    borderRadius: 4,
    transform: [{ rotate: '90deg' }],
  },
  flipHint: {
    position: 'absolute',
    bottom: 12,
    color: '#666',
    fontSize: 13,
    fontStyle: 'italic',
  },
  // Card content
  coverBanner: {
    width: '100%',
    height: 90,
    marginTop: -16,
    marginHorizontal: -16,
    marginBottom: 12,
    alignSelf: 'center',
    position: 'relative',
    overflow: 'hidden',
  },
  coverBannerGrad: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    height: 40,
    backgroundColor: 'rgba(0,0,0,0.3)',
  },
  storeLogo: {
    width: 80,
    height: 40,
    marginBottom: 12,
    backgroundColor: 'transparent',
  },
  photoContainer: {
    marginBottom: 12,
  },
  photo: {
    width: 160,
    height: 160,
    borderRadius: 20,
    borderWidth: 3,
  },
  photoPlaceholder: {
    width: 160,
    height: 160,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 3,
  },
  userName: {
    fontSize: 24,
    fontWeight: '700',
    textAlign: 'center',
    letterSpacing: 0.5,
  },
  userTitle: {
    fontSize: 16,
    marginTop: 4,
    textTransform: 'uppercase',
    letterSpacing: 1.5,
    fontWeight: '500',
  },
  storeName: {
    fontSize: 15,
    marginTop: 6,
  },
  divider: {
    width: 60,
    height: 2,
    marginVertical: 10,
    borderRadius: 1,
  },
  contactRow: {
    alignItems: 'center',
    marginBottom: 12,
  },
  contactItem: {
    flexDirection: 'row',
    alignItems: 'center',
    marginVertical: 4,
  },
  contactText: {
    color: '#CCC',
    fontSize: 15,
    marginLeft: 8,
  },
  socialRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginTop: 8,
  },
  socialIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
    marginHorizontal: 6,
  },
  // QR Code Back
  qrTitle: {
    fontSize: 19,
    fontWeight: '600',
    marginBottom: 20,
    textTransform: 'uppercase',
    letterSpacing: 2,
  },
  qrContainer: {
    padding: 16,
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    marginBottom: 20,
  },
  qrActions: {
    flexDirection: 'row',
    marginTop: 20,
    gap: 16,
  },
  qrActionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 24,
    gap: 8,
  },
  qrActionText: {
    fontSize: 16,
    fontWeight: '600',
  },
  // Save Button (static parts only)
  // Quick Actions
  quickActionsRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    marginBottom: 32,
  },
  quickActionButton: {
    alignItems: 'center',
  },
  quickActionIcon: {
    width: 56,
    height: 56,
    borderRadius: 28,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    marginBottom: 8,
  },
  quickActionLabel: {
    fontSize: 14,
    fontWeight: '500',
  },
  // Sections
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 12,
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  infoCard: {
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
  },
  infoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
  },
  infoText: {
    fontSize: 16,
    marginLeft: 12,
    flex: 1,
  },
  linkText: {
    textDecorationLine: 'underline',
  },
  bioText: {
    fontSize: 16,
    lineHeight: 22,
  },
  // Testimonials
  testimonialCard: {
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
  },
  testimonialHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  testimonialName: {
    fontSize: 16,
    fontWeight: '600',
  },
  starsRow: {
    flexDirection: 'row',
  },
  testimonialText: {
    fontSize: 15,
    fontStyle: 'italic',
    lineHeight: 20,
  },
  // Footer
  footer: {
    alignItems: 'center',
    paddingVertical: 24,
  },
  footerText: {
    color: '#333',
    fontSize: 13,
    textTransform: 'uppercase',
    letterSpacing: 2,
  },
  // Feedback Section
  reviewCTABanner: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 14,
    padding: 16,
    borderWidth: 1,
  },
  reviewCTABannerTitle: { fontSize: 18, fontWeight: '700' },
  reviewCTABannerSub: { fontSize: 15, marginTop: 2, fontWeight: '500' },
  referralBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 14,
    padding: 16,
    borderWidth: 1,
  },
  referralBannerTitle: { fontSize: 18, fontWeight: '700' },
  referralBannerSub: { color: '#34C759', fontSize: 15, marginTop: 2, fontWeight: '500' },
  feedbackCard: {
    borderRadius: 12,
    padding: 20,
    marginTop: 10,
    borderWidth: 1,
  },
  feedbackLabel: {
    fontSize: 17,
    textAlign: 'center',
    marginBottom: 14,
  },
  starRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 8,
    marginBottom: 16,
  },
  feedbackInput: {
    borderRadius: 10,
    padding: 14,
    fontSize: 17,
    borderWidth: 1,
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
  },
  feedbackSuccess: {
    alignItems: 'center',
    paddingVertical: 16,
  },
  feedbackSuccessTitle: {
    fontSize: 19,
    fontWeight: '700',
    color: '#FFF',
    marginTop: 10,
  },
  feedbackSuccessText: {
    fontSize: 16,
    color: '#8E8E93',
    marginTop: 4,
  },
  // Share Modal Styles
  modalOverlay: {
    flex: 1,
    justifyContent: 'flex-end',
  },
  shareModal: {
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 24,
    paddingBottom: 40,
  },
  shareModalHandle: {
    width: 40,
    height: 4,
    borderRadius: 2,
    alignSelf: 'center',
    marginBottom: 20,
  },
  shareModalTitle: {
    fontSize: 21,
    fontWeight: '700',
    textAlign: 'center',
    marginBottom: 4,
  },
  shareModalSubtitle: {
    fontSize: 16,
    textAlign: 'center',
    marginBottom: 24,
  },
  shareOptionsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    gap: 16,
  },
  shareOption: {
    width: '30%',
    alignItems: 'center',
  },
  shareOptionIcon: {
    width: 60,
    height: 60,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 8,
  },
  shareOptionText: {
    fontSize: 14,
    fontWeight: '500',
    textAlign: 'center',
  },
  shareModalCancel: {
    marginTop: 24,
    paddingVertical: 16,
    borderRadius: 12,
  },
  shareModalCancelText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FF3B30',
    textAlign: 'center',
  },
  recipientSection: {
    marginBottom: 16,
    gap: 8,
  },
  recipientLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: '#6E6E73',
    letterSpacing: 1,
    marginBottom: 0,
    textTransform: 'uppercase',
  },
  recipientInput: {
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 12,
    fontSize: 16,
    borderWidth: 1.5,
    minWidth: 0,
  },
  recipientRow: {
    flexDirection: 'row' as any,
    gap: 8,
    width: '100%' as any,
  },
  matchOverlay: {
    position: 'absolute' as any,
    top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'center' as any,
    alignItems: 'center' as any,
    zIndex: 9999,
  },
  matchModal: {
    borderRadius: 16,
    padding: 24,
    width: '90%',
    maxWidth: 380,
  },
  matchTitle: { fontSize: 19, fontWeight: '700' as any, textAlign: 'center' as any, marginBottom: 8 },
  matchSubtitle: { fontSize: 16, textAlign: 'center' as any, marginBottom: 16 },
  matchCard: { borderRadius: 10, padding: 14, alignItems: 'center' as any },
  matchActionBtn: { flexDirection: 'row' as any, alignItems: 'center' as any, padding: 14, borderRadius: 10, gap: 10, marginBottom: 8 },
  matchActionText: { fontSize: 17, fontWeight: '500' as any, flex: 1 },
});
