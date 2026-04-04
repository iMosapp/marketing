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

const ACTION_CONFIG: Record<string, {
  title: string; icon: string; color: string; previewTitle: string;
  getUrl: (userId: string, storeSlug: string) => string;
  getMessage: (name: string, url: string) => string;
  eventType: string;
}> = {
  digitalcard: {
    title: 'Share My Card', icon: 'card-outline', color: '#007AFF',
    previewTitle: 'Digital Business Card',
    getUrl: (uid) => `${process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com'}/card/${uid}`,
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
  linkpage: {
    title: 'Share Link Page', icon: 'link-outline', color: '#5856D6',
    previewTitle: 'My Link Page',
    getUrl: (uid) => `${process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com'}/links/${uid}`,
    getMessage: (name, url) => `Hey ${name}! Here's a link to all my pages in one spot: ${url}`,
    eventType: 'link_page_shared',
  },
  landingpage: {
    title: 'Share Landing Page', icon: 'globe-outline', color: '#AF52DE',
    previewTitle: 'My Landing Page',
    getUrl: (uid) => `${process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com'}/p/${uid}`,
    getMessage: (name, url) => `Hey ${name}! Here's my personal page with all my info: ${url}`,
    eventType: 'landing_page_shared',
  },
  congrats: {
    title: 'Send a Card', icon: 'gift-outline', color: '#C9A962',
    previewTitle: 'Greeting Card',
    getUrl: () => '',
    getMessage: () => '',
    eventType: 'congrats_card_sent',
  },
};

const DEFAULT_CARD_TYPES = [
  { key: 'congrats', label: 'Congrats Card', icon: 'trophy', color: '#C9A962' },
  { key: 'birthday', label: 'Birthday Card', icon: 'gift', color: '#FF6B6B' },
  { key: 'holiday', label: 'Holiday Card', icon: 'snow', color: '#5AC8FA' },
  { key: 'thankyou', label: 'Thank You Card', icon: 'heart', color: '#FF2D55' },
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

  const [step, setStep] = useState<Step>(actionKey === 'congrats' ? 'cardtype' : 'info');

  // Customer info — split into first/last name
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [matchedContact, setMatchedContact] = useState<any>(null);
  const [checking, setChecking] = useState(false);
  const dupTimer = useRef<any>(null);

  const [selectedCardType, setSelectedCardType] = useState('congrats');
  const [cardTypes, setCardTypes] = useState(DEFAULT_CARD_TYPES);

  // Fetch custom card types from API
  useEffect(() => {
    const fetchCustomTypes = async () => {
      try {
        const storeId = user?.store_id;
        if (!storeId) return;
        const res = await api.get(`/congrats/templates/all/${storeId}`);
        const all = res.data || [];
        const defaultKeys = DEFAULT_CARD_TYPES.map(d => d.key);
        const custom = all
          .filter((t: any) => !defaultKeys.includes(t.card_type))
          .map((t: any) => ({
            key: t.card_type,
            label: `${t.headline || t.card_type} Card`,
            icon: 'create-outline',
            color: t.accent_color || '#C9A962',
          }));
        if (custom.length > 0) {
          setCardTypes([...DEFAULT_CARD_TYPES, ...custom]);
        }
      } catch (e) { /* ignore */ }
    };
    fetchCustomTypes();
  }, [user?.store_id]);

  const [shareUrl, setShareUrl] = useState('');
  const [messageText, setMessageText] = useState('');
  const [sendMethod, setSendMethod] = useState<'sms' | 'email' | 'copy'>('sms');

  const [sending, setSending] = useState(false);
  const [newContactId, setNewContactId] = useState('');
  const [availableTags, setAvailableTags] = useState<any[]>([]);
  const [selectedTag, setSelectedTag] = useState('');      // single tag name
  const [startCampaign, setStartCampaign] = useState(true); // campaign toggle

  const storeSlug = user?.store_slug || user?.storeSlug || '';
  const userId = user?._id || '';

  // Fetch tags when user is known
  useEffect(() => {
    if (!userId) return;
    api.get(`/tags/${userId}`).then(r => setAvailableTags(r.data || [])).catch(() => {});
  }, [userId]);

  const fullName = `${firstName} ${lastName}`.trim();

  // Card-grouped styles matching Add Contact form
  const cardStyle = {
    backgroundColor: colors.card,
    borderRadius: 12,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: 'hidden' as const,
  };
  const inputStyle = {
    fontSize: 18,
    color: colors.text,
    paddingVertical: 14,
    paddingHorizontal: 16,
  };
  const dividerStyle = {
    height: 1,
    backgroundColor: colors.border,
    marginLeft: 16,
  };
  const rowStyle = {
    flexDirection: 'row' as const,
    alignItems: 'center' as const,
    paddingVertical: 12,
    paddingHorizontal: 16,
  };
  const rowIconStyle = {
    width: 28,
    marginRight: 10,
  };

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
        if (m.first_name) setFirstName(m.first_name);
        if (m.last_name) setLastName(m.last_name || '');
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
    if (actionKey === 'congrats') {
      const params = new URLSearchParams();
      params.set('type', selectedCardType);
      if (fullName) params.set('prefillName', fullName);
      if (phone) params.set('prefillPhone', phone);
      if (email) params.set('prefillEmail', email);
      params.set('return_quick_send', '1');
      router.replace(`/settings/create-card?${params.toString()}` as any);
      return;
    }

    const url = config.getUrl(userId, storeSlug);
    const msg = config.getMessage(firstName || fullName, url);
    setShareUrl(url);
    setMessageText(msg);
    setStep('preview');
  };

  // Open native SMS app with pre-populated message
  const openNativeSMS = (phoneNum: string, body: string) => {
    const encodedBody = encodeURIComponent(body);
    const encodedPhone = encodeURIComponent(phoneNum);
    if (IS_WEB && typeof window !== 'undefined') {
      const ua = window.navigator.userAgent.toLowerCase();
      const isIos = /iphone|ipad|ipod/.test(ua);
      const sep = isIos ? '&' : '?';
      const smsUrl = `sms:${encodedPhone}${sep}body=${encodedBody}`;
      window.location.href = smsUrl;
    } else {
      const smsUrl = Platform.OS === 'ios'
        ? `sms:${encodedPhone}&body=${encodedBody}`
        : `sms:${encodedPhone}?body=${encodedBody}`;
      Linking.openURL(smsUrl);
    }
  };

  // Send the message — corrected flow
  const handleSend = async () => {
    if (!firstName.trim()) return;
    setSending(true);
    setStep('sending');

    try {
      let contactId = matchedContact?.id || '';

      // If no matched contact, create one
      if (!contactId) {
        const res = await api.post(`/contacts/${userId}`, {
          first_name: firstName.trim(),
          last_name: lastName.trim(),
          phone: phone,
          email: email,
        });
        contactId = res.data?._id || res.data?.id || '';
      }
      setNewContactId(contactId);

      // Create a trackable short URL with contact_id so click attribution is correct
      let finalMessage = messageText;
      if (contactId && shareUrl && actionKey !== 'congrats') {
        try {
          const shortRes = await api.post('/s/create', {
            original_url: shareUrl,
            link_type: config.eventType === 'review_invite_sent' ? 'review_request'
              : config.eventType === 'digital_card_shared' ? 'business_card'
              : config.eventType === 'showcase_shared' ? 'showcase' : 'link',
            user_id: userId,
            reference_id: contactId,
            metadata: { contact_id: contactId },
          });
          const trackableUrl = shortRes.data?.short_url;
          if (trackableUrl) {
            // Replace the raw URL in the message with the trackable short URL
            finalMessage = messageText.replace(shareUrl, trackableUrl);
          }
        } catch (e) {
          // Fallback: use the raw URL if short URL creation fails
          console.warn('Short URL creation failed, using raw URL:', e);
        }
      }

      // Auto-apply "Review Sent" tag when sending a review invite → triggers Review Follow-Up campaign
      if (config.eventType === 'review_invite_sent' && contactId) {
        try {
          await api.post(`/tags/${userId}/assign`, {
            tag_name: 'Review Sent',
            contact_ids: [contactId],
            skip_campaign: false,
            auto_create_tag: true,
          });
        } catch {}
      }

      // Apply user-chosen tag (triggers matching campaign if toggle is on)
      // Works for ALL actions including review (on top of the auto "Review Sent" tag)
      if (selectedTag && contactId) {
        try {
          await api.post(`/tags/${userId}/assign`, {
            tag_name: selectedTag,
            contact_ids: [contactId],
            skip_campaign: !startCampaign,
            auto_create_tag: false,
          });
        } catch {}
      }

      if (sendMethod === 'copy') {
        // Copy to clipboard
        if (IS_WEB && navigator.clipboard) {
          await navigator.clipboard.writeText(finalMessage);
        }
        // Log the event via contact event endpoint
        if (contactId) {
          await api.post(`/contacts/${userId}/${contactId}/events`, {
            event_type: config.eventType,
            title: config.previewTitle,
            description: `Shared via copy link`,
            channel: 'link_copy',
            category: 'outreach',
            icon: config.icon,
            color: config.color,
          }).catch(() => {});
        }

        setStep('done');
        setTimeout(() => {
          if (contactId) router.replace(`/contact/${contactId}` as any);
          else router.back();
        }, 2000);

      } else if (sendMethod === 'sms') {
        // Log the event server-side first
        if (contactId) {
          await api.post(`/contacts/${userId}/${contactId}/events`, {
            event_type: config.eventType,
            title: config.previewTitle,
            description: `Sent via personal SMS to ${firstName}`,
            channel: 'sms_personal',
            category: 'outreach',
            icon: 'chatbubble',
            color: '#007AFF',
          }).catch(() => {});
        }

        // Open native SMS app with pre-populated message
        openNativeSMS(phone, finalMessage);

        // Show confirmation after a brief delay (to let SMS app open)
        setTimeout(() => {
          setStep('done');
          setTimeout(() => {
            if (contactId) router.replace(`/contact/${contactId}` as any);
            else router.back();
          }, 2000);
        }, 500);

      } else if (sendMethod === 'email') {
        if (email) {
          // Log the event and send email via backend
          if (contactId) {
            await api.post(`/contacts/${userId}/${contactId}/events`, {
              event_type: config.eventType,
              title: config.previewTitle,
              description: `Sent via email to ${firstName}`,
              channel: 'email',
              category: 'outreach',
              icon: 'mail',
              color: '#AF52DE',
            }).catch(() => {});
          }
          // Also try to send via Resend if conversation exists
          try {
            const convRes = await api.post(`/messages/conversations/${userId}`, {
              contact_id: contactId,
              contact_phone: phone,
            });
            const convId = convRes.data?._id;
            if (convId) {
              await api.post(`/messages/send/${userId}/${convId}`, {
                conversation_id: convId,
                content: finalMessage,
                channel: 'email',
                to_email: email,
                event_type: config.eventType,
              });
            }
          } catch {}
        }
        setStep('done');
        setTimeout(() => {
          if (contactId) router.replace(`/contact/${contactId}` as any);
          else router.back();
        }, 2000);
      }

    } catch (err) {
      console.error('Send error:', err);
      setStep('preview');
    }
    setSending(false);
  };

  // ==================== RENDER ====================

  const renderCardTypePicker = () => (
    <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16 }}>
      <Text style={{ fontSize: 15, color: colors.textSecondary, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 12 }}>
        What type of card?
      </Text>
      {cardTypes.map(ct => (
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
          <Text style={{ fontSize: 18, fontWeight: '600', color: colors.text, flex: 1 }}>{ct.label}</Text>
          <Ionicons name="chevron-forward" size={18} color={colors.textTertiary} />
        </TouchableOpacity>
      ))}
    </ScrollView>
  );

  const renderInfoStep = () => (
    <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16 }} keyboardShouldPersistTaps="handled">
        <Text style={{ fontSize: 15, color: colors.textSecondary, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 12 }}>
          Who are you sending to?
        </Text>

        {/* Name Card — First + Last like Add Contact */}
        <View style={cardStyle}>
          <TextInput
            style={inputStyle}
            placeholder="First name"
            placeholderTextColor={colors.textTertiary}
            value={firstName}
            onChangeText={setFirstName}
            autoFocus
            returnKeyType="next"
            data-testid="qs-first-name"
          />
          <View style={dividerStyle} />
          <TextInput
            style={inputStyle}
            placeholder="Last name"
            placeholderTextColor={colors.textTertiary}
            value={lastName}
            onChangeText={setLastName}
            returnKeyType="next"
            data-testid="qs-last-name"
          />
        </View>

        {/* Contact Info Card — Phone + Email */}
        <View style={cardStyle}>
          <View style={rowStyle}>
            <Ionicons name="call-outline" size={20} color="#34C759" style={rowIconStyle} />
            <TextInput
              style={[inputStyle, { flex: 1, paddingVertical: 0 }]}
              placeholder="Phone"
              placeholderTextColor={colors.textTertiary}
              value={phone}
              onChangeText={onPhoneChange}
              keyboardType="phone-pad"
              returnKeyType="next"
              data-testid="qs-phone"
            />
            {checking && <ActivityIndicator size="small" color={colors.accent} />}
          </View>
          <View style={dividerStyle} />
          <View style={rowStyle}>
            <Ionicons name="mail-outline" size={20} color="#007AFF" style={rowIconStyle} />
            <TextInput
              style={[inputStyle, { flex: 1, paddingVertical: 0 }]}
              placeholder="Email (optional)"
              placeholderTextColor={colors.textTertiary}
              value={email}
              onChangeText={setEmail}
              keyboardType="email-address"
              autoCapitalize="none"
              data-testid="qs-email"
            />
          </View>
        </View>

        {/* Match banner */}
        {matchedContact && (
          <View style={{
            flexDirection: 'row', alignItems: 'center', padding: 12, gap: 12, marginBottom: 12,
            backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: colors.border,
          }} data-testid="qs-match-banner">
            <View style={{ width: 40, height: 40, borderRadius: 12, backgroundColor: `${colors.accent}20`, alignItems: 'center', justifyContent: 'center' }}>
              <Text style={{ fontWeight: '700', fontSize: 16, color: colors.accent }}>
                {(matchedContact.first_name || '?')[0]}{(matchedContact.last_name || '')[0] || ''}
              </Text>
            </View>
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 17, fontWeight: '600', color: colors.text }}>{matchedContact.first_name} {matchedContact.last_name}</Text>
              <Text style={{ fontSize: 15, color: colors.textSecondary }}>Existing contact</Text>
            </View>
            <View style={{ backgroundColor: 'rgba(52,199,89,0.15)', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 }}>
              <Text style={{ fontSize: 14, fontWeight: '600', color: '#34C759' }}>Matched</Text>
            </View>
          </View>
        )}

        {/* Next button */}
        <TouchableOpacity
          style={{
            padding: 16, borderRadius: 14, alignItems: 'center', marginTop: 8,
            backgroundColor: (firstName.trim() && phone.trim()) ? '#C9A962' : colors.border,
          }}
          onPress={goToPreview}
          disabled={!firstName.trim() || !phone.trim()}
          data-testid="qs-next-btn"
        >
          <Text style={{ fontSize: 18, fontWeight: '700', color: (firstName.trim() && phone.trim()) ? '#000' : colors.textTertiary }}>
            {actionKey === 'congrats' ? 'Create Card' : 'Preview'}
          </Text>
        </TouchableOpacity>

        {!matchedContact && firstName.trim() && phone.trim() && (
          <Text style={{ fontSize: 15, color: colors.textTertiary, textAlign: 'center', marginTop: 10 }}>
            New contact will be auto-created when you send
          </Text>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );

  const renderPreview = () => (
    <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16 }}>
      {/* Recipient */}
      <View style={{
        flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14,
        backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: colors.border, marginBottom: 16,
      }}>
        <View style={{ width: 44, height: 44, borderRadius: 12, backgroundColor: `${colors.accent}20`, alignItems: 'center', justifyContent: 'center' }}>
          <Text style={{ fontWeight: '700', fontSize: 18, color: colors.accent }}>{(firstName || '?')[0].toUpperCase()}</Text>
        </View>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 18, fontWeight: '700', color: colors.text }}>{fullName}</Text>
          <Text style={{ fontSize: 15, color: colors.textSecondary }}>{phone}</Text>
        </View>
        {matchedContact && (
          <View style={{ backgroundColor: 'rgba(52,199,89,0.12)', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 }}>
            <Text style={{ fontSize: 13, fontWeight: '600', color: '#34C759' }}>Existing</Text>
          </View>
        )}
      </View>

      {/* What you're sending */}
      <Text style={{ fontSize: 15, color: colors.textSecondary, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>
        What you're sending
      </Text>
      <View style={{ backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: colors.border, overflow: 'hidden', marginBottom: 16 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.border }}>
          <Ionicons name={config.icon as any} size={20} color={config.color} />
          <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text, flex: 1 }}>{config.previewTitle}</Text>
          {shareUrl ? (
            <TouchableOpacity
              style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingVertical: 4, paddingHorizontal: 10, backgroundColor: `${config.color}18`, borderRadius: 8 }}
              onPress={() => Linking.openURL(shareUrl)}
              data-testid="qs-preview-link"
            >
              <Ionicons name="eye-outline" size={16} color={config.color} />
              <Text style={{ fontSize: 15, fontWeight: '600', color: config.color }}>Preview</Text>
            </TouchableOpacity>
          ) : null}
        </View>
        <View style={{ padding: 16 }}>
          <View style={{ backgroundColor: colors.bg, borderRadius: 10, padding: 14 }}>
            <Text style={{ fontSize: 16, color: colors.textSecondary, lineHeight: 22 }}>{messageText}</Text>
          </View>
          {shareUrl ? (
            <TouchableOpacity style={{ marginTop: 8 }} onPress={() => Linking.openURL(shareUrl)}>
              <Text style={{ fontSize: 15, color: '#007AFF' }} numberOfLines={1}>{shareUrl}</Text>
            </TouchableOpacity>
          ) : null}
        </View>
      </View>

      {/* Tag picker — ABOVE send options, same UX as Create a Card */}
      <View style={{ marginBottom: 20 }}>
        <Text style={{ fontSize: 13, fontWeight: '700', color: colors.textSecondary, textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 4 }}>
          Apply Tag (Optional)
        </Text>
        <Text style={{ fontSize: 14, color: colors.textSecondary, marginBottom: 10 }}>
          Applying a tag starts the associated follow-up campaign
        </Text>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 4 }} data-testid="qs-tag-picker">
          {availableTags.map((tag: any) => {
            const isSelected = selectedTag === tag.name;
            return (
              <TouchableOpacity
                key={tag._id || tag.name}
                onPress={() => setSelectedTag(isSelected ? '' : tag.name)}
                style={{
                  flexDirection: 'row', alignItems: 'center',
                  paddingHorizontal: 12, paddingVertical: 8,
                  borderRadius: 20, borderWidth: 1.5,
                  borderColor: isSelected ? (tag.color || '#C9A962') : colors.border,
                  backgroundColor: isSelected ? `${tag.color || '#C9A962'}20` : colors.card,
                  gap: 6,
                }}
                data-testid={`qs-tag-${tag.name.toLowerCase().replace(/\s/g, '-')}`}
              >
                {isSelected && <Ionicons name="checkmark-circle" size={16} color={tag.color || '#C9A962'} />}
                <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: tag.color || '#8E8E93' }} />
                <Text style={{ fontSize: 15, fontWeight: isSelected ? '700' : '400', color: isSelected ? (tag.color || '#C9A962') : colors.text }}>
                  {tag.name}
                </Text>
              </TouchableOpacity>
            );
          })}
          {availableTags.length === 0 && (
            <Text style={{ fontSize: 15, color: colors.textSecondary, fontStyle: 'italic' }}>No tags yet</Text>
          )}
        </View>

        {/* Campaign toggle — only when a tag is selected */}
        {selectedTag ? (
          <TouchableOpacity
            style={{
              flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
              backgroundColor: colors.card, borderRadius: 10,
              paddingHorizontal: 14, paddingVertical: 12,
              marginTop: 10, borderWidth: 1, borderColor: colors.border,
            }}
            onPress={() => setStartCampaign(prev => !prev)}
            data-testid="qs-campaign-toggle"
          >
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, flex: 1 }}>
              <Ionicons name="megaphone-outline" size={18} color={startCampaign ? '#34C759' : colors.textSecondary} />
              <Text style={{ fontSize: 16, color: colors.text, flex: 1 }}>Start follow-up campaign</Text>
            </View>
            <View style={{
              width: 44, height: 26, borderRadius: 13,
              backgroundColor: startCampaign ? '#34C759' : colors.surface,
              justifyContent: 'center', paddingHorizontal: 2,
            }}>
              <View style={{
                width: 22, height: 22, borderRadius: 11, backgroundColor: '#fff',
                alignSelf: startCampaign ? 'flex-end' : 'flex-start',
                shadowColor: '#000', shadowOpacity: 0.15, shadowRadius: 2,
              }} />
            </View>
          </TouchableOpacity>
        ) : null}
      </View>

      {/* Send options */}
      <Text style={{ fontSize: 15, color: colors.textSecondary, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>
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
            <Text style={{ fontSize: 14, fontWeight: '600', color: sendMethod === opt.key ? '#C9A962' : colors.textTertiary, marginTop: 4 }}>{opt.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Send button */}
      <TouchableOpacity
        style={{ padding: 16, borderRadius: 14, backgroundColor: '#C9A962', alignItems: 'center' }}
        onPress={handleSend}
        data-testid="qs-send-btn"
      >
        <Text style={{ fontSize: 18, fontWeight: '700', color: '#000' }}>
          {sendMethod === 'copy' ? 'Copy Link' : sendMethod === 'email' ? 'Send Email' : 'Send via SMS'}
        </Text>
      </TouchableOpacity>

      {sendMethod === 'sms' && (
        <Text style={{ fontSize: 14, color: colors.textTertiary, textAlign: 'center', marginTop: 8 }}>
          This will open your phone's messaging app
        </Text>
      )}
    </ScrollView>
  );

  const renderSending = () => (
    <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 40 }}>
      <ActivityIndicator size="large" color="#C9A962" />
      <Text style={{ fontSize: 19, fontWeight: '600', color: colors.text, marginTop: 16 }}>Sending...</Text>
    </View>
  );

  const renderDone = () => (
    <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 40 }}>
      <View style={{ width: 80, height: 80, borderRadius: 40, backgroundColor: 'rgba(52,199,89,0.12)', alignItems: 'center', justifyContent: 'center', marginBottom: 20 }}>
        <Ionicons name="checkmark" size={40} color="#34C759" />
      </View>
      <Text style={{ fontSize: 24, fontWeight: '800', color: colors.text, marginBottom: 8 }}>Sent!</Text>
      <Text style={{ fontSize: 17, color: colors.textSecondary, textAlign: 'center', lineHeight: 22 }}>
        {config.previewTitle} sent to{'\n'}<Text style={{ fontWeight: '700', color: colors.text }}>{fullName}</Text>
      </Text>

      <View style={{ backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: colors.border, padding: 14, width: '100%', marginTop: 20 }}>
        <Text style={{ fontSize: 14, color: colors.textTertiary, fontWeight: '600', marginBottom: 8 }}>AUTOMATICALLY LOGGED</Text>
        {[
          { icon: 'checkmark-circle', text: `${config.previewTitle} shared`, color: '#34C759' },
          { icon: 'chatbubble', text: `${sendMethod === 'email' ? 'Email' : sendMethod === 'copy' ? 'Link copied' : 'SMS'} sent`, color: '#007AFF' },
          { icon: 'analytics', text: 'Activity feed updated', color: '#C9A962' },
          ...(!matchedContact ? [{ icon: 'person-add' as any, text: 'New contact created', color: '#AF52DE' }] : []),
          ...(selectedTag ? [{ icon: 'pricetag' as any, text: `Tag "${selectedTag}" applied`, color: '#FF9500' }] : []),
        ].map((item, i) => (
          <View key={i} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 4 }}>
            <Ionicons name={item.icon as any} size={16} color={item.color} />
            <Text style={{ fontSize: 16, color: colors.textSecondary, flex: 1 }}>{item.text}</Text>
            <Ionicons name="checkmark" size={16} color="#34C759" />
          </View>
        ))}
      </View>

      <Text style={{ fontSize: 15, color: colors.textTertiary, marginTop: 16 }}>Redirecting to contact...</Text>
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
        <Text style={{ flex: 1, textAlign: 'center', fontSize: 19, fontWeight: '700', color: colors.text }}>
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
