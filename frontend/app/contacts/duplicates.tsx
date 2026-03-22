import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import api from '../../services/api';
import { showSimpleAlert, showConfirm } from '../../services/alert';

interface DuplicateContact {
  id: string;
  first_name: string;
  last_name: string;
  phone: string;
  email: string;
  photo: string | null;
  tags: string[];
  notes: string;
  source: string;
  created_at: string | null;
  event_count: number;
  conversation_count: number;
  card_count: number;
  last_activity: string | null;
}

interface DuplicateSet {
  phone: string;
  contacts: DuplicateContact[];
}

export default function DuplicatesScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const userId = user?._id;

  const [duplicates, setDuplicates] = useState<DuplicateSet[]>([]);
  const [mergedContacts, setMergedContacts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [merging, setMerging] = useState<string | null>(null);
  const [repairing, setRepairing] = useState<string | null>(null);

  const fetchDuplicates = useCallback(async () => {
    if (!userId) return;
    try {
      setLoading(true);
      const res = await api.get(`/contacts/${userId}/duplicates`);
      setDuplicates(res.data?.duplicates || []);
      // Also fetch contacts that have previously been merged (for repair)
      const mergedRes = await api.get(`/contacts/${userId}/merged-history`);
      setMergedContacts(mergedRes.data?.merged || []);
    } catch (e) {
      showSimpleAlert('Failed to load duplicates', 'error');
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useFocusEffect(useCallback(() => { fetchDuplicates(); }, [fetchDuplicates]));

  const handleRepair = (primaryId: string, primaryName: string) => {
    showConfirm(
      'Repair Merge',
      `Re-run migration for "${primaryName}"?\n\nThis will consolidate any messages or records that were missed during the original merge.`,
      async () => {
        try {
          setRepairing(primaryId);
          const res = await api.post(`/contacts/${userId}/repair-merge`, {
            primary_id: primaryId,
          });
          const data = res.data;
          if (data.records_migrated > 0) {
            showSimpleAlert(`Repaired! ${data.records_migrated} record${data.records_migrated !== 1 ? 's' : ''} consolidated.`, 'success');
          } else {
            showSimpleAlert('All records are already consolidated. Nothing to repair.', 'success');
          }
          fetchDuplicates();
        } catch (e: any) {
          showSimpleAlert(e?.response?.data?.detail || 'Repair failed', 'error');
        } finally {
          setRepairing(null);
        }
      }
    );
  };

  useFocusEffect(useCallback(() => { fetchDuplicates(); }, [fetchDuplicates]));

  const handleMerge = (primaryId: string, duplicateId: string, primaryName: string, dupName: string) => {
    showConfirm(
      'Merge Contacts',
      `Keep "${primaryName}" and merge "${dupName}" into it?\n\nAll activity, messages, cards, and tags from "${dupName}" will be moved to "${primaryName}". This cannot be undone.`,
      async () => {
        try {
          setMerging(duplicateId);
          const res = await api.post(`/contacts/${userId}/merge`, {
            primary_id: primaryId,
            duplicate_id: duplicateId,
          });
          const data = res.data;
          showSimpleAlert(
            `Merged! ${data.records_migrated} record${data.records_migrated !== 1 ? 's' : ''} moved.`,
            'success'
          );
          fetchDuplicates();
        } catch (e: any) {
          showSimpleAlert(e?.response?.data?.detail || 'Merge failed', 'error');
        } finally {
          setMerging(null);
        }
      }
    );
  };

  const formatDate = (iso: string | null) => {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const formatPhone = (phone: string) => {
    if (phone.length === 10) {
      return `(${phone.slice(0,3)}) ${phone.slice(3,6)}-${phone.slice(6)}`;
    }
    return phone;
  };

  const renderContact = (contact: DuplicateContact, isPrimary: boolean) => (
    <View
      style={[styles.contactCard, isPrimary && styles.primaryCard]}
      data-testid={`duplicate-contact-${contact.id}`}
    >
      {isPrimary && (
        <View style={styles.suggestedBadge}>
          <Ionicons name="star" size={10} color="#C9A962" />
          <Text style={styles.suggestedText}>Most Active</Text>
        </View>
      )}
      <Text style={styles.contactName} numberOfLines={1}>
        {contact.first_name} {contact.last_name}
      </Text>
      {contact.email ? (
        <Text style={styles.contactDetail} numberOfLines={1}>{contact.email}</Text>
      ) : null}
      <View style={styles.statsRow}>
        <View style={styles.stat}>
          <Ionicons name="pulse-outline" size={13} color={colors.textSecondary} />
          <Text style={styles.statText}>{contact.event_count} events</Text>
        </View>
        <View style={styles.stat}>
          <Ionicons name="chatbubble-outline" size={13} color={colors.textSecondary} />
          <Text style={styles.statText}>{contact.conversation_count} chats</Text>
        </View>
        <View style={styles.stat}>
          <Ionicons name="gift-outline" size={13} color={colors.textSecondary} />
          <Text style={styles.statText}>{contact.card_count} cards</Text>
        </View>
      </View>
      {contact.tags.length > 0 && (
        <View style={styles.tagsRow}>
          {contact.tags.slice(0, 3).map((t) => (
            <View key={t} style={styles.tagChip}>
              <Text style={styles.tagText}>{t}</Text>
            </View>
          ))}
          {contact.tags.length > 3 && (
            <Text style={styles.moreTagsText}>+{contact.tags.length - 3}</Text>
          )}
        </View>
      )}
      <Text style={styles.contactMeta}>
        Created {formatDate(contact.created_at)}
        {contact.last_activity ? ` · Active ${formatDate(contact.last_activity)}` : ''}
      </Text>
    </View>
  );

  const renderDuplicateSet = ({ item }: { item: DuplicateSet }) => {
    const contacts = item.contacts;
    // First contact is the suggested primary (most activity)
    const primary = contacts[0];
    const others = contacts.slice(1);

    return (
      <View style={styles.setCard} data-testid={`duplicate-set-${item.phone}`}>
        <View style={styles.setHeader}>
          <Ionicons name="call-outline" size={16} color={colors.textSecondary} />
          <Text style={styles.setPhone}>{formatPhone(item.phone)}</Text>
          <View style={styles.countBadge}>
            <Text style={styles.countText}>{contacts.length} records</Text>
          </View>
        </View>

        {renderContact(primary, true)}

        {others.map((dup) => (
          <View key={dup.id}>
            {renderContact(dup, false)}
            <TouchableOpacity
              style={styles.mergeButton}
              onPress={() => handleMerge(
                primary.id,
                dup.id,
                `${primary.first_name} ${primary.last_name}`.trim(),
                `${dup.first_name} ${dup.last_name}`.trim(),
              )}
              disabled={merging === dup.id}
              data-testid={`merge-btn-${dup.id}`}
            >
              {merging === dup.id ? (
                <ActivityIndicator size="small" color="#fff" />
              ) : (
                <>
                  <Ionicons name="git-merge-outline" size={16} color="#fff" />
                  <Text style={styles.mergeButtonText}>
                    Merge into {primary.first_name}
                  </Text>
                </>
              )}
            </TouchableOpacity>
          </View>
        ))}
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} data-testid="duplicates-back-btn">
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <View style={{ flex: 1, marginLeft: 12 }}>
          <Text style={styles.title}>Duplicate Contacts</Text>
          <Text style={styles.subtitle}>
            Same phone number, same salesperson
          </Text>
        </View>
        <TouchableOpacity onPress={fetchDuplicates} data-testid="duplicates-refresh-btn">
          <Ionicons name="refresh-outline" size={22} color={colors.textSecondary} />
        </TouchableOpacity>
      </View>

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color={colors.primary} />
          <Text style={styles.loadingText}>Scanning for duplicates...</Text>
        </View>
      ) : duplicates.length === 0 && mergedContacts.length === 0 ? (
        <View style={styles.center} data-testid="no-duplicates">
          <Ionicons name="checkmark-circle-outline" size={56} color="#4CAF50" />
          <Text style={styles.emptyTitle}>No Duplicates Found</Text>
          <Text style={styles.emptySubtitle}>
            All your contacts have unique phone numbers.
          </Text>
        </View>
      ) : (
        <FlatList
          data={[
            ...(mergedContacts.length > 0 ? [{ _type: 'repair_header' }] : []),
            ...mergedContacts.map(m => ({ ...m, _type: 'repair' })),
            ...(duplicates.length > 0 ? [{ _type: 'dup_header' }] : []),
            ...duplicates.map(d => ({ ...d, _type: 'duplicate' })),
          ]}
          keyExtractor={(item, idx) => item._type + '_' + (item.phone || item.primary_id || idx)}
          renderItem={({ item }) => {
            if (item._type === 'repair_header') {
              return (
                <View style={styles.sectionHeader}>
                  <Ionicons name="construct-outline" size={16} color={colors.textSecondary} />
                  <Text style={styles.sectionHeaderText}>Previously Merged — Repair if Needed</Text>
                </View>
              );
            }
            if (item._type === 'repair') {
              return (
                <View style={styles.repairCard} data-testid={`repair-${item.primary_id}`}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.contactName}>{item.primary_name}</Text>
                    <Text style={styles.contactMeta}>
                      {item.duplicates_count} duplicate{item.duplicates_count !== 1 ? 's' : ''} merged · {formatDate(item.merged_at)}
                    </Text>
                  </View>
                  <TouchableOpacity
                    style={styles.repairButton}
                    onPress={() => handleRepair(item.primary_id, item.primary_name)}
                    disabled={repairing === item.primary_id}
                    data-testid={`repair-btn-${item.primary_id}`}
                  >
                    {repairing === item.primary_id ? (
                      <ActivityIndicator size="small" color="#C9A962" />
                    ) : (
                      <>
                        <Ionicons name="construct-outline" size={14} color="#C9A962" />
                        <Text style={styles.repairButtonText}>Repair</Text>
                      </>
                    )}
                  </TouchableOpacity>
                </View>
              );
            }
            if (item._type === 'dup_header') {
              return (
                <View style={styles.sectionHeader}>
                  <Ionicons name="copy-outline" size={16} color={colors.textSecondary} />
                  <Text style={styles.sectionHeaderText}>Unmerged Duplicates</Text>
                </View>
              );
            }
            return renderDuplicateSet({ item: item as DuplicateSet });
          }}
          contentContainerStyle={styles.list}
          data-testid="duplicates-list"
        />
      )}
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  title: { fontSize: 19, fontWeight: '700', color: colors.text },
  subtitle: { fontSize: 14, color: colors.textSecondary, marginTop: 1 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 32 },
  loadingText: { color: colors.textSecondary, marginTop: 12, fontSize: 16 },
  emptyTitle: { fontSize: 19, fontWeight: '600', color: colors.text, marginTop: 16 },
  emptySubtitle: { fontSize: 16, color: colors.textSecondary, marginTop: 6, textAlign: 'center' },
  list: { padding: 16, paddingBottom: 40 },

  setCard: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    marginBottom: 16,
    padding: 14,
    borderWidth: 1,
    borderColor: colors.border,
  },
  setHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  setPhone: {
    fontSize: 17,
    fontWeight: '600',
    color: colors.text,
    marginLeft: 8,
    flex: 1,
  },
  countBadge: {
    backgroundColor: colors.primary + '20',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 10,
  },
  countText: { fontSize: 13, color: colors.primary, fontWeight: '600' },

  contactCard: {
    backgroundColor: colors.background,
    borderRadius: 8,
    padding: 12,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: colors.border,
  },
  primaryCard: {
    borderColor: '#C9A962',
    borderWidth: 1.5,
  },
  suggestedBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 6,
    gap: 4,
  },
  suggestedText: { fontSize: 12, color: '#C9A962', fontWeight: '700', textTransform: 'uppercase' },
  contactName: { fontSize: 17, fontWeight: '600', color: colors.text, marginBottom: 2 },
  contactDetail: { fontSize: 14, color: colors.textSecondary, marginBottom: 6 },
  statsRow: { flexDirection: 'row', gap: 12, marginBottom: 6 },
  stat: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  statText: { fontSize: 13, color: colors.textSecondary },
  tagsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginBottom: 6 },
  tagChip: {
    backgroundColor: colors.primary + '15',
    paddingHorizontal: 7,
    paddingVertical: 2,
    borderRadius: 6,
  },
  tagText: { fontSize: 12, color: colors.primary, fontWeight: '600' },
  moreTagsText: { fontSize: 12, color: colors.textSecondary, alignSelf: 'center' },
  contactMeta: { fontSize: 12, color: colors.textSecondary },

  mergeButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    backgroundColor: '#C9A962',
    paddingVertical: 10,
    borderRadius: 8,
    marginBottom: 8,
  },
  mergeButtonText: { fontSize: 15, fontWeight: '600', color: '#fff' },

  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 10,
    marginTop: 4,
  },
  sectionHeaderText: { fontSize: 15, fontWeight: '600', color: colors.textSecondary },
  repairCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: 10,
    padding: 12,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: colors.border,
  },
  repairButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    borderWidth: 1,
    borderColor: '#C9A962',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
  },
  repairButtonText: { fontSize: 14, fontWeight: '600', color: '#C9A962' },
});
