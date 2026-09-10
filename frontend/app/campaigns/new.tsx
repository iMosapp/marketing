import React, { useEffect, useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, ScrollView, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { useToast } from '../../components/common/Toast';
import { ScreenHeader } from '../../components/common/ScreenHeader';
import api, { campaignsAPI } from '../../services/api';
import { SmartTagPicker } from '../../components/SmartTagPicker';
import { Eyebrow, OptionRow, GoldButton, Segmented, Chip } from '../../components/campaigns/Sheet';
import { DATE_TYPES, normalizeTouches, summarizeTouches, GOLD, tid } from '../../components/campaigns/utils';

const SCOPES = [
  { value: 'personal', label: 'Just me', roles: null },
  { value: 'account', label: 'Whole store', roles: ['super_admin', 'org_admin', 'store_manager'] },
  { value: 'org', label: 'Whole org', roles: ['super_admin', 'org_admin'] },
];

export default function NewCampaignScreen() {
  const { colors } = useThemeStore();
  const router = useRouter();
  const { template: templateId } = useLocalSearchParams<{ template?: string }>();
  const user = useAuthStore(s => s.user);
  const { showToast } = useToast();

  const [name, setName] = useState('');
  const [triggerType, setTriggerType] = useState<'tag' | 'date'>('tag');
  const [triggerTag, setTriggerTag] = useState('');
  const [dateType, setDateType] = useState('birthday');
  const [scope, setScope] = useState('personal');
  const [tags, setTags] = useState<any[]>([]);
  const [template, setTemplate] = useState<any>(null);
  const [loadingTpl, setLoadingTpl] = useState(!!templateId);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (!user?._id) return;
    api.get(`/tags/${user._id}`).then(r => setTags(r.data || [])).catch(() => {});
    if (templateId) {
      api.get(`/campaigns/templates/prebuilt/${templateId}`).then(r => {
        const t = r.data;
        setTemplate(t);
        setName(t.name || '');
        setTriggerTag(t.trigger_tag || '');
      }).catch(() => showToast('Template not found', 'error')).finally(() => setLoadingTpl(false));
    }
  }, [user?._id, templateId]);

  const scopes = SCOPES.filter(s => !s.roles || s.roles.includes(user?.role || ''));
  const touches = normalizeTouches(template?.sequences);

  const create = async () => {
    if (!name.trim()) { showToast('Give the plan a name', 'error'); return; }
    if (triggerType === 'tag' && !triggerTag) { showToast('Pick the tag that starts it', 'error'); return; }
    setCreating(true);
    try {
      const c = await campaignsAPI.create(user!._id, {
        name: name.trim(),
        type: triggerType === 'date' ? dateType : (template?.type || 'custom'),
        trigger_tag: triggerType === 'tag' ? triggerTag : '',
        date_type: triggerType === 'date' ? dateType : '',
        sequences: template?.sequences || [],
        active: false,
        delivery_mode: 'auto',
        ai_enabled: template ? !!template.ai_enabled : true,
        ai_assist_mode: 'auto_reply',
        scope,
        ownership_level: scope === 'account' ? 'store' : 'user',
      });
      router.replace(`/campaigns/${c._id || c.id}` as any);
    } catch (e: any) {
      showToast(e?.response?.data?.detail || 'Could not create the plan', 'error');
    } finally { setCreating(false); }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="New plan" subtitle={template ? `From the ${template.name} template` : 'Two taps, then fill in the texts'} testID="new-campaign-header" />
      {loadingTpl ? <ActivityIndicator style={{ marginTop: 60 }} color={GOLD} /> : (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 40, gap: 18 }} keyboardShouldPersistTaps="handled">
          <View style={{ gap: 8 }}>
            <Eyebrow colors={colors}>NAME</Eyebrow>
            <TextInput value={name} onChangeText={setName} placeholder="Sold Follow-Up" placeholderTextColor={colors.textTertiary} autoFocus={!templateId}
              style={{ backgroundColor: colors.card, borderRadius: 14, padding: 14, fontSize: 16, fontWeight: '700', color: colors.text, borderWidth: 1, borderColor: colors.border }} {...tid('new-campaign-name')} />
          </View>

          <View style={{ gap: 10 }}>
            <Eyebrow colors={colors}>WHAT STARTS IT?</Eyebrow>
            <Segmented colors={colors} testId="new-trigger-type" value={triggerType} onChange={v => setTriggerType(v as any)}
              options={[{ value: 'tag', label: 'A tag', icon: 'pricetag' }, { value: 'date', label: 'A date', icon: 'calendar' }]} />
            {triggerType === 'tag' ? (
              <>
                <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 17 }}>The moment anyone tags a contact with this, the plan starts for them.</Text>
                <SmartTagPicker tags={tags} selectedTag={triggerTag} onSelect={setTriggerTag} onTagCreated={t => setTags(p => [...p, { name: t, color: GOLD }])} userId={user?._id || ''} colors={colors} userRole={user?.role} />
              </>
            ) : (
              <View style={{ gap: 8 }}>
                {DATE_TYPES.map(d => <OptionRow key={d.id} label={d.name} sub={d.phrase} selected={dateType === d.id} onPress={() => setDateType(d.id)} testId={`new-date-${d.id}`} colors={colors} />)}
              </View>
            )}
          </View>

          {scopes.length > 1 ? (
            <View style={{ gap: 8 }}>
              <Eyebrow colors={colors}>WHO USES IT</Eyebrow>
              <View style={{ flexDirection: 'row', gap: 8 }}>
                {scopes.map(s => <Chip key={s.value} label={s.label} active={scope === s.value} colors={colors} testId={`new-scope-${s.value}`} onPress={() => setScope(s.value)} />)}
              </View>
            </View>
          ) : null}

          {template ? (
            <View style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 14, gap: 6 }} {...tid('new-template-summary')}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <Ionicons name={template.icon || 'rocket-outline'} size={16} color={template.color || GOLD} />
                <Text style={{ fontSize: 14, fontWeight: '800', color: colors.text }}>{summarizeTouches(touches)} come pre-written</Text>
              </View>
              <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 17 }}>{template.description}</Text>
              <Text style={{ fontSize: 12, color: colors.textSecondary }}>You can edit every touch on the next screen before turning it on.</Text>
            </View>
          ) : (
            <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 17 }}>Next you'll add the texts. Jessi answers replies automatically and personalizes each text by default; change either on the next screen.</Text>
          )}

          <GoldButton label={creating ? 'Creating…' : template ? 'Create from template' : 'Create plan'} onPress={create} disabled={creating} testId="new-campaign-create" icon="arrow-forward" />
        </ScrollView>
      )}
    </SafeAreaView>
  );
}
