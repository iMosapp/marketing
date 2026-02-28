import React, { useState, useEffect } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView,
  ActivityIndicator, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../../services/api';

interface NDAItem {
  id: string;
  recipient_name: string;
  recipient_email: string;
  sender_name: string;
  status: string;
  created_at: string;
  signed_at?: string;
}

export default function NDAListPage() {
  const router = useRouter();
  const [ndas, setNdas] = useState<NDAItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => { loadNDAs(); }, []);

  const loadNDAs = async () => {
    try {
      const res = await api.get('/nda/agreements');
      setNdas(res.data);
    } catch (err) {
      console.error('Failed to load NDAs:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const statusColor = (s: string) => {
    switch (s) {
      case 'signed': return '#34C759';
      case 'viewed': return '#FF9500';
      case 'pending': return '#007AFF';
      default: return '#8E8E93';
    }
  };

  const fmt = (d: string) => new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={{ width: 40 }}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>NDAs</Text>
        <TouchableOpacity onPress={() => router.push('/admin/nda/create')} data-testid="create-nda-btn">
          <Ionicons name="add" size={28} color="#007AFF" />
        </TouchableOpacity>
      </View>

      <ScrollView
        style={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); loadNDAs(); }} tintColor="#007AFF" />}
      >
        {loading ? (
          <ActivityIndicator color="#007AFF" style={{ marginTop: 40 }} />
        ) : ndas.length === 0 ? (
          <View style={styles.empty}>
            <Ionicons name="document-lock-outline" size={64} color="#2C2C2E" />
            <Text style={styles.emptyTitle}>No NDAs yet</Text>
            <Text style={styles.emptySub}>Create your first NDA to send for signature</Text>
            <TouchableOpacity style={styles.createBtn} onPress={() => router.push('/admin/nda/create')}>
              <Ionicons name="add" size={20} color="#FFF" />
              <Text style={styles.createBtnText}>Create NDA</Text>
            </TouchableOpacity>
          </View>
        ) : (
          ndas.map((nda) => (
            <TouchableOpacity
              key={nda.id}
              style={styles.card}
              onPress={() => router.push(`/admin/nda/${nda.id}`)}
              data-testid={`nda-item-${nda.id}`}
            >
              <View style={styles.cardHeader}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.recipientName}>{nda.recipient_name}</Text>
                  <Text style={styles.recipientEmail}>{nda.recipient_email}</Text>
                </View>
                <View style={[styles.badge, { backgroundColor: statusColor(nda.status) + '20' }]}>
                  <Text style={[styles.badgeText, { color: statusColor(nda.status) }]}>{nda.status.toUpperCase()}</Text>
                </View>
              </View>
              <View style={styles.cardFooter}>
                <Text style={styles.meta}>Created {fmt(nda.created_at)}</Text>
                {nda.signed_at && <Text style={styles.meta}>Signed {fmt(nda.signed_at)}</Text>}
                <Ionicons name="chevron-forward" size={18} color="#666" />
              </View>
            </TouchableOpacity>
          ))
        )}
        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: '#1C1C1E' },
  headerTitle: { fontSize: 17, fontWeight: '600', color: '#FFF' },
  content: { flex: 1, paddingHorizontal: 16, paddingTop: 16 },
  empty: { alignItems: 'center', paddingVertical: 60 },
  emptyTitle: { fontSize: 18, fontWeight: '600', color: '#FFF', marginTop: 16 },
  emptySub: { fontSize: 14, color: '#8E8E93', marginTop: 8 },
  createBtn: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#007AFF', paddingHorizontal: 20, paddingVertical: 12, borderRadius: 12, marginTop: 24 },
  createBtnText: { fontSize: 16, fontWeight: '600', color: '#FFF' },
  card: { backgroundColor: '#1C1C1E', borderRadius: 16, padding: 16, marginBottom: 12 },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 },
  recipientName: { fontSize: 17, fontWeight: '600', color: '#FFF' },
  recipientEmail: { fontSize: 14, color: '#8E8E93', marginTop: 2 },
  badge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  badgeText: { fontSize: 11, fontWeight: '700' },
  cardFooter: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingTop: 12, borderTopWidth: 1, borderTopColor: '#2C2C2E' },
  meta: { fontSize: 13, color: '#666' },
});
