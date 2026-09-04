import React from 'react';
import { View, Text, TouchableOpacity, Linking, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';

const FB = '#1877F2';
const GOLD = '#C9A962';
const MONO = Platform.select({ ios: 'Menlo', android: 'monospace', default: 'monospace' });
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });
export const ZAPIER_FB_TEMPLATE = 'https://zapier.com/webintent/create-zap?template=10288';

const ROWS: [string, string][] = [
  ['phone', 'Phone Number'],
  ['full_name', 'Full Name (or first_name + last_name if the form splits them)'],
  ['email', 'Email'],
  ['comments', 'Your custom question (vehicle, timing, trade)'],
  ['form_name', 'Form Name'],
  ['campaign_name', 'Campaign Name'],
  ['ad_name', 'Ad Name'],
  ['platform', 'Platform (fb or ig)'],
];

type Props = {
  sources: { id: string; name: string; is_active: boolean }[];
  selected: string | null;
  onSelect: (id: string) => void;
  webhookUrl?: string;
  apiKey?: string | null;
  headerName?: string;
  colors: any;
  onCopy: (value: string, label: string) => void;
};

export const FacebookRecipe = ({ sources, selected, onSelect, webhookUrl, apiKey, headerName, colors, onCopy }: Props) => {
  const router = useRouter();
  const fb = sources.find(s => /facebook|meta|instagram|\bfb\b/i.test(s.name));
  const using = fb && fb.id === selected;
  const sub = { fontSize: 13, color: colors.textSecondary, lineHeight: 18 } as const;
  const steps = [
    fb ? `Feed it into your "${fb.name}" source (tap Use it below).` : 'Create a "Facebook Lead Ads" source so Proof shows what Facebook really costs per sale.',
    'Tap Open the Zapier template. Sign in, then connect Facebook: pick your Page and the lead form.',
    `In the Webhooks POST step: URL below, Payload Type json${apiKey ? `, Headers ${headerName} with your key from step 2` : ''}.`,
    'Data: add the rows in the table. Left side exactly as written, right side picked from the Facebook fields.',
    'Test the step, watch step 4 turn green, publish. Facebook phone numbers arrive as +1..., that is fine.',
  ];
  return (
    <View style={{ backgroundColor: colors.card, borderRadius: 14, padding: 16, gap: 12, borderWidth: 1, borderColor: `${FB}66` }} {...tid('connect-fb-recipe')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
        <View style={{ width: 34, height: 34, borderRadius: 10, backgroundColor: `${FB}22`, alignItems: 'center', justifyContent: 'center' }}><Ionicons name="logo-facebook" size={20} color={FB} /></View>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text }}>Facebook Lead Ads in 5 minutes</Text>
          <Text style={sub}>Form submit to first text in seconds. No CSV, no inbox.</Text>
        </View>
      </View>

      {fb ? (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: colors.bg, borderRadius: 10, padding: 10 }}>
          <Ionicons name={using ? 'checkmark-circle' : 'ellipse-outline'} size={18} color={using ? '#34C759' : colors.textSecondary} />
          <Text style={{ flex: 1, fontSize: 13, color: colors.text }} numberOfLines={1}>{`Feeds "${fb.name}"`}</Text>
          {!using && (
            <TouchableOpacity onPress={() => onSelect(fb.id)} style={{ paddingHorizontal: 12, height: 30, borderRadius: 15, backgroundColor: GOLD, justifyContent: 'center' }} {...tid('connect-fb-use-source')}>
              <Text style={{ fontSize: 12, fontWeight: '700', color: '#000' }}>Use it</Text>
            </TouchableOpacity>
          )}
        </View>
      ) : (
        <TouchableOpacity onPress={() => router.push({ pathname: '/admin/lead-sources/new', params: { name: 'Facebook Lead Ads', description: 'Facebook and Instagram lead forms via Zapier' } } as any)}
          style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: colors.bg, borderRadius: 10, padding: 12, borderWidth: 1, borderColor: `${GOLD}66` }} {...tid('connect-fb-create-source')}>
          <Ionicons name="add-circle" size={18} color={GOLD} />
          <Text style={{ flex: 1, fontSize: 13, fontWeight: '700', color: GOLD }}>{'Create a "Facebook Lead Ads" source first'}</Text>
          <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
        </TouchableOpacity>
      )}

      <TouchableOpacity onPress={() => Linking.openURL(ZAPIER_FB_TEMPLATE)} style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: FB, borderRadius: 12, height: 46 }} {...tid('connect-fb-open-zapier')}>
        <Ionicons name="flash" size={18} color="#fff" />
        <Text style={{ fontSize: 15, fontWeight: '700', color: '#fff' }}>Open the Zapier template</Text>
        <Ionicons name="open-outline" size={16} color="#fff" />
      </TouchableOpacity>

      <View style={{ gap: 6 }}>
        {steps.map((t, i) => (
          <View key={i} style={{ flexDirection: 'row', gap: 10 }}>
            <Text style={{ fontSize: 13, fontWeight: '700', color: FB, width: 18 }}>{i + 1}.</Text>
            <Text style={[sub, { flex: 1 }]}>{t}</Text>
          </View>
        ))}
      </View>

      {!!webhookUrl && (
        <TouchableOpacity onPress={() => onCopy(webhookUrl, 'Webhook URL')} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: colors.bg, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, borderWidth: 1, borderColor: colors.border }} {...tid('connect-fb-copy-url')}>
          <Text style={{ flex: 1, fontSize: 12, color: colors.text, fontFamily: MONO }} numberOfLines={1}>{webhookUrl}</Text>
          <Ionicons name="copy-outline" size={18} color={GOLD} />
        </TouchableOpacity>
      )}

      <View style={{ gap: 6 }}>
        <Text style={{ fontSize: 12, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.6 }}>DATA ROWS IN THE POST STEP</Text>
        <View style={{ flexDirection: 'row', gap: 10 }}>
          <Text style={{ width: 112, fontSize: 11, color: colors.textSecondary }}>Left (type this)</Text>
          <Text style={{ flex: 1, fontSize: 11, color: colors.textSecondary }}>Right (pick from Facebook)</Text>
        </View>
        {ROWS.map(([k, v]) => (
          <View key={k} style={{ flexDirection: 'row', gap: 10, alignItems: 'flex-start' }} {...tid(`connect-fb-row-${k}`)}>
            <Text style={{ width: 112, fontSize: 12, color: k === 'phone' ? GOLD : colors.text, fontFamily: MONO }}>{k}</Text>
            <Text style={{ flex: 1, fontSize: 12, color: colors.textSecondary, lineHeight: 17 }}>{v}</Text>
          </View>
        ))}
        <Text style={sub}>Campaign, ad and form names ride along, so every Facebook lead in the queue shows which ad it came from.</Text>
      </View>
    </View>
  );
};
