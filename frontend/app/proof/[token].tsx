import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, Linking } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams } from 'expo-router';
import api from '../../services/api';
import { COLORS } from '../../store/themeStore';
import { ProofPanel } from '../../components/leads/ProofPanel';

const GOLD = '#C9A962';

export default function PublicProofPage() {
  const { token } = useLocalSearchParams<{ token: string }>();
  const colors = COLORS.dark;
  const [days, setDays] = useState(90);
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    api.get(`/public/proof/${token}?days=${days}`)
      .then(r => { setData(r.data); setError(null); })
      .catch(e => setError(e?.response?.data?.detail || 'This link is not active'))
      .finally(() => setLoading(false));
  }, [token, days]);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} testID="public-proof-page">
      <ScrollView contentContainerStyle={{ padding: 16, gap: 12, maxWidth: 720, width: '100%', alignSelf: 'center' }}>
        <View style={{ gap: 4 }}>
          <Text style={{ fontSize: 12, fontWeight: '700', color: GOLD, letterSpacing: 0.8 }}>{"I'M ON SOCIAL · LIVE LEAD PROOF"}</Text>
          <Text style={{ fontSize: 28, fontWeight: '800', color: colors.text }} testID="public-proof-store">{data?.store_name || 'Internet lead results'}</Text>
          <Text style={{ fontSize: 13, color: colors.textSecondary }}>{"Real numbers from the store's own internet leads. Updated every time this page loads."}</Text>
        </View>
        <View style={{ flexDirection: 'row', gap: 8 }}>
          {[30, 90, 365].map(d => (
            <TouchableOpacity key={d} onPress={() => setDays(d)} style={{ paddingHorizontal: 14, height: 32, borderRadius: 16, justifyContent: 'center', backgroundColor: days === d ? GOLD : colors.card }} testID={`public-proof-days-${d}`}>
              <Text style={{ fontSize: 13, fontWeight: '600', color: days === d ? '#000' : colors.textSecondary }}>{d === 365 ? '1 Year' : `${d} Days`}</Text>
            </TouchableOpacity>
          ))}
        </View>
        {loading && !data ? (
          <ActivityIndicator color={GOLD} style={{ marginTop: 40 }} />
        ) : error ? (
          <View style={{ alignItems: 'center', paddingVertical: 60, gap: 8 }} testID="public-proof-error">
            <Ionicons name="lock-closed-outline" size={36} color={colors.textSecondary} />
            <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text }}>{error}</Text>
            <Text style={{ fontSize: 13, color: colors.textSecondary }}>Ask the store for a fresh link.</Text>
          </View>
        ) : (
          <ProofPanel data={data} colors={colors} publicToken={String(token)} days={days} />
        )}
        <TouchableOpacity onPress={() => Linking.openURL('https://imonsocial.com')} style={{ backgroundColor: colors.card, borderRadius: 14, padding: 16, flexDirection: 'row', alignItems: 'center', gap: 12, borderWidth: 1, borderColor: `${GOLD}55`, marginTop: 8 }} testID="public-proof-cta">
          <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: `${GOLD}22`, alignItems: 'center', justifyContent: 'center' }}>
            <Ionicons name="flash" size={20} color={GOLD} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text }}>Want numbers like these at your store?</Text>
            <Text style={{ fontSize: 13, color: colors.textSecondary }}>{"iMOS answers every internet lead in seconds, texts and calls from the rep's number, and tracks it all. imonsocial.com"}</Text>
          </View>
          <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}
