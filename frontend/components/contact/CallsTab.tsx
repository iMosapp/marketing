/**
 * CallsTab — call history list with AI summaries and synced transcript player.
 * Extracted from contact/[id].tsx (render-only; all state lives in the parent).
 */
import React from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { CallTranscript } from '../CallTranscript';

export default function CallsTab({ colors, callLogs, callLogsLoading, onRefresh }: any) {
  return (
    <View style={{ padding: 16 }}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <Text style={{ color: colors.textSecondary, fontSize: 13 }}>
          {callLogs.length} call{callLogs.length !== 1 ? 's' : ''}
        </Text>
        <TouchableOpacity
          onPress={onRefresh}
          style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}
          data-testid="refresh-calls-btn"
        >
          <Ionicons name="refresh" size={14} color={colors.accent} />
          <Text style={{ color: colors.accent, fontSize: 13, fontWeight: '600' }}>Refresh</Text>
        </TouchableOpacity>
      </View>
      {callLogsLoading ? (
        <View style={{ alignItems: 'center', padding: 40 }}>
          <ActivityIndicator size="large" color={colors.accent} />
          <Text style={{ color: colors.textSecondary, marginTop: 8 }}>Loading call history...</Text>
        </View>
      ) : callLogs.length === 0 ? (
        <View style={{ alignItems: 'center', padding: 40 }}>
          <Ionicons name="call-outline" size={48} color={colors.textSecondary} />
          <Text style={{ color: colors.text, fontSize: 16, fontWeight: '600', marginTop: 12 }}>No calls yet</Text>
          <Text style={{ color: colors.textSecondary, fontSize: 13, marginTop: 4, textAlign: 'center' }}>
            Call logs and AI summaries will appear here after calls are made or received.
          </Text>
        </View>
      ) : (
        callLogs.map((call: any, i: number) => {
          const ts = call.timestamp || call.created_at;
          const date = ts ? new Date(ts).toLocaleString() : '';
          const dur = call.duration_s || call.duration || 0;
          const durStr = dur > 0 ? `${Math.floor(dur/60)}m ${dur%60}s` : '';
          const isInbound = (call.direction || '').includes('inbound');
          const hasData = !!(call.ai_summary || call.transcript);
          const isRecent = ts && (Date.now() - new Date(ts).getTime()) < 10 * 60 * 1000; // < 10 min

          return (
            <View key={`call-${i}`} style={{ backgroundColor: colors.card, borderRadius: 14, padding: 14, marginBottom: 12 }}>
              {/* Header */}
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                <View style={{ width: 38, height: 38, borderRadius: 19, backgroundColor: isInbound ? '#007AFF20' : '#34C75920', alignItems: 'center', justifyContent: 'center' }}>
                  <Ionicons name={isInbound ? 'call-outline' : 'call'} size={17} color={isInbound ? '#007AFF' : '#34C759'} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={{ color: colors.text, fontWeight: '700', fontSize: 15 }}>
                    {isInbound ? 'Inbound call' : 'Outbound call'}{durStr ? ` — ${durStr}` : ''}
                  </Text>
                  <Text style={{ color: colors.textSecondary, fontSize: 12, marginTop: 1 }}>{date}</Text>
                </View>
                {!hasData && isRecent && (
                  <View style={{ backgroundColor: '#FF950015', borderRadius: 8, paddingHorizontal: 8, paddingVertical: 3 }}>
                    <Text style={{ fontSize: 11, color: '#FF9500', fontWeight: '700' }}>PROCESSING</Text>
                  </View>
                )}
              </View>

              {/* AI Summary */}
              {call.ai_summary ? (
                <View style={{ backgroundColor: '#C9A96210', borderRadius: 10, padding: 10, marginBottom: 8, borderLeftWidth: 3, borderLeftColor: '#C9A962' }}>
                  <Text style={{ color: '#C9A962', fontSize: 12, fontWeight: '700', marginBottom: 5, letterSpacing: 0.8 }}>AI KEY INFO</Text>
                  <Text style={{ color: colors.text, fontSize: 13, lineHeight: 19 }}>{call.ai_summary}</Text>
                </View>
              ) : !hasData && !isRecent ? (
                <View style={{ backgroundColor: colors.surface, borderRadius: 10, padding: 10, marginBottom: 8 }}>
                  <Text style={{ color: colors.textSecondary, fontSize: 12, fontStyle: 'italic' }}>
                    No transcript available for this call.
                  </Text>
                </View>
              ) : !hasData && isRecent ? (
                <View style={{ backgroundColor: '#FF950010', borderRadius: 10, padding: 10, marginBottom: 8 }}>
                  <Text style={{ color: '#FF9500', fontSize: 12 }}>
                    Transcript is being processed — check back in a few minutes.
                  </Text>
                </View>
              ) : null}

              {/* Recording player + synced transcript (tap a line to jump) */}
              <CallTranscript call={call} colors={colors} isInbound={isInbound} />
            </View>
          );
        })
      )}
    </View>
  );
}
