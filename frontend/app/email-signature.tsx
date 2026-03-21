import React, { useState, useCallback } from 'react';
import { View, Text, ScrollView, TouchableOpacity, StyleSheet, Platform, Alert } from 'react-native';
import { useRouter, Stack } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '../store/authStore';
import * as Clipboard from 'expo-clipboard';

const APP_URL = process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com';

type LinkOption = 'card' | 'showcase' | 'linkpage' | 'landing';

export default function EmailSignaturePage() {
  const router = useRouter();
  const { user } = useAuthStore();
  const profile = user as any;
  const [selectedLink, setSelectedLink] = useState<LinkOption>('card');
  const [copied, setCopied] = useState<'html' | 'text' | null>(null);

  const getProfileUrl = useCallback(() => {
    if (!profile) return '';
    switch (selectedLink) {
      case 'card': return `${APP_URL}/card/${profile._id}`;
      case 'showcase': return `${APP_URL}/showcase/${profile.seo_slug || profile._id}`;
      case 'linkpage': return `${APP_URL}/l/${profile.username || profile._id}`;
      case 'landing': return `${APP_URL}/p/${profile._id}`;
      default: return `${APP_URL}/card/${profile._id}`;
    }
  }, [profile, selectedLink]);

  const getLinkLabel = useCallback(() => {
    switch (selectedLink) {
      case 'card': return 'View My Digital Card';
      case 'showcase': return 'See My Customer Reviews';
      case 'linkpage': return 'Visit My Link Page';
      case 'landing': return 'Visit My Landing Page';
      default: return 'View My Profile';
    }
  }, [selectedLink]);

  const photoUrl = profile?.photo_url
    ? (profile.photo_url.startsWith('http') ? profile.photo_url : `${APP_URL}${profile.photo_url}`)
    : null;

  const buildHtml = useCallback(() => {
    if (!profile) return '';
    const url = getProfileUrl();
    const label = getLinkLabel();
    const socials = profile.social_links || {};
    let socialHtml = '';
    if (socials.linkedin) socialHtml += `<a href="${socials.linkedin}" style="color:#0A66C2;text-decoration:none;margin-right:8px;font-size:13px;">LinkedIn</a>`;
    if (socials.instagram) socialHtml += `<a href="https://instagram.com/${socials.instagram.replace('@','')}" style="color:#E1306C;text-decoration:none;margin-right:8px;font-size:13px;">Instagram</a>`;
    if (socials.facebook) socialHtml += `<a href="${socials.facebook}" style="color:#1877F2;text-decoration:none;margin-right:8px;font-size:13px;">Facebook</a>`;

    return `<table cellpadding="0" cellspacing="0" border="0" style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#333333;line-height:1.4;">
  <tr>
    <td style="padding-right:16px;vertical-align:top;">
      ${photoUrl ? `<a href="${url}" style="text-decoration:none;"><img src="${photoUrl}" alt="${profile.name}" width="80" height="80" style="border-radius:50%;width:80px;height:80px;object-fit:cover;display:block;" /></a>` : ''}
    </td>
    <td style="vertical-align:top;">
      <a href="${url}" style="font-size:16px;font-weight:bold;color:#111111;text-decoration:none;">${profile.name || ''}</a><br/>
      ${profile.title ? `<span style="font-size:13px;color:#666666;">${profile.title}${profile.organization_name ? ` | ${profile.organization_name}` : ''}</span><br/>` : ''}
      <table cellpadding="0" cellspacing="0" border="0" style="margin-top:6px;font-size:13px;color:#555555;">
        ${profile.phone ? `<tr><td style="padding-right:6px;">P:</td><td><a href="tel:${profile.phone}" style="color:#555555;text-decoration:none;">${profile.phone}</a></td></tr>` : ''}
        ${profile.email ? `<tr><td style="padding-right:6px;">E:</td><td><a href="mailto:${profile.email}" style="color:#555555;text-decoration:none;">${profile.email}</a></td></tr>` : ''}
      </table>
      <table cellpadding="0" cellspacing="0" border="0" style="margin-top:10px;">
        <tr>
          <td>
            <a href="${url}" style="display:inline-block;background:#007AFF;color:#ffffff;font-size:13px;font-weight:bold;padding:8px 18px;border-radius:6px;text-decoration:none;">${label}</a>
          </td>
        </tr>
      </table>
      ${socialHtml ? `<div style="margin-top:8px;">${socialHtml}</div>` : ''}
    </td>
  </tr>
</table>`;
  }, [profile, photoUrl, getProfileUrl, getLinkLabel]);

  const buildPlainText = useCallback(() => {
    if (!profile) return '';
    const url = getProfileUrl();
    let text = profile.name || '';
    if (profile.title) text += `\n${profile.title}`;
    if (profile.organization_name) text += ` | ${profile.organization_name}`;
    if (profile.phone) text += `\nP: ${profile.phone}`;
    if (profile.email) text += `\nE: ${profile.email}`;
    text += `\n\n${url}`;
    return text;
  }, [profile, getProfileUrl]);

  const copyToClipboard = async (type: 'html' | 'text') => {
    const content = type === 'html' ? buildHtml() : buildPlainText();
    if (Platform.OS === 'web') {
      if (type === 'html') {
        try {
          await navigator.clipboard.write([
            new ClipboardItem({
              'text/html': new Blob([content], { type: 'text/html' }),
              'text/plain': new Blob([buildPlainText()], { type: 'text/plain' }),
            }),
          ]);
        } catch {
          await navigator.clipboard.writeText(type === 'html' ? content : buildPlainText());
        }
      } else {
        await navigator.clipboard.writeText(content);
      }
    } else {
      await Clipboard.setStringAsync(type === 'html' ? content : buildPlainText());
    }
    setCopied(type);
    setTimeout(() => setCopied(null), 2500);
  };

  const linkOptions: { key: LinkOption; label: string; icon: string; desc: string }[] = [
    { key: 'card', label: 'Digital Card', icon: 'id-card', desc: 'Your contact info & QR code' },
    { key: 'showcase', label: 'Showcase', icon: 'images', desc: 'Your reviews & happy customers' },
    { key: 'linkpage', label: 'Link Page', icon: 'globe-outline', desc: 'All your links in one place' },
    { key: 'landing', label: 'Landing Page', icon: 'planet-outline', desc: 'Your personal welcome page' },
  ];

  if (!profile) {
    return (
      <View style={s.container}>
        <Stack.Screen options={{ headerShown: false }} />
        <View style={s.header}>
          <TouchableOpacity onPress={() => router.back()} style={s.backBtn} data-testid="sig-back-btn">
            <Ionicons name="arrow-back" size={24} color="#111" />
          </TouchableOpacity>
          <Text style={s.headerTitle}>Email Signature</Text>
          <View style={{ width: 40 }} />
        </View>
        <View style={s.loadingWrap}><Text style={s.loadingText}>Loading your profile...</Text></View>
      </View>
    );
  }

  return (
    <View style={s.container}>
      <Stack.Screen options={{ headerShown: false }} />
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn} data-testid="sig-back-btn">
          <Ionicons name="arrow-back" size={24} color="#111" />
        </TouchableOpacity>
        <Text style={s.headerTitle}>Email Signature</Text>
        <View style={{ width: 40 }} />
      </View>

      <ScrollView style={s.scroll} contentContainerStyle={s.scrollContent} showsVerticalScrollIndicator={false}>

        {/* LINK PICKER */}
        <Text style={s.sectionLabel}>Link destination</Text>
        <Text style={s.sectionHint}>Choose where the signature button links to</Text>
        <View style={s.linkGrid}>
          {linkOptions.map(opt => (
            <TouchableOpacity
              key={opt.key}
              style={[s.linkCard, selectedLink === opt.key && s.linkCardActive]}
              onPress={() => setSelectedLink(opt.key)}
              data-testid={`sig-link-${opt.key}`}
            >
              <Ionicons name={opt.icon as any} size={22} color={selectedLink === opt.key ? '#007AFF' : '#888'} />
              <Text style={[s.linkLabel, selectedLink === opt.key && s.linkLabelActive]}>{opt.label}</Text>
              <Text style={s.linkDesc}>{opt.desc}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* PREVIEW */}
        <Text style={[s.sectionLabel, { marginTop: 28 }]}>Preview</Text>
        <View style={s.previewCard} data-testid="sig-preview">
          <View style={s.previewInner}>
            {photoUrl && (
              <View style={s.previewPhoto}>
                <img src={photoUrl} alt={profile.name} style={{ width: 72, height: 72, borderRadius: 36, objectFit: 'cover' } as any} />
              </View>
            )}
            <View style={s.previewInfo}>
              <Text style={s.previewName}>{profile.name}</Text>
              {profile.title && (
                <Text style={s.previewTitle}>
                  {profile.title}{profile.organization_name ? ` | ${profile.organization_name}` : ''}
                </Text>
              )}
              {profile.phone && <Text style={s.previewDetail}>P: {profile.phone}</Text>}
              {profile.email && <Text style={s.previewDetail}>E: {profile.email}</Text>}
              <View style={s.previewBtnWrap}>
                <View style={s.previewBtn}>
                  <Text style={s.previewBtnText}>{getLinkLabel()}</Text>
                </View>
              </View>
              {profile.social_links && Object.values(profile.social_links).some(Boolean) && (
                <View style={s.previewSocials}>
                  {profile.social_links.linkedin && <Text style={[s.socialTag, { color: '#0A66C2' }]}>LinkedIn</Text>}
                  {profile.social_links.instagram && <Text style={[s.socialTag, { color: '#E1306C' }]}>Instagram</Text>}
                  {profile.social_links.facebook && <Text style={[s.socialTag, { color: '#1877F2' }]}>Facebook</Text>}
                </View>
              )}
            </View>
          </View>
        </View>

        {/* COPY BUTTONS */}
        <View style={s.copyRow}>
          <TouchableOpacity
            style={[s.copyBtn, copied === 'html' && s.copyBtnDone]}
            onPress={() => copyToClipboard('html')}
            data-testid="sig-copy-html"
          >
            <Ionicons name={copied === 'html' ? 'checkmark-circle' : 'copy-outline'} size={18} color="#FFF" />
            <Text style={s.copyBtnText}>{copied === 'html' ? 'Copied!' : 'Copy Rich Signature'}</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[s.copyBtnAlt, copied === 'text' && s.copyBtnDone]}
            onPress={() => copyToClipboard('text')}
            data-testid="sig-copy-text"
          >
            <Ionicons name={copied === 'text' ? 'checkmark-circle' : 'document-text-outline'} size={18} color={copied === 'text' ? '#FFF' : '#333'} />
            <Text style={[s.copyBtnAltText, copied === 'text' && { color: '#FFF' }]}>{copied === 'text' ? 'Copied!' : 'Copy Plain Text'}</Text>
          </TouchableOpacity>
        </View>

        {/* INSTRUCTIONS */}
        <Text style={[s.sectionLabel, { marginTop: 32 }]}>How to add your signature</Text>

        <View style={s.instrCard}>
          <View style={s.instrHeader}>
            <Ionicons name="mail" size={20} color="#EA4335" />
            <Text style={s.instrTitle}>Gmail</Text>
          </View>
          <Text style={s.instrStep}>1. Open Gmail and click the gear icon, then "See all settings"</Text>
          <Text style={s.instrStep}>2. Scroll to the "Signature" section</Text>
          <Text style={s.instrStep}>3. Click "Create new" or edit your existing signature</Text>
          <Text style={s.instrStep}>4. Clear the box, then paste (Ctrl+V / Cmd+V)</Text>
          <Text style={s.instrStep}>5. Scroll down and click "Save Changes"</Text>
        </View>

        <View style={s.instrCard}>
          <View style={s.instrHeader}>
            <Ionicons name="mail" size={20} color="#0078D4" />
            <Text style={s.instrTitle}>Outlook / Microsoft 365</Text>
          </View>
          <Text style={s.instrStep}>1. Click the gear icon, then "View all Outlook settings"</Text>
          <Text style={s.instrStep}>2. Go to Mail &gt; Compose and reply</Text>
          <Text style={s.instrStep}>3. Under "Email signature", clear the box and paste</Text>
          <Text style={s.instrStep}>4. Check "Automatically include my signature" for new and replies</Text>
          <Text style={s.instrStep}>5. Click "Save"</Text>
        </View>

        <View style={s.instrCard}>
          <View style={s.instrHeader}>
            <Ionicons name="phone-portrait-outline" size={20} color="#007AFF" />
            <Text style={s.instrTitle}>iPhone / Apple Mail</Text>
          </View>
          <Text style={s.instrStep}>1. Copy the "Plain Text" version above</Text>
          <Text style={s.instrStep}>2. Go to Settings &gt; Apps &gt; Mail &gt; Signature</Text>
          <Text style={s.instrStep}>3. Clear the existing signature and paste</Text>
          <Text style={s.instrNote}>Note: Apple Mail on iPhone only supports plain text signatures. For rich HTML signatures, use Gmail or Outlook.</Text>
        </View>

        <View style={s.instrCard}>
          <View style={s.instrHeader}>
            <Ionicons name="logo-google" size={20} color="#34A853" />
            <Text style={s.instrTitle}>Gmail App (iOS / Android)</Text>
          </View>
          <Text style={s.instrStep}>1. Open Gmail app &gt; tap the menu &gt; Settings</Text>
          <Text style={s.instrStep}>2. Select your account &gt; "Mobile Signature"</Text>
          <Text style={s.instrStep}>3. Paste the plain text version</Text>
          <Text style={s.instrNote}>Tip: For the best-looking signature, set it up on desktop Gmail — it will apply to mobile too.</Text>
        </View>

        <View style={{ height: 40 }} />
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F8F9FB' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingTop: Platform.OS === 'ios' ? 56 : 16, paddingHorizontal: 16, paddingBottom: 12, backgroundColor: '#FFF', borderBottomWidth: 1, borderBottomColor: 'rgba(0,0,0,0.06)' },
  backBtn: { width: 40, height: 40, borderRadius: 12, backgroundColor: '#F2F2F7', alignItems: 'center', justifyContent: 'center' },
  headerTitle: { fontSize: 17, fontWeight: '700', color: '#111' },
  loadingWrap: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  loadingText: { fontSize: 15, color: '#888' },
  scroll: { flex: 1 },
  scrollContent: { padding: 20 },
  sectionLabel: { fontSize: 16, fontWeight: '700', color: '#111', marginBottom: 4 },
  sectionHint: { fontSize: 13, color: '#888', marginBottom: 14 },
  linkGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  linkCard: { width: '48%' as any, backgroundColor: '#FFF', borderRadius: 14, padding: 14, borderWidth: 2, borderColor: 'rgba(0,0,0,0.06)' },
  linkCardActive: { borderColor: '#007AFF', backgroundColor: 'rgba(0,122,255,0.04)' },
  linkLabel: { fontSize: 14, fontWeight: '700', color: '#333', marginTop: 8 },
  linkLabelActive: { color: '#007AFF' },
  linkDesc: { fontSize: 11, color: '#888', marginTop: 2, lineHeight: 15 },
  previewCard: { backgroundColor: '#FFF', borderRadius: 16, padding: 20, borderWidth: 1, borderColor: 'rgba(0,0,0,0.06)', shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.04, shadowRadius: 8 },
  previewInner: { flexDirection: 'row', gap: 16 },
  previewPhoto: { width: 72, height: 72, borderRadius: 36, overflow: 'hidden' },
  previewInfo: { flex: 1 },
  previewName: { fontSize: 16, fontWeight: '800', color: '#111' },
  previewTitle: { fontSize: 13, color: '#666', marginTop: 2 },
  previewDetail: { fontSize: 13, color: '#555', marginTop: 2 },
  previewBtnWrap: { marginTop: 10 },
  previewBtn: { backgroundColor: '#007AFF', paddingHorizontal: 16, paddingVertical: 8, borderRadius: 6, alignSelf: 'flex-start' },
  previewBtnText: { color: '#FFF', fontSize: 13, fontWeight: '700' },
  previewSocials: { flexDirection: 'row', gap: 10, marginTop: 8 },
  socialTag: { fontSize: 12, fontWeight: '600' },
  copyRow: { flexDirection: 'row', gap: 10, marginTop: 20 },
  copyBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#007AFF', paddingVertical: 14, borderRadius: 12 },
  copyBtnDone: { backgroundColor: '#34C759' },
  copyBtnText: { color: '#FFF', fontSize: 14, fontWeight: '700' },
  copyBtnAlt: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#F2F2F7', paddingVertical: 14, borderRadius: 12, borderWidth: 1, borderColor: 'rgba(0,0,0,0.08)' },
  copyBtnAltText: { color: '#333', fontSize: 14, fontWeight: '700' },
  instrCard: { backgroundColor: '#FFF', borderRadius: 14, padding: 16, marginTop: 12, borderWidth: 1, borderColor: 'rgba(0,0,0,0.06)' },
  instrHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 },
  instrTitle: { fontSize: 15, fontWeight: '700', color: '#111' },
  instrStep: { fontSize: 13, color: '#555', lineHeight: 20, marginBottom: 4 },
  instrNote: { fontSize: 12, color: '#007AFF', marginTop: 6, fontStyle: 'italic', lineHeight: 17 },
});
