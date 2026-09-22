import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';
import { showConfirm, showSimpleAlert } from '../../services/alert';
import { useThemeStore } from '../../store/themeStore';
import { GOLD, tid, tint } from '../ui/tokens';
import { STAGE_LABEL, WAITING } from './shared';

/** On the admin user page: "Follow Jessi's onboarding" when it exists, "Start Jessi onboarding by text" when it does not. */
export const UserJessiRow = ({ userId, userName, phone }: { userId: string; userName: string; phone?: string }) => {
  const router = useRouter();
  const { colors } = useThemeStore();
  const [state, setState] = useState<{ exists: boolean; stage?: string; waiting?: string; available: boolean } | null>(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      const cfg = await api.get('/admin/onboarding-jessi/config');
      try { const d = await api.get(`/admin/onboarding-jessi/${userId}`); setState({ exists: true, stage: d.data.state, waiting: d.data.waiting_on, available: !!cfg.data.available && !!cfg.data.sender }); }
      catch { setState({ exists: false, available: !!cfg.data.available && !!cfg.data.sender }); }
    } catch { setState(null); }
  };
  useEffect(() => { load(); }, [userId]);
  if (!state || (!state.exists && !state.available)) return null;

  const start = () => showConfirm('Let Jessi onboard them?', `Jessi texts ${userName}${phone ? ` at ${phone}` : ''}: intro, her contact card, the setup call, photo, then the activation link.`, async () => {
    setBusy(true);
    try { await api.post(`/admin/onboarding-jessi/${userId}/start`); await load(); router.push(`/admin/onboarding-jessi/${userId}` as any); }
    catch (e: any) { showSimpleAlert('Could not start', e?.response?.data?.detail || 'Try again in a minute'); }
    finally { setBusy(false); }
  }, undefined, 'Start');

  const w = state.exists ? WAITING[state.waiting || 'them'] : null;
  return (
    <TouchableOpacity onPress={state.exists ? () => router.push(`/admin/onboarding-jessi/${userId}` as any) : start} disabled={busy}
      style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 8, padding: 14, borderRadius: 12, borderWidth: 1, borderColor: tint(GOLD, 0.45), backgroundColor: tint(GOLD, 0.08) }}
      {...tid(state.exists ? 'user-jessi-onboarding-open' : 'user-jessi-onboarding-start')}>
      {busy ? <ActivityIndicator size="small" color={GOLD} /> : <Ionicons name="chatbubbles-outline" size={20} color={GOLD} />}
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 15, fontWeight: '700', color: GOLD }}>{state.exists ? "Follow Jessi's onboarding" : 'Start Jessi onboarding by text'}</Text>
        {state.exists && <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 1 }}>{STAGE_LABEL[state.stage || ''] || state.stage} · {w?.label}</Text>}
      </View>
      <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />
    </TouchableOpacity>
  );
};
