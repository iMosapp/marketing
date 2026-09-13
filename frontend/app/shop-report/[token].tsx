import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, useWindowDimensions } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams } from 'expo-router';
import api, { API_BASE_URL } from '../../services/api';
import { ReportView, openUrl, type Report } from '../../components/mystery-shops/ReportView';
import { monthLabel, shiftMonth, GOLD, tid } from '../../components/mystery-shops/shared';

// Light, fixed palette: the client GM opens this on a laptop, no login, no theme store.
const LIGHT = { bg: '#F6F4EE', card: '#FFFFFF', border: '#E4DFD2', text: '#161616', textSecondary: '#6B6B6B', surface: '#F1EEE6' };

export default function PublicShopReport() {
  const { token } = useLocalSearchParams<{ token: string }>();
  const { width } = useWindowDimensions();
  const [report, setReport] = useState<Report | null>(null);
  const [month, setMonth] = useState<string | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!token) return;
    setReport(null);
    api.get(`/public/shop-report/${token}`, { params: month ? { month } : {} }).then(r => { setReport(r.data); if (!month) setMonth(r.data.month); }).catch(() => setError('This report link is not valid anymore. Ask I\'m On Social for a fresh one.'));
  }, [token, month]);

  const wide = width > 900;
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: LIGHT.bg }}>
      <ScrollView contentContainerStyle={{ padding: wide ? 32 : 16, paddingBottom: 60, alignItems: 'center' }}>
        <View style={{ width: '100%', maxWidth: 920, gap: 18 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <View style={{ flex: 1, minWidth: 240 }}>
              <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 2 }}>I'M ON SOCIAL · MYSTERY SHOP REPORT</Text>
              <Text style={{ fontSize: wide ? 34 : 26, fontWeight: '800', color: LIGHT.text, marginTop: 4 }} {...tid('public-report-title')}>{report?.client.name || (error ? 'Report' : ' ')}</Text>
              {report && <Text style={{ fontSize: 14, color: LIGHT.textSecondary }}>{[report.client.brand, [report.client.city, report.client.state].filter(Boolean).join(', ')].filter(Boolean).join(' · ')}</Text>}
            </View>
            {report && month && (
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: LIGHT.card, borderRadius: 14, borderWidth: 1, borderColor: LIGHT.border, paddingHorizontal: 8, height: 42 }}>
                <TouchableOpacity onPress={() => setMonth(shiftMonth(month, -1))} hitSlop={8} {...tid('public-report-prev')}><Ionicons name="chevron-back" size={20} color={GOLD} /></TouchableOpacity>
                <Text style={{ fontSize: 14, fontWeight: '800', color: LIGHT.text, minWidth: 130, textAlign: 'center' }} {...tid('public-report-month')}>{monthLabel(month)}</Text>
                <TouchableOpacity onPress={() => setMonth(shiftMonth(month, 1))} hitSlop={8} {...tid('public-report-next')}><Ionicons name="chevron-forward" size={20} color={GOLD} /></TouchableOpacity>
                <TouchableOpacity onPress={() => openUrl(`${API_BASE_URL}/public/shop-report/${token}.pdf?month=${month}`)} style={{ marginLeft: 6, height: 32, paddingHorizontal: 12, borderRadius: 10, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 }} {...tid('public-report-pdf')}>
                  <Ionicons name="download-outline" size={14} color="#111" /><Text style={{ fontSize: 13, fontWeight: '800', color: '#111' }}>PDF</Text>
                </TouchableOpacity>
              </View>
            )}
          </View>
          {error ? <Text style={{ fontSize: 15, color: LIGHT.textSecondary }} {...tid('public-report-error')}>{error}</Text> : !report ? <ActivityIndicator color={GOLD} style={{ marginTop: 40 }} /> : (
            <>
              <Text style={{ fontSize: 14, color: LIGHT.textSecondary, lineHeight: 20 }}>Every call below was placed by our shopper to your team member's cell during your business hours, recorded, transcribed and graded the same way for everyone. Tap any shop to hear the call and read the coaching.</Text>
              <ReportView report={report} colors={LIGHT} compact />
              <Text style={{ fontSize: 12, color: LIGHT.textSecondary, textAlign: 'center', marginTop: 20 }}>Prepared by I'm On Social · imonsocial.com · Questions? Reply to the email this link came in.</Text>
            </>
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
