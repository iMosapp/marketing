import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, TextInput, useWindowDimensions } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams } from 'expo-router';
import api from '../../services/api';
import { KickoffHours } from '../../components/mystery-shops/KickoffHours';
import { KickoffPeople, newPerson, type KPerson } from '../../components/mystery-shops/KickoffPeople';
import { Label, GoldButton, LIGHT, GOLD, GREEN, RED, tid, type Hours } from '../../components/mystery-shops/shared';

const inp = { backgroundColor: LIGHT.surface, borderRadius: 12, borderWidth: 1, borderColor: LIGHT.border, paddingHorizontal: 12, height: 46, color: LIGHT.text, fontSize: 15 } as const;
const Card = ({ title, sub, children, testID }: { title: string; sub?: string; children: React.ReactNode; testID: string }) => (
  <View style={{ backgroundColor: LIGHT.card, borderRadius: 18, borderWidth: 1, borderColor: LIGHT.border, padding: 18, gap: 14 }} {...tid(testID)}>
    <View style={{ gap: 2 }}><Text style={{ fontSize: 18, fontWeight: '800', color: LIGHT.text }}>{title}</Text>{!!sub && <Text style={{ fontSize: 13.5, color: LIGHT.textSecondary, lineHeight: 19 }}>{sub}</Text>}</View>
    {children}
  </View>
);

// No-login store setup form. The GM fills in contact, hours, vehicles and people; it saves straight into the client and pings iMOS.
export default function PublicShopKickoff() {
  const { token } = useLocalSearchParams<{ token: string }>();
  const { width } = useWindowDimensions();
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState('');
  const [contact, setContact] = useState({ contact_name: '', contact_title: '', contact_email: '', contact_phone: '' });
  const [hours, setHours] = useState<Hours>({ start: '09:00', end: '18:00', days: [0, 1, 2, 3, 4, 5] });
  const [timezone, setTimezone] = useState('America/Denver');
  const [vehicles, setVehicles] = useState<string[]>([]);
  const [vehicle, setVehicle] = useState('');
  const [people, setPeople] = useState<KPerson[]>([]);
  const [removed, setRemoved] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [saved, setSaved] = useState<any>(null);

  const hydrate = (d: any) => {
    const c = d.client;
    setData(d); setContact({ contact_name: c.contact_name || '', contact_title: c.contact_title || '', contact_email: c.contact_email || '', contact_phone: c.contact_phone || '' });
    setHours(c.hours); setTimezone(c.timezone); setVehicles(c.vehicles || []);
    setPeople((d.people || []).map((p: any) => ({ key: p.id, id: p.id, name: p.name, phone: p.phone, department: p.department, title: p.title || '' })).concat(d.people?.length ? [] : [newPerson('sales'), newPerson('service')]));
    setRemoved([]);
  };
  useEffect(() => { if (token) api.get(`/public/shop-kickoff/${token}`).then(r => hydrate(r.data)).catch(() => setError('This setup link is not valid anymore. Ask I\'m On Social for a fresh one.')); }, [token]);

  const onPeople = (next: KPerson[]) => { const gone = people.filter(p => p.id && !next.some(n => n.key === p.key)).map(p => p.id!); if (gone.length) setRemoved(r => [...r, ...gone]); setPeople(next); };
  const addVehicle = () => { const v = vehicle.trim(); if (!v) return; setVehicles(x => [...x, v]); setVehicle(''); };
  const filled = people.filter(p => p.name.trim() || p.phone.trim());
  const incomplete = filled.filter(p => !p.name.trim() || p.phone.replace(/\D/g, '').length < 10);

  const save = async () => {
    setBusy(true); setErr('');
    try {
      const r = await api.post(`/public/shop-kickoff/${token}`, { ...contact, timezone, hours, vehicles, people: filled.map(p => ({ id: p.id, name: p.name, phone: p.phone, department: p.department, title: p.title })), remove_ids: removed });
      setSaved(r.data); hydrate(r.data);
    } catch (e: any) { setErr(e?.response?.data?.detail || 'Something went wrong, try again'); }
    finally { setBusy(false); }
  };

  const wide = width > 800;
  const c = data?.client;
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: LIGHT.bg }}>
      <ScrollView contentContainerStyle={{ padding: wide ? 32 : 16, paddingBottom: 80, alignItems: 'center' }} keyboardShouldPersistTaps="handled">
        <View style={{ width: '100%', maxWidth: 760, gap: 18 }}>
          <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 2 }}>I'M ON SOCIAL · STORE SETUP</Text>
          {error ? <Text style={{ fontSize: 15, color: LIGHT.textSecondary }} {...tid('kickoff-error')}>{error}</Text> : !c ? <ActivityIndicator color={GOLD} style={{ marginTop: 40 }} /> : (
            <>
              <Text style={{ fontSize: wide ? 32 : 26, fontWeight: '800', color: LIGHT.text }} {...tid('kickoff-title')}>Set up {c.name}</Text>
              <Text style={{ fontSize: 15, color: LIGHT.text, lineHeight: 23 }}>Takes about five minutes. {data.sender_name} gets it the moment you save, and your shops start right away. Come back to this same link any time to add or fix people.</Text>
              {saved && (
                <View style={{ backgroundColor: LIGHT.card, borderRadius: 18, padding: 18, borderWidth: 1, borderColor: GREEN + '88', flexDirection: 'row', gap: 12, alignItems: 'center' }} {...tid('kickoff-saved')}>
                  <Ionicons name="checkmark-circle" size={28} color={GREEN} />
                  <View style={{ flex: 1 }}><Text style={{ fontSize: 17, fontWeight: '800', color: LIGHT.text }}>Saved, thank you</Text><Text style={{ fontSize: 14, color: LIGHT.textSecondary, lineHeight: 20 }}>{saved.people.length} people to shop{saved.added ? ` (${saved.added} new)` : ''}, {vehicles.length} vehicles, hours set. {data.sender_name} has been notified. You can keep editing below.</Text></View>
                </View>
              )}
              <Card title="Who we send reports to" sub="The monthly report and invoice go here." testID="kickoff-contact-card">
                <View style={{ flexDirection: wide ? 'row' : 'column', gap: 10 }}>
                  <TextInput value={contact.contact_name} onChangeText={v => setContact({ ...contact, contact_name: v })} placeholder="Your name" placeholderTextColor={LIGHT.textSecondary} style={[inp, { flex: 1.4 }]} {...tid('kickoff-contact-name')} />
                  <TextInput value={contact.contact_title} onChangeText={v => setContact({ ...contact, contact_title: v })} placeholder="Title (GM, Owner)" placeholderTextColor={LIGHT.textSecondary} style={[inp, { flex: 1 }]} {...tid('kickoff-contact-title')} />
                </View>
                <View style={{ flexDirection: wide ? 'row' : 'column', gap: 10 }}>
                  <TextInput value={contact.contact_email} onChangeText={v => setContact({ ...contact, contact_email: v })} placeholder="Email" placeholderTextColor={LIGHT.textSecondary} keyboardType="email-address" autoCapitalize="none" style={[inp, { flex: 1.4 }]} {...tid('kickoff-contact-email')} />
                  <TextInput value={contact.contact_phone} onChangeText={v => setContact({ ...contact, contact_phone: v })} placeholder="Your cell (optional)" placeholderTextColor={LIGHT.textSecondary} keyboardType="phone-pad" style={[inp, { flex: 1 }]} {...tid('kickoff-contact-phone')} />
                </View>
              </Card>
              <Card title="When we may call" sub="Shops land at random times inside this window so nobody can predict them." testID="kickoff-hours-card">
                <KickoffHours hours={hours} timezone={timezone} timezones={data.timezones} onHours={setHours} onTimezone={setTimezone} />
              </Card>
              <Card title="Vehicles our shopper can mention" sub="Real units from your lot make the calls believable. Year, make, model, trim is plenty." testID="kickoff-vehicles-card">
                <View style={{ flexDirection: 'row', gap: 8 }}>
                  <TextInput value={vehicle} onChangeText={setVehicle} onSubmitEditing={addVehicle} placeholder="2024 Jeep Grand Cherokee L Limited" placeholderTextColor={LIGHT.textSecondary} style={[inp, { flex: 1 }]} {...tid('kickoff-vehicle-input')} />
                  <TouchableOpacity onPress={addVehicle} style={{ paddingHorizontal: 16, height: 46, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center' }} {...tid('kickoff-vehicle-add')}><Text style={{ fontSize: 14, fontWeight: '800', color: '#111' }}>Add</Text></TouchableOpacity>
                </View>
                {vehicles.length === 0 && <Text style={{ fontSize: 13, color: LIGHT.textSecondary }} {...tid('kickoff-vehicles-empty')}>None yet. We will use generic "the SUV you have listed online" until you add some.</Text>}
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
                  {vehicles.map((v, i) => (
                    <View key={`${v}-${i}`} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingLeft: 10, paddingRight: 6, height: 32, borderRadius: 16, backgroundColor: LIGHT.surface, borderWidth: 1, borderColor: LIGHT.border }} {...tid(`kickoff-vehicle-${i}`)}>
                      <Text style={{ fontSize: 13, fontWeight: '600', color: LIGHT.text }}>{v}</Text>
                      <TouchableOpacity onPress={() => setVehicles(vehicles.filter((_, j) => j !== i))} hitSlop={6} {...tid(`kickoff-vehicle-remove-${i}`)}><Ionicons name="close-circle" size={18} color={LIGHT.textSecondary} /></TouchableOpacity>
                    </View>
                  ))}
                </View>
              </Card>
              <Card title="People to shop" sub={`Your plan covers ${c.plan?.sales_per_month || 0} sales and ${c.plan?.service_per_month || 0} service shops a month, spread across everyone below. We only ever call the cell numbers here; nobody gets a text or an email.`} testID="kickoff-people-card">
                <KickoffPeople people={people} onChange={onPeople} />
              </Card>
              {!!err && <Text style={{ fontSize: 14, color: RED, fontWeight: '600' }} {...tid('kickoff-error')}>{err}</Text>}
              {incomplete.length > 0 && <Text style={{ fontSize: 13, color: LIGHT.textSecondary }} {...tid('kickoff-incomplete')}>{incomplete.length} {incomplete.length === 1 ? 'person still needs' : 'people still need'} a name and a full cell number.</Text>}
              <GoldButton label={saved ? 'Save changes' : `Save and start the shops`} onPress={save} busy={busy} disabled={incomplete.length > 0 || hours.days.length === 0} testID="kickoff-save" icon="checkmark" />
              <Text style={{ fontSize: 12, color: LIGHT.textSecondary, textAlign: 'center' }}>I'm On Social LLC · 1741 Lunford Ln, Riverton, UT 84065 · Questions? Reply to the email this link came in.</Text>
            </>
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
