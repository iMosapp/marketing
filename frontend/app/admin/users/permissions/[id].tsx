import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, ScrollView, ActivityIndicator, Switch } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import api from '../../../../services/api';
import { useAuthStore } from '../../../../store/authStore';
import { useThemeStore } from '../../../../store/themeStore';
import { showSimpleAlert } from '../../../../services/alert';

const SECTIONS = [
  {
    key: 'my_tools', title: 'My Tools', icon: 'apps', color: '#007AFF',
    items: [
      { key: 'touchpoints', label: "Today's Touchpoints", icon: 'checkbox-outline' },
      { key: 'ask_jessi', label: 'Ask Jessi', icon: 'sparkles' },
      { key: 'training_hub', label: 'Training Hub', icon: 'school' },
      { key: 'team_chat', label: 'Team Chat', icon: 'chatbox-ellipses' },
    ],
  },
  {
    key: 'campaigns', title: 'Campaigns', icon: 'rocket', color: '#FF2D55',
    items: [
      { key: 'campaign_builder', label: 'Campaign Builder', icon: 'chatbubbles' },
      { key: 'campaign_dashboard', label: 'Campaign Dashboard', icon: 'speedometer' },
      { key: 'broadcast', label: 'Broadcast', icon: 'megaphone' },
      { key: 'date_triggers', label: 'Date Triggers', icon: 'calendar-outline' },
    ],
  },
  {
    key: 'content', title: 'Content', icon: 'color-palette', color: '#AF52DE',
    items: [
      { key: 'sms_templates', label: 'SMS Templates', icon: 'document-text' },
      { key: 'email_templates', label: 'Email Templates', icon: 'mail-outline' },
      { key: 'card_templates', label: 'Card Templates', icon: 'color-palette-outline' },
      { key: 'manage_showcase', label: 'Manage Showcase', icon: 'images' },
    ],
  },
  {
    key: 'insights', title: 'Insights', icon: 'stats-chart', color: '#34C759',
    items: [
      { key: 'my_performance', label: 'My Performance', icon: 'stats-chart' },
      { key: 'activity_reports', label: 'Activity Reports', icon: 'bar-chart' },
      { key: 'email_analytics', label: 'Email Analytics', icon: 'bar-chart' },
      { key: 'leaderboard', label: 'Leaderboard', icon: 'podium' },
      { key: 'lead_attribution', label: 'Lead Attribution', icon: 'analytics' },
    ],
  },
];

export default function UserPermissionsScreen() {
  const { colors } = useThemeStore();
  const router = useRouter();
  const { id: userId } = useLocalSearchParams<{ id: string }>();
  const currentUser = useAuthStore((s) => s.user);

  const [perms, setPerms] = useState<any>(null);
  const [userName, setUserName] = useState('');
  const [userRole, setUserRole] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => { loadPerms(); }, [userId, currentUser?._id]);

  const loadPerms = async () => {
    if (!userId || !currentUser?._id) return;
    setLoading(true);
    try {
      const res = await api.get(`/admin/permissions/${userId}`, { headers: { 'X-User-ID': currentUser._id } });
      setPerms(res.data.permissions);
      setUserName(res.data.name || '');
      setUserRole(res.data.role || 'user');
    } catch (e: any) {
      showSimpleAlert('Error', e?.response?.data?.detail || 'Failed to load permissions');
    }
    setLoading(false);
  };

  const savePerms = async () => {
    if (!userId || !currentUser?._id || !perms) return;
    setSaving(true);
    try {
      await api.put(`/admin/permissions/${userId}`, { permissions: perms }, { headers: { 'X-User-ID': currentUser._id } });
      showSimpleAlert('Saved', 'Permissions updated successfully');
    } catch (e: any) {
      showSimpleAlert('Error', e?.response?.data?.detail || 'Failed to save');
    }
    setSaving(false);
  };

  const toggleSection = (sectionKey: string) => {
    setPerms((prev: any) => {
      const section = prev[sectionKey] || {};
      const newEnabled = !section._enabled;
      const updated = { ...section, _enabled: newEnabled };
      // When toggling section ON, don't auto-enable all items
      // When toggling section OFF, items keep their state but section is hidden
      return { ...prev, [sectionKey]: updated };
    });
  };

  const toggleItem = (sectionKey: string, itemKey: string) => {
    setPerms((prev: any) => {
      const section = prev[sectionKey] || {};
      return { ...prev, [sectionKey]: { ...section, [itemKey]: !section[itemKey] } };
    });
  };

  const enableAll = () => {
    const newPerms: any = {};
    SECTIONS.forEach(s => {
      const section: any = { _enabled: true };
      s.items.forEach(i => { section[i.key] = true; });
      newPerms[s.key] = section;
    });
    setPerms(newPerms);
  };

  const roleLabel = userRole === 'super_admin' ? 'Super Admin' : userRole === 'org_admin' ? 'Org Admin' : userRole === 'store_manager' ? 'Manager' : 'User';

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      {/* Header */}
      <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 0.5, borderBottomColor: colors.border }}>
        <TouchableOpacity onPress={() => router.back()} style={{ padding: 4, marginRight: 8 }} data-testid="perms-back-btn">
          <Ionicons name="chevron-back" size={24} color={colors.accent} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 19, fontWeight: '700', color: colors.text }}>Feature Permissions</Text>
          {userName ? <Text style={{ fontSize: 14, color: colors.textSecondary }}>{userName} ({roleLabel})</Text> : null}
        </View>
        <TouchableOpacity onPress={savePerms} disabled={saving} style={{ paddingHorizontal: 14, paddingVertical: 7, borderRadius: 8, backgroundColor: colors.accent }} data-testid="save-perms-btn">
          {saving ? <ActivityIndicator size="small" color="#000" /> : <Text style={{ fontSize: 16, fontWeight: '700', color: '#000' }}>Save</Text>}
        </TouchableOpacity>
      </View>

      {loading ? (
        <ActivityIndicator size="large" color={colors.accent} style={{ marginTop: 40 }} />
      ) : perms ? (
        <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingBottom: 40 }} showsVerticalScrollIndicator={false}>
          {/* Enable All shortcut */}
          <TouchableOpacity onPress={enableAll} style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 10 }} data-testid="enable-all-btn">
            <Ionicons name="toggle" size={18} color={colors.accent} />
            <Text style={{ fontSize: 15, fontWeight: '600', color: colors.accent }}>Enable All Features</Text>
          </TouchableOpacity>

          {SECTIONS.map(section => {
            const sectionPerms = perms[section.key] || {};
            const sectionEnabled = sectionPerms._enabled !== false;
            const enabledCount = section.items.filter(i => sectionPerms[i.key]).length;

            return (
              <View key={section.key} style={{ marginHorizontal: 16, marginBottom: 14 }}>
                {/* Section Header with Master Toggle */}
                <View style={{
                  flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: colors.card,
                  borderRadius: 14, borderBottomLeftRadius: sectionEnabled ? 0 : 14, borderBottomRightRadius: sectionEnabled ? 0 : 14,
                  padding: 14, paddingHorizontal: 16, borderWidth: 1, borderColor: colors.border,
                  borderBottomWidth: sectionEnabled ? 0 : 1,
                }}>
                  <View style={{ width: 36, height: 36, borderRadius: 10, backgroundColor: `${section.color}20`, alignItems: 'center', justifyContent: 'center' }}>
                    <Ionicons name={section.icon as any} size={18} color={section.color} />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={{ fontSize: 17, fontWeight: '700', color: colors.text }}>{section.title}</Text>
                    <Text style={{ fontSize: 13, color: colors.textSecondary }}>{enabledCount}/{section.items.length} features enabled</Text>
                  </View>
                  <Switch
                    value={sectionEnabled}
                    onValueChange={() => toggleSection(section.key)}
                    trackColor={{ false: '#3A3A3C', true: `${section.color}60` }}
                    thumbColor={sectionEnabled ? section.color : '#8E8E93'}
                  />
                </View>

                {/* Individual Items */}
                {sectionEnabled && (
                  <View style={{ backgroundColor: colors.card, borderRadius: 14, borderTopLeftRadius: 0, borderTopRightRadius: 0, borderWidth: 1, borderTopWidth: 0, borderColor: colors.border, overflow: 'hidden' }}>
                    {section.items.map((item, idx) => (
                      <View key={item.key} style={{
                        flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 12, paddingHorizontal: 16,
                        borderBottomWidth: idx < section.items.length - 1 ? 0.5 : 0, borderBottomColor: colors.border,
                      }}>
                        <Ionicons name={item.icon as any} size={18} color={sectionPerms[item.key] ? section.color : '#48484A'} />
                        <Text style={{ flex: 1, fontSize: 16, color: sectionPerms[item.key] ? colors.text : '#636366' }}>{item.label}</Text>
                        <Switch
                          value={!!sectionPerms[item.key]}
                          onValueChange={() => toggleItem(section.key, item.key)}
                          trackColor={{ false: '#3A3A3C', true: `${section.color}60` }}
                          thumbColor={sectionPerms[item.key] ? section.color : '#8E8E93'}
                        />
                      </View>
                    ))}
                  </View>
                )}
              </View>
            );
          })}

          <Text style={{ fontSize: 14, color: '#48484A', textAlign: 'center', paddingHorizontal: 32, paddingTop: 8 }}>
            Admin section is always visible for admin/manager roles and cannot be toggled here.
          </Text>
        </ScrollView>
      ) : null}
    </SafeAreaView>
  );
}
