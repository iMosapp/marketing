// Owner Settings: which internal tools the other super admins can see, and who else counts as an owner. Owner only.
import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, Switch, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useThemeStore } from '../../store/themeStore';
import { useOwnerStore } from '../../store/ownerStore';
import { ScreenHeader } from '../../components/common/ScreenHeader';
import { useToast } from '../../components/common/Toast';
import api from '../../services/api';

const GOLD = '#C9A962';
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });
type Tool = { key: string; title: string; visible: boolean; locked: boolean };
type Admin = { user_id: string; name: string; email: string; is_owner: boolean; me: boolean };

export default function OwnerSettingsScreen() {
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [tools, setTools] = useState<Tool[] | null>(null);
  const [admins, setAdmins] = useState<Admin[] | null>(null);
  const [err, setErr] = useState('');

  const load = () => {
    api.get('/owner/visibility').then(r => { if (!r.data.is_owner) { setErr('Owner only.'); return; } setTools(r.data.tools); }).catch(() => setErr('Could not load.'));
    api.get('/owner/owners').then(r => setAdmins(r.data.admins)).catch(() => {});
  };
  useEffect(load, []);

  const flipTool = async (t: Tool, v: boolean) => {
    setTools(ts => (ts || []).map(x => (x.key === t.key ? { ...x, visible: v } : x)));
    try { await api.put('/owner/visibility', { key: t.key, visible: v }); useOwnerStore.getState().reset(); useOwnerStore.getState().load(); }
    catch { showToast('Could not save.', 'error'); load(); }
  };
  const flipOwner = async (a: Admin, v: boolean) => {
    setAdmins(as => (as || []).map(x => (x.user_id === a.user_id ? { ...x, is_owner: v } : x)));
    try { await api.put('/owner/grant', { user_id: a.user_id, is_owner: v }); showToast(v ? `${a.name} is now an owner.` : `${a.name} is a regular super admin again.`, 'success'); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Could not save.', 'error'); load(); }
  };

  const hidden = (tools || []).filter(t => !t.visible).length;
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']} {...tid('owner-settings-screen')}>
      <ScreenHeader title="Owner Settings" subtitle="What other super admins can see" testID="owner-settings-header" />
      {err ? <Text style={{ margin: 20, color: '#FF453A' }} {...tid('owner-settings-error')}>{err}</Text> : !tools ? <ActivityIndicator color={GOLD} style={{ marginTop: 40 }} /> : (
        <ScrollView contentContainerStyle={{ padding: 14, paddingBottom: 60, gap: 14 }}>
          <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>Switch a tool off and it disappears for every super admin except owners. You always see everything. {hidden} tool{hidden === 1 ? '' : 's'} currently hidden.</Text>
          <View style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 14 }} {...tid('owner-tools')}>
            <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 0.6, paddingTop: 12, paddingBottom: 4 }}>OTHER SUPER ADMINS CAN SEE</Text>
            {tools.map((t, i) => (
              <View key={t.key} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10, borderBottomWidth: i === tools.length - 1 ? 0 : 0.5, borderBottomColor: colors.border }} {...tid(`owner-tool-${t.key}`)}>
                <Ionicons name={t.visible ? 'eye-outline' : 'eye-off-outline'} size={16} color={t.visible ? colors.textSecondary : GOLD} />
                <Text style={{ flex: 1, fontSize: 15, color: colors.text }}>{t.title}{t.locked ? '  (always owner-only)' : ''}</Text>
                <Switch value={t.visible} disabled={t.locked} onValueChange={v => flipTool(t, v)} trackColor={{ true: GOLD }} {...tid(`owner-tool-switch-${t.key}`)} />
              </View>
            ))}
          </View>
          {admins && (
            <View style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 14 }} {...tid('owner-admins')}>
              <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 0.6, paddingTop: 12, paddingBottom: 4 }}>OWNERS</Text>
              <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17, paddingBottom: 6 }}>An owner sees everything and can change these settings. Only hand this to someone you trust completely.</Text>
              {admins.map((a, i) => (
                <View key={a.user_id} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10, borderBottomWidth: i === admins.length - 1 ? 0 : 0.5, borderBottomColor: colors.border }} {...tid(`owner-admin-${a.user_id}`)}>
                  <View style={{ flex: 1, minWidth: 0 }}>
                    <Text style={{ fontSize: 15, color: colors.text }} numberOfLines={1}>{a.name}{a.me ? ' (you)' : ''}</Text>
                    <Text style={{ fontSize: 12, color: colors.textTertiary }} numberOfLines={1}>{a.email}</Text>
                  </View>
                  <Switch value={a.is_owner} disabled={a.me} onValueChange={v => flipOwner(a, v)} trackColor={{ true: GOLD }} {...tid(`owner-admin-switch-${a.user_id}`)} />
                </View>
              ))}
            </View>
          )}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}
