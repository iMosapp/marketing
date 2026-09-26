import React, { useState } from 'react';
import { View, Text, TouchableOpacity, TextInput, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';
import { GOLD, tid, timeAgo } from '../inbox/ownership';
import { Section, Label, Hint, inputStyle } from '../inbox/InboxEditorParts';

type Props = { widget: any; colors: any; domains: string; setDomains: (v: string) => void; onRotate: () => void; onDisable: () => void; showToast: (m: string, t?: any) => void };

export const InstallCard = ({ widget, colors, domains, setDomains, onRotate, onDisable, showToast }: Props) => {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      if (Platform.OS === 'web' && navigator?.clipboard) await navigator.clipboard.writeText(widget.snippet);
      else await Clipboard.setStringAsync(widget.snippet);
      setCopied(true); showToast('Install code copied', 'success'); setTimeout(() => setCopied(false), 2500);
    } catch { showToast('Could not copy. Long-press the code to select it.', 'error'); }
  };
  return (
    <>
      <Section colors={colors} testId="widget-section-install">
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 }}>
          <View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: widget.installed ? '#34C759' : '#FF9500' }} />
          <Text style={{ fontSize: 13, fontWeight: '800', color: colors.text }} {...tid('widget-install-status')}>
            {widget.installed ? `Live on ${widget.last_seen_host || 'your site'} · seen ${timeAgo(widget.last_seen_at)}` : 'Not seen on a website yet'}
          </Text>
        </View>
        <Label colors={colors}>One line, every page</Label>
        <Hint colors={colors}>Paste it right before {'</body>'} in your site's template, or in the header/footer scripts box of your website provider (Dealer.com, DealerOn, Wix, WordPress, Google Tag Manager all work). Done once, the widget follows every change you save here.</Hint>
        <TouchableOpacity onPress={copy} activeOpacity={0.85} style={{ backgroundColor: '#111', borderRadius: 12, padding: 14 }} {...tid('widget-snippet')}>
          <Text selectable style={{ fontSize: 12.5, color: '#E5E5EA', fontFamily: Platform.OS === 'web' ? 'monospace' : undefined, lineHeight: 18 }}>{widget.snippet}</Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={copy} style={{ marginTop: 10, height: 48, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8 }} {...tid('widget-copy-snippet')}>
          <Ionicons name={copied ? 'checkmark' : 'copy-outline'} size={18} color="#111" />
          <Text style={{ fontSize: 15, fontWeight: '800', color: '#111' }}>{copied ? 'Copied' : 'Copy install code'}</Text>
        </TouchableOpacity>
      </Section>

      <Section colors={colors} testId="widget-section-domains">
        <Label colors={colors}>Only run on these sites (optional)</Label>
        <Hint colors={colors}>Comma separated, like yourdealership.com, yourdealership.net. Blank = any site that has the code.</Hint>
        <TextInput value={domains} onChangeText={setDomains} placeholder="yourdealership.com" placeholderTextColor={colors.textSecondary} autoCapitalize="none" autoCorrect={false} style={inputStyle(colors)} {...tid('widget-domains')} />
      </Section>

      <Section colors={colors} testId="widget-section-danger">
        <Label colors={colors}>Housekeeping</Label>
        <TouchableOpacity onPress={onRotate} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10 }} {...tid('widget-rotate-key')}>
          <Ionicons name="key-outline" size={18} color={colors.textSecondary} />
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>Get a new install code</Text>
            <Text style={{ fontSize: 12, color: colors.textSecondary }}>The old one stops working. You will need to paste the new line on the site.</Text>
          </View>
        </TouchableOpacity>
        <TouchableOpacity onPress={onDisable} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10 }} {...tid('widget-disable')}>
          <Ionicons name="power-outline" size={18} color="#FF3B30" />
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 14, fontWeight: '700', color: '#FF3B30' }}>Turn the widget off</Text>
            <Text style={{ fontSize: 12, color: colors.textSecondary }}>The bubble disappears from your site until you create it again.</Text>
          </View>
        </TouchableOpacity>
      </Section>
    </>
  );
};
