import React, { useState } from 'react';
import { View, Text, TouchableOpacity, Switch, useWindowDimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../../services/api';
import { useToast } from '../../common/Toast';
import { Sheet, GoldButton, Label } from '../../mystery-shops/shared';
import { Card, Progress } from '../CcShell';
import { GOLD, GREEN, AMBER, RED, READY_COLOR, detail, tid, type Executive } from '../shared';

const PART: Record<string, string> = { orchestrator: 'Convenes the room', always: 'Always in the room', on_topic: 'Joins when the topic is theirs' };
const ITEM_ICON: Record<string, { icon: any; color: string }> = { verified: { icon: 'checkmark-circle', color: GREEN }, stale: { icon: 'time', color: AMBER }, proposed: { icon: 'help-circle', color: AMBER }, disputed: { icon: 'alert-circle', color: RED }, missing: { icon: 'ellipse-outline', color: RED } };

export const Monogram = ({ e, size = 44 }: { e: { short: string; color: string }; size?: number }) => {
  const label = e.short.length > 3 && size < 40 ? e.short.slice(0, 3).toUpperCase() : e.short;
  return (
    <View style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: e.color + '26', borderWidth: 1.5, borderColor: e.color, alignItems: 'center', justifyContent: 'center' }}>
      <Text style={{ fontSize: label.length > 3 ? size * 0.21 : size * 0.3, fontWeight: '900', color: e.color, letterSpacing: 0.3 }} numberOfLines={1}>{label}</Text>
    </View>
  );
};

export const Bullets = ({ items, colors, testID }: { items: string[]; colors: any; testID?: string }) => (
  <View style={{ gap: 4 }} {...tid(testID || 'cc-bullets')}>
    {items.map((x, i) => <Text key={i} style={{ fontSize: 13, color: colors.text, lineHeight: 18 }}>· {x}</Text>)}
  </View>
);

const ExecTile = ({ e, colors, onOpen, onAsk, width }: { e: Executive; colors: any; onOpen: () => void; onAsk: () => void; width: any }) => (
  <Card colors={colors} onPress={onOpen} testID={`cc-exec-${e.key}`} style={{ width, opacity: e.enabled ? 1 : 0.55 }}>
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
      <Monogram e={e} />
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }} numberOfLines={1}>{e.title}</Text>
        <Text style={{ fontSize: 12, color: colors.textSecondary }}>{PART[e.participation]}{e.enabled ? '' : ' · switched off'}</Text>
      </View>
    </View>
    <Text style={{ fontSize: 13, color: colors.text, lineHeight: 18 }} numberOfLines={3}>{e.mission}</Text>
    <View style={{ gap: 4 }}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
        <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8 }}>KNOWLEDGE READINESS</Text>
        <Text style={{ fontSize: 11.5, fontWeight: '800', color: READY_COLOR[e.readiness.level] }} {...tid(`cc-exec-${e.key}-readiness`)}>{e.readiness.score}% · {e.readiness.level}</Text>
      </View>
      <Progress pct={e.readiness.score} color={READY_COLOR[e.readiness.level]} colors={colors} testID={`cc-exec-${e.key}-progress`} />
    </View>
    {!e.is_orchestrator && (
      <TouchableOpacity onPress={onAsk} disabled={!e.enabled} style={{ alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, height: 32, borderRadius: 16, backgroundColor: e.enabled ? e.color + '22' : colors.border }} {...tid(`cc-exec-${e.key}-ask`)}>
        <Ionicons name="chatbubble-ellipses" size={14} color={e.enabled ? e.color : colors.textSecondary} /><Text style={{ fontSize: 12.5, fontWeight: '800', color: e.enabled ? e.color : colors.textSecondary }}>Ask the {e.short}</Text>
      </TouchableOpacity>
    )}
  </Card>
);

// THE ROSTER: seven executives, each a document the founder can switch on or off; readiness tells how much the company has actually told them.
export const Roster = ({ execs, colors, onAsk, onTalk, onChanged }: { execs: Executive[]; colors: any; onAsk: (key: string) => void; onTalk: (key: string) => void; onChanged: () => void }) => {
  const { width } = useWindowDimensions();
  const [open, setOpen] = useState<Executive | null>(null);
  const cols = width >= 1024 ? 3 : width >= 700 ? 2 : 1;
  const inner = (width >= 1024 ? 1100 : width) - 32;
  const tileW = cols === 1 ? '100%' : (inner - 12 * (cols - 1)) / cols;
  return (
    <View style={{ gap: 12 }} {...tid('cc-roster')}>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 12 }}>
        {execs.map(e => <ExecTile key={e.key} e={e} colors={colors} width={tileW} onOpen={() => setOpen(e)} onAsk={() => onAsk(e.key)} />)}
      </View>
      <ExecutiveSheet e={open} colors={colors} onClose={() => setOpen(null)} onAsk={onAsk} onTalk={onTalk} onChanged={onChanged} />
    </View>
  );
};

const Section = ({ t, children, colors }: { t: string; children: React.ReactNode; colors: any }) => <View style={{ gap: 6 }}><Label t={t} colors={colors} />{children}</View>;

export const ExecutiveSheet = ({ e, colors, onClose, onAsk, onTalk, onChanged }: { e: Executive | null; colors: any; onClose: () => void; onAsk: (k: string) => void; onTalk: (k: string) => void; onChanged: () => void }) => {
  const { showToast } = useToast();
  const [busy, setBusy] = useState(false);
  if (!e) return null;
  const fixed = e.key === 'chief_of_staff' || e.key === 'strategic_advisor';
  const toggle = async (v: boolean) => {
    setBusy(true);
    try { await api.patch(`/command-center/team/roster/${e.key}`, { enabled: v }); showToast(v ? `${e.title} is back on the team` : `${e.title} switched off`); onChanged(); onClose(); }
    catch (err: any) { showToast(detail(err, 'Could not update'), 'error'); } finally { setBusy(false); }
  };
  const footer = e.is_orchestrator ? undefined : (
    <View style={{ flexDirection: 'row', gap: 8 }}>
      <View style={{ flex: 1 }}><GoldButton label={`Ask the ${e.short}`} icon="chatbubble-ellipses" color={e.color} disabled={!e.enabled} onPress={() => { onClose(); onAsk(e.key); }} testID="cc-exec-sheet-ask" /></View>
      <View style={{ flex: 1 }}><GoldButton label="Talk live" icon="mic" outline color={e.color} disabled={!e.enabled} onPress={() => { onClose(); onTalk(e.key); }} testID="cc-exec-sheet-talk" /></View>
    </View>
  );
  return (
    <Sheet visible={!!e} onClose={onClose} title={e.title} colors={colors} testID="cc-exec-sheet" footer={footer}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
        <Monogram e={e} size={52} />
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 13, color: colors.textSecondary }}>{PART[e.participation]} · authority level {e.authority.level} ({e.authority.level === 1 ? 'advises only' : 'prepares, you approve'})</Text>
          <Text style={{ fontSize: 13, color: colors.text, lineHeight: 18, marginTop: 4 }}>{e.mission}</Text>
        </View>
      </View>
      {!fixed && (
        <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 12, borderRadius: 12, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border }}>
          <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>{e.enabled ? 'On the team' : 'Switched off'}</Text>
          <Switch value={e.enabled} onValueChange={toggle} disabled={busy} trackColor={{ true: GOLD }} {...tid('cc-exec-sheet-enabled')} />
        </View>
      )}
      <Section t={`KNOWLEDGE READINESS · ${e.readiness.score}% ${e.readiness.level.toUpperCase()}`} colors={colors}>
        <View style={{ gap: 8 }} {...tid('cc-exec-sheet-readiness')}>
          {e.readiness.items.map(it => {
            const ic = ITEM_ICON[it.status] || ITEM_ICON.missing;
            const next = e.readiness.missing.find(m => m.key === it.key)?.next_step;
            return (
              <View key={it.key} style={{ flexDirection: 'row', gap: 8, alignItems: 'flex-start' }} {...tid(`cc-readiness-${it.key}`)}>
                <Ionicons name={ic.icon} size={16} color={ic.color} style={{ marginTop: 1 }} />
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 13.5, fontWeight: '700', color: colors.text }}>{it.label}</Text>
                  <Text style={{ fontSize: 12, color: colors.textSecondary }}>{it.detail}{next ? ` · ${next}` : ''}</Text>
                </View>
              </View>
            );
          })}
        </View>
        <Text style={{ fontSize: 11, color: colors.textSecondary, lineHeight: 15 }}>{e.readiness.rule}</Text>
      </Section>
      <Section t="RESPONSIBILITIES" colors={colors}><Bullets items={e.responsibilities} colors={colors} /></Section>
      <Section t="DELIVERS" colors={colors}><Bullets items={e.deliverables} colors={colors} /></Section>
      <Section t="NEEDS YOUR APPROVAL FOR" colors={colors}><Bullets items={e.authority.needs_approval} colors={colors} /></Section>
      <Section t="NEVER" colors={colors}><Bullets items={[...e.prohibited, ...e.extra_boundaries]} colors={colors} /></Section>
      <Section t="EXPERTISE" colors={colors}><Text style={{ fontSize: 13, color: colors.text, lineHeight: 18 }}>{e.expertise.join(' · ')}</Text></Section>
    </Sheet>
  );
};
