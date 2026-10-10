/**
 * NowStrip — the four questions above the familiar History feed, in plain words:
 * Recommended (what to do next), Active (what the customer is trying to do), Current (what we believe today), and a calm "needs a look" count.
 * Every line opens its source. Hidden entirely when relationship intelligence is off for this tenant.
 */
import React, { useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

const GOLD = '#C9A962';
const GREEN = '#34C759';

function Row({ icon, label, children, colors, testid }: any) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 10, paddingVertical: 6 }} testID={testid} dataSet={{ testid } as any}>
      <Ionicons name={icon} size={14} color={GOLD} style={{ marginTop: 3, width: 16 }} />
      <Text style={{ width: 100, fontSize: 10.5, fontWeight: '800', color: colors.textSecondary, textTransform: 'uppercase', letterSpacing: 0.4, marginTop: 2 }} numberOfLines={1}>{label}</Text>
      <View style={{ flex: 1 }}>{children}</View>
    </View>
  );
}

export default function NowStrip({ timeline, colors, onOpenFact, onUseOpening }: { timeline: any; colors: any; onOpenFact: (factId: string) => void; onUseOpening?: (text: string) => void }) {
  const [showAllNeeds, setShowAllNeeds] = useState(false);
  if (!timeline?.enabled) return null;
  const rec = timeline.recommended;
  const active: any[] = timeline.active || [];
  const sup = timeline.suppression;
  const cur = timeline.current || {};
  const needs: any[] = timeline.needs_look || [];
  const currentBits: { label: string; fact_id: string; confirmed: boolean }[] = [
    ...(cur.drives || []).slice(0, 2).map((x: any) => ({ label: `Drives ${x.label}`, fact_id: x.fact_id, confirmed: x.confirmed })),
    ...(cur.household || []).slice(0, 2).map((x: any) => ({ label: x.label, fact_id: x.fact_id, confirmed: x.confirmed })),
    ...(cur.work || []).slice(0, 1).map((x: any) => ({ label: x.label, fact_id: x.fact_id, confirmed: x.confirmed })),
  ];
  if (!rec && !active.length && !currentBits.length && !sup) return null;

  return (
    <View style={{ marginHorizontal: 16, marginTop: 12, borderRadius: 16, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.card, paddingHorizontal: 14, paddingVertical: 8 }} testID="now-strip" dataSet={{ testid: 'now-strip' } as any}>
      {rec && (
        <Row icon="compass" label="Recommended" colors={colors} testid="now-recommended">
          <Text style={{ fontSize: 14.5, fontWeight: '700', color: colors.text, lineHeight: 20 }} testID="now-recommended-topic" dataSet={{ testid: 'now-recommended-topic' } as any}>{rec.topic}</Text>
          <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 18, marginTop: 2 }}>{rec.why}</Text>
          {!!rec.opening && (
            <TouchableOpacity onPress={() => onUseOpening?.(rec.opening)} activeOpacity={0.75} style={{ marginTop: 6, padding: 10, borderRadius: 10, backgroundColor: `${GOLD}12`, borderLeftWidth: 3, borderLeftColor: GOLD }} testID="now-recommended-opening" dataSet={{ testid: 'now-recommended-opening' } as any}>
              <Text style={{ fontSize: 13.5, color: colors.text, lineHeight: 19, fontStyle: 'italic' }}>“{rec.opening}”</Text>
              {!!onUseOpening && <Text style={{ fontSize: 11, color: GOLD, fontWeight: '700', marginTop: 4 }}>Tap to use as your text</Text>}
            </TouchableOpacity>
          )}
          {!!rec.evidence?.length && (
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
              {rec.evidence.slice(0, 3).map((e: any, i: number) => (
                <TouchableOpacity key={e.fact_id + i} onPress={() => onOpenFact(e.fact_id)} style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 4, borderRadius: 999, backgroundColor: colors.surface }} testID={`now-evidence-${i}`} dataSet={{ testid: `now-evidence-${i}` } as any}>
                  <Ionicons name="help-circle-outline" size={12} color={GOLD} />
                  <Text style={{ fontSize: 11.5, color: colors.textSecondary, fontWeight: '600' }}>Why? {e.source}</Text>
                </TouchableOpacity>
              ))}
            </View>
          )}
        </Row>
      )}
      {(active.length > 0 || sup) && (
        <Row icon="flash" label="Active" colors={colors} testid="now-active">
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6 }}>
            {sup && (
              <TouchableOpacity onPress={() => onOpenFact(sup.fact_id)} style={{ paddingHorizontal: 10, paddingVertical: 6, borderRadius: 10, backgroundColor: '#FF950018', borderWidth: 1, borderColor: '#FF950055' }} testID="now-suppression" dataSet={{ testid: 'now-suppression' } as any}>
                <Text style={{ fontSize: 12.5, fontWeight: '700', color: '#FF9500' }}>{sup.label}</Text>
                <Text style={{ fontSize: 11, color: colors.textSecondary }}>{sup.when}, do not pitch</Text>
              </TouchableOpacity>
            )}
            {active.slice(0, 4).map((a: any, i: number) => {
              const lead = a.fact_id === timeline.driving_fact_id;
              return (
                <TouchableOpacity key={a.fact_id} onPress={() => onOpenFact(a.fact_id)} style={{ paddingHorizontal: 10, paddingVertical: 6, borderRadius: 10, backgroundColor: lead ? `${GREEN}18` : colors.surface, borderWidth: 1, borderColor: lead ? `${GREEN}66` : colors.border, maxWidth: 260 }} testID={`now-active-${i}`} dataSet={{ testid: `now-active-${i}` } as any}>
                  <Text style={{ fontSize: 12.5, fontWeight: '700', color: lead ? GREEN : colors.text }} numberOfLines={1}>{a.label}</Text>
                  <Text style={{ fontSize: 11, color: colors.textSecondary }} numberOfLines={1}>{a.detail}</Text>
                </TouchableOpacity>
              );
            })}
          </ScrollView>
        </Row>
      )}
      {currentBits.length > 0 && (
        <Row icon="checkmark-done" label="Current" colors={colors} testid="now-current">
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
            {currentBits.map((b, i) => (
              <TouchableOpacity key={b.fact_id} onPress={() => onOpenFact(b.fact_id)} style={{ flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 9, paddingVertical: 5, borderRadius: 999, backgroundColor: colors.surface }} testID={`now-current-${i}`} dataSet={{ testid: `now-current-${i}` } as any}>
                <View style={{ width: 7, height: 7, borderRadius: 4, backgroundColor: b.confirmed ? GREEN : colors.textTertiary }} />
                <Text style={{ fontSize: 12.5, color: colors.text, fontWeight: '600' }} numberOfLines={1}>{b.label}</Text>
                {!b.confirmed && <Text style={{ fontSize: 10.5, color: colors.textTertiary }}>unconfirmed</Text>}
              </TouchableOpacity>
            ))}
          </View>
        </Row>
      )}
      {needs.length > 0 && (
        <View style={{ borderTopWidth: 1, borderTopColor: colors.border, marginTop: 4, paddingTop: 8 }}>
          <TouchableOpacity onPress={() => setShowAllNeeds(v => !v)} style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }} testID="now-needs-toggle" dataSet={{ testid: 'now-needs-toggle' } as any}>
            <Ionicons name="eye-outline" size={13} color={colors.textSecondary} />
            <Text style={{ flex: 1, fontSize: 12, color: colors.textSecondary, fontWeight: '600' }}>{needs.length === 1 ? 'One thing' : `${needs.length} things`} nobody has confirmed yet</Text>
            <Ionicons name={showAllNeeds ? 'chevron-up' : 'chevron-down'} size={13} color={colors.textTertiary} />
          </TouchableOpacity>
          {showAllNeeds && needs.slice(0, 12).map((n: any, i: number) => (
            <TouchableOpacity key={n.fact_id || i} onPress={() => n.fact_id && onOpenFact(n.fact_id)} style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 6, paddingLeft: 19 }} testID={`now-needs-${i}`} dataSet={{ testid: `now-needs-${i}` } as any}>
              <Text style={{ flex: 1, fontSize: 12.5, color: colors.text }} numberOfLines={1}>{n.statement}</Text>
              <Text style={{ fontSize: 10.5, color: colors.textTertiary }}>{n.reason === 'unconfirmed' ? 'unconfirmed' : n.reason === 'stale' ? 'may be outdated' : n.reason === 'disputed' ? 'marked not right' : 'AI guess'}</Text>
            </TouchableOpacity>
          ))}
        </View>
      )}
    </View>
  );
}
