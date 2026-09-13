import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { showConfirm } from '../../services/alert';
import { useToast } from '../common/Toast';
import { Sheet, Field, Label, Chip, GoldButton, fmtPhone, GOLD, GREEN, RED, tid } from './shared';

export type OwnedNumber = { phone: string; sid: string; friendly_name: string; voice: boolean; use: string };
export type NumberState = { current: string; source: 'saved' | 'platform' | 'none'; owned: OwnedNumber[]; twilio_error?: string | null; clients_with_own_number: { id: string; name: string; from_number: string }[] };
type Found = { phone: string; locality: string; region: string; monthly_cost_usd: number };
const place = (f: Found) => { const city = (f.locality || '').toLowerCase().replace(/\b\w/g, ch => ch.toUpperCase()); const st = f.region && f.region.length === 2 && f.region !== 'US' ? f.region : ''; return [city, st].filter(Boolean).join(', ') || 'US'; };

// Pick one of your Twilio numbers, or buy a new one, as the number every shop call and scorecard text comes from.
export const ShopNumberSheet = ({ visible, onClose, colors, onChanged }: { visible: boolean; onClose: () => void; colors: any; onChanged: (s: NumberState) => void }) => {
  const { showToast } = useToast();
  const [state, setState] = useState<NumberState | null>(null);
  const [mode, setMode] = useState<'pick' | 'buy'>('pick');
  const [area, setArea] = useState('');
  const [found, setFound] = useState<Found[] | null>(null);
  const [busy, setBusy] = useState('');
  const load = () => api.get('/shop-clients/number').then(r => setState(r.data)).catch(() => setState({ current: '', source: 'none', owned: [], twilio_error: 'Could not load numbers', clients_with_own_number: [] }));
  useEffect(() => { if (visible) { setState(null); setMode('pick'); setFound(null); setArea(''); load(); } }, [visible]);

  const apply = (s: NumberState, msg: string) => { setState(s); onChanged(s); showToast(msg, 'success'); };
  const pick = (n: OwnedNumber) => {
    if (n.use === 'Main Mystery Shop number') return;
    const go = async () => { setBusy(n.phone); try { const r = await api.put('/shop-clients/number', { phone_number: n.phone }); apply(r.data, `Shop calls now come from ${fmtPhone(n.phone)}`); } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not save', 'error'); } finally { setBusy(''); } };
    if (n.use === 'Not in use') return go();
    showConfirm('Use this number for shops?', `${fmtPhone(n.phone)} is ${n.use}. Whoever calls it back gets a voicemail instead of a person while it is the shop number.`, go, undefined, 'Use it');
  };
  const search = async () => { setBusy('search'); setFound(null); try { const r = await api.get('/shop-clients/number/search', { params: { area_code: area } }); setFound(r.data.numbers); } catch (e: any) { showToast(e?.response?.data?.detail || 'Search failed', 'error'); setFound([]); } finally { setBusy(''); } };
  const buy = (f: Found) => showConfirm('Buy this number?', `${fmtPhone(f.phone)} (${place(f)}) is $${f.monthly_cost_usd.toFixed(2)}/month on your Twilio bill. It becomes the main Mystery Shop number right away.`, async () => {
    setBusy(f.phone);
    try { const r = await api.post('/shop-clients/number/buy', { phone_number: f.phone }); apply(r.data, `Bought ${fmtPhone(f.phone)}. Shops call from it now.`); setMode('pick'); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Could not buy it', 'error'); }
    finally { setBusy(''); }
  }, undefined, 'Buy it');
  const reset = () => showConfirm('Go back to the platform number?', 'Shop calls will come from the shared platform number again.', async () => { const r = await api.delete('/shop-clients/number'); apply(r.data, 'Back to the platform number'); }, undefined, 'Reset');

  return (
    <Sheet visible={visible} onClose={onClose} title="Mystery Shop number" colors={colors} testID="shop-number-sheet">
      {!state ? <ActivityIndicator color={GOLD} /> : (
        <>
          <View style={{ backgroundColor: colors.card, borderRadius: 16, padding: 14, borderWidth: 1, borderColor: state.source === 'saved' ? GREEN + '88' : colors.border, gap: 4 }} {...tid('shop-number-current')}>
            <Label t="EVERY SHOP CALL AND SCORECARD TEXT COMES FROM" colors={colors} />
            <Text style={{ fontSize: 24, fontWeight: '800', color: colors.text }}>{state.current ? fmtPhone(state.current) : 'No number yet'}</Text>
            <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>{state.source === 'saved' ? 'Your saved Mystery Shop number. Reps who save this contact will see it on every shop.' : state.source === 'platform' ? 'The shared platform number. Pick or buy one below to make it your own.' : 'Pick or buy a number below.'}</Text>
            {state.source === 'saved' && <TouchableOpacity onPress={reset} {...tid('shop-number-reset')}><Text style={{ fontSize: 12.5, fontWeight: '800', color: RED }}>Back to the platform number</Text></TouchableOpacity>}
          </View>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <Chip label="Pick one of mine" active={mode === 'pick'} onPress={() => setMode('pick')} colors={colors} testID="shop-number-mode-pick" />
            <Chip label="Buy a new one" active={mode === 'buy'} onPress={() => setMode('buy')} colors={colors} testID="shop-number-mode-buy" />
          </View>
          {mode === 'pick' && (
            <View style={{ gap: 8 }}>
              <Label t={`NUMBERS ON YOUR TWILIO ACCOUNT · ${state.owned.length}`} colors={colors} />
              {!!state.twilio_error && <Text style={{ fontSize: 13, color: RED }} {...tid('shop-number-error')}>{state.twilio_error}</Text>}
              {state.owned.map(n => {
                const on = n.use === 'Main Mystery Shop number';
                return (
                  <TouchableOpacity key={n.sid} onPress={() => pick(n)} disabled={on || !n.voice || !!busy} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: on ? GREEN : colors.border, padding: 12, opacity: n.voice ? 1 : 0.5 }} {...tid(`shop-number-pick-${n.phone.replace(/\D/g, '')}`)}>
                    <Ionicons name={on ? 'checkmark-circle' : 'call-outline'} size={22} color={on ? GREEN : n.use === 'Not in use' ? GOLD : colors.textSecondary} />
                    <View style={{ flex: 1 }}>
                      <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>{fmtPhone(n.phone)}</Text>
                      <Text style={{ fontSize: 12, color: on ? GREEN : colors.textSecondary }}>{n.voice ? n.use : 'No voice on this number'}{n.friendly_name && !n.friendly_name.replace(/\D/g, '').includes(n.phone.replace(/\D/g, '').slice(-10)) && !on ? ` · ${n.friendly_name}` : ''}</Text>
                    </View>
                    {busy === n.phone ? <ActivityIndicator color={GOLD} /> : !on && n.voice && <Text style={{ fontSize: 12.5, fontWeight: '800', color: GOLD }}>Use</Text>}
                  </TouchableOpacity>
                );
              })}
              {state.owned.length === 0 && !state.twilio_error && <Text style={{ fontSize: 13, color: colors.textSecondary }}>No numbers on the account yet. Buy one.</Text>}
            </View>
          )}
          {mode === 'buy' && (
            <View style={{ gap: 10 }}>
              <View style={{ flexDirection: 'row', gap: 8, alignItems: 'flex-end' }}>
                <View style={{ flex: 1 }}><Field label="AREA CODE" value={area} onChange={(v: string) => setArea(v.replace(/\D/g, '').slice(0, 3))} colors={colors} placeholder="801" keyboardType="number-pad" testID="shop-number-area" /></View>
                <View style={{ width: 120 }}><GoldButton label="Search" onPress={search} busy={busy === 'search'} disabled={area.length !== 3} testID="shop-number-search" icon="search" /></View>
              </View>
              <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }}>A local number reps will not recognize is best. It costs about $1.15/month plus call minutes, billed to your Twilio account, and becomes the main shop number the moment you buy it.</Text>
              {found && found.length === 0 && <Text style={{ fontSize: 13, color: colors.textSecondary }} {...tid('shop-number-none')}>Nothing in that area code right now. Try a nearby one.</Text>}
              {(found || []).map(f => (
                <View key={f.phone} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: colors.border, padding: 12 }} {...tid(`shop-number-result-${f.phone.replace(/\D/g, '')}`)}>
                  <View style={{ flex: 1 }}>
                    <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>{fmtPhone(f.phone)}</Text>
                    <Text style={{ fontSize: 12, color: colors.textSecondary }}>{place(f)} · ${f.monthly_cost_usd.toFixed(2)}/mo</Text>
                  </View>
                  <TouchableOpacity onPress={() => buy(f)} disabled={!!busy} style={{ paddingHorizontal: 14, height: 34, borderRadius: 17, backgroundColor: GOLD, justifyContent: 'center' }} {...tid(`shop-number-buy-${f.phone.replace(/\D/g, '')}`)}>
                    {busy === f.phone ? <ActivityIndicator color="#111" /> : <Text style={{ fontSize: 13, fontWeight: '800', color: '#111' }}>Buy</Text>}
                  </TouchableOpacity>
                </View>
              ))}
            </View>
          )}
          {state.clients_with_own_number.length > 0 && <Text style={{ fontSize: 12, color: colors.textSecondary }}>{state.clients_with_own_number.map(c => c.name).join(', ')} {state.clients_with_own_number.length === 1 ? 'has' : 'have'} their own number set on the client and will keep using it.</Text>}
        </>
      )}
    </Sheet>
  );
};
