import React from 'react';
import { View, Text } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { format } from 'date-fns';
import { CallRecordingPlayer } from '../CallRecordingPlayer';
import api from '../../services/api';

export const CallLogCard = ({ item, timestamp }: { item: any; timestamp: Date }) => {
  const hasRecording = item.has_recording;
  const aiSummary    = item.ai_summary || '';
  const dur          = item.duration_s || 0;
  const durLabel     = dur >= 60 ? `${Math.floor(dur / 60)}m ${dur % 60}s` : dur > 0 ? `${dur}s` : '';
  const isOutbound   = item.direction === 'outbound';
  const callStatus   = item.call_status || 'placed';
  const callColor    = '#30D158';

  return (
    <View style={{ marginVertical: 6, marginHorizontal: 16 }}>
      <Text style={{ fontSize: 12, color: '#8E8E93', marginBottom: 4, textAlign: 'center' }}>
        {format(timestamp, 'h:mm a')}
      </Text>
      <View style={{ backgroundColor: '#F2F9F4', borderRadius: 14, borderWidth: 1.5, borderColor: callColor, padding: 14 }}>
        {/* Call header */}
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: aiSummary ? 10 : 0 }}>
          <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: callColor + '20', alignItems: 'center', justifyContent: 'center' }}>
            <Ionicons name={isOutbound ? 'call' : 'call-outline'} size={18} color={callColor} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 15, fontWeight: '700', color: '#1C1C1E' }}>
              {isOutbound ? 'Outbound Call' : 'Inbound Call'}{durLabel ? ` · ${durLabel}` : ''}
            </Text>
            <Text style={{ fontSize: 12, color: '#8E8E93', marginTop: 1 }}>
              {callStatus === 'placed' ? 'Call placed — waiting for recording...' : callStatus === 'completed' ? 'Call completed' : callStatus}
            </Text>
          </View>
          {hasRecording && (
            <View style={{ backgroundColor: callColor + '20', borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3 }}>
              <Text style={{ fontSize: 11, color: callColor, fontWeight: '700' }}>✓ Recorded</Text>
            </View>
          )}
        </View>

        {/* AI Summary */}
        {!!aiSummary && (
          <View style={{ backgroundColor: '#fff', borderRadius: 10, padding: 10, borderWidth: 1, borderColor: '#E5E5EA' }}>
            <Text style={{ fontSize: 12, fontWeight: '700', color: '#8E8E93', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5 }}>Call Summary</Text>
            <Text style={{ fontSize: 13, color: '#1C1C1E', lineHeight: 18 }}>{aiSummary}</Text>
          </View>
        )}

        {/* Inline recording player — 1x / 1.5x / 2x speeds */}
        {hasRecording && (item.call_sid || item.recording_url) && (
          <View style={{ marginTop: 10, paddingTop: 10, borderTopWidth: 1, borderTopColor: '#E5E5EA' }}>
            <CallRecordingPlayer
              url={item.call_sid
                ? `${api.defaults.baseURL}/calls/recording/${item.call_sid}`
                : `${api.defaults.baseURL}/webhooks/twilio/media-proxy?url=${encodeURIComponent(item.recording_url)}`}
              tint={callColor}
            />
          </View>
        )}
      </View>
    </View>
  );
};
