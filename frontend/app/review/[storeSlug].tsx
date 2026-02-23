import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Alert,
  Linking,
  Image,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import api from '../../services/api';

// Review platform configurations
const REVIEW_PLATFORMS = [
  { key: 'google', name: 'Google', icon: 'logo-google', color: '#4285F4', bgColor: '#4285F420' },
  { key: 'yelp', name: 'Yelp', icon: 'star', color: '#FF1A1A', bgColor: '#FF1A1A20' },
  { key: 'facebook', name: 'Facebook', icon: 'logo-facebook', color: '#1877F2', bgColor: '#1877F220' },
  { key: 'dealerrater', name: 'DealerRater', icon: 'car-sport', color: '#00A0E3', bgColor: '#00A0E320' },
  { key: 'cars_com', name: 'Cars.com', icon: 'car', color: '#8E44AD', bgColor: '#8E44AD20' },
];

const SOCIAL_PLATFORMS = [
  { key: 'facebook', icon: 'logo-facebook', color: '#1877F2' },
  { key: 'instagram', icon: 'logo-instagram', color: '#E4405F' },
  { key: 'twitter', icon: 'logo-twitter', color: '#1DA1F2' },
  { key: 'youtube', icon: 'logo-youtube', color: '#FF0000' },
  { key: 'tiktok', icon: 'logo-tiktok', color: '#000000' },
  { key: 'linkedin', icon: 'logo-linkedin', color: '#0A66C2' },
];

export default function PublicReviewPage() {
  const { storeSlug, sp } = useLocalSearchParams();
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [storeData, setStoreData] = useState<any>(null);
  const [showFeedbackForm, setShowFeedbackForm] = useState(false);
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);
  
  // Feedback form state
  const [feedback, setFeedback] = useState({
    customer_name: '',
    customer_email: '',
    customer_phone: '',
    rating: 5,
    text_review: '',
    photo_consent: false,
  });

  useEffect(() => {
    loadStoreData();
  }, [storeSlug]);

  const loadStoreData = async () => {
    try {
      const params = sp ? `?sp=${sp}` : '';
      const response = await api.get(`/review/page/${storeSlug}${params}`);
      setStoreData(response.data);
    } catch (error) {
      console.error('Error loading store:', error);
      Alert.alert('Error', 'Store not found');
    } finally {
      setLoading(false);
    }
  };

  const handlePlatformClick = async (platform: string, url: string) => {
    // Track the click
    try {
      await api.post(`/review/submit/${storeSlug}`, {
        customer_name: 'Link Click',
        platform_clicked: platform,
        salesperson_id: sp,
      });
    } catch (e) {
      // Ignore tracking errors
    }
    
    // Open the review platform
    Linking.openURL(url);
  };

  const submitFeedback = async () => {
    if (!feedback.customer_name.trim()) {
      Alert.alert('Required', 'Please enter your name');
      return;
    }
    
    setSubmitting(true);
    try {
      await api.post(`/review/submit/${storeSlug}`, {
        ...feedback,
        salesperson_id: sp,
        salesperson_name: storeData?.salesperson?.name,
      });
      setFeedbackSubmitted(true);
      Alert.alert('Thank You!', 'Your feedback has been submitted.');
    } catch (error) {
      Alert.alert('Error', 'Failed to submit feedback. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const renderStars = () => {
    return (
      <View style={styles.starsContainer}>
        {[1, 2, 3, 4, 5].map((star) => (
          <TouchableOpacity
            key={star}
            onPress={() => setFeedback(prev => ({ ...prev, rating: star }))}
            style={styles.starButton}
          >
            <Ionicons
              name={star <= feedback.rating ? 'star' : 'star-outline'}
              size={36}
              color={star <= feedback.rating ? '#FFD700' : '#8E8E93'}
            />
          </TouchableOpacity>
        ))}
      </View>
    );
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#007AFF" />
        <Text style={styles.loadingText}>Loading...</Text>
      </View>
    );
  }

  if (!storeData) {
    return (
      <View style={styles.errorContainer}>
        <Ionicons name="alert-circle" size={64} color="#FF3B30" />
        <Text style={styles.errorTitle}>Account Not Found</Text>
        <Text style={styles.errorText}>This review page doesn't exist.</Text>
      </View>
    );
  }

  const { store, review_links, social_links, salesperson } = storeData;
  const primaryColor = store.primary_color || '#007AFF';

  // Filter out empty review links
  const activeReviewLinks = REVIEW_PLATFORMS.filter(
    p => review_links?.[p.key] && review_links[p.key].trim()
  );
  
  // Add custom links
  const customLinks = review_links?.custom || [];

  // Filter active social links
  const activeSocialLinks = SOCIAL_PLATFORMS.filter(
    p => social_links?.[p.key] && social_links[p.key].trim()
  );

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top', 'bottom']} style={{ flex: 1 }}>
        <KeyboardAvoidingView 
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={{ flex: 1 }}
        >
          <ScrollView 
            style={styles.scrollView}
            contentContainerStyle={styles.scrollContent}
            showsVerticalScrollIndicator={false}
          >
            {/* Header with Logo */}
            <View style={styles.header}>
              {store.logo_url ? (
                <Image 
                  source={{ uri: store.logo_url }} 
                  style={styles.logo}
                  resizeMode="contain"
                />
              ) : (
                <View style={[styles.logoPlaceholder, { backgroundColor: primaryColor + '20' }]}>
                  <Ionicons name="business" size={40} color={primaryColor} />
                </View>
              )}
              <Text style={styles.storeName}>{store.name}</Text>
              {store.address && (
                <Text style={styles.storeAddress}>
                  {store.address}{store.city ? `, ${store.city}` : ''}{store.state ? `, ${store.state}` : ''}
                </Text>
              )}
              {salesperson?.name && (
                <View style={styles.salespersonBadge}>
                  <Ionicons name="person-circle" size={16} color="#8E8E93" />
                  <Text style={styles.salespersonText}>Helped by {salesperson.name}</Text>
                </View>
              )}
            </View>

            {/* Review Links Section */}
            {(activeReviewLinks.length > 0 || customLinks.length > 0) && (
              <View style={styles.section}>
                <Text style={styles.sectionTitle}>Leave Us a Review</Text>
                <Text style={styles.sectionSubtitle}>
                  Your feedback helps us improve! Choose a platform:
                </Text>
                
                {activeReviewLinks.map((platform) => (
                  <TouchableOpacity
                    key={platform.key}
                    style={[styles.reviewButton, { backgroundColor: platform.bgColor, borderColor: platform.color }]}
                    onPress={() => handlePlatformClick(platform.key, review_links[platform.key])}
                    data-testid={`review-link-${platform.key}`}
                  >
                    <View style={[styles.reviewIconBox, { backgroundColor: platform.color }]}>
                      <Ionicons name={platform.icon as any} size={24} color="#FFF" />
                    </View>
                    <Text style={[styles.reviewButtonText, { color: platform.color }]}>
                      Review on {platform.name}
                    </Text>
                    <Ionicons name="chevron-forward" size={20} color={platform.color} />
                  </TouchableOpacity>
                ))}
                
                {/* Custom Links */}
                {customLinks.map((link: { name: string; url: string }, index: number) => (
                  <TouchableOpacity
                    key={`custom-${index}`}
                    style={[styles.reviewButton, { backgroundColor: primaryColor + '20', borderColor: primaryColor }]}
                    onPress={() => handlePlatformClick('custom', link.url)}
                    data-testid={`review-link-custom-${index}`}
                  >
                    <View style={[styles.reviewIconBox, { backgroundColor: primaryColor }]}>
                      <Ionicons name="link" size={24} color="#FFF" />
                    </View>
                    <Text style={[styles.reviewButtonText, { color: primaryColor }]}>
                      {link.name}
                    </Text>
                    <Ionicons name="chevron-forward" size={20} color={primaryColor} />
                  </TouchableOpacity>
                ))}
              </View>
            )}

            {/* Text Feedback Section */}
            {!feedbackSubmitted ? (
              <View style={styles.section}>
                <TouchableOpacity
                  style={styles.feedbackToggle}
                  onPress={() => setShowFeedbackForm(!showFeedbackForm)}
                  data-testid="toggle-feedback-form"
                >
                  <View style={styles.feedbackToggleLeft}>
                    <Ionicons name="chatbubble-ellipses" size={24} color={primaryColor} />
                    <Text style={styles.feedbackToggleText}>
                      {showFeedbackForm ? 'Hide Feedback Form' : 'Leave Private Feedback'}
                    </Text>
                  </View>
                  <Ionicons 
                    name={showFeedbackForm ? 'chevron-up' : 'chevron-down'} 
                    size={20} 
                    color="#8E8E93" 
                  />
                </TouchableOpacity>
                
                {showFeedbackForm && (
                  <View style={styles.feedbackForm}>
                    <Text style={styles.formLabel}>Your Name *</Text>
                    <TextInput
                      style={styles.input}
                      value={feedback.customer_name}
                      onChangeText={(text) => setFeedback(prev => ({ ...prev, customer_name: text }))}
                      placeholder="John Doe"
                      placeholderTextColor="#8E8E93"
                      data-testid="feedback-name-input"
                    />
                    
                    <Text style={styles.formLabel}>Email (optional)</Text>
                    <TextInput
                      style={styles.input}
                      value={feedback.customer_email}
                      onChangeText={(text) => setFeedback(prev => ({ ...prev, customer_email: text }))}
                      placeholder="john@example.com"
                      placeholderTextColor="#8E8E93"
                      keyboardType="email-address"
                      autoCapitalize="none"
                      data-testid="feedback-email-input"
                    />
                    
                    <Text style={styles.formLabel}>How was your experience?</Text>
                    {renderStars()}
                    
                    <Text style={styles.formLabel}>Your Feedback</Text>
                    <TextInput
                      style={[styles.input, styles.textArea]}
                      value={feedback.text_review}
                      onChangeText={(text) => setFeedback(prev => ({ ...prev, text_review: text }))}
                      placeholder="Tell us about your experience..."
                      placeholderTextColor="#8E8E93"
                      multiline
                      numberOfLines={4}
                      textAlignVertical="top"
                      data-testid="feedback-text-input"
                    />
                    
                    <TouchableOpacity
                      style={styles.consentRow}
                      onPress={() => setFeedback(prev => ({ ...prev, photo_consent: !prev.photo_consent }))}
                    >
                      <View style={[styles.checkbox, feedback.photo_consent && styles.checkboxChecked]}>
                        {feedback.photo_consent && (
                          <Ionicons name="checkmark" size={16} color="#FFF" />
                        )}
                      </View>
                      <Text style={styles.consentText}>
                        I consent to having my feedback shared publicly
                      </Text>
                    </TouchableOpacity>
                    
                    <TouchableOpacity
                      style={[styles.submitButton, { backgroundColor: primaryColor }]}
                      onPress={submitFeedback}
                      disabled={submitting}
                      data-testid="submit-feedback-btn"
                    >
                      {submitting ? (
                        <ActivityIndicator color="#FFF" />
                      ) : (
                        <>
                          <Ionicons name="send" size={20} color="#FFF" />
                          <Text style={styles.submitButtonText}>Submit Feedback</Text>
                        </>
                      )}
                    </TouchableOpacity>
                  </View>
                )}
              </View>
            ) : (
              <View style={styles.thankYouSection}>
                <Ionicons name="checkmark-circle" size={64} color="#34C759" />
                <Text style={styles.thankYouTitle}>Thank You!</Text>
                <Text style={styles.thankYouText}>Your feedback has been received.</Text>
              </View>
            )}

            {/* Social Links Section */}
            {activeSocialLinks.length > 0 && (
              <View style={styles.section}>
                <Text style={styles.sectionTitle}>Follow Us</Text>
                <View style={styles.socialGrid}>
                  {activeSocialLinks.map((platform) => (
                    <TouchableOpacity
                      key={platform.key}
                      style={[styles.socialButton, { backgroundColor: platform.color + '20' }]}
                      onPress={() => Linking.openURL(social_links[platform.key])}
                      data-testid={`social-link-${platform.key}`}
                    >
                      <Ionicons name={platform.icon as any} size={28} color={platform.color} />
                    </TouchableOpacity>
                  ))}
                </View>
              </View>
            )}

            {/* Contact Section */}
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Get in Touch</Text>
              <View style={styles.contactGrid}>
                {store.phone && (
                  <TouchableOpacity
                    style={styles.contactButton}
                    onPress={() => Linking.openURL(`tel:${store.phone}`)}
                    data-testid="call-store-btn"
                  >
                    <Ionicons name="call" size={24} color="#34C759" />
                    <Text style={styles.contactButtonText}>Call Us</Text>
                  </TouchableOpacity>
                )}
                {store.website && (
                  <TouchableOpacity
                    style={styles.contactButton}
                    onPress={() => Linking.openURL(store.website)}
                    data-testid="visit-website-btn"
                  >
                    <Ionicons name="globe" size={24} color="#007AFF" />
                    <Text style={styles.contactButtonText}>Website</Text>
                  </TouchableOpacity>
                )}
              </View>
            </View>

            {/* Business Hours */}
            {store.business_hours && Object.keys(store.business_hours).length > 0 && (
              <View style={styles.section}>
                <Text style={styles.sectionTitle}>Business Hours</Text>
                <View style={styles.hoursCard}>
                  {['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'].map((day) => {
                    const hours = store.business_hours[day];
                    const isOpen = hours !== null;
                    return (
                      <View key={day} style={styles.hoursRow}>
                        <Text style={styles.dayText}>
                          {day.charAt(0).toUpperCase() + day.slice(1)}
                        </Text>
                        <Text style={[styles.hoursText, !isOpen && styles.closedText]}>
                          {isOpen ? `${hours.open} - ${hours.close}` : 'Closed'}
                        </Text>
                      </View>
                    );
                  })}
                </View>
              </View>
            )}

            {/* Footer */}
            <View style={styles.footer}>
              <Text style={styles.footerText}>Powered by iMOs</Text>
            </View>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
  },
  loadingContainer: {
    flex: 1,
    backgroundColor: '#000',
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
    backgroundColor: '#000',
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
    padding: 20,
  },
  header: {
    alignItems: 'center',
    marginBottom: 32,
  },
  logo: {
    width: 100,
    height: 100,
    borderRadius: 20,
    marginBottom: 16,
  },
  logoPlaceholder: {
    width: 100,
    height: 100,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  storeName: {
    fontSize: 28,
    fontWeight: '700',
    color: '#FFF',
    textAlign: 'center',
  },
  storeAddress: {
    fontSize: 15,
    color: '#8E8E93',
    marginTop: 8,
    textAlign: 'center',
  },
  salespersonBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    marginTop: 16,
  },
  salespersonText: {
    color: '#8E8E93',
    fontSize: 14,
    marginLeft: 8,
  },
  section: {
    marginBottom: 28,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 8,
  },
  sectionSubtitle: {
    fontSize: 14,
    color: '#8E8E93',
    marginBottom: 16,
  },
  reviewButton: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    borderRadius: 12,
    marginBottom: 12,
    borderWidth: 1,
  },
  reviewIconBox: {
    width: 44,
    height: 44,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 16,
  },
  reviewButtonText: {
    flex: 1,
    fontSize: 16,
    fontWeight: '600',
  },
  feedbackToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#1C1C1E',
    padding: 16,
    borderRadius: 12,
  },
  feedbackToggleLeft: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  feedbackToggleText: {
    color: '#FFF',
    fontSize: 16,
    fontWeight: '500',
    marginLeft: 12,
  },
  feedbackForm: {
    backgroundColor: '#1C1C1E',
    padding: 16,
    borderRadius: 12,
    marginTop: 12,
  },
  formLabel: {
    color: '#8E8E93',
    fontSize: 13,
    marginBottom: 8,
    marginTop: 12,
  },
  input: {
    backgroundColor: '#2C2C2E',
    borderRadius: 10,
    padding: 14,
    fontSize: 15,
    color: '#FFF',
  },
  textArea: {
    height: 100,
    paddingTop: 14,
  },
  starsContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginVertical: 12,
  },
  starButton: {
    padding: 4,
  },
  consentRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 16,
  },
  checkbox: {
    width: 24,
    height: 24,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: '#8E8E93',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  checkboxChecked: {
    backgroundColor: '#007AFF',
    borderColor: '#007AFF',
  },
  consentText: {
    flex: 1,
    color: '#8E8E93',
    fontSize: 14,
  },
  submitButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 16,
    borderRadius: 12,
    marginTop: 20,
  },
  submitButtonText: {
    color: '#FFF',
    fontSize: 16,
    fontWeight: '600',
    marginLeft: 8,
  },
  thankYouSection: {
    alignItems: 'center',
    padding: 32,
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    marginBottom: 28,
  },
  thankYouTitle: {
    fontSize: 24,
    fontWeight: '700',
    color: '#FFF',
    marginTop: 16,
  },
  thankYouText: {
    fontSize: 16,
    color: '#8E8E93',
    marginTop: 8,
  },
  socialGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginTop: 8,
  },
  socialButton: {
    width: 56,
    height: 56,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
    marginBottom: 12,
  },
  contactGrid: {
    flexDirection: 'row',
    marginTop: 8,
  },
  contactButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#1C1C1E',
    padding: 16,
    borderRadius: 12,
    marginRight: 12,
  },
  contactButtonText: {
    color: '#FFF',
    fontSize: 15,
    fontWeight: '500',
    marginLeft: 8,
  },
  hoursCard: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginTop: 8,
  },
  hoursRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  dayText: {
    color: '#FFF',
    fontSize: 15,
  },
  hoursText: {
    color: '#8E8E93',
    fontSize: 15,
  },
  closedText: {
    color: '#FF3B30',
  },
  footer: {
    alignItems: 'center',
    paddingVertical: 24,
    marginTop: 12,
  },
  footerText: {
    color: '#3A3A3C',
    fontSize: 12,
  },
});
