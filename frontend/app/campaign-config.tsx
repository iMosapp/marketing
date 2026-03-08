import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, TouchableOpacity, ScrollView, StyleSheet, Switch, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import api from '../services/api';
import { useAuthStore } from '../store/authStore';

interface CampaignConfig {
  message_mode: 'ai_suggested' | 'template' | 'hybrid';
  sequence_mode: 'preset_timing' | 'ai_full';
  auto_enroll_on_tag: boolean;
  review_before_send: boolean;
  auto_send: boolean;
  default_channel: string;
  ai_tone: string;
  include_personal_details: boolean;
  include_engagement_signals: boolean;
  allow_user_override?: boolean;
}

const modeDescriptions = {
  ai_suggested: 'AI crafts every message using relationship intelligence, voice memos, and engagement data. Each touchpoint is unique and personal.',
  template: 'Use your pre-written message templates exactly as-is. Consistent and predictable.',
  hybrid: 'Each campaign step chooses: AI generates where marked, templates where not. Best of both worlds.',
};

const toneDescriptions = {
  casual: 'Friendly, conversational — like texting a friend',
  warm: 'Personal and caring — shows genuine interest',
  professional: 'Polished but approachable — still human',
};

export default function CampaignConfigPage() {
  const user = useAuthStore((s: any) => s.user);
  const router = useRouter();
  const [config, setConfig] = useState<CampaignConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [storeId, setStoreId] = useState('');
  const [level, setLevel] = useState('store');

  const load = useCallback(async () => {
    if (!user?._id) return;
    setLoading(true);
    try {
      const res = await api.get(`/campaign-config/effective/${user._id}`);
      setConfig(res.data.config);
      setStoreId(res.data.store_id || '');
    } catch (e) {
      console.error('Config load failed:', e);
    }
    setLoading(false);
  }, [user?._id]);

  useEffect(() => { load(); }, [load]);

  const updateField = (key: keyof CampaignConfig, value: any) => {
    if (!config) return;
    setConfig({ ...config, [key]: value });
    setDirty(true);
  };

  const save = async () => {
    if (!config) return;
    setSaving(true);
    try {
      const entityId = level === 'store' ? storeId : user?._id;
      await api.put(`/campaign-config/${level}/${entityId}`, { config });
      setDirty(false);
    } catch (e) {
      console.error('Save failed:', e);
    }
    setSaving(false);
  };

  if (loading || !config) {
    return (
      <View style={st.container}>
        <ActivityIndicator size="large" color="#C9A962" style={{ marginTop: 100 }} />
      </View>
    );
  }

  return (
    <ScrollView style={st.container}>
      {/* Header */}
      <View style={st.header} data-testid="campaign-config-header">
        <TouchableOpacity onPress={() => router.back()} style={st.backBtn} data-testid="campaign-config-back-btn">
          <Ionicons name="arrow-back" size={24} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={st.title}>Campaign Settings</Text>
          <Text style={st.subtitle}>How your follow-up campaigns work</Text>
        </View>
        {dirty && (
          <TouchableOpacity style={st.saveBtn} onPress={save} disabled={saving} data-testid="save-config-btn">
            {saving ? <ActivityIndicator size="small" color="#000" /> : (
              <>
                <Ionicons name="checkmark" size={16} color="#000" />
                <Text style={st.saveBtnText}>Save</Text>
              </>
            )}
          </TouchableOpacity>
        )}
      </View>

      {/* Level selector */}
      <View style={st.levelRow} data-testid="config-level-selector">
        <Text style={st.levelLabel}>Configuring for:</Text>
        <View style={st.levelBtns}>
          <TouchableOpacity
            style={[st.levelBtn, level === 'store' && st.levelBtnActive]}
            onPress={() => setLevel('store')}
            data-testid="level-store-btn"
          >
            <Text style={[st.levelBtnText, level === 'store' && st.levelBtnTextActive]}>Store</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[st.levelBtn, level === 'user' && st.levelBtnActive]}
            onPress={() => setLevel('user')}
            data-testid="level-user-btn"
          >
            <Text style={[st.levelBtnText, level === 'user' && st.levelBtnTextActive]}>My Override</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Message Mode */}
      <View style={st.section} data-testid="message-mode-section">
        <Text style={st.sectionTitle}>Message Generation</Text>
        <Text style={st.sectionSubtitle}>How campaign messages are created</Text>
        {(['ai_suggested', 'template', 'hybrid'] as const).map((mode) => (
          <TouchableOpacity
            key={mode}
            style={[st.optionCard, config.message_mode === mode && st.optionCardActive]}
            onPress={() => updateField('message_mode', mode)}
            data-testid={`mode-${mode}`}
          >
            <View style={st.optionHeader}>
              <View style={[st.radioOuter, config.message_mode === mode && st.radioOuterActive]}>
                {config.message_mode === mode && <View style={st.radioInner} />}
              </View>
              <View style={{ flex: 1 }}>
                <Text style={[st.optionTitle, config.message_mode === mode && st.optionTitleActive]}>
                  {mode === 'ai_suggested' ? 'AI-Powered' : mode === 'template' ? 'Templates Only' : 'Hybrid'}
                </Text>
                <Text style={st.optionDesc}>{modeDescriptions[mode]}</Text>
              </View>
              {mode === 'ai_suggested' && <Ionicons name="sparkles" size={18} color={config.message_mode === mode ? '#C9A962' : '#555'} />}
            </View>
          </TouchableOpacity>
        ))}
      </View>

      {/* AI Tone */}
      {config.message_mode !== 'template' && (
        <View style={st.section} data-testid="ai-tone-section">
          <Text style={st.sectionTitle}>AI Tone</Text>
          <Text style={st.sectionSubtitle}>How AI messages should sound</Text>
          {(['casual', 'warm', 'professional'] as const).map((tone) => (
            <TouchableOpacity
              key={tone}
              style={[st.optionCard, config.ai_tone === tone && st.optionCardActive]}
              onPress={() => updateField('ai_tone', tone)}
              data-testid={`tone-${tone}`}
            >
              <View style={st.optionHeader}>
                <View style={[st.radioOuter, config.ai_tone === tone && st.radioOuterActive]}>
                  {config.ai_tone === tone && <View style={st.radioInner} />}
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={[st.optionTitle, config.ai_tone === tone && st.optionTitleActive]}>
                    {tone.charAt(0).toUpperCase() + tone.slice(1)}
                  </Text>
                  <Text style={st.optionDesc}>{toneDescriptions[tone]}</Text>
                </View>
              </View>
            </TouchableOpacity>
          ))}
        </View>
      )}

      {/* AI Data Sources */}
      {config.message_mode !== 'template' && (
        <View style={st.section} data-testid="ai-data-section">
          <Text style={st.sectionTitle}>AI Data Sources</Text>
          <Text style={st.sectionSubtitle}>What data powers AI message generation</Text>
          <View style={st.toggleRow}>
            <View style={{ flex: 1 }}>
              <Text style={st.toggleLabel}>Voice Memo Intelligence</Text>
              <Text style={st.toggleDesc}>Use personal details from voice memos (spouse, kids, interests, vehicle)</Text>
            </View>
            <Switch
              value={config.include_personal_details}
              onValueChange={(v) => updateField('include_personal_details', v)}
              trackColor={{ false: '#333', true: 'rgba(201,169,98,0.4)' }}
              thumbColor={config.include_personal_details ? '#C9A962' : '#666'}
            />
          </View>
          <View style={st.toggleRow}>
            <View style={{ flex: 1 }}>
              <Text style={st.toggleLabel}>Engagement Signals</Text>
              <Text style={st.toggleDesc}>Use card views, link clicks, return visits to personalize messages</Text>
            </View>
            <Switch
              value={config.include_engagement_signals}
              onValueChange={(v) => updateField('include_engagement_signals', v)}
              trackColor={{ false: '#333', true: 'rgba(201,169,98,0.4)' }}
              thumbColor={config.include_engagement_signals ? '#C9A962' : '#666'}
            />
          </View>
        </View>
      )}

      {/* Delivery Settings */}
      <View style={st.section} data-testid="delivery-section">
        <Text style={st.sectionTitle}>Delivery</Text>
        <Text style={st.sectionSubtitle}>How messages get delivered</Text>
        <View style={st.toggleRow}>
          <View style={{ flex: 1 }}>
            <Text style={st.toggleLabel}>Review Before Sending</Text>
            <Text style={st.toggleDesc}>Salesperson reviews and manually approves each message</Text>
          </View>
          <Switch
            value={config.review_before_send}
            onValueChange={(v) => updateField('review_before_send', v)}
            trackColor={{ false: '#333', true: 'rgba(52,199,89,0.4)' }}
            thumbColor={config.review_before_send ? '#34C759' : '#666'}
          />
        </View>
        <View style={st.toggleRow}>
          <View style={{ flex: 1 }}>
            <Text style={st.toggleLabel}>Auto-Send</Text>
            <Text style={[st.toggleDesc, !config.auto_send && { color: '#FF9500' }]}>
              {config.auto_send ? 'Messages send automatically (requires messaging provider)' : 'Coming soon — requires Twilio or messaging provider integration'}
            </Text>
          </View>
          <Switch
            value={config.auto_send}
            onValueChange={(v) => updateField('auto_send', v)}
            trackColor={{ false: '#333', true: 'rgba(52,199,89,0.4)' }}
            thumbColor={config.auto_send ? '#34C759' : '#666'}
            disabled={true}
          />
        </View>
        <View style={st.toggleRow}>
          <View style={{ flex: 1 }}>
            <Text style={st.toggleLabel}>Auto-Enroll on Tag</Text>
            <Text style={st.toggleDesc}>When a tag is applied (e.g., "Sold"), automatically enroll in matching campaigns</Text>
          </View>
          <Switch
            value={config.auto_enroll_on_tag}
            onValueChange={(v) => updateField('auto_enroll_on_tag', v)}
            trackColor={{ false: '#333', true: 'rgba(201,169,98,0.4)' }}
            thumbColor={config.auto_enroll_on_tag ? '#C9A962' : '#666'}
          />
        </View>
      </View>

      <View style={{ height: 100 }} />
    </ScrollView>
  );
}

const st = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  header: { flexDirection: 'row', alignItems: 'center', padding: 20, paddingTop: 60, gap: 12 },
  backBtn: { width: 40, height: 40, borderRadius: 20, backgroundColor: 'rgba(255,255,255,0.1)', justifyContent: 'center', alignItems: 'center' },
  title: { color: '#FFF', fontSize: 22, fontWeight: '700' },
  subtitle: { color: '#8E8E93', fontSize: 13, marginTop: 2 },
  saveBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#C9A962', paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8 },
  saveBtnText: { color: '#000', fontSize: 13, fontWeight: '700' },
  levelRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginHorizontal: 16, marginBottom: 16, padding: 12, backgroundColor: '#111', borderRadius: 10, borderWidth: 1, borderColor: '#222' },
  levelLabel: { color: '#8E8E93', fontSize: 13 },
  levelBtns: { flexDirection: 'row', gap: 4, backgroundColor: '#1A1A1A', borderRadius: 8, padding: 2 },
  levelBtn: { paddingVertical: 6, paddingHorizontal: 12, borderRadius: 6 },
  levelBtnActive: { backgroundColor: '#333' },
  levelBtnText: { color: '#666', fontSize: 12, fontWeight: '600' },
  levelBtnTextActive: { color: '#FFF' },
  section: { marginHorizontal: 16, marginBottom: 20 },
  sectionTitle: { color: '#FFF', fontSize: 16, fontWeight: '700', marginBottom: 2 },
  sectionSubtitle: { color: '#8E8E93', fontSize: 12, marginBottom: 12 },
  optionCard: { backgroundColor: '#111', borderRadius: 10, borderWidth: 1, borderColor: '#222', padding: 14, marginBottom: 8 },
  optionCardActive: { borderColor: 'rgba(201,169,98,0.5)', backgroundColor: 'rgba(201,169,98,0.05)' },
  optionHeader: { flexDirection: 'row', alignItems: 'flex-start', gap: 10 },
  radioOuter: { width: 20, height: 20, borderRadius: 10, borderWidth: 2, borderColor: '#444', justifyContent: 'center', alignItems: 'center', marginTop: 2 },
  radioOuterActive: { borderColor: '#C9A962' },
  radioInner: { width: 10, height: 10, borderRadius: 5, backgroundColor: '#C9A962' },
  optionTitle: { color: '#CCC', fontSize: 14, fontWeight: '600' },
  optionTitleActive: { color: '#FFF' },
  optionDesc: { color: '#666', fontSize: 12, lineHeight: 16, marginTop: 2 },
  toggleRow: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: '#1A1A1A' },
  toggleLabel: { color: '#FFF', fontSize: 14, fontWeight: '500' },
  toggleDesc: { color: '#666', fontSize: 11, lineHeight: 15, marginTop: 2 },
});
