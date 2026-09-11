import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { View, Text, TouchableOpacity, FlatList, ScrollView, RefreshControl, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { GOLD, tid, ownershipAPI, errText, timeAgo, firstName } from './ownership';
import { InboxBadge, ClaimButton } from './InboxBadge';

type View_ = 'all' | 'unassigned' | 'mine';
type Props = { inboxes: any[]; meId?: string; colors: any; showToast: (m: string, t?: any, ms?: number) => void; onClaimed?: () => void; refreshInboxes: () => void };

const Chip = ({ label, count, active, color, onPress, testId, colors }: { label: string; count?: number; active: boolean; color?: string; onPress: () => void; testId: string; colors: any }) => {
  const c = color || GOLD;
  return (
    <TouchableOpacity onPress={onPress} activeOpacity={0.75} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 11, paddingVertical: 7, borderRadius: 14, backgroundColor: active ? c + '22' : colors.surface, borderWidth: 1, borderColor: active ? c : 'transparent' }} {...tid(testId)}>
      {color ? <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: c }} /> : null}
      <Text style={{ fontSize: 13, fontWeight: active ? '800' : '600', color: active ? c : colors.textPrimary }}>{label}</Text>
      {typeof count === 'number' ? <Text style={{ fontSize: 12, fontWeight: '800', color: active ? c : colors.textSecondary }}>{count > 99 ? '99+' : count}</Text> : null}
    </TouchableOpacity>
  );
};

export function SharedInboxPanel({ inboxes, meId, colors, showToast, onClaimed, refreshInboxes }: Props) {
  const router = useRouter();
  const [inboxId, setInboxId] = useState<string>('all');
  const [view, setView] = useState<View_>('all');
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [claiming, setClaiming] = useState<string | null>(null);
  const colorOf = useMemo(() => Object.fromEntries(inboxes.map((i: any) => [i.id, i.color || GOLD])), [inboxes]);

  const load = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    try {
      const targets = inboxId === 'all' ? inboxes : inboxes.filter((i: any) => i.id === inboxId);
      const results = await Promise.all(targets.map((i: any) => ownershipAPI.inboxConversations(i.id, view).catch(() => ({ conversations: [] }))));
      const merged = results.flatMap((r: any) => r.conversations || []);
      merged.sort((a: any, b: any) => (b.unread ? 1 : 0) - (a.unread ? 1 : 0) || new Date(b.last_message_at || 0).getTime() - new Date(a.last_message_at || 0).getTime());
      setRows(merged);
    } finally { setLoading(false); }
  }, [inboxId, view, inboxes]);

  useEffect(() => { load(); }, [load]);

  const totals = useMemo(() => {
    const src = inboxId === 'all' ? inboxes : inboxes.filter((i: any) => i.id === inboxId);
    return src.reduce((acc: any, i: any) => ({ open: acc.open + (i.counts?.open || 0), unassigned: acc.unassigned + (i.counts?.unassigned || 0), mine: acc.mine + (i.counts?.mine || 0) }), { open: 0, unassigned: 0, mine: 0 });
  }, [inboxes, inboxId]);

  const claim = async (row: any) => {
    setClaiming(row.id);
    try {
      const res = await ownershipAPI.claim(row.id);
      showToast(res?.already ? 'Already yours' : `${row.contact_name || 'Lead'} is yours`, 'success', 2000);
      setRows(prev => prev.map(r => r.id === row.id ? { ...r, assigned_to: meId, assigned_to_name: 'You', is_mine: true } : r));
      refreshInboxes(); onClaimed?.();
    } catch (e: any) {
      showToast(errText(e, "Couldn't claim that one"), 'error', 3000);
      load(true); refreshInboxes();
    } finally { setClaiming(null); }
  };

  const renderRow = ({ item }: { item: any }) => {
    const name = item.contact_name || item.contact_phone || 'Unknown';
    const unassigned = !item.assigned_to;
    const initials = name.split(' ').map((n: string) => n[0] || '').join('').toUpperCase().slice(0, 2) || '?';
    return (
      <TouchableOpacity activeOpacity={0.75} onPress={() => router.push({ pathname: `/thread/${item.id}`, params: { contact_name: name, contact_phone: item.contact_phone || '' } } as any)}
        style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 14, paddingVertical: 12, backgroundColor: colors.surface, borderLeftWidth: 3, borderLeftColor: unassigned ? GOLD : (colorOf[item.inbox_id] || 'transparent') }} {...tid(`inbox-thread-row-${item.id}`)}>
        <View style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: colors.elevated || colors.card, alignItems: 'center', justifyContent: 'center', borderWidth: item.unread ? 2 : 0, borderColor: GOLD }}>
          <Text style={{ fontSize: 15, fontWeight: '800', color: GOLD }}>{initials}</Text>
        </View>
        <View style={{ flex: 1, gap: 3 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <Text style={{ flex: 1, fontSize: 15, fontWeight: item.unread ? '800' : '600', color: colors.textPrimary }} numberOfLines={1}>{name}</Text>
            <Text style={{ fontSize: 12, color: colors.textSecondary }}>{timeAgo(item.last_message_at)}</Text>
          </View>
          <InboxBadge inboxName={item.inbox_name} color={colorOf[item.inbox_id]} ownerName={item.assigned_to_name} isMine={item.is_mine} unassigned={unassigned} isCollaborator={item.is_collaborator} colors={colors} />
          <Text style={{ fontSize: 13, color: colors.textSecondary }} numberOfLines={1}>
            {item.last_message_from === 'user' ? 'Rep: ' : ''}{item.last_message || (unassigned ? 'Waiting for someone to pick it up' : 'No messages yet')}
          </Text>
          {item.handoff_note?.text && unassigned ? <Text style={{ fontSize: 12, color: GOLD, fontStyle: 'italic' }} numberOfLines={1}>"{item.handoff_note.text}" - {firstName(item.handoff_note.by_name)}</Text> : null}
        </View>
        {unassigned ? <ClaimButton onPress={() => claim(item)} busy={claiming === item.id} testId={`inbox-row-claim-${item.id}`} /> : <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />}
      </TouchableOpacity>
    );
  };

  return (
    <View style={{ flex: 1 }} {...tid('shared-inbox-panel')}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ flexGrow: 0, flexShrink: 0 }} contentContainerStyle={{ paddingHorizontal: 12, paddingTop: 8, gap: 8 }}>
        <Chip label="All inboxes" active={inboxId === 'all'} onPress={() => setInboxId('all')} testId="inbox-chip-all" colors={colors} />
        {inboxes.map((i: any) => (
          <Chip key={i.id} label={i.name} count={i.counts?.open} color={i.color || GOLD} active={inboxId === i.id} onPress={() => setInboxId(i.id)} testId={`inbox-chip-${i.id}`} colors={colors} />
        ))}
      </ScrollView>
      <View style={{ flexDirection: 'row', gap: 8, paddingHorizontal: 12, paddingVertical: 8 }}>
        <Chip label="Everything" count={totals.open} active={view === 'all'} onPress={() => setView('all')} testId="inbox-view-all" colors={colors} />
        <Chip label="Up for grabs" count={totals.unassigned} active={view === 'unassigned'} onPress={() => setView('unassigned')} testId="inbox-view-unassigned" colors={colors} />
        <Chip label="Mine" count={totals.mine} active={view === 'mine'} onPress={() => setView('mine')} testId="inbox-view-mine" colors={colors} />
      </View>
      {loading ? <ActivityIndicator color={GOLD} style={{ marginTop: 40 }} /> : (
        <FlatList
          data={rows}
          keyExtractor={(r) => r.id}
          renderItem={renderRow}
          ItemSeparatorComponent={() => <View style={{ height: 1, backgroundColor: colors.border, marginLeft: 70 }} />}
          contentContainerStyle={{ paddingBottom: 100 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={async () => { setRefreshing(true); refreshInboxes(); await load(true); setRefreshing(false); }} tintColor={GOLD} />}
          ListEmptyComponent={() => (
            <View style={{ alignItems: 'center', paddingTop: 60, paddingHorizontal: 32, gap: 10 }} {...tid('shared-inbox-empty')}>
              <Ionicons name={view === 'unassigned' ? 'checkmark-done-circle' : 'chatbubbles'} size={44} color={GOLD} />
              <Text style={{ fontSize: 17, fontWeight: '800', color: colors.textPrimary }}>{view === 'unassigned' ? 'Nothing up for grabs' : view === 'mine' ? 'Nothing assigned to you here' : 'Quiet in here'}</Text>
              <Text style={{ fontSize: 13, color: colors.textSecondary, textAlign: 'center' }}>
                {view === 'unassigned' ? 'Every text to the shared number has an owner.' : 'Texts to the shared number land here for the whole team.'}
              </Text>
            </View>
          )}
        />
      )}
    </View>
  );
}
