/**
 * app/contact/new.tsx — New Contact creation screen.
 *
 * Expo Router routes `/contact/new` here automatically (preferred over [id].tsx).
 * This page is 100% standalone — it owns all its own state and handlers.
 * No state shared with contact/[id].tsx.
 *
 * Flow: Fill form → Done → navigates to /contact/{newId}
 */

import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ScrollView, KeyboardAvoidingView, Platform,
  ActivityIndicator, Modal, FlatList,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { Image } from 'expo-image';
import * as ImagePicker from 'expo-image-picker';
import * as DeviceContacts from 'expo-contacts';
import { Audio } from 'expo-av';
import { format } from 'date-fns';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { contactsAPI, tagsAPI } from '../../services/api';
import api from '../../services/api';
import { showSimpleAlert, showConfirm } from '../../services/alert';
import { useToast } from '../../components/common/Toast';
import { getS } from '../../components/contact/contactStyles';

const IS_WEB = Platform.OS === 'web';

const EMPTY_CONTACT = {
  first_name: '', last_name: '', phone: '', email: '',
  photo: null as string | null,
  notes: '', vehicle: '',
  tags: [] as string[],
  referred_by: null as string | null, referred_by_name: null as string | null,
  address_street: '', address_city: '', address_state: '', address_zip: '',
  birthday: null as Date | null, anniversary: null as Date | null, date_sold: null as Date | null,
  custom_dates: [] as { name: string; date: Date | null }[],
  ownership_type: 'org' as string,
};

export default function NewContactScreen() {
  const { colors } = useThemeStore();
  const s = getS(colors);
  const router = useRouter();
  const user = useAuthStore(st => st.user);
  const { showToast } = useToast();

  // ── Contact form state ────────────────────────────────────────────────────
  const [contact, setContact] = useState({ ...EMPTY_CONTACT });
  const [saving, setSaving] = useState(false);
  const [showMoreDetails, setShowMoreDetails] = useState(false);
  const [duplicateMatches, setDuplicateMatches] = useState<any[]>([]);
  const dupCheckTimer = useRef<any>(null);

  // ── Photo ──────────────────────────────────────────────────────────────────
  const pickImage = async () => {
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: true, aspect: [1, 1], quality: 0.5, base64: true,
      });
      if (!result.canceled && result.assets?.[0]) {
        const asset = result.assets[0];
        const photoData = asset.base64
          ? `data:image/jpeg;base64,${asset.base64}`
          : asset.uri || null;
        if (photoData) {
          setContact(prev => ({ ...prev, photo: photoData }));
          showToast('Photo selected! Tap Done to save.', 'info');
        }
      }
    } catch (e) {
      showToast('Failed to pick photo. Please try again.', 'error');
    }
  };

  // ── Tags ───────────────────────────────────────────────────────────────────
  const [availableTags, setAvailableTags] = useState<any[]>([]);
  const [showTagPicker, setShowTagPicker] = useState(false);
  const [tagSearch, setTagSearch] = useState('');

  const loadTags = async () => {
    if (!user) return;
    try { setAvailableTags(await tagsAPI.getAll(user._id)); } catch {}
  };

  const addTag = (name: string) => {
    if (!contact.tags.includes(name)) setContact(prev => ({ ...prev, tags: [...prev.tags, name] }));
    setShowTagPicker(false); setTagSearch('');
  };

  const removeTag = (tag: string) => {
    setContact(prev => ({ ...prev, tags: prev.tags.filter(t => t !== tag) }));
  };

  const filteredAvailableTags = availableTags.filter(
    t => !contact.tags.includes(t.name) && t.name.toLowerCase().includes(tagSearch.toLowerCase())
  );

  // ── Referral ───────────────────────────────────────────────────────────────
  const [allContacts, setAllContacts] = useState<any[]>([]);
  const [contactSearch, setContactSearch] = useState('');
  const [showReferralPicker, setShowReferralPicker] = useState(false);

  const loadAllContacts = async () => {
    if (!user) return;
    try {
      const data = await contactsAPI.getAll(user._id);
      setAllContacts(Array.isArray(data) ? data : (data?.contacts || []));
    } catch {}
  };

  const filteredContacts = useMemo(() =>
    contactSearch.trim()
      ? allContacts.filter(c => {
          const name = `${c.first_name || ''} ${c.last_name || ''}`.toLowerCase();
          return name.includes(contactSearch.toLowerCase()) || (c.phone || '').includes(contactSearch);
        })
      : allContacts,
    [allContacts, contactSearch]
  );

  // ── Date picker ────────────────────────────────────────────────────────────
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [activeDateField, setActiveDateField] = useState<string | null>(null);
  const [activeDateLabel, setActiveDateLabel] = useState('');
  const [tempDate, setTempDate] = useState(new Date());
  const [webMonth, setWebMonth] = useState(new Date().getMonth());
  const [webDay, setWebDay] = useState(new Date().getDate());
  const [webYear, setWebYear] = useState(new Date().getFullYear());

  const openDatePicker = (field: string, currentDate: Date | null, label?: string) => {
    const d = currentDate || new Date();
    setActiveDateField(field);
    setActiveDateLabel(label || field);
    setTempDate(d);
    setWebMonth(d.getMonth()); setWebDay(d.getDate()); setWebYear(d.getFullYear());
    setShowDatePicker(true);
  };

  const confirmDateSelection = () => {
    const dateToUse = Platform.OS === 'web' ? new Date(webYear, webMonth, webDay) : tempDate;
    if (activeDateField) {
      setContact(prev => ({ ...prev, [activeDateField]: dateToUse }));
    }
    setShowDatePicker(false); setActiveDateField(null);
  };

  // ── Voice note for new contact ─────────────────────────────────────────────
  const [ncVoiceRecording, setNcVoiceRecording] = useState(false);
  const [ncVoiceTranscribing, setNcVoiceTranscribing] = useState(false);
  const ncVoiceRef = useRef<any>(null);
  const ncVoiceAudioBlob = useRef<Blob | null>(null);
  const ncScrollRef = useRef<ScrollView>(null);

  const handleVoice = async () => {
    try {
      if (ncVoiceRecording) {
        setNcVoiceRecording(false);
        if (ncVoiceRef.current) {
          setNcVoiceTranscribing(true);
          await ncVoiceRef.current.stopAndUnloadAsync();
          const uri = ncVoiceRef.current.getURI();
          ncVoiceRef.current = null;
          if (uri) {
            const formData = new FormData();
            if (IS_WEB) {
              const resp = await fetch(uri);
              const blob = await resp.blob();
              ncVoiceAudioBlob.current = blob;
              formData.append('file', blob, 'recording.webm');
            } else {
              ncVoiceAudioBlob.current = { uri, type: 'audio/m4a', name: 'recording.m4a' } as any;
              formData.append('file', { uri, type: 'audio/m4a', name: 'recording.m4a' } as any);
            }
            try {
              const response = await api.post('/voice/transcribe', formData, {
                
              });
              if (response.data.success && response.data.text) {
                setContact(prev => ({
                  ...prev,
                  notes: prev.notes ? `${prev.notes}\n${response.data.text}` : response.data.text,
                }));
              }
            } catch {}
          }
          setNcVoiceTranscribing(false);
        }
      } else {
        const { status } = await Audio.requestPermissionsAsync();
        if (status !== 'granted') { showSimpleAlert('Permission Denied', 'Microphone permission required.'); return; }
        await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true });
        const opts = IS_WEB
          ? { ...Audio.RecordingOptionsPresets.HIGH_QUALITY, isMeteringEnabled: false, web: { mimeType: 'audio/webm;codecs=opus', bitsPerSecond: 128000 } }
          : Audio.RecordingOptionsPresets.HIGH_QUALITY;
        const recording = new Audio.Recording();
        await recording.prepareToRecordAsync(opts);
        await recording.startAsync();
        ncVoiceRef.current = recording;
        ncVoiceAudioBlob.current = null;
        setNcVoiceRecording(true);
      }
    } catch {
      setNcVoiceRecording(false); setNcVoiceTranscribing(false);
    }
  };

  // ── Device contacts ────────────────────────────────────────────────────────
  const [showDeviceContacts, setShowDeviceContacts] = useState(false);
  const [deviceContacts, setDeviceContacts] = useState<DeviceContacts.Contact[]>([]);
  const [deviceContactSearch, setDeviceContactSearch] = useState('');
  const [loadingDeviceContacts, setLoadingDeviceContacts] = useState(false);
  const [selectedDeviceIds, setSelectedDeviceIds] = useState<Set<string>>(new Set());
  const [bulkImporting, setBulkImporting] = useState(false);

  const loadDeviceContacts = useCallback(async () => {
    setLoadingDeviceContacts(true);
    try {
      const { status } = await DeviceContacts.requestPermissionsAsync();
      if (status !== 'granted') { showSimpleAlert('Permission Needed', 'Allow contacts access in your device Settings.'); return; }
      const { data } = await DeviceContacts.getContactsAsync({
        fields: [
          DeviceContacts.Fields.FirstName, DeviceContacts.Fields.LastName,
          DeviceContacts.Fields.PhoneNumbers, DeviceContacts.Fields.Emails,
          DeviceContacts.Fields.Image, DeviceContacts.Fields.Birthday,
          DeviceContacts.Fields.Company, DeviceContacts.Fields.JobTitle,
          DeviceContacts.Fields.Addresses,
        ],
      });
      setDeviceContacts(data || []);
      setSelectedDeviceIds(new Set());
      setShowDeviceContacts(true);
    } catch { showSimpleAlert('Error', 'Could not load phone contacts. Check your permissions in Settings.'); }
    finally { setLoadingDeviceContacts(false); }
  }, []);

  const filteredDeviceContactsList = useMemo(() => {
    const list = deviceContactSearch.trim()
      ? deviceContacts.filter(dc => {
          const name = `${dc.firstName || ''} ${dc.lastName || ''}`.toLowerCase();
          return name.includes(deviceContactSearch.toLowerCase()) || (dc.phoneNumbers?.[0]?.number || '').includes(deviceContactSearch);
        })
      : deviceContacts;
    return list.slice(0, 100);
  }, [deviceContacts, deviceContactSearch]);

  const selectDeviceContact = useCallback((dc: DeviceContacts.Contact) => {
    const addr = dc.addresses?.[0];
    const bday = dc.birthday;
    setContact(prev => ({
      ...prev,
      first_name: dc.firstName || prev.first_name,
      last_name: dc.lastName || prev.last_name,
      phone: dc.phoneNumbers?.[0]?.number || prev.phone,
      email: dc.emails?.[0]?.email || prev.email,
      address_street: addr?.street || prev.address_street,
      address_city: addr?.city || prev.address_city,
      address_state: addr?.region || prev.address_state,
      address_zip: addr?.postalCode || prev.address_zip,
      birthday: bday ? new Date(`${bday.year || new Date().getFullYear()}-${String((bday.month || 0) + 1).padStart(2,'0')}-${String(bday.day).padStart(2,'0')}`) : prev.birthday,
      photo: dc.image?.uri || prev.photo,
    }));
    setShowDeviceContacts(false); setDeviceContactSearch(''); setSelectedDeviceIds(new Set());
  }, []);

  const toggleDeviceContact = useCallback((dcId: string) => {
    setSelectedDeviceIds(prev => {
      const next = new Set(prev);
      if (next.has(dcId)) next.delete(dcId); else next.add(dcId);
      return next;
    });
  }, []);

  const toggleSelectAllVisible = useCallback(() => {
    setSelectedDeviceIds(prev => {
      const ids = filteredDeviceContactsList.map(dc => dc.id!).filter(Boolean);
      const allSel = ids.length > 0 && ids.every(id => prev.has(id));
      return allSel ? new Set() : new Set(ids);
    });
  }, [filteredDeviceContactsList]);

  const handleBulkImport = useCallback(async () => {
    if (!user || selectedDeviceIds.size === 0) return;
    const selected = deviceContacts.filter(dc => dc.id && selectedDeviceIds.has(dc.id));
    const payload = selected.map(dc => ({
      first_name: dc.firstName || '', last_name: dc.lastName || '',
      phone: dc.phoneNumbers?.[0]?.number || '',
      email: dc.emails?.[0]?.email || '',
      address_street: dc.addresses?.[0]?.street || '',
      address_city: dc.addresses?.[0]?.city || '',
      address_state: dc.addresses?.[0]?.region || '',
      address_zip: dc.addresses?.[0]?.postalCode || '',
    })).filter(c => c.first_name || c.last_name || c.phone);

    if (payload.length === 0) { showSimpleAlert('No valid contacts to import', ''); return; }
    try {
      setBulkImporting(true);
      const res = await api.post(`/contacts/${user._id}/import?source=phone_import`, payload);
      const count = res.data?.imported || payload.length;
      showSimpleAlert(`Imported ${count} contact${count !== 1 ? 's' : ''}!`, '');
      setShowDeviceContacts(false); setSelectedDeviceIds(new Set()); setDeviceContactSearch('');
      router.back();
    } catch (e: any) { showSimpleAlert(e?.response?.data?.detail || 'Import failed', ''); }
    finally { setBulkImporting(false); }
  }, [selectedDeviceIds, deviceContacts, user, router]);

  // ── Duplicate detection ────────────────────────────────────────────────────
  const checkDuplicate = useCallback(async (phone: string, email: string) => {
    if (!user) return;
    const params = new URLSearchParams();
    if (phone?.replace(/\D/g, '').length >= 7) params.set('phone', phone);
    if (email?.length >= 3 && email.includes('@')) params.set('email', email);
    if (!params.toString()) { setDuplicateMatches([]); return; }
    try {
      const res = await api.get(`/contacts/${user._id}/check-duplicate?${params.toString()}`);
      setDuplicateMatches(res.data.matches || []);
    } catch { setDuplicateMatches([]); }
  }, [user]);

  const onPhoneOrEmailChange = useCallback((field: 'phone' | 'email', value: string) => {
    setContact(prev => ({ ...prev, [field]: value }));
    clearTimeout(dupCheckTimer.current);
    dupCheckTimer.current = setTimeout(() => {
      setContact(prev => {
        const p = field === 'phone' ? value : prev.phone;
        const e = field === 'email' ? value : prev.email;
        checkDuplicate(p, e);
        return prev;
      });
    }, 500);
  }, [checkDuplicate]);

  // ── Save ───────────────────────────────────────────────────────────────────
  const handleSave = async () => {
    if (!contact.first_name) { showSimpleAlert('Error', 'First name is required'); return; }
    if (!contact.phone && !contact.email) { showSimpleAlert('Error', 'Please provide a phone number or email'); return; }
    if (!user) return;
    try {
      setSaving(true);
      const result = await contactsAPI.create(user._id, contact);
      showToast('Contact saved!', 'success');
      const newId = result?._id || result?.id;

      // Upload the voice recording if one was made
      if (newId && ncVoiceAudioBlob.current) {
        try {
          const formData = new FormData();
          if (IS_WEB && ncVoiceAudioBlob.current instanceof Blob) {
            formData.append('audio', ncVoiceAudioBlob.current, 'recording.webm');
          } else {
            formData.append('audio', ncVoiceAudioBlob.current as any);
          }
          formData.append('duration', '0');
          await api.post(`/voice-notes/${user._id}/${newId}`, formData, {
            
          });
          ncVoiceAudioBlob.current = null;
        } catch {}
      }

      if (newId) router.replace(`/contact/${newId}` as any);
      else router.back();
    } catch (e: any) {
      showSimpleAlert('Error', e?.response?.data?.detail || e?.message || 'Failed to save contact.');
    } finally {
      setSaving(false);
    }
  };

  // ── Inline card styles (shared across all ncs.* usage) ────────────────────
  const ncs = {
    card: { backgroundColor: colors.card, borderRadius: 12, marginHorizontal: 16, marginBottom: 12, borderWidth: 1, borderColor: colors.border, overflow: 'hidden' as const },
    cardInput: { fontSize: 18, color: colors.text, paddingVertical: 14, paddingHorizontal: 16 },
    cardDivider: { height: 1, backgroundColor: colors.border, marginLeft: 16 },
    cardRow: { flexDirection: 'row' as const, alignItems: 'center' as const, paddingVertical: 12, paddingHorizontal: 16 },
    cardRowIcon: { width: 28, marginRight: 10 },
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <SafeAreaView style={[s.container, { backgroundColor: colors.bg }]} edges={['top']}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>

        {/* Header */}
        <View style={[s.header, { borderBottomColor: colors.border }]} data-testid="new-contact-header">
          <TouchableOpacity onPress={() => router.back()} style={s.headerBtn} data-testid="new-contact-cancel">
            <Text style={{ fontSize: 18, color: '#007AFF' }}>Cancel</Text>
          </TouchableOpacity>
          <Text style={[s.headerTitle, { color: colors.text }]}>New Contact</Text>
          <TouchableOpacity
            onPress={handleSave}
            style={[s.headerBtn, { backgroundColor: (contact.first_name && (contact.phone || contact.email)) ? '#C9A962' : colors.card, borderRadius: 8, paddingHorizontal: 16, paddingVertical: 6 }]}
            disabled={saving || !contact.first_name}
            data-testid="new-contact-done"
          >
            {saving
              ? <ActivityIndicator size="small" color="#000" />
              : <Text style={{ fontSize: 18, fontWeight: '700', color: (contact.first_name && (contact.phone || contact.email)) ? '#000' : colors.textTertiary }}>Done</Text>
            }
          </TouchableOpacity>
        </View>

        <ScrollView ref={ncScrollRef} contentContainerStyle={{ paddingBottom: 80 }} showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled">

          {/* Photo */}
          <View style={{ alignItems: 'center', paddingTop: 24, paddingBottom: 20 }}>
            <TouchableOpacity onPress={pickImage} activeOpacity={0.7} data-testid="new-contact-photo">
              {contact.photo ? (
                <Image source={{ uri: contact.photo }} style={{ width: 100, height: 100, borderRadius: 50, borderWidth: 2, borderColor: '#C9A962' }} />
              ) : (
                <View style={{ width: 100, height: 100, borderRadius: 50, backgroundColor: colors.card, borderWidth: 2, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }}>
                  <Ionicons name="camera" size={32} color={colors.textTertiary} />
                </View>
              )}
            </TouchableOpacity>
            <TouchableOpacity onPress={pickImage} style={{ marginTop: 8 }}>
              <Text style={{ fontSize: 15, color: '#007AFF', fontWeight: '600' }}>{contact.photo ? 'Change Photo' : 'Add Photo'}</Text>
            </TouchableOpacity>
          </View>

          {/* Import from Phone Contacts */}
          {!IS_WEB && (
            <TouchableOpacity
              onPress={loadDeviceContacts}
              style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, marginBottom: 16, paddingVertical: 10, marginHorizontal: 16, borderRadius: 10, borderWidth: 1, borderColor: '#C9A962' }}
              disabled={loadingDeviceContacts}
              data-testid="import-phone-contact-btn"
            >
              {loadingDeviceContacts ? <ActivityIndicator size="small" color="#C9A962" /> : <Ionicons name="person-add-outline" size={18} color="#C9A962" />}
              <Text style={{ fontSize: 16, fontWeight: '600', color: '#C9A962' }}>Import from Phone Contacts</Text>
            </TouchableOpacity>
          )}

          {/* Name */}
          <View style={ncs.card}>
            <TextInput style={ncs.cardInput} placeholder="First name" placeholderTextColor={colors.textTertiary}
              value={contact.first_name} onChangeText={t => setContact(p => ({ ...p, first_name: t }))}
              autoFocus returnKeyType="next" data-testid="input-first-name" />
            <View style={ncs.cardDivider} />
            <TextInput style={ncs.cardInput} placeholder="Last name" placeholderTextColor={colors.textTertiary}
              value={contact.last_name} onChangeText={t => setContact(p => ({ ...p, last_name: t }))}
              returnKeyType="next" data-testid="input-last-name" />
          </View>

          {/* Contact Info */}
          <View style={ncs.card}>
            <View style={ncs.cardRow}>
              <Ionicons name="call-outline" size={20} color="#34C759" style={ncs.cardRowIcon} />
              <TextInput style={[ncs.cardInput, { flex: 1 }]} placeholder="Phone" placeholderTextColor={colors.textTertiary}
                value={contact.phone} onChangeText={t => onPhoneOrEmailChange('phone', t)}
                keyboardType="phone-pad" returnKeyType="next" data-testid="input-phone" />
            </View>
            <View style={ncs.cardDivider} />
            <View style={ncs.cardRow}>
              <Ionicons name="mail-outline" size={20} color="#007AFF" style={ncs.cardRowIcon} />
              <TextInput style={[ncs.cardInput, { flex: 1 }]} placeholder="Email" placeholderTextColor={colors.textTertiary}
                value={contact.email} onChangeText={t => onPhoneOrEmailChange('email', t)}
                keyboardType="email-address" autoCapitalize="none" returnKeyType="next" data-testid="input-email" />
            </View>
          </View>

          {/* Duplicate match banner */}
          {duplicateMatches.length > 0 && (
            <View style={{ marginHorizontal: 16, marginBottom: 12, borderRadius: 12, backgroundColor: '#FF950020', borderWidth: 1, borderColor: '#FF9500', overflow: 'hidden' }} data-testid="duplicate-match-banner">
              <View style={{ padding: 12 }}>
                <Text style={{ fontSize: 16, fontWeight: '700', color: '#FF9500', marginBottom: 6 }}>Existing Contact Found</Text>
                {duplicateMatches.map((m: any) => (
                  <TouchableOpacity key={m.id}
                    style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: 8, borderTopWidth: 1, borderTopColor: '#FF950030' }}
                    onPress={() => router.replace(`/contact/${m.id}` as any)} data-testid={`duplicate-match-${m.id}`}
                  >
                    <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center', marginRight: 10 }}>
                      <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text }}>{(m.first_name || '?')[0]}</Text>
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={{ fontSize: 17, fontWeight: '600', color: colors.text }}>{m.first_name} {m.last_name}</Text>
                      <Text style={{ fontSize: 15, color: colors.textSecondary }}>{m.phone || m.email}</Text>
                    </View>
                    <Ionicons name="chevron-forward" size={18} color="#FF9500" />
                  </TouchableOpacity>
                ))}
              </View>
            </View>
          )}

          {/* Vehicle */}
          <View style={ncs.card}>
            <View style={ncs.cardRow}>
              <Ionicons name="car-outline" size={20} color="#FF9500" style={ncs.cardRowIcon} />
              <TextInput style={[ncs.cardInput, { flex: 1 }]} placeholder="Vehicle (e.g., 2023 Toyota RAV4)"
                placeholderTextColor={colors.textTertiary} value={contact.vehicle}
                onChangeText={t => setContact(p => ({ ...p, vehicle: t }))} data-testid="input-vehicle" />
            </View>
          </View>

          {/* Referral */}
          <View style={ncs.card}>
            <TouchableOpacity style={ncs.cardRow} onPress={() => { loadAllContacts(); setShowReferralPicker(true); }} data-testid="new-contact-referral">
              <Ionicons name="people-outline" size={20} color="#AF52DE" style={ncs.cardRowIcon} />
              <View style={{ flex: 1 }}>
                {contact.referred_by_name
                  ? <Text style={{ fontSize: 18, color: colors.text }}>{contact.referred_by_name}</Text>
                  : <Text style={{ fontSize: 18, color: colors.textTertiary }}>Referred by</Text>
                }
              </View>
              <Ionicons name="chevron-forward" size={18} color={colors.textTertiary} />
            </TouchableOpacity>
          </View>

          {/* Notes */}
          <View style={ncs.card}>
            <View style={[ncs.cardRow, { alignItems: 'flex-start' }]}>
              <Ionicons name="document-text-outline" size={20} color="#FF9F0A" style={[ncs.cardRowIcon, { marginTop: 2 }]} />
              <TextInput style={[ncs.cardInput, { flex: 1, minHeight: 60, textAlignVertical: 'top' }]}
                placeholder="Notes" placeholderTextColor={colors.textTertiary}
                value={contact.notes} onChangeText={t => setContact(p => ({ ...p, notes: t }))}
                multiline data-testid="input-notes" />
            </View>
          </View>

          {/* Voice note recorder */}
          <View style={[ncs.card, { alignItems: 'center', paddingVertical: 12, paddingHorizontal: 16 }]}>
            <TouchableOpacity
              style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 10, paddingHorizontal: 20, borderRadius: 24, width: '100%',
                backgroundColor: ncVoiceRecording ? '#FF3B3020' : ncVoiceTranscribing ? colors.card : '#34C75920',
                borderWidth: 1, borderColor: ncVoiceRecording ? '#FF3B30' : ncVoiceTranscribing ? colors.border : '#34C759' }}
              onPress={handleVoice} disabled={ncVoiceTranscribing} data-testid="new-contact-voice-btn"
            >
              {ncVoiceTranscribing ? (
                <><ActivityIndicator size="small" color="#C9A962" style={{ marginRight: 8 }} /><Text style={{ fontSize: 17, fontWeight: '600', color: '#C9A962' }}>Transcribing...</Text></>
              ) : ncVoiceRecording ? (
                <><Ionicons name="stop-circle" size={22} color="#FF3B30" style={{ marginRight: 8 }} /><Text style={{ fontSize: 17, fontWeight: '600', color: '#FF3B30' }}>Stop Recording</Text></>
              ) : (
                <><Ionicons name="mic" size={22} color="#34C759" style={{ marginRight: 8 }} /><Text style={{ fontSize: 17, fontWeight: '600', color: '#34C759' }}>Record Voice Note</Text></>
              )}
            </TouchableOpacity>
            <Text style={{ fontSize: 14, color: colors.textTertiary, marginTop: 6, textAlign: 'center' }}>Record a voice memo — transcribed and added to notes</Text>
          </View>

          {/* Tags */}
          <View style={ncs.card}>
            <View style={[ncs.cardRow, { flexWrap: 'wrap', gap: 6 }]}>
              <Ionicons name="pricetag-outline" size={20} color="#5AC8FA" style={ncs.cardRowIcon} />
              {contact.tags.map((tag, i) => {
                const info = availableTags.find(t => t.name === tag);
                return (
                  <View key={i} style={[s.tagPill, info?.color && { borderColor: info.color }]}>
                    {info?.icon && <Ionicons name={info.icon as any} size={13} color={info.color || colors.textSecondary} />}
                    <Text style={[s.tagPillText, info?.color && { color: info.color }]}>{tag}</Text>
                    <TouchableOpacity onPress={() => removeTag(tag)} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
                      <Ionicons name="close-circle" size={15} color={colors.textSecondary} />
                    </TouchableOpacity>
                  </View>
                );
              })}
              <TouchableOpacity
                style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: '#007AFF15', borderRadius: 16, paddingHorizontal: 10, paddingVertical: 5 }}
                onPress={() => { loadTags(); setShowTagPicker(true); }} data-testid="new-contact-add-tag"
              >
                <Ionicons name="add" size={16} color="#007AFF" />
                <Text style={{ fontSize: 15, color: '#007AFF', fontWeight: '600', marginLeft: 2 }}>Tag</Text>
              </TouchableOpacity>
            </View>
          </View>

          {/* More Details */}
          {!showMoreDetails ? (
            <TouchableOpacity
              style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 14, marginHorizontal: 16, marginBottom: 16 }}
              onPress={() => setShowMoreDetails(true)} data-testid="new-contact-more-details"
            >
              <Ionicons name="add-circle-outline" size={18} color="#007AFF" style={{ marginRight: 6 }} />
              <Text style={{ fontSize: 17, color: '#007AFF', fontWeight: '500' }}>Add Address & Dates</Text>
            </TouchableOpacity>
          ) : (
            <>
              {/* Address */}
              <View style={ncs.card}>
                <View style={ncs.cardRow}>
                  <Ionicons name="location-outline" size={20} color="#FF3B30" style={ncs.cardRowIcon} />
                  <TextInput style={[ncs.cardInput, { flex: 1 }]} placeholder="Street" placeholderTextColor={colors.textTertiary}
                    value={contact.address_street} onChangeText={t => setContact(p => ({ ...p, address_street: t }))} data-testid="input-address-street" />
                </View>
                <View style={[ncs.cardDivider, { marginLeft: 40 }]} />
                <View style={{ flexDirection: 'row' }}>
                  <TextInput style={[ncs.cardInput, { flex: 1, marginLeft: 40 }]} placeholder="City" placeholderTextColor={colors.textTertiary}
                    value={contact.address_city} onChangeText={t => setContact(p => ({ ...p, address_city: t }))} data-testid="input-address-city" />
                  <TextInput style={[ncs.cardInput, { width: 60 }]} placeholder="ST" placeholderTextColor={colors.textTertiary}
                    value={contact.address_state} onChangeText={t => setContact(p => ({ ...p, address_state: t }))} autoCapitalize="characters" data-testid="input-address-state" />
                  <TextInput style={[ncs.cardInput, { width: 80 }]} placeholder="ZIP" placeholderTextColor={colors.textTertiary}
                    value={contact.address_zip} onChangeText={t => setContact(p => ({ ...p, address_zip: t }))} keyboardType="number-pad" data-testid="input-address-zip" />
                </View>
              </View>

              {/* Dates */}
              <View style={ncs.card}>
                {[
                  { field: 'birthday', label: 'Birthday', icon: 'gift', color: '#FF9500' },
                  { field: 'anniversary', label: 'Anniversary', icon: 'heart', color: '#FF2D55' },
                  { field: 'date_sold', label: 'Date Sold', icon: 'car', color: '#34C759' },
                ].map((d, idx) => (
                  <React.Fragment key={d.field}>
                    {idx > 0 && <View style={[ncs.cardDivider, { marginLeft: 40 }]} />}
                    <TouchableOpacity style={ncs.cardRow} onPress={() => openDatePicker(d.field, (contact as any)[d.field], d.label)}>
                      <View style={{ width: 28, height: 28, borderRadius: 7, alignItems: 'center', justifyContent: 'center', marginRight: 12, backgroundColor: `${d.color}20` }}>
                        <Ionicons name={d.icon as any} size={16} color={d.color} />
                      </View>
                      <Text style={{ flex: 1, fontSize: 18, color: (contact as any)[d.field] ? colors.text : colors.textTertiary }}>
                        {(contact as any)[d.field] ? format(new Date((contact as any)[d.field]), 'MMM d, yyyy') : d.label}
                      </Text>
                    </TouchableOpacity>
                  </React.Fragment>
                ))}
              </View>
            </>
          )}

        </ScrollView>
      </KeyboardAvoidingView>

      {/* ── Tag Picker Modal ── */}
      <Modal visible={showTagPicker} animationType="slide" transparent>
        <TouchableOpacity style={s.actionSheetOverlay} activeOpacity={1} onPress={() => setShowTagPicker(false)}>
          <View style={s.actionSheetContainer} onStartShouldSetResponder={() => true}>
            <View style={s.actionSheetGroup}>
              <View style={{ padding: 16 }}>
                <Text style={{ fontSize: 18, fontWeight: '600', color: colors.text, marginBottom: 12 }}>Add Tag</Text>
                <TextInput style={[s.input, { marginBottom: 12 }]} placeholder="Search or create a tag..."
                  placeholderTextColor={colors.textTertiary} value={tagSearch} onChangeText={setTagSearch} />
                <ScrollView style={{ maxHeight: 250 }}>
                  {tagSearch.trim() && !availableTags.some(t => t.name.toLowerCase() === tagSearch.trim().toLowerCase()) && (
                    <TouchableOpacity style={[s.pickerItem, { backgroundColor: '#007AFF10' }]}
                      onPress={async () => {
                        const newName = tagSearch.trim();
                        try {
                          await api.post(`/tags/${user?._id}`, { name: newName, color: '#C9A962', icon: 'pricetag' });
                          addTag(newName); loadTags();
                          showToast(`Tag "${newName}" created!`, 'success');
                        } catch (e: any) { showSimpleAlert('Error', e?.response?.data?.detail || 'Failed to create tag'); }
                      }} data-testid="create-new-tag-btn"
                    >
                      <Ionicons name="add-circle" size={22} color="#007AFF" />
                      <Text style={{ fontSize: 18, fontWeight: '600', color: '#007AFF' }}>Create "{tagSearch.trim()}"</Text>
                    </TouchableOpacity>
                  )}
                  {filteredAvailableTags.map(tag => (
                    <TouchableOpacity key={tag._id} style={s.pickerItem} onPress={() => addTag(tag.name)} data-testid={`tag-option-${tag.name}`}>
                      {tag.icon && <Ionicons name={tag.icon as any} size={18} color={tag.color || colors.textSecondary} />}
                      <Text style={s.pickerItemText}>{tag.name}</Text>
                    </TouchableOpacity>
                  ))}
                </ScrollView>
              </View>
            </View>
            <TouchableOpacity style={s.actionSheetCancel} onPress={() => setShowTagPicker(false)}>
              <Text style={s.actionSheetCancelText}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </TouchableOpacity>
      </Modal>

      {/* ── Referral Picker Modal ── */}
      <Modal visible={showReferralPicker} animationType="slide" transparent={false}>
        <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }}>
          <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.border }}>
              <Text style={{ fontSize: 18, fontWeight: '600', color: colors.text }}>Select Referrer</Text>
              <TouchableOpacity onPress={() => { setShowReferralPicker(false); setContactSearch(''); }}>
                <Text style={{ fontSize: 18, color: '#007AFF' }}>Cancel</Text>
              </TouchableOpacity>
            </View>
            <View style={{ paddingHorizontal: 16, paddingTop: 12 }}>
              <TextInput style={[s.input, { marginBottom: 12 }]} placeholder="Search contacts..."
                placeholderTextColor={colors.textTertiary} value={contactSearch} onChangeText={setContactSearch}
                autoFocus data-testid="referral-search-input" />
            </View>
            <ScrollView style={{ flex: 1 }} keyboardShouldPersistTaps="handled">
              {filteredContacts.map((c: any) => (
                <TouchableOpacity key={c._id}
                  style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: 12, paddingHorizontal: 16, borderBottomWidth: 1, borderBottomColor: colors.border }}
                  onPress={() => { setContact(p => ({ ...p, referred_by: c._id, referred_by_name: `${c.first_name} ${c.last_name || ''}`.trim() })); setShowReferralPicker(false); setContactSearch(''); }}
                  data-testid={`referral-option-${c._id}`}
                >
                  <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center', marginRight: 12 }}>
                    <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text }}>{(c.first_name || '?')[0]}</Text>
                  </View>
                  <Text style={{ fontSize: 18, color: colors.text }}>{c.first_name} {c.last_name || ''}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
          </KeyboardAvoidingView>
        </SafeAreaView>
      </Modal>

      {/* ── Date Picker Modal ── */}
      <Modal visible={showDatePicker} animationType="fade" transparent>
        <TouchableOpacity style={s.actionSheetOverlay} activeOpacity={1} onPress={() => setShowDatePicker(false)}>
          <View style={s.actionSheetContainer} onStartShouldSetResponder={() => true}>
            <View style={[s.actionSheetGroup, { padding: 16 }]}>
              <Text style={{ fontSize: 18, fontWeight: '600', color: colors.text, marginBottom: 12 }}>{activeDateLabel}</Text>
              {IS_WEB ? (
                <input type="date"
                  value={tempDate ? new Date(tempDate).toISOString().split('T')[0] : ''}
                  onChange={(e: any) => { if (e.target.value) { const d = new Date(e.target.value + 'T12:00:00'); setTempDate(d); setWebYear(d.getFullYear()); setWebMonth(d.getMonth()); setWebDay(d.getDate()); } }}
                  style={{ fontSize: 19, padding: 12, borderRadius: 8, border: `1px solid ${colors.border}`, backgroundColor: colors.card, color: colors.text, width: '100%' }}
                />
              ) : null}
              <TouchableOpacity style={{ marginTop: 16, alignItems: 'center', padding: 14, backgroundColor: '#007AFF', borderRadius: 10 }} onPress={confirmDateSelection}>
                <Text style={{ fontSize: 18, fontWeight: '600', color: '#FFF' }}>Done</Text>
              </TouchableOpacity>
            </View>
          </View>
        </TouchableOpacity>
      </Modal>

      {/* ── Device Contacts Modal ── */}
      <Modal visible={showDeviceContacts} animationType="slide" presentationStyle="pageSheet">
        <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.border }}>
            <TouchableOpacity onPress={() => { setShowDeviceContacts(false); setDeviceContactSearch(''); setSelectedDeviceIds(new Set()); }} data-testid="device-contacts-close">
              <Ionicons name="close" size={24} color={colors.text} />
            </TouchableOpacity>
            <Text style={{ flex: 1, fontSize: 18, fontWeight: '700', color: colors.text, textAlign: 'center' }}>Phone Contacts</Text>
            {selectedDeviceIds.size === 0 ? <View style={{ width: 24 }} /> : <Text style={{ fontSize: 15, color: '#C9A962', fontWeight: '600' }}>{selectedDeviceIds.size} selected</Text>}
          </View>
          <View style={{ paddingHorizontal: 16, paddingVertical: 10 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, borderRadius: 10, paddingHorizontal: 12 }}>
              <Ionicons name="search" size={18} color={colors.textTertiary} />
              <TextInput style={{ flex: 1, paddingVertical: 10, paddingLeft: 8, fontSize: 17, color: colors.text }}
                placeholder="Search by name or phone..." placeholderTextColor={colors.textTertiary}
                value={deviceContactSearch} onChangeText={setDeviceContactSearch} autoFocus data-testid="device-contacts-search" />
              {deviceContactSearch ? <TouchableOpacity onPress={() => setDeviceContactSearch('')}><Ionicons name="close-circle" size={18} color={colors.textTertiary} /></TouchableOpacity> : null}
            </View>
          </View>
          <TouchableOpacity onPress={toggleSelectAllVisible}
            style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 8, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border }}
            data-testid="select-all-btn"
          >
            <Ionicons name={filteredDeviceContactsList.length > 0 && filteredDeviceContactsList.every(dc => dc.id && selectedDeviceIds.has(dc.id)) ? "checkbox" : "square-outline"} size={22} color="#C9A962" />
            <Text style={{ fontSize: 16, fontWeight: '600', color: '#C9A962', marginLeft: 10 }}>Select All ({filteredDeviceContactsList.length})</Text>
          </TouchableOpacity>
          <FlatList
            data={filteredDeviceContactsList}
            keyExtractor={item => item.id || Math.random().toString()}
            renderItem={({ item: dc }) => {
              const isSelected = dc.id ? selectedDeviceIds.has(dc.id) : false;
              return (
                <TouchableOpacity
                  onPress={() => selectedDeviceIds.size > 0 && dc.id ? toggleDeviceContact(dc.id) : selectDeviceContact(dc)}
                  onLongPress={() => dc.id && toggleDeviceContact(dc.id)}
                  style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border, backgroundColor: isSelected ? '#C9A96210' : 'transparent' }}
                  data-testid={`device-contact-${dc.id}`}
                >
                  {selectedDeviceIds.size > 0 && <Ionicons name={isSelected ? "checkbox" : "square-outline"} size={22} color={isSelected ? '#C9A962' : colors.textTertiary} style={{ marginRight: 10 }} />}
                  {dc.image?.uri
                    ? <Image source={{ uri: dc.image.uri }} style={{ width: 40, height: 40, borderRadius: 20 }} />
                    : <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center' }}><Text style={{ fontSize: 18, fontWeight: '600', color: colors.textTertiary }}>{(dc.firstName?.[0] || '') + (dc.lastName?.[0] || '')}</Text></View>
                  }
                  <View style={{ flex: 1, marginLeft: 12 }}>
                    <Text style={{ fontSize: 17, fontWeight: '500', color: colors.text }}>{dc.firstName || ''} {dc.lastName || ''}</Text>
                    {dc.phoneNumbers?.[0]?.number && <Text style={{ fontSize: 15, color: colors.textSecondary, marginTop: 1 }}>{dc.phoneNumbers[0].number}</Text>}
                  </View>
                  {selectedDeviceIds.size === 0 && <Ionicons name="chevron-forward" size={18} color={colors.textTertiary} />}
                </TouchableOpacity>
              );
            }}
            ListEmptyComponent={<View style={{ padding: 32, alignItems: 'center' }}><Text style={{ fontSize: 16, color: colors.textSecondary }}>{deviceContactSearch ? 'No contacts match your search' : 'No contacts found'}</Text></View>}
          />
          {selectedDeviceIds.size > 0 && (
            <View style={{ paddingHorizontal: 16, paddingVertical: 12, borderTopWidth: 1, borderTopColor: colors.border, backgroundColor: colors.bg }}>
              <TouchableOpacity onPress={handleBulkImport} disabled={bulkImporting}
                style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#C9A962', paddingVertical: 14, borderRadius: 12 }}
                data-testid="bulk-import-btn"
              >
                {bulkImporting ? <ActivityIndicator size="small" color="#fff" /> : <Ionicons name="download-outline" size={18} color="#fff" />}
                <Text style={{ fontSize: 17, fontWeight: '700', color: '#fff' }}>{bulkImporting ? 'Importing...' : `Import ${selectedDeviceIds.size} Contact${selectedDeviceIds.size !== 1 ? 's' : ''}`}</Text>
              </TouchableOpacity>
            </View>
          )}
        </SafeAreaView>
      </Modal>
    </SafeAreaView>
  );
}
