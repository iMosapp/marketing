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
import api from '../../services/api';

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

  const orgId = user?.organization_id;

  useEffect(() => { loadChannels(); }, []);

  const loadChannels = async () => {
    setLoading(true);
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
    }
    setLoading(false);
  };

  const toggleChannel = useCallback(async (channelId: string) => {
    const isEnabled = enabled.includes(channelId);
    let updated: string[];

    if (isEnabled) {
      // Don't allow disabling the last channel
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
        setEnabled(enabled); // revert
      }
      setSaving(false);
    }
  }, [enabled, orgId]);

  if (loading) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.bg }]}>
        <ActivityIndicator size="large" color="#007AFF" style={{ marginTop: 40 }} />
      </SafeAreaView>
    );
  }

  const enabledCount = enabled.length;

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.bg }]}>
      <ScrollView style={styles.scroll} contentContainerStyle={styles.content}>
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backBtn} data-testid="back-btn">
            <Ionicons name="arrow-back" size={22} color={colors.text} />
          </TouchableOpacity>
          <View style={{ flex: 1 }}>
            <Text style={[styles.title, { color: colors.text }]}>Messaging Channels</Text>
            <Text style={[styles.subtitle, { color: colors.textSecondary }]}>
              {enabledCount} channel{enabledCount !== 1 ? 's' : ''} enabled
              {enabledCount === 1 ? ' — messages go directly' : ' — users pick channel'}
            </Text>
          </View>
          {saving && <ActivityIndicator size="small" color="#007AFF" />}
        </View>

        {/* Info Banner */}
        <View style={[styles.infoBanner, { backgroundColor: '#C9A96215', borderColor: '#C9A96230' }]}>
          <Ionicons name="information-circle" size={18} color="#C9A962" />
          <Text style={[styles.infoText, { color: colors.textSecondary }]}>
            {enabledCount === 1
              ? 'With one channel enabled, messages open directly — no extra steps for your team.'
              : 'With multiple channels, your team sees a quick picker to choose where to send.'}
          </Text>
        </View>

        {/* Channel List */}
        {available.map((ch, i) => {
          const isOn = enabled.includes(ch.id);
          return (
            <View key={ch.id} style={[styles.channelCard, {
              backgroundColor: colors.card,
              borderColor: isOn ? `${ch.color}40` : colors.surface,
              borderLeftColor: isOn ? ch.color : colors.surface,
            }]} data-testid={`channel-card-${ch.id}`}>
              <View style={[styles.channelIcon, { backgroundColor: `${ch.color}18` }]}>
                <Ionicons name={ch.icon as any} size={22} color={ch.color} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={[styles.channelName, { color: colors.text }]}>{ch.name}</Text>
                <Text style={[styles.channelDesc, { color: colors.textSecondary }]}>{ch.description}</Text>
                {ch.requires_phone && (
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 3 }}>
                    <Ionicons name="call-outline" size={10} color="#888" />
                    <Text style={{ fontSize: 12, color: '#888' }}>Requires contact phone number</Text>
                  </View>
                )}
              </View>
              <Switch
                value={isOn}
                onValueChange={() => toggleChannel(ch.id)}
                trackColor={{ false: colors.surface, true: ch.color }}
                thumbColor="#FFF"
                data-testid={`toggle-${ch.id}`}
              />
            </View>
          );
        })}

        {/* Preview */}
        <Text style={[styles.sectionTitle, { color: colors.text }]}>Share Experience Preview</Text>
        <View style={[styles.previewCard, { backgroundColor: colors.card, borderColor: colors.surface }]}>
          {enabledCount === 1 ? (
            <View style={styles.previewSingle}>
              <Ionicons name={(available.find(c => c.id === enabled[0])?.icon || 'chatbubble') as any} size={24} color={available.find(c => c.id === enabled[0])?.color || '#34C759'} />
              <Text style={[styles.previewText, { color: colors.text }]}>
                Messages open directly in {available.find(c => c.id === enabled[0])?.name || 'SMS'}
              </Text>
              <Text style={{ fontSize: 13, color: colors.textSecondary }}>Zero extra taps for your team</Text>
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
                      <Text style={{ fontSize: 13, color: ch.color, fontWeight: '600' }}>{ch.name}</Text>
                    </View>
                  );
                })}
              </View>
            </View>
          )}
        </View>

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  scroll: { flex: 1 },
  content: { padding: 16, maxWidth: 700, alignSelf: 'center' as any, width: '100%' },
  header: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 16 },
  backBtn: { width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 21, fontWeight: '700' },
  subtitle: { fontSize: 14, marginTop: 2 },
  infoBanner: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, padding: 12, borderRadius: 10, borderWidth: 1, marginBottom: 16 },
  infoText: { flex: 1, fontSize: 14, lineHeight: 17 },
  channelCard: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderRadius: 12, borderWidth: 1.5, borderLeftWidth: 4, marginBottom: 8 },
  channelIcon: { width: 42, height: 42, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  channelName: { fontSize: 17, fontWeight: '700' },
  channelDesc: { fontSize: 14, marginTop: 2, lineHeight: 16 },
  sectionTitle: { fontSize: 17, fontWeight: '700', marginTop: 20, marginBottom: 10 },
  previewCard: { borderRadius: 12, borderWidth: 1, padding: 16 },
  previewSingle: { alignItems: 'center', gap: 6, paddingVertical: 10 },
  previewText: { fontSize: 16, fontWeight: '600' },
  previewLabel: { fontSize: 14, marginBottom: 10 },
  previewPicker: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  previewOption: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 14, paddingVertical: 8, borderRadius: 10, borderWidth: 1 },
});
