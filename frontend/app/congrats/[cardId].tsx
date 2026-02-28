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
} from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import api from '../../services/api';

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
  const { cardId } = useLocalSearchParams();
  const [cardData, setCardData] = useState<CongratsCardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const cardRef = useRef<View>(null);

  useEffect(() => {
    loadCardData();
  }, [cardId]);

  const loadCardData = async () => {
    try {
      const response = await api.get(`/congrats/card/${cardId}`);
      setCardData(response.data);
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

  const handleDownload = async () => {
    const imageUrl = `${api.defaults.baseURL}/congrats/card/${cardId}/image`;
    if (Platform.OS === 'web') {
      const a = document.createElement('a');
      a.href = imageUrl;
      a.download = `congrats-${cardId}.png`;
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
    
    const shareUrl = Platform.OS === 'web' 
      ? window.location.href 
      : `https://app.imosapp.com/congrats/${cardId}`;
    
    const shareText = `Check out my thank you card from ${cardData?.salesman?.name || 'my salesperson'}! ${cardData?.headline}`;
    
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
          alert('To share on Instagram:\n\n1. Take a screenshot of this card\n2. Open Instagram and create a new post or story\n3. Select the screenshot from your gallery');
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
        {/* Store Logo */}
        {cardData.store?.logo && (
          <View style={styles.storeLogoContainer}>
            <Image source={{ uri: cardData.store.logo }} style={styles.storeLogo} />
          </View>
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

        {/* Salesman Info */}
        {cardData.salesman && (
          <View style={styles.salesmanContainer}>
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
          </View>
        )}

        {/* Footer */}
        {cardData.footer_text && (
          <Text style={[styles.footerText, { color: '#8E8E93' }]}>
            {cardData.footer_text}
          </Text>
        )}
      </View>

      {/* Action Buttons */}
      <View style={styles.actionsSection}>
        <TouchableOpacity 
          style={styles.actionsTitleLink}
          onPress={() => {
            if (cardData?.salesman_id) {
              router.push(`/p/${cardData.salesman_id}` as any);
            }
          }}
        >
          <Text style={styles.actionsTitle}>Share Your Experience</Text>
          <Ionicons name="chevron-forward" size={18} color="#C9A962" />
        </TouchableOpacity>
        
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

      {/* View Salesman Profile Link */}
      {cardData.salesman_id && (
        <TouchableOpacity
          style={styles.profileLinkSection}
          onPress={() => {
            router.push(`/p/${cardData.salesman_id}` as any);
          }}
        >
          <View style={styles.profileLinkContent}>
            <Ionicons name="person-circle-outline" size={24} color={style.accent_color} />
            <View style={styles.profileLinkText}>
              <Text style={styles.profileLinkTitle}>View {cardData.salesman?.name?.split(' ')[0]}'s Profile</Text>
              <Text style={styles.profileLinkSubtitle}>Leave a review or refer a friend</Text>
            </View>
          </View>
          <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
        </TouchableOpacity>
      )}

      {/* Contact Salesman */}
      {cardData.salesman && (cardData.salesman.phone || cardData.salesman.email) && (
        <View style={styles.contactSection}>
          <Text style={styles.contactTitle}>Stay Connected</Text>
          <View style={styles.contactButtons}>
            {cardData.salesman.phone && (
              <TouchableOpacity
                style={styles.contactButton}
                onPress={() => Linking.openURL(`tel:${cardData.salesman?.phone}`)}
              >
                <Ionicons name="call-outline" size={20} color={style.accent_color} />
                <Text style={[styles.contactButtonText, { color: style.accent_color }]}>Call</Text>
              </TouchableOpacity>
            )}
            {cardData.salesman.phone && (
              <TouchableOpacity
                style={styles.contactButton}
                onPress={() => Linking.openURL(`sms:${cardData.salesman?.phone}`)}
              >
                <Ionicons name="chatbubble-outline" size={20} color={style.accent_color} />
                <Text style={[styles.contactButtonText, { color: style.accent_color }]}>Text</Text>
              </TouchableOpacity>
            )}
            {cardData.salesman.email && (
              <TouchableOpacity
                style={styles.contactButton}
                onPress={() => Linking.openURL(`mailto:${cardData.salesman?.email}`)}
              >
                <Ionicons name="mail-outline" size={20} color={style.accent_color} />
                <Text style={[styles.contactButtonText, { color: style.accent_color }]}>Email</Text>
              </TouchableOpacity>
            )}
          </View>
        </View>
      )}

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
  },
  headline: {
    fontSize: 36,
    fontWeight: '700',
    textAlign: 'center',
    marginBottom: 24,
  },
  photoContainer: {
    width: 200,
    height: 200,
    borderRadius: 100,
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
    marginTop: 24,
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
  contactSection: {
    width: '100%',
    maxWidth: 400,
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    padding: 24,
    marginTop: 16,
    alignItems: 'center',
  },
  contactTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 16,
  },
  contactButtons: {
    flexDirection: 'row',
    gap: 24,
  },
  contactButton: {
    alignItems: 'center',
    gap: 6,
  },
  contactButtonText: {
    fontSize: 13,
    fontWeight: '500',
  },
  actionsTitleLink: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 20,
  },
  profileLinkSection: {
    width: '100%',
    maxWidth: 400,
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    padding: 16,
    marginTop: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  profileLinkContent: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    flex: 1,
  },
  profileLinkText: {
    flex: 1,
  },
  profileLinkTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  profileLinkSubtitle: {
    fontSize: 13,
    color: '#8E8E93',
    marginTop: 2,
  },
});
