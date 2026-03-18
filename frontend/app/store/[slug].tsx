import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView, Image, TouchableOpacity,
  ActivityIndicator, Linking, Platform,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import Head from 'expo-router/head';
import api from '../../services/api';

interface TeamMember {
  _id: string;
  name: string;
  title: string;
  photo_url: string;
  phone: string;
  email: string;
  bio: string;
  seo_slug: string;
  review_count: number;
  avg_rating: number | null;
}

export default function StoreDirectoryPage() {
  const { slug } = useLocalSearchParams<{ slug: string }>();
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!slug) return;
    api.get(`/seo/store-directory/${slug}`)
      .then(res => {
        if (res.data.error) setError(true);
        else setData(res.data);
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [slug]);

  // Inject JSON-LD
  useEffect(() => {
    if (!data?.schema || Platform.OS !== 'web') return;
    const existing = document.querySelector('script[data-seo-store]');
    if (existing) existing.remove();
    const s = document.createElement('script');
    s.type = 'application/ld+json';
    s.setAttribute('data-seo-store', 'true');
    s.textContent = JSON.stringify(data.schema);
    document.head.appendChild(s);
    return () => { s.remove(); };
  }, [data?.schema]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#007AFF" />
      </View>
    );
  }

  if (error || !data) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>Store not found</Text>
      </View>
    );
  }

  const store = data.store;
  const team: TeamMember[] = data.team || [];
  const location = [store.city, store.state].filter(Boolean).join(', ');

  const handleMemberPress = (member: TeamMember) => {
    if (member.seo_slug) {
      router.push(`/salesperson/${member.seo_slug}`);
    } else {
      router.push(`/card/${member._id}`);
    }
  };

  const renderStars = (rating: number) => {
    const stars = [];
    for (let i = 1; i <= 5; i++) {
      stars.push(
        <Ionicons
          key={i}
          name={i <= Math.round(rating) ? 'star' : 'star-outline'}
          size={12}
          color={i <= Math.round(rating) ? '#FFB800' : '#555'}
        />
      );
    }
    return <View style={styles.stars}>{stars}</View>;
  };

  return (
    <View style={styles.container}>
      <Head>
        <title>{store.name} Team{location ? ` - ${location}` : ''} | i'M On Social</title>
        <meta name="description" content={`Meet the ${team.length} professionals at ${store.name}${location ? ` in ${location}` : ''}. View profiles, reviews, and connect directly.`} />
        <meta property="og:title" content={`${store.name} Team`} />
        <meta property="og:description" content={`Meet the ${team.length} professionals at ${store.name}`} />
        {store.logo_url && <meta property="og:image" content={store.logo_url} />}
        <meta name="twitter:card" content="summary_large_image" />
      </Head>

      <ScrollView contentContainerStyle={styles.scroll}>
        {/* Store header */}
        <View style={styles.storeHeader}>
          {store.logo_url ? (
            <Image source={{ uri: store.logo_url }} style={styles.storeLogo} />
          ) : (
            <View style={styles.storeLogoPlaceholder}>
              <Ionicons name="business" size={36} color="#555" />
            </View>
          )}
          <Text style={styles.storeName} data-testid="store-name">{store.name}</Text>
          {store.organization_name ? (
            <Text style={styles.orgName}>{store.organization_name}</Text>
          ) : null}
          {location ? (
            <View style={styles.locationRow}>
              <Ionicons name="location" size={14} color="#999" />
              <Text style={styles.locationText}>{location}</Text>
            </View>
          ) : null}
          {store.address ? <Text style={styles.addressText}>{store.address}</Text> : null}

          <View style={styles.contactRow}>
            {store.phone ? (
              <TouchableOpacity
                style={styles.contactBtn}
                onPress={() => Linking.openURL(`tel:${store.phone}`)}
                data-testid="store-phone-btn"
              >
                <Ionicons name="call" size={16} color="#007AFF" />
                <Text style={styles.contactBtnText}>Call</Text>
              </TouchableOpacity>
            ) : null}
            {store.website ? (
              <TouchableOpacity
                style={styles.contactBtn}
                onPress={() => Linking.openURL(store.website)}
                data-testid="store-website-btn"
              >
                <Ionicons name="globe" size={16} color="#007AFF" />
                <Text style={styles.contactBtnText}>Website</Text>
              </TouchableOpacity>
            ) : null}
            {store.email ? (
              <TouchableOpacity
                style={styles.contactBtn}
                onPress={() => Linking.openURL(`mailto:${store.email}`)}
              >
                <Ionicons name="mail" size={16} color="#007AFF" />
                <Text style={styles.contactBtnText}>Email</Text>
              </TouchableOpacity>
            ) : null}
          </View>
        </View>

        {/* Team section */}
        <View style={styles.teamSection}>
          <Text style={styles.teamTitle} data-testid="team-heading">
            Meet Our Team ({team.length})
          </Text>

          {team.map(member => (
            <TouchableOpacity
              key={member._id}
              style={styles.memberCard}
              onPress={() => handleMemberPress(member)}
              activeOpacity={0.7}
              data-testid={`team-member-${member._id}`}
            >
              {member.photo_url ? (
                <Image source={{ uri: member.photo_url }} style={styles.memberPhoto} />
              ) : (
                <View style={styles.memberPhotoPlaceholder}>
                  <Text style={styles.memberInitials}>
                    {member.name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)}
                  </Text>
                </View>
              )}
              <View style={styles.memberInfo}>
                <Text style={styles.memberName}>{member.name}</Text>
                {member.title ? <Text style={styles.memberTitle}>{member.title}</Text> : null}
                {member.avg_rating ? (
                  <View style={styles.ratingRow}>
                    {renderStars(member.avg_rating)}
                    <Text style={styles.ratingText}>
                      {member.avg_rating} ({member.review_count} review{member.review_count !== 1 ? 's' : ''})
                    </Text>
                  </View>
                ) : null}
                {member.bio ? (
                  <Text style={styles.memberBio} numberOfLines={2}>{member.bio}</Text>
                ) : null}
              </View>
              <Ionicons name="chevron-forward" size={18} color="#555" />
            </TouchableOpacity>
          ))}

          {team.length === 0 && (
            <Text style={styles.emptyText}>No team members listed yet.</Text>
          )}
        </View>

        {/* Footer */}
        <View style={styles.footer}>
          <Text style={styles.footerText}>Powered by i'M On Social</Text>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0A0A0A' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#0A0A0A' },
  errorText: { color: '#999', fontSize: 16 },
  scroll: { paddingBottom: 40 },
  storeHeader: {
    alignItems: 'center',
    paddingHorizontal: 24,
    paddingTop: 48,
    paddingBottom: 32,
    borderBottomWidth: 1,
    borderBottomColor: '#1A1A1A',
  },
  storeLogo: { width: 80, height: 80, borderRadius: 20, marginBottom: 16 },
  storeLogoPlaceholder: {
    width: 80, height: 80, borderRadius: 20, backgroundColor: '#1A1A1A',
    alignItems: 'center', justifyContent: 'center', marginBottom: 16,
  },
  storeName: { fontSize: 28, fontWeight: '700', color: '#FFF', textAlign: 'center' },
  orgName: { fontSize: 14, color: '#999', marginTop: 4 },
  locationRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 8 },
  locationText: { fontSize: 14, color: '#999' },
  addressText: { fontSize: 13, color: '#666', marginTop: 4 },
  contactRow: { flexDirection: 'row', gap: 12, marginTop: 20 },
  contactBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 16, paddingVertical: 10,
    borderRadius: 10, backgroundColor: '#1A1A1A',
  },
  contactBtnText: { fontSize: 14, fontWeight: '500', color: '#007AFF' },
  teamSection: { paddingHorizontal: 16, paddingTop: 24 },
  teamTitle: { fontSize: 20, fontWeight: '600', color: '#FFF', marginBottom: 16 },
  memberCard: {
    flexDirection: 'row', alignItems: 'center', gap: 14,
    padding: 16, borderRadius: 14, backgroundColor: '#111',
    marginBottom: 10, borderWidth: 1, borderColor: '#1A1A1A',
  },
  memberPhoto: { width: 56, height: 56, borderRadius: 14 },
  memberPhotoPlaceholder: {
    width: 56, height: 56, borderRadius: 14, backgroundColor: '#1A1A1A',
    alignItems: 'center', justifyContent: 'center',
  },
  memberInitials: { fontSize: 18, fontWeight: '600', color: '#555' },
  memberInfo: { flex: 1 },
  memberName: { fontSize: 16, fontWeight: '600', color: '#FFF' },
  memberTitle: { fontSize: 13, color: '#999', marginTop: 2 },
  ratingRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 4 },
  stars: { flexDirection: 'row', gap: 1 },
  ratingText: { fontSize: 12, color: '#999' },
  memberBio: { fontSize: 13, color: '#666', marginTop: 4, lineHeight: 18 },
  emptyText: { fontSize: 14, color: '#555', textAlign: 'center', paddingVertical: 40 },
  footer: { paddingVertical: 32, alignItems: 'center' },
  footerText: { fontSize: 12, color: '#444' },
});
