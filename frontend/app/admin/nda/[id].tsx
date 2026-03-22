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

import { useThemeStore } from '../../../store/themeStore';
export default function NDADetailPage() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
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
    const appUrl = process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com';
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
  if (!nda) return <View style={styles.container}><Text style={{ color: colors.text, textAlign: 'center', marginTop: 80 }}>NDA not found</Text></View>;

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
              {sending ? <ActivityIndicator color={colors.text} /> : (
                <>
                  <Ionicons name="mail" size={20} color={colors.text} />
                  <Text style={styles.actionText}>Resend Email</Text>
                </>
              )}
            </TouchableOpacity>
            <TouchableOpacity style={[styles.actionBtn, { backgroundColor: '#5856D6' }]} onPress={handleCopyLink}>
              <Ionicons name="copy" size={20} color={colors.text} />
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
      <View style={{ width: 32, height: 32, borderRadius: 16, backgroundColor: done ? '#34C75920' : colors.surface, alignItems: 'center', justifyContent: 'center' }}>
        <Ionicons name={icon as any} size={16} color={done ? '#34C759' : '#666'} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 17, color: done ? '#FFF' : '#666', fontWeight: '500' }}>{label}</Text>
        {date && <Text style={{ fontSize: 14, color: colors.textSecondary, marginTop: 2 }}>{fmt(date)}</Text>}
      </View>
      {done && <Ionicons name="checkmark" size={16} color="#34C759" />}
    </View>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.card },
  headerTitle: { fontSize: 18, fontWeight: '600', color: colors.text },
  content: { flex: 1, paddingHorizontal: 20 },
  statusBanner: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 16, borderRadius: 12, marginTop: 16 },
  statusText: { fontSize: 17, fontWeight: '600' },
  section: { marginTop: 24, backgroundColor: colors.card, borderRadius: 16, padding: 16 },
  sectionTitle: { fontSize: 18, fontWeight: '700', color: colors.text, marginBottom: 12 },
  infoRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: colors.surface },
  infoLabel: { fontSize: 16, color: colors.textSecondary },
  infoValue: { fontSize: 16, color: colors.text, fontWeight: '500' },
  sigBox: { marginTop: 12, padding: 12, backgroundColor: '#0D0D0D', borderRadius: 12, borderWidth: 1, borderColor: colors.surface },
  sigLabel: { fontSize: 14, color: colors.textSecondary, marginBottom: 8 },
  sigImage: { width: '100%', height: 80 },
  sigDate: { fontSize: 13, color: '#666', marginTop: 8, textAlign: 'right' },
  pendingText: { fontSize: 16, color: '#FF9500', fontStyle: 'italic', marginTop: 12 },
  timeline: { marginTop: 4 },
  actionBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, backgroundColor: '#007AFF', paddingVertical: 16, borderRadius: 12 },
  actionText: { fontSize: 18, fontWeight: '600', color: colors.text },
});
