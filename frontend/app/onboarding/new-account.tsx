import React, { useEffect, useRef, useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, ScrollView, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import api from '../../services/api';
import { showSimpleAlert } from '../../services/alert';

const FALLBACK_PLANS = [
  { key: 'pilot_store_monthly', name: 'Pilot Store', amount: 375, seats_included: 5, seat_price: 75, desc: '5 seats included, $75/mo per extra seat' },
  { key: 'pilot_individual_monthly', name: 'Pilot Individual', amount: 100, seats_included: 1, seat_price: null, desc: 'One person, one seat' },
];
const PLAN_COLOR: Record<string, string> = { pilot_store_monthly: '#C9A962', pilot_individual_monthly: '#007AFF' };

const INDUSTRIES = [
  'Automotive / Dealership', 'Real Estate', 'Restaurant / Hospitality',
  'Salon / Barbershop', 'Health & Wellness', 'Insurance',
  'Financial Services', 'Home Services', 'Retail', 'Other',
];

interface PlaceResult {
  display_name: string;
  name: string;
  address: string;
  city: string;
  state: string;
  zip: string;
  lat: string;
  lon: string;
  place_id: string;
  type: string;
}

// --- Business Search Service (swappable: Nominatim now, Google Places later) ---
async function searchBusinesses(query: string): Promise<PlaceResult[]> {
  if (query.length < 3) return [];
  try {
    const url = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(query)}&format=json&addressdetails=1&limit=8&countrycodes=us`;
    const res = await fetch(url, { headers: { 'User-Agent': 'IMOnSocial/1.0' } });
    const data = await res.json();
    return data.map((item: any) => {
      const addr = item.address || {};
      return {
        display_name: item.display_name,
        name: addr.shop || addr.amenity || addr.building || item.name || item.display_name.split(',')[0],
        address: [addr.house_number, addr.road].filter(Boolean).join(' ') || '',
        city: addr.city || addr.town || addr.village || addr.county || '',
        state: addr.state || '',
        zip: addr.postcode || '',
        lat: item.lat,
        lon: item.lon,
        place_id: String(item.place_id),
        type: item.type || '',
      };
    });
  } catch {
    return [];
  }
}

export default function NewAccountScreen() {
  const { colors } = useThemeStore();
  const router = useRouter();
  const user = useAuthStore((s) => s.user);

  // Search
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<PlaceResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [selectedPlace, setSelectedPlace] = useState<PlaceResult | null>(null);
  const searchTimer = useRef<any>(null);

  // Business details
  const [businessName, setBusinessName] = useState('');
  const [address, setAddress] = useState('');
  const [city, setCity] = useState('');
  const [state, setState] = useState('');
  const [zip, setZip] = useState('');
  const [phone, setPhone] = useState('');
  const [website, setWebsite] = useState('');
  const [industry, setIndustry] = useState('');

  // Contact person
  const [contactName, setContactName] = useState('');
  const [contactEmail, setContactEmail] = useState('');
  const [contactPhone, setContactPhone] = useState('');

  // Plan & submit
  const [plans, setPlans] = useState<any[]>(FALLBACK_PLANS);
  const [plan, setPlan] = useState('pilot_store_monthly');
  const [seatsExtra, setSeatsExtra] = useState(0);
  const [billingMode, setBillingMode] = useState<'founding_pilot' | 'paid'>('founding_pilot');
  const [submitting, setSubmitting] = useState(false);
  const [step, setStep] = useState<'search' | 'details'>('search');

  useEffect(() => {
    api.get('/customers/plans').then((r) => Array.isArray(r.data) && r.data.length && setPlans(r.data)).catch(() => {});
  }, []);
  const selectedPlan = plans.find((p) => p.key === plan) || plans[0];

  const handleSearch = (text: string) => {
    setSearchQuery(text);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    if (text.length < 3) { setSearchResults([]); return; }
    searchTimer.current = setTimeout(async () => {
      setSearching(true);
      const results = await searchBusinesses(text);
      setSearchResults(results);
      setSearching(false);
    }, 400);
  };

  const selectPlace = (place: PlaceResult) => {
    setSelectedPlace(place);
    setBusinessName(place.name);
    setAddress(place.address);
    setCity(place.city);
    setState(place.state);
    setZip(place.zip);
    setSearchResults([]);
    setSearchQuery(place.name);
    setStep('details');
  };

  const handleManualEntry = () => {
    setBusinessName(searchQuery);
    setSelectedPlace(null);
    setStep('details');
  };

  const handleSubmit = async () => {
    if (!businessName.trim()) { showSimpleAlert('Required', 'Business name is required'); return; }
    if (!contactName.trim() || !contactPhone.trim()) { showSimpleAlert('Required', 'Contact name and phone are required'); return; }
    if (!user?._id) return;

    setSubmitting(true);
    try {
      const res = await api.post('/setup-wizard/new-account', {
        business_name: businessName.trim(),
        address: address.trim(),
        city: city.trim(),
        state: state.trim(),
        zip: zip.trim(),
        phone: phone.trim(),
        website: website.trim(),
        industry,
        contact_name: contactName.trim(),
        contact_email: contactEmail.trim(),
        contact_phone: contactPhone.trim(),
        plan_key: plan,
        seats_extra: selectedPlan?.seat_price ? seatsExtra : 0,
        pilot: true,
        billing_mode: billingMode,
        place_id: selectedPlace?.place_id || '',
        lat: selectedPlace?.lat || '',
        lon: selectedPlace?.lon || '',
        verified_source: selectedPlace ? 'openstreetmap' : 'manual',
      });
      router.replace(`/admin/customers/${res.data.organization_id}` as any);
    } catch (e: any) {
      showSimpleAlert('Error', e?.response?.data?.detail || 'Failed to create account');
    }
    setSubmitting(false);
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      {/* Header */}
      <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 0.5, borderBottomColor: colors.border }}>
        <TouchableOpacity
          onPress={() => {
            if (step === 'details') setStep('search');
            else router.back();
          }}
          style={{ padding: 4, marginRight: 8 }}
          data-testid="new-account-back"
        >
          <Ionicons name="chevron-back" size={24} color={colors.accent} />
        </TouchableOpacity>
        <Text style={{ fontSize: 19, fontWeight: '700', color: colors.text, flex: 1 }}>New Customer</Text>
      </View>

      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingBottom: 40 }} showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled">
        {step === 'search' ? (
          <>
            {/* Search */}
            <View style={{ paddingHorizontal: 16, paddingTop: 20 }}>
              <Text style={{ fontSize: 22, fontWeight: '800', color: colors.text, marginBottom: 4 }}>Find the Business</Text>
              <Text style={{ fontSize: 16, color: colors.textSecondary, marginBottom: 16 }}>Search by name to auto-fill their info</Text>

              <View style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 14, gap: 10 }}>
                <Ionicons name="search" size={20} color={colors.textSecondary} />
                <TextInput
                  style={{ flex: 1, paddingVertical: 14, fontSize: 18, color: colors.text }}
                  placeholder="Type business name or address..."
                  placeholderTextColor="#48484A"
                  value={searchQuery}
                  onChangeText={handleSearch}
                  autoFocus
                  data-testid="business-search-input"
                />
                {searching && <ActivityIndicator size="small" color={colors.accent} />}
              </View>
            </View>

            {/* Results */}
            {searchResults.length > 0 && (
              <View style={{ marginTop: 8, paddingHorizontal: 16 }}>
                {searchResults.map((place, idx) => (
                  <TouchableOpacity
                    key={place.place_id + idx}
                    onPress={() => selectPlace(place)}
                    style={{
                      flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12,
                      borderBottomWidth: idx < searchResults.length - 1 ? 0.5 : 0, borderBottomColor: colors.border,
                    }}
                    data-testid={`search-result-${idx}`}
                  >
                    <View style={{ width: 40, height: 40, borderRadius: 10, backgroundColor: 'rgba(0,122,255,0.12)', alignItems: 'center', justifyContent: 'center' }}>
                      <Ionicons name="location" size={20} color="#007AFF" />
                    </View>
                    <View style={{ flex: 1, minWidth: 0 }}>
                      <Text style={{ fontSize: 16, fontWeight: '600', color: colors.text }} numberOfLines={1}>{place.name}</Text>
                      <Text style={{ fontSize: 14, color: colors.textSecondary }} numberOfLines={1}>
                        {[place.address, place.city, place.state].filter(Boolean).join(', ')}
                      </Text>
                    </View>
                    <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />
                  </TouchableOpacity>
                ))}
              </View>
            )}

            {/* Manual entry option */}
            {searchQuery.length >= 3 && !searching && (
              <TouchableOpacity
                onPress={handleManualEntry}
                style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 16, paddingVertical: 14, marginTop: 4 }}
                data-testid="manual-entry-btn"
              >
                <Ionicons name="create-outline" size={20} color={colors.accent} />
                <Text style={{ fontSize: 16, color: colors.accent, fontWeight: '600' }}>Enter details manually for "{searchQuery}"</Text>
              </TouchableOpacity>
            )}

            {searchQuery.length < 3 && (
              <View style={{ alignItems: 'center', paddingVertical: 40, paddingHorizontal: 32 }}>
                <Ionicons name="storefront-outline" size={48} color={colors.textTertiary} />
                <Text style={{ fontSize: 16, color: colors.textTertiary, textAlign: 'center', marginTop: 12 }}>
                  Start typing a business name to search. We'll auto-fill their address and details.
                </Text>
              </View>
            )}
          </>
        ) : (
          <>
            {/* Verified source badge */}
            {selectedPlace && (
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 16, paddingTop: 16, paddingBottom: 4 }}>
                <Ionicons name="checkmark-circle" size={16} color="#34C759" />
                <Text style={{ fontSize: 14, color: '#34C759', fontWeight: '600' }}>Address verified via map data</Text>
              </View>
            )}

            {/* Business Details */}
            <Text style={{ fontSize: 13, fontWeight: '700', color: '#48484A', letterSpacing: 1.5, paddingHorizontal: 16, paddingTop: 16, paddingBottom: 8 }}>BUSINESS DETAILS</Text>
            <View style={{ marginHorizontal: 16, backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: colors.border, overflow: 'hidden' }}>
              <Field label="Business Name" value={businessName} onChange={setBusinessName} colors={colors} testId="biz-name" />
              <Field label="Street Address" value={address} onChange={setAddress} colors={colors} testId="biz-address" />
              <View style={{ flexDirection: 'row' }}>
                <View style={{ flex: 2 }}><Field label="City" value={city} onChange={setCity} colors={colors} testId="biz-city" /></View>
                <View style={{ flex: 1 }}><Field label="State" value={state} onChange={setState} colors={colors} testId="biz-state" /></View>
                <View style={{ flex: 1 }}><Field label="ZIP" value={zip} onChange={setZip} colors={colors} testId="biz-zip" /></View>
              </View>
              <Field label="Phone" value={phone} onChange={setPhone} colors={colors} keyboard="phone-pad" testId="biz-phone" />
              <Field label="Website" value={website} onChange={setWebsite} colors={colors} keyboard="url" testId="biz-website" last />
            </View>

            {/* Industry */}
            <Text style={{ fontSize: 13, fontWeight: '700', color: '#48484A', letterSpacing: 1.5, paddingHorizontal: 16, paddingTop: 20, paddingBottom: 8 }}>INDUSTRY</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: 16, gap: 6 }}>
              {INDUSTRIES.map(ind => (
                <TouchableOpacity
                  key={ind}
                  onPress={() => setIndustry(ind)}
                  style={{
                    paddingVertical: 7, paddingHorizontal: 14, borderRadius: 20, borderWidth: 1,
                    backgroundColor: industry === ind ? 'rgba(201,169,98,0.1)' : colors.card,
                    borderColor: industry === ind ? 'rgba(201,169,98,0.4)' : colors.border,
                  }}
                  data-testid={`industry-${ind.toLowerCase().replace(/\s+/g, '-')}`}
                >
                  <Text style={{ fontSize: 15, fontWeight: '600', color: industry === ind ? colors.accent : colors.textSecondary }}>{ind}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>

            {/* Contact Person */}
            <Text style={{ fontSize: 13, fontWeight: '700', color: '#48484A', letterSpacing: 1.5, paddingHorizontal: 16, paddingTop: 20, paddingBottom: 8 }}>CONTACT PERSON</Text>
            <View style={{ marginHorizontal: 16, backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: colors.border, overflow: 'hidden' }}>
              <Field label="Full Name" value={contactName} onChange={setContactName} colors={colors} testId="contact-name" />
              <Field label="Phone" value={contactPhone} onChange={setContactPhone} colors={colors} keyboard="phone-pad" testId="contact-phone" />
              <Field label="Email" value={contactEmail} onChange={setContactEmail} colors={colors} keyboard="email-address" testId="contact-email" last />
            </View>

            {/* Plan */}
            <Text style={{ fontSize: 13, fontWeight: '700', color: '#48484A', letterSpacing: 1.5, paddingHorizontal: 16, paddingTop: 20, paddingBottom: 8 }}>PLAN (PROVISIONAL PILOT PRICING)</Text>
            <View style={{ flexDirection: 'row', gap: 8, paddingHorizontal: 16 }}>
              {plans.map(p => {
                const sel = plan === p.key;
                const color = PLAN_COLOR[p.key] || '#C9A962';
                return (
                  <TouchableOpacity
                    key={p.key}
                    onPress={() => { setPlan(p.key); if (!p.seat_price) setSeatsExtra(0); }}
                    style={{
                      flex: 1, padding: 14, borderRadius: 12, alignItems: 'center', borderWidth: 1,
                      backgroundColor: sel ? `${color}12` : colors.card,
                      borderColor: sel ? `${color}40` : colors.border,
                    }}
                    data-testid={`plan-${p.key}`}
                  >
                    <Text style={{ fontSize: 16, fontWeight: '700', color: sel ? color : colors.textSecondary }}>{p.name}</Text>
                    <Text style={{ fontSize: 18, fontWeight: '800', color: sel ? color : colors.text, marginTop: 2 }}>${p.amount}/mo</Text>
                    <Text style={{ fontSize: 13, color: colors.textTertiary, marginTop: 1, textAlign: 'center' }}>{p.desc}</Text>
                  </TouchableOpacity>
                );
              })}
            </View>
            {selectedPlan?.seat_price ? (
              <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginHorizontal: 16, marginTop: 10, padding: 12, borderRadius: 12, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.card }}>
                <View>
                  <Text style={{ fontSize: 15, fontWeight: '600', color: colors.text }}>Extra seats</Text>
                  <Text style={{ fontSize: 13, color: colors.textTertiary }} data-testid="seats-summary">
                    {selectedPlan.seats_included + seatsExtra} seats total · ${selectedPlan.amount + selectedPlan.seat_price * seatsExtra}/mo
                  </Text>
                </View>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 14 }}>
                  <TouchableOpacity onPress={() => setSeatsExtra(Math.max(0, seatsExtra - 1))} data-testid="seats-minus"><Ionicons name="remove-circle-outline" size={28} color={colors.accent} /></TouchableOpacity>
                  <Text style={{ fontSize: 18, fontWeight: '700', color: colors.text, minWidth: 20, textAlign: 'center' }} data-testid="seats-extra">{seatsExtra}</Text>
                  <TouchableOpacity onPress={() => setSeatsExtra(Math.min(500, seatsExtra + 1))} data-testid="seats-plus"><Ionicons name="add-circle-outline" size={28} color={colors.accent} /></TouchableOpacity>
                </View>
              </View>
            ) : null}

            {/* Billing mode */}
            <Text style={{ fontSize: 13, fontWeight: '700', color: '#48484A', letterSpacing: 1.5, paddingHorizontal: 16, paddingTop: 20, paddingBottom: 8 }}>BILLING</Text>
            <View style={{ gap: 8, paddingHorizontal: 16 }}>
              {([
                { key: 'founding_pilot', title: 'Founding Partner Pilot', desc: `90 complimentary days from the day the owner activates. No card, no Stripe. They agree to $${selectedPlan ? selectedPlan.amount + (selectedPlan.seat_price || 0) * seatsExtra : 375}/mo after and are charged only if they choose to continue.` },
                { key: 'paid', title: 'Paid from day one', desc: 'Send a Stripe payment link; the account is activated once the first payment clears.' },
              ] as const).map((m) => {
                const sel = billingMode === m.key;
                return (
                  <TouchableOpacity key={m.key} onPress={() => setBillingMode(m.key)} data-testid={`billing-mode-${m.key}`}
                    style={{ flexDirection: 'row', gap: 12, padding: 14, borderRadius: 12, borderWidth: 1, backgroundColor: sel ? '#C9A96212' : colors.card, borderColor: sel ? '#C9A96260' : colors.border }}>
                    <Ionicons name={sel ? 'radio-button-on' : 'radio-button-off'} size={20} color={sel ? '#C9A962' : colors.textTertiary} />
                    <View style={{ flex: 1 }}>
                      <Text style={{ fontSize: 15, fontWeight: '700', color: sel ? '#C9A962' : colors.text }}>{m.title}</Text>
                      <Text style={{ fontSize: 13, color: colors.textTertiary, marginTop: 2, lineHeight: 18 }}>{m.desc}</Text>
                    </View>
                  </TouchableOpacity>
                );
              })}
            </View>

            {/* Submit */}
            <TouchableOpacity
              onPress={handleSubmit}
              disabled={submitting}
              style={{ marginHorizontal: 16, marginTop: 24, padding: 16, borderRadius: 14, backgroundColor: colors.accent, alignItems: 'center' }}
              activeOpacity={0.8}
              data-testid="start-onboarding-btn"
            >
              {submitting ? <ActivityIndicator color="#000" /> : <Text style={{ fontSize: 18, fontWeight: '700', color: '#000' }}>Create Customer</Text>}
            </TouchableOpacity>
            <Text style={{ fontSize: 14, color: '#48484A', textAlign: 'center', padding: 8, paddingHorizontal: 24 }}>
              Creates the company and a dormant owner account. Nobody can sign in until you activate the account and send the owner their activation link.
            </Text>
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function Field({ label, value, onChange, colors, keyboard, last, testId }: {
  label: string; value: string; onChange: (v: string) => void; colors: any; keyboard?: any; last?: boolean; testId?: string;
}) {
  return (
    <View style={{ borderBottomWidth: last ? 0 : 0.5, borderBottomColor: colors.border }}>
      <TextInput
        style={{ padding: 14, paddingHorizontal: 16, fontSize: 18, color: colors.text }}
        placeholder={label}
        placeholderTextColor="#48484A"
        value={value}
        onChangeText={onChange}
        keyboardType={keyboard}
        autoCapitalize={keyboard === 'email-address' || keyboard === 'url' ? 'none' : 'words'}
        data-testid={testId}
      />
    </View>
  );
}
