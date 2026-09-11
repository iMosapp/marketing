import React, { useCallback, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, RefreshControl } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { useThemeStore } from '../../store/themeStore';
import { useToast } from '../../components/common/Toast';
import { ScreenHeader, HeaderTextButton } from '../../components/common/ScreenHeader';
import { Avatar } from '../../components/Avatar';
import { GOLD, tid, ownershipAPI, errText, fmtPhone } from '../../components/inbox/ownership';
import { routingLabel, aiModeLabel } from '../../components/inbox/InboxEditorParts';

const Stat = ({ n, label, colors, hot }: { n: number; label: string; colors: any; hot?: boolean }) => (
  <View style={{ flex: 1, alignItems: 'center', paddingVertical: 8, borderRadius: 10, backgroundColor: hot && n > 0 ? GOLD + '22' : colors.surface }}>
    <Text style={{ fontSize: 17, fontWeight: '800', color: hot && n > 0 ? GOLD : colors.text }}>{n}</Text>
    <Text style={{ fontSize: 11, color: colors.textSecondary, fontWeight: '600' }}>{label}</Text>
  </View>
);

export default function InboxesLibrary() {
  const router = useRouter();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [data, setData] = useState<any>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try { setData(await ownershipAPI.listInboxes()); }
    catch (e) { showToast(errText(e, "Couldn't load inboxes"), 'error'); }
  }, []);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const inboxes: any[] = data?.inboxes || [];
  const canCreate = !!data?.can_create;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="Inboxes" subtitle="Shared numbers your team works together" testID="inboxes-header"
        right={canCreate ? <HeaderTextButton label="New" onPress={() => router.push('/inboxes/new' as any)} testID="inboxes-new-btn" color={GOLD} /> : undefined} />
      {!data ? <ActivityIndicator style={{ marginTop: 60 }} color={GOLD} /> : (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 80, gap: 14 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={async () => { setRefreshing(true); await load(); setRefreshing(false); }} tintColor={GOLD} />}>
          {inboxes.length === 0 && (
            <View style={{ alignItems: 'center', paddingVertical: 50, paddingHorizontal: 24, gap: 12 }} {...tid('inboxes-empty')}>
              <View style={{ width: 72, height: 72, borderRadius: 36, backgroundColor: GOLD + '22', alignItems: 'center', justifyContent: 'center' }}>
                <Ionicons name="chatbubbles" size={34} color={GOLD} />
              </View>
              <Text style={{ fontSize: 18, fontWeight: '800', color: colors.text, textAlign: 'center' }}>One number, the whole team</Text>
              <Text style={{ fontSize: 14, color: colors.textSecondary, textAlign: 'center', lineHeight: 20 }}>
                A shared inbox is a department line (Sales, Service, Parts) that several reps work at once. Texts come in, Jessi holds the fort, the first rep to claim owns the customer, and when it's sold the thread moves to that rep's own number.
              </Text>
              {canCreate && (
                <TouchableOpacity onPress={() => router.push('/inboxes/new' as any)} style={{ marginTop: 8, height: 50, paddingHorizontal: 24, borderRadius: 14, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8 }} {...tid('inboxes-empty-new')}>
                  <Ionicons name="add" size={20} color="#111" />
                  <Text style={{ fontSize: 15, fontWeight: '800', color: '#111' }}>Create your first inbox</Text>
                </TouchableOpacity>
              )}
            </View>
          )}
          {inboxes.map(ib => (
            <TouchableOpacity key={ib.id} onPress={() => router.push(`/inboxes/${ib.id}` as any)} activeOpacity={0.8}
              style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 14, gap: 12, borderLeftWidth: 4, borderLeftColor: ib.color || GOLD }} {...tid(`inbox-card-${ib.id}`)}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
                <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: (ib.color || GOLD) + '22', alignItems: 'center', justifyContent: 'center' }}>
                  <Ionicons name={(ib.icon || 'chatbubbles') as any} size={20} color={ib.color || GOLD} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 17, fontWeight: '800', color: colors.text }}>{ib.name}</Text>
                  <Text style={{ fontSize: 13, color: ib.phone_number ? colors.textSecondary : '#FF9500', marginTop: 1 }}>{ib.phone_number ? fmtPhone(ib.phone_number) : 'No number yet · texts can\'t land here'}</Text>
                </View>
                {ib.can_manage ? <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} /> : null}
              </View>
              <View style={{ flexDirection: 'row', gap: 8 }}>
                <Stat n={ib.counts?.unassigned || 0} label="Up for grabs" colors={colors} hot />
                <Stat n={ib.counts?.mine || 0} label="Mine" colors={colors} />
                <Stat n={ib.counts?.open || 0} label="Open" colors={colors} />
              </View>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                <View style={{ flexDirection: 'row' }}>
                  {(ib.member_details || []).slice(0, 5).map((m: any, i: number) => (
                    <View key={m.id} style={{ marginLeft: i === 0 ? 0 : -8, borderWidth: 2, borderColor: colors.card, borderRadius: 16 }}>
                      <Avatar photo={m.photo || null} name={m.name} size="sm" />
                    </View>
                  ))}
                </View>
                <Text style={{ flex: 1, fontSize: 12, color: colors.textSecondary }} numberOfLines={2}>
                  {ib.members.length} on it · {routingLabel(ib.routing)} · {ib.ai_mode === 'off' ? 'Humans only' : aiModeLabel(ib.ai_mode).replace('Jessi answers until someone claims', 'Jessi answers first')} · Sold {ib.after_close === 'stay' ? 'stays here' : "moves to the rep's line"}
                </Text>
              </View>
            </TouchableOpacity>
          ))}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}
