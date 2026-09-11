import React, { useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, GREEN, RED, tid, type EvalResult } from './shared';

type Props = { results: EvalResult[]; colors: any; canManage: boolean; onOverride?: (criterionId: string, passed: boolean | null) => void; busyId?: string | null };

const iconFor = (p: boolean | null) => (p === true ? { name: 'checkmark-circle', color: GREEN } : p === false ? { name: 'close-circle', color: RED } : { name: 'remove-circle', color: '#8E8E93' });

// Pass / fail / N/A checklist with evidence quotes. Managers tap a row to correct the AI.
export const CriteriaChecklist = ({ results, colors, canManage, onOverride, busyId }: Props) => {
  const [open, setOpen] = useState<string | null>(null);
  return (
    <View style={{ gap: 6 }} {...tid('eval-criteria')}>
      {results.map(r => {
        const ic = iconFor(r.passed);
        const expanded = open === r.criterion_id;
        return (
          <TouchableOpacity key={r.criterion_id} activeOpacity={0.8} onPress={() => setOpen(expanded ? null : r.criterion_id)}
            style={{ backgroundColor: colors.surface, borderRadius: 12, padding: 10, borderLeftWidth: 3, borderLeftColor: r.critical && r.passed === false ? RED : 'transparent' }}
            {...tid(`eval-criterion-${r.criterion_id}`)}>
            <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 10 }}>
              <Ionicons name={ic.name as any} size={22} color={ic.color} style={{ marginTop: -1 }} />
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 14, fontWeight: '600', color: colors.text, lineHeight: 19 }}>{r.text}</Text>
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 4 }}>
                  {r.critical && <Text style={{ fontSize: 10, fontWeight: '800', color: RED, letterSpacing: 0.5 }}>CRITICAL</Text>}
                  {r.passed === null && <Text style={{ fontSize: 10, fontWeight: '700', color: colors.textSecondary }}>N/A on this call</Text>}
                  {r.override && <Text style={{ fontSize: 10, fontWeight: '700', color: GOLD }}>Corrected by {r.override.by_name}</Text>}
                  {!r.override && r.confidence < 0.7 && r.passed !== null && <Text style={{ fontSize: 10, fontWeight: '700', color: colors.textSecondary }}>AI unsure</Text>}
                </View>
                {(expanded || (r.passed === false && r.critical)) && r.evidence ? (
                  <Text style={{ fontSize: 12, color: colors.textSecondary, fontStyle: 'italic', marginTop: 6, lineHeight: 17 }}>"{r.evidence}"</Text>
                ) : null}
                {expanded && !r.evidence && <Text style={{ fontSize: 12, color: colors.textSecondary, fontStyle: 'italic', marginTop: 6 }}>No supporting quote found in the transcript.</Text>}
              </View>
            </View>
            {expanded && canManage && onOverride && (
              <View style={{ flexDirection: 'row', gap: 6, marginTop: 10, marginLeft: 32 }}>
                {([[true, 'Passed', GREEN], [false, 'Missed', RED], [null, 'N/A', '#8E8E93']] as const).map(([v, l, c]) => (
                  <TouchableOpacity key={l} disabled={busyId === r.criterion_id} onPress={() => onOverride(r.criterion_id, v)}
                    style={{ paddingHorizontal: 12, paddingVertical: 6, borderRadius: 10, backgroundColor: r.passed === v ? c : colors.card, borderWidth: 1, borderColor: r.passed === v ? c : colors.border }}
                    {...tid(`eval-override-${r.criterion_id}-${l.toLowerCase().replace('/', '')}`)}>
                    <Text style={{ fontSize: 12, fontWeight: '800', color: r.passed === v ? '#fff' : colors.text }}>{l}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            )}
          </TouchableOpacity>
        );
      })}
    </View>
  );
};
