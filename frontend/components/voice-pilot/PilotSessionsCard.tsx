import React from 'react';
import { View, Text } from 'react-native';
import { useThemeStore } from '../../store/themeStore';
import { Card, Pill, PilotStatus, Segment, GOLD, GREEN, RED, AMBER, fmtS, usd, when, ENGINE_LABEL, tid } from './shared';

const stopTone = (r?: string | null) => (!r ? GREEN : r === 'close_requested' || r === 'idle' || r === 'handoff' ? '#8E8E93' : r === 'killed' || r === 'server_kill' ? RED : AMBER);

const SegmentRow = ({ seg, colors }: { seg: Segment; colors: any }) => (
  <View style={{ paddingVertical: 8, borderTopWidth: 1, borderTopColor: colors.border }} {...tid(`pilot-seg-${seg.live_id}`)}>
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
      <Pill text={ENGINE_LABEL[seg.engine] || seg.engine} tone={seg.engine === 'live' ? GOLD : AMBER} />
      <Text style={{ color: colors.text, fontSize: 13, fontWeight: '700', flex: 1 }} numberOfLines={1}>{seg.user}{seg.device_id ? ` · ${seg.device_id}` : ''}</Text>
      <Text style={{ color: colors.textSecondary, fontSize: 12 }}>{when(seg.started_at)}</Text>
    </View>
    <Text style={{ color: colors.textSecondary, fontSize: 12, marginTop: 3 }}>
      {fmtS(seg.billable_s)} billed · holding {fmtS(Math.max(0, seg.reserved_s - seg.settled_s))} · {usd(seg.est_cost_usd)} ({seg.cost_basis || 'server clock'})
      {seg.segment_no && seg.segment_no > 1 ? ` · segment ${seg.segment_no}` : ''}{seg.fake_provider ? ' · FAKE' : ''}{seg.unconfirmed && seg.status === 'closed' ? ' · unconfirmed' : ''}
    </Text>
    <Text style={{ color: stopTone(seg.stop_reason), fontSize: 12, marginTop: 2 }}>{seg.status === 'open' ? (seg.stop_reason ? `told to stop: ${seg.stop_reason}` : 'open') : `ended: ${seg.stop_reason || 'closed'}`}{seg.kill_attempts ? ` · kill attempts ${seg.kill_attempts}` : ''}</Text>
  </View>
);

// Open sessions (what the kill switch would end), the hand-offs between engines, and the latest segments on the account.
export const PilotSessionsCard = ({ s }: { s: PilotStatus }) => {
  const { colors } = useThemeStore();
  return (
    <>
      <Card title={`ACTIVE SESSIONS · ${s.active.length}`} testID="pilot-active-card">
        {s.active.length === 0 && <Text style={{ color: colors.textSecondary, fontSize: 13 }} {...tid('pilot-active-none')}>Nobody is talking to Jessi right now.</Text>}
        {s.active.map(seg => <SegmentRow key={seg.live_id} seg={seg} colors={colors} />)}
      </Card>
      <Card title={`RECENT HAND-OFFS · ${s.handoffs.length}`} testID="pilot-handoffs-card">
        {s.handoffs.length === 0 && <Text style={{ color: colors.textSecondary, fontSize: 13 }} {...tid('pilot-handoffs-none')}>No engine switch yet. One appears here the moment a premium pool runs out mid-conversation.</Text>}
        {s.handoffs.map(h => (
          <View key={h.to_live_id} style={{ paddingVertical: 8, borderTopWidth: 1, borderTopColor: colors.border }} {...tid(`pilot-handoff-${h.to_live_id}`)}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <Text style={{ color: colors.text, fontSize: 13, fontWeight: '700', flex: 1 }} numberOfLines={1}>{h.user}</Text>
              <Text style={{ color: colors.textSecondary, fontSize: 12 }}>{when(h.at)}</Text>
            </View>
            <Text style={{ color: colors.textSecondary, fontSize: 12, marginTop: 3 }}>
              {ENGINE_LABEL[h.from_engine || ''] || h.from_engine || '?'} ({fmtS(h.from_billable_s)}) → {ENGINE_LABEL[h.to_engine] || h.to_engine} ({fmtS(h.to_billable_s)}{h.to_status === 'open' ? ', still open' : ''}) · {h.reason.replace('_', ' ')}
            </Text>
          </View>
        ))}
      </Card>
      <Card title="RECENT SEGMENTS" testID="pilot-recent-card">
        {s.recent.length === 0 && <Text style={{ color: colors.textSecondary, fontSize: 13 }}>No voice sessions on this account yet.</Text>}
        {s.recent.map(seg => <SegmentRow key={seg.live_id} seg={seg} colors={colors} />)}
      </Card>
    </>
  );
};
