import React, { useCallback, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import api from '../../../services/api';
import { useThemeStore } from '../../../store/themeStore';
import { useToast } from '../../../components/common/Toast';
import { ScreenHeader } from '../../../components/common/ScreenHeader';
import { GOLD, tid, errText, timeAgo } from '../../../components/inbox/ownership';

const Door = ({ on, label, colors }: { on: boolean; label: string; colors: any }) => (
  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
    <Ionicons name={on ? 'checkmark-circle' : 'close-circle'} size={14} color={on ? '#34C759' : colors.textTertiary || colors.textSecondary} />
    <Text style={{ fontSize: 12, color: colors.textSecondary }}>{label}</Text>
  </View>
);

export default function WebsiteWidgets() {
  const router = useRouter();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [data, setData] = useState<any>(null);
  const [creating, setCreating] = useState<string | null>(null);

  const load = useCallback(async () => {
    try { setData((await api.get('/widgets')).data); }
    catch (e) { showToast(errText(e, "Couldn't load widgets"), 'error'); }
  }, []);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const create = async (storeId: string) => {
    setCreating(storeId);
    try {
      const res = await api.post('/widgets', { store_id: storeId });
      showToast(res.data.existing ? 'That store already has a widget' : 'Widget created. Pick your color, then copy the install code.', 'success', 3500);
      router.push(`/admin/website-widget/${res.data.widget.id}` as any);
    } catch (e: any) { showToast(errText(e, 'Could not create the widget'), 'error', 3500); }
    finally { setCreating(null); }
  };

  const widgets: any[] = data?.widgets || [];
  const free: any[] = (data?.stores || []).filter((s: any) => !s.has_widget);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="Website Widget" subtitle="Text Us and Call Me Now on your own site" testID="widgets-header" />
      {!data ? <ActivityIndicator style={{ marginTop: 60 }} color={GOLD} /> : (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 80, gap: 14 }}>
          {widgets.length === 0 && (
            <View style={{ alignItems: 'center', paddingVertical: 30, paddingHorizontal: 20, gap: 12 }} {...tid('widgets-empty')}>
              <View style={{ width: 72, height: 72, borderRadius: 36, backgroundColor: GOLD + '22', alignItems: 'center', justifyContent: 'center' }}>
                <Ionicons name="chatbubble-ellipses" size={34} color={GOLD} />
              </View>
              <Text style={{ fontSize: 18, fontWeight: '800', color: colors.text, textAlign: 'center' }}>One line of code, real people answer</Text>
              <Text style={{ fontSize: 14, color: colors.textSecondary, textAlign: 'center', lineHeight: 20 }}>
                A bubble in the corner of your website. Visitors tap Text Us and land in your Inbox, or Call Me Now and every rep's phone rings at once; the first to press 1 is talking to them in seconds. Match the color to your site, copy one line, done.
              </Text>
            </View>
          )}
          {widgets.map(w => (
            <TouchableOpacity key={w.id} onPress={() => router.push(`/admin/website-widget/${w.id}` as any)} activeOpacity={0.8}
              style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 14, gap: 10, borderLeftWidth: 4, borderLeftColor: w.appearance?.bubble_color || GOLD }} {...tid(`widget-card-${w.id}`)}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
                <View style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: w.appearance?.bubble_color || GOLD, alignItems: 'center', justifyContent: 'center' }}>
                  <Ionicons name="chatbubble-ellipses" size={20} color={w.appearance?.text_color || '#fff'} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 17, fontWeight: '800', color: colors.text }}>{w.store_name || w.name}</Text>
                  <Text style={{ fontSize: 13, color: w.installed ? '#34C759' : '#FF9500', marginTop: 1 }}>{w.installed ? `Live on ${w.last_seen_host} · seen ${timeAgo(w.last_seen_at)}` : 'Not installed yet · copy the code'}</Text>
                </View>
                <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
              </View>
              <View style={{ flexDirection: 'row', gap: 14, flexWrap: 'wrap' }}>
                <Door on={!!w.doors?.text?.on} label="Text us" colors={colors} />
                <Door on={!!w.doors?.call?.on} label="Call me now" colors={colors} />
                <Text style={{ fontSize: 12, color: colors.textSecondary }}>· {(w.routing?.call_user_ids || []).length} in the ring group · {w.stats?.text_leads || 0} texts · {w.stats?.call_requests || 0} calls</Text>
              </View>
            </TouchableOpacity>
          ))}
          {data.can_manage && free.length > 0 && (
            <View style={{ gap: 8 }} {...tid('widgets-create-list')}>
              {widgets.length > 0 ? <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1, marginTop: 6 }}>STORES WITHOUT A WIDGET</Text> : null}
              {free.map((s: any) => (
                <TouchableOpacity key={s.id} onPress={() => create(s.id)} disabled={!!creating} style={{ minHeight: 52, paddingVertical: 12, paddingHorizontal: 18, borderRadius: 14, backgroundColor: widgets.length === 0 && free.length === 1 ? GOLD : colors.card, borderWidth: 1, borderColor: widgets.length === 0 && free.length === 1 ? GOLD : colors.border, alignItems: 'center', flexDirection: 'row', gap: 10 }} {...tid(`widget-create-${s.id}`)}>
                  {creating === s.id ? <ActivityIndicator color={widgets.length === 0 && free.length === 1 ? '#111' : GOLD} /> : <Ionicons name="add" size={20} color={widgets.length === 0 && free.length === 1 ? '#111' : GOLD} />}
                  <Text style={{ flex: 1, fontSize: 15, fontWeight: '800', color: widgets.length === 0 && free.length === 1 ? '#111' : colors.text }} numberOfLines={2}>Create the widget for {s.name}</Text>
                </TouchableOpacity>
              ))}
            </View>
          )}
          {data.can_manage && free.length === 0 && widgets.length === 0 && (
            <Text style={{ fontSize: 13, color: colors.textSecondary, textAlign: 'center' }} {...tid('widgets-no-store')}>Your account is not linked to a store yet, so there is nothing to attach a widget to.</Text>
          )}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}
