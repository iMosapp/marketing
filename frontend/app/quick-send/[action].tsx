import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, ScrollView, SafeAreaView,
  ActivityIndicator, Platform, KeyboardAvoidingView, Linking,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import api from '../../services/api';

const IS_WEB = Platform.OS === 'web';

// Action config — what each tile sends
const ACTION_CONFIG: Record<string, {
  title: string; icon: string; color: string; previewTitle: string;
  getUrl: (userId: string, storeSlug: string) => string;
  getMessage: (name: string, url: string) => string;
  eventType: string;
}> = {
  digitalcard: {
    title: 'Share My Card', icon: 'card-outline', color: '#007AFF',
    previewTitle: 'Digital Business Card',
    getUrl: (uid) => `${process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com'}/p/${uid}`,
    getMessage: (name, url) => `Hey ${name}! Here's my digital business card. Save my info and reach out anytime! ${url}`,
    eventType: 'digital_card_shared',
  },
  review: {
    title: 'Send Review Link', icon: 'star-outline', color: '#FFD60A',
    previewTitle: 'Review Invite',
    getUrl: (uid, slug) => `${process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com'}/review/${slug}?sp=${uid}`,
    getMessage: (name, url) => `Hey ${name}! I'd really appreciate a review. It only takes a minute: ${url}`,
    eventType: 'review_invite_sent',
  },
  showcase: {
    title: 'Share Showcase', icon: 'storefront-outline', color: '#34C759',
    previewTitle: 'My Showcase',
    getUrl: (uid) => `${process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com'}/showcase/${uid}`,
    getMessage: (name, url) => `Hey ${name}! Check out my showcase of happy customers: ${url}`,
    eventType: 'showcase_shared',
  },
  congrats: {
    title: 'Send a Card', icon: 'gift-outline', color: '#C9A962',
    previewTitle: 'Greeting Card',
    getUrl: () => '', // Cards need to be created first — handled separately
    getMessage: () => '',
    eventType: 'congrats_card_sent',
  },
};

const CARD_TYPES = [
  { key: 'congrats', label: 'Congrats Card', icon: 'trophy', color: '#C9A962' },
  { key: 'birthday', label: 'Birthday Card', icon: 'gift', color: '#FF6B6B' },
  { key: 'holiday', label: 'Holiday Card', icon: 'snow', color: '#5AC8FA' },
  { key: 'thank_you', label: 'Thank You Card', icon: 'heart', color: '#FF2D55' },
  { key: 'anniversary', label: 'Anniversary Card', icon: 'ribbon', color: '#AF52DE' },
  { key: 'welcome', label: 'Welcome Card', icon: 'hand-left', color: '#34C759' },
];

type Step = 'info' | 'cardtype' | 'preview' | 'sending' | 'done';

export default function QuickSendPage() {
  const router = useRouter();
  const { action } = useLocalSearchParams();
  const { user } = useAuthStore();
  const { colors } = useThemeStore();
  const actionKey = (typeof action === 'string' ? action : 'digitalcard');
  const config = ACTION_CONFIG[actionKey] || ACTION_CONFIG.digitalcard;

  // Step state
  const [step, setStep] = useState<Step>(actionKey === 'congrats' ? 'cardtype' : 'info');

  // Customer info
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [matchedContact, setMatchedContact] = useState<any>(null);
  const [checking, setChecking] = useState(false);
  const dupTimer = useRef<any>(null);

  // Card type (for Send a Card)
  const [selectedCardType, setSelectedCardType] = useState('congrats');

  // Preview
  const [shareUrl, setShareUrl] = useState('');
  const [messageText, setMessageText] = useState('');
  const [sendMethod, setSendMethod] = useState<'sms' | 'email' | 'copy'>('sms');

  // Sending
  const [sending, setSending] = useState(false);
  const [newContactId, setNewContactId] = useState('');

  const storeSlug = user?.store_slug || user?.storeSlug || '';
  const userId = user?._id || '';

  // Duplicate check on phone
  const checkPhone = useCallback(async (p: string) => {
    if (!userId || p.replace(/\D/g, '').length < 7) {
      setMatchedContact(null);
      return;
    }
    setChecking(true);
    try {
      const res = await api.get(`/contacts/${userId}/check-duplicate?phone=${encodeURIComponent(p)}`);
      const matches = res.data?.matches || [];
      if (matches.length > 0) {
        const m = matches[0];
        setMatchedContact(m);
        if (m.first_name) setName(`${m.first_name} ${m.last_name || ''}`.trim());
        if (m.email) setEmail(m.email);
      } else {
        setMatchedContact(null);
      }
    } catch { setMatchedContact(null); }
    setChecking(false);
  }, [userId]);

  const onPhoneChange = (val: string) => {
    setPhone(val);
    clearTimeout(dupTimer.current);
    dupTimer.current = setTimeout(() => checkPhone(val), 600);
  };

  // Move to preview step
  const goToPreview = async () => {
    const firstName = name.split(/\s+/)[0] || name;

    if (actionKey === 'congrats') {
      // For cards, navigate to card creation flow and come back
      const params = new URLSearchParams();
      params.set('type', selectedCardType);
      if (name) params.set('prefillName', name);
      if (phone) params.set('prefillPhone', phone);
      if (email) params.set('prefillEmail', email);
      params.set('return_quick_send', '1');
      router.push(`/settings/create-card?${params.toString()}` as any);
      return;
    }

    const url = config.getUrl(userId, storeSlug);
    const msg = config.getMessage(firstName, url);
    setShareUrl(url);
    setMessageText(msg);
    setStep('preview');
  };

  // Send the message
  const handleSend = async () => {
    if (!name.trim()) return;
    setSending(true);
    setStep('sending');

    try {
      let contactId = matchedContact?.id || '';

      // If no matched contact, create one
      if (!contactId) {
        const parts = name.trim().split(/\s+/);
        const res = await api.post(`/contacts/${userId}`, {
          first_name: parts[0],
          last_name: parts.slice(1).join(' '),
          phone: phone,
          email: email,
        });
        contactId = res.data?._id || res.data?.id || '';
      }
      setNewContactId(contactId);

      if (sendMethod === 'copy') {
        // Copy to clipboard
        if (IS_WEB && navigator.clipboard) {
          await navigator.clipboard.writeText(messageText);
        }
        // Log the event
        await api.post(`/contacts/${userId}/${contactId}/find-or-create-and-log`, {
          event_type: config.eventType,
          channel: 'link_copy',
          content: messageText,
        }).catch(() => {});
      } else if (sendMethod === 'sms') {
        // Send via messages API
        await api.post(`/messages/send/${userId}`, {
          contact_id: contactId,
          content: messageText,
          channel: 'sms_personal',
          event_type: config.eventType,
        }).catch(() => {});
      } else if (sendMethod === 'email') {
        if (email) {
          await api.post(`/messages/send/${userId}`, {
            contact_id: contactId,
            content: messageText,
            channel: 'email',
            to_email: email,
            event_type: config.eventType,
          }).catch(() => {});
        }
      }

      setStep('done');
      // Auto-redirect to contact after 2 seconds
      setTimeout(() => {
        if (contactId) {
          router.replace(`/contact/${contactId}` as any);
        } else {
          router.back();
        }
      }, 2000);

    } catch (err) {
      console.error('Send error:', err);
      setStep('preview');
    }
    setSending(false);
  };

  // ==================== RENDER ====================

  const renderCardTypePicker = () => (
    <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16 }}>
      <Text style={{ fontSize: 13, color: colors.textSecondary, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 12 }}>
        What type of card?
      </Text>
      {CARD_TYPES.map(ct => (
        <TouchableOpacity
          key={ct.key}
          style={{
            flexDirection: 'row', alignItems: 'center', padding: 16, marginBottom: 10,
            backgroundColor: selectedCardType === ct.key ? `${ct.color}15` : colors.card,
            borderRadius: 14, borderWidth: 1,
            borderColor: selectedCardType === ct.key ? ct.color : colors.border,
            gap: 14,
          }}
          onPress={() => { setSelectedCardType(ct.key); setStep('info'); }}
          data-testid={`card-type-${ct.key}`}
        >
          <View style={{ width: 44, height: 44, borderRadius: 14, backgroundColor: `${ct.color}20`, alignItems: 'center', justifyContent: 'center' }}>
            <Ionicons name={ct.icon as any} size={22} color={ct.color} />
          </View>
          <Text style={{ fontSize: 16, fontWeight: '600', color: colors.text, flex: 1 }}>{ct.label}</Text>
          <Ionicons name="chevron-forward" size={18} color={colors.textTertiary} />
        </TouchableOpacity>
      ))}
    </ScrollView>
  );

  const renderInfoStep = () => (
    <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16 }} keyboardShouldPersistTaps="handled">
        <Text style={{ fontSize: 13, color: colors.textSecondary, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 12 }}>
          Who are you sending to?
        </Text>

        {/* Name */}
        <View style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: 12, paddingHorizontal: 14, marginBottom: 10, gap: 10 }}>
          <Ionicons name="person-outline" size={18} color={colors.textTertiary} />
          <TextInput
            style={{ flex: 1, paddingVertical: 14, fontSize: 16, color: colors.text }}
            placeholder="Customer name"
            placeholderTextColor={colors.textTertiary}
            value={name}
            onChangeText={setName}
            autoFocus
            data-testid="qs-name"
          />
        </View>

        {/* Phone */}
        <View style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, borderWidth: 1, borderColor: matchedContact ? '#34C759' : colors.border, borderRadius: 12, paddingHorizontal: 14, marginBottom: 10, gap: 10 }}>
          <Ionicons name="call-outline" size={18} color={matchedContact ? '#34C759' : colors.textTertiary} />
          <TextInput
            style={{ flex: 1, paddingVertical: 14, fontSize: 16, color: colors.text }}
            placeholder="Phone number"
            placeholderTextColor={colors.textTertiary}
            value={phone}
            onChangeText={onPhoneChange}
            keyboardType="phone-pad"
            data-testid="qs-phone"
          />
          {checking && <ActivityIndicator size="small" color={colors.accent} />}
        </View>

        {/* Email */}
        <View style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: 12, paddingHorizontal: 14, marginBottom: 12, gap: 10 }}>
          <Ionicons name="mail-outline" size={18} color={colors.textTertiary} />
          <TextInput
            style={{ flex: 1, paddingVertical: 14, fontSize: 16, color: colors.text }}
            placeholder="Email (optional)"
            placeholderTextColor={colors.textTertiary}
            value={email}
            onChangeText={setEmail}
            keyboardType="email-address"
            autoCapitalize="none"
            data-testid="qs-email"
          />
        </View>

        {/* Match banner */}
        {matchedContact && (
          <View style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: 'rgba(52,199,89,0.08)', borderWidth: 1, borderColor: 'rgba(52,199,89,0.3)', borderRadius: 12, padding: 12, gap: 12, marginBottom: 12 }} data-testid="qs-match-banner">
            <View style={{ width: 40, height: 40, borderRadius: 12, backgroundColor: `${colors.accent}20`, alignItems: 'center', justifyContent: 'center' }}>
              <Text style={{ fontWeight: '700', fontSize: 14, color: colors.accent }}>
                {(matchedContact.first_name || '?')[0]}{(matchedContact.last_name || '')[0] || ''}
              </Text>
            </View>
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 15, fontWeight: '600', color: colors.text }}>{matchedContact.first_name} {matchedContact.last_name}</Text>
              <Text style={{ fontSize: 13, color: colors.textSecondary }}>Existing contact</Text>
            </View>
            <View style={{ backgroundColor: 'rgba(52,199,89,0.15)', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 }}>
              <Text style={{ fontSize: 12, fontWeight: '600', color: '#34C759' }}>Matched</Text>
            </View>
          </View>
        )}

        {/* Next button */}
        <TouchableOpacity
          style={{ padding: 16, borderRadius: 14, backgroundColor: (name.trim() && phone.trim()) ? '#C9A962' : colors.border, alignItems: 'center', marginTop: 8 }}
          onPress={goToPreview}
          disabled={!name.trim() || !phone.trim()}
          data-testid="qs-next-btn"
        >
          <Text style={{ fontSize: 17, fontWeight: '700', color: (name.trim() && phone.trim()) ? '#000' : colors.textTertiary }}>
            {actionKey === 'congrats' ? 'Create Card' : 'Preview'}
          </Text>
        </TouchableOpacity>

        {!matchedContact && name.trim() && phone.trim() && (
          <Text style={{ fontSize: 13, color: colors.textTertiary, textAlign: 'center', marginTop: 10 }}>
            New contact will be auto-created when you send
          </Text>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );

  const renderPreview = () => {
    const firstName = name.split(/\s+/)[0] || name;
    return (
      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16 }}>
        {/* Recipient */}
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: colors.border, marginBottom: 16 }}>
          <View style={{ width: 44, height: 44, borderRadius: 14, backgroundColor: `${colors.accent}20`, alignItems: 'center', justifyContent: 'center' }}>
            <Text style={{ fontWeight: '700', fontSize: 16, color: colors.accent }}>{(name || '?')[0].toUpperCase()}</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text }}>{name}</Text>
            <Text style={{ fontSize: 13, color: colors.textSecondary }}>{phone}</Text>
          </View>
          {matchedContact && (
            <View style={{ backgroundColor: 'rgba(52,199,89,0.12)', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 }}>
              <Text style={{ fontSize: 11, fontWeight: '600', color: '#34C759' }}>Existing</Text>
            </View>
          )}
        </View>

        {/* What you're sending */}
        <Text style={{ fontSize: 13, color: colors.textSecondary, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>
          What you're sending
        </Text>
        <View style={{ backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: colors.border, overflow: 'hidden', marginBottom: 16 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.border }}>
            <Ionicons name={config.icon as any} size={20} color={config.color} />
            <Text style={{ fontSize: 14, fontWeight: '700', color: '#C9A962' }}>{config.previewTitle}</Text>
          </View>
          <View style={{ padding: 16 }}>
            <View style={{ backgroundColor: colors.bg, borderRadius: 12, padding: 14 }}>
              <Text style={{ fontSize: 14, color: colors.textSecondary, lineHeight: 22 }}>{messageText}</Text>
            </View>
          </View>
        </View>

        {/* Send options */}
        <Text style={{ fontSize: 13, color: colors.textSecondary, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>
          How do you want to send it?
        </Text>
        <View style={{ flexDirection: 'row', gap: 10, marginBottom: 16 }}>
          {[
            { key: 'sms' as const, icon: 'chatbubble', label: 'Text / SMS' },
            { key: 'email' as const, icon: 'mail', label: 'Email', disabled: !email },
            { key: 'copy' as const, icon: 'copy', label: 'Copy Link' },
          ].map(opt => (
            <TouchableOpacity
              key={opt.key}
              style={{
                flex: 1, padding: 12, borderRadius: 12, alignItems: 'center',
                borderWidth: 1,
                borderColor: sendMethod === opt.key ? '#C9A962' : colors.border,
                backgroundColor: sendMethod === opt.key ? 'rgba(201,169,98,0.08)' : colors.card,
                opacity: opt.disabled ? 0.4 : 1,
              }}
              onPress={() => !opt.disabled && setSendMethod(opt.key)}
              disabled={opt.disabled}
              data-testid={`qs-method-${opt.key}`}
            >
              <Ionicons name={opt.icon as any} size={22} color={sendMethod === opt.key ? '#C9A962' : colors.textTertiary} />
              <Text style={{ fontSize: 12, fontWeight: '600', color: sendMethod === opt.key ? '#C9A962' : colors.textTertiary, marginTop: 4 }}>{opt.label}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Send button */}
        <TouchableOpacity
          style={{ padding: 16, borderRadius: 14, backgroundColor: '#C9A962', alignItems: 'center' }}
          onPress={handleSend}
          data-testid="qs-send-btn"
        >
          <Text style={{ fontSize: 17, fontWeight: '700', color: '#000' }}>
            {sendMethod === 'copy' ? 'Copy Link' : sendMethod === 'email' ? 'Send via Email' : 'Send via SMS'}
          </Text>
        </TouchableOpacity>

        {sendMethod === 'sms' && (
          <TouchableOpacity
            style={{ alignItems: 'center', paddingVertical: 12 }}
            onPress={() => {
              const smsBody = encodeURIComponent(messageText);
              const smsUrl = Platform.OS === 'ios' ? `sms:${phone}&body=${smsBody}` : `sms:${phone}?body=${smsBody}`;
              Linking.openURL(smsUrl);
            }}
          >
            <Text style={{ fontSize: 13, color: '#34C759', fontWeight: '600' }}>Send from My Phone</Text>
          </TouchableOpacity>
        )}
      </ScrollView>
    );
  };

  const renderSending = () => (
    <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 40 }}>
      <ActivityIndicator size="large" color="#C9A962" />
      <Text style={{ fontSize: 18, fontWeight: '600', color: colors.text, marginTop: 16 }}>Sending...</Text>
    </View>
  );

  const renderDone = () => (
    <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 40 }}>
      <View style={{ width: 80, height: 80, borderRadius: 40, backgroundColor: 'rgba(52,199,89,0.12)', alignItems: 'center', justifyContent: 'center', marginBottom: 20 }}>
        <Ionicons name="checkmark" size={40} color="#34C759" />
      </View>
      <Text style={{ fontSize: 24, fontWeight: '800', color: colors.text, marginBottom: 8 }}>Sent!</Text>
      <Text style={{ fontSize: 15, color: colors.textSecondary, textAlign: 'center', lineHeight: 22 }}>
        {config.previewTitle} sent to{'\n'}<Text style={{ fontWeight: '700', color: colors.text }}>{name}</Text>
      </Text>

      <View style={{ backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: colors.border, padding: 14, width: '100%', marginTop: 20 }}>
        <Text style={{ fontSize: 12, color: colors.textTertiary, fontWeight: '600', marginBottom: 8 }}>AUTOMATICALLY LOGGED</Text>
        {[
          { icon: 'checkmark-circle', text: `${config.previewTitle} shared`, color: '#34C759' },
          { icon: 'chatbubble', text: `${sendMethod === 'email' ? 'Email' : sendMethod === 'copy' ? 'Link copied' : 'SMS'} sent`, color: '#007AFF' },
          { icon: 'analytics', text: 'Activity feed updated', color: '#C9A962' },
          ...(!matchedContact ? [{ icon: 'person-add' as any, text: 'New contact created', color: '#AF52DE' }] : []),
        ].map((item, i) => (
          <View key={i} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 4 }}>
            <Ionicons name={item.icon as any} size={16} color={item.color} />
            <Text style={{ fontSize: 14, color: colors.textSecondary, flex: 1 }}>{item.text}</Text>
            <Ionicons name="checkmark" size={16} color="#34C759" />
          </View>
        ))}
      </View>

      <Text style={{ fontSize: 13, color: colors.textTertiary, marginTop: 16 }}>Redirecting to contact...</Text>
    </View>
  );

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }}>
      {/* Header */}
      <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.border }}>
        <TouchableOpacity onPress={() => {
          if (step === 'preview') setStep('info');
          else if (step === 'info' && actionKey === 'congrats') setStep('cardtype');
          else router.back();
        }} style={{ padding: 4 }} data-testid="qs-back">
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={{ flex: 1, textAlign: 'center', fontSize: 18, fontWeight: '700', color: colors.text }}>
          {config.title}
        </Text>
        <View style={{ width: 32 }} />
      </View>

      {step === 'cardtype' && renderCardTypePicker()}
      {step === 'info' && renderInfoStep()}
      {step === 'preview' && renderPreview()}
      {step === 'sending' && renderSending()}
      {step === 'done' && renderDone()}
    </SafeAreaView>
  );
}
