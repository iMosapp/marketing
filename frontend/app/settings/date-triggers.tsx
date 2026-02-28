import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  Switch,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';
import { showSimpleAlert } from '../../services/alert';

type TriggerType = 'birthday' | 'anniversary' | 'sold_date';

const DATE_TRIGGERS: { type: TriggerType; label: string; icon: string; defaultMsg: string }[] = [
  {
    type: 'birthday',
    label: 'Birthday',
    icon: 'gift-outline',
    defaultMsg: 'Happy Birthday, {first_name}! Wishing you an amazing day!',
  },
  {
    type: 'anniversary',
    label: 'Anniversary',
    icon: 'heart-outline',
    defaultMsg: 'Happy Anniversary, {first_name}! Wishing you many more wonderful years!',
  },
  {
    type: 'sold_date',
    label: 'Sold Date',
    icon: 'car-outline',
    defaultMsg: 'Hey {first_name}, it\'s been another year since your purchase! Hope you\'re still loving it. Let me know if you need anything!',
  },
];

const DELIVERY_OPTIONS = [
  { value: 'sms', label: 'SMS' },
  { value: 'email', label: 'Email' },
  { value: 'both', label: 'Both' },
];

export default function DateTriggersScreen() {
  const router = useRouter();
  const user = useAuthStore((state) => state.user);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [configs, setConfigs] = useState<Record<string, any>>({});
  const [holidays, setHolidays] = useState<any[]>([]);
  const [holidayConfigs, setHolidayConfigs] = useState<Record<string, any>>({});
  const [holidayTemplate, setHolidayTemplate] = useState('Happy {holiday_name}, {first_name}! Wishing you and yours a wonderful day!');
  const [holidayDelivery, setHolidayDelivery] = useState('sms');
  const [activeTab, setActiveTab] = useState<'dates' | 'holidays'>('dates');

  useFocusEffect(
    useCallback(() => {
      loadData();
    }, [user?._id])
  );

  const loadData = async () => {
    if (!user?._id) return;
    try {
      setLoading(true);
      const [configRes, holidayRes] = await Promise.all([
        api.get(`/date-triggers/${user._id}/config`),
        api.get('/date-triggers/holidays'),
      ]);

      // Build config map
      const cfgMap: Record<string, any> = {};
      for (const c of configRes.data || []) {
        cfgMap[c.trigger_type] = c;
      }
      setConfigs(cfgMap);

      // Build holiday config map
      const hMap: Record<string, any> = {};
      for (const c of configRes.data || []) {
        if (c.trigger_type?.startsWith('holiday_')) {
          const hId = c.holiday_id || c.trigger_type.replace('holiday_', '');
          hMap[hId] = c;
          if (c.message_template) setHolidayTemplate(c.message_template);
          if (c.delivery_method) setHolidayDelivery(c.delivery_method);
        }
      }
      setHolidayConfigs(hMap);
      setHolidays(holidayRes.data || []);
    } catch (error) {
      console.error('Failed to load date trigger data:', error);
    } finally {
      setLoading(false);
    }
  };

  const toggleTrigger = async (type: string, enabled: boolean) => {
    const current = configs[type] || {};
    const trigger = DATE_TRIGGERS.find(t => t.type === type);
    const newConfig: any = {
      trigger_type: type,
      enabled,
      delivery_method: current.delivery_method || 'sms',
      message_template: current.message_template || trigger?.defaultMsg || '',
    };
    if (type === 'birthday') {
      newConfig.include_birthday_card = current.include_birthday_card ?? true;
    }

    setConfigs(prev => ({ ...prev, [type]: { ...prev[type], ...newConfig } }));

    try {
      await api.put(`/date-triggers/${user?._id}/config/${type}`, newConfig);
    } catch (error) {
      console.error('Failed to save trigger config:', error);
      showSimpleAlert('Error', 'Failed to save');
    }
  };

  const updateTriggerField = (type: string, field: string, value: any) => {
    setConfigs(prev => ({
      ...prev,
      [type]: { ...prev[type], trigger_type: type, [field]: value }
    }));
  };

  const saveTriggerConfig = async (type: string) => {
    const current = configs[type];
    if (!current) return;

    const trigger = DATE_TRIGGERS.find(t => t.type === type);
    const payload = {
      trigger_type: type,
      enabled: current.enabled ?? true,
      delivery_method: current.delivery_method || 'sms',
      message_template: current.message_template || trigger?.defaultMsg || '',
    };

    setSaving(true);
    try {
      await api.put(`/date-triggers/${user?._id}/config/${type}`, payload);
      showSimpleAlert('Saved', `${trigger?.label} trigger updated`);
    } catch (error) {
      showSimpleAlert('Error', 'Failed to save configuration');
    } finally {
      setSaving(false);
    }
  };

  const toggleHoliday = (holidayId: string) => {
    setHolidayConfigs(prev => {
      const current = prev[holidayId];
      if (current) {
        const { [holidayId]: _, ...rest } = prev;
        return rest;
      }
      return { ...prev, [holidayId]: { enabled: true } };
    });
  };

  const saveHolidays = async () => {
    setSaving(true);
    try {
      const holidayList = holidays.map(h => ({
        id: h.id,
        enabled: !!holidayConfigs[h.id],
        delivery_method: holidayDelivery,
        message_template: holidayTemplate,
      }));
      await api.put(`/date-triggers/${user?._id}/holidays`, holidayList);
      showSimpleAlert('Saved', `${Object.keys(holidayConfigs).length} holidays activated`);
    } catch (error) {
      showSimpleAlert('Error', 'Failed to save holiday config');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
            <Ionicons name="chevron-back" size={28} color="#007AFF" />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Date Triggers</Text>
          <View style={{ width: 40 }} />
        </View>
        <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
          <ActivityIndicator size="large" color="#C9A962" />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Date Triggers</Text>
        <View style={{ width: 40 }} />
      </View>

      {/* Tabs */}
      <View style={styles.tabs}>
        <TouchableOpacity
          style={[styles.tab, activeTab === 'dates' && styles.tabActive]}
          onPress={() => setActiveTab('dates')}
        >
          <Text style={[styles.tabText, activeTab === 'dates' && styles.tabTextActive]}>Dates</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tab, activeTab === 'holidays' && styles.tabActive]}
          onPress={() => setActiveTab('holidays')}
        >
          <Text style={[styles.tabText, activeTab === 'holidays' && styles.tabTextActive]}>Holidays</Text>
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        {activeTab === 'dates' ? (
          <>
            <Text style={styles.sectionDescription}>
              Contacts with these dates will automatically receive your message every year at 10 AM. Tags are auto-applied when dates are saved.
            </Text>

            {DATE_TRIGGERS.map((trigger) => {
              const config = configs[trigger.type] || {};
              const isEnabled = config.enabled ?? false;

              return (
                <View key={trigger.type} style={styles.triggerCard}>
                  <View style={styles.triggerHeader}>
                    <View style={styles.triggerTitleRow}>
                      <Ionicons name={trigger.icon as any} size={22} color="#C9A962" />
                      <Text style={styles.triggerTitle}>{trigger.label}</Text>
                    </View>
                    <Switch
                      value={isEnabled}
                      onValueChange={(val) => toggleTrigger(trigger.type, val)}
                      trackColor={{ false: '#3A3A3C', true: '#34C75966' }}
                      thumbColor={isEnabled ? '#34C759' : '#8E8E93'}
                    />
                  </View>

                  {isEnabled && (
                    <View style={styles.triggerBody}>
                      <Text style={styles.fieldLabel}>Delivery Method</Text>
                      <View style={styles.deliveryRow}>
                        {DELIVERY_OPTIONS.map((opt) => (
                          <TouchableOpacity
                            key={opt.value}
                            style={[
                              styles.deliveryOption,
                              (config.delivery_method || 'sms') === opt.value && styles.deliveryActive,
                            ]}
                            onPress={() => updateTriggerField(trigger.type, 'delivery_method', opt.value)}
                          >
                            <Text style={[
                              styles.deliveryText,
                              (config.delivery_method || 'sms') === opt.value && styles.deliveryTextActive,
                            ]}>{opt.label}</Text>
                          </TouchableOpacity>
                        ))}
                      </View>

                      <Text style={styles.fieldLabel}>Message Template</Text>
                      <Text style={styles.fieldHint}>Use {'{first_name}'}, {'{last_name}'}, {'{name}'}</Text>
                      <TextInput
                        style={styles.templateInput}
                        value={config.message_template || trigger.defaultMsg}
                        onChangeText={(text) => updateTriggerField(trigger.type, 'message_template', text)}
                        multiline
                        placeholderTextColor="#6E6E73"
                      />

                      <TouchableOpacity
                        style={[styles.saveBtn, saving && { opacity: 0.6 }]}
                        onPress={() => saveTriggerConfig(trigger.type)}
                        disabled={saving}
                      >
                        <Text style={styles.saveBtnText}>Save {trigger.label} Trigger</Text>
                      </TouchableOpacity>
                    </View>
                  )}
                </View>
              );
            })}
          </>
        ) : (
          <>
            <Text style={styles.sectionDescription}>
              Contacts tagged "Holiday" or "Holidays" will receive your message on selected holidays. Pick the ones you want to send on.
            </Text>

            {/* Holiday message template */}
            <View style={styles.triggerCard}>
              <Text style={styles.fieldLabel}>Holiday Message Template</Text>
              <Text style={styles.fieldHint}>Use {'{first_name}'}, {'{holiday_name}'}</Text>
              <TextInput
                style={styles.templateInput}
                value={holidayTemplate}
                onChangeText={setHolidayTemplate}
                multiline
                placeholderTextColor="#6E6E73"
              />
              <Text style={[styles.fieldLabel, { marginTop: 12 }]}>Delivery Method</Text>
              <View style={styles.deliveryRow}>
                {DELIVERY_OPTIONS.map((opt) => (
                  <TouchableOpacity
                    key={opt.value}
                    style={[styles.deliveryOption, holidayDelivery === opt.value && styles.deliveryActive]}
                    onPress={() => setHolidayDelivery(opt.value)}
                  >
                    <Text style={[styles.deliveryText, holidayDelivery === opt.value && styles.deliveryTextActive]}>
                      {opt.label}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>

            {/* Holiday list */}
            <View style={styles.triggerCard}>
              <Text style={styles.triggerTitle}>Select Holidays</Text>
              {holidays.map((holiday) => {
                const isSelected = !!holidayConfigs[holiday.id];
                return (
                  <TouchableOpacity
                    key={holiday.id}
                    style={styles.holidayRow}
                    onPress={() => toggleHoliday(holiday.id)}
                  >
                    <Ionicons
                      name={isSelected ? 'checkmark-circle' : 'ellipse-outline'}
                      size={24}
                      color={isSelected ? '#34C759' : '#6E6E73'}
                    />
                    <Text style={styles.holidayName}>{holiday.name}</Text>
                    <Text style={styles.holidayDate}>
                      {holiday.month}/{holiday.day}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>

            <TouchableOpacity
              style={[styles.saveBtn, { marginTop: 8 }, saving && { opacity: 0.6 }]}
              onPress={saveHolidays}
              disabled={saving}
            >
              {saving ? (
                <ActivityIndicator size="small" color="#000" />
              ) : (
                <Text style={styles.saveBtnText}>Save Holiday Settings</Text>
              )}
            </TouchableOpacity>
          </>
        )}

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingVertical: 12,
    borderBottomWidth: 1, borderBottomColor: '#1C1C1E',
  },
  backButton: { padding: 4 },
  headerTitle: { fontSize: 17, fontWeight: '600', color: '#FFF' },
  tabs: {
    flexDirection: 'row', paddingHorizontal: 16, paddingTop: 12, gap: 8,
  },
  tab: {
    flex: 1, paddingVertical: 10, alignItems: 'center',
    borderRadius: 10, backgroundColor: '#1C1C1E',
  },
  tabActive: { backgroundColor: '#C9A962' },
  tabText: { fontSize: 15, fontWeight: '600', color: '#8E8E93' },
  tabTextActive: { color: '#000' },
  content: { padding: 16 },
  sectionDescription: {
    fontSize: 14, color: '#8E8E93', marginBottom: 16, lineHeight: 20,
  },
  triggerCard: {
    backgroundColor: '#1C1C1E', borderRadius: 12, padding: 16, marginBottom: 12,
  },
  triggerHeader: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
  },
  triggerTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  triggerTitle: { fontSize: 16, fontWeight: '600', color: '#FFF' },
  triggerBody: { marginTop: 16 },
  fieldLabel: { fontSize: 14, fontWeight: '500', color: '#FFF', marginBottom: 8 },
  fieldHint: { fontSize: 12, color: '#6E6E73', marginBottom: 8 },
  deliveryRow: { flexDirection: 'row', gap: 8, marginBottom: 16 },
  deliveryOption: {
    flex: 1, paddingVertical: 10, alignItems: 'center',
    borderRadius: 8, backgroundColor: '#2C2C2E',
  },
  deliveryActive: { backgroundColor: '#C9A962' },
  deliveryText: { fontSize: 14, fontWeight: '500', color: '#8E8E93' },
  deliveryTextActive: { color: '#000' },
  templateInput: {
    backgroundColor: '#2C2C2E', borderRadius: 10, padding: 14,
    color: '#FFF', fontSize: 15, minHeight: 80, textAlignVertical: 'top',
  },
  saveBtn: {
    backgroundColor: '#C9A962', paddingVertical: 14, borderRadius: 20,
    alignItems: 'center', marginTop: 16,
  },
  saveBtnText: { color: '#000', fontSize: 15, fontWeight: '600' },
  holidayRow: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: '#2C2C2E',
  },
  holidayName: { flex: 1, fontSize: 15, color: '#FFF' },
  holidayDate: { fontSize: 13, color: '#8E8E93' },
});
