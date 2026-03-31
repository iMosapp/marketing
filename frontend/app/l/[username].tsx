import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView, Image, Linking, Platform, ActivityIndicator } from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { trackCustomerAction } from '../../services/tracking';
import { SEOHead } from '../../components/SEOHead';

const ICON_MAP: Record<string, string> = {
  'logo-instagram': 'logo-instagram',
  'logo-facebook': 'logo-facebook',
  'logo-tiktok': 'logo-tiktok',
  'logo-linkedin': 'logo-linkedin',
  'logo-youtube': 'logo-youtube',
  'logo-twitter': 'logo-twitter',
  'call': 'call',
  'mail': 'mail',
  'card': 'card',
  'star': 'star',
  'globe': 'globe-outline',
  'link': 'link',
  'images': 'images',
  'sms': 'chatbubble',
  'storefront': 'storefront',
  'planet': 'planet-outline',
};

interface LinkItem { id: string; label: string; url: string; icon: string; color: string; visible: boolean; }
interface PageData {
  username: string; display_name: string; bio: string; photo_url: string;
  company: string; built_social_links: LinkItem[]; contact_links: LinkItem[];
  custom_links: LinkItem[]; theme: string; accent_color: string;
  user_id?: string;
  // Legacy fields for backward compat
  links?: LinkItem[];
}

export default function PublicLinkPage() {
  const { username, cid } = useLocalSearchParams<{ username: string; cid?: string }>();
  const [data, setData] = useState<PageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (username) loadPage();
  }, [username]);

  const loadPage = async () => {
    try {
      const cidParam = cid ? `?cid=${cid}` : '';
      const res = await api.get(`/linkpage/public/${username}${cidParam}`);
      setData(res.data);
    } catch { setNotFound(true); }
    finally { setLoading(false); }
  };

  const openLink = (link: LinkItem) => {
    // Legacy counter
    api.post(`/linkpage/public/${username}/click`, { link_id: link.id }).catch(() => {});
    // Universal tracking
    if (data?.user_id) {
      trackCustomerAction('link_page', 'link_clicked', {
        salesperson_id: data.user_id,
        contact_id: cid || undefined,
        url: link.url,
        metadata: { link_id: link.id, link_label: link.label },
      });
    }
    const url = link.url.startsWith('/') ? `${process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com'}${link.url}` : link.url;
    Linking.openURL(url).catch(() => {});
  };

  const isDark = !data || data.theme === 'dark';
  const accent = data?.accent_color || '#C9A962';
  const photoBorderColor = data?.primary_color || (isDark ? '#3A3A3C' : '#D1D1D6');
  const bg = isDark ? '#000' : '#F2F2F7';
  const cardBg = isDark ? '#1C1C1E' : '#FFFFFF';
  const textColor = isDark ? '#FFFFFF' : '#000000';
  const linkBorderColor = isDark ? '#2C2C2E' : '#D1D1D6';
  const subColor = isDark ? '#8E8E93' : '#6C6C70';

  if (!mounted || loading) return <View style={[s.center, { backgroundColor: bg }]}><ActivityIndicator size="large" color={accent} /></View>;
  if (notFound || !data) return (
    <View style={[s.center, { backgroundColor: bg }]}>
      <Text style={{ fontSize: 21, fontWeight: '700', color: textColor, marginBottom: 8 }}>Page Not Found</Text>
      <Text style={{ fontSize: 16, color: subColor }}>This link page doesn't exist yet.</Text>
      <View style={s.footer}><Text style={[s.footerText, { color: subColor }]}>powered by <Text style={s.footerBrand}>i'MOnsocial</Text></Text></View>
    </View>
  );

  // Use new separated fields, with fallback to legacy `links` array
  const socialLinks = data.built_social_links || [];
  const contactLinks = data.contact_links || data.links?.filter(l => l.visible !== false) || [];
  const customLinks = (data.custom_links || []).filter(l => l.visible !== false);

  return (
    <ScrollView style={{ flex: 1, backgroundColor: bg }} contentContainerStyle={s.page}>
      <SEOHead type="link" id={username as string} />
      <View style={s.profile}>
        {data.photo_url ? (
          <Image source={{ uri: data.photo_url }} style={[s.avatar, { borderColor: photoBorderColor }]} />
        ) : (
          <View style={[s.avatarPlaceholder, { borderColor: photoBorderColor, backgroundColor: isDark ? '#1C1C1E' : '#E5E5EA' }]}>
            <Text style={{ fontSize: 36, fontWeight: '800', color: textColor }}>
              {data.display_name ? data.display_name.split(' ').map(w => w[0]).join('').substring(0, 2).toUpperCase() : '?'}
            </Text>
          </View>
        )}
        <Text style={[s.name, { color: textColor }]}>{data.display_name}</Text>
        {data.company ? <Text style={[s.company, { color: subColor }]}>{data.company}</Text> : null}
        {data.bio ? <Text style={[s.bio, { color: subColor }]}>{data.bio}</Text> : null}
      </View>

      {/* Contact Links */}
      <View style={s.links}>
        {contactLinks.map(link => (
          <TouchableOpacity key={link.id} style={[s.linkBtn, { backgroundColor: cardBg, borderColor: linkBorderColor }]} onPress={() => openLink(link)} data-testid={`link-${link.id}`}>
            <View style={[s.linkIcon, { backgroundColor: `${link.color}18` }]}>
              <Ionicons name={(ICON_MAP[link.icon] || 'link') as any} size={18} color={link.color} />
            </View>
            <Text style={[s.linkLabel, { color: textColor }]}>{link.label}</Text>
            <Text style={{ color: subColor, fontSize: 16 }}>&rsaquo;</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Social Links */}
      {socialLinks.length > 0 && (
        <View style={s.links}>
          <Text style={[s.sectionLabel, { color: subColor }]}>Socials</Text>
          {socialLinks.map(link => (
            <TouchableOpacity key={link.id} style={[s.linkBtn, { backgroundColor: cardBg, borderColor: linkBorderColor }]} onPress={() => openLink(link)} data-testid={`link-${link.id}`}>
              <View style={[s.linkIcon, { backgroundColor: `${link.color}18` }]}>
                <Ionicons name={(ICON_MAP[link.icon] || 'link') as any} size={18} color={link.color} />
              </View>
              <Text style={[s.linkLabel, { color: textColor }]}>{link.label}</Text>
              <Text style={{ color: subColor, fontSize: 16 }}>&rsaquo;</Text>
            </TouchableOpacity>
          ))}
        </View>
      )}

      {/* Custom Links */}
      {customLinks.length > 0 && (
        <View style={s.links}>
          {customLinks.map(link => (
            <TouchableOpacity key={link.id} style={[s.linkBtn, { backgroundColor: cardBg, borderColor: linkBorderColor }]} onPress={() => openLink(link)} data-testid={`link-${link.id}`}>
              <View style={[s.linkIcon, { backgroundColor: `${link.color}18` }]}>
                <Ionicons name={(ICON_MAP[link.icon] || 'globe-outline') as any} size={18} color={link.color} />
              </View>
              <Text style={[s.linkLabel, { color: textColor }]}>{link.label}</Text>
              <Text style={{ color: subColor, fontSize: 16 }}>&rsaquo;</Text>
            </TouchableOpacity>
          ))}
        </View>
      )}

      <View style={s.footer}>
        <TouchableOpacity onPress={() => Linking.openURL('https://app.imonsocial.com/install.html')}>
          <Text style={[s.footerText, { color: subColor }]}>powered by <Text style={s.footerBrand}>i'MOnsocial</Text></Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  page: { maxWidth: 480, alignSelf: 'center', width: '100%', paddingHorizontal: 20, paddingTop: 48, paddingBottom: 32, minHeight: '100%' },
  profile: { alignItems: 'center', marginBottom: 28 },
  avatar: { width: 96, height: 96, borderRadius: 18, borderWidth: 3, marginBottom: 14 },
  avatarPlaceholder: { width: 96, height: 96, borderRadius: 18, borderWidth: 3, marginBottom: 14, alignItems: 'center', justifyContent: 'center' },
  name: { fontSize: 22, fontWeight: '800', letterSpacing: -0.3 },
  company: { fontSize: 15, fontWeight: '600', marginTop: 2, opacity: 0.5 },
  bio: { fontSize: 16, marginTop: 8, lineHeight: 21, opacity: 0.7, textAlign: 'center', maxWidth: 320 },
  links: { gap: 10, marginBottom: 8 },
  linkBtn: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderRadius: 14, borderWidth: 1 },
  linkIcon: { width: 36, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  linkLabel: { flex: 1, fontSize: 17, fontWeight: '600' },
  sectionLabel: { fontSize: 13, textTransform: 'uppercase', letterSpacing: 1.5, fontWeight: '700', marginTop: 10, marginBottom: -2, marginLeft: 4, opacity: 0.5 },
  footer: { alignItems: 'center', marginTop: 36, paddingTop: 20, borderTopWidth: 1, borderTopColor: 'rgba(128,128,128,0.15)' },
  footerText: { fontSize: 14, fontWeight: '600', opacity: 0.4 },
  footerBrand: { fontWeight: '800' },
});
