import React from 'react';
import { View, Text, TouchableOpacity, Switch } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useThemeStore } from '../../store/themeStore';
import { Card, Pill, GOLD, GREEN, RED, AMBER, tid } from '../voice-pilot/shared';
import { PhotoSettings, Scope, SCOPE_LABEL, Segmented } from './shared';

type Props = { s: PhotoSettings; busy: boolean; onScope: (cap: 'replies' | 'intelligence', v: Scope) => void; onPause: (v: boolean) => void;
  onAddMine: () => void; onRemove: (id: string) => void };

const CAPS: { cap: 'replies' | 'intelligence'; title: string; body: string }[] = [
  { cap: 'replies', title: 'Jessi Photo Replies', body: 'Jessi uses what a customer photo shows when she replies and when a rep taps AI Suggest.' },
  { cap: 'intelligence', title: 'Automatic Photo Intelligence', body: 'Details from a photo (a vehicle, a product, a project) are proposed on the contact. Nothing is saved until the rep taps Add it.' },
];

export const ControlsCard = ({ s, busy, onScope, onPause, onAddMine, onRemove }: Props) => {
  const { colors } = useThemeStore();
  const opts = s.scopes.map(k => ({ key: k, label: SCOPE_LABEL[k] }));
  return (
    <Card title="SETTINGS" testID="photo-intel-controls">
      {CAPS.map(c => (
        <View key={c.cap} style={{ marginBottom: 16 }} {...tid(`photo-intel-${c.cap}`)}>
          <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>{c.title}</Text>
          <Text style={{ fontSize: 12.5, color: colors.textSecondary, marginTop: 3, marginBottom: 8, lineHeight: 17 }}>{c.body}</Text>
          <Segmented value={s[c.cap]} options={opts} disabled={busy} onChange={v => onScope(c.cap, v as Scope)} testID={`photo-intel-${c.cap}-scope`} />
        </View>
      ))}
      <View style={{ borderTopWidth: 1, borderTopColor: colors.border, paddingTop: 12, marginBottom: 12 }}>
        <Text style={{ fontSize: 12, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6, marginBottom: 6 }}>TEST ORGANIZATIONS</Text>
        {s.test_orgs.length === 0 && <Text style={{ fontSize: 13, color: colors.textSecondary }} {...tid('photo-intel-no-test-orgs')}>None yet.</Text>}
        {s.test_orgs.map(o => (
          <View key={o.id} style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: 6, gap: 8 }} {...tid(`photo-intel-test-org-${o.id}`)}>
            <Ionicons name="business" size={15} color={GOLD} />
            <Text style={{ flex: 1, fontSize: 13.5, color: colors.text, fontWeight: '600' }}>{o.name}</Text>
            <TouchableOpacity disabled={busy} onPress={() => onRemove(o.id)} {...tid(`photo-intel-remove-org-${o.id}`)}>
              <Text style={{ fontSize: 12.5, color: RED, fontWeight: '700' }}>Remove</Text>
            </TouchableOpacity>
          </View>
        ))}
        {s.my_org && !s.my_org.is_test && (
          <TouchableOpacity disabled={busy} onPress={onAddMine} style={{ marginTop: 8, height: 40, borderRadius: 11, borderWidth: 1, borderColor: GOLD, alignItems: 'center', justifyContent: 'center' }} {...tid('photo-intel-add-my-org')}>
            <Text style={{ color: GOLD, fontWeight: '800', fontSize: 13.5 }}>Add my organization ({s.my_org.name})</Text>
          </TouchableOpacity>
        )}
        {s.my_org && (
          <View style={{ flexDirection: 'row', gap: 6, marginTop: 10, flexWrap: 'wrap' }} {...tid('photo-intel-my-org-status')}>
            <Pill text={`MY ORG REPLIES ${s.my_org.replies_on ? 'ON' : 'OFF'}`} tone={s.my_org.replies_on ? GREEN : '#8E8E93'} testID="photo-intel-my-replies" />
            <Pill text={`MY ORG INTELLIGENCE ${s.my_org.intelligence_on ? 'ON' : 'OFF'}`} tone={s.my_org.intelligence_on ? GREEN : '#8E8E93'} testID="photo-intel-my-intel" />
          </View>
        )}
      </View>
      <View style={{ borderRadius: 12, padding: 12, backgroundColor: s.paused ? `${RED}18` : colors.bg, borderWidth: 1, borderColor: s.paused ? RED : colors.border }} {...tid('photo-intel-pause-card')}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
          <Ionicons name="pause-circle" size={20} color={s.paused ? RED : AMBER} />
          <Text style={{ flex: 1, fontSize: 14.5, fontWeight: '800', color: colors.text }}>Emergency Pause All</Text>
          <Switch value={s.paused} disabled={busy} onValueChange={onPause} trackColor={{ true: RED, false: colors.border }} {...tid('photo-intel-pause-switch')} />
        </View>
        <Text style={{ fontSize: 12.5, color: colors.textSecondary, marginTop: 6, lineHeight: 17 }} {...tid('photo-intel-pause-note')}>
          {s.paused ? 'PAUSED: no new photo is analyzed anywhere (replies, intelligence, Files). Texted photos are still received and saved in Files.'
            : 'Stops every new photo analysis at once (Jessi replies, intelligence and Files). Photos are still received and saved.'}
        </Text>
      </View>
      {!!s.updated_by && <Text style={{ fontSize: 11.5, color: colors.textSecondary, marginTop: 10 }} {...tid('photo-intel-updated')}>Last changed by {s.updated_by}{s.updated_at ? ` · ${new Date(s.updated_at).toLocaleString()}` : ''}</Text>}
    </Card>
  );
};
