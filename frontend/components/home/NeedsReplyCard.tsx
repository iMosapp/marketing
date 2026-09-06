import React, { useCallback, useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { useThemeStore } from '../../store/themeStore';
import { messagesAPI } from '../../services/api';

const timeAgo = (iso?: string) => {
  if (!iso) return '';
  const m = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (m < 1) return 'now';
  if (m < 60) return `${m}m`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h`;
  return `${Math.round(h / 24)}d`;
};

const lastText = (c: any) => c?.last_message?.content || c?.last_message_preview || '';

// Rep Home: the conversations that need a human reply right now (waiting on rep, or unread customer texts).
export function NeedsReplyCard({ userId }: { userId: string }) {
  const { colors } = useThemeStore();
  const router = useRouter();
  const [rows, setRows] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    if (!userId) return;
    try {
      const all: any[] = await messagesAPI.getConversations(userId);
      const open = (all || []).filter(c => c.status !== 'closed' && c.status !== 'archived');
      const waiting = open.filter(c => c.needs_assistance || c.status === 'paused' || c.unread);
      waiting.sort((a, b) => {
        const ua = a.needs_assistance ? 1 : 0, ub = b.needs_assistance ? 1 : 0;
        if (ua !== ub) return ub - ua;
        return new Date(b.last_message_at || 0).getTime() - new Date(a.last_message_at || 0).getTime();
      });
      setTotal(waiting.length);
      setRows(waiting.slice(0, 3));
    } catch {
      setRows([]);
    } finally {
      setLoaded(true);
    }
  }, [userId]);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  if (!loaded) return null;

  return (
    <View style={{ marginHorizontal: 16, marginBottom: 20 }} data-testid="needs-reply-card">
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <View style={{ flex: 1, marginRight: 10 }}>
          <Text style={{ fontSize: 17, fontWeight: '700', color: colors.text }}>Needs a reply</Text>
          <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 2 }} numberOfLines={1}>
            {total === 0 ? 'Inbox is clear. Nice.' : `${total} conversation${total === 1 ? '' : 's'} waiting on you`}
          </Text>
        </View>
        <TouchableOpacity onPress={() => router.push('/(tabs)/inbox' as any)} data-testid="needs-reply-open-inbox">
          <Text style={{ fontSize: 13, fontWeight: '700', color: '#C9A962' }}>Open Inbox →</Text>
        </TouchableOpacity>
      </View>

      {rows.length === 0 ? (
        <View style={{ backgroundColor: colors.card, borderRadius: 16, padding: 20, alignItems: 'center', borderWidth: 1, borderColor: colors.border }}>
          <Ionicons name="chatbubbles-outline" size={28} color="#34C759" />
          <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 8, textAlign: 'center' }}>Everyone has been answered. Jessi has the rest.</Text>
        </View>
      ) : (
        <View style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: colors.border, overflow: 'hidden' }}>
          {rows.map((c, i) => {
            const waiting = !!c.needs_assistance || c.status === 'paused';
            const initials = (c.contact_name || '?').split(' ').map((p: string) => p[0]).join('').slice(0, 2).toUpperCase();
            return (
              <TouchableOpacity
                key={c._id}
                onPress={() => router.push(`/thread/${c._id}` as any)}
                activeOpacity={0.75}
                style={{ flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderTopWidth: i ? 1 : 0, borderTopColor: colors.border }}
                data-testid={`needs-reply-row-${i}`}
              >
                <View style={{ width: 42, height: 42, borderRadius: 21, backgroundColor: waiting ? '#FF453A22' : '#C9A96222', alignItems: 'center', justifyContent: 'center' }}>
                  <Text style={{ fontSize: 14, fontWeight: '700', color: waiting ? '#FF453A' : '#C9A962' }}>{initials}</Text>
                </View>
                <View style={{ flex: 1, minWidth: 0 }}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                    {c.unread ? <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: '#FF453A' }} /> : null}
                    <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text, flex: 1 }} numberOfLines={1}>{c.contact_name || 'Unknown'}</Text>
                  </View>
                  <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }} numberOfLines={1}>
                    {c.last_message?.sender === 'ai' ? 'Jessi: ' : ''}{lastText(c) || 'Tap to open'}
                  </Text>
                </View>
                {waiting ? (
                  <View style={{ backgroundColor: '#FF453A22', borderRadius: 6, paddingHorizontal: 7, paddingVertical: 3 }}>
                    <Text style={{ fontSize: 10, fontWeight: '800', color: '#FF453A' }}>WAITING {timeAgo(c.you_are_needed_at || c.last_message_at)}</Text>
                  </View>
                ) : (
                  <Text style={{ fontSize: 11, color: colors.textSecondary }}>{timeAgo(c.last_message_at)}</Text>
                )}
              </TouchableOpacity>
            );
          })}
        </View>
      )}
    </View>
  );
}
