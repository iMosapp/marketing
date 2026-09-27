import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, tid } from '../inbox/ownership';
import { Section, Label, Hint, inputStyle } from '../inbox/InboxEditorParts';
import { ColorField, Chips, Field, ToggleRow, Stepper, Swatch, contrastText } from './parts';
import { PageRulesSection } from './PageRulesSection';
import { ImageField } from './ImageField';
import { PersonaSection } from './PersonaSection';

const TEASER_PAGES: Record<string, { key: string; label: string; path: string }[]> = {
  dealership: [{ key: 'home', label: 'Home page', path: '/' }, { key: 'inventory', label: 'Inventory lists', path: '/inventory' }, { key: 'vehicle', label: 'A vehicle page', path: '/vehicle-details/123' }, { key: 'service', label: 'Service', path: '/service' }, { key: 'finance', label: 'Financing', path: '/finance' }, { key: 'specials', label: 'Specials', path: '/specials' }],
  business: [{ key: 'home', label: 'Home page', path: '/' }, { key: 'pricing', label: 'Pricing', path: '/pricing' }, { key: 'features', label: 'Features / product', path: '/features' }],
};
const TEASER_DEFAULTS: Record<string, string> = {
  home: 'Hi! Looking for something specific today? I can help.', inventory: 'Not sure which to pick? I can help you narrow it down.', vehicle: 'Have a question about this one? Ask me, or I can set up a test drive.',
  service: 'Need service? I can get you scheduled in about a minute.', finance: 'Questions about financing or payments? I can point you the right way.', specials: 'Wondering if a special applies to you? Just ask.',
  pricing: 'Questions about plans or pricing? Ask away, I know them cold.', features: 'Want to see how this would work for your team? I can walk you through it.',
};
const BIZ_HOME = 'Hi! Want a quick tour of what we do?';

const ICONS = [
  { value: 'text', label: 'Text', icon: 'phone-portrait-outline' }, { value: 'chat', label: 'Chat', icon: 'chatbubble-outline' }, { value: 'phone', label: 'Phone', icon: 'call-outline' },
  { value: 'sparkles', label: 'Sparkle', icon: 'sparkles-outline' }, { value: 'menu', label: 'Menu', icon: 'menu-outline' }, { value: 'image', label: 'My own', icon: 'image-outline' },
];

type Props = { form: any; set: (section: string, patch: any) => void; colors: any; swatches: Swatch[]; siteUrl: string; setSiteUrl: (v: string) => void; onMatchSite: () => void; matching: boolean; previewPath: string; setPreviewPath: (p: string) => void;
  widgetId: string; showToast: (m: string, t?: any, d?: number) => void; canManage: boolean };

export const LookTab = ({ form, set, colors, swatches, siteUrl, setSiteUrl, onMatchSite, matching, previewPath, setPreviewPath, widgetId, showToast, canManage }: Props) => {
  const a = form.appearance;
  const person = a.launcher === 'person';
  const mode = form.kb?.mode === 'business' ? 'business' : 'dealership';
  const teasers = a.smart_teasers || {};
  const [showCustom, setShowCustom] = useState(false);
  const pickPerson = (v: string) => {
    set('appearance', { launcher: v, ...(v === 'person' ? { greeting_on: true } : {}) });
    if (v === 'person' && !form.persona?.on) set('persona', { on: true });
  };
  return (
    <>
      <Section colors={colors} testId="widget-section-match">
        <Label colors={colors}>Match my website</Label>
        <Hint colors={colors}>Paste your site address and we pull its colors so the bubble looks like it was always there.</Hint>
        <View style={{ flexDirection: 'row', gap: 8 }}>
          <TextInput value={siteUrl} onChangeText={setSiteUrl} placeholder="www.yourdealership.com" placeholderTextColor={colors.textSecondary} autoCapitalize="none" autoCorrect={false} keyboardType="url"
            style={[inputStyle(colors), { flex: 1 }]} {...tid('widget-site-url')} />
          <TouchableOpacity onPress={onMatchSite} disabled={matching || !siteUrl.trim()} style={{ height: 46, paddingHorizontal: 14, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', opacity: matching || !siteUrl.trim() ? 0.5 : 1 }} {...tid('widget-match-site-btn')}>
            {matching ? <ActivityIndicator color="#111" /> : <Text style={{ fontSize: 14, fontWeight: '800', color: '#111' }}>Pull colors</Text>}
          </TouchableOpacity>
        </View>
      </Section>

      <Section colors={colors} testId="widget-section-launcher">
        <Label colors={colors}>What sits in the corner</Label>
        <Hint colors={colors}>{person ? 'A round photo of your assistant with a green "online" dot and a speech-bubble teaser, like a person waiting to help. Uses the name and face below.' : 'A classic button bubble with an icon and optional label.'}</Hint>
        <Chips options={[{ value: 'bubble', label: 'Button bubble', icon: 'chatbubble-ellipses-outline' }, { value: 'person', label: 'A person (photo)', icon: 'person-circle-outline' }]} value={a.launcher || 'bubble'} onChange={pickPerson} colors={colors} testId="widget-launcher" />
      </Section>

      <PersonaSection persona={form.persona} setPersona={p => set('persona', p)} widgetId={widgetId} colors={colors} showToast={showToast} canManage={canManage} />

      <Section colors={colors} testId="widget-section-bubble">
        <Label colors={colors}>{person ? 'Colors and placement' : 'The bubble'}</Label>
        <ColorField label={person ? 'Accent color (buttons, visitor bubbles)' : 'Bubble color'} value={a.bubble_color} onChange={hex => set('appearance', { bubble_color: hex, text_color: contrastText(hex) })} colors={colors} testId="widget-bubble-color" swatches={swatches} />
        {!person ? (
          <>
            <Label colors={colors} top>Icon</Label>
            <Chips options={ICONS} value={a.icon} onChange={v => { set('appearance', { icon: v }); if (v === 'image') setShowCustom(true); }} colors={colors} testId="widget-icon" />
            {(a.icon === 'image' || showCustom) && (
              <ImageField label="Your own icon" hint="Your logo mark works best: square, PNG or SVG, on a transparent or matching background." value={a.icon_url} onChange={v => set('appearance', { icon_url: v })} widgetId={widgetId} target="icon" colors={colors} testId="widget-icon-image" showToast={showToast} canManage={canManage} />
            )}
            <ToggleRow label="Show a label next to the icon" value={!!a.label_on} onChange={v => set('appearance', { label_on: v })} colors={colors} testId="widget-label-on" />
            {a.label_on ? <Field label="Label" value={a.label} onChange={v => set('appearance', { label: v })} placeholder="Text Us" colors={colors} testId="widget-label" maxLength={30} top={false} /> : null}
          </>
        ) : null}
        <Label colors={colors} top>Corner of the screen</Label>
        <Chips options={[{ value: 'right', label: 'Bottom right', icon: 'arrow-forward' }, { value: 'left', label: 'Bottom left', icon: 'arrow-back' }]} value={a.position} onChange={v => set('appearance', { position: v })} colors={colors} testId="widget-position" />
        <Stepper label="Distance from the bottom" value={Number(a.offset_y)} onChange={v => set('appearance', { offset_y: v })} min={0} max={200} step={10} unit="px" colors={colors} testId="widget-offset-y" />
        <Stepper label="Distance from the side" value={Number(a.offset_x ?? 20)} onChange={v => set('appearance', { offset_x: v })} min={0} max={120} step={10} unit="px" colors={colors} testId="widget-offset-x" />
        <Hint colors={colors}>On phones the bubble also stays clear of the home bar on its own. Nudge these if it crowds a sticky button on your site.</Hint>
        <ToggleRow label="Hide on phones" hint="Skip the bubble on screens narrower than 520px (if your site already has a sticky call bar)." value={!!a.hide_mobile} onChange={v => set('appearance', { hide_mobile: v })} colors={colors} testId="widget-hide-mobile" />
        <ToggleRow label="Let visitors tuck it away" hint="A small arrow on the bubble slides it off the edge, leaving a slim tab they can tap to bring it back. Remembered on their device." value={a.tuck_on !== false} onChange={v => set('appearance', { tuck_on: v })} colors={colors} testId="widget-tuck-on" />
      </Section>

      <Section colors={colors} testId="widget-section-greeting">
        <ToggleRow label={person ? 'Speech-bubble teaser' : 'Pop a greeting bubble'} hint={person ? 'The line your assistant says from the corner. Dismissed once per visit.' : 'A little speech bubble that invites the visitor to text. Dismissed once per visit.'} value={!!a.greeting_on} onChange={v => set('appearance', { greeting_on: v })} colors={colors} testId="widget-greeting-on" />
        {a.greeting_on ? (
          <>
            <Field label="Fallback line" hint="Used on pages the smart lines and page rules don't cover." value={a.greeting} onChange={v => set('appearance', { greeting: v })} multiline colors={colors} testId="widget-greeting" maxLength={200} />
            <Stepper label="Show after" value={Number(a.greeting_delay_s)} onChange={v => set('appearance', { greeting_delay_s: v })} min={0} max={60} step={2} unit="s" colors={colors} testId="widget-greeting-delay" />
            <ToggleRow label="Smart lines by page" hint="Reads the page address and picks a fitting line: inventory, a vehicle page, service, financing, specials. Your page rules below still win when they match." value={a.smart_teasers_on !== false} onChange={v => set('appearance', { smart_teasers_on: v })} colors={colors} testId="widget-smart-teasers-on" />
            {a.smart_teasers_on !== false ? TEASER_PAGES[mode].map(tp => (
              <View key={tp.key} {...tid(`widget-teaser-${tp.key}`)}>
                <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
                  <Label colors={colors} top>{tp.label}</Label>
                  <TouchableOpacity onPress={() => setPreviewPath(previewPath === tp.path ? '' : tp.path)} style={{ flexDirection: 'row', alignItems: 'center', gap: 5, paddingTop: 10 }} {...tid(`widget-teaser-${tp.key}-preview`)}>
                    <Ionicons name={previewPath === tp.path ? 'eye-off-outline' : 'eye-outline'} size={15} color={GOLD} />
                    <Text style={{ fontSize: 12, fontWeight: '700', color: GOLD }}>{previewPath === tp.path ? 'Normal preview' : 'Preview'}</Text>
                  </TouchableOpacity>
                </View>
                <TextInput value={teasers[tp.key] ?? ''} onChangeText={v => set('appearance', { smart_teasers: { ...teasers, [tp.key]: v } })} placeholder={mode === 'business' && tp.key === 'home' ? BIZ_HOME : TEASER_DEFAULTS[tp.key]} placeholderTextColor={colors.textSecondary} maxLength={160}
                  style={inputStyle(colors)} {...tid(`widget-teaser-${tp.key}-input`)} />
              </View>
            )) : null}
            {a.smart_teasers_on !== false ? <Hint colors={colors}>Leave a line blank to use the suggestion shown in grey.</Hint> : null}
          </>
        ) : null}
      </Section>

      <PageRulesSection rules={a.page_rules || []} onChange={rules => set('appearance', { page_rules: rules })} doors={form.doors} colors={colors} onPreview={setPreviewPath} previewPath={previewPath} />

      <Section colors={colors} testId="widget-section-panel">
        <Label colors={colors}>The window</Label>
        <ColorField label="Window background" value={a.panel_color} onChange={hex => set('appearance', { panel_color: hex, panel_text: contrastText(hex) })} colors={colors} testId="widget-panel-color" />
        <Stepper label="Rounded corners" value={Number(a.radius)} onChange={v => set('appearance', { radius: v })} min={0} max={32} step={4} unit="px" colors={colors} testId="widget-radius" />
        <ImageField label="Photo or logo in the window header" hint="Your store logo or a photo of the team. Leave empty for the store initial." value={a.avatar_url} onChange={v => set('appearance', { avatar_url: v })} widgetId={widgetId} target="avatar" colors={colors} testId="widget-avatar-image" round showToast={showToast} canManage={canManage} />
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 10 }}>
          <Ionicons name="information-circle-outline" size={16} color={colors.textSecondary} />
          <Text style={{ flex: 1, fontSize: 12, color: colors.textSecondary, lineHeight: 16 }}>Fonts follow your website automatically so the widget looks native.</Text>
        </View>
      </Section>
    </>
  );
};
