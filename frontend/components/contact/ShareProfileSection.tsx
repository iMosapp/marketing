import React, { useState } from 'react';
import { View, Text, TouchableOpacity, Modal, ActivityIndicator, Switch, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Sharing from 'expo-sharing';
import { File as ExpoFile, Paths } from 'expo-file-system';
import api from '../../services/api';
import { showSimpleAlert } from '../../services/alert';
import { copyToClipboard } from '../../utils/clipboard';

const GOLD = '#C9A962';
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });
type Link = { token: string; url: string; include_private: boolean; views: number };

// Share a contact's full profile (photo included) with anyone: .vcf card, public link, or plain text.
export default function ShareProfileSection({ userId, contactId, contactName, colors, s }: any) {
  const [open, setOpen] = useState(false);
  const [priv, setPriv] = useState(true);
  const [links, setLinks] = useState<Link[]>([]);
  const [busy, setBusy] = useState<'' | 'vcf' | 'link' | 'text' | 'revoke'>('');
  const [done, setDone] = useState<'' | 'link' | 'text'>('');
  const base = `/contacts/${userId}/${contactId}/share`;

  const openSheet = async () => {
    setOpen(true);
    try { setLinks((await api.get(base)).data.links || []); } catch {}
  };
  const flash = (k: 'link' | 'text') => { setDone(k); setTimeout(() => setDone(''), 2000); };
  const fail = (e: any, what: string) => showSimpleAlert(`${what} failed`, e?.response?.data?.detail || 'Please try again.');

  const sendVcf = async () => {
    setBusy('vcf');
    try {
      const res = await api.get(`${base}/vcard?include_private=${priv}`, { responseType: 'text', transformResponse: [(d: any) => d] });
      const filename = `${(contactName || 'contact').replace(/\s+/g, '_')}.vcf`;
      if (Platform.OS === 'web') {
        const url = URL.createObjectURL(new Blob([res.data], { type: 'text/vcard' }));
        const a = document.createElement('a'); a.href = url; a.download = filename; a.click();
        setTimeout(() => URL.revokeObjectURL(url), 5000);
      } else {
        const file = new ExpoFile(Paths.cache, filename);
        file.write(res.data);
        if (await Sharing.isAvailableAsync()) await Sharing.shareAsync(file.uri, { mimeType: 'text/vcard', UTI: 'public.vcard', dialogTitle: `Share ${contactName}` });
      }
      openSheet();
    } catch (e) { fail(e, 'Contact card'); }
    setBusy('');
  };

  const copyLink = async () => {
    setBusy('link');
    try {
      const res = await api.post(`${base}/link`, { include_private: priv });
      await copyToClipboard(res.data.url);
      setLinks(l => (l.some(x => x.token === res.data.token) ? l : [res.data, ...l]));
      flash('link');
    } catch (e) { fail(e, 'Copy link'); }
    setBusy('');
  };

  const copyText = async () => {
    setBusy('text');
    try {
      const res = await api.get(`${base}/text?include_private=${priv}`);
      await copyToClipboard(res.data.text);
      if (res.data.link) setLinks(l => (l.some(x => x.token === res.data.link.token) ? l : [res.data.link, ...l]));
      flash('text');
    } catch (e) { fail(e, 'Copy text'); }
    setBusy('');
  };

  const revoke = async (token: string) => {
    setBusy('revoke');
    try { await api.delete(`${base}/link/${token}`); setLinks(l => l.filter(x => x.token !== token)); } catch (e) { fail(e, 'Revoke'); }
    setBusy('');
  };

  const Btn = ({ onPress, icon, label, k, gold }: any) => (
    <TouchableOpacity onPress={onPress} disabled={!!busy} {...tid(`share-profile-${k}`)}
      style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, borderRadius: 16, paddingVertical: gold ? 15 : 13, marginTop: 10,
        backgroundColor: gold ? GOLD : 'transparent', borderWidth: gold ? 0 : 1, borderColor: colors.border, opacity: busy && busy !== k ? 0.5 : 1 }}>
      {busy === k ? <ActivityIndicator color={gold ? '#111' : colors.text} /> : <Ionicons name={done === k ? 'checkmark' : icon} size={16} color={done === k ? '#34C759' : gold ? '#111' : colors.text} />}
      <Text style={{ fontSize: gold ? 16 : 14, fontWeight: '800', color: done === k ? '#34C759' : gold ? '#111' : colors.text }}>{done === k ? 'Copied!' : label}</Text>
    </TouchableOpacity>
  );

  return (
    <>
      <View style={s.section}>
        <TouchableOpacity onPress={openSheet} {...tid('share-profile-btn')}
          style={{ flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: colors.card, borderRadius: 14, padding: 14, borderWidth: 1, borderColor: colors.border }}>
          <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: GOLD + '22', alignItems: 'center', justifyContent: 'center' }}>
            <Ionicons name="share-social" size={18} color={GOLD} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text }}>Share Profile</Text>
            <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 1 }}>Contact card with photo, link or text. No app needed</Text>
          </View>
          <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
        </TouchableOpacity>
      </View>

      <Modal visible={open} transparent animationType="slide" onRequestClose={() => setOpen(false)}>
        <TouchableOpacity style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.55)', justifyContent: 'flex-end' }} activeOpacity={1} onPress={() => setOpen(false)}>
          <TouchableOpacity activeOpacity={1} onPress={() => {}}>
            <View style={{ backgroundColor: colors.card, borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 20, paddingBottom: 34 }} {...tid('share-profile-sheet')}>
              <View style={{ width: 40, height: 4, borderRadius: 2, backgroundColor: colors.border, alignSelf: 'center', marginBottom: 16 }} />
              <Text style={{ fontSize: 19, fontWeight: '800', color: colors.text }}>Share {contactName || 'this contact'}</Text>
              <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 4, lineHeight: 18 }}>
                Works for anyone, even without the app. The contact card saves straight into their phone with the photo; the link opens a read-only profile page.
              </Text>

              <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 16, paddingVertical: 10, paddingHorizontal: 12, borderRadius: 12, backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.border }}>
                <View style={{ flex: 1, paddingRight: 10 }}>
                  <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>Include notes &amp; Relationship Intel</Text>
                  <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 1 }}>{priv ? 'Everything you know goes with it' : 'Basics, vehicle and tags only'}</Text>
                </View>
                <Switch value={priv} onValueChange={setPriv} trackColor={{ true: GOLD }} {...tid('share-profile-private-toggle')} />
              </View>

              <Btn k="vcf" gold icon="person-add" label="Send Contact Card (.vcf)" onPress={sendVcf} />
              <Btn k="link" icon="link" label="Copy Profile Link" onPress={copyLink} />
              <Btn k="text" icon="document-text-outline" label="Copy as Text" onPress={copyText} />

              {links.length > 0 && (
                <View style={{ marginTop: 14 }} {...tid('share-profile-links')}>
                  <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8, marginBottom: 6 }}>ACTIVE LINKS · NEVER EXPIRE UNTIL YOU TURN THEM OFF</Text>
                  {links.map(l => (
                    <View key={l.token} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 8, borderTopWidth: 1, borderTopColor: colors.border }} {...tid(`share-link-row-${l.token}`)}>
                      <Ionicons name={l.include_private ? 'lock-open-outline' : 'lock-closed-outline'} size={14} color={l.include_private ? '#FF9500' : '#34C759'} />
                      <View style={{ flex: 1 }}>
                        <Text style={{ fontSize: 12, color: colors.text, fontWeight: '600' }} numberOfLines={1}>{l.include_private ? 'Full profile (notes & intel)' : 'Basics only'}</Text>
                        <Text style={{ fontSize: 11, color: colors.textSecondary }}>{l.views} view{l.views === 1 ? '' : 's'} · {l.url.replace(/^https?:\/\//, '')}</Text>
                      </View>
                      <TouchableOpacity onPress={() => revoke(l.token)} disabled={!!busy} {...tid(`share-link-revoke-${l.token}`)} style={{ paddingVertical: 6, paddingHorizontal: 10, borderRadius: 8, backgroundColor: '#FF3B3018' }}>
                        <Text style={{ fontSize: 12, fontWeight: '700', color: '#FF3B30' }}>Turn off</Text>
                      </TouchableOpacity>
                    </View>
                  ))}
                </View>
              )}
            </View>
          </TouchableOpacity>
        </TouchableOpacity>
      </Modal>
    </>
  );
}
