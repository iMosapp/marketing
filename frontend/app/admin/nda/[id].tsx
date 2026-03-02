import React, { useState, useEffect } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView,
  ActivityIndicator, Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import * as Clipboard from 'expo-clipboard';
import api from '../../../services/api';
import { showSimpleAlert } from '../../../services/alert';

export default function NDADetailPage() {
  const router = useRouter();
  const { id } = useLocalSearchParams();
  const [nda, setNda] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);

  useEffect(() => { loadNDA(); }, [id]);

  const loadNDA = async () => {
    try {
      const res = await api.get(`/nda/agreements/${id}`);
      setNda(res.data);
    } catch (err) {
      console.error('Failed to load NDA:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    setSending(true);
    try {
      await api.post(`/nda/agreements/${id}/send`);
      showSimpleAlert('Sent', `NDA emailed to ${nda.recipient?.email}`);
    } catch (err) {
      showSimpleAlert('Error', 'Failed to send');
    } finally {
      setSending(false);
    }
  };

  const handleCopyLink = async () => {
    const appUrl = process.env.EXPO_PUBLIC_APP_URL || window?.location?.origin || '';
    await Clipboard.setStringAsync(`${appUrl}/nda/sign/${id}`);
    showSimpleAlert('Copied', 'Link copied');
  };

  const handleDelete = async () => {
    if (!confirm('Delete this NDA?')) return;
    try {
      await api.delete(`/nda/agreements/${id}`);
      router.back();
    } catch (err: any) {
      showSimpleAlert('Error', err.response?.data?.detail || 'Cannot delete');
    }
  };

  const fmt = (d: string) => d ? new Date(d).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';

  const statusColor = (s: string) => s === 'signed' ? '#34C759' : s === 'viewed' ? '#FF9500' : '#007AFF';

  if (loading) return <View style={styles.container}><ActivityIndicator color="#007AFF" style={{ marginTop: 80 }} /></View>;
  if (!nda) return <View style={styles.container}><Text style={{ color: '#FFF', textAlign: 'center', marginTop: 80 }}>NDA not found</Text></View>;

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={{ width: 40 }}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>NDA Details</Text>
        <View style={{ width: 28 }} />
      </View>

      <ScrollView style={styles.content} contentContainerStyle={{ paddingBottom: 40 }}>
        {/* Status */}
        <View style={[styles.statusBanner, { backgroundColor: statusColor(nda.status) + '15' }]}>
          <Ionicons
            name={nda.status === 'signed' ? 'checkmark-circle' : nda.status === 'viewed' ? 'eye' : 'time'}
            size={24}
            color={statusColor(nda.status)}
          />
          <Text style={[styles.statusText, { color: statusColor(nda.status) }]}>
            {nda.status === 'signed' ? 'Signed' : nda.status === 'viewed' ? 'Viewed  - Awaiting Signature' : 'Pending  - Not Yet Opened'}
          </Text>
        </View>

        {/* Parties */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Disclosing Party</Text>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Name</Text>
            <Text style={styles.infoValue}>{nda.sender?.name}</Text>
          </View>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Title</Text>
            <Text style={styles.infoValue}>{nda.sender?.title}</Text>
          </View>
          {nda.sender?.signature && (
            <View style={styles.sigBox}>
              <Text style={styles.sigLabel}>Signature</Text>
              <Image source={{ uri: nda.sender.signature }} style={styles.sigImage} resizeMode="contain" />
              <Text style={styles.sigDate}>Signed {fmt(nda.sender?.signed_at)}</Text>
            </View>
          )}
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Receiving Party</Text>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Name</Text>
            <Text style={styles.infoValue}>{nda.recipient?.name}</Text>
          </View>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Email</Text>
            <Text style={styles.infoValue}>{nda.recipient?.email}</Text>
          </View>
          {nda.signed_recipient ? (
            <>
              <View style={styles.infoRow}>
                <Text style={styles.infoLabel}>Company</Text>
                <Text style={styles.infoValue}>{nda.signed_recipient.company}</Text>
              </View>
              {nda.signed_recipient.signature && (
                <View style={styles.sigBox}>
                  <Text style={styles.sigLabel}>Signature</Text>
                  <Image source={{ uri: nda.signed_recipient.signature }} style={styles.sigImage} resizeMode="contain" />
                  <Text style={styles.sigDate}>Signed {fmt(nda.signed_recipient?.signed_at)}</Text>
                </View>
              )}
            </>
          ) : (
            <Text style={styles.pendingText}>Awaiting signature...</Text>
          )}
        </View>

        {/* Timeline */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Timeline</Text>
          <View style={styles.timeline}>
            <TimelineItem label="Created" date={nda.created_at} icon="create" done />
            <TimelineItem label="Sent" date={nda.sent_at} icon="send" done={!!nda.sent_at} />
            <TimelineItem label="Viewed" date={nda.viewed_at} icon="eye" done={!!nda.viewed_at} />
            <TimelineItem label="Signed" date={nda.signed_at} icon="checkmark-circle" done={!!nda.signed_at} />
          </View>
        </View>

        {/* Actions */}
        {nda.status !== 'signed' && (
          <View style={{ gap: 12, marginTop: 12 }}>
            <TouchableOpacity style={styles.actionBtn} onPress={handleResend} data-testid="nda-resend">
              {sending ? <ActivityIndicator color="#FFF" /> : (
                <>
                  <Ionicons name="mail" size={20} color="#FFF" />
                  <Text style={styles.actionText}>Resend Email</Text>
                </>
              )}
            </TouchableOpacity>
            <TouchableOpacity style={[styles.actionBtn, { backgroundColor: '#5856D6' }]} onPress={handleCopyLink}>
              <Ionicons name="copy" size={20} color="#FFF" />
              <Text style={styles.actionText}>Copy Link</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.actionBtn, { backgroundColor: '#FF3B3020', borderWidth: 1, borderColor: '#FF3B30' }]} onPress={handleDelete}>
              <Ionicons name="trash" size={20} color="#FF3B30" />
              <Text style={[styles.actionText, { color: '#FF3B30' }]}>Delete</Text>
            </TouchableOpacity>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function TimelineItem({ label, date, icon, done }: { label: string; date?: string; icon: string; done: boolean }) {
  const fmt = (d: string) => new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 16 }}>
      <View style={{ width: 32, height: 32, borderRadius: 16, backgroundColor: done ? '#34C75920' : '#2C2C2E', alignItems: 'center', justifyContent: 'center' }}>
        <Ionicons name={icon as any} size={16} color={done ? '#34C759' : '#666'} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 15, color: done ? '#FFF' : '#666', fontWeight: '500' }}>{label}</Text>
        {date && <Text style={{ fontSize: 12, color: '#8E8E93', marginTop: 2 }}>{fmt(date)}</Text>}
      </View>
      {done && <Ionicons name="checkmark" size={16} color="#34C759" />}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: '#1C1C1E' },
  headerTitle: { fontSize: 17, fontWeight: '600', color: '#FFF' },
  content: { flex: 1, paddingHorizontal: 20 },
  statusBanner: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 16, borderRadius: 12, marginTop: 16 },
  statusText: { fontSize: 15, fontWeight: '600' },
  section: { marginTop: 24, backgroundColor: '#1C1C1E', borderRadius: 16, padding: 16 },
  sectionTitle: { fontSize: 16, fontWeight: '700', color: '#FFF', marginBottom: 12 },
  infoRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#2C2C2E' },
  infoLabel: { fontSize: 14, color: '#8E8E93' },
  infoValue: { fontSize: 14, color: '#FFF', fontWeight: '500' },
  sigBox: { marginTop: 12, padding: 12, backgroundColor: '#0D0D0D', borderRadius: 12, borderWidth: 1, borderColor: '#333' },
  sigLabel: { fontSize: 12, color: '#8E8E93', marginBottom: 8 },
  sigImage: { width: '100%', height: 80 },
  sigDate: { fontSize: 11, color: '#666', marginTop: 8, textAlign: 'right' },
  pendingText: { fontSize: 14, color: '#FF9500', fontStyle: 'italic', marginTop: 12 },
  timeline: { marginTop: 4 },
  actionBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, backgroundColor: '#007AFF', paddingVertical: 16, borderRadius: 12 },
  actionText: { fontSize: 16, fontWeight: '600', color: '#FFF' },
});
