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
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Paths, File as ExpoFile } from 'expo-file-system';
import * as Sharing from 'expo-sharing';
import * as Clipboard from 'expo-clipboard';
import QRCode from 'react-native-qrcode-svg';
import api from '../../services/api';

// Web-safe URL opener — Linking.openURL uses window.open('_blank')
// which popup blockers intercept for sms: and mailto: protocols.
// Using an anchor click or location.href is more reliable on web.
const openProtocolUrl = (url: string) => {
  if (Platform.OS === 'web') {
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

// Social platform icons with brand colors
const SOCIAL_PLATFORMS = [
  { key: 'website', icon: 'globe-outline', color: '#34C759', baseUrl: '' },
  { key: 'facebook', icon: 'logo-facebook', color: '#1877F2', baseUrl: 'https://facebook.com/' },
  { key: 'instagram', icon: 'logo-instagram', color: '#E4405F', baseUrl: 'https://instagram.com/' },
  { key: 'twitter', icon: 'logo-twitter', color: '#1DA1F2', baseUrl: 'https://x.com/' },
  { key: 'linkedin', icon: 'logo-linkedin', color: '#0A66C2', baseUrl: 'https://linkedin.com/in/' },
  { key: 'youtube', icon: 'logo-youtube', color: '#FF0000', baseUrl: 'https://youtube.com/@' },
  { key: 'tiktok', icon: 'logo-tiktok', color: '#000000', baseUrl: 'https://tiktok.com/@' },
];

export default function DigitalCardPage() {
  const router = useRouter();
  const { userId, campaign, contact } = useLocalSearchParams();
  const [loading, setLoading] = useState(true);
  const [cardData, setCardData] = useState<any>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [isFlipped, setIsFlipped] = useState(false);
  const [showShareModal, setShowShareModal] = useState(false);
  
  // Direct shareable link - always use production URL like congrats cards
  const cardUrl = `https://app.imosapp.com/card/${userId}`;
  
  // Animation values
  const flipAnimation = useRef(new Animated.Value(0)).current;
  const qrRef = useRef<any>(null);

  useEffect(() => {
    loadCardData();
  }, [userId]);

  const loadCardData = async () => {
    try {
      const response = await api.get(`/card/data/${userId}`);
      setCardData(response.data);
    } catch (error) {
      console.error('Error loading card:', error);
    } finally {
      setLoading(false);
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
    try {
      // Get vCard data
      const vcardResponse = await api.get(`/card/vcard/${userId}`);
      const { vcard, filename } = vcardResponse.data;

      // Track the save + enroll in campaign if specified
      await api.post(`/card/save/${userId}`, {
        contact_id: contact,
        campaign_id: campaign,
      });

      if (Platform.OS === 'web') {
        // Web: Download as file
        const blob = new Blob([vcard], { type: 'text/vcard' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      } else {
        // Native: Save and share using new Expo File System API
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
    try {
      const cardUrl = `https://app.imosapp.com/card/${userId}`;
      if (Platform.OS === 'web') {
        if (navigator.share) {
          await navigator.share({
            title: cardData?.user?.name ? `${cardData.user.name}'s Business Card` : 'My Business Card',
            text: 'Check out my digital business card:',
            url: cardUrl,
          });
        } else {
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
    try {
      const cardUrl = `https://app.imosapp.com/card/${userId}`;
      await Clipboard.setStringAsync(cardUrl);
      if (Platform.OS === 'web') {
        alert('Link copied to clipboard!');
      }
      setShowShareModal(false);
    } catch (error) {
      console.error('Error copying link:', error);
    }
  };

  // Share via SMS
  const handleShareSMS = () => {
    const cardUrl = `https://app.imosapp.com/card/${userId}`;
    const message = `Check out my digital business card: ${cardUrl}`;
    Linking.openURL(`sms:?body=${encodeURIComponent(message)}`);
    setShowShareModal(false);
  };

  // Share via Email
  const handleShareEmail = () => {
    const cardUrl = `https://app.imosapp.com/card/${userId}`;
    const subject = `${cardData?.user?.name || 'My'} Digital Business Card`;
    const body = `Hi!\n\nHere's my digital business card:\n${cardUrl}\n\nLooking forward to connecting!`;
    Linking.openURL(`mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`);
    setShowShareModal(false);
  };

  // Share QR Code - uses short URL for cleaner sharing
  const handleShareQR = async () => {
    try {
      const cardUrl = `https://app.imosapp.com/card/${userId}`;
      if (Platform.OS === 'web') {
        if (navigator.share) {
          await navigator.share({
            title: cardData?.user?.name ? `${cardData.user.name}'s Business Card` : 'My Business Card',
            text: 'Check out my digital business card:',
            url: cardUrl,
          });
        } else {
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
    if (Platform.OS === 'web' && qrRef.current) {
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

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#C9A962" />
        <Text style={styles.loadingText}>Loading card...</Text>
      </View>
    );
  }

  if (!cardData) {
    return (
      <View style={styles.errorContainer}>
        <Ionicons name="alert-circle" size={64} color="#FF3B30" />
        <Text style={styles.errorTitle}>Card Not Found</Text>
        <Text style={styles.errorText}>This digital card doesn't exist.</Text>
      </View>
    );
  }

  const { user, store, testimonials } = cardData;
  // QR code and share links use the direct production URL

  // Filter active social links
  const activeSocialLinks = SOCIAL_PLATFORMS.filter(
    p => user.social_links?.[p.key]
  );

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top', 'bottom']} style={{ flex: 1 }}>
        {/* Header with Back Button */}
        <View style={styles.header}>
          <TouchableOpacity 
            onPress={() => router.back()} 
            style={styles.backButton}
            accessibilityRole="button"
            data-testid="back-button"
          >
            <Ionicons name="chevron-back" size={28} color="#C9A962" />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>My Digital Card</Text>
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
            <Animated.View style={[styles.card, styles.cardFront, frontAnimatedStyle]}>
              {/* Flip indicator - top right corner */}
              <TouchableOpacity 
                style={styles.flipCorner} 
                onPress={flipCard}
                data-testid="flip-card-btn"
              >
                <View style={styles.flipCornerInner}>
                  <Ionicons name="qr-code" size={16} color="#C9A962" />
                </View>
                <View style={styles.cornerFold} />
              </TouchableOpacity>

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
                    style={styles.photo}
                  />
                ) : (
                  <View style={styles.photoPlaceholder}>
                    <Ionicons name="person" size={48} color="#666" />
                  </View>
                )}
              </View>
              
              {/* Name & Title */}
              <Text style={styles.userName}>{user.name}</Text>
              <Text style={styles.userTitle}>{user.title || 'Sales Professional'}</Text>
              
              {store?.name && (
                <Text style={styles.storeName}>{store.name}</Text>
              )}

              {/* Divider */}
              <View style={styles.divider} />

              {/* Contact Row */}
              <View style={styles.contactRow}>
                {user.phone && (
                  <TouchableOpacity
                    style={styles.contactItem}
                    onPress={() => Linking.openURL(`tel:${user.phone}`)}
                    data-testid="call-btn"
                  >
                    <Ionicons name="call" size={18} color="#C9A962" />
                    <Text style={styles.contactText}>{user.phone}</Text>
                  </TouchableOpacity>
                )}
                {user.email && (
                  <TouchableOpacity
                    style={styles.contactItem}
                    onPress={() => Linking.openURL(`mailto:${user.email}`)}
                    data-testid="email-btn"
                  >
                    <Ionicons name="mail" size={18} color="#C9A962" />
                    <Text style={styles.contactText} numberOfLines={1}>{user.email}</Text>
                  </TouchableOpacity>
                )}
              </View>

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
                        style={styles.socialIcon}
                        onPress={() => Linking.openURL(url)}
                        data-testid={`social-${platform.key}`}
                      >
                        <Ionicons name={platform.icon as any} size={22} color={platform.color} />
                      </TouchableOpacity>
                    );
                  })}
                </View>
              )}

              {/* Tap to flip hint */}
              <Text style={styles.flipHint}>Tap corner for QR code</Text>
            </Animated.View>

            {/* Back of Card - QR Code */}
            <Animated.View style={[styles.card, styles.cardBack, backAnimatedStyle]}>
              {/* Flip back indicator - top right corner */}
              <TouchableOpacity 
                style={styles.flipCorner} 
                onPress={flipCard}
                data-testid="flip-back-btn"
              >
                <View style={styles.flipCornerInner}>
                  <Ionicons name="person" size={16} color="#C9A962" />
                </View>
                <View style={styles.cornerFold} />
              </TouchableOpacity>

              <Text style={styles.qrTitle}>Scan to Connect</Text>
              
              <View style={styles.qrContainer}>
                <QRCode
                  value={cardUrl}
                  size={200}
                  color="#1A1A1A"
                  backgroundColor="#FFFFFF"
                  getRef={(ref) => (qrRef.current = ref)}
                />
              </View>

              <Text style={styles.userName} numberOfLines={1}>{user.name}</Text>
              <Text style={styles.userTitle}>{user.title || 'Sales Professional'}</Text>

              {/* QR Action Buttons */}
              <View style={styles.qrActions}>
                <TouchableOpacity 
                  style={styles.qrActionBtn}
                  onPress={handleShareQR}
                  data-testid="share-qr-btn"
                >
                  <Ionicons name="share-outline" size={20} color="#FFF" />
                  <Text style={styles.qrActionText}>Share</Text>
                </TouchableOpacity>
                <TouchableOpacity 
                  style={styles.qrActionBtn}
                  onPress={handleDownloadQR}
                  data-testid="download-qr-btn"
                >
                  <Ionicons name="download-outline" size={20} color="#FFF" />
                  <Text style={styles.qrActionText}>Download</Text>
                </TouchableOpacity>
              </View>

              {/* Tap to flip hint */}
              <Text style={styles.flipHint}>Tap corner to flip back</Text>
            </Animated.View>
          </View>

          {/* Share Contact Button - Below Card */}
          <TouchableOpacity
            style={[styles.saveButton, saved && styles.saveButtonSaved]}
            onPress={() => setShowShareModal(true)}
            disabled={saving}
            data-testid="share-contact-btn"
          >
            {saved ? (
              <>
                <Ionicons name="checkmark-circle" size={22} color="#1A1A1A" />
                <Text style={styles.saveButtonText}>Contact Shared!</Text>
              </>
            ) : (
              <>
                <Ionicons name="share-social" size={22} color="#1A1A1A" />
                <Text style={styles.saveButtonText}>Share My Contact</Text>
              </>
            )}
          </TouchableOpacity>

          {/* Quick Actions */}
          <View style={styles.quickActionsRow}>
            {user.phone && (
              <TouchableOpacity
                style={styles.quickActionButton}
                onPress={() => Linking.openURL(`tel:${user.phone}`)}
                data-testid="quick-call-btn"
              >
                <View style={styles.quickActionIcon}>
                  <Ionicons name="call" size={22} color="#34C759" />
                </View>
                <Text style={styles.quickActionLabel}>Call</Text>
              </TouchableOpacity>
            )}
            
            {user.phone && (
              <TouchableOpacity
                style={styles.quickActionButton}
                onPress={() => Linking.openURL(`sms:${user.phone}`)}
                data-testid="quick-text-btn"
              >
                <View style={styles.quickActionIcon}>
                  <Ionicons name="chatbubble" size={22} color="#007AFF" />
                </View>
                <Text style={styles.quickActionLabel}>Text</Text>
              </TouchableOpacity>
            )}
            
            {user.email && (
              <TouchableOpacity
                style={styles.quickActionButton}
                onPress={() => Linking.openURL(`mailto:${user.email}`)}
                data-testid="quick-email-btn"
              >
                <View style={styles.quickActionIcon}>
                  <Ionicons name="mail" size={22} color="#FF9500" />
                </View>
                <Text style={styles.quickActionLabel}>Email</Text>
              </TouchableOpacity>
            )}

            <TouchableOpacity
              style={styles.quickActionButton}
              onPress={flipCard}
              data-testid="quick-qr-btn"
            >
              <View style={styles.quickActionIcon}>
                <Ionicons name="qr-code" size={22} color="#C9A962" />
              </View>
              <Text style={styles.quickActionLabel}>QR Code</Text>
            </TouchableOpacity>
          </View>

          {/* Bio Section */}
          {user.bio && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>About Me</Text>
              <View style={styles.infoCard}>
                <Text style={styles.bioText}>{user.bio}</Text>
              </View>
            </View>
          )}

          {/* Contact Info Section */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Contact Information</Text>
            <View style={styles.infoCard}>
              {user.phone && (
                <View style={styles.infoRow}>
                  <Ionicons name="call-outline" size={20} color="#C9A962" />
                  <Text style={styles.infoText}>{user.phone}</Text>
                </View>
              )}
              {user.email && (
                <View style={styles.infoRow}>
                  <Ionicons name="mail-outline" size={20} color="#C9A962" />
                  <Text style={styles.infoText}>{user.email}</Text>
                </View>
              )}
              {store?.address && (
                <View style={styles.infoRow}>
                  <Ionicons name="location-outline" size={20} color="#C9A962" />
                  <Text style={styles.infoText}>
                    {store.address}{store.city ? `, ${store.city}` : ''}{store.state ? `, ${store.state}` : ''}
                  </Text>
                </View>
              )}
              {store?.website && (
                <TouchableOpacity 
                  style={[styles.infoRow, { borderBottomWidth: 0 }]}
                  onPress={() => Linking.openURL(store.website)}
                >
                  <Ionicons name="globe-outline" size={20} color="#C9A962" />
                  <Text style={[styles.infoText, styles.linkText]}>{store.website}</Text>
                </TouchableOpacity>
              )}
            </View>
          </View>

          {/* Testimonials */}
          {testimonials && testimonials.length > 0 && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>What Customers Say</Text>
              {testimonials.map((t: any) => (
                <View key={t.id} style={styles.testimonialCard}>
                  <View style={styles.testimonialHeader}>
                    <Text style={styles.testimonialName}>{t.customer_name}</Text>
                    {renderStars(t.rating)}
                  </View>
                  {t.text && (
                    <Text style={styles.testimonialText}>"{t.text}"</Text>
                  )}
                </View>
              ))}
            </View>
          )}

          {/* Footer */}
          <View style={styles.footer}>
            <Text style={styles.footerText}>Powered by iMOs</Text>
          </View>
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
          style={styles.modalOverlay}
          activeOpacity={1}
          onPress={() => setShowShareModal(false)}
        >
          <View style={styles.shareModal}>
            <View style={styles.shareModalHandle} />
            <Text style={styles.shareModalTitle}>Share My Contact</Text>
            <Text style={styles.shareModalSubtitle}>Choose how to share your digital card</Text>
            
            <View style={styles.shareOptionsGrid}>
              <TouchableOpacity 
                style={styles.shareOption}
                onPress={handleShareLink}
                data-testid="share-via-link"
              >
                <View style={[styles.shareOptionIcon, { backgroundColor: '#007AFF20' }]}>
                  <Ionicons name="share-outline" size={24} color="#007AFF" />
                </View>
                <Text style={styles.shareOptionText}>Share Link</Text>
              </TouchableOpacity>

              <TouchableOpacity 
                style={styles.shareOption}
                onPress={handleCopyLink}
                data-testid="copy-link"
              >
                <View style={[styles.shareOptionIcon, { backgroundColor: '#5856D620' }]}>
                  <Ionicons name="copy-outline" size={24} color="#5856D6" />
                </View>
                <Text style={styles.shareOptionText}>Copy Link</Text>
              </TouchableOpacity>

              <TouchableOpacity 
                style={styles.shareOption}
                onPress={handleShareSMS}
                data-testid="share-via-sms"
              >
                <View style={[styles.shareOptionIcon, { backgroundColor: '#34C75920' }]}>
                  <Ionicons name="chatbubble-outline" size={24} color="#34C759" />
                </View>
                <Text style={styles.shareOptionText}>Via Text</Text>
              </TouchableOpacity>

              <TouchableOpacity 
                style={styles.shareOption}
                onPress={handleShareEmail}
                data-testid="share-via-email"
              >
                <View style={[styles.shareOptionIcon, { backgroundColor: '#FF950020' }]}>
                  <Ionicons name="mail-outline" size={24} color="#FF9500" />
                </View>
                <Text style={styles.shareOptionText}>Via Email</Text>
              </TouchableOpacity>

              <TouchableOpacity 
                style={styles.shareOption}
                onPress={handleSaveContact}
                disabled={saving}
                data-testid="download-vcard"
              >
                <View style={[styles.shareOptionIcon, { backgroundColor: '#C9A96220' }]}>
                  {saving ? (
                    <ActivityIndicator size="small" color="#C9A962" />
                  ) : (
                    <Ionicons name="download-outline" size={24} color="#C9A962" />
                  )}
                </View>
                <Text style={styles.shareOptionText}>Save vCard</Text>
              </TouchableOpacity>

              <TouchableOpacity 
                style={styles.shareOption}
                onPress={() => { flipCard(); setShowShareModal(false); }}
                data-testid="show-qr-code"
              >
                <View style={[styles.shareOptionIcon, { backgroundColor: '#AF52DE20' }]}>
                  <Ionicons name="qr-code-outline" size={24} color="#AF52DE" />
                </View>
                <Text style={styles.shareOptionText}>Show QR</Text>
              </TouchableOpacity>
            </View>

            <TouchableOpacity 
              style={styles.shareModalCancel}
              onPress={() => setShowShareModal(false)}
            >
              <Text style={styles.shareModalCancelText}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </TouchableOpacity>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0D0D0D',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#1C1C1E',
  },
  backButton: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFF',
  },
  loadingContainer: {
    flex: 1,
    backgroundColor: '#0D0D0D',
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    color: '#FFF',
    marginTop: 16,
    fontSize: 16,
  },
  errorContainer: {
    flex: 1,
    backgroundColor: '#0D0D0D',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  errorTitle: {
    color: '#FFF',
    fontSize: 20,
    fontWeight: '600',
    marginTop: 16,
  },
  errorText: {
    color: '#8E8E93',
    fontSize: 16,
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
    // Luxury dark card styling
    backgroundColor: '#1A1A1A',
    borderWidth: 1,
    borderColor: '#333',
    shadowColor: '#C9A962',
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
    backgroundColor: 'rgba(201, 169, 98, 0.15)',
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
    borderRightColor: '#C9A962',
    borderTopColor: 'transparent',
    borderRadius: 4,
    transform: [{ rotate: '90deg' }],
  },
  flipHint: {
    position: 'absolute',
    bottom: 12,
    color: '#666',
    fontSize: 11,
    fontStyle: 'italic',
  },
  // Card content
  storeLogo: {
    width: 80,
    height: 40,
    marginBottom: 12,
  },
  photoContainer: {
    marginBottom: 16,
  },
  photo: {
    width: 100,
    height: 100,
    borderRadius: 50,
    borderWidth: 3,
    borderColor: '#C9A962',
  },
  photoPlaceholder: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: '#2A2A2A',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 3,
    borderColor: '#C9A962',
  },
  userName: {
    fontSize: 24,
    fontWeight: '700',
    color: '#FFFFFF',
    textAlign: 'center',
    letterSpacing: 0.5,
  },
  userTitle: {
    fontSize: 14,
    color: '#C9A962',
    marginTop: 4,
    textTransform: 'uppercase',
    letterSpacing: 1.5,
    fontWeight: '500',
  },
  storeName: {
    fontSize: 13,
    color: '#888',
    marginTop: 6,
  },
  divider: {
    width: 60,
    height: 2,
    backgroundColor: '#C9A962',
    marginVertical: 16,
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
    fontSize: 13,
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
    backgroundColor: '#2A2A2A',
    alignItems: 'center',
    justifyContent: 'center',
    marginHorizontal: 6,
  },
  // QR Code Back
  qrTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#C9A962',
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
    backgroundColor: '#C9A962',
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 24,
    gap: 8,
  },
  qrActionText: {
    color: '#1A1A1A',
    fontSize: 14,
    fontWeight: '600',
  },
  // Save Button
  saveButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#C9A962',
    paddingVertical: 16,
    borderRadius: 16,
    marginBottom: 24,
    gap: 10,
  },
  saveButtonSaved: {
    backgroundColor: '#34C759',
  },
  saveButtonText: {
    color: '#1A1A1A',
    fontSize: 17,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
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
    backgroundColor: '#1A1A1A',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: '#333',
    marginBottom: 8,
  },
  quickActionLabel: {
    color: '#888',
    fontSize: 12,
    fontWeight: '500',
  },
  // Sections
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#C9A962',
    marginBottom: 12,
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  infoCard: {
    backgroundColor: '#1A1A1A',
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: '#2A2A2A',
  },
  infoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#2A2A2A',
  },
  infoText: {
    color: '#FFF',
    fontSize: 14,
    marginLeft: 12,
    flex: 1,
  },
  linkText: {
    color: '#C9A962',
    textDecorationLine: 'underline',
  },
  bioText: {
    color: '#CCC',
    fontSize: 14,
    lineHeight: 22,
  },
  // Testimonials
  testimonialCard: {
    backgroundColor: '#1A1A1A',
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#2A2A2A',
  },
  testimonialHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  testimonialName: {
    color: '#FFF',
    fontSize: 14,
    fontWeight: '600',
  },
  starsRow: {
    flexDirection: 'row',
  },
  testimonialText: {
    color: '#888',
    fontSize: 13,
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
    fontSize: 11,
    textTransform: 'uppercase',
    letterSpacing: 2,
  },
  // Share Modal Styles
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.7)',
    justifyContent: 'flex-end',
  },
  shareModal: {
    backgroundColor: '#1C1C1E',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 24,
    paddingBottom: 40,
  },
  shareModalHandle: {
    width: 40,
    height: 4,
    backgroundColor: '#3A3A3C',
    borderRadius: 2,
    alignSelf: 'center',
    marginBottom: 20,
  },
  shareModalTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#FFF',
    textAlign: 'center',
    marginBottom: 4,
  },
  shareModalSubtitle: {
    fontSize: 14,
    color: '#8E8E93',
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
    fontSize: 12,
    fontWeight: '500',
    color: '#FFF',
    textAlign: 'center',
  },
  shareModalCancel: {
    marginTop: 24,
    paddingVertical: 16,
    backgroundColor: '#2C2C2E',
    borderRadius: 12,
  },
  shareModalCancelText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FF3B30',
    textAlign: 'center',
  },
});
