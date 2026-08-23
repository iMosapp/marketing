import { ScreenErrorBoundary } from '../../components/ScreenErrorBoundary';
import React, { useState, useEffect } from 'react';
import {
  View, Text, TouchableOpacity, TextInput, ScrollView, ActivityIndicator, Platform, FlatList,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Image } from 'expo-image';
import { useRouter } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import api, { contactsAPI, smartSendSMS } from '../../services/api';
import { showSimpleAlert } from '../../services/alert';

const IS_WEB = Platform.OS === 'web';

type Step = 'photo' | 'who' | 'send' | 'done';

function SendPhotoScreen() {
  const router = useRouter();
  const { user } = useAuthStore();
  const { colors } = useThemeStore();

  const [step, setStep] = useState<Step>('photo');
  const [photo, setPhoto] = useState<any>(null);
  const [contacts, setContacts] = useState<any[]>([]);
  const [contactsLoading, setContactsLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [selContact, setSelContact] = useState<any>(null);
  const [caption, setCaption] = useState('');
  const [sending, setSending] = useState(false);
  const [sentVia, setSentVia] = useState<'twilio' | 'native'>('twilio');

  useEffect(() => {
    const load = async () => {
      if (!user?._id) return;
      setContactsLoading(true);
      try {
        const data = await contactsAPI.getAll(user._id);
        setContacts(Array.isArray(data) ? data : (data?.contacts || []));
      } catch {}
      setContactsLoading(false);
    };
    load();
  }, [user?._id]);

  const takePhoto = async () => {
    try {
      if (!IS_WEB) {
        const { status } = await ImagePicker.requestCameraPermissionsAsync();
        if (status !== 'granted') { showSimpleAlert('Permission Needed', 'Camera access is required.'); return; }
      }
      const result = await ImagePicker.launchCameraAsync({ quality: 0.7, allowsEditing: false, exif: false });
      if (!result.canceled && result.assets[0]?.uri) {
        setPhoto(result.assets[0]);
        setStep('who');
      }
    } catch {
      showSimpleAlert('Error', 'Could not open the camera.');
    }
  };

  const pickPhoto = async () => {
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images, allowsEditing: false, quality: 0.7,
      });
      if (!result.canceled && result.assets[0]?.uri) {
        setPhoto(result.assets[0]);
        setStep('who');
      }
    } catch {
      showSimpleAlert('Error', 'Could not open your photos.');
    }
  };

  const filteredContacts = contacts.filter(c => {
    const q = search.toLowerCase();
    if (!q) return true;
    return (c.first_name || '').toLowerCase().includes(q)
      || (c.last_name || '').toLowerCase().includes(q)
      || (c.phone || '').includes(q)
      || `${c.first_name || ''} ${c.last_name || ''}`.toLowerCase().includes(q);
  });

  const selectContact = (c: any) => {
    if (!c.phone) { showSimpleAlert('No Phone', `${c.first_name || 'This contact'} has no phone number saved.`); return; }
    setSelContact(c);
    setStep('send');
  };

  const sendPhoto = async () => {
    if (!user || !selContact || !photo) return;
    setSending(true);
    try {
      // 1. Upload photo to object storage
      const formData = new FormData();
      if (IS_WEB) {
        const resp = await fetch(photo.uri);
        const blob = await resp.blob();
        formData.append('file', blob, 'photo.jpg');
      } else {
        formData.append('file', { uri: photo.uri, type: 'image/jpeg', name: 'photo.jpg' } as any);
      }
      const uploadRes = await api.post('/images/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
      let photoUrl = uploadRes.data?.original_url || uploadRes.data?.url || uploadRes.data?.file_url || '';
      if (photoUrl && photoUrl.startsWith('/')) {
        const baseUrl = process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com';
        photoUrl = `${baseUrl}${photoUrl}`;
      }
      const mediaUrl = photoUrl ? `${photoUrl}?format=jpeg` : '';
      if (!mediaUrl) { showSimpleAlert('Error', 'Photo upload failed. Try again.'); setSending(false); return; }

      const contactId = selContact._id || selContact.id;
      const body = caption.trim();
      const twilioNumber = (user as any).twilio_number || (user as any).mvpline_number;

      // 2. Preferred: real MMS from the rep's business number
      if (twilioNumber) {
        try {
          const result = await smartSendSMS({
            to: selContact.phone,
            body,
            userId: user._id,
            twilioNumber,
            contactId,
            eventType: 'photo_sent',
            platform: Platform.OS,
            mediaUrls: [mediaUrl],
          });
          if (result.usedTwilio) {
            setSentVia('twilio');
            setStep('done');
            setSending(false);
            return;
          }
        } catch {}
      }

      // 3. Fallback: log the event, open native SMS with the photo as a link
      try {
        await contactsAPI.logEvent(user._id, contactId, {
          event_type: 'photo_sent',
          title: 'Photo Sent',
          description: body || 'Sent a photo',
          channel: 'sms',
          category: 'message',
          icon: 'image',
          color: '#32ADE6',
        });
      } catch {}
      const smsBody = body ? `${body} ${mediaUrl}` : mediaUrl;
      const phoneClean = (selContact.phone || '').replace(/[^\d+]/g, '');
      let sep = '?';
      if (IS_WEB && typeof window !== 'undefined') {
        const ua = window.navigator.userAgent.toLowerCase();
        if (/iphone|ipad|ipod/.test(ua)) sep = '&';
      } else if (Platform.OS === 'ios') {
        sep = '&';
      }
      const smsUrl = `sms:${phoneClean}${sep}body=${encodeURIComponent(smsBody)}`;
      if (IS_WEB && typeof window !== 'undefined') {
        window.open(smsUrl, '_self');
      } else {
        const { Linking } = require('react-native');
        Linking.openURL(smsUrl);
      }
      setSentVia('native');
      setStep('done');
    } catch (e) {
      showSimpleAlert('Error', 'Could not send the photo. Please try again.');
    }
    setSending(false);
  };

  const contactName = selContact ? `${selContact.first_name || ''} ${selContact.last_name || ''}`.trim() : '';

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      {/* Header */}
      <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 0.5, borderBottomColor: colors.border }}>
        <TouchableOpacity
          onPress={() => {
            if (step === 'who') setStep('photo');
            else if (step === 'send') setStep('who');
            else router.back();
          }}
          style={{ padding: 4, marginRight: 8 }}
          data-testid="send-photo-back-btn"
        >
          <Ionicons name="chevron-back" size={24} color={colors.accent} />
        </TouchableOpacity>
        <Text style={{ fontSize: 19, fontWeight: '700', color: colors.text, flex: 1 }}>Send Photo</Text>
        {photo && step !== 'done' && (
          <Image source={{ uri: photo.uri }} style={{ width: 34, height: 34, borderRadius: 8 }} contentFit="cover" />
        )}
      </View>

      {/* STEP 1: PHOTO */}
      {step === 'photo' && (
        <View style={{ flex: 1, justifyContent: 'center', paddingHorizontal: 24, gap: 14 }}>
          <View style={{ alignItems: 'center', marginBottom: 12 }}>
            <View style={{ width: 72, height: 72, borderRadius: 22, backgroundColor: 'rgba(50,173,230,0.14)', alignItems: 'center', justifyContent: 'center', marginBottom: 12 }}>
              <Ionicons name="camera" size={36} color="#32ADE6" />
            </View>
            <Text style={{ fontSize: 21, fontWeight: '800', color: colors.text }}>Grab a photo</Text>
            <Text style={{ fontSize: 14, color: colors.textSecondary, marginTop: 4, textAlign: 'center' }}>
              Snap it or pick one — then choose who gets it
            </Text>
          </View>
          {!IS_WEB && (
            <TouchableOpacity
              onPress={takePhoto}
              style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, backgroundColor: '#32ADE6', borderRadius: 16, paddingVertical: 16 }}
              data-testid="send-photo-camera-btn"
            >
              <Ionicons name="camera" size={22} color="#FFF" />
              <Text style={{ fontSize: 17, fontWeight: '800', color: '#FFF' }}>Take a Photo</Text>
            </TouchableOpacity>
          )}
          <TouchableOpacity
            onPress={pickPhoto}
            style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, backgroundColor: colors.card, borderWidth: 1.5, borderColor: '#32ADE655', borderRadius: 16, paddingVertical: 16 }}
            data-testid="send-photo-library-btn"
          >
            <Ionicons name="images" size={22} color="#32ADE6" />
            <Text style={{ fontSize: 17, fontWeight: '800', color: '#32ADE6' }}>Choose from Photos</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* STEP 2: WHO */}
      {step === 'who' && (
        <View style={{ flex: 1 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, margin: 16, marginBottom: 8, backgroundColor: colors.card, borderRadius: 12, paddingHorizontal: 12, paddingVertical: 10, borderWidth: 1, borderColor: colors.border }}>
            <Ionicons name="search" size={18} color={colors.textSecondary} />
            <TextInput
              style={{ flex: 1, fontSize: 16, color: colors.text }}
              placeholder="Who gets this photo?"
              placeholderTextColor={colors.textTertiary}
              value={search}
              onChangeText={setSearch}
              autoFocus
              data-testid="send-photo-search"
            />
          </View>
          {contactsLoading ? (
            <ActivityIndicator size="large" color={colors.accent} style={{ marginTop: 40 }} />
          ) : (
            <FlatList
              data={filteredContacts}
              keyExtractor={(item: any) => item._id || item.id}
              keyboardShouldPersistTaps="handled"
              renderItem={({ item }: any) => {
                const name = `${item.first_name || ''} ${item.last_name || ''}`.trim() || item.phone || 'Unknown';
                const initials = `${(item.first_name || '?')[0] || ''}${(item.last_name || '')[0] || ''}`.toUpperCase();
                return (
                  <TouchableOpacity
                    onPress={() => selectContact(item)}
                    style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 0.5, borderBottomColor: colors.border }}
                    data-testid={`send-photo-contact-${item._id || item.id}`}
                  >
                    <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: 'rgba(50,173,230,0.14)', alignItems: 'center', justifyContent: 'center' }}>
                      <Text style={{ fontWeight: '700', fontSize: 15, color: '#32ADE6' }}>{initials}</Text>
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={{ fontSize: 16, fontWeight: '600', color: colors.text }}>{name}</Text>
                      {item.phone ? <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 1 }}>{item.phone}</Text> : (
                        <Text style={{ fontSize: 13, color: '#FF9500', marginTop: 1 }}>No phone number</Text>
                      )}
                    </View>
                    <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />
                  </TouchableOpacity>
                );
              }}
              ListEmptyComponent={
                <View style={{ alignItems: 'center', paddingVertical: 40 }}>
                  <Text style={{ color: colors.textSecondary, fontSize: 15 }}>{search ? 'No contacts found' : 'No contacts yet'}</Text>
                </View>
              }
            />
          )}
        </View>
      )}

      {/* STEP 3: CAPTION + SEND */}
      {step === 'send' && selContact && (
        <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16 }} keyboardShouldPersistTaps="handled">
          <Image source={{ uri: photo?.uri }} style={{ width: '100%', height: 260, borderRadius: 16, backgroundColor: colors.card }} contentFit="cover" />
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: colors.card, borderRadius: 12, padding: 12, marginTop: 14 }}>
            <Ionicons name="person-circle" size={20} color="#32ADE6" />
            <Text style={{ fontSize: 15, fontWeight: '600', color: colors.text, flex: 1 }}>{contactName}</Text>
            <Text style={{ fontSize: 13, color: colors.textSecondary }}>{selContact.phone}</Text>
          </View>
          <TextInput
            style={{ backgroundColor: colors.card, borderRadius: 12, padding: 14, fontSize: 16, color: colors.text, borderWidth: 1, borderColor: colors.border, marginTop: 12, minHeight: 70, textAlignVertical: 'top' }}
            placeholder={`Add a quick note for ${selContact.first_name || 'them'} (optional)`}
            placeholderTextColor={colors.textTertiary}
            value={caption}
            onChangeText={setCaption}
            multiline
            maxLength={500}
            data-testid="send-photo-caption"
          />
          <TouchableOpacity
            onPress={sendPhoto}
            disabled={sending}
            style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, backgroundColor: '#32ADE6', borderRadius: 16, paddingVertical: 16, marginTop: 16, opacity: sending ? 0.6 : 1 }}
            data-testid="send-photo-send-btn"
          >
            {sending ? <ActivityIndicator size="small" color="#FFF" /> : <Ionicons name="send" size={20} color="#FFF" />}
            <Text style={{ fontSize: 17, fontWeight: '800', color: '#FFF' }}>{sending ? 'Sending...' : `Text it to ${selContact.first_name || 'them'}`}</Text>
          </TouchableOpacity>
        </ScrollView>
      )}

      {/* STEP 4: DONE */}
      {step === 'done' && (
        <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', paddingHorizontal: 32 }}>
          <View style={{ width: 84, height: 84, borderRadius: 42, backgroundColor: 'rgba(52,199,89,0.15)', alignItems: 'center', justifyContent: 'center', marginBottom: 16 }}>
            <Ionicons name="checkmark" size={44} color="#34C759" />
          </View>
          <Text style={{ fontSize: 22, fontWeight: '800', color: colors.text }}>Photo sent!</Text>
          <Text style={{ fontSize: 14, color: colors.textSecondary, marginTop: 6, textAlign: 'center' }}>
            {sentVia === 'twilio'
              ? `On its way to ${contactName} — logged to their timeline`
              : `Finish sending in your texting app — it's logged to ${contactName}'s timeline`}
          </Text>
          <TouchableOpacity
            onPress={() => router.back()}
            style={{ backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: 14, paddingHorizontal: 32, paddingVertical: 13, marginTop: 24 }}
            data-testid="send-photo-done-btn"
          >
            <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text }}>Done</Text>
          </TouchableOpacity>
          <TouchableOpacity
            onPress={() => { setPhoto(null); setSelContact(null); setCaption(''); setSearch(''); setStep('photo'); }}
            style={{ marginTop: 14 }}
            data-testid="send-photo-another-btn"
          >
            <Text style={{ fontSize: 15, fontWeight: '600', color: '#32ADE6' }}>Send another</Text>
          </TouchableOpacity>
        </View>
      )}
    </SafeAreaView>
  );
}

export default function SendPhotoScreenWithBoundary(props: any) {
  return <ScreenErrorBoundary screenName="Send Photo"><SendPhotoScreen {...props} /></ScreenErrorBoundary>;
}
