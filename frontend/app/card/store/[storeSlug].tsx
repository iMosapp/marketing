import React, { useState, useEffect } from 'react';
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
  TextInput,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams } from 'expo-router';
import api from '../../../services/api';

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

export default function StoreCardPage() {
  const { storeSlug } = useLocalSearchParams();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<any>(null);
  const [fbRating, setFbRating] = useState(0);
  const [fbName, setFbName] = useState('');
  const [fbText, setFbText] = useState('');
  const [fbSubmitted, setFbSubmitted] = useState(false);
  const [fbSubmitting, setFbSubmitting] = useState(false);

  useEffect(() => { loadData(); }, [storeSlug]);

  const loadData = async () => {
    try {
      const res = await api.get(`/card/store/${storeSlug}`);
      setData(res.data);
    } catch (e) {
      console.error('Error loading store card:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitFeedback = async () => {
    if (fbRating === 0) return;
    setFbSubmitting(true);
    try {
      await api.post(`/review/submit/${storeSlug}`, {
        customer_name: fbName.trim() || 'Anonymous',
        rating: fbRating,
        text_review: fbText.trim() || null,
        source: 'store_card',
      });
      setFbSubmitted(true);
    } catch (e) {
      console.error('Feedback error:', e);
    } finally {
      setFbSubmitting(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#C9A962" />
      </View>
    );
  }

  if (!data) {
    return (
      <View style={styles.loadingContainer}>
        <Ionicons name="alert-circle-outline" size={48} color="#555" />
        <Text style={styles.errorText}>Store not found</Text>
      </View>
    );
  }

  const { store, brand_kit, testimonials, team, review_links } = data;
  const primaryColor = brand_kit?.primary_color || store.primary_color || '#007AFF';

  return (
    <View style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {/* Header */}
        <View style={styles.header}>
          {store.logo_url ? (
            <Image source={{ uri: store.logo_url }} style={styles.logo} resizeMode="contain" data-testid="store-card-logo" />
          ) : (
            <View style={[styles.logoPlaceholder, { backgroundColor: primaryColor + '20' }]}>
              <Ionicons name="business" size={36} color={primaryColor} />
            </View>
          )}
          <Text style={styles.storeName} data-testid="store-card-name">{brand_kit?.company_name || store.name}</Text>
          {brand_kit?.tagline ? <Text style={styles.tagline}>{brand_kit.tagline}</Text> : null}
        </View>

        {/* Contact Actions */}
        <View style={styles.actionsRow}>
          {store.phone && (
            <TouchableOpacity style={styles.actionBtn} onPress={() => openProtocolUrl(`tel:${store.phone}`)} data-testid="store-call-btn">
              <Ionicons name="call" size={20} color="#C9A962" />
              <Text style={styles.actionLabel}>Call</Text>
            </TouchableOpacity>
          )}
          {store.email && (
            <TouchableOpacity style={styles.actionBtn} onPress={() => openProtocolUrl(`mailto:${store.email}`)} data-testid="store-email-btn">
              <Ionicons name="mail" size={20} color="#C9A962" />
              <Text style={styles.actionLabel}>Email</Text>
            </TouchableOpacity>
          )}
          {store.website && (
            <TouchableOpacity style={styles.actionBtn} onPress={() => Linking.openURL(store.website.startsWith('http') ? store.website : `https://${store.website}`)} data-testid="store-web-btn">
              <Ionicons name="globe" size={20} color="#C9A962" />
              <Text style={styles.actionLabel}>Website</Text>
            </TouchableOpacity>
          )}
          {store.address && (
            <TouchableOpacity style={styles.actionBtn} onPress={() => Linking.openURL(`https://maps.google.com/?q=${encodeURIComponent(`${store.address}, ${store.city || ''} ${store.state || ''}`)}`)}>
              <Ionicons name="navigate" size={20} color="#C9A962" />
              <Text style={styles.actionLabel}>Directions</Text>
            </TouchableOpacity>
          )}
        </View>

        {/* Store Details */}
        <View style={styles.section}>
          {store.address && (
            <View style={styles.infoRow}>
              <Ionicons name="location" size={16} color="#C9A962" />
              <Text style={styles.infoText}>
                {store.address}{store.city ? `, ${store.city}` : ''}{store.state ? `, ${store.state}` : ''}
              </Text>
            </View>
          )}
          {store.phone && (
            <View style={styles.infoRow}>
              <Ionicons name="call" size={16} color="#C9A962" />
              <Text style={styles.infoText}>{store.phone}</Text>
            </View>
          )}
          {store.website && (
            <View style={styles.infoRow}>
              <Ionicons name="globe" size={16} color="#C9A962" />
              <Text style={styles.infoText}>{store.website.replace(/^https?:\/\//, '')}</Text>
            </View>
          )}
        </View>

        {/* Team Members */}
        {team && team.length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Our Team</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.teamScroll}>
              {team.map((member: any) => (
                <TouchableOpacity
                  key={member.id}
                  style={styles.teamCard}
                  onPress={() => Linking.openURL(`https://app.imosapp.com/card/${member.id}`)}
                  data-testid={`team-${member.id}`}
                >
                  {member.photo_url ? (
                    <Image source={{ uri: member.photo_url }} style={styles.teamAvatar} />
                  ) : (
                    <View style={styles.teamAvatarPlaceholder}>
                      <Text style={styles.teamAvatarText}>
                        {member.name?.split(' ').map((n: string) => n[0]).join('').toUpperCase() || '?'}
                      </Text>
                    </View>
                  )}
                  <Text style={styles.teamName} numberOfLines={1}>{member.name}</Text>
                  {member.title ? <Text style={styles.teamTitle} numberOfLines={1}>{member.title}</Text> : null}
                </TouchableOpacity>
              ))}
            </ScrollView>
          </View>
        )}

        {/* Testimonials */}
        {testimonials && testimonials.length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Customer Reviews</Text>
            {testimonials.map((t: any) => (
              <View key={t.id} style={styles.testimonialCard}>
                <View style={styles.starsRow}>
                  {[1, 2, 3, 4, 5].map((s) => (
                    <Ionicons key={s} name={s <= t.rating ? 'star' : 'star-outline'} size={14} color="#FFD60A" />
                  ))}
                </View>
                {t.text ? <Text style={styles.testimonialText}>"{t.text}"</Text> : null}
                <Text style={styles.testimonialAuthor}>
                  — {t.customer_name}{t.salesperson_name ? `, helped by ${t.salesperson_name}` : ''}
                </Text>
              </View>
            ))}
          </View>
        )}

        {/* Leave Feedback */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Leave a Review</Text>
          <View style={styles.feedbackCard}>
            {fbSubmitted ? (
              <View style={styles.feedbackSuccess}>
                <Ionicons name="checkmark-circle" size={40} color="#34C759" />
                <Text style={styles.successTitle}>Thank you!</Text>
                <Text style={styles.successText}>Your feedback is pending approval.</Text>
              </View>
            ) : (
              <>
                <Text style={styles.feedbackLabel}>How was your experience?</Text>
                <View style={styles.starSelectRow} data-testid="store-fb-stars">
                  {[1, 2, 3, 4, 5].map((star) => (
                    <TouchableOpacity key={star} onPress={() => setFbRating(star)} data-testid={`store-fb-star-${star}`}>
                      <Ionicons name={star <= fbRating ? 'star' : 'star-outline'} size={36} color={star <= fbRating ? '#FFD60A' : '#3A3A3C'} />
                    </TouchableOpacity>
                  ))}
                </View>
                {fbRating > 0 && (
                  <>
                    <TextInput style={styles.input} placeholder="Your name (optional)" placeholderTextColor="#6E6E73" value={fbName} onChangeText={setFbName} data-testid="store-fb-name" />
                    <TextInput style={[styles.input, styles.textArea]} placeholder="Tell us about your experience..." placeholderTextColor="#6E6E73" value={fbText} onChangeText={setFbText} multiline numberOfLines={3} data-testid="store-fb-text" />
                    <TouchableOpacity style={[styles.submitBtn, { backgroundColor: '#C9A962' }]} onPress={handleSubmitFeedback} disabled={fbSubmitting} data-testid="store-fb-submit">
                      {fbSubmitting ? <ActivityIndicator size="small" color="#000" /> : <Text style={styles.submitText}>Submit Review</Text>}
                    </TouchableOpacity>
                  </>
                )}
              </>
            )}
          </View>
        </View>

        {/* Footer */}
        <TouchableOpacity style={styles.footer} onPress={() => Linking.openURL('https://app.imosapp.com/imos')}>
          <Text style={styles.footerText}>{data?.partner_branding ? `${data.partner_branding.name} \u2022 ` : "Powered by i'M On Social"}</Text>
          <Text style={styles.footerBrand}>{data?.partner_branding ? data.partner_branding.powered_by_text : 'iMOs'}</Text>
        </TouchableOpacity>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  loadingContainer: { flex: 1, backgroundColor: '#000', justifyContent: 'center', alignItems: 'center' },
  errorText: { color: '#8E8E93', fontSize: 16, marginTop: 12 },
  scrollContent: {
    paddingBottom: 40,
    ...(Platform.OS === 'web' ? { maxWidth: 480, marginLeft: 'auto', marginRight: 'auto', width: '100%' } : {}),
  },
  header: { alignItems: 'center', paddingTop: 48, paddingBottom: 24, paddingHorizontal: 24 },
  logo: { width: 80, height: 80, borderRadius: 20, marginBottom: 16, backgroundColor: 'transparent' },
  logoPlaceholder: { width: 80, height: 80, borderRadius: 20, alignItems: 'center', justifyContent: 'center', marginBottom: 16 },
  storeName: { fontSize: 24, fontWeight: '700', color: '#FFF', textAlign: 'center', letterSpacing: -0.3 },
  tagline: { fontSize: 14, color: '#C9A962', marginTop: 4, fontWeight: '500' },
  actionsRow: { flexDirection: 'row', justifyContent: 'center', gap: 24, paddingVertical: 20, borderTopWidth: 1, borderBottomWidth: 1, borderColor: '#1C1C1E', marginHorizontal: 24 },
  actionBtn: { alignItems: 'center', gap: 6 },
  actionLabel: { fontSize: 11, color: '#8E8E93', fontWeight: '500' },
  section: { paddingHorizontal: 24, marginTop: 24 },
  sectionTitle: { fontSize: 13, fontWeight: '600', color: '#C9A962', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 14 },
  infoRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#1A1A1A' },
  infoText: { fontSize: 15, color: '#CCC', flex: 1 },
  teamScroll: { gap: 12, paddingBottom: 4 },
  teamCard: { width: 90, alignItems: 'center' },
  teamAvatar: { width: 56, height: 56, borderRadius: 14, borderWidth: 2, borderColor: '#C9A962' },
  teamAvatarPlaceholder: { width: 56, height: 56, borderRadius: 14, backgroundColor: '#1C1C1E', alignItems: 'center', justifyContent: 'center' },
  teamAvatarText: { color: '#C9A962', fontSize: 16, fontWeight: '600' },
  teamName: { fontSize: 12, color: '#FFF', fontWeight: '600', marginTop: 6, textAlign: 'center' },
  teamTitle: { fontSize: 10, color: '#8E8E93', textAlign: 'center', marginTop: 1 },
  testimonialCard: { backgroundColor: '#1A1A1C', borderRadius: 12, padding: 16, marginBottom: 10, borderWidth: 1, borderColor: '#2A2A2C' },
  starsRow: { flexDirection: 'row', gap: 2, marginBottom: 8 },
  testimonialText: { fontSize: 14, color: '#CCC', fontStyle: 'italic', lineHeight: 20, marginBottom: 8 },
  testimonialAuthor: { fontSize: 12, color: '#8E8E93' },
  feedbackCard: { backgroundColor: '#1A1A1C', borderRadius: 12, padding: 20, borderWidth: 1, borderColor: '#2A2A2C' },
  feedbackLabel: { fontSize: 15, color: '#CCC', textAlign: 'center', marginBottom: 14 },
  starSelectRow: { flexDirection: 'row', justifyContent: 'center', gap: 8, marginBottom: 16 },
  feedbackSuccess: { alignItems: 'center', paddingVertical: 16 },
  successTitle: { fontSize: 18, fontWeight: '700', color: '#FFF', marginTop: 10 },
  successText: { fontSize: 14, color: '#8E8E93', marginTop: 4 },
  input: { backgroundColor: '#111', borderRadius: 10, padding: 14, fontSize: 15, color: '#FFF', borderWidth: 1, borderColor: '#2A2A2C', marginBottom: 10 },
  textArea: { height: 80, textAlignVertical: 'top', paddingTop: 14 },
  submitBtn: { borderRadius: 10, paddingVertical: 14, alignItems: 'center', marginTop: 4 },
  submitText: { fontSize: 16, fontWeight: '600', color: '#000' },
  footer: { flexDirection: 'row', justifyContent: 'center', marginTop: 32, paddingBottom: 20 },
  footerText: { fontSize: 12, color: '#555' },
  footerBrand: { fontSize: 12, fontWeight: '700', color: '#8E8E93' },
});
