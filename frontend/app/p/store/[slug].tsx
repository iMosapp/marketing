import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, Image, TouchableOpacity, ActivityIndicator, Linking, Platform } from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import api from '../../../services/api';
import { PoweredByFooter } from '../../../components/PoweredByFooter';

interface StoreData {
  store: {
    id: string;
    name: string;
    logo_url: string | null;
    primary_color: string;
    phone: string | null;
    address: string | null;
    city: string | null;
    state: string | null;
    zip_code: string | null;
    website: string | null;
    description: string;
    hours: string;
    review_links: Record<string, string>;
  };
  team: Array<{
    id: string;
    name: string;
    title: string;
    photo_url: string | null;
  }>;
  reviews: Array<{
    id: string;
    customer_name: string;
    rating: number;
    text: string;
    created_at: string | null;
  }>;
}

export default function StorePublicPage() {
  const { slug } = useLocalSearchParams();
  const [data, setData] = useState<StoreData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchStore = async () => {
      try {
        const res = await api.get(`/p/store/data/${slug}`);
        setData(res.data);
      } catch (e: any) {
        setError(e?.response?.data?.detail || 'Store not found');
      } finally {
        setLoading(false);
      }
    };
    if (slug) fetchStore();
  }, [slug]);

  if (loading) return (
    <View style={styles.center}>
      <ActivityIndicator size="large" color="#C9A962" />
    </View>
  );

  if (error || !data) return (
    <View style={styles.center}>
      <Ionicons name="storefront-outline" size={48} color="#999" />
      <Text style={styles.errorText}>{error || 'Store not found'}</Text>
    </View>
  );

  const { store, team, reviews } = data;
  const color = store.primary_color || '#C9A962';

  const openLink = (url: string) => {
    if (!url) return;
    const full = url.startsWith('http') ? url : `https://${url}`;
    Linking.openURL(full);
  };

  const callPhone = () => {
    if (store.phone) Linking.openURL(`tel:${store.phone}`);
  };

  const openMap = () => {
    const addr = [store.address, store.city, store.state].filter(Boolean).join(', ');
    if (!addr) return;
    const url = Platform.OS === 'ios'
      ? `maps:0,0?q=${encodeURIComponent(addr)}`
      : `geo:0,0?q=${encodeURIComponent(addr)}`;
    Linking.openURL(url);
  };

  const fullAddress = [store.address, store.city, store.state, store.zip_code].filter(Boolean).join(', ');

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Header */}
      <View style={[styles.header, { backgroundColor: color }]}>
        {store.logo_url ? (
          <Image source={{ uri: store.logo_url }} style={styles.logo} resizeMode="contain" />
        ) : (
          <View style={styles.logoPlaceholder}>
            <Ionicons name="storefront" size={40} color="#fff" />
          </View>
        )}
        <Text style={styles.storeName}>{store.name}</Text>
        {store.description ? <Text style={styles.storeDesc}>{store.description}</Text> : null}
      </View>

      {/* Contact Actions */}
      <View style={styles.actions} data-testid="store-actions">
        {store.phone && (
          <TouchableOpacity style={[styles.actionBtn, { borderColor: color }]} onPress={callPhone} data-testid="store-call-btn">
            <Ionicons name="call-outline" size={20} color={color} />
            <Text style={[styles.actionText, { color }]}>Call</Text>
          </TouchableOpacity>
        )}
        {fullAddress ? (
          <TouchableOpacity style={[styles.actionBtn, { borderColor: color }]} onPress={openMap} data-testid="store-directions-btn">
            <Ionicons name="navigate-outline" size={20} color={color} />
            <Text style={[styles.actionText, { color }]}>Directions</Text>
          </TouchableOpacity>
        ) : null}
        {store.website && (
          <TouchableOpacity style={[styles.actionBtn, { borderColor: color }]} onPress={() => openLink(store.website!)} data-testid="store-website-btn">
            <Ionicons name="globe-outline" size={20} color={color} />
            <Text style={[styles.actionText, { color }]}>Website</Text>
          </TouchableOpacity>
        )}
      </View>

      {/* Info */}
      {(fullAddress || store.phone || store.hours) && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Info</Text>
          {fullAddress ? (
            <View style={styles.infoRow}>
              <Ionicons name="location-outline" size={18} color="#666" />
              <Text style={styles.infoText}>{fullAddress}</Text>
            </View>
          ) : null}
          {store.phone && (
            <View style={styles.infoRow}>
              <Ionicons name="call-outline" size={18} color="#666" />
              <Text style={styles.infoText}>{store.phone}</Text>
            </View>
          )}
          {store.hours ? (
            <View style={styles.infoRow}>
              <Ionicons name="time-outline" size={18} color="#666" />
              <Text style={styles.infoText}>{store.hours}</Text>
            </View>
          ) : null}
        </View>
      )}

      {/* Review Links */}
      {Object.keys(store.review_links).length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Leave Us a Review</Text>
          <View style={styles.reviewLinks}>
            {Object.entries(store.review_links).map(([platform, url]) => {
              if (!url) return null;
              const icons: Record<string, string> = { google: 'logo-google', yelp: 'star', facebook: 'logo-facebook' };
              return (
                <TouchableOpacity key={platform} style={[styles.reviewLinkBtn, { backgroundColor: color + '15', borderColor: color + '30' }]} onPress={() => openLink(url)} data-testid={`review-link-${platform}`}>
                  <Ionicons name={(icons[platform] || 'link') as any} size={20} color={color} />
                  <Text style={[styles.reviewLinkText, { color }]}>{platform.charAt(0).toUpperCase() + platform.slice(1)}</Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </View>
      )}

      {/* Team */}
      {team.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Our Team</Text>
          <View style={styles.teamGrid}>
            {team.map((member) => (
              <TouchableOpacity key={member.id} style={styles.teamCard} onPress={() => openLink(`/p/${member.id}`)} data-testid={`team-member-${member.id}`}>
                {member.photo_url ? (
                  <Image source={{ uri: member.photo_url }} style={styles.teamPhoto} />
                ) : (
                  <View style={[styles.teamPhotoPlaceholder, { backgroundColor: color + '20' }]}>
                    <Ionicons name="person" size={24} color={color} />
                  </View>
                )}
                <Text style={styles.teamName} numberOfLines={1}>{member.name}</Text>
                <Text style={styles.teamTitle} numberOfLines={1}>{member.title}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      )}

      {/* Customer Reviews */}
      {reviews.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>What Our Customers Say</Text>
          {reviews.map((review) => (
            <View key={review.id} style={styles.reviewCard} data-testid={`review-${review.id}`}>
              <View style={styles.reviewHeader}>
                <Text style={styles.reviewName}>{review.customer_name}</Text>
                <View style={styles.stars}>
                  {[1, 2, 3, 4, 5].map(s => (
                    <Ionicons key={s} name={s <= review.rating ? 'star' : 'star-outline'} size={14} color="#FFD60A" />
                  ))}
                </View>
              </View>
              {review.text ? <Text style={styles.reviewText}>{review.text}</Text> : null}
            </View>
          ))}
        </View>
      )}

      <PoweredByFooter />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  content: { paddingBottom: 40 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 40 },
  errorText: { marginTop: 12, fontSize: 18, color: '#666' },
  header: { paddingTop: 60, paddingBottom: 32, alignItems: 'center', paddingHorizontal: 20 },
  logo: { width: 80, height: 80, borderRadius: 16, backgroundColor: '#fff', marginBottom: 16 },
  logoPlaceholder: { width: 80, height: 80, borderRadius: 16, backgroundColor: 'rgba(255,255,255,0.2)', justifyContent: 'center', alignItems: 'center', marginBottom: 16 },
  storeName: { fontSize: 24, fontWeight: '700', color: '#fff', textAlign: 'center' },
  storeDesc: { fontSize: 17, color: 'rgba(255,255,255,0.85)', textAlign: 'center', marginTop: 8, lineHeight: 22 },
  actions: { flexDirection: 'row', justifyContent: 'center', flexWrap: 'wrap', gap: 8, paddingVertical: 20, paddingHorizontal: 16 },
  actionBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20, borderWidth: 1.5 },
  actionText: { fontSize: 15, fontWeight: '600' },
  section: { paddingHorizontal: 20, paddingTop: 24 },
  sectionTitle: { fontSize: 19, fontWeight: '700', color: '#1D1D1F', marginBottom: 16 },
  infoRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, marginBottom: 12 },
  infoText: { fontSize: 17, color: '#333', flex: 1, lineHeight: 21 },
  reviewLinks: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  reviewLinkBtn: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 16, paddingVertical: 10, borderRadius: 12, borderWidth: 1 },
  reviewLinkText: { fontSize: 16, fontWeight: '600' },
  teamGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  teamCard: { width: 100, alignItems: 'center' },
  teamPhoto: { width: 64, height: 64, borderRadius: 32 },
  teamPhotoPlaceholder: { width: 64, height: 64, borderRadius: 32, justifyContent: 'center', alignItems: 'center' },
  teamName: { fontSize: 15, fontWeight: '600', color: '#1D1D1F', marginTop: 8, textAlign: 'center' },
  teamTitle: { fontSize: 13, color: '#666', textAlign: 'center' },
  reviewCard: { backgroundColor: '#F9F9F9', borderRadius: 12, padding: 16, marginBottom: 12 },
  reviewHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  reviewName: { fontSize: 17, fontWeight: '600', color: '#1D1D1F' },
  stars: { flexDirection: 'row', gap: 2 },
  reviewText: { fontSize: 16, color: '#444', lineHeight: 20 },
});
