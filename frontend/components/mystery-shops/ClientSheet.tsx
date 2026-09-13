import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, Switch } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useToast } from '../common/Toast';
import { Sheet, Field, Label, Chip, GoldButton, DAYS, GOLD, tid, type Client } from './shared';

type Props = { visible: boolean; onClose: () => void; colors: any; client?: Client | null; onSaved: (c: Client) => void; defaultFrom?: string };

const blank = { name: '', brand: '', city: '', state: '', contact_name: '', contact_email: '', contact_phone: '', contact_title: '', sales: '20', service: '20', price: '400', start: '09:00', end: '18:00', days: [0, 1, 2, 3, 4, 5], vehicles: '', from_number: '', record: true, notes: '', timezone: 'America/Denver' };

// Create / edit a client store: who they are, the plan they bought, when we may call, what vehicles the shopper mentions.
export const ClientSheet = ({ visible, onClose, colors, client, onSaved, defaultFrom }: Props) => {
  const { showToast } = useToast();
  const [f, setF] = useState<any>(blank);
  const [busy, setBusy] = useState(false);
  const set = (k: string, v: any) => setF((x: any) => ({ ...x, [k]: v }));

  useEffect(() => {
    if (!visible) return;
    if (client) setF({ name: client.name, brand: client.brand, city: client.city, state: client.state, contact_name: client.contact_name, contact_email: client.contact_email, contact_phone: client.contact_phone, contact_title: client.contact_title,
      sales: String(client.plan.sales_per_month), service: String(client.plan.service_per_month), price: String(client.plan.price_monthly), start: client.hours.start, end: client.hours.end, days: client.hours.days, vehicles: (client.vehicles || []).join('\n'),
      from_number: client.from_number || '', record: client.record_calls, notes: client.notes || '', timezone: client.timezone, text_scorecards: !!client.text_scorecards });
    else setF(blank);
  }, [visible, client?.id]);

  const save = async () => {
    if (!f.name.trim()) { showToast('Give the client a name', 'error'); return; }
    setBusy(true);
    try {
      const payload = { name: f.name, brand: f.brand, city: f.city, state: f.state, timezone: f.timezone, contact_name: f.contact_name, contact_email: f.contact_email.trim(), contact_phone: f.contact_phone, contact_title: f.contact_title,
        plan: { sales_per_month: Number(f.sales) || 0, service_per_month: Number(f.service) || 0, price_monthly: Number(f.price) || 0 }, hours: { start: f.start, end: f.end, days: f.days },
        vehicles: f.vehicles.split('\n').map((v: string) => v.trim()).filter(Boolean), from_number: f.from_number || '', record_calls: f.record, notes: f.notes, text_scorecards: !!f.text_scorecards };
      const res = client ? await api.put(`/shop-clients/${client.id}`, payload) : await api.post('/shop-clients', payload);
      onSaved(res.data); onClose(); showToast(client ? 'Saved' : 'Client added', 'success');
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not save', 'error'); }
    finally { setBusy(false); }
  };

  return (
    <Sheet visible={visible} onClose={onClose} title={client ? 'Edit client' : 'New mystery shop client'} colors={colors} testID="client-sheet" footer={<GoldButton label={client ? 'Save changes' : 'Add client'} onPress={save} busy={busy} testID="client-save" />}>
      <Field label="STORE NAME" value={f.name} onChange={(v: string) => set('name', v)} colors={colors} placeholder="LHM Jeep Sandy" testID="client-name" />
      <View style={{ flexDirection: 'row', gap: 10 }}>
        <View style={{ flex: 2 }}><Field label="BRANDS" value={f.brand} onChange={(v: string) => set('brand', v)} colors={colors} placeholder="Jeep, Ram, Chrysler" testID="client-brand" /></View>
        <View style={{ flex: 1.3 }}><Field label="CITY" value={f.city} onChange={(v: string) => set('city', v)} colors={colors} placeholder="Sandy" testID="client-city" /></View>
        <View style={{ flex: 0.7 }}><Field label="ST" value={f.state} onChange={(v: string) => set('state', v.toUpperCase().slice(0, 2))} colors={colors} placeholder="UT" autoCapitalize="characters" testID="client-state" /></View>
      </View>
      <View style={{ gap: 8 }}>
        <Label t="CONTACT (GETS THE PROPOSAL, INVOICE AND REPORT)" colors={colors} />
        <View style={{ flexDirection: 'row', gap: 10 }}>
          <View style={{ flex: 1.4 }}><Field value={f.contact_name} onChange={(v: string) => set('contact_name', v)} colors={colors} placeholder="Name" testID="client-contact-name" /></View>
          <View style={{ flex: 1 }}><Field value={f.contact_title} onChange={(v: string) => set('contact_title', v)} colors={colors} placeholder="GM" testID="client-contact-title" /></View>
        </View>
        <Field value={f.contact_email} onChange={(v: string) => set('contact_email', v)} colors={colors} placeholder="gm@dealer.com" keyboardType="email-address" autoCapitalize="none" testID="client-contact-email" />
        <Field value={f.contact_phone} onChange={(v: string) => set('contact_phone', v)} colors={colors} placeholder="Contact phone (optional)" keyboardType="phone-pad" testID="client-contact-phone" />
      </View>
      <View style={{ gap: 8 }}>
        <Label t="PLAN PER MONTH" colors={colors} />
        <View style={{ flexDirection: 'row', gap: 10 }}>
          <View style={{ flex: 1 }}><Field label="SALES SHOPS" value={f.sales} onChange={(v: string) => set('sales', v.replace(/\D/g, ''))} colors={colors} keyboardType="number-pad" testID="client-plan-sales" /></View>
          <View style={{ flex: 1 }}><Field label="SERVICE SHOPS" value={f.service} onChange={(v: string) => set('service', v.replace(/\D/g, ''))} colors={colors} keyboardType="number-pad" testID="client-plan-service" /></View>
          <View style={{ flex: 1 }}><Field label="PRICE ($/MO)" value={f.price} onChange={(v: string) => set('price', v.replace(/[^\d.]/g, ''))} colors={colors} keyboardType="decimal-pad" testID="client-plan-price" /></View>
        </View>
      </View>
      <View style={{ gap: 8 }}>
        <Label t="WHEN WE MAY CALL (STORE LOCAL TIME)" colors={colors} />
        <View style={{ flexDirection: 'row', gap: 10, alignItems: 'center' }}>
          <View style={{ flex: 1 }}><Field value={f.start} onChange={(v: string) => set('start', v)} colors={colors} placeholder="09:00" testID="client-hours-start" /></View>
          <Text style={{ color: colors.textSecondary }}>to</Text>
          <View style={{ flex: 1 }}><Field value={f.end} onChange={(v: string) => set('end', v)} colors={colors} placeholder="18:00" testID="client-hours-end" /></View>
        </View>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
          {DAYS.map((d, i) => <Chip key={d} label={d} small active={f.days.includes(i)} onPress={() => set('days', f.days.includes(i) ? f.days.filter((x: number) => x !== i) : [...f.days, i].sort())} colors={colors} testID={`client-day-${i}`} />)}
        </View>
        <Field value={f.timezone} onChange={(v: string) => set('timezone', v)} colors={colors} placeholder="America/Denver" autoCapitalize="none" testID="client-timezone" />
      </View>
      <Field label="VEHICLES THE SHOPPER CAN MENTION (ONE PER LINE)" value={f.vehicles} onChange={(v: string) => set('vehicles', v)} colors={colors} multiline placeholder={'2023 Jeep Grand Cherokee L Limited\n2022 Ram 1500 Big Horn'} testID="client-vehicles" />
      <Field label="CALL FROM NUMBER (OPTIONAL)" value={f.from_number} onChange={(v: string) => set('from_number', v)} colors={colors} placeholder={defaultFrom ? `Default ${defaultFrom}` : 'Twilio number the shopper calls from'} keyboardType="phone-pad" testID="client-from-number" />
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: colors.card, borderRadius: 12, padding: 12, borderWidth: 1, borderColor: colors.border }}>
        <Ionicons name="recording" size={18} color={GOLD} />
        <View style={{ flex: 1 }}><Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>Record shop calls</Text><Text style={{ fontSize: 12, color: colors.textSecondary }}>Recordings go on the store report. Consent is covered in the proposal.</Text></View>
        <Switch value={f.record} onValueChange={(v) => set('record', v)} {...tid('client-record-toggle')} />
      </View>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: colors.card, borderRadius: 12, padding: 12, borderWidth: 1, borderColor: colors.border }}>
        <Ionicons name="chatbubble-ellipses" size={18} color={GOLD} />
        <View style={{ flex: 1 }}><Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>Text people their scorecard</Text><Text style={{ fontSize: 12, color: colors.textSecondary }}>Right after each shop is graded, the person gets a text with their score, top win, top fix and a link to the full scorecard and recording.</Text></View>
        <Switch value={!!f.text_scorecards} onValueChange={(v) => set('text_scorecards', v)} {...tid('client-text-scorecards-toggle')} />
      </View>
      <Field label="NOTES" value={f.notes} onChange={(v: string) => set('notes', v)} colors={colors} multiline placeholder="Anything the shopper should know about this store" testID="client-notes" />
    </Sheet>
  );
};
