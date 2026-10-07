import React, { useEffect, useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, FlatList, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import api, { contactsAPI } from '../../services/api';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { useToast } from '../../components/common/Toast';
import { ScreenHeader } from '../../components/common/ScreenHeader';
import { GOLD, tid, errText } from '../../components/inbox/ownership';
import { useContactSearch } from '../../hooks/useContactSearch';

// Step 1: whose trade is this? Pick an existing contact or create one through the normal new-contact flow (it comes back here).
export default function NewAppraisal() {
  const router = useRouter();
  const { contact_id, vehicle_id } = useLocalSearchParams<{ contact_id?: string; vehicle_id?: string }>();
  const user = useAuthStore(s => s.user);
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [q, setQ] = useState('');
  const [contacts, setContacts] = useState<any[]>([]);
  const [creating, setCreating] = useState<string | null>(null);
  useContactSearch(user?._id, q, setContacts);
  useEffect(() => { if (user?._id) contactsAPI.getAll(user._id).then((d: any) => setContacts(Array.isArray(d) ? d : d?.contacts || [])).catch(() => {}); }, [user?._id]);

  const start = async (cid: string, vid?: string) => {
    setCreating(cid);
    try {
      const r = (await api.post('/appraisals', { contact_id: cid, mode: 'vehicle_here', vehicle_id: vid || undefined })).data;
      router.replace(`/appraisal/${r.appraisal.id}` as any);
    } catch (e: any) {
      if (e?.response?.status === 403) { showToast(e.response.data?.detail || 'Not switched on for you', 'error', 5000); router.replace('/appraisals' as any); return; }
      showToast(errText(e, 'Could not start the appraisal'), 'error');
    } finally { setCreating(null); }
  };
  useEffect(() => { if (typeof contact_id === 'string' && contact_id) start(contact_id, typeof vehicle_id === 'string' ? vehicle_id : undefined); }, [contact_id]);

  const name = (c: any) => c.name || `${c.first_name || ''} ${c.last_name || ''}`.trim() || c.phone || 'Contact';
  const shown = q.trim().length >= 2 ? contacts.filter(c => `${name(c)} ${c.phone || ''} ${c.email || ''}`.toLowerCase().includes(q.trim().toLowerCase())) : contacts;
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']} {...tid('appraisal-new')}>
      <ScreenHeader title="Whose trade?" subtitle="Pick the customer or add a new one" />
      <View style={{ padding: 16, gap: 12 }}>
        <TouchableOpacity onPress={() => router.push('/contact/new?returnTo=appraisal' as any)} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, height: 56, paddingHorizontal: 14, borderRadius: 16, backgroundColor: GOLD }} {...tid('appraisal-new-contact')}>
          <Ionicons name="person-add" size={20} color="#0B0B0D" /><Text style={{ flex: 1, fontSize: 16, fontWeight: '800', color: '#0B0B0D' }}>New customer</Text><Ionicons name="chevron-forward" size={18} color="#0B0B0D" />
        </TouchableOpacity>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, height: 46, borderRadius: 14, paddingHorizontal: 14, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border }}>
          <Ionicons name="search" size={16} color={colors.textSecondary} />
          <TextInput value={q} onChangeText={setQ} placeholder="Search your contacts" placeholderTextColor={colors.textSecondary} style={{ flex: 1, color: colors.text, fontSize: 14 }} autoCorrect={false} autoFocus {...tid('appraisal-contact-search')} />
        </View>
      </View>
      <FlatList data={shown} keyExtractor={(c) => String(c._id || c.id)} contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 40 }} keyboardShouldPersistTaps="handled"
        ListEmptyComponent={<Text style={{ textAlign: 'center', color: colors.textSecondary, paddingVertical: 24 }} {...tid('appraisal-contacts-empty')}>No contacts match.</Text>}
        renderItem={({ item: c }) => { const cid = String(c._id || c.id); return (
          <TouchableOpacity onPress={() => start(cid)} disabled={!!creating} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.border }} {...tid(`appraisal-pick-${cid}`)}>
            <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: GOLD + '1F', alignItems: 'center', justifyContent: 'center' }}><Text style={{ fontSize: 15, fontWeight: '800', color: GOLD }}>{name(c)[0]?.toUpperCase()}</Text></View>
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text }}>{name(c)}</Text>
              <Text style={{ fontSize: 12, color: colors.textSecondary }}>{[c.phone, c.vehicle].filter(Boolean).join(' · ')}</Text>
            </View>
            {creating === cid ? <ActivityIndicator color={GOLD} /> : <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />}
          </TouchableOpacity>
        ); }} />
    </SafeAreaView>
  );
}
