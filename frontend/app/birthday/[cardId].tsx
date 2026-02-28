import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  ScrollView,
  Image,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Platform,
  Share,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import api from '../../services/api';

const IS_WEB = Platform.OS === 'web';

interface CardData {
  card_id: string;
  customer_name: string;
  customer_photo: string | null;
  headline: string;
  message: string;
  custom_message: string | null;
  footer_text: string;
  salesman: {
    name: string;
    photo: string | null;
    title: string;
    phone: string | null;
    email: string | null;
  } | null;
  store: {
    name: string;
    logo: string | null;
  } | null;
  style: {
    background_color: string;
    accent_color: string;
    text_color: string;
  };
  created_at: string | null;
}

export default function BirthdayCardPage() {
  const { cardId } = useLocalSearchParams();
  const router = useRouter();
  const [card, setCard] = useState<CardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadCard();
  }, [cardId]);

  const loadCard = async () => {
    if (!cardId) return;
    try {
      const res = await api.get(`/birthday/card/${cardId}`);
      setCard(res.data);
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Card not found');
    } finally {
      setLoading(false);
    }
  };

  const handleShare = async () => {
    const url = IS_WEB ? window.location.href : `https://app.imosapp.com/birthday/${cardId}`;
    if (IS_WEB && navigator.share) {
      try { await navigator.share({ title: `Birthday Card for ${card?.customer_name}`, url }); } catch {}
    } else if (IS_WEB) {
      navigator.clipboard?.writeText(url);
      alert('Link copied!');
    } else {
      Share.share({ message: url });
    }
    api.post(`/birthday/card/${cardId}/track`, { action: 'share' }).catch(() => {});
  };

  const handleDownload = () => {
    const imageUrl = `${api.defaults.baseURL}/birthday/card/${cardId}/image`;
    if (IS_WEB) {
      const a = document.createElement('a');
      a.href = imageUrl;
      a.download = `birthday-${cardId}.png`;
      a.target = '_self';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.center}>
          <ActivityIndicator size="large" color="#FF6B8A" />
        </View>
      </SafeAreaView>
    );
  }

  if (error || !card) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.center}>
          <Ionicons name="alert-circle-outline" size={48} color="#FF3B30" />
          <Text style={styles.errorText}>{error || 'Card not found'}</Text>
        </View>
      </SafeAreaView>
    );
  }

  const accent = card.style.accent_color || '#FF6B8A';
  const initials = card.customer_name.split(' ').map(w => w[0] || '').join('').toUpperCase().slice(0, 2);

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: card.style.background_color }]} edges={['top']}>
      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>

        {/* Confetti top decoration */}
        <View style={styles.confettiRow}>
          {['#FF6B8A', '#FFD700', '#00CED1', '#FF8C00', '#9370DB', '#32CD32', '#FF6B8A', '#FFD700'].map((c, i) => (
            <View key={i} style={[styles.confettiDot, { backgroundColor: c, width: 6 + (i % 3) * 3, height: 6 + (i % 3) * 3 }]} />
          ))}
        </View>

        {/* Headline */}
        <Text style={[styles.headline, { color: accent }]}>{card.headline}</Text>

        {/* Customer photo */}
        <View style={styles.photoSection}>
          <View style={[styles.photoRing, { borderColor: accent }]}>
            {card.customer_photo ? (
              <Image source={{ uri: card.customer_photo }} style={styles.customerPhoto} />
            ) : (
              <View style={[styles.photoFallback, { backgroundColor: accent + '30' }]}>
                <Text style={[styles.initials, { color: accent }]}>{initials}</Text>
              </View>
            )}
          </View>
        </View>

        {/* Customer name */}
        <Text style={[styles.customerName, { color: card.style.text_color }]}>{card.customer_name}</Text>

        {/* Message */}
        <Text style={[styles.message, { color: card.style.text_color + 'CC' }]}>{card.message}</Text>

        {/* Custom message */}
        {card.custom_message && (
          <View style={[styles.customMsgBox, { borderLeftColor: accent }]}>
            <Text style={[styles.customMsg, { color: card.style.text_color + 'BB' }]}>"{card.custom_message}"</Text>
          </View>
        )}

        {/* Divider */}
        <View style={[styles.divider, { backgroundColor: accent }]} />

        {/* Salesman info */}
        {card.salesman && (
          <View style={styles.salesmanSection}>
            {card.salesman.photo ? (
              <Image source={{ uri: card.salesman.photo }} style={[styles.salesmanPhoto, { borderColor: accent }]} />
            ) : null}
            <Text style={[styles.salesmanName, { color: card.style.text_color }]}>{card.salesman.name}</Text>
            <Text style={[styles.salesmanTitle, { color: accent }]}>{card.salesman.title}</Text>
            {card.store?.name && (
              <Text style={styles.storeName}>{card.store.name}</Text>
            )}
          </View>
        )}

        {/* Store logo */}
        {card.store?.logo && (
          <Image source={{ uri: card.store.logo }} style={styles.storeLogo} resizeMode="contain" />
        )}

        {/* Actions */}
        <View style={styles.actions}>
          <TouchableOpacity style={[styles.actionBtn, { backgroundColor: accent }]} onPress={handleShare} data-testid="share-birthday-btn">
            <Ionicons name="share-outline" size={18} color="#000" />
            <Text style={styles.actionBtnText}>Share</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[styles.actionBtn, { backgroundColor: '#2C2C2E' }]} onPress={handleDownload} data-testid="download-birthday-btn">
            <Ionicons name="download-outline" size={18} color="#FFF" />
            <Text style={[styles.actionBtnText, { color: '#FFF' }]}>Save</Text>
          </TouchableOpacity>
        </View>

        {/* Connect with salesman */}
        {card.salesman && (
          <View style={styles.connectSection}>
            {card.salesman.phone && (
              <TouchableOpacity
                style={styles.connectBtn}
                onPress={() => {
                  if (IS_WEB) window.location.href = `tel:${card.salesman!.phone}`;
                }}
                data-testid="call-salesman-btn"
              >
                <Ionicons name="call-outline" size={16} color={accent} />
                <Text style={[styles.connectText, { color: accent }]}>Call {card.salesman.name.split(' ')[0]}</Text>
              </TouchableOpacity>
            )}
            {card.salesman.email && (
              <TouchableOpacity
                style={styles.connectBtn}
                onPress={() => {
                  if (IS_WEB) window.location.href = `mailto:${card.salesman!.email}`;
                }}
                data-testid="email-salesman-btn"
              >
                <Ionicons name="mail-outline" size={16} color={accent} />
                <Text style={[styles.connectText, { color: accent }]}>Email</Text>
              </TouchableOpacity>
            )}
          </View>
        )}

        {/* Confetti bottom */}
        <View style={styles.confettiRow}>
          {['#32CD32', '#FF8C00', '#9370DB', '#00CED1', '#FFD700', '#FF6B8A'].map((c, i) => (
            <View key={i} style={[styles.confettiDot, { backgroundColor: c, width: 5 + (i % 3) * 2, height: 5 + (i % 3) * 2 }]} />
          ))}
        </View>

        {/* Footer */}
        <View style={styles.footer}>
          <Text style={styles.footerText}>Powered by i'M On Social</Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#1A1A1A' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 20 },
  errorText: { color: '#FF3B30', fontSize: 16, marginTop: 12 },
  scrollContent: { alignItems: 'center', paddingVertical: 30, paddingHorizontal: 24, maxWidth: 480, width: '100%', alignSelf: 'center' },

  confettiRow: { flexDirection: 'row', justifyContent: 'space-around', width: '100%', marginBottom: 20, paddingHorizontal: 20 },
  confettiDot: { borderRadius: 20 },

  headline: { fontSize: 36, fontWeight: '800', textAlign: 'center', marginBottom: 28, letterSpacing: -0.5 },

  photoSection: { marginBottom: 24 },
  photoRing: { borderWidth: 4, borderRadius: 100, padding: 6 },
  customerPhoto: { width: 160, height: 160, borderRadius: 80 },
  photoFallback: { width: 160, height: 160, borderRadius: 80, justifyContent: 'center', alignItems: 'center' },
  initials: { fontSize: 48, fontWeight: '800' },

  customerName: { fontSize: 28, fontWeight: '700', textAlign: 'center', marginBottom: 16, letterSpacing: -0.3 },
  message: { fontSize: 16, lineHeight: 24, textAlign: 'center', marginBottom: 20, paddingHorizontal: 10 },

  customMsgBox: { borderLeftWidth: 3, paddingLeft: 16, paddingVertical: 8, marginBottom: 24, width: '100%' },
  customMsg: { fontSize: 15, fontStyle: 'italic', lineHeight: 22 },

  divider: { width: 60, height: 4, borderRadius: 2, marginVertical: 24 },

  salesmanSection: { alignItems: 'center', marginBottom: 16 },
  salesmanPhoto: { width: 56, height: 56, borderRadius: 28, borderWidth: 2, marginBottom: 10 },
  salesmanName: { fontSize: 18, fontWeight: '700', marginBottom: 2 },
  salesmanTitle: { fontSize: 14, fontWeight: '500', marginBottom: 2 },
  storeName: { fontSize: 13, color: '#8E8E93', marginTop: 2 },
  storeLogo: { width: 100, height: 36, marginBottom: 20, opacity: 0.7 },

  actions: { flexDirection: 'row', gap: 12, marginBottom: 20 },
  actionBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 24, paddingVertical: 12, borderRadius: 24 },
  actionBtnText: { fontSize: 14, fontWeight: '700', color: '#000' },

  connectSection: { flexDirection: 'row', gap: 20, marginBottom: 24 },
  connectBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 8 },
  connectText: { fontSize: 14, fontWeight: '600' },

  footer: { marginTop: 16, paddingTop: 16 },
  footerText: { fontSize: 11, color: '#3A3A3C', letterSpacing: 0.5 },
});
