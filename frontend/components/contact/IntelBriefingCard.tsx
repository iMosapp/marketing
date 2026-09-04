/**
 * IntelBriefingCard — auto-updating Relationship Intel briefing.
 * Quick Take + key bullets at a glance; expands to the full briefing.
 */
import React, { useMemo, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { IntelRenderer } from '../../utils/contactHelpers';
import api from '../../services/api';

const GOLD = '#C9A962';
const AMBER = '#FF9F0A';
const GREEN = '#34C759';
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });
const LEARNED_WINDOW_MS = 7 * 24 * 3600 * 1000;

function LearnedChip({ learned, colors }: any) {
  const [open, setOpen] = useState(false);
  if (!learned?.at || Date.now() - new Date(learned.at).getTime() > LEARNED_WINDOW_MS) return null;
  const labels: string[] = learned.labels || learned.fields || [];
  if (!labels.length) return null;
  const values: Record<string, any> = learned.values || {};
  const fields: string[] = learned.fields || [];
  return (
    <View style={{ marginBottom: 10 }}>
      <TouchableOpacity onPress={() => setOpen(v => !v)} activeOpacity={0.7}
        style={{ flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start', paddingHorizontal: 10, paddingVertical: 5, borderRadius: 12, backgroundColor: '#AF52DE22', borderWidth: 1, borderColor: '#AF52DE55' }}
        {...tid('intel-learned-chip')}>
        <Ionicons name="sparkles" size={12} color="#C77DFF" />
        <Text style={{ fontSize: 12, fontWeight: '700', color: '#C77DFF' }} numberOfLines={1}>
          Updated from {learned.source || 'texts'}: {labels.slice(0, 3).join(', ')}{labels.length > 3 ? ` +${labels.length - 3}` : ''} · {timeAgo(learned.at)}
        </Text>
        <Ionicons name={open ? 'chevron-up' : 'chevron-down'} size={12} color="#C77DFF" />
      </TouchableOpacity>
      {open && (
        <View style={{ marginTop: 6, marginBottom: 8, marginLeft: 4, gap: 3 }} {...tid('intel-learned-details')}>
          {fields.map((f, i) => (
            <Text key={f} style={{ fontSize: 13, color: colors.textSecondary }}>
              <Text style={{ fontWeight: '700', color: colors.text }}>{labels[i] || f}: </Text>{String(values[f] ?? '')}
            </Text>
          ))}
        </View>
      )}
    </View>
  );
}

function SuggestionRow({ s, colors, busy, onDecide }: any) {
  return (
    <View style={{ borderRadius: 12, borderWidth: 1, borderColor: `${AMBER}66`, backgroundColor: `${AMBER}12`, padding: 10, marginBottom: 8 }} {...tid(`intel-suggestion-${s.id}`)}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
        <Ionicons name="help-circle" size={14} color={AMBER} />
        <Text style={{ fontSize: 12, fontWeight: '700', color: AMBER, letterSpacing: 0.8 }}>JESSI NOTICED A CHANGE · from {s.source || 'texts'}</Text>
      </View>
      <Text style={{ fontSize: 13, color: colors.text, marginTop: 5, lineHeight: 19 }}>
        <Text style={{ fontWeight: '700' }}>{s.label}: </Text>
        <Text style={{ color: colors.textSecondary, textDecorationLine: 'line-through' }}>{String(s.old)}</Text>
        {'  →  '}
        <Text style={{ fontWeight: '700', color: GREEN }}>{String(s.new)}</Text>
      </Text>
      <View style={{ flexDirection: 'row', gap: 8, marginTop: 8 }}>
        <TouchableOpacity disabled={busy} onPress={() => onDecide(s, 'accept')} style={{ flex: 1, backgroundColor: GOLD, borderRadius: 9, paddingVertical: 8, alignItems: 'center', opacity: busy ? 0.6 : 1 }} {...tid(`intel-suggestion-accept-${s.id}`)}>
          <Text style={{ fontSize: 13, fontWeight: '800', color: '#000' }}>Update to {String(s.new).length > 18 ? 'new value' : String(s.new)}</Text>
        </TouchableOpacity>
        <TouchableOpacity disabled={busy} onPress={() => onDecide(s, 'reject')} style={{ flex: 1, borderRadius: 9, paddingVertical: 8, alignItems: 'center', borderWidth: 1, borderColor: colors.border, opacity: busy ? 0.6 : 1 }} {...tid(`intel-suggestion-reject-${s.id}`)}>
          <Text style={{ fontSize: 13, fontWeight: '700', color: colors.text }}>Keep {String(s.old).length > 18 ? 'current' : String(s.old)}</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}
const SECTIONS = ['Quick Take', 'Key Facts', 'Communication Patterns', 'Personal Notes', 'Before Your Next Interaction'];

export function parseSections(text: string): Record<string, string[]> {
  const out: Record<string, string[]> = {};
  let current = '';
  text.split('\n').map(l => l.trim()).filter(Boolean).forEach(line => {
    const clean = line.replace(/\*\*/g, '');
    const header = SECTIONS.find(h => clean.toLowerCase().startsWith(h.toLowerCase()));
    if (header) {
      current = header;
      out[current] = out[current] || [];
    } else if (current) {
      out[current].push(clean.replace(/^[-•]\s*/, ''));
    }
  });
  return out;
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return d === 1 ? 'yesterday' : `${d}d ago`;
}

export default function IntelBriefingCard({ colors, intelData, refreshing, onRefresh, userId, contactId, onUpdate, onDetailsChanged }: any) {
  const [expanded, setExpanded] = useState(false);
  const [deciding, setDeciding] = useState(false);
  const summary: string = intelData?.summary || '';
  const suggestions: any[] = intelData?.suggestions || [];

  const decide = async (s: any, action: 'accept' | 'reject') => {
    if (!userId || !contactId || deciding) return;
    setDeciding(true);
    try {
      const r = await api.post(`/contact-intel/${userId}/${contactId}/suggestions/${s.id}`, { action });
      onUpdate?.({ suggestions: r.data.suggestions || [] });
      if (action === 'accept') onDetailsChanged?.();
    } catch {
      onUpdate?.({ suggestions: suggestions.filter(x => x.id !== s.id) });
    } finally {
      setDeciding(false);
    }
  };
  const sections = useMemo(() => parseSections(summary), [summary]);

  const quickTake = (sections['Quick Take'] || []).join(' ');
  const keyFacts = (sections['Key Facts'] || []).slice(0, 2);
  const nextUp = (sections['Before Your Next Interaction'] || [])[0];

  const card = {
    marginHorizontal: 16, marginBottom: 12, padding: 14, borderRadius: 16,
    backgroundColor: colors.card, borderWidth: 1, borderColor: `${GOLD}30`,
  };

  return (
    <View style={card} testID="intel-briefing-card" dataSet={{ testid: 'intel-briefing-card' }}>
      {/* Header */}
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: summary ? 10 : 0 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <View style={{ width: 26, height: 26, borderRadius: 8, backgroundColor: `${GOLD}20`, alignItems: 'center', justifyContent: 'center' }}>
            <Ionicons name="sparkles" size={14} color={GOLD} />
          </View>
          <Text style={{ fontSize: 12, fontWeight: '700', color: GOLD, letterSpacing: 0.8 }}>RELATIONSHIP INTEL</Text>
        </View>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 5 }} testID="intel-status" dataSet={{ testid: 'intel-status' }}>
          {refreshing ? (
            <>
              <ActivityIndicator size="small" color={GOLD} />
              <Text style={{ fontSize: 12, color: GOLD, fontWeight: '600' }}>Updating…</Text>
            </>
          ) : intelData?.generated_at ? (
            <>
              <View style={{ width: 7, height: 7, borderRadius: 4, backgroundColor: '#34C759' }} />
              <Text style={{ fontSize: 12, color: colors.textTertiary }}>Updated {timeAgo(intelData.generated_at)}</Text>
            </>
          ) : null}
        </View>
      </View>

      {/* What Jessi learned recently + changes waiting for your OK */}
      {(suggestions.length > 0 || intelData?.last_learned) && (
        <View style={{ marginBottom: summary ? 4 : 0 }}>
          {suggestions.map(s => <SuggestionRow key={s.id} s={s} colors={colors} busy={deciding} onDecide={decide} />)}
          <LearnedChip learned={intelData?.last_learned} colors={colors} />
        </View>
      )}

      {summary ? (
        <>
          {/* Quick Take */}
          {quickTake ? (
            <Text style={{ fontSize: 16, fontWeight: '600', color: colors.text, lineHeight: 22, marginBottom: keyFacts.length || nextUp ? 10 : 0 }} testID="intel-quick-take" dataSet={{ testid: 'intel-quick-take' }}>
              {quickTake}
            </Text>
          ) : null}

          {/* Key bullets */}
          {keyFacts.map((f, i) => (
            <View key={i} style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 8, marginBottom: 5 }}>
              <View style={{ width: 5, height: 5, borderRadius: 3, backgroundColor: GOLD, marginTop: 7 }} />
              <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 19, flex: 1 }}>{f}</Text>
            </View>
          ))}
          {nextUp ? (
            <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 8, marginTop: 3 }}>
              <Ionicons name="flag" size={13} color={GOLD} style={{ marginTop: 3 }} />
              <Text style={{ fontSize: 13, color: colors.text, lineHeight: 19, flex: 1, fontWeight: '500' }}>
                <Text style={{ color: GOLD, fontWeight: '700' }}>Next: </Text>{nextUp}
              </Text>
            </View>
          ) : null}

          {/* Expand / collapse */}
          <TouchableOpacity
            onPress={() => setExpanded(!expanded)}
            style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4, marginTop: 12, paddingTop: 10, borderTopWidth: 1, borderTopColor: colors.border }}
            activeOpacity={0.7}
            testID="intel-expand-btn"
            dataSet={{ testid: 'intel-expand-btn' }}
          >
            <Text style={{ fontSize: 13, fontWeight: '600', color: colors.textSecondary }}>{expanded ? 'Hide full briefing' : 'Full briefing'}</Text>
            <Ionicons name={expanded ? 'chevron-up' : 'chevron-down'} size={14} color={colors.textSecondary} />
          </TouchableOpacity>

          {expanded && (
            <View style={{ marginTop: 12 }}>
              <IntelRenderer text={summary} />
              <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 12, paddingTop: 10, borderTopWidth: 1, borderTopColor: colors.border }}>
                <Text style={{ fontSize: 12, color: colors.textTertiary, flex: 1 }}>
                  {intelData.data_points?.messages || 0} texts · {intelData.data_points?.calls || 0} calls · {intelData.data_points?.voice_notes || 0} voice notes · {intelData.data_points?.events || 0} events
                </Text>
                <TouchableOpacity onPress={onRefresh} disabled={refreshing} style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }} testID="intel-refresh-btn" dataSet={{ testid: 'intel-refresh-btn' }}>
                  <Ionicons name="refresh" size={13} color={GOLD} />
                  <Text style={{ fontSize: 12, fontWeight: '700', color: GOLD }}>Refresh</Text>
                </TouchableOpacity>
              </View>
            </View>
          )}
        </>
      ) : refreshing ? (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 8 }}>
          <ActivityIndicator size="small" color={GOLD} />
          <Text style={{ fontSize: 13, color: colors.textSecondary, fontStyle: 'italic' }}>Building your briefing…</Text>
        </View>
      ) : (
        <View style={{ paddingTop: 8 }}>
          <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 19 }}>
            Intel builds itself from texts, calls, and voice notes — check back after your first interaction.
          </Text>
          <TouchableOpacity
            onPress={onRefresh}
            style={{ alignSelf: 'flex-start', marginTop: 10, paddingHorizontal: 14, paddingVertical: 7, borderRadius: 20, backgroundColor: `${GOLD}18`, borderWidth: 1, borderColor: `${GOLD}40` }}
            testID="intel-generate-btn"
            dataSet={{ testid: 'intel-generate-btn' }}
          >
            <Text style={{ fontSize: 13, fontWeight: '700', color: GOLD }}>Generate now</Text>
          </TouchableOpacity>
        </View>
      )}
    </View>
  );
}
