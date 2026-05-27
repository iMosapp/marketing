import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, ScrollView, StyleSheet,
  ActivityIndicator, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useThemeStore } from '../../store/themeStore';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';

const ROLE_LABELS: Record<string, string> = {
  super_admin: 'Super Admin', org_admin: 'Admin', admin: 'Admin',
  store_manager: 'Manager', manager: 'Manager', user: 'Rep',
};

const ROLE_COLORS: Record<string, string> = {
  super_admin: '#FF3B30', org_admin: '#FF9500', admin: '#FF9500',
  store_manager: '#34C759', manager: '#34C759', user: '#007AFF',
};

function fmtTime(t: string | null | undefined) {
  if (!t || !t.includes(':')) return '';
  const [h, m] = t.split(':').map(Number);
  if (isNaN(h) || isNaN(m)) return t;
  const ap = h >= 12 ? 'PM' : 'AM';
  return `${h % 12 || 12}:${m.toString().padStart(2, '0')} ${ap}`;
}

function fmtBlocks(blocks: { start: string; end: string }[] | null | undefined) {
  if (!blocks?.length) return null;
  return blocks.map(b => `${fmtTime(b?.start)} – ${fmtTime(b?.end)}`).join('  ·  ');
}

function Initials({ name, size = 44, available }: { name: any; size?: number; available: boolean }) {
  const safe = typeof name === 'string' && name.trim() ? name.trim() : '?';
  const initials = safe.split(' ').filter(Boolean).map((w: string) => w[0] || '').join('').toUpperCase().slice(0, 2) || safe[0] || '?';
  return (
    <View style={{
      width: size, height: size, borderRadius: size / 2,
      backgroundColor: available ? '#34C75925' : '#8E8E9320',
      alignItems: 'center', justifyContent: 'center',
      borderWidth: 2, borderColor: available ? '#34C759' : '#48484A',
    }}>
      <Text style={{ fontSize: size * 0.38, fontWeight: '700', color: available ? '#34C759' : '#8E8E93' }}>
        {initials}
      </Text>
    </View>
  );
}

export default function TeamAvailabilityPage() {
  const { colors } = useThemeStore();
  const s = getStyles(colors);
  const router = useRouter();
  const { user } = useAuthStore();

  const [team, setTeam] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const res = await api.get('/schedule/team', { headers: { 'X-User-ID': user?._id } });
      setTeam(res.data || []);
      setLastUpdated(new Date());
    } catch (e) {
      console.error('Team availability error', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [user?._id]);

  useEffect(() => {
    if (user?._id) {
      load();
      const interval = setInterval(() => load(true), 30_000); // auto-refresh every 30s
      return () => clearInterval(interval);
    }
  }, [user?._id]);

  const onRefresh = () => { setRefreshing(true); load(true); };

  const available = team.filter(r => r.available);
  const offShift  = team.filter(r => !r.available);

  const renderRep = (rep: any) => {
    const blocks    = fmtBlocks(rep.today_blocks);
    const roleColor = ROLE_COLORS[rep.role] || '#8E8E93';
    const roleLabel = ROLE_LABELS[rep.role] || rep.role;
    const isOverride = rep.available && rep.override_until;

    return (
      <View key={rep.user_id} style={s.repCard} data-testid={`rep-card-${rep.user_id}`}>
        <Initials name={rep.name} available={rep.available} />

        <View style={{ flex: 1, marginLeft: 12 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 2 }}>
            <Text style={s.repName}>{rep.name || 'Unknown'}</Text>
            <View style={{ backgroundColor: roleColor + '20', borderRadius: 6, paddingHorizontal: 7, paddingVertical: 2 }}>
              <Text style={{ color: roleColor, fontSize: 11, fontWeight: '700' }}>{roleLabel}</Text>
            </View>
          </View>

          {rep.available ? (
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 5 }}>
              <View style={s.dotGreen} />
              <Text style={s.availText}>
                {isOverride ? 'Override active' : blocks ? blocks : 'On shift'}
              </Text>
              {isOverride && (
                <Text style={{ fontSize: 11, color: colors.textSecondary }}>
                  until {fmtTime(new Date(rep.override_until).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }))}
                </Text>
              )}
            </View>
          ) : (
            <View>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 5 }}>
                <View style={s.dotRed} />
                <Text style={s.offText}>
                  {rep.has_schedule && rep.quiet_mode ? 'Off shift' : 'No schedule set'}
                </Text>
              </View>
              {rep.next_window && (
                <Text style={s.nextText}>Next: {rep.next_window}</Text>
              )}
              {blocks && (
                <Text style={s.blocksText}>Today: {blocks}</Text>
              )}
            </View>
          )}
        </View>

        <TouchableOpacity
          onPress={() => router.push('/settings/schedule' as any)}
          hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
        >
          <Ionicons name="calendar-outline" size={18} color={colors.textSecondary} />
        </TouchableOpacity>
      </View>
    );
  };

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      {/* Header */}
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={{ width: 40 }}>
          <Ionicons name="chevron-back" size={28} color={colors.accent} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={s.title}>Team Availability</Text>
          {lastUpdated && (
            <Text style={s.updatedText}>Updated {lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</Text>
          )}
        </View>
        <TouchableOpacity onPress={() => load(true)} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
          <Ionicons name="refresh" size={22} color={colors.accent} />
        </TouchableOpacity>
      </View>

      {loading ? (
        <View style={s.center}><ActivityIndicator color={colors.accent} size="large" /></View>
      ) : (
        <ScrollView
          style={{ flex: 1 }}
          contentContainerStyle={{ padding: 16, paddingBottom: 60 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />}
        >
          {/* Summary bar */}
          <View style={s.summaryRow}>
            <View style={[s.summaryCard, { borderColor: '#34C759' }]}>
              <Text style={[s.summaryNum, { color: '#34C759' }]}>{available.length}</Text>
              <Text style={s.summaryLabel}>On Shift</Text>
            </View>
            <View style={[s.summaryCard, { borderColor: '#FF3B30' }]}>
              <Text style={[s.summaryNum, { color: '#FF3B30' }]}>{offShift.length}</Text>
              <Text style={s.summaryLabel}>Off Shift</Text>
            </View>
            <View style={[s.summaryCard, { borderColor: colors.accent }]}>
              <Text style={[s.summaryNum, { color: colors.accent }]}>{team.length}</Text>
              <Text style={s.summaryLabel}>Total</Text>
            </View>
          </View>

          {/* On shift */}
          {available.length > 0 && (
            <>
              <View style={s.sectionHeader}>
                <View style={s.dotGreen} />
                <Text style={[s.sectionTitle, { color: '#34C759' }]}>On Shift ({available.length})</Text>
              </View>
              {available.map(renderRep)}
            </>
          )}

          {/* Off shift */}
          {offShift.length > 0 && (
            <>
              <View style={[s.sectionHeader, { marginTop: available.length ? 20 : 0 }]}>
                <View style={s.dotRed} />
                <Text style={[s.sectionTitle, { color: '#FF3B30' }]}>Off Shift ({offShift.length})</Text>
              </View>
              {offShift.map(renderRep)}
            </>
          )}

          {team.length === 0 && (
            <View style={s.empty}>
              <Ionicons name="people-outline" size={56} color={colors.surface} />
              <Text style={{ color: colors.textSecondary, marginTop: 12, fontSize: 15 }}>No team members found</Text>
            </View>
          )}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container:    { flex: 1, backgroundColor: colors.background },
  center:       { flex: 1, alignItems: 'center', justifyContent: 'center' },
  header:       { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.border },
  title:        { fontSize: 18, fontWeight: '700', color: colors.text },
  updatedText:  { fontSize: 11, color: colors.textSecondary, marginTop: 1 },
  summaryRow:   { flexDirection: 'row', gap: 10, marginBottom: 20 },
  summaryCard:  { flex: 1, backgroundColor: colors.card, borderRadius: 14, padding: 14, alignItems: 'center', borderWidth: 1.5 },
  summaryNum:   { fontSize: 28, fontWeight: '800', marginBottom: 2 },
  summaryLabel: { fontSize: 12, color: colors.textSecondary, fontWeight: '600' },
  sectionHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 },
  sectionTitle:  { fontSize: 14, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5 },
  repCard:      { backgroundColor: colors.card, borderRadius: 14, padding: 14, marginBottom: 10, flexDirection: 'row', alignItems: 'center' },
  repName:      { fontSize: 16, fontWeight: '700', color: colors.text },
  availText:    { fontSize: 13, color: '#34C759', fontWeight: '600' },
  offText:      { fontSize: 13, color: '#FF3B30', fontWeight: '600' },
  nextText:     { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  blocksText:   { fontSize: 12, color: colors.textSecondary, marginTop: 1 },
  dotGreen:     { width: 8, height: 8, borderRadius: 4, backgroundColor: '#34C759' },
  dotRed:       { width: 8, height: 8, borderRadius: 4, backgroundColor: '#FF3B30' },
  empty:        { alignItems: 'center', paddingVertical: 60 },
});
