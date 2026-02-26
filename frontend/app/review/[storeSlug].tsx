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
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams } from 'expo-router';
import api from '../../services/api';

const REVIEW_PLATFORMS = [
  { key: 'google', name: 'Google', icon: 'logo-google', color: '#4285F4', bgColor: '#EAF1FE' },
  { key: 'yelp', name: 'Yelp', icon: 'star', color: '#FF1A1A', bgColor: '#FFF0F0' },
  { key: 'facebook', name: 'Facebook', icon: 'logo-facebook', color: '#1877F2', bgColor: '#EBF3FE' },
  { key: 'dealerrater', name: 'DealerRater', icon: 'car-sport', color: '#00A0E3', bgColor: '#E6F7FD' },
  { key: 'cars_com', name: 'Cars.com', icon: 'car', color: '#8E44AD', bgColor: '#F3EAFA' },
];

export default function PublicReviewPage() {
  const { storeSlug, sp } = useLocalSearchParams();
  const [loading, setLoading] = useState(true);
  const [storeData, setStoreData] = useState<any>(null);
  const [showOtherSites, setShowOtherSites] = useState(false);

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
    } finally {
      setLoading(false);
    }
  };

  const handlePlatformClick = async (platform: string, url: string) => {
    try {
      await api.post(`/review/submit/${storeSlug}`, {
        customer_name: 'Link Click',
        platform_clicked: platform,
        salesperson_id: sp,
      });
    } catch (e) {}
    Linking.openURL(url);
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#4285F4" />
      </View>
    );
  }

  if (!storeData) {
    return (
      <View style={styles.errorContainer}>
        <Ionicons name="alert-circle" size={48} color="#ccc" />
        <Text style={styles.errorTitle}>Page Not Found</Text>
        <Text style={styles.errorText}>This review page doesn't exist.</Text>
      </View>
    );
  }

  const { store, review_links, salesperson } = storeData;
  
  const activeLinks = REVIEW_PLATFORMS.filter(
    p => review_links?.[p.key]?.trim()
  );
  const customLinks = review_links?.custom || [];
  const primaryLink = activeLinks[0];
  const otherLinks = activeLinks.slice(1);

  return (
    <View style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {/* Header */}
        <View style={styles.header}>
          {store.logo_url ? (
            <Image source={{ uri: store.logo_url }} style={styles.logo} resizeMode="contain" />
          ) : (
            <View style={styles.logoPlaceholder}>
              <Ionicons name="business" size={36} color="#666" />
            </View>
          )}
        </View>

        {/* Invitation Card */}
        <View style={styles.card}>
          <Text style={styles.storeName}>{store.name}</Text>
          <Text style={styles.inviteText}>has invited you to review their business</Text>

          {salesperson?.name && (
            <Text style={styles.helpedBy}>Helped by {salesperson.name}</Text>
          )}

          {/* Primary Review Button */}
          {primaryLink && (
            <>
              <Text style={styles.submitText}>
                Submit your review on {primaryLink.name}, or select a different review site
              </Text>
              <TouchableOpacity
                style={[styles.primaryButton, { backgroundColor: primaryLink.color }]}
                onPress={() => handlePlatformClick(primaryLink.key, review_links[primaryLink.key])}
                data-testid={`review-primary-${primaryLink.key}`}
              >
                <Ionicons name={primaryLink.icon as any} size={22} color="#FFF" style={{ marginRight: 10 }} />
                <Text style={styles.primaryButtonText}>Continue with {primaryLink.name}</Text>
              </TouchableOpacity>
            </>
          )}

          {/* Select Different Site */}
          {(otherLinks.length > 0 || customLinks.length > 0) && (
            <TouchableOpacity
              style={styles.selectOtherButton}
              onPress={() => setShowOtherSites(!showOtherSites)}
              data-testid="select-different-site"
            >
              <Text style={styles.selectOtherText}>
                {showOtherSites ? 'Hide other sites' : 'Select a different site'}
              </Text>
              <Ionicons name={showOtherSites ? 'chevron-up' : 'chevron-down'} size={18} color="#4285F4" />
            </TouchableOpacity>
          )}

          {/* Other Review Sites */}
          {showOtherSites && (
            <View style={styles.otherSites}>
              {otherLinks.map((platform) => (
                <TouchableOpacity
                  key={platform.key}
                  style={[styles.otherButton, { backgroundColor: platform.bgColor }]}
                  onPress={() => handlePlatformClick(platform.key, review_links[platform.key])}
                  data-testid={`review-link-${platform.key}`}
                >
                  <Ionicons name={platform.icon as any} size={22} color={platform.color} />
                  <Text style={[styles.otherButtonText, { color: platform.color }]}>
                    {platform.name}
                  </Text>
                  <Ionicons name="open-outline" size={16} color={platform.color} />
                </TouchableOpacity>
              ))}
              {customLinks.map((link: { name: string; url: string }, i: number) => (
                <TouchableOpacity
                  key={`custom-${i}`}
                  style={[styles.otherButton, { backgroundColor: '#F0F0F0' }]}
                  onPress={() => handlePlatformClick('custom', link.url)}
                  data-testid={`review-custom-${i}`}
                >
                  <Ionicons name="link" size={22} color="#333" />
                  <Text style={[styles.otherButtonText, { color: '#333' }]}>{link.name}</Text>
                  <Ionicons name="open-outline" size={16} color="#333" />
                </TouchableOpacity>
              ))}
            </View>
          )}
        </View>

        {/* Footer */}
        <View style={styles.footer}>
          <Text style={styles.footerText}>Powered by </Text>
          <Text style={[styles.footerText, styles.footerBrand]}>iMOs</Text>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F5F5F7',
  },
  loadingContainer: {
    flex: 1,
    backgroundColor: '#F5F5F7',
    justifyContent: 'center',
    alignItems: 'center',
  },
  errorContainer: {
    flex: 1,
    backgroundColor: '#F5F5F7',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  errorTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#333',
    marginTop: 12,
  },
  errorText: {
    fontSize: 14,
    color: '#999',
    marginTop: 4,
  },
  scrollContent: {
    flexGrow: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 40,
    paddingHorizontal: 20,
    ...(Platform.OS === 'web' ? { minHeight: '100vh' } : {}),
  },
  header: {
    alignItems: 'center',
    marginBottom: 24,
  },
  logo: {
    width: 80,
    height: 80,
    borderRadius: 16,
  },
  logoPlaceholder: {
    width: 80,
    height: 80,
    borderRadius: 16,
    backgroundColor: '#E8E8ED',
    alignItems: 'center',
    justifyContent: 'center',
  },
  card: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 32,
    width: '100%',
    maxWidth: 440,
    alignItems: 'center',
    ...(Platform.OS === 'web' ? {
      boxShadow: '0 2px 20px rgba(0,0,0,0.08)',
    } : {
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 2 },
      shadowOpacity: 0.08,
      shadowRadius: 20,
      elevation: 4,
    }),
  },
  storeName: {
    fontSize: 22,
    fontWeight: '700',
    color: '#1A1A1A',
    textAlign: 'center',
  },
  inviteText: {
    fontSize: 15,
    color: '#666',
    textAlign: 'center',
    marginTop: 6,
    lineHeight: 22,
  },
  helpedBy: {
    fontSize: 13,
    color: '#999',
    marginTop: 8,
    fontStyle: 'italic',
  },
  submitText: {
    fontSize: 14,
    color: '#888',
    textAlign: 'center',
    marginTop: 24,
    marginBottom: 16,
    lineHeight: 20,
  },
  primaryButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    width: '100%',
    paddingVertical: 16,
    borderRadius: 12,
    marginBottom: 12,
  },
  primaryButtonText: {
    color: '#FFF',
    fontSize: 16,
    fontWeight: '600',
  },
  selectOtherButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
  },
  selectOtherText: {
    color: '#4285F4',
    fontSize: 14,
    fontWeight: '500',
    marginRight: 4,
  },
  otherSites: {
    width: '100%',
    marginTop: 8,
  },
  otherButton: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 14,
    borderRadius: 12,
    marginBottom: 8,
  },
  otherButtonText: {
    flex: 1,
    fontSize: 15,
    fontWeight: '500',
    marginLeft: 12,
  },
  footer: {
    flexDirection: 'row',
    marginTop: 32,
    alignItems: 'center',
  },
  footerText: {
    fontSize: 12,
    color: '#BBB',
  },
  footerBrand: {
    fontWeight: '700',
  },
});
