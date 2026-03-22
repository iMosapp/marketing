import React, { useState, useRef } from 'react';
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
import * as Clipboard from 'expo-clipboard';

const PLANS = [
  { id: 'starter', name: 'Starter', price: '$49/mo', desc: '1-5 users', color: '#007AFF' },
  { id: 'pro', name: 'Professional', price: '$99/mo', desc: '6-15 users', color: '#C9A962' },
  { id: 'enterprise', name: 'Enterprise', price: '$199/mo', desc: '16+ users', color: '#AF52DE' },
];

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

interface SuccessData {
  business_name: string;
  contact_name: string;
  contact_email: string;
  temp_password: string;
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
  const [plan, setPlan] = useState('pro');
  const [submitting, setSubmitting] = useState(false);
  const [step, setStep] = useState<'search' | 'details' | 'success'>('search');
  const [successData, setSuccessData] = useState<SuccessData | null>(null);
  const [copiedPassword, setCopiedPassword] = useState(false);

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
        plan,
        place_id: selectedPlace?.place_id || '',
        lat: selectedPlace?.lat || '',
        lon: selectedPlace?.lon || '',
        verified_source: selectedPlace ? 'openstreetmap' : 'manual',
      }, { headers: { 'X-User-ID': user._id } });

      setSuccessData({
        business_name: res.data.business_name,
        contact_name: res.data.contact_name,
        contact_email: res.data.contact_email,
        temp_password: res.data.temp_password,
      });
      setStep('success');
    } catch (e: any) {
      showSimpleAlert('Error', e?.response?.data?.detail || 'Failed to create account');
    }
    setSubmitting(false);
  };

  const copyPassword = async () => {
    if (!successData?.temp_password) return;
    try {
      await Clipboard.setStringAsync(successData.temp_password);
      setCopiedPassword(true);
      setTimeout(() => setCopiedPassword(false), 2000);
    } catch {
      showSimpleAlert('Copied', successData.temp_password);
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      {/* Header */}
      <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 0.5, borderBottomColor: colors.border }}>
        <TouchableOpacity
          onPress={() => {
            if (step === 'details') setStep('search');
            else if (step === 'success') router.back();
            else router.back();
          }}
          style={{ padding: 4, marginRight: 8 }}
          data-testid="new-account-back"
        >
          <Ionicons name={step === 'success' ? 'close' : 'chevron-back'} size={24} color={colors.accent} />
        </TouchableOpacity>
        <Text style={{ fontSize: 19, fontWeight: '700', color: colors.text, flex: 1 }}>
          {step === 'success' ? 'Account Created' : 'Sign Up New Account'}
        </Text>
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
        ) : step === 'details' ? (
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
            <Text style={{ fontSize: 13, fontWeight: '700', color: '#48484A', letterSpacing: 1.5, paddingHorizontal: 16, paddingTop: 20, paddingBottom: 8 }}>PLAN</Text>
            <View style={{ flexDirection: 'row', gap: 8, paddingHorizontal: 16 }}>
              {PLANS.map(p => {
                const sel = plan === p.id;
                return (
                  <TouchableOpacity
                    key={p.id}
                    onPress={() => setPlan(p.id)}
                    style={{
                      flex: 1, padding: 14, borderRadius: 12, alignItems: 'center', borderWidth: 1,
                      backgroundColor: sel ? `${p.color}12` : colors.card,
                      borderColor: sel ? `${p.color}40` : colors.border,
                    }}
                    data-testid={`plan-${p.id}`}
                  >
                    <Text style={{ fontSize: 16, fontWeight: '700', color: sel ? p.color : colors.textSecondary }}>{p.name}</Text>
                    <Text style={{ fontSize: 18, fontWeight: '800', color: sel ? p.color : colors.text, marginTop: 2 }}>{p.price}</Text>
                    <Text style={{ fontSize: 13, color: colors.textTertiary, marginTop: 1 }}>{p.desc}</Text>
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
              {submitting ? <ActivityIndicator color="#000" /> : <Text style={{ fontSize: 18, fontWeight: '700', color: '#000' }}>Start Onboarding</Text>}
            </TouchableOpacity>
            <Text style={{ fontSize: 14, color: '#48484A', textAlign: 'center', padding: 8 }}>This will create the account and start the onboarding checklist</Text>
          </>
        ) : (
          /* ── Success Screen ── */
          <View style={{ paddingHorizontal: 16, paddingTop: 32, alignItems: 'center' }}>
            <View style={{ width: 72, height: 72, borderRadius: 36, backgroundColor: 'rgba(52,199,89,0.15)', alignItems: 'center', justifyContent: 'center', marginBottom: 16 }}>
              <Ionicons name="checkmark-circle" size={48} color="#34C759" />
            </View>
            <Text style={{ fontSize: 24, fontWeight: '800', color: colors.text, textAlign: 'center' }}>Account Created!</Text>
            <Text style={{ fontSize: 17, color: colors.textSecondary, textAlign: 'center', marginTop: 8, paddingHorizontal: 16 }}>
              {successData?.business_name} has been set up and is ready to go.
            </Text>

            {/* Credentials Card */}
            <View style={{ width: '100%', marginTop: 24, backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: colors.border, overflow: 'hidden' }}>
              <View style={{ padding: 16, borderBottomWidth: 0.5, borderBottomColor: colors.border }}>
                <Text style={{ fontSize: 13, fontWeight: '700', color: '#48484A', letterSpacing: 1.5, marginBottom: 12 }}>LOGIN CREDENTIALS</Text>
                <View style={{ gap: 10 }}>
                  <View>
                    <Text style={{ fontSize: 14, color: colors.textSecondary }}>Name</Text>
                    <Text style={{ fontSize: 17, fontWeight: '600', color: colors.text, marginTop: 2 }} data-testid="success-contact-name">{successData?.contact_name}</Text>
                  </View>
                  <View>
                    <Text style={{ fontSize: 14, color: colors.textSecondary }}>Email</Text>
                    <Text style={{ fontSize: 17, fontWeight: '600', color: colors.text, marginTop: 2 }} data-testid="success-contact-email">{successData?.contact_email || 'Not provided'}</Text>
                  </View>
                  <View>
                    <Text style={{ fontSize: 14, color: colors.textSecondary }}>Temporary Password</Text>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 2 }}>
                      <Text style={{ fontSize: 17, fontWeight: '700', color: '#C9A962', fontFamily: 'monospace' }} data-testid="success-temp-password">{successData?.temp_password}</Text>
                      <TouchableOpacity onPress={copyPassword} data-testid="copy-password-btn">
                        <Ionicons name={copiedPassword ? 'checkmark' : 'copy-outline'} size={18} color={copiedPassword ? '#34C759' : colors.accent} />
                      </TouchableOpacity>
                    </View>
                  </View>
                </View>
              </View>
              <View style={{ padding: 16, backgroundColor: 'rgba(255,149,0,0.06)' }}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                  <Ionicons name="information-circle" size={16} color="#FF9500" />
                  <Text style={{ fontSize: 14, color: '#FF9500', fontWeight: '600' }}>Share these credentials with the account owner</Text>
                </View>
              </View>
            </View>

            {/* Action Buttons */}
            <TouchableOpacity
              onPress={() => router.back()}
              style={{ width: '100%', marginTop: 24, padding: 16, borderRadius: 14, backgroundColor: colors.accent, alignItems: 'center' }}
              activeOpacity={0.8}
              data-testid="success-done-btn"
            >
              <Text style={{ fontSize: 18, fontWeight: '700', color: '#000' }}>Done</Text>
            </TouchableOpacity>
          </View>
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
