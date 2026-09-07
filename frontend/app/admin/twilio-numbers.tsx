import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView,
  ActivityIndicator, TextInput, RefreshControl, Modal,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useThemeStore } from '../../store/themeStore';
import { ScreenHeader, HeaderTextButton } from '../../components/common/ScreenHeader';
import api from '../../services/api';
import { showSimpleAlert, showConfirm } from '../../services/alert';

function timeAgo(iso?: string) {
  if (!iso) return 'Never';
  const d = new Date(iso);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return 'Just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export default function TwilioNumbersDashboard() {
  const { colors } = useThemeStore();
  const s = getS(colors);
  const router = useRouter();

  const [stats, setStats] = useState<any>(null);
  const [numbers, setNumbers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Purchase flow
  const [showPurchase, setShowPurchase] = useState(false);
  const [areaCode, setAreaCode] = useState('');
  const [searching, setSearching] = useState(false);
  const [available, setAvailable] = useState<any[]>([]);
  const [purchasing, setPurchasing] = useState<string | null>(null);
  const [buyFor, setBuyFor] = useState<any | null>(null); // rep to assign the new number to (null = pool)

  // Assign flow
  const [showAssign, setShowAssign] = useState(false);
  const [assignTarget, setAssignTarget] = useState<any>(null);
  const [users, setUsers] = useState<any[]>([]);
  const [fixingWebhook, setFixingWebhook] = useState<string | null>(null);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const [statsRes, numbersRes] = await Promise.all([
        api.get('/admin/twilio/stats'),
        api.get('/admin/twilio/numbers'),
      ]);
      setStats(statsRes.data);
      setNumbers(numbersRes.data.numbers || []);
    } catch { showSimpleAlert('Error', 'Could not load Twilio data.'); }
    finally { setLoading(false); setRefreshing(false); }
  }, []);

  useEffect(() => { load(); }, []);

  const searchNumbers = async () => {
    if (!areaCode.trim()) { showSimpleAlert('Required', 'Enter an area code'); return; }
    setSearching(true);
    setAvailable([]);
    try {
      const res = await api.get(`/admin/twilio/numbers/search?area_code=${areaCode}&limit=8`);
      setAvailable(res.data.numbers || []);
      if (!res.data.numbers?.length) showSimpleAlert('No Results', `No available numbers with area code ${areaCode}. Try another.`);
    } catch { showSimpleAlert('Error', 'Search failed.'); }
    finally { setSearching(false); }
  };

  const purchaseNumber = async (phone: string) => {
    setPurchasing(phone);
    try {
      await api.post('/admin/twilio/numbers/purchase', { phone_number: phone, user_id: buyFor?._id || null });
      showSimpleAlert('Done', buyFor ? `${phone} is live and assigned to ${buyFor.name}. Texting and calling are wired up.` : `${phone} is live in the number pool. Jessi answers it until you assign a rep.`);
      setShowPurchase(false);
      setAvailable([]);
      setAreaCode('');
      setBuyFor(null);
      load();
    } catch (e: any) {
      showSimpleAlert('Error', e?.response?.data?.detail || 'Purchase failed.');
    } finally { setPurchasing(null); }
  };

  const fixWebhook = async (sid: string) => {
    setFixingWebhook(sid);
    try {
      await api.post(`/admin/twilio/numbers/${sid}/fix-webhook`);
      showSimpleAlert('Fixed', 'Webhook updated to the correct URL.');
      load(true);
    } catch { showSimpleAlert('Error', 'Could not update webhook.'); }
    finally { setFixingWebhook(null); }
  };

  const releaseNumber = async (sid: string, phone: string) => {
    showConfirm(
      'Release Number',
      `This will permanently release ${phone} and stop billing. This cannot be undone. Are you sure?`,
      async () => {
        try {
          await api.delete(`/admin/twilio/numbers/${sid}`);
          showSimpleAlert('Released', `${phone} released. Billing stopped.`);
          load();
        } catch (e: any) {
          showSimpleAlert('Error', e?.response?.data?.detail || 'Release failed.');
        }
      }
    );
  };

  const loadUsers = async () => {
    try {
      const res = await api.get('/admin/users');
      setUsers(res.data?.users || res.data || []);
    } catch {}
  };

  const assignNumber = async (sid: string, userId: string | null) => {
    try {
      await api.post(`/admin/twilio/numbers/${sid}/assign`, { user_id: userId });
      showSimpleAlert('Updated', userId ? 'Number assigned.' : 'Number moved to pool.');
      setShowAssign(false);
      load(true);
    } catch (e: any) {
      showSimpleAlert('Error', e?.response?.data?.detail || 'Assignment failed.');
    }
  };

  if (loading) return (
    <SafeAreaView style={s.container} edges={['top']}>
      <ScreenHeader title="Phone Numbers" testID="phone-numbers-header" />
      <ActivityIndicator size="large" color="#C9A962" style={{ marginTop: 80 }} />
    </SafeAreaView>
  );

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <ScreenHeader title="Phone Numbers" testID="phone-numbers-header" right={<HeaderTextButton label="Buy" onPress={() => { setShowPurchase(true); setAvailable([]); setBuyFor(null); loadUsers(); }} testID="phone-numbers-buy-btn" />} />

      <ScrollView
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor="#C9A962" />}
        contentContainerStyle={{ padding: 16, paddingBottom: 60 }}
      >
        {/* Stats Bar */}
        {stats && (
          <View style={s.statsRow}>
            <StatBox label="Total Numbers" value={stats.total_numbers} color={colors.text} />
            <StatBox label="Assigned" value={stats.assigned} color="#34C759" />
            <StatBox label="In Pool" value={stats.in_pool} color="#FF9500" />
            <StatBox label="Monthly Cost" value={`$${stats.monthly_cost_usd?.toFixed(2)}`} color="#C9A962" />
          </View>
        )}

        {/* Messaging Service */}
        {stats?.messaging_service_sid && (
          <View style={{ backgroundColor: '#34C75915', borderRadius: 12, padding: 12, marginBottom: 16, flexDirection: 'row', alignItems: 'center', gap: 8, borderWidth: 1, borderColor: '#34C75930' }}>
            <Ionicons name="checkmark-circle" size={18} color="#34C759" />
            <Text style={{ fontSize: 13, color: '#34C759', flex: 1 }}>
              A2P 10DLC Active — Messaging Service: {stats.messaging_service_sid.slice(0, 12)}...
            </Text>
          </View>
        )}

        {/* Number Cards */}
        {numbers.map(num => (
          <View key={num.sid} style={s.card}>
            {/* Number + status */}
            <View style={s.cardRow}>
              <View style={{ flex: 1 }}>
                <Text style={s.cardNumber}>{num.friendly_name}</Text>
                <Text style={s.cardSub}>{num.phone_number}</Text>
              </View>
              <View style={[s.statusBadge, { backgroundColor: num.status === 'assigned' ? '#34C75920' : '#FF950020' }]}>
                <Text style={{ fontSize: 11, fontWeight: '700', color: num.status === 'assigned' ? '#34C759' : '#FF9500' }}>
                  {num.status === 'assigned' ? 'ASSIGNED' : 'POOL'}
                </Text>
              </View>
            </View>

            {/* Assigned user or pool info */}
            {num.assigned_to ? (
              <View style={s.assignedRow}>
                <Ionicons name="person-circle" size={16} color="#C9A962" />
                <Text style={s.assignedText}>
                  {num.assigned_to.name} — {num.store_name || 'No store'}
                </Text>
                {!num.assigned_to.active && (
                  <View style={{ backgroundColor: '#FF3B3020', borderRadius: 8, paddingHorizontal: 6, paddingVertical: 2 }}>
                    <Text style={{ fontSize: 10, color: '#FF3B30', fontWeight: '700' }}>INACTIVE</Text>
                  </View>
                )}
              </View>
            ) : (
              <View style={{ gap: 4, marginBottom: 8 }}>
                <View style={[s.assignedRow, { marginBottom: 0 }]}>
                  <Ionicons name="alert-circle" size={16} color="#FF9500" />
                  <Text style={[s.assignedText, { color: '#FF9500' }]}>In pool. Jessi answers inbound for the store.</Text>
                </View>
                {num.previous_owner?.name && (
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingLeft: 22 }}>
                    <Ionicons name="person-remove-outline" size={13} color={colors.textSecondary} />
                    <Text style={{ fontSize: 12, color: colors.textSecondary }}>
                      Previously: {num.previous_owner.name}
                      {num.previous_owner.released_at ? ` (released ${timeAgo(num.previous_owner.released_at)})` : ''}
                    </Text>
                  </View>
                )}
              </View>
            )}

            {/* Stats row */}
            <View style={s.statsLine}>
              <StatChip icon="people" value={`${num.contact_count} contacts`} color={colors.textSecondary} />
              <StatChip icon="chatbubble" value={`${num.messages_this_month} msgs/mo`} color={colors.textSecondary} />
              <StatChip icon="time" value={`Last: ${timeAgo(num.last_activity)}`} color={colors.textSecondary} />
            </View>

            {/* Webhook status */}
            <View style={[s.webhookRow, { backgroundColor: num.webhook_correct ? '#34C75910' : '#FF3B3010' }]}>
              <Ionicons
                name={num.webhook_correct ? 'checkmark-circle' : 'warning'}
                size={14}
                color={num.webhook_correct ? '#34C759' : '#FF3B30'}
              />
              <Text style={{ fontSize: 12, color: num.webhook_correct ? '#34C759' : '#FF3B30', flex: 1 }} numberOfLines={1}>
                {num.webhook_correct ? 'Texts and calls OK' : 'Needs a fix: texts will not reach the app'}
              </Text>
              {!num.webhook_correct && (
                <TouchableOpacity
                  onPress={() => fixWebhook(num.sid)}
                  style={{ backgroundColor: '#C9A96220', borderRadius: 8, paddingHorizontal: 8, paddingVertical: 3 }}
                  disabled={fixingWebhook === num.sid}
                >
                  {fixingWebhook === num.sid
                    ? <ActivityIndicator size="small" color="#C9A962" />
                    : <Text style={{ fontSize: 11, fontWeight: '700', color: '#C9A962' }}>Fix</Text>
                  }
                </TouchableOpacity>
              )}
            </View>

            {/* Actions */}
            <View style={s.actionRow}>
              <TouchableOpacity style={s.actionBtn} onPress={() => { setAssignTarget(num); loadUsers(); setShowAssign(true); }}>
                <Ionicons name="swap-horizontal" size={14} color="#C9A962" />
                <Text style={[s.actionBtnText, { color: '#C9A962' }]}>
                  {num.assigned_to ? 'Reassign' : 'Assign'}
                </Text>
              </TouchableOpacity>
              <TouchableOpacity style={[s.actionBtn, { borderColor: '#FF3B3040' }]} onPress={() => releaseNumber(num.sid, num.phone_number)}>
                <Ionicons name="trash" size={14} color="#FF3B30" />
                <Text style={[s.actionBtnText, { color: '#FF3B30' }]}>Release</Text>
              </TouchableOpacity>
            </View>
          </View>
        ))}

        {numbers.length === 0 && (
          <View style={{ alignItems: 'center', paddingTop: 60 }}>
            <Ionicons name="phone-portrait" size={56} color={colors.textSecondary} />
            <Text style={{ fontSize: 18, fontWeight: '700', color: colors.text, marginTop: 16 }}>No numbers yet</Text>
            <Text style={{ fontSize: 14, color: colors.textSecondary, marginTop: 8 }}>Tap "Buy" to purchase your first dedicated number.</Text>
          </View>
        )}
      </ScrollView>

      {/* Purchase Modal */}
      <Modal visible={showPurchase} animationType="slide" presentationStyle="pageSheet" onRequestClose={() => setShowPurchase(false)}>
        <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }}>
          <View style={s.modalHeader}>
            <TouchableOpacity onPress={() => setShowPurchase(false)}>
              <Text style={{ fontSize: 17, color: '#FF3B30' }}>Cancel</Text>
            </TouchableOpacity>
            <Text style={{ fontSize: 17, fontWeight: '700', color: colors.text }}>Buy a Number</Text>
            <View style={{ width: 60 }} />
          </View>
          <ScrollView contentContainerStyle={{ padding: 20 }}>
            <Text style={{ fontSize: 14, color: colors.textSecondary, marginBottom: 16, lineHeight: 20 }}>
              Numbers are $1.15/month each. Pick who gets it, enter an area code, then tap Buy. Texting and calling are wired automatically.
            </Text>
            <Text style={{ fontSize: 12, fontWeight: '700', letterSpacing: 0.8, color: colors.textSecondary, marginBottom: 8 }}>ASSIGN TO</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 16 }} contentContainerStyle={{ gap: 8 }}>
              {[{ _id: null, name: 'Number pool' }, ...users.filter(u => u.role !== 'super_admin' || users.length < 3)].map(u => {
                const on = (buyFor?._id || null) === u._id;
                return (
                  <TouchableOpacity key={u._id || 'pool'} onPress={() => setBuyFor(u._id ? u : null)}
                    style={{ paddingHorizontal: 14, paddingVertical: 9, borderRadius: 20, backgroundColor: on ? '#C9A962' : colors.card, borderWidth: 1, borderColor: on ? '#C9A962' : colors.border }}
                    data-testid={`buy-assign-${u._id || 'pool'}`}>
                    <Text style={{ fontSize: 13, fontWeight: '700', color: on ? '#000' : colors.text }}>{u.name}</Text>
                  </TouchableOpacity>
                );
              })}
            </ScrollView>
            <View style={{ flexDirection: 'row', gap: 10, marginBottom: 16 }}>
              <TextInput
                style={{ flex: 1, backgroundColor: colors.card, borderRadius: 12, padding: 14, fontSize: 20, color: colors.text, borderWidth: 1, borderColor: colors.border, fontFamily: 'monospace' }}
                value={areaCode}
                onChangeText={v => setAreaCode(v.replace(/\D/g, '').slice(0, 3))}
                placeholder="435"
                placeholderTextColor={colors.textSecondary}
                keyboardType="number-pad"
                maxLength={3}
              />
              <TouchableOpacity
                style={{ backgroundColor: '#C9A962', borderRadius: 12, paddingHorizontal: 20, justifyContent: 'center', opacity: searching ? 0.7 : 1 }}
                onPress={searchNumbers} disabled={searching}
              >
                {searching ? <ActivityIndicator size="small" color="#000" /> : <Text style={{ fontSize: 15, fontWeight: '700', color: '#000' }}>Search</Text>}
              </TouchableOpacity>
            </View>

            {available.map(n => (
              <View key={n.phone_number} style={{ backgroundColor: colors.card, borderRadius: 14, padding: 14, marginBottom: 8, flexDirection: 'row', alignItems: 'center', gap: 12, borderWidth: 1, borderColor: colors.border }}>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 18, fontWeight: '700', color: colors.text, fontFamily: 'monospace' }}>{n.phone_number}</Text>
                  <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 2 }}>{n.locality}, {n.region} — SMS + MMS</Text>
                </View>
                <Text style={{ fontSize: 13, color: '#34C759', fontWeight: '600' }}>$1.15/mo</Text>
                <TouchableOpacity
                  style={{ backgroundColor: '#C9A962', borderRadius: 10, paddingHorizontal: 14, paddingVertical: 9, opacity: purchasing === n.phone_number ? 0.6 : 1 }}
                  onPress={() => purchaseNumber(n.phone_number)}
                  disabled={purchasing !== null}
                >
                  {purchasing === n.phone_number
                    ? <ActivityIndicator size="small" color="#000" />
                    : <Text style={{ fontSize: 13, fontWeight: '700', color: '#000' }}>{buyFor ? 'Buy & assign' : 'Buy'}</Text>
                  }
                </TouchableOpacity>
              </View>
            ))}
          </ScrollView>
        </SafeAreaView>
      </Modal>

      {/* Assign Modal */}
      <Modal visible={showAssign} animationType="slide" presentationStyle="pageSheet" onRequestClose={() => setShowAssign(false)}>
        <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }}>
          <View style={s.modalHeader}>
            <TouchableOpacity onPress={() => setShowAssign(false)}>
              <Text style={{ fontSize: 17, color: '#FF3B30' }}>Cancel</Text>
            </TouchableOpacity>
            <Text style={{ fontSize: 17, fontWeight: '700', color: colors.text }}>Assign {assignTarget?.phone_number}</Text>
            <View style={{ width: 60 }} />
          </View>
          <ScrollView contentContainerStyle={{ padding: 16 }}>
            <TouchableOpacity style={[s.card, { borderColor: '#FF950040', marginBottom: 8 }]} onPress={() => assignTarget && assignNumber(assignTarget.sid, null)}>
              <Text style={{ fontSize: 15, fontWeight: '600', color: '#FF9500' }}>Move to Pool (unassign)</Text>
              <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 4 }}>Number stays active, store VA handles inbound</Text>
            </TouchableOpacity>
            {users.filter(u => u.role !== 'super_admin' || users.length < 3).map(u => (
              <TouchableOpacity key={u._id} style={[s.card, { flexDirection: 'row', alignItems: 'center', gap: 12 }]}
                onPress={() => assignTarget && assignNumber(assignTarget.sid, u._id)}>
                <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: '#C9A96220', alignItems: 'center', justifyContent: 'center' }}>
                  <Ionicons name="person" size={18} color="#C9A962" />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 15, fontWeight: '600', color: colors.text }}>{u.name}</Text>
                  <Text style={{ fontSize: 13, color: colors.textSecondary }}>{u.email} — {u.role}</Text>
                </View>
                {assignTarget?.assigned_to?.user_id === u._id && (
                  <Ionicons name="checkmark-circle" size={20} color="#34C759" />
                )}
              </TouchableOpacity>
            ))}
          </ScrollView>
        </SafeAreaView>
      </Modal>
    </SafeAreaView>
  );
}

function StatBox({ label, value, color }: any) {
  const { colors } = useThemeStore();
  return (
    <View style={{ flex: 1, alignItems: 'center', backgroundColor: colors.card, borderRadius: 12, padding: 12, marginHorizontal: 3 }}>
      <Text style={{ fontSize: 20, fontWeight: '800', color }}>{value}</Text>
      <Text style={{ fontSize: 10, color: colors.textSecondary, marginTop: 2, textAlign: 'center' }}>{label}</Text>
    </View>
  );
}

function StatChip({ icon, value, color }: any) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
      <Ionicons name={icon as any} size={12} color={color} />
      <Text style={{ fontSize: 12, color }}>{value}</Text>
    </View>
  );
}

const getS = (colors: any) => StyleSheet.create({
  container:    { flex: 1, backgroundColor: colors.bg },
  header:       { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.border },
  backBtn:      { width: 36, height: 36, borderRadius: 18, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center' },
  headerTitle:  { fontSize: 18, fontWeight: '700', color: colors.text },
  buyBtn:       { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#C9A962', borderRadius: 20, paddingHorizontal: 14, paddingVertical: 8 },
  buyBtnText:   { fontSize: 14, fontWeight: '700', color: '#000' },
  statsRow:     { flexDirection: 'row', marginBottom: 16 },
  card:         { backgroundColor: colors.card, borderRadius: 16, padding: 14, marginBottom: 12, borderWidth: 1, borderColor: colors.border },
  cardRow:      { flexDirection: 'row', alignItems: 'flex-start', marginBottom: 8 },
  cardNumber:   { fontSize: 18, fontWeight: '700', color: colors.text },
  cardSub:      { fontSize: 13, color: colors.textSecondary, fontFamily: 'monospace', marginTop: 2 },
  statusBadge:  { borderRadius: 8, paddingHorizontal: 8, paddingVertical: 4 },
  assignedRow:  { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8 },
  assignedText: { fontSize: 14, color: colors.text, fontWeight: '500' },
  statsLine:    { flexDirection: 'row', gap: 14, marginBottom: 8 },
  webhookRow:   { flexDirection: 'row', alignItems: 'center', gap: 6, borderRadius: 8, padding: 8, marginBottom: 8 },
  actionRow:    { flexDirection: 'row', gap: 8 },
  actionBtn:    { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: colors.bg, borderRadius: 10, paddingVertical: 9, borderWidth: 1, borderColor: '#C9A96240' },
  actionBtnText:{ fontSize: 13, fontWeight: '600' },
  modalHeader:  { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 16, borderBottomWidth: 1, borderBottomColor: colors.border },
});
