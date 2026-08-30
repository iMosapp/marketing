/**
 * IntelBriefingCard — auto-updating Relationship Intel briefing.
 * Quick Take + key bullets at a glance; expands to the full briefing.
 */
import React, { useMemo, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { IntelRenderer } from '../../utils/contactHelpers';

const GOLD = '#C9A962';
const SECTIONS = ['Quick Take', 'Key Facts', 'Communication Patterns', 'Personal Notes', 'Before Your Next Interaction'];

function parseSections(text: string): Record<string, string[]> {
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

export default function IntelBriefingCard({ colors, intelData, refreshing, onRefresh }: any) {
  const [expanded, setExpanded] = useState(false);
  const summary: string = intelData?.summary || '';
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
          <Text style={{ fontSize: 12, fontWeight: '800', color: GOLD, letterSpacing: 1.2 }}>RELATIONSHIP INTEL</Text>
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
              <Text style={{ fontSize: 14, color: colors.textSecondary, lineHeight: 19, flex: 1 }}>{f}</Text>
            </View>
          ))}
          {nextUp ? (
            <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 8, marginTop: 3 }}>
              <Ionicons name="flag" size={13} color={GOLD} style={{ marginTop: 3 }} />
              <Text style={{ fontSize: 14, color: colors.text, lineHeight: 19, flex: 1, fontWeight: '500' }}>
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
                  {intelData.data_points?.messages || 0} messages · {intelData.data_points?.events || 0} events · {intelData.data_points?.voice_notes || 0} voice notes
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
          <Text style={{ fontSize: 14, color: colors.textSecondary, fontStyle: 'italic' }}>Building your briefing…</Text>
        </View>
      ) : (
        <View style={{ paddingTop: 8 }}>
          <Text style={{ fontSize: 14, color: colors.textSecondary, lineHeight: 19 }}>
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
