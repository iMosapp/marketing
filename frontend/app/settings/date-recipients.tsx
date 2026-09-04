import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';
import { showSimpleAlert } from '../../services/alert';
import { useThemeStore } from '../../store/themeStore';

type Occasion = 'birthday' | 'anniversary';
type Filter = 'all' | 'on' | 'off';

export default function DateRecipientsScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const user = useAuthStore((state) => state.user);

  const [occasion, setOccasion] = useState<Occasion>('birthday');
  const [filter, setFilter] = useState<Filter>('all');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [data, setData] = useState<any>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const loadData = useCallback(async (occ: Occasion) => {
    if (!user?._id) return;
    try {
      setLoading(true);
      const res = await api.get(`/contacts/${user._id}/date-optins?occasion=${occ}`);
      setData(res.data);
    } catch (e) {
      console.error('Failed to load recipients:', e);
    } finally {
      setLoading(false);
    }
  }, [user?._id]);

  useEffect(() => {
    setSelected(new Set());
    setFilter('all');
    loadData(occasion);
  }, [occasion, loadData]);

  const visible = useMemo(() => {
    let list = data?.contacts || [];
    const q = search.trim().toLowerCase();
    if (q) {
      list = list.filter((c: any) =>
        `${c.first_name} ${c.last_name}`.toLowerCase().includes(q)
      );
    }
    if (filter === 'on') list = list.filter((c: any) => c.opted_in);
    if (filter === 'off') list = list.filter((c: any) => !c.opted_in);
    return list;
  }, [data, search, filter]);

  const toggleSelect = (id: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const selectAllVisible = () => {
    if (selected.size === visible.length && visible.length > 0) {
      setSelected(new Set());
    } else {
      setSelected(new Set(visible.map((c: any) => c.id)));
    }
  };

  const bulkUpdate = async (enable: boolean) => {
    if (selected.size === 0) return;
    setSaving(true);
    try {
      const res = await api.post(`/contacts/${user?._id}/date-optins/bulk`, {
        contact_ids: Array.from(selected),
        occasion,
        enable,
      });
      showSimpleAlert(
        enable ? 'Sends turned ON' : 'Sends turned OFF',
        `${res.data.updated} contact${res.data.updated !== 1 ? 's' : ''} updated. ${enable ? `They'll get your ${occasion} message on their date.` : 'They will not receive anything.'}`
      );
      setSelected(new Set());
      loadData(occasion);
    } catch (e) {
      showSimpleAlert('Error', 'Failed to update. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const occLabel = occasion === 'birthday' ? 'birthday' : 'anniversary';

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton} data-testid="recipients-back-btn">
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Date Recipients</Text>
        <View style={{ width: 40 }} />
      </View>

      {/* Occasion tabs */}
      <View style={styles.tabs}>
        {([['birthday', 'Birthdays', 'gift-outline'], ['anniversary', 'Anniversaries', 'car-outline']] as const).map(([k, label, icon]) => (
          <TouchableOpacity
            key={k}
            style={[styles.tab, occasion === k && styles.tabActive]}
            onPress={() => setOccasion(k)}
            data-testid={`recipients-tab-${k}`}
          >
            <Ionicons name={icon as any} size={16} color={occasion === k ? colors.text : colors.textSecondary} />
            <Text style={[styles.tabText, occasion === k && styles.tabTextActive]}>{label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      <Text style={styles.explainer}>
        Only contacts turned ON receive a {occLabel} text{occasion === 'anniversary' ? ' + card with their car photo on their purchase anniversary' : ' + card on their birthday'}. Nothing sends without your say-so.
      </Text>

      {/* Summary + search */}
      {data && (
        <View style={styles.summaryRow} data-testid="recipients-summary">
          <Text style={styles.summaryText}>
            <Text style={{ color: '#34C759', fontWeight: '800' }}>{data.opted_in}</Text> of {data.total} opted in
          </Text>
          <View style={styles.filterRow}>
            {(['all', 'on', 'off'] as Filter[]).map(f => (
              <TouchableOpacity
                key={f}
                style={[styles.filterChip, filter === f && styles.filterChipActive]}
                onPress={() => setFilter(f)}
                data-testid={`recipients-filter-${f}`}
              >
                <Text style={[styles.filterText, filter === f && styles.filterTextActive]}>
                  {f === 'all' ? 'All' : f === 'on' ? 'ON' : 'OFF'}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      )}

      <View style={styles.searchBox}>
        <Ionicons name="search" size={17} color={colors.textSecondary} />
        <TextInput
          style={styles.searchInput}
          placeholder="Search by name"
          placeholderTextColor={colors.textSecondary}
          value={search}
          onChangeText={setSearch}
          autoCorrect={false}
          data-testid="recipients-search-input"
        />
        {search.length > 0 && (
          <TouchableOpacity onPress={() => setSearch('')}>
            <Ionicons name="close-circle" size={18} color={colors.textSecondary} />
          </TouchableOpacity>
        )}
      </View>

      {/* Select all */}
      {visible.length > 0 && (
        <TouchableOpacity style={styles.selectAllRow} onPress={selectAllVisible} data-testid="recipients-select-all">
          <Ionicons
            name={selected.size === visible.length && visible.length > 0 ? 'checkbox' : 'square-outline'}
            size={20}
            color="#C9A962"
          />
          <Text style={styles.selectAllText}>
            {selected.size > 0 ? `${selected.size} selected` : `Select all (${visible.length})`}
          </Text>
        </TouchableOpacity>
      )}

      {loading ? (
        <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
          <ActivityIndicator size="large" color="#C9A962" />
        </View>
      ) : (
        <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 120 }}>
          {visible.length === 0 ? (
            <View style={{ alignItems: 'center', paddingTop: 50 }}>
              <Ionicons name={occasion === 'birthday' ? 'gift-outline' : 'car-outline'} size={40} color={colors.textSecondary} />
              <Text style={styles.emptyTitle}>
                {search ? 'No matches' : `No contacts with ${occasion === 'birthday' ? 'a birthday' : 'a sold date'} on file`}
              </Text>
              <Text style={styles.emptyHint}>
                {search ? 'Try a different name.' : `Add ${occasion === 'birthday' ? 'birthdays' : 'sold dates'} on contact profiles and they'll show up here.`}
              </Text>
            </View>
          ) : (
            visible.map((c: any) => {
              const isSelected = selected.has(c.id);
              return (
                <TouchableOpacity
                  key={c.id}
                  style={[styles.contactRow, isSelected && styles.contactRowSelected]}
                  onPress={() => toggleSelect(c.id)}
                  data-testid={`recipient-row-${c.id}`}
                >
                  <Ionicons
                    name={isSelected ? 'checkbox' : 'square-outline'}
                    size={22}
                    color={isSelected ? '#C9A962' : colors.textSecondary}
                  />
                  {c.photo_thumbnail ? (
                    <Image source={{ uri: c.photo_thumbnail }} style={styles.avatar} />
                  ) : (
                    <View style={[styles.avatar, styles.avatarPlaceholder]}>
                      <Text style={styles.avatarInitial}>{(c.first_name || '?')[0]}</Text>
                    </View>
                  )}
                  <View style={{ flex: 1 }}>
                    <Text style={styles.contactName} numberOfLines={1}>
                      {c.first_name} {c.last_name}
                    </Text>
                    <Text style={styles.contactMeta} numberOfLines={1}>
                      {c.date || 'No date'}
                      {occasion === 'anniversary' && c.years != null ? ` · ${c.years} yr${c.years !== 1 ? 's' : ''}` : ''}
                      {occasion === 'anniversary' && c.vehicle ? ` · ${c.vehicle}` : ''}
                    </Text>
                  </View>
                  <View style={[styles.statusBadge, { backgroundColor: c.opted_in ? '#34C75922' : `${colors.textSecondary}18` }]}>
                    <Text style={[styles.statusText, { color: c.opted_in ? '#34C759' : colors.textSecondary }]}>
                      {c.opted_in ? 'ON' : 'OFF'}
                    </Text>
                  </View>
                </TouchableOpacity>
              );
            })
          )}
        </ScrollView>
      )}

      {/* Bulk action bar */}
      {selected.size > 0 && (
        <View style={styles.bulkBar} data-testid="recipients-bulk-bar">
          <TouchableOpacity
            style={[styles.bulkBtn, { backgroundColor: '#34C759' }, saving && { opacity: 0.6 }]}
            onPress={() => bulkUpdate(true)}
            disabled={saving}
            data-testid="recipients-bulk-on"
          >
            {saving ? <ActivityIndicator size="small" color="#fff" /> : (
              <>
                <Ionicons name="notifications" size={16} color="#fff" />
                <Text style={styles.bulkBtnText}>Turn ON ({selected.size})</Text>
              </>
            )}
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.bulkBtn, { backgroundColor: '#FF3B30' }, saving && { opacity: 0.6 }]}
            onPress={() => bulkUpdate(false)}
            disabled={saving}
            data-testid="recipients-bulk-off"
          >
            <Ionicons name="notifications-off" size={16} color="#fff" />
            <Text style={styles.bulkBtnText}>Turn OFF</Text>
          </TouchableOpacity>
        </View>
      )}
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingVertical: 12,
    borderBottomWidth: 1, borderBottomColor: colors.card,
  },
  backButton: { padding: 4 },
  headerTitle: { fontSize: 17, fontWeight: '600', color: colors.text },
  tabs: { flexDirection: 'row', paddingHorizontal: 16, paddingTop: 12, gap: 8 },
  tab: {
    flex: 1, paddingVertical: 10, alignItems: 'center', justifyContent: 'center',
    flexDirection: 'row', gap: 6, borderRadius: 10, backgroundColor: colors.card,
  },
  tabActive: { backgroundColor: '#C9A962' },
  tabText: { fontSize: 15, fontWeight: '600', color: colors.textSecondary },
  tabTextActive: { color: colors.text },
  explainer: {
    fontSize: 13, color: colors.textSecondary, paddingHorizontal: 16,
    paddingTop: 10, lineHeight: 18,
  },
  summaryRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingTop: 12,
  },
  summaryText: { fontSize: 15, color: colors.text, fontWeight: '600' },
  filterRow: { flexDirection: 'row', gap: 6 },
  filterChip: {
    paddingVertical: 5, paddingHorizontal: 12, borderRadius: 14,
    backgroundColor: colors.card,
  },
  filterChipActive: { backgroundColor: '#C9A962' },
  filterText: { fontSize: 12, fontWeight: '700', color: colors.textSecondary },
  filterTextActive: { color: colors.text },
  searchBox: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    marginHorizontal: 16, marginTop: 10, marginBottom: 6,
    backgroundColor: colors.card, borderRadius: 10, paddingHorizontal: 12,
  },
  searchInput: { flex: 1, height: 40, fontSize: 15, color: colors.text },
  selectAllRow: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    paddingHorizontal: 18, paddingVertical: 8,
  },
  selectAllText: { fontSize: 15, fontWeight: '600', color: '#C9A962' },
  contactRow: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    backgroundColor: colors.card, borderRadius: 12, padding: 12, marginBottom: 8,
  },
  contactRowSelected: { borderWidth: 1, borderColor: '#C9A962' },
  avatar: { width: 38, height: 38, borderRadius: 19 },
  avatarPlaceholder: {
    backgroundColor: '#C9A96233', alignItems: 'center', justifyContent: 'center',
  },
  avatarInitial: { fontSize: 16, fontWeight: '700', color: '#C9A962' },
  contactName: { fontSize: 15, fontWeight: '600', color: colors.text },
  contactMeta: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  statusBadge: { paddingVertical: 4, paddingHorizontal: 10, borderRadius: 8 },
  statusText: { fontSize: 11, fontWeight: '800', letterSpacing: 0.5 },
  emptyTitle: { fontSize: 16, fontWeight: '600', color: colors.text, marginTop: 12 },
  emptyHint: {
    fontSize: 13, color: colors.textSecondary, textAlign: 'center',
    marginTop: 6, paddingHorizontal: 32, lineHeight: 18,
  },
  bulkBar: {
    position: 'absolute', bottom: 0, left: 0, right: 0,
    flexDirection: 'row', gap: 10, padding: 16, paddingBottom: 28,
    backgroundColor: colors.bg, borderTopWidth: 1, borderTopColor: colors.card,
  },
  bulkBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 6, paddingVertical: 13, borderRadius: 12,
  },
  bulkBtnText: { color: '#fff', fontSize: 15, fontWeight: '700' },
});
