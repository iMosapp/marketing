/** MESSAGING READY banner + one status line per Twilio resource (subaccount, profile, brand, campaign, Messaging Service, numbers). */
import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { GOLD, Pill, STATUS_COLOR, tid } from './shared';

const ORDER = ['subaccount', 'compliance_profile', 'a2p_brand', 'a2p_campaign', 'messaging_service', 'phone_numbers'];
const ICON: Record<string, any> = { subaccount: 'business', compliance_profile: 'document-text', a2p_brand: 'ribbon', a2p_campaign: 'megaphone', messaging_service: 'git-network', phone_numbers: 'call' };

type Props = { view: any; colors: any; s: any };

export const StatusGrid = ({ view, colors, s }: Props) => {
  const router = useRouter();
  const ready = !!view.messaging_ready;
  const st = view.statuses || {};
  const complianceStoreId = view.compliance_store_id;
  return (
    <View style={s.card} {...tid('twilio-status-card')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: ready ? '#34C75918' : `${GOLD}18`, borderRadius: 12, padding: 12, marginBottom: 12 }} {...tid('messaging-ready-banner')} dataSet={{ testid: 'messaging-ready-banner', ready: ready ? '1' : '0' } as any}>
        <Ionicons name={ready ? 'checkmark-circle' : 'time'} size={22} color={ready ? '#34C759' : GOLD} />
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }} {...tid('messaging-ready-label')}>{ready ? 'MESSAGING READY' : 'Not ready to text yet'}</Text>
          <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }} {...tid('messaging-ready-next')}>{view.provisioning?.next_action}</Text>
        </View>
      </View>
      {ORDER.map((k, i) => {
        const v = st[k] || {};
        const color = STATUS_COLOR[v.status] || '#8E8E93';
        const link = ['compliance_profile', 'a2p_brand', 'a2p_campaign'].includes(k) && complianceStoreId;
        const Row: any = link ? TouchableOpacity : View;
        return (
          <Row key={k} onPress={link ? () => router.push(`/admin/compliance/${complianceStoreId}` as any) : undefined}
            style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 9, borderTopWidth: i ? 1 : 0, borderTopColor: colors.border }}
            {...tid(`twilio-resource-${k}`)} dataSet={{ testid: `twilio-resource-${k}`, status: v.status } as any}>
            <Ionicons name={ICON[k]} size={17} color={color} />
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>{v.title}</Text>
              <Text style={{ fontSize: 12, color: colors.textTertiary, lineHeight: 16 }} numberOfLines={2}>{v.detail}{v.sid ? ` · ${v.sid}` : ''}</Text>
            </View>
            <Pill label={v.label || v.status} color={color} />
            {link ? <Ionicons name="chevron-forward" size={14} color={colors.textTertiary} /> : null}
          </Row>
        );
      })}
    </View>
  );
};
