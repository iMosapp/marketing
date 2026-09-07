import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView, ActivityIndicator, Switch,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useThemeStore } from '../../store/themeStore';
import { useAuthStore } from '../../store/authStore';
import { useToast } from '../../components/common/Toast';
import { ScreenHeader } from '../../components/common/ScreenHeader';
import { FS, EYEBROW } from '../../constants/typography';
import api from '../../services/api';

const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });

type Channel = {
  id: string; name: string; icon: string; color: string; description: string;
  url_scheme: string; requires_phone: boolean;
};

export default function MessagingChannelsSettings() {
  const router = useRouter();
  const colors = useThemeStore((s) => s.colors);
  const user = useAuthStore((s) => s.user);
  const { showToast } = useToast();
  const [available, setAvailable] = useState<Channel[]>([]);
  const [enabled, setEnabled] = useState<string[]>(['sms']);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [failed, setFailed] = useState(false);

  const orgId = user?.organization_id;

  useEffect(() => { loadChannels(); }, []);

  const loadChannels = async () => {
    setLoading(true);
    setFailed(false);
    try {
      if (orgId) {
        const res = await api.get(`/messaging-channels/org/${orgId}`);
        setAvailable(res.data.available || []);
        setEnabled(res.data.enabled_channels || ['sms']);
      } else {
        const res = await api.get('/messaging-channels/available');
        setAvailable(res.data || []);
      }
    } catch (e) {
      console.error('Failed to load channels:', e);
      setFailed(true);
    }
    setLoading(false);
  };

  const toggleChannel = useCallback(async (channelId: string) => {
    const isEnabled = enabled.includes(channelId);
    let updated: string[];

    if (isEnabled) {
      if (enabled.length <= 1) {
        showToast('At least one channel must be enabled', 'error');
        return;
      }
      updated = enabled.filter(c => c !== channelId);
    } else {
      updated = [...enabled, channelId];
    }

    setEnabled(updated);

    if (orgId) {
      setSaving(true);
      try {
        await api.put(`/messaging-channels/org/${orgId}`, { channels: updated });
        showToast(`${isEnabled ? 'Disabled' : 'Enabled'} ${channelId}`, 'success');
      } catch (e: any) {
        showToast('Failed to save', 'error');
        setEnabled(enabled);
      }
      setSaving(false);
    }
  }, [enabled, orgId]);

  const enabledCount = enabled.length;
  const subtitle = loading ? undefined : `${enabledCount} channel${enabledCount !== 1 ? 's' : ''} enabled · ${enabledCount === 1 ? 'messages go directly' : 'team picks a channel'}`;

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.bg }]} edges={['top']}>
      <ScreenHeader
        title="Messaging Channels"
        subtitle={subtitle}
        testID="messaging-channels-header"
        right={saving ? <ActivityIndicator size="small" color={colors.accent} /> : undefined}
      />

      {loading ? (
        <ActivityIndicator size="large" color={colors.accent} style={{ marginTop: 40 }} />
      ) : failed || available.length === 0 ? (
        <View style={styles.empty} {...tid('messaging-channels-empty')}>
          <Ionicons name="chatbubbles-outline" size={44} color={colors.textTertiary} />
          <Text style={[styles.emptyTitle, { color: colors.text }]}>{failed ? 'Could not load channels' : 'No channels available'}</Text>
          <Text style={[styles.emptySub, { color: colors.textSecondary }]}>Check your connection and try again.</Text>
          <TouchableOpacity onPress={loadChannels} style={[styles.retryBtn, { backgroundColor: colors.accent }]} {...tid('messaging-channels-retry')}>
            <Text style={styles.retryText}>Retry</Text>
          </TouchableOpacity>
        </View>
      ) : (
      <ScrollView style={styles.scroll} contentContainerStyle={styles.content}>
        <View style={[styles.infoBanner, { backgroundColor: 'rgba(201,169,98,0.10)', borderColor: 'rgba(201,169,98,0.25)' }]}>
          <Ionicons name="information-circle" size={18} color={colors.accent} />
          <Text style={[styles.infoText, { color: colors.textSecondary }]}>
            {enabledCount === 1
              ? 'With one channel enabled, messages open directly. No extra steps for your team.'
              : 'With multiple channels, your team sees a quick picker to choose where to send.'}
          </Text>
        </View>

        {available.map((ch) => {
          const isOn = enabled.includes(ch.id);
          return (
            <View key={ch.id} style={[styles.channelCard, {
              backgroundColor: colors.card,
              borderColor: isOn ? `${ch.color}55` : colors.border,
              borderLeftColor: isOn ? ch.color : colors.border,
            }]} {...tid(`channel-card-${ch.id}`)}>
              <View style={[styles.channelIcon, { backgroundColor: `${ch.color}18` }]}>
                <Ionicons name={ch.icon as any} size={22} color={ch.color} />
              </View>
              <View style={{ flex: 1, minWidth: 0 }}>
                <Text style={[styles.channelName, { color: colors.text }]}>{ch.name}</Text>
                <Text style={[styles.channelDesc, { color: colors.textSecondary }]}>{ch.description}</Text>
                {ch.requires_phone && (
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 3 }}>
                    <Ionicons name="call-outline" size={10} color={colors.textTertiary} />
                    <Text style={{ fontSize: FS.caption, color: colors.textTertiary }}>Requires contact phone number</Text>
                  </View>
                )}
              </View>
              <Switch
                value={isOn}
                onValueChange={() => toggleChannel(ch.id)}
                trackColor={{ false: colors.surface, true: ch.color }}
                thumbColor="#FFF"
                {...tid(`toggle-${ch.id}`)}
              />
            </View>
          );
        })}

        <Text style={[styles.sectionTitle, { color: colors.textSecondary }]}>Share experience preview</Text>
        <View style={[styles.previewCard, { backgroundColor: colors.card, borderColor: colors.border }]} {...tid('messaging-channels-preview')}>
          {enabledCount === 1 ? (
            <View style={styles.previewSingle}>
              <Ionicons name={(available.find(c => c.id === enabled[0])?.icon || 'chatbubble') as any} size={24} color={available.find(c => c.id === enabled[0])?.color || '#34C759'} />
              <Text style={[styles.previewText, { color: colors.text }]}>
                Messages open directly in {available.find(c => c.id === enabled[0])?.name || 'SMS'}
              </Text>
              <Text style={{ fontSize: FS.secondary, color: colors.textSecondary }}>Zero extra taps for your team</Text>
            </View>
          ) : (
            <View>
              <Text style={[styles.previewLabel, { color: colors.textSecondary }]}>Your team will see:</Text>
              <View style={styles.previewPicker}>
                {enabled.map(chId => {
                  const ch = available.find(c => c.id === chId);
                  if (!ch) return null;
                  return (
                    <View key={chId} style={[styles.previewOption, { backgroundColor: `${ch.color}15`, borderColor: `${ch.color}30` }]}>
                      <Ionicons name={ch.icon as any} size={18} color={ch.color} />
                      <Text style={{ fontSize: FS.secondary, color: ch.color, fontWeight: '600' }}>{ch.name}</Text>
                    </View>
                  );
                })}
              </View>
            </View>
          )}
        </View>

        <View style={{ height: 40 }} />
      </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  scroll: { flex: 1 },
  content: { padding: 16, maxWidth: 700, alignSelf: 'center' as any, width: '100%' },
  infoBanner: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, padding: 12, borderRadius: 12, borderWidth: 1, marginBottom: 16 },
  infoText: { flex: 1, fontSize: FS.secondary, lineHeight: 17 },
  channelCard: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderRadius: 16, borderWidth: 1, borderLeftWidth: 4, marginBottom: 8 },
  channelIcon: { width: 42, height: 42, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  channelName: { fontSize: FS.heading, fontWeight: '700' },
  channelDesc: { fontSize: FS.secondary, marginTop: 2, lineHeight: 16 },
  sectionTitle: { ...EYEBROW, marginTop: 20, marginBottom: 10 },
  previewCard: { borderRadius: 16, borderWidth: 1, padding: 16 },
  previewSingle: { alignItems: 'center', gap: 6, paddingVertical: 10 },
  previewText: { fontSize: FS.heading, fontWeight: '700', textAlign: 'center' },
  previewLabel: { fontSize: FS.body, marginBottom: 10 },
  previewPicker: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  previewOption: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 14, paddingVertical: 8, borderRadius: 10, borderWidth: 1 },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32 },
  emptyTitle: { fontSize: FS.heading, fontWeight: '700', marginTop: 12, textAlign: 'center' },
  emptySub: { fontSize: FS.body, marginTop: 6, textAlign: 'center' },
  retryBtn: { marginTop: 18, paddingHorizontal: 22, paddingVertical: 12, borderRadius: 14 },
  retryText: { color: '#000', fontWeight: '700', fontSize: FS.heading },
});
