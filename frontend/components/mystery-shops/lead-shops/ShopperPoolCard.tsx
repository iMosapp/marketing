import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../../services/api';
import { showConfirm } from '../../../services/alert';
import { useToast } from '../../common/Toast';
import { fmtPhone, fmtDay, GOLD, GREEN, AMBER, BLUE, tid } from '../shared';
import type { Pool } from './shared';

// Numbers the AI shopper answers on during a lead shop. Bought on demand (never more than the cap), rested 14 days between stores.
export const ShopperPoolCard = ({ colors }: { colors: any }) => {
  const { showToast } = useToast();
  const [pool, setPool] = useState<Pool | null>(null);
  const [openList, setOpenList] = useState(false);
  const [busy, setBusy] = useState(false);
  const load = () => api.get('/lead-shops/numbers').then(r => setPool(r.data)).catch(() => setPool(null));
  useEffect(() => { load(); }, []);
  const buy = () => showConfirm('Buy another shopper number?', 'About $1.15 a month on the Twilio bill. Lead shops buy one automatically when none is free, so you only need this to get ahead of a busy week.', async () => {
    setBusy(true);
    try { const r = await api.post('/lead-shops/numbers/buy', {}); setPool(r.data); showToast('Number added to the pool', 'success'); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Twilio would not sell a number', 'error'); }
    finally { setBusy(false); }
  }, undefined, 'Buy');
  if (!pool) return null;
  return (
    <View style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 14, gap: 10 }} {...tid('shopper-pool-card')}>
      <TouchableOpacity onPress={() => setOpenList(v => !v)} activeOpacity={0.85} style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }} {...tid('shopper-pool-toggle')}>
        <View style={{ width: 40, height: 40, borderRadius: 12, backgroundColor: BLUE + '22', alignItems: 'center', justifyContent: 'center' }}><Ionicons name="people-circle-outline" size={22} color={BLUE} /></View>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>Lead shopper numbers</Text>
          <Text style={{ fontSize: 12.5, color: colors.textSecondary }} {...tid('shopper-pool-summary')}>{pool.total === 0 ? 'None yet. The first lead shop buys one on its own.' : `${pool.in_use} in use · ${pool.available} ready · ${pool.total - pool.in_use - pool.available} resting · ${pool.total} of ${pool.cap} owned`}</Text>
        </View>
        <Ionicons name={openList ? 'chevron-up' : 'chevron-down'} size={18} color={colors.textSecondary} />
      </TouchableOpacity>
      {openList && (
        <View style={{ gap: 6 }}>
          {pool.numbers.map(n => { const tone = n.status === 'in_use' ? GREEN : n.cooling ? AMBER : BLUE; return (
            <View key={n.phone} style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }} {...tid(`shopper-number-${n.phone.replace(/\D/g, '')}`)}>
              <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: tone }} />
              <Text style={{ flex: 1, fontSize: 13.5, fontWeight: '700', color: colors.text }}>{fmtPhone(n.phone)}</Text>
              <Text style={{ fontSize: 12, color: colors.textSecondary }}>{n.status === 'in_use' ? 'on a lead shop' : n.cooling ? `resting until ${fmtDay(n.cooldown_until)}` : 'ready'}</Text>
            </View>
          ); })}
          {pool.total < pool.cap && (
            <TouchableOpacity onPress={buy} disabled={busy} style={{ height: 36, borderRadius: 12, borderWidth: 1, borderColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6, marginTop: 4, opacity: busy ? 0.6 : 1 }} {...tid('shopper-pool-buy')}>
              {busy ? <ActivityIndicator size="small" color={GOLD} /> : <Ionicons name="cart-outline" size={14} color={GOLD} />}<Text style={{ fontSize: 13, fontWeight: '800', color: GOLD }}>Buy another number</Text>
            </TouchableOpacity>
          )}
        </View>
      )}
    </View>
  );
};
