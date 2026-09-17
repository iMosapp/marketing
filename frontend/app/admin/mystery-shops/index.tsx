import React, { useCallback, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, RefreshControl } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import api from '../../../services/api';
import { useThemeStore } from '../../../store/themeStore';
import { ScreenHeader, HeaderIconButton } from '../../../components/common/ScreenHeader';
import { ClientSheet } from '../../../components/mystery-shops/ClientSheet';
import { DemoShopSheet } from '../../../components/mystery-shops/DemoShopSheet';
import { ShopNumberSheet, type NumberState } from '../../../components/mystery-shops/ShopNumberSheet';
import { ImportSheet } from '../../../components/mystery-shops/ImportSheet';
import { ShopperPoolCard } from '../../../components/mystery-shops/lead-shops/ShopperPoolCard';
import { Bar, money, scoreColor, fmtPhone, perMonthText, loadIndustries, afterModal, GOLD, GREEN, RED, PURPLE, BLUE, tid, type Client } from '../../../components/mystery-shops/shared';

export default function MysteryShopClients() {
  const router = useRouter();
  const { colors } = useThemeStore();
  const [clients, setClients] = useState<Client[] | null>(null);
  const [defaultFrom, setDefaultFrom] = useState('');
  const [numberSaved, setNumberSaved] = useState<boolean | null>(null);
  const [sheet, setSheet] = useState(false);
  const [demo, setDemo] = useState(false);
  const [numberSheet, setNumberSheet] = useState(false);
  const [importSheet, setImportSheet] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try { const r = await api.get('/shop-clients'); setClients(r.data.clients); setDefaultFrom(r.data.from_number_default || ''); } catch { setClients([]); }
    finally { setRefreshing(false); }
    loadIndustries();
    api.get('/shop-clients/number').then(r => setNumberSaved(r.data.source === 'saved')).catch(() => setNumberSaved(false));
  }, []);
  useFocusEffect(useCallback(() => { load(); }, [load]));
  const onNumberChanged = (s: NumberState) => { setDefaultFrom(s.current || ''); setNumberSaved(s.source === 'saved'); };

  const mrr = (clients || []).filter(c => c.active && !c.demo).reduce((s, c) => s + (c.plan.price_monthly || 0), 0);
  const stores = (clients || []).filter(c => !c.demo).length;
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="Mystery Shop Clients" subtitle={clients ? `${stores} account${stores === 1 ? '' : 's'} · ${money(mrr)}/mo` : undefined} testID="shop-clients-header" right={<HeaderIconButton icon="add-circle" onPress={() => setSheet(true)} testID="shop-clients-add" />} />
      {clients === null ? <ActivityIndicator style={{ marginTop: 60 }} color={GOLD} /> : (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60, gap: 12 }} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor={GOLD} />}>
          <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>Businesses that pay you to shop their people. Jessi calls, texts or emails their reps as a practice shop, or drops a covert internet lead into their CRM (Lead Shops) and grades how the whole store responds. Every shop is graded, and the account gets a live report link plus a monthly PDF. Works for any industry: dealerships, brokerages, home services, practices and more.</Text>
          <TouchableOpacity onPress={() => setDemo(true)} activeOpacity={0.85} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: GOLD, borderRadius: 16, padding: 14 }} {...tid('shop-demo')}>
            <View style={{ width: 40, height: 40, borderRadius: 12, backgroundColor: '#11111122', alignItems: 'center', justifyContent: 'center' }}><Ionicons name="call" size={20} color="#111" /></View>
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 15.5, fontWeight: '800', color: '#111' }}>Shop anyone right now</Text>
              <Text style={{ fontSize: 12.5, color: '#111111AA' }}>Name, cell, industry, department. No account needed. It dials, grades, and texts them their scorecard.</Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color="#111" />
          </TouchableOpacity>
          <TouchableOpacity onPress={() => router.push('/admin/mystery-shops/library' as any)} activeOpacity={0.85} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: colors.card, borderRadius: 16, padding: 14, borderWidth: 1, borderColor: colors.border }} {...tid('shop-library')}>
            <View style={{ width: 40, height: 40, borderRadius: 12, backgroundColor: PURPLE + '22', alignItems: 'center', justifyContent: 'center' }}><Ionicons name="library" size={20} color={PURPLE} /></View>
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>Challenge library</Text>
              <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>Scenarios for every industry you sell to. Describe one and Jessi writes it.</Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
          </TouchableOpacity>
          <TouchableOpacity onPress={() => setNumberSheet(true)} activeOpacity={0.85} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: colors.card, borderRadius: 16, padding: 14, borderWidth: 1, borderColor: numberSaved ? GREEN + '66' : colors.border }} {...tid('shop-number-card')}>
            <View style={{ width: 40, height: 40, borderRadius: 12, backgroundColor: (numberSaved ? GREEN : GOLD) + '22', alignItems: 'center', justifyContent: 'center' }}><Ionicons name="call-outline" size={20} color={numberSaved ? GREEN : GOLD} /></View>
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>{defaultFrom ? `Shops call from ${fmtPhone(defaultFrom)}` : 'Pick the number shops call from'}</Text>
              <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>{numberSaved ? 'Your Mystery Shop number. Tap to change or buy another.' : numberSaved === false ? 'Shared platform number. Pick one of yours or buy a new one.' : 'Checking your Twilio numbers…'}</Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
          </TouchableOpacity>
          <ShopperPoolCard colors={colors} />
          <TouchableOpacity onPress={() => setImportSheet(true)} activeOpacity={0.85} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: colors.card, borderRadius: 16, padding: 14, borderWidth: 1, borderColor: colors.border }} {...tid('shop-import')}>
            <View style={{ width: 40, height: 40, borderRadius: 12, backgroundColor: BLUE + '22', alignItems: 'center', justifyContent: 'center' }}><Ionicons name="cloud-upload-outline" size={20} color={BLUE} /></View>
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>Import dealers from CSV</Text>
              <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>Hundreds at once, any country. Preview first, then each one gets its own proposal and setup link.</Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
          </TouchableOpacity>
          {clients.length === 0 && (
            <TouchableOpacity onPress={() => setSheet(true)} style={{ alignItems: 'center', padding: 30, gap: 10, backgroundColor: colors.card, borderRadius: 18, borderWidth: 1, borderColor: colors.border }} {...tid('shop-clients-empty')}>
              <Ionicons name="storefront" size={36} color={GOLD} />
              <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text }}>Add your first client</Text>
              <Text style={{ fontSize: 13, color: colors.textSecondary, textAlign: 'center' }}>Industry, name, plan, hours, then the people to shop.</Text>
            </TouchableOpacity>
          )}
          {clients.map(c => {
            const done = c.completed || 0; const planned = c.planned || 0;
            const prog = Object.entries(c.progress || {});
            return (
              <TouchableOpacity key={c.id} onPress={() => router.push(`/admin/mystery-shops/${c.id}` as any)} activeOpacity={0.85} style={{ backgroundColor: colors.card, borderRadius: 18, borderWidth: 1, borderColor: colors.border, padding: 14, gap: 10, opacity: c.active ? 1 : 0.6 }} {...tid(`shop-client-${c.id}`)}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
                  <View style={{ width: 44, height: 44, borderRadius: 12, backgroundColor: GOLD + '22', alignItems: 'center', justifyContent: 'center' }}><Ionicons name={c.demo ? 'flash' : 'storefront'} size={20} color={GOLD} /></View>
                  <View style={{ flex: 1 }}>
                    <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text }}>{c.name}{!c.active ? '  · paused' : ''}</Text>
                    <Text style={{ fontSize: 12.5, color: colors.textSecondary }} {...tid(`shop-client-sub-${c.id}`)}>{c.demo ? 'Anyone you shop without a client account' : [c.locale && c.locale !== 'en-US' ? c.locale_label : '', c.industry !== 'automotive' ? c.industry_label : '', c.brand, [c.city, c.state].filter(Boolean).join(', ')].filter(Boolean).join(' · ')}{c.people ? ` · ${c.people} people` : ''}</Text>
                  </View>
                  <View style={{ alignItems: 'flex-end' }}>
                    <Text style={{ fontSize: 18, fontWeight: '800', color: scoreColor(c.avg_score) }}>{c.avg_score != null ? `${c.avg_score}%` : '–'}</Text>
                    <Text style={{ fontSize: 10.5, fontWeight: '700', color: colors.textSecondary }}>AVG THIS MONTH</Text>
                  </View>
                </View>
                {!c.demo && (
                  <>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                      <Bar pct={planned ? (100 * done) / planned : 0} color={GOLD} colors={colors} />
                      <Text style={{ fontSize: 12.5, fontWeight: '700', color: colors.text }}>{done} of {planned} shops</Text>
                    </View>
                    <View style={{ flexDirection: 'row', gap: 12, flexWrap: 'wrap' }} {...tid(`shop-client-progress-${c.id}`)}>
                      {prog.map(([k, p]) => <Text key={k} style={{ fontSize: 12, color: colors.textSecondary }}>{p.label || k} {p.completed}/{p.planned}</Text>)}
                      <Text style={{ fontSize: 12, color: colors.textSecondary }}>{money(c.plan.price_monthly, c.currency)}/mo</Text>
                      {!!c.needs_training && <Text style={{ fontSize: 12, fontWeight: '700', color: RED }}>{c.needs_training} need training</Text>}
                      {c.billing?.status && <Text style={{ fontSize: 12, fontWeight: '700', color: c.billing.status === 'paid' ? GREEN : GOLD }}>{c.billing.status}</Text>}
                    </View>
                  </>
                )}
                {c.demo && (
                  <View style={{ flexDirection: 'row', gap: 12, flexWrap: 'wrap' }} {...tid('quick-shops-stats')}>
                    <Text style={{ fontSize: 12.5, fontWeight: '700', color: colors.text }}>{done} shop{done === 1 ? '' : 's'} this month</Text>
                    {prog.filter(([, p]) => p.completed > 0).map(([k, p]) => <Text key={k} style={{ fontSize: 12, color: colors.textSecondary }}>{p.label || k} {p.completed}</Text>)}
                    {!!c.needs_training && <Text style={{ fontSize: 12, fontWeight: '700', color: RED }}>{c.needs_training} need training</Text>}
                    <Text style={{ fontSize: 12, color: colors.textSecondary }}>not billed</Text>
                  </View>
                )}
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      )}
      <ClientSheet visible={sheet} onClose={() => setSheet(false)} colors={colors} onSaved={(c) => afterModal(() => router.push(`/admin/mystery-shops/${c.id}` as any))} defaultFrom={defaultFrom} />
      <DemoShopSheet visible={demo} onClose={() => setDemo(false)} colors={colors} onStarted={(clientId) => afterModal(() => router.push(`/admin/mystery-shops/${clientId}?tab=calls` as any))} />
      <ShopNumberSheet visible={numberSheet} onClose={() => setNumberSheet(false)} colors={colors} onChanged={onNumberChanged} />
      <ImportSheet visible={importSheet} onClose={() => { setImportSheet(false); load(); }} colors={colors} onDone={() => load()} />
    </SafeAreaView>
  );
}
