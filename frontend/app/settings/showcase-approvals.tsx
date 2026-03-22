import React, { useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ScrollView, Image,
  ActivityIndicator, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import api from '../../services/api';
import { showAlert, showSimpleAlert } from '../../services/alert';

interface PendingEntry {
  card_id: string;
  customer_name: string;
  customer_phone?: string;
  salesman_name?: string;
  salesman_id?: string;
  customer_photo?: string;
  created_at: string | null;
}

export default function ShowcaseApprovalsScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { user } = useAuthStore();
  const [entries, setEntries] = useState<PendingEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [processingId, setProcessingId] = useState<string | null>(null);
  const [processingAction, setProcessingAction] = useState<'approve' | 'reject' | null>(null);

  useFocusEffect(
    useCallback(() => {
      fetchPending();
    }, [user?._id])
  );

  const fetchPending = async () => {
    if (!user?._id) return;
    try {
      const res = await api.get(`/showcase/pending/${user._id}`);
      setEntries(res.data);
    } catch (e) {
      console.error('Error fetching pending entries:', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const handleApprove = async (cardId: string) => {
    setProcessingId(cardId);
    setProcessingAction('approve');
    try {
      await api.post(`/showcase/entry/${cardId}/approve`);
      setEntries(prev => prev.filter(e => e.card_id !== cardId));
      showSimpleAlert('Approved', 'Entry is now visible on the showcase.');
    } catch {
      showSimpleAlert('Error', 'Failed to approve entry. Please try again.');
    } finally {
      setProcessingId(null);
      setProcessingAction(null);
    }
  };

  const handleReject = (cardId: string) => {
    showAlert(
      'Reject Entry',
      'Are you sure? This entry will be hidden from the showcase.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Reject',
          style: 'destructive',
          onPress: async () => {
            setProcessingId(cardId);
            setProcessingAction('reject');
            try {
              await api.post(`/showcase/entry/${cardId}/reject`);
              setEntries(prev => prev.filter(e => e.card_id !== cardId));
              showSimpleAlert('Rejected', 'Entry has been hidden from the showcase.');
            } catch {
              showSimpleAlert('Error', 'Failed to reject entry. Please try again.');
            } finally {
              setProcessingId(null);
              setProcessingAction(null);
            }
          },
        },
      ]
    );
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '';
    try {
      return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
      return '';
    }
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#C9A962" />
      </View>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton} data-testid="showcase-approvals-back">
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Showcase Approvals</Text>
        <View style={{ width: 32 }} />
      </View>

      <ScrollView
        style={styles.content}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); fetchPending(); }} tintColor="#C9A962" />
        }
      >
        {entries.length === 0 ? (
          <View style={styles.emptyState}>
            <Ionicons name="checkmark-circle" size={64} color="#34C759" />
            <Text style={styles.emptyTitle}>All Caught Up!</Text>
            <Text style={styles.emptySubtitle}>No pending showcase entries to approve. New posts will appear here.</Text>
          </View>
        ) : (
          <>
            <Text style={styles.sectionTitle}>{entries.length} Pending Post{entries.length !== 1 ? 's' : ''}</Text>
            {entries.map((entry) => {
              const isProcessing = processingId === entry.card_id;
              return (
                <View key={entry.card_id} style={styles.entryCard} data-testid={`pending-entry-${entry.card_id}`}>
                  {entry.customer_photo && (
                    <Image source={{ uri: entry.customer_photo }} style={styles.entryPhoto} resizeMode="cover" />
                  )}
                  <View style={styles.entryInfo}>
                    <Text style={styles.customerName}>{entry.customer_name}</Text>
                    {entry.salesman_name && (
                      <Text style={styles.salesmanName}>by {entry.salesman_name}</Text>
                    )}
                    {entry.created_at && (
                      <Text style={styles.dateText}>{formatDate(entry.created_at)}</Text>
                    )}
                  </View>

                  <View style={styles.actionButtons}>
                    <TouchableOpacity
                      style={styles.rejectButton}
                      onPress={() => handleReject(entry.card_id)}
                      disabled={isProcessing}
                      data-testid={`reject-entry-${entry.card_id}`}
                    >
                      {isProcessing && processingAction === 'reject' ? (
                        <ActivityIndicator size="small" color="#FF3B30" />
                      ) : (
                        <>
                          <Ionicons name="close" size={20} color="#FF3B30" />
                          <Text style={styles.rejectButtonText}>Reject</Text>
                        </>
                      )}
                    </TouchableOpacity>

                    <TouchableOpacity
                      style={styles.approveButton}
                      onPress={() => handleApprove(entry.card_id)}
                      disabled={isProcessing}
                      data-testid={`approve-entry-${entry.card_id}`}
                    >
                      {isProcessing && processingAction === 'approve' ? (
                        <ActivityIndicator size="small" color="#FFF" />
                      ) : (
                        <>
                          <Ionicons name="checkmark" size={20} color="#FFF" />
                          <Text style={styles.approveButtonText}>Approve</Text>
                        </>
                      )}
                    </TouchableOpacity>
                  </View>
                </View>
              );
            })}
          </>
        )}
        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  loadingContainer: { flex: 1, backgroundColor: colors.bg, justifyContent: 'center', alignItems: 'center' },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.card,
  },
  backButton: { padding: 4 },
  headerTitle: { fontSize: 18, fontWeight: '600', color: colors.text },
  content: { flex: 1, padding: 16 },
  sectionTitle: { fontSize: 15, fontWeight: '600', color: colors.textSecondary, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 16 },
  emptyState: { alignItems: 'center', justifyContent: 'center', paddingVertical: 60 },
  emptyTitle: { fontSize: 21, fontWeight: '600', color: colors.text, marginTop: 16 },
  emptySubtitle: { fontSize: 16, color: colors.textSecondary, textAlign: 'center', marginTop: 8, paddingHorizontal: 40 },
  entryCard: { backgroundColor: colors.card, borderRadius: 12, padding: 16, marginBottom: 16 },
  entryPhoto: { width: '100%', height: 180, borderRadius: 10, marginBottom: 12, backgroundColor: colors.surface },
  entryInfo: { marginBottom: 12 },
  customerName: { fontSize: 18, fontWeight: '600', color: colors.text },
  salesmanName: { fontSize: 15, color: '#C9A962', marginTop: 2 },
  dateText: { fontSize: 14, color: colors.textSecondary, marginTop: 2 },
  actionButtons: { flexDirection: 'row', gap: 12 },
  rejectButton: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    backgroundColor: '#FF3B3020', paddingVertical: 12, borderRadius: 10, gap: 6,
  },
  rejectButtonText: { fontSize: 17, fontWeight: '600', color: '#FF3B30' },
  approveButton: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    backgroundColor: '#34C759', paddingVertical: 12, borderRadius: 10, gap: 6,
  },
  approveButtonText: { fontSize: 17, fontWeight: '600', color: '#FFF' },
});
