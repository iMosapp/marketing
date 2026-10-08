import React from 'react';
import { View, Text, TouchableOpacity, Image, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, tid } from '../inbox/ownership';
import { resolvePhotoUrl } from '../../utils/photoUrl';
import { Chip, SourceTag, SEVERITY_COLORS, CONFIDENCE_LABEL } from './shared';

type Props = { colors: any; finding: any; onDecide: (decision: 'confirmed' | 'dismissed' | 'pending') => void; onEdit: () => void; onEvidence: (ev: any) => void; busy?: boolean };

// One AI (or human) finding: what, where, how sure, the frames that show it, and CONFIRM · DISMISS · EDIT. Low confidence reads "Possible — Needs Review".
export const FindingCard = ({ colors, finding: f, onDecide, onEdit, onEvidence, busy }: Props) => {
  const sev = SEVERITY_COLORS[f.severity] || colors.textSecondary;
  const confirmed = f.decision === 'confirmed';
  const dismissed = f.decision === 'dismissed';
  const title = f.possible ? `Possible ${f.subtype_label} — Needs Review` : `${f.severity_label} ${f.subtype_label}`;
  const Btn = ({ icon, label, onPress, active, color, testId }: any) => (
    <TouchableOpacity onPress={onPress} disabled={busy} style={{ flex: 1, height: 40, borderRadius: 10, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: active ? color : colors.bg, borderWidth: 1, borderColor: active ? color : colors.border }} {...tid(testId)}>
      <Ionicons name={icon} size={15} color={active ? '#0B0B0D' : colors.text} /><Text style={{ fontSize: 13, fontWeight: '800', color: active ? '#0B0B0D' : colors.text }}>{label}</Text>
    </TouchableOpacity>
  );
  return (
    <View style={{ borderRadius: 16, padding: 14, backgroundColor: colors.card, borderWidth: 1, borderColor: confirmed ? '#34C75988' : dismissed ? colors.border : f.possible ? '#FF950088' : colors.border, gap: 10, opacity: dismissed ? 0.6 : 1 }} {...tid(`finding-${f.id}`)}>
      <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 10 }}>
        <View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: sev, marginTop: 6 }} />
        <View style={{ flex: 1, gap: 3 }}>
          <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }} {...tid(`finding-location-${f.id}`)}>{f.location_label}</Text>
          <Text style={{ fontSize: 13.5, color: f.possible ? '#FF9500' : colors.text, fontWeight: f.possible ? '700' : '500' }} {...tid(`finding-title-${f.id}`)}>{title}</Text>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 5, marginTop: 2 }}>
            <Chip label={f.category_label} color={GOLD} />
            {f.origin === 'voice' ? <Chip label={f.spoken_by === 'customer' ? 'Customer said' : 'You said'} color="#5AC8FA" icon="mic" testId={`finding-voice-${f.id}`} /> : null}
            {f.origin === 'ai' || f.origin === 'voice' ? <Chip label={CONFIDENCE_LABEL[f.confidence] || f.confidence} color={f.confidence === 'high' ? '#34C759' : f.confidence === 'medium' ? '#30B0C7' : '#FF9500'} testId={`finding-confidence-${f.id}`} /> : <Chip label="Added by you" color="#AF52DE" icon="person" />}
            {f.recon_cost != null ? <Chip label={`Recon $${Math.round(f.recon_cost).toLocaleString()}${f.recon_by_name ? ` · ${f.recon_by_name}` : ''}`} color="#34C759" icon="cash-outline" testId={`finding-recon-${f.id}`} /> : null}
            {f.edited ? <Chip label="Edited" color="#8E8E93" icon="create-outline" testId={`finding-edited-${f.id}`} /> : null}
            {confirmed ? <Chip label={`Confirmed${f.decision_by_name ? ` · ${f.decision_by_name.split(' ')[0]}` : ''}`} color="#34C759" icon="checkmark" testId={`finding-state-${f.id}`} /> : dismissed ? <Chip label="Dismissed" color="#8E8E93" icon="close" testId={`finding-state-${f.id}`} /> : <Chip label="Needs your call" color="#FF9500" testId={`finding-state-${f.id}`} />}
          </View>
        </View>
      </View>
      {f.quote ? <Text style={{ fontSize: 13.5, color: colors.text, lineHeight: 19, fontStyle: 'italic' }} {...tid(`finding-quote-${f.id}`)}>"{f.quote}"</Text> : null}
      {f.explanation ? <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>{f.explanation}</Text> : null}
      {f.evidence?.length ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
          {f.evidence.map((ev: any) => (
            <TouchableOpacity key={ev.frame_id} onPress={() => onEvidence(ev)} style={{ width: 120, gap: 3 }} {...tid(`evidence-${f.id}-${ev.frame_id}`)}>
              <View style={{ width: 120, height: 84, borderRadius: 10, overflow: 'hidden', backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.border }}>
                {ev.thumb_url ? <Image source={{ uri: resolvePhotoUrl(ev.thumb_url) || '' }} style={{ width: '100%', height: '100%' }} resizeMode="cover" /> : null}
                {ev.timestamp_label ? <View style={{ position: 'absolute', left: 5, bottom: 5, backgroundColor: '#000000AA', borderRadius: 5, paddingHorizontal: 5, paddingVertical: 1 }}><Text style={{ fontSize: 10, fontWeight: '700', color: '#fff' }}>{ev.timestamp_label}</Text></View> : null}
              </View>
              <Text style={{ fontSize: 10.5, color: colors.textSecondary }} numberOfLines={1}>{ev.media_kind === 'video' ? 'Video: ' : ''}{ev.media_name}</Text>
              <SourceTag source={ev.media_source} colors={colors} />
            </TouchableOpacity>
          ))}
        </ScrollView>
      ) : null}
      <View style={{ flexDirection: 'row', gap: 8 }}>
        <Btn icon="checkmark" label="Confirm" onPress={() => onDecide(confirmed ? 'pending' : 'confirmed')} active={confirmed} color="#34C759" testId={`finding-confirm-${f.id}`} />
        <Btn icon="close" label="Dismiss" onPress={() => onDecide(dismissed ? 'pending' : 'dismissed')} active={dismissed} color="#8E8E93" testId={`finding-dismiss-${f.id}`} />
        <Btn icon="create-outline" label="Edit" onPress={onEdit} active={false} color={GOLD} testId={`finding-edit-${f.id}`} />
      </View>
    </View>
  );
};
