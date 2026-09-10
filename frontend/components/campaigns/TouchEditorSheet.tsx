import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, ScrollView, Image, ActivityIndicator, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import api from '../../services/api';
import { useToast } from '../common/Toast';
import { SheetShell, Eyebrow, Chip, GoldButton, Segmented } from './Sheet';
import { Touch, PRESETS, matchPreset, touchMinutes, whenSentence, humanDelay, CARD_TYPES, MIN_FOLLOWUP_MINUTES, GOLD, AMBER, RED, tid } from './utils';
import type { QuickLink } from './useQuickLinks';

const TOKENS = [
  { key: '{first_name}', label: 'First name' },
  { key: '{vehicle}', label: 'Their purchase' },
  { key: '{my_name}', label: 'My name' },
  { key: '{company}', label: 'Company' },
  { key: '{review_link}', label: 'Review link' },
];

type Props = {
  touch: Touch;
  index: number;
  isFirst: boolean;
  triggerLabel: string;
  canRemove: boolean;
  campaignId: string;
  quickLinks: QuickLink[];
  aiPersonalizes: boolean;
  colors: any;
  onDone: (t: Touch) => void;
  onRemove: () => void;
  onClose: () => void;
};

export function TouchEditorSheet({ touch, index, isFirst, triggerLabel, canRemove, campaignId, quickLinks, aiPersonalizes, colors, onDone, onRemove, onClose }: Props) {
  const { showToast } = useToast();
  const [t, setT] = useState<Touch>({ ...touch, media_urls: [...(touch.media_urls || [])] });
  const [custom, setCustom] = useState(!matchPreset(touch) && touchMinutes(touch) > 0);
  const [uploading, setUploading] = useState(false);
  const set = (patch: Partial<Touch>) => setT(p => ({ ...p, ...patch }));

  const preset = custom ? undefined : matchPreset(t);
  const mins = touchMinutes(t);
  const belowMin = !isFirst && mins < MIN_FOLLOWUP_MINUTES;

  const insert = (s: string) => set({ message: t.message ? `${t.message}${/\s$/.test(t.message) ? '' : ' '}${s}` : s });

  const addPhoto = async () => {
    try {
      const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (perm.status !== 'granted') { showToast('Allow photo access to attach a picture', 'error'); return; }
      const res = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ImagePicker.MediaTypeOptions.Images, quality: 0.8 });
      if (res.canceled || !res.assets?.[0]) return;
      const asset = res.assets[0];
      setUploading(true);
      const form = new FormData();
      const name = asset.fileName || asset.uri.split('/').pop() || 'photo.jpg';
      if (Platform.OS === 'web') {
        const blob = await (await fetch(asset.uri)).blob();
        form.append('file', blob, name);
      } else {
        form.append('file', { uri: asset.uri, name, type: asset.mimeType || 'image/jpeg' } as any);
      }
      const up = await api.post(`/images/upload?entity_type=campaign&entity_id=${campaignId}`, form, { headers: { 'Content-Type': 'multipart/form-data' } });
      if (!up.data?.original_url) throw new Error('no url');
      set({ media_urls: [...t.media_urls, up.data.original_url] });
    } catch {
      showToast('Photo upload failed. Try again.', 'error');
    } finally { setUploading(false); }
  };

  const done = () => {
    if (t.actionType === 'message' && !t.message.trim()) { showToast('Write the text first', 'error'); return; }
    if (t.actionType === 'send_card' && !t.cardType) { showToast('Pick a card', 'error'); return; }
    if (belowMin) { showToast(`Follow-ups need at least ${MIN_FOLLOWUP_MINUTES} min`, 'error'); return; }
    onDone(t);
  };

  const Stepper = ({ k, label, max }: { k: keyof Touch; label: string; max: number }) => (
    <View style={{ flex: 1, alignItems: 'center' }}>
      <Text style={{ fontSize: 11, color: colors.textSecondary, marginBottom: 4, fontWeight: '700' }}>{label}</Text>
      <View style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, borderRadius: 10, borderWidth: 1, borderColor: colors.border }}>
        <TouchableOpacity style={{ paddingHorizontal: 9, paddingVertical: 8 }} onPress={() => set({ [k]: Math.max(0, ((t as any)[k] || 0) - 1) } as any)} {...tid(`touch-${k}-minus`)}>
          <Ionicons name="remove" size={16} color={colors.text} />
        </TouchableOpacity>
        <Text style={{ fontSize: 14, color: colors.text, fontWeight: '800', minWidth: 22, textAlign: 'center' }}>{(t as any)[k] || 0}</Text>
        <TouchableOpacity style={{ paddingHorizontal: 9, paddingVertical: 8 }} onPress={() => set({ [k]: Math.min(max, ((t as any)[k] || 0) + 1) } as any)} {...tid(`touch-${k}-plus`)}>
          <Ionicons name="add" size={16} color={colors.text} />
        </TouchableOpacity>
      </View>
    </View>
  );

  return (
    <SheetShell
      title={`Touch ${index + 1}`}
      subtitle={whenSentence(t, triggerLabel)}
      onClose={onClose}
      testId="touch-editor"
      colors={colors}
      footer={
        <>
          <GoldButton label="Done" onPress={done} testId="touch-done" />
          {canRemove ? (
            <TouchableOpacity onPress={onRemove} style={{ alignItems: 'center', paddingVertical: 8 }} {...tid('touch-remove')}>
              <Text style={{ fontSize: 13, color: RED, fontWeight: '700' }}>Remove this touch</Text>
            </TouchableOpacity>
          ) : null}
        </>
      }
    >
      <View style={{ gap: 8 }}>
        <Eyebrow colors={colors}>WHEN</Eyebrow>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
          {PRESETS.filter(p => !p.firstOnly || isFirst).map(p => (
            <Chip key={p.label} label={p.label} active={preset?.label === p.label} colors={colors} testId={`touch-preset-${p.label.replace(/\s+/g, '-')}`}
              onPress={() => { setCustom(false); set({ delayMonths: p.mo, delayDays: p.d, delayHours: p.h, delayMinutes: p.m }); }} />
          ))}
          <Chip label="Custom" icon="options-outline" active={custom} colors={colors} testId="touch-preset-custom" onPress={() => setCustom(true)} />
        </View>
        {custom ? (
          <View style={{ flexDirection: 'row', gap: 8, marginTop: 4 }}>
            <Stepper k="delayMonths" label="Months" max={24} />
            <Stepper k="delayDays" label="Days" max={365} />
            <Stepper k="delayHours" label="Hours" max={23} />
            <Stepper k="delayMinutes" label="Min" max={59} />
          </View>
        ) : null}
        <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 17 }} {...tid('touch-when-note')}>
          {mins === 0 ? `Goes out the moment someone is tagged ${triggerLabel}.` : `Goes out ${humanDelay(t)} after they're tagged ${triggerLabel}. Never overnight; anything due after 9 PM waits until 9 AM.`}
        </Text>
        {belowMin ? (
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: AMBER + '22', borderRadius: 10, padding: 10 }} {...tid('touch-min-warning')}>
            <Ionicons name="warning-outline" size={16} color={AMBER} />
            <Text style={{ flex: 1, fontSize: 12, color: AMBER, fontWeight: '600' }}>Follow-up touches need at least 15 minutes so the scheduler can catch them.</Text>
          </View>
        ) : null}
      </View>

      <View style={{ gap: 10 }}>
        <Eyebrow colors={colors}>WHAT TO SEND</Eyebrow>
        <Segmented colors={colors} testId="touch-kind" value={t.actionType} onChange={v => set({ actionType: v as Touch['actionType'] })}
          options={[{ value: 'message', label: 'Text', icon: 'chatbubble-ellipses' }, { value: 'send_card', label: 'Card', icon: 'gift' }]} />

        {t.actionType === 'message' ? (
          <View style={{ gap: 10 }}>
            <View style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: GOLD + '55', padding: 12 }}>
              <TextInput
                value={t.message}
                onChangeText={m => set({ message: m })}
                placeholder={`Hey {first_name}! Hope everything is going great with your new {vehicle}…`}
                placeholderTextColor={colors.textTertiary}
                multiline
                style={{ minHeight: 110, fontSize: 15, lineHeight: 21, color: colors.text, textAlignVertical: 'top' }}
                {...tid('touch-message-input')}
              />
              <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 6 }}>
                <Text style={{ fontSize: 11, color: colors.textSecondary }}>{aiPersonalizes ? 'Jessi rewrites this in your voice for each person' : 'Sent exactly as written'}</Text>
                <Text style={{ fontSize: 11, color: t.message.length > 320 ? RED : colors.textSecondary }}>{t.message.length}/320</Text>
              </View>
            </View>
            <ScrollView horizontal showsHorizontalScrollIndicator={false}>
              <View style={{ flexDirection: 'row', gap: 6 }}>
                {TOKENS.map(tk => <Chip key={tk.key} label={tk.label} icon="at" colors={colors} testId={`touch-token-${tk.key.replace(/[{}]/g, '')}`} onPress={() => insert(tk.key)} />)}
              </View>
            </ScrollView>
            {quickLinks.length ? (
              <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                <View style={{ flexDirection: 'row', gap: 6 }}>
                  {quickLinks.map(l => <Chip key={l.label} label={l.label} icon={l.icon} color={l.color} colors={colors} testId={`touch-link-${l.label.replace(/\s+/g, '-')}`} onPress={() => insert(l.url)} />)}
                </View>
              </ScrollView>
            ) : null}

            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
              {t.media_urls.map((u, i) => (
                <View key={u + i} style={{ width: 64, height: 64, borderRadius: 10, overflow: 'hidden', backgroundColor: colors.card }}>
                  <Image source={{ uri: u }} style={{ width: 64, height: 64 }} />
                  <TouchableOpacity onPress={() => set({ media_urls: t.media_urls.filter((_, j) => j !== i) })} style={{ position: 'absolute', top: 2, right: 2 }} {...tid(`touch-photo-remove-${i}`)}>
                    <Ionicons name="close-circle" size={20} color="#fff" />
                  </TouchableOpacity>
                </View>
              ))}
              {t.media_urls.length < 3 ? (
                <TouchableOpacity onPress={addPhoto} disabled={uploading} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, height: 36, borderRadius: 18, borderWidth: 1, borderColor: colors.border, borderStyle: 'dashed' }} {...tid('touch-add-photo')}>
                  {uploading ? <ActivityIndicator size="small" color={GOLD} /> : <Ionicons name="image-outline" size={16} color={colors.textSecondary} />}
                  <Text style={{ fontSize: 13, color: colors.textSecondary, fontWeight: '600' }}>{t.media_urls.length ? 'Add another photo' : 'Attach a photo'}</Text>
                </TouchableOpacity>
              ) : null}
            </View>
          </View>
        ) : (
          <View style={{ gap: 10 }}>
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
              {CARD_TYPES.map(c => {
                const on = t.cardType === c.key;
                return (
                  <TouchableOpacity key={c.key} onPress={() => set({ cardType: c.key })} style={{ width: '31%', flexGrow: 1, alignItems: 'center', gap: 6, paddingVertical: 12, borderRadius: 14, backgroundColor: colors.card, borderWidth: 1.5, borderColor: on ? c.color : colors.border }} {...tid(`touch-card-${c.key}`)}>
                    <View style={{ width: 38, height: 38, borderRadius: 19, backgroundColor: c.color + '22', alignItems: 'center', justifyContent: 'center' }}>
                      <Ionicons name={c.icon as any} size={18} color={c.color} />
                    </View>
                    <Text style={{ fontSize: 12, fontWeight: '700', color: on ? c.color : colors.text }}>{c.label}</Text>
                  </TouchableOpacity>
                );
              })}
            </View>
            <TextInput
              value={t.message}
              onChangeText={m => set({ message: m })}
              placeholder="Optional note texted with the card"
              placeholderTextColor={colors.textTertiary}
              style={{ backgroundColor: colors.card, borderRadius: 12, padding: 12, fontSize: 14, color: colors.text, borderWidth: 1, borderColor: colors.border }}
              {...tid('touch-card-note-input')}
            />
            <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 17 }}>
              A digital {CARD_TYPES.find(c => c.key === t.cardType)?.label.toLowerCase() || ''} card with your photo is created for them and texted as a link.
            </Text>
          </View>
        )}
      </View>
    </SheetShell>
  );
}
