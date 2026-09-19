/** This month's usage (SMS / MMS in and out, segments, number rental) and the audit trail. */
import React, { useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { prettyPhone, tid, when } from './shared';

const ACTION_LABEL: Record<string, string> = {
  subaccount_created: 'Subaccount created', subaccount_adopted: 'Subaccount adopted', subaccount_dry_run: 'Subaccount created (dry run)', subaccount_suspended: 'Subaccount suspended', subaccount_active: 'Subaccount reactivated',
  provisioning_started: 'Provisioning started', provision_step: 'Provisioning step', provisioning_error: 'Provisioning error', compliance_submitted: 'Compliance submitted',
  number_purchased: 'Number purchased', number_assigned: 'Number assigned', number_reassigned: 'Number reassigned', number_unassigned: 'Number unassigned',
  number_suspended: 'Number suspended', number_reactivated: 'Number reactivated', number_released: 'Number released', number_imported: 'Number imported', number_purchase_failed: 'Purchase failed',
  number_release_failed: 'Release failed', inbound_unrouted: 'Unrouted inbound text', flags_changed: 'Settings changed',
};

export const UsageCard = ({ usage, colors, s }: { usage: any; colors: any; s: any }) => {
  const t = usage?.totals || {};
  const Stat = ({ label, value, testID }: any) => (
    <View style={{ flex: 1, minWidth: 90, backgroundColor: colors.bg, borderRadius: 10, padding: 10 }} {...tid(testID)}>
      <Text style={{ fontSize: 20, fontWeight: '800', color: colors.text }}>{value ?? 0}</Text>
      <Text style={{ fontSize: 11, fontWeight: '700', color: colors.textTertiary, textTransform: 'uppercase', letterSpacing: 0.4 }}>{label}</Text>
    </View>
  );
  return (
    <View style={s.card} {...tid('usage-card')}>
      <Text style={s.cardTitle}>Usage · {usage?.month}</Text>
      <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
        <Stat label="SMS sent" value={t.sms_out} testID="usage-sms-out" />
        <Stat label="SMS received" value={t.sms_in} testID="usage-sms-in" />
        <Stat label="MMS sent" value={t.mms_out} testID="usage-mms-out" />
        <Stat label="MMS received" value={t.mms_in} testID="usage-mms-in" />
        <Stat label="Segments out" value={t.segments_out} testID="usage-segments-out" />
        <Stat label="Numbers · $/mo" value={`${usage?.numbers_active ?? 0} · $${usage?.numbers_monthly_cost_usd ?? 0}`} testID="usage-numbers-cost" />
      </View>
      {(usage?.per_number || []).length > 0 && (
        <View style={{ marginTop: 10 }}>
          {usage.per_number.slice(0, 8).map((r: any) => (
            <Text key={r.phone_number || 'none'} style={{ fontSize: 12.5, color: colors.textSecondary, paddingTop: 4 }} {...tid(`usage-number-${(r.phone_number || '').replace(/\D/g, '')}`)}>
              {prettyPhone(r.phone_number) || 'unattributed'} · {r.sms_out + r.mms_out} out · {r.sms_in + r.mms_in} in
            </Text>
          ))}
        </View>
      )}
      <Text style={s.hint}>Counted per message at send and receive time. Twilio fees are added when price data is available; number rental is estimated at $1.15/mo.</Text>
    </View>
  );
};

export const AuditList = ({ entries, colors, s }: { entries: any[]; colors: any; s: any }) => {
  const [open, setOpen] = useState(false);
  const list = entries || [];
  return (
    <View style={s.card} {...tid('audit-card')}>
      <TouchableOpacity onPress={() => setOpen(v => !v)} style={{ flexDirection: 'row', alignItems: 'center' }} {...tid('audit-toggle')}>
        <Text style={[s.cardTitle, { flex: 1, marginBottom: 0 }]}>Audit log ({list.length})</Text>
        <Ionicons name={open ? 'chevron-up' : 'chevron-down'} size={16} color={colors.textSecondary} />
      </TouchableOpacity>
      {open && list.length === 0 && <Text style={[s.hint, { marginTop: 8 }]}>Nothing yet.</Text>}
      {open && list.map((e: any) => (
        <View key={e.id} style={{ paddingTop: 8, marginTop: 8, borderTopWidth: 1, borderTopColor: colors.border }} {...tid(`audit-${e.id}`)}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            <Ionicons name={e.ok ? 'checkmark-circle' : 'alert-circle'} size={14} color={e.ok ? '#34C759' : '#FF3B30'} />
            <Text style={{ flex: 1, fontSize: 13, fontWeight: '700', color: colors.text }}>{ACTION_LABEL[e.action] || e.action}</Text>
            <Text style={{ fontSize: 11.5, color: colors.textTertiary }}>{when(e.at)}</Text>
          </View>
          <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }}>
            {e.actor_name || 'system'}{e.target?.phone_number ? ` · ${prettyPhone(e.target.phone_number)}` : ''}{e.details?.to_user_name ? ` → ${e.details.to_user_name}` : ''}{e.details?.status ? ` · ${e.details.status}` : ''}{e.error ? ` · ${e.error}` : ''}
          </Text>
        </View>
      ))}
    </View>
  );
};
