import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Image,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  Linking,
  Platform,
  Modal,
  Alert,
} from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { PoweredByFooter } from '../../components/PoweredByFooter';
import { LinearGradient } from 'expo-linear-gradient';
import * as ImagePicker from 'expo-image-picker';

interface LandingPageData {
  user: {
    id: string;
    name: string;
    email: string;
    phone: string;
    title: string;
    photo_url: string | null;
    bio: string;
    hobbies: string[];
    family_info: string;
    hometown: string;
    years_experience: string;
    fun_facts: string[];
    personal_motto: string;
    social_links: {
      facebook?: string;
      instagram?: string;
      linkedin?: string;
      twitter?: string;
      youtube?: string;
      tiktok?: string;
    };
  };
  store: {
    id: string;
    name: string;
    logo_url: string | null;
    primary_color: string;
    phone: string | null;
    address: string | null;
    city: string | null;
    state: string | null;
    website: string | null;
    review_links: {
      google?: string;
      yelp?: string;
      facebook?: string;
    };
  } | null;
  testimonials: Array<{
    id: string;
    customer_name: string;
    rating: number;
    text: string;
    photo_url: string | null;
    created_at: string | null;
  }>;
}

export default function PublicLandingPage() {
  const { userId } = useLocalSearchParams();
  const [data, setData] = useState<LandingPageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Review form state
  const [showReviewModal, setShowReviewModal] = useState(false);
  const [reviewName, setReviewName] = useState('');
  const [reviewRating, setReviewRating] = useState(5);
  const [reviewText, setReviewText] = useState('');
  const [reviewPhone, setReviewPhone] = useState('');
  const [reviewPhoto, setReviewPhoto] = useState<string | null>(null);
  const [submittingReview, setSubmittingReview] = useState(false);
  
  // Referral form state
  const [showReferModal, setShowReferModal] = useState(false);
  const [referrerName, setReferrerName] = useState('');
  const [referrerPhone, setReferrerPhone] = useState('');
  const [referredName, setReferredName] = useState('');
  const [referredPhone, setReferredPhone] = useState('');
  const [referredEmail, setReferredEmail] = useState('');
  const [referNotes, setReferNotes] = useState('');
  const [submittingReferral, setSubmittingReferral] = useState(false);

  useEffect(() => {
    loadData();
  }, [userId]);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await api.get(`/p/data/${userId}`);
      setData(response.data);
    } catch (err: any) {
      setError('Unable to load profile');
      console.error('Error loading landing page:', err);
    } finally {
      setLoading(false);
    }
  };

  // Native anchor tag wrapper for web — avoids Safari "trying to open another app" popup
  // by rendering a real <a> link that the browser trusts as a direct user click.
  const NativeLink = ({ href, style, children, ...props }: { href: string; style: any; children: React.ReactNode; [key: string]: any }) => {
    if (Platform.OS === 'web') {
      return (
        <View style={style} {...props}>
          <a
            href={href}
            style={{
              display: 'flex',
              flexDirection: 'column' as const,
              alignItems: 'center',
              justifyContent: 'center',
              textDecoration: 'none',
              width: '100%',
              height: '100%',
            }}
          >
            {children}
          </a>
        </View>
      );
    }
    return (
      <TouchableOpacity style={style} onPress={() => Linking.openURL(href)} {...props}>
        {children}
      </TouchableOpacity>
    );
  };

  const openSocialLink = (url: string) => {
    if (url) {
      Linking.openURL(url.startsWith('http') ? url : `https://${url}`);
    }
  };

  const pickImage = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: true,
      aspect: [4, 3],
      quality: 0.5,
      base64: true,
    });

    if (!result.canceled && result.assets[0]) {
      const base64 = result.assets[0].base64;
      setReviewPhoto(`data:image/jpeg;base64,${base64}`);
    }
  };

  const submitReview = async () => {
    if (!reviewName.trim()) {
      Alert.alert('Error', 'Please enter your name');
      return;
    }

    setSubmittingReview(true);
    try {
      const formData = new FormData();
      formData.append('customer_name', reviewName);
      formData.append('rating', reviewRating.toString());
      if (reviewText) formData.append('text_review', reviewText);
      if (reviewPhone) formData.append('customer_phone', reviewPhone);
      
      if (reviewPhoto) {
        // Convert base64 to blob for form data
        const blob = await fetch(reviewPhoto).then(r => r.blob());
        formData.append('photo', blob, 'purchase.jpg');
      }

      await api.post(`/p/review/${userId}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      Alert.alert('Thank You!', 'Your review has been submitted and will be visible after approval.');
      setShowReviewModal(false);
      resetReviewForm();
    } catch (err) {
      console.error('Error submitting review:', err);
      Alert.alert('Error', 'Failed to submit review. Please try again.');
    } finally {
      setSubmittingReview(false);
    }
  };

  const resetReviewForm = () => {
    setReviewName('');
    setReviewRating(5);
    setReviewText('');
    setReviewPhone('');
    setReviewPhoto(null);
  };

  const submitReferral = async () => {
    if (!referrerName.trim() || !referredName.trim()) {
      Alert.alert('Error', 'Please enter both your name and your friend\'s name');
      return;
    }

    setSubmittingReferral(true);
    try {
      await api.post(`/p/refer/${userId}`, {
        referrer_name: referrerName,
        referrer_phone: referrerPhone,
        referred_name: referredName,
        referred_phone: referredPhone,
        referred_email: referredEmail,
        notes: referNotes,
      });

      Alert.alert('Thank You!', 'Your referral has been submitted. We appreciate your trust!');
      setShowReferModal(false);
      resetReferralForm();
    } catch (err) {
      console.error('Error submitting referral:', err);
      Alert.alert('Error', 'Failed to submit referral. Please try again.');
    } finally {
      setSubmittingReferral(false);
    }
  };

  const resetReferralForm = () => {
    setReferrerName('');
    setReferrerPhone('');
    setReferredName('');
    setReferredPhone('');
    setReferredEmail('');
    setReferNotes('');
  };

  const primaryColor = data?.store?.primary_color || '#C9A962';

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={primaryColor} />
        <Text style={styles.loadingText}>Loading profile...</Text>
      </View>
    );
  }

  if (error || !data) {
    return (
      <View style={styles.errorContainer}>
        <Ionicons name="alert-circle-outline" size={64} color="#FF3B30" />
        <Text style={styles.errorText}>{error || 'Profile not found'}</Text>
        <TouchableOpacity style={styles.retryButton} onPress={loadData}>
          <Text style={styles.retryButtonText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const renderStars = (rating: number) => {
    return (
      <View style={styles.starsContainer}>
        {[1, 2, 3, 4, 5].map((star) => (
          <Ionicons
            key={star}
            name={star <= rating ? 'star' : 'star-outline'}
            size={16}
            color="#FFD700"
          />
        ))}
      </View>
    );
  };

  return (
    <ScrollView style={styles.container} bounces={false}>
      {/* Hero Section */}
      <LinearGradient
        colors={[primaryColor, '#1C1C1E']}
        style={styles.heroSection}
      >
        {/* Store Logo */}
        {data.store?.logo_url && (
          <Image source={{ uri: data.store.logo_url }} style={styles.storeLogo} />
        )}
        
        {/* Profile Photo */}
        <View style={styles.profileImageContainer}>
          {data.user.photo_url ? (
            <Image source={{ uri: data.user.photo_url }} style={styles.profileImage} />
          ) : (
            <View style={[styles.profileImage, styles.profileImagePlaceholder]}>
              <Ionicons name="person" size={60} color="#666" />
            </View>
          )}
        </View>
        
        {/* Name & Title */}
        <Text style={styles.userName}>{data.user.name}</Text>
        <Text style={styles.userTitle}>{data.user.title}</Text>
        {data.store && (
          <Text style={styles.storeName}>{data.store.name}</Text>
        )}
      </LinearGradient>

      {/* Quick Actions */}
      <View style={styles.actionsContainer}>
        {data?.user.phone && (
          <NativeLink
            href={`tel:${data.user.phone}`}
            style={[styles.actionButton, { backgroundColor: primaryColor }]}
            data-testid="landing-call-btn"
          >
            <Ionicons name="call" size={24} color="#FFF" />
            <Text style={styles.actionButtonText}>Call</Text>
          </NativeLink>
        )}
        
        {data?.user.phone && (
          <NativeLink
            href={`sms:${data.user.phone}`}
            style={[styles.actionButton, { backgroundColor: primaryColor }]}
            data-testid="landing-text-btn"
          >
            <Ionicons name="chatbubble" size={24} color="#FFF" />
            <Text style={styles.actionButtonText}>Text</Text>
          </NativeLink>
        )}
        
        {data?.user.email && (
          <NativeLink
            href={`mailto:${data.user.email}`}
            style={[styles.actionButton, { backgroundColor: primaryColor }]}
            data-testid="landing-email-btn"
          >
            <Ionicons name="mail" size={24} color="#FFF" />
            <Text style={styles.actionButtonText}>Email</Text>
          </NativeLink>
        )}
      </View>

      {/* About Section */}
      {data.user.bio && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>About Me</Text>
          <Text style={styles.bioText}>{data.user.bio}</Text>
        </View>
      )}

      {/* Fun Facts */}
      {data.user.fun_facts && data.user.fun_facts.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Fun Facts</Text>
          {data.user.fun_facts.map((fact, index) => (
            <View key={index} style={styles.funFactItem}>
              <Ionicons name="sparkles" size={16} color={primaryColor} />
              <Text style={styles.funFactText}>{fact}</Text>
            </View>
          ))}
        </View>
      )}

      {/* Social Links */}
      {data.user.social_links && Object.keys(data.user.social_links).length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Connect With Me</Text>
          <View style={styles.socialLinksContainer}>
            {data.user.social_links.facebook && (
              <TouchableOpacity
                style={[styles.socialButton, { backgroundColor: '#1877F2' }]}
                onPress={() => openSocialLink(data.user.social_links.facebook!)}
              >
                <Ionicons name="logo-facebook" size={24} color="#FFF" />
              </TouchableOpacity>
            )}
            {data.user.social_links.instagram && (
              <TouchableOpacity
                style={[styles.socialButton, { backgroundColor: '#E1306C' }]}
                onPress={() => openSocialLink(data.user.social_links.instagram!)}
              >
                <Ionicons name="logo-instagram" size={24} color="#FFF" />
              </TouchableOpacity>
            )}
            {data.user.social_links.linkedin && (
              <TouchableOpacity
                style={[styles.socialButton, { backgroundColor: '#0A66C2' }]}
                onPress={() => openSocialLink(data.user.social_links.linkedin!)}
              >
                <Ionicons name="logo-linkedin" size={24} color="#FFF" />
              </TouchableOpacity>
            )}
            {data.user.social_links.twitter && (
              <TouchableOpacity
                style={[styles.socialButton, { backgroundColor: '#1DA1F2' }]}
                onPress={() => openSocialLink(data.user.social_links.twitter!)}
              >
                <Ionicons name="logo-twitter" size={24} color="#FFF" />
              </TouchableOpacity>
            )}
            {data.user.social_links.youtube && (
              <TouchableOpacity
                style={[styles.socialButton, { backgroundColor: '#FF0000' }]}
                onPress={() => openSocialLink(data.user.social_links.youtube!)}
              >
                <Ionicons name="logo-youtube" size={24} color="#FFF" />
              </TouchableOpacity>
            )}
            {data.user.social_links.tiktok && (
              <TouchableOpacity
                style={[styles.socialButton, { backgroundColor: '#000' }]}
                onPress={() => openSocialLink(data.user.social_links.tiktok!)}
              >
                <Ionicons name="logo-tiktok" size={24} color="#FFF" />
              </TouchableOpacity>
            )}
          </View>
        </View>
      )}

      {/* Testimonials */}
      {data.testimonials && data.testimonials.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Customer Reviews</Text>
          {data.testimonials.map((testimonial) => (
            <View key={testimonial.id} style={styles.testimonialCard}>
              <View style={styles.testimonialHeader}>
                <Text style={styles.testimonialName}>{testimonial.customer_name}</Text>
                {renderStars(testimonial.rating)}
              </View>
              {testimonial.text && (
                <Text style={styles.testimonialText}>"{testimonial.text}"</Text>
              )}
              {testimonial.photo_url && (
                <Image
                  source={{ uri: testimonial.photo_url }}
                  style={styles.testimonialPhoto}
                />
              )}
            </View>
          ))}
        </View>
      )}

      {/* CTA Buttons */}
      <View style={styles.ctaSection}>
        <TouchableOpacity
          style={[styles.ctaButton, { backgroundColor: primaryColor }]}
          onPress={() => setShowReviewModal(true)}
          data-testid="leave-review-btn"
        >
          <Ionicons name="star" size={20} color="#FFF" />
          <Text style={styles.ctaButtonText}>Leave a Review</Text>
        </TouchableOpacity>
        
        <TouchableOpacity
          style={[styles.ctaButton, { backgroundColor: '#34C759' }]}
          onPress={() => setShowReferModal(true)}
          data-testid="refer-friend-btn"
        >
          <Ionicons name="people" size={20} color="#FFF" />
          <Text style={styles.ctaButtonText}>Refer a Friend</Text>
        </TouchableOpacity>
      </View>

      {/* Quick Links  - Showroom, Save Contact */}
      <View style={styles.quickLinksSection}>
        <TouchableOpacity
          style={styles.quickLinkBtn}
          onPress={() => Linking.openURL(`${process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com'}/showcase/${userId}`)}
          data-testid="landing-view-showroom"
        >
          <View style={[styles.quickLinkIcon, { backgroundColor: '#34C75918' }]}>
            <Ionicons name="storefront-outline" size={20} color="#34C759" />
          </View>
          <Text style={styles.quickLinkText}>View My Showcase</Text>
          <Ionicons name="chevron-forward" size={16} color="#8E8E93" />
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.quickLinkBtn}
          onPress={async () => {
            try {
              const res = await api.get(`/card/vcard/${userId}`);
              if (Platform.OS === 'web' && res.data) {
                const vcardData = typeof res.data === 'string' ? res.data : res.data.vcard || '';
                const filename = res.data.filename || 'contact.vcf';
                const blob = new Blob([vcardData], { type: 'text/vcard' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
              }
            } catch {}
          }}
          data-testid="landing-save-contact"
        >
          <View style={[styles.quickLinkIcon, { backgroundColor: '#C9A96218' }]}>
            <Ionicons name="download-outline" size={20} color="#C9A962" />
          </View>
          <Text style={styles.quickLinkText}>Save My Contact</Text>
          <Ionicons name="chevron-forward" size={16} color="#8E8E93" />
        </TouchableOpacity>
      </View>

      {/* External Review Links */}
      {data.store?.review_links && Object.keys(data.store.review_links).length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Leave a Review On</Text>
          <View style={styles.reviewLinksContainer}>
            {data.store.review_links.google && (
              <TouchableOpacity
                style={styles.reviewLinkButton}
                onPress={() => openSocialLink(data.store!.review_links.google!)}
              >
                <Ionicons name="logo-google" size={20} color="#4285F4" />
                <Text style={styles.reviewLinkText}>Google</Text>
              </TouchableOpacity>
            )}
            {data.store.review_links.yelp && (
              <TouchableOpacity
                style={styles.reviewLinkButton}
                onPress={() => openSocialLink(data.store!.review_links.yelp!)}
              >
                <Ionicons name="star" size={20} color="#FF1A1A" />
                <Text style={styles.reviewLinkText}>Yelp</Text>
              </TouchableOpacity>
            )}
            {data.store.review_links.facebook && (
              <TouchableOpacity
                style={styles.reviewLinkButton}
                onPress={() => openSocialLink(data.store!.review_links.facebook!)}
              >
                <Ionicons name="logo-facebook" size={20} color="#1877F2" />
                <Text style={styles.reviewLinkText}>Facebook</Text>
              </TouchableOpacity>
            )}
          </View>
        </View>
      )}

      {/* Footer */}
      <PoweredByFooter />

      {/* Review Modal */}
      <Modal
        visible={showReviewModal}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setShowReviewModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Leave a Review</Text>
              <TouchableOpacity onPress={() => setShowReviewModal(false)}>
                <Ionicons name="close" size={24} color="#FFF" />
              </TouchableOpacity>
            </View>

            <ScrollView style={styles.modalBody}>
              <Text style={styles.inputLabel}>Your Name *</Text>
              <TextInput
                style={styles.input}
                value={reviewName}
                onChangeText={setReviewName}
                placeholder="Enter your name"
                placeholderTextColor="#666"
              />

              <Text style={styles.inputLabel}>Rating</Text>
              <View style={styles.ratingSelector}>
                {[1, 2, 3, 4, 5].map((star) => (
                  <TouchableOpacity key={star} onPress={() => setReviewRating(star)}>
                    <Ionicons
                      name={star <= reviewRating ? 'star' : 'star-outline'}
                      size={32}
                      color="#FFD700"
                    />
                  </TouchableOpacity>
                ))}
              </View>

              <Text style={styles.inputLabel}>Your Review (Optional)</Text>
              <TextInput
                style={[styles.input, styles.textArea]}
                value={reviewText}
                onChangeText={setReviewText}
                placeholder="Tell us about your experience..."
                placeholderTextColor="#666"
                multiline
                numberOfLines={4}
              />

              <Text style={styles.inputLabel}>Phone (Optional)</Text>
              <TextInput
                style={styles.input}
                value={reviewPhone}
                onChangeText={setReviewPhone}
                placeholder="Your phone number"
                placeholderTextColor="#666"
                keyboardType="phone-pad"
              />

              <Text style={styles.inputLabel}>Photo of Purchase (Optional)</Text>
              <TouchableOpacity style={styles.photoUploadButton} onPress={pickImage}>
                {reviewPhoto ? (
                  <Image source={{ uri: reviewPhoto }} style={styles.uploadedPhoto} />
                ) : (
                  <View style={styles.photoPlaceholder}>
                    <Ionicons name="camera" size={32} color="#666" />
                    <Text style={styles.photoPlaceholderText}>Tap to upload photo</Text>
                  </View>
                )}
              </TouchableOpacity>

              <TouchableOpacity
                style={[styles.submitButton, { backgroundColor: primaryColor }]}
                onPress={submitReview}
                disabled={submittingReview}
              >
                {submittingReview ? (
                  <ActivityIndicator color="#FFF" />
                ) : (
                  <Text style={styles.submitButtonText}>Submit Review</Text>
                )}
              </TouchableOpacity>
            </ScrollView>
          </View>
        </View>
      </Modal>

      {/* Referral Modal */}
      <Modal
        visible={showReferModal}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setShowReferModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Refer a Friend</Text>
              <TouchableOpacity onPress={() => setShowReferModal(false)}>
                <Ionicons name="close" size={24} color="#FFF" />
              </TouchableOpacity>
            </View>

            <ScrollView style={styles.modalBody}>
              <Text style={styles.subHeader}>Your Information</Text>
              
              <Text style={styles.inputLabel}>Your Name *</Text>
              <TextInput
                style={styles.input}
                value={referrerName}
                onChangeText={setReferrerName}
                placeholder="Enter your name"
                placeholderTextColor="#666"
              />

              <Text style={styles.inputLabel}>Your Phone (Optional)</Text>
              <TextInput
                style={styles.input}
                value={referrerPhone}
                onChangeText={setReferrerPhone}
                placeholder="Your phone number"
                placeholderTextColor="#666"
                keyboardType="phone-pad"
              />

              <Text style={styles.subHeader}>Friend's Information</Text>

              <Text style={styles.inputLabel}>Friend's Name *</Text>
              <TextInput
                style={styles.input}
                value={referredName}
                onChangeText={setReferredName}
                placeholder="Enter friend's name"
                placeholderTextColor="#666"
              />

              <Text style={styles.inputLabel}>Friend's Phone</Text>
              <TextInput
                style={styles.input}
                value={referredPhone}
                onChangeText={setReferredPhone}
                placeholder="Friend's phone number"
                placeholderTextColor="#666"
                keyboardType="phone-pad"
              />

              <Text style={styles.inputLabel}>Friend's Email (Optional)</Text>
              <TextInput
                style={styles.input}
                value={referredEmail}
                onChangeText={setReferredEmail}
                placeholder="Friend's email"
                placeholderTextColor="#666"
                keyboardType="email-address"
              />

              <Text style={styles.inputLabel}>Notes (Optional)</Text>
              <TextInput
                style={[styles.input, styles.textArea]}
                value={referNotes}
                onChangeText={setReferNotes}
                placeholder="Any additional information..."
                placeholderTextColor="#666"
                multiline
                numberOfLines={3}
              />

              <TouchableOpacity
                style={[styles.submitButton, { backgroundColor: '#34C759' }]}
                onPress={submitReferral}
                disabled={submittingReferral}
              >
                {submittingReferral ? (
                  <ActivityIndicator color="#FFF" />
                ) : (
                  <Text style={styles.submitButtonText}>Submit Referral</Text>
                )}
              </TouchableOpacity>
            </ScrollView>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#1C1C1E',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
  },
  loadingText: {
    color: '#FFF',
    marginTop: 16,
    fontSize: 16,
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    padding: 20,
  },
  errorText: {
    color: '#FF3B30',
    fontSize: 18,
    marginTop: 16,
    textAlign: 'center',
  },
  retryButton: {
    marginTop: 20,
    paddingHorizontal: 24,
    paddingVertical: 12,
    backgroundColor: '#007AFF',
    borderRadius: 8,
  },
  retryButtonText: {
    color: '#FFF',
    fontSize: 16,
    fontWeight: '600',
  },
  heroSection: {
    alignItems: 'center',
    paddingTop: 60,
    paddingBottom: 40,
    paddingHorizontal: 20,
  },
  storeLogo: {
    width: 80,
    height: 80,
    resizeMode: 'contain',
    marginBottom: 16,
    backgroundColor: 'transparent',
  },
  profileImageContainer: {
    marginBottom: 16,
  },
  profileImage: {
    width: 180,
    height: 180,
    borderRadius: 24,
    borderWidth: 4,
    borderColor: '#FFF',
  },
  profileImagePlaceholder: {
    backgroundColor: '#2C2C2E',
    justifyContent: 'center',
    alignItems: 'center',
  },
  userName: {
    fontSize: 28,
    fontWeight: '700',
    color: '#FFF',
    textAlign: 'center',
  },
  userTitle: {
    fontSize: 18,
    color: '#FFF',
    opacity: 0.9,
    marginTop: 4,
  },
  storeName: {
    fontSize: 16,
    color: '#FFF',
    opacity: 0.8,
    marginTop: 8,
  },
  actionsContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 16,
    padding: 20,
    marginTop: -20,
  },
  actionButton: {
    width: 80,
    height: 80,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 6,
  },
  actionButtonText: {
    color: '#FFF',
    fontSize: 12,
    fontWeight: '600',
  },
  section: {
    padding: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#FFF',
    marginBottom: 16,
  },
  bioText: {
    fontSize: 16,
    color: '#CCC',
    lineHeight: 24,
  },
  funFactItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 12,
  },
  funFactText: {
    fontSize: 15,
    color: '#CCC',
    flex: 1,
  },
  socialLinksContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  socialButton: {
    width: 50,
    height: 50,
    borderRadius: 25,
    justifyContent: 'center',
    alignItems: 'center',
  },
  testimonialCard: {
    backgroundColor: '#2C2C2E',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
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
    color: '#FFF',
  },
  starsContainer: {
    flexDirection: 'row',
    gap: 2,
  },
  testimonialText: {
    fontSize: 14,
    color: '#CCC',
    fontStyle: 'italic',
    lineHeight: 20,
  },
  testimonialPhoto: {
    width: '100%',
    height: 200,
    borderRadius: 8,
    marginTop: 12,
  },
  ctaSection: {
    padding: 20,
    gap: 12,
  },
  ctaButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    paddingVertical: 16,
    borderRadius: 12,
  },
  ctaButtonText: {
    color: '#FFF',
    fontSize: 18,
    fontWeight: '600',
  },
  // Quick Links (Showroom, Save Contact)
  quickLinksSection: {
    paddingHorizontal: 20,
    paddingBottom: 12,
    gap: 8,
  },
  quickLinkBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: '#1C1C1E',
    padding: 14,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#2C2C2E',
  },
  quickLinkIcon: {
    width: 40,
    height: 40,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  quickLinkText: {
    flex: 1,
    color: '#FFF',
    fontSize: 15,
    fontWeight: '600',
  },
  reviewLinksContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  reviewLinkButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#2C2C2E',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 8,
  },
  reviewLinkText: {
    color: '#FFF',
    fontSize: 14,
    fontWeight: '500',
  },
  footer: {
    padding: 30,
    alignItems: 'center',
  },
  footerText: {
    color: '#666',
    fontSize: 12,
  },
  // Modal styles
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.8)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: '#1C1C1E',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: '90%',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#FFF',
  },
  modalBody: {
    padding: 20,
  },
  subHeader: {
    fontSize: 16,
    fontWeight: '600',
    color: '#C9A962',
    marginTop: 16,
    marginBottom: 12,
  },
  inputLabel: {
    fontSize: 14,
    color: '#AAA',
    marginBottom: 8,
  },
  input: {
    backgroundColor: '#2C2C2E',
    borderRadius: 10,
    padding: 14,
    color: '#FFF',
    fontSize: 16,
    marginBottom: 16,
  },
  textArea: {
    minHeight: 100,
    textAlignVertical: 'top',
  },
  ratingSelector: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 16,
  },
  photoUploadButton: {
    backgroundColor: '#2C2C2E',
    borderRadius: 10,
    height: 150,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
    overflow: 'hidden',
  },
  photoPlaceholder: {
    alignItems: 'center',
    gap: 8,
  },
  photoPlaceholderText: {
    color: '#666',
    fontSize: 14,
  },
  uploadedPhoto: {
    width: '100%',
    height: '100%',
    resizeMode: 'cover',
  },
  submitButton: {
    paddingVertical: 16,
    borderRadius: 12,
    alignItems: 'center',
    marginBottom: 30,
  },
  submitButtonText: {
    color: '#FFF',
    fontSize: 18,
    fontWeight: '600',
  },
});
