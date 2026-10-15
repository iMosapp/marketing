import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, AppState, Platform, Text, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { router, useSegments } from 'expo-router';
import api from '../../services/api';
import { useAuthStore } from '../../store/authStore';
import { useCompliance } from '../../store/complianceStore';
import { useThemeStore } from '../../store/themeStore';
import { GOLD, RADIUS, SPACE, TYPE, tid, tint } from '../ui/tokens';

/** Keeps the subscription lock in sync: on sign-in, when the app returns to the foreground, and from any 403 billing_locked (api.ts). */
export function useBillingAccess() {
  const userId = useAuthStore(s => s.user?._id);
  const signInLock = useAuthStore(s => (s.user as any)?.billing_lock);
  const setLock = useCompliance(s => s.setLock);
  // The sign-in response already carries the lock (owner flag included): show the right screen at once, /billing/access then refreshes it
  useEffect(() => { if (signInLock?.locked) setLock(signInLock); }, [userId]); // eslint-disable-line react-hooks/exhaustive-deps
  const check = useCallback(async () => {
    if (!userId) { setLock(null); return; }
    try {
      const st = (await api.get('/billing/access')).data;
      setLock(st?.locked ? st : null);
    } catch { /* keep the last known state */ }
  }, [userId, setLock]);
  useEffect(() => { check(); }, [check]);
  useEffect(() => {
    const sub = AppState.addEventListener('change', s => { if (s === 'active') check(); });
    return () => sub.remove();
  }, [check]);
  return check;
}

/** Full-screen "Access paused" for a locked organization. Owners can still reach Billing; everyone else can only sign out. */
export function AccessPausedGate() {
  const { colors } = useThemeStore();
  const user = useAuthStore(s => s.user);
  const impersonating = useAuthStore(s => s.isImpersonating);
  const logout = useAuthStore(s => s.logout);
  const lock = useCompliance(s => s.lock);
  const segments = useSegments() as string[];
  const recheck = useBillingAccess();
  const [busy, setBusy] = useState(false);
  if (!lock?.locked || !user?._id || user.role === 'super_admin' || impersonating) return null;
  const onBilling = segments[0] === 'settings' && segments[1] === 'billing';
  if (lock.owner && onBilling) return null;
  const again = async () => { setBusy(true); await recheck(); setBusy(false); };

  return (
    <View style={{ position: Platform.OS === 'web' ? ('fixed' as any) : 'absolute', top: 0, left: 0, right: 0, bottom: 0, zIndex: 9999, backgroundColor: colors.bg, alignItems: 'center', justifyContent: 'center', padding: SPACE.xl }} {...tid('access-paused-screen')}>
      <View style={{ width: '100%', maxWidth: 460, gap: SPACE.lg, alignItems: 'center' }}>
        <View style={{ width: 72, height: 72, borderRadius: 36, alignItems: 'center', justifyContent: 'center', backgroundColor: tint(GOLD, 0.15) }}>
          <Ionicons name="pause-circle" size={40} color={GOLD} />
        </View>
        <Text style={{ fontSize: 26, fontWeight: '800', color: colors.text, textAlign: 'center' }} {...tid('access-paused-title')}>Access paused</Text>
        <Text style={{ fontSize: TYPE.body, color: colors.textSecondary, textAlign: 'center', lineHeight: 22 }} {...tid('access-paused-message')}>
          {lock.message || 'Access to your organization\'s account is paused.'}
        </Text>
        {lock.owner && lock.reason_text ? <Text style={{ fontSize: TYPE.sub, color: colors.textTertiary, textAlign: 'center' }} {...tid('access-paused-reason')}>{lock.reason_text}</Text> : null}
        {lock.owner ? (
          <TouchableOpacity onPress={() => router.push('/settings/billing' as any)} {...tid('access-paused-restore-billing')}
            style={{ width: '100%', flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: GOLD, borderRadius: RADIUS.md, paddingVertical: 15 }}>
            <Ionicons name="card" size={18} color="#111" />
            <Text style={{ fontSize: TYPE.body, fontWeight: '800', color: '#111' }}>Restore billing</Text>
          </TouchableOpacity>
        ) : null}
        <TouchableOpacity onPress={again} disabled={busy} {...tid('access-paused-check-again')} style={{ paddingVertical: 10 }}>
          {busy ? <ActivityIndicator color={GOLD} /> : <Text style={{ fontSize: TYPE.body, fontWeight: '700', color: GOLD }}>Check again</Text>}
        </TouchableOpacity>
        <TouchableOpacity onPress={() => logout()} {...tid('access-paused-sign-out')} style={{ paddingVertical: 6 }}>
          <Text style={{ fontSize: TYPE.body, fontWeight: '600', color: colors.textSecondary }}>Sign out</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}
