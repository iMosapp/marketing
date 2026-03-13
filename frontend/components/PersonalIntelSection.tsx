import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, TextInput, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../services/api';
import { useToast } from './common/Toast';

interface Kid { name: string; details?: string }

interface PersonalDetails {
  spouse_name?: string;
  spouse_details?: string;
  kids?: Kid[];
  interests?: string[];
  occupation?: string;
  employer?: string;
  vehicle_purchased?: string;
  vehicle_color?: string;
  vehicle_details?: string;
  trade_in?: string;
  purchase_context?: string;
  pets?: string;
  neighborhood?: string;
  referral_potential?: string;
  personal_notes?: string;
  communication_preference?: string;
}

const FIELDS: { key: string; label: string; icon: string; multi?: boolean }[] = [
  { key: 'spouse_name', label: 'Spouse Name', icon: 'heart' },
  { key: 'spouse_details', label: 'Spouse Details', icon: 'heart-outline' },
  { key: 'kids_text', label: 'Kids (comma separated: name|details)', icon: 'people' },
  { key: 'interests_text', label: 'Interests (comma separated)', icon: 'golf' },
  { key: 'occupation', label: 'Occupation', icon: 'briefcase' },
  { key: 'employer', label: 'Employer', icon: 'business' },
  { key: 'vehicle_purchased', label: 'Vehicle', icon: 'car' },
  { key: 'vehicle_color', label: 'Vehicle Color', icon: 'color-palette' },
  { key: 'vehicle_details', label: 'Vehicle Details', icon: 'car-outline' },
  { key: 'trade_in', label: 'Trade-in', icon: 'swap-horizontal' },
  { key: 'purchase_context', label: 'Why They Bought', icon: 'chatbox-ellipses', multi: true },
  { key: 'pets', label: 'Pets', icon: 'paw' },
  { key: 'neighborhood', label: 'Area / Neighborhood', icon: 'location' },
  { key: 'referral_potential', label: 'Referral Potential', icon: 'people-circle' },
  { key: 'personal_notes', label: 'Notes', icon: 'document-text', multi: true },
  { key: 'communication_preference', label: 'Comm. Preference', icon: 'chatbubbles' },
];

function kidsToText(kids?: Kid[]): string {
  if (!kids?.length) return '';
  return kids.map(k => k.details ? `${k.name}|${k.details}` : k.name).join(', ');
}

function textToKids(text: string): Kid[] {
  if (!text.trim()) return [];
  return text.split(',').map(s => {
    const [name, ...rest] = s.trim().split('|');
    return { name: name.trim(), details: rest.join('|').trim() || undefined };
  }).filter(k => k.name);
}

function detailsToForm(d: PersonalDetails): Record<string, string> {
  return {
    spouse_name: d.spouse_name || '',
    spouse_details: d.spouse_details || '',
    kids_text: kidsToText(d.kids),
    interests_text: (d.interests || []).join(', '),
    occupation: d.occupation || '',
    employer: d.employer || '',
    vehicle_purchased: d.vehicle_purchased || '',
    vehicle_color: d.vehicle_color || '',
    vehicle_details: d.vehicle_details || '',
    trade_in: d.trade_in || '',
    purchase_context: d.purchase_context || '',
    pets: d.pets || '',
    neighborhood: d.neighborhood || '',
    referral_potential: d.referral_potential || '',
    personal_notes: d.personal_notes || '',
    communication_preference: d.communication_preference || '',
  };
}

function formToPayload(form: Record<string, string>): PersonalDetails {
  const p: PersonalDetails = {};
  if (form.spouse_name?.trim()) p.spouse_name = form.spouse_name.trim();
  if (form.spouse_details?.trim()) p.spouse_details = form.spouse_details.trim();
  const kids = textToKids(form.kids_text || '');
  if (kids.length) p.kids = kids;
  const interests = (form.interests_text || '').split(',').map(s => s.trim()).filter(Boolean);
  if (interests.length) p.interests = interests;
  if (form.occupation?.trim()) p.occupation = form.occupation.trim();
  if (form.employer?.trim()) p.employer = form.employer.trim();
  if (form.vehicle_purchased?.trim()) p.vehicle_purchased = form.vehicle_purchased.trim();
  if (form.vehicle_color?.trim()) p.vehicle_color = form.vehicle_color.trim();
  if (form.vehicle_details?.trim()) p.vehicle_details = form.vehicle_details.trim();
  if (form.trade_in?.trim()) p.trade_in = form.trade_in.trim();
  if (form.purchase_context?.trim()) p.purchase_context = form.purchase_context.trim();
  if (form.pets?.trim()) p.pets = form.pets.trim();
  if (form.neighborhood?.trim()) p.neighborhood = form.neighborhood.trim();
  if (form.referral_potential?.trim()) p.referral_potential = form.referral_potential.trim();
  if (form.personal_notes?.trim()) p.personal_notes = form.personal_notes.trim();
  if (form.communication_preference?.trim()) p.communication_preference = form.communication_preference.trim();
  return p;
}

// View mode display items
function buildViewItems(d: PersonalDetails): { label: string; value: string; icon: string }[] {
  const items: { label: string; value: string; icon: string }[] = [];
  if (d.spouse_name) items.push({ label: 'Spouse', value: `${d.spouse_name}${d.spouse_details ? ` — ${d.spouse_details}` : ''}`, icon: 'heart' });
  if (d.kids?.length) items.push({ label: 'Kids', value: d.kids.map(k => `${k.name}${k.details ? ` (${k.details})` : ''}`).join(', '), icon: 'people' });
  if (d.interests?.length) items.push({ label: 'Interests', value: d.interests.join(', '), icon: 'golf' });
  if (d.occupation) items.push({ label: 'Work', value: `${d.occupation}${d.employer ? ` at ${d.employer}` : ''}`, icon: 'briefcase' });
  if (d.vehicle_purchased) items.push({ label: 'Vehicle', value: `${d.vehicle_purchased}${d.vehicle_color ? ` (${d.vehicle_color})` : ''}${d.vehicle_details ? ` — ${d.vehicle_details}` : ''}`, icon: 'car' });
  if (d.trade_in) items.push({ label: 'Trade-in', value: d.trade_in, icon: 'swap-horizontal' });
  if (d.purchase_context) items.push({ label: 'Why they bought', value: d.purchase_context, icon: 'chatbox-ellipses' });
  if (d.pets) items.push({ label: 'Pets', value: d.pets, icon: 'paw' });
  if (d.neighborhood) items.push({ label: 'Area', value: d.neighborhood, icon: 'location' });
  if (d.referral_potential) items.push({ label: 'Referral lead', value: d.referral_potential, icon: 'people-circle' });
  if (d.personal_notes) items.push({ label: 'Notes', value: d.personal_notes, icon: 'document-text' });
  if (d.communication_preference) items.push({ label: 'Prefers', value: d.communication_preference, icon: 'chatbubbles' });
  return items;
}

export default function PersonalIntelSection({ contactId, userId, colors }: { contactId: string; userId: string; colors: any }) {
  const { showToast } = useToast();
  const [details, setDetails] = useState<PersonalDetails | null>(null);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    if (!contactId || !userId || loaded) return;
    setLoading(true);
    try {
      const res = await api.get(`/contacts/${userId}/${contactId}/personal-details`);
      setDetails(res.data.personal_details || {});
    } catch { /* ignore */ }
    setLoading(false);
    setLoaded(true);
  }, [contactId, userId, loaded]);

  useEffect(() => { load(); }, [load]);

  const startEdit = () => {
    setForm(detailsToForm(details || {}));
    setEditing(true);
  };

  const cancelEdit = () => {
    setEditing(false);
    setForm({});
  };

  const save = async () => {
    setSaving(true);
    try {
      const payload = formToPayload(form);
      const res = await api.patch(`/contacts/${userId}/${contactId}/personal-details`, { personal_details: payload });
      setDetails(res.data.personal_details || {});
      setEditing(false);
      showToast('Personal details saved!', 'success');
    } catch {
      showToast('Failed to save details', 'error');
    }
    setSaving(false);
  };

  const updateField = (key: string, val: string) => {
    setForm(prev => ({ ...prev, [key]: val }));
  };

  if (loading || !loaded) return null;

  const hasData = details && Object.keys(details).length > 0;

  // No data and not editing — show "Add" prompt
  if (!hasData && !editing) {
    return (
      <View style={{ paddingHorizontal: 16, marginBottom: 16 }} data-testid="personal-intel-section">
        <TouchableOpacity
          onPress={startEdit}
          style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 10, paddingHorizontal: 14, borderRadius: 8, borderWidth: 1, borderColor: '#AF52DE40', borderStyle: 'dashed' }}
          data-testid="add-personal-intel-btn"
        >
          <Ionicons name="sparkles" size={16} color="#AF52DE" />
          <Text style={{ color: '#AF52DE', fontSize: 13, fontWeight: '600' }}>Add Personal Intelligence</Text>
          <Ionicons name="add-circle-outline" size={16} color="#AF52DE" style={{ marginLeft: 'auto' }} />
        </TouchableOpacity>
      </View>
    );
  }

  // Edit mode
  if (editing) {
    return (
      <View style={{ paddingHorizontal: 16, marginBottom: 16 }} data-testid="personal-intel-section">
        <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            <Ionicons name="sparkles" size={14} color="#AF52DE" />
            <Text style={{ color: '#AF52DE', fontSize: 12, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5 }}>Edit Personal Intelligence</Text>
          </View>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <TouchableOpacity onPress={cancelEdit} disabled={saving} style={{ paddingHorizontal: 12, paddingVertical: 6, borderRadius: 6, backgroundColor: colors.border }} data-testid="cancel-edit-intel-btn">
              <Text style={{ color: colors.text, fontSize: 12, fontWeight: '600' }}>Cancel</Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={save} disabled={saving} style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 12, paddingVertical: 6, borderRadius: 6, backgroundColor: '#AF52DE' }} data-testid="save-intel-btn">
              {saving ? <ActivityIndicator size="small" color="#fff" /> : <Ionicons name="checkmark" size={14} color="#fff" />}
              <Text style={{ color: '#fff', fontSize: 12, fontWeight: '600' }}>{saving ? 'Saving...' : 'Save'}</Text>
            </TouchableOpacity>
          </View>
        </View>

        {FIELDS.map(f => (
          <View key={f.key} style={{ marginBottom: 10 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 4 }}>
              <Ionicons name={f.icon as any} size={13} color="#C9A962" />
              <Text style={{ color: '#8E8E93', fontSize: 10, textTransform: 'uppercase', letterSpacing: 0.5 }}>{f.label}</Text>
            </View>
            <TextInput
              value={form[f.key] || ''}
              onChangeText={v => updateField(f.key, v)}
              placeholder={f.label}
              placeholderTextColor="#666"
              multiline={f.multi}
              numberOfLines={f.multi ? 3 : 1}
              style={{
                backgroundColor: colors.card,
                color: colors.text,
                fontSize: 13,
                paddingHorizontal: 12,
                paddingVertical: 8,
                borderRadius: 6,
                borderWidth: 1,
                borderColor: colors.border,
                minHeight: f.multi ? 60 : 36,
                textAlignVertical: f.multi ? 'top' : 'center',
              }}
              data-testid={`intel-input-${f.key}`}
            />
          </View>
        ))}
      </View>
    );
  }

  // View mode
  const items = buildViewItems(details!);
  if (items.length === 0) return null;

  return (
    <View style={{ paddingHorizontal: 16, marginBottom: 16 }} data-testid="personal-intel-section">
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
          <Ionicons name="sparkles" size={14} color="#AF52DE" />
          <Text style={{ color: '#AF52DE', fontSize: 12, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5 }}>Personal Intelligence</Text>
          <Text style={{ color: '#555', fontSize: 10, fontStyle: 'italic', marginLeft: 4 }}>from voice memos</Text>
        </View>
        <TouchableOpacity onPress={startEdit} style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 4, borderRadius: 6, backgroundColor: '#AF52DE18' }} data-testid="edit-intel-btn">
          <Ionicons name="create-outline" size={13} color="#AF52DE" />
          <Text style={{ color: '#AF52DE', fontSize: 11, fontWeight: '600' }}>Edit</Text>
        </TouchableOpacity>
      </View>
      {items.map((item, i) => (
        <View key={i} style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 10, paddingVertical: 6, borderBottomWidth: i < items.length - 1 ? 1 : 0, borderBottomColor: colors.border }} data-testid={`personal-detail-${item.label.toLowerCase().replace(/\s/g, '-')}`}>
          <Ionicons name={item.icon as any} size={15} color="#C9A962" style={{ marginTop: 2, width: 18 }} />
          <View style={{ flex: 1 }}>
            <Text style={{ color: '#8E8E93', fontSize: 10, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 2 }}>{item.label}</Text>
            <Text style={{ color: colors.text, fontSize: 13, lineHeight: 18 }}>{item.value}</Text>
          </View>
        </View>
      ))}
    </View>
  );
}
