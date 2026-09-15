import React, { useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { showConfirm } from '../../services/alert';
import { useToast } from '../common/Toast';
import { GOLD, GREEN, RED, AMBER, tid, type Client } from './shared';
import { NumberBundleRow } from './NumberBundleRow';

const KIND_NOTE: Record<string, string> = {
  NL: 'Dutch mobile-range number (+31 97): no address paperwork, bought in seconds.',
  BE: 'Belgian mobile number. Twilio sells it only against a regulatory bundle (one per country, set below).',
  GB: 'UK mobile number (+44 7). Twilio sells it only against a regulatory bundle (one per country, set below).',
  IE: 'Irish mobile number (+353 8). Twilio sells it only against a regulatory bundle (one per country, set below).',
};
const BUNDLE_COUNTRIES = ['GB', 'IE', 'BE'];

// Non-US clients get their own in-country shop number (bought automatically at kickoff). This card shows it, buys one now, or releases it.
export const ClientNumberCard = ({ client, colors, onChanged }: { client: Client; colors: any; onChanged: () => void }) => {
  const { showToast } = useToast();
  const [busy, setBusy] = useState(false);
  const st = client.number_state;
  if (!st || client.country === 'US' || !client.country) return null;
  const own = st.own;
  const tone = own ? GREEN : st.error ? RED : AMBER;

  const buy = () => showConfirm('Buy a local shop number?', `${KIND_NOTE[client.country!] || 'A local number in the client\'s country.'} Around $3 a month on the Twilio bill, released when you delete the client.`, async () => {
    setBusy(true);
    try { await api.post(`/shop-clients/${client.id}/number/buy-local`); showToast('Number bought, shops call from it now', 'success'); onChanged(); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Twilio would not sell a number', 'error'); onChanged(); }
    finally { setBusy(false); }
  }, undefined, 'Buy');
  const release = () => showConfirm('Release this number?', 'Shops go back to the platform number. The number returns to Twilio and stops billing.', async () => {
    setBusy(true);
    try { await api.delete(`/shop-clients/${client.id}/number`); showToast('Released', 'success'); onChanged(); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Could not release', 'error'); }
    finally { setBusy(false); }
  }, undefined, 'Release');

  return (
    <View style={{ backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: tone + '66', padding: 12, gap: 8 }} {...tid('client-number-card')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
        <Ionicons name={own ? 'call' : 'call-outline'} size={18} color={tone} />
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 14, fontWeight: '800', color: colors.text }} {...tid('client-number-title')}>{own ? `Shops call from ${client.from_number}` : client.from_number ? `Shops call from ${client.from_number}` : `No ${client.locale_label || client.country} number yet`}</Text>
          <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 16 }} {...tid('client-number-status')}>
            {own ? `Their own ${client.locale_label} number, so reps see a local caller id. Bought automatically at kickoff or by you.` : st.error ? `Last attempt failed: ${st.error}` : `Bought automatically when the ${client.industry && client.industry !== 'automotive' ? 'account' : 'store'} finishes the setup form, or buy it now. Until then shops use the US platform number.`}
          </Text>
        </View>
      </View>
      <Text style={{ fontSize: 11.5, color: colors.textSecondary }}>{KIND_NOTE[client.country!] || ''}</Text>
      {BUNDLE_COUNTRIES.includes(client.country!) && <NumberBundleRow country={client.country!} colors={colors} onSaved={onChanged} />}
      <View style={{ flexDirection: 'row', gap: 8 }}>
        {!own && (
          <TouchableOpacity onPress={buy} disabled={busy} style={{ flex: 1, height: 36, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6, opacity: busy ? 0.6 : 1 }} {...tid('client-number-buy')}>
            {busy ? <ActivityIndicator color="#111" size="small" /> : <Ionicons name="cart-outline" size={14} color="#111" />}<Text style={{ fontSize: 13, fontWeight: '800', color: '#111' }}>{st.error ? 'Try again' : 'Buy local number now'}</Text>
          </TouchableOpacity>
        )}
        {own && (
          <TouchableOpacity onPress={release} disabled={busy} style={{ flex: 1, height: 36, borderRadius: 12, borderWidth: 1, borderColor: RED, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 }} {...tid('client-number-release')}>
            <Ionicons name="trash-outline" size={14} color={RED} /><Text style={{ fontSize: 13, fontWeight: '800', color: RED }}>Release number</Text>
          </TouchableOpacity>
        )}
      </View>
    </View>
  );
};
