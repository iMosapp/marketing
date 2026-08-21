import React, { useState, useRef, useMemo } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { CallRecordingPlayer } from './CallRecordingPlayer';
import api from '../services/api';

type Props = {
  call: any;
  colors: any;
  isInbound?: boolean;
};

export const CallTranscript = ({ call, colors, isInbound = false }: Props) => {
  const [posMs, setPosMs] = useState(0);
  const seekRef = useRef<((ms: number) => void) | null>(null);
  const tint = isInbound ? '#007AFF' : '#34C759';

  const hasRecording = !!call.recording_url;
  const segs = call.transcript_segments || [];
  const canSync = hasRecording && segs.length > 0 && segs.some((s: any) => s.start != null);

  const recUrl = hasRecording
    ? (call.call_sid
        ? `${api.defaults.baseURL}/calls/recording/${call.call_sid}`
        : `${api.defaults.baseURL}/webhooks/twilio/media-proxy?url=${encodeURIComponent(call.recording_url)}`)
    : '';

  // The segment currently being spoken
  const activeIdx = useMemo(() => {
    if (!canSync || posMs <= 0) return -1;
    const t = posMs / 1000;
    let idx = -1;
    for (let i = 0; i < segs.length; i++) {
      if ((segs[i].start ?? 0) <= t) idx = i;
      else break;
    }
    return idx;
  }, [posMs, segs, canSync]);

  return (
    <>
      {hasRecording ? (
        <View style={{ backgroundColor: colors.surface, borderRadius: 10, padding: 10, marginBottom: 8 }}>
          <CallRecordingPlayer
            url={recUrl}
            tint={tint}
            textColor={colors.text}
            subColor={colors.textSecondary}
            trackColor={colors.border}
            onPositionChange={setPosMs}
            seekControl={seekRef}
          />
        </View>
      ) : null}

      {segs.length ? (
        <View style={{ borderTopWidth: 1, borderTopColor: colors.border, paddingTop: 8 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
            <Text style={{ color: colors.textSecondary, fontSize: 11, fontWeight: '700', letterSpacing: 0.5 }}>TRANSCRIPT</Text>
            {canSync && (
              <Text style={{ color: colors.textSecondary, fontSize: 10, fontStyle: 'italic' }}>tap a line to jump</Text>
            )}
          </View>
          {segs.map((seg: any, si: number) => {
            const isActive = si === activeIdx;
            return (
              <TouchableOpacity
                key={si}
                activeOpacity={canSync && seg.start != null ? 0.6 : 1}
                onPress={() => {
                  if (canSync && seg.start != null) seekRef.current?.(Math.floor(seg.start * 1000));
                }}
                style={{
                  marginBottom: 8,
                  borderRadius: 8,
                  padding: isActive ? 8 : 0,
                  marginLeft: isActive ? -8 : 0,
                  marginRight: isActive ? -8 : 0,
                  backgroundColor: isActive ? `${tint}18` : 'transparent',
                  borderLeftWidth: isActive ? 3 : 0,
                  borderLeftColor: tint,
                }}
                data-testid={`transcript-seg-${si}`}
              >
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                  <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: seg.role === 'rep' ? '#C9A962' : '#007AFF' }} />
                  <Text style={{ color: seg.role === 'rep' ? '#C9A962' : '#007AFF', fontSize: 11, fontWeight: '800' }}>
                    {seg.speaker}
                  </Text>
                  {seg.start != null && (
                    <Text style={{ color: isActive ? tint : colors.textSecondary, fontSize: 10, fontWeight: isActive ? '800' : '400' }}>
                      {Math.floor(seg.start / 60)}:{String(Math.floor(seg.start % 60)).padStart(2, '0')}
                    </Text>
                  )}
                </View>
                <Text style={{ color: isActive ? colors.text : colors.text, fontSize: 12, lineHeight: 17, marginTop: 2, paddingLeft: 12, fontWeight: isActive ? '600' : '400' }}>
                  {seg.text}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>
      ) : call.transcript ? (
        <View style={{ borderTopWidth: 1, borderTopColor: colors.border, paddingTop: 8 }}>
          <Text style={{ color: colors.textSecondary, fontSize: 11, fontWeight: '700', marginBottom: 4, letterSpacing: 0.5 }}>TRANSCRIPT</Text>
          <Text style={{ color: colors.textSecondary, fontSize: 12, lineHeight: 17 }}>
            {call.transcript}
          </Text>
        </View>
      ) : null}
    </>
  );
};
