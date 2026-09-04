import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, ScrollView, Switch,
  StyleSheet, ActivityIndicator, TextInput, Modal, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useThemeStore } from '../../store/themeStore';
import { useAuthStore } from '../../store/authStore';
import { useToast } from '../../components/common/Toast';
import api from '../../services/api';

const IS_WEB = Platform.OS === 'web';

const DAYS = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'] as const;
type Day = typeof DAYS[number];
const DAY_LABELS: Record<Day, string> = {
  monday:'Mon', tuesday:'Tue', wednesday:'Wed', thursday:'Thu',
  friday:'Fri', saturday:'Sat', sunday:'Sun',
};
const DAY_FULL: Record<Day, string> = {
  monday:'Monday', tuesday:'Tuesday', wednesday:'Wednesday', thursday:'Thursday',
  friday:'Friday', saturday:'Saturday', sunday:'Sunday',
};

type Block = { start: string; end: string };
type WeekSchedule = Record<Day, Block[]>;

const EMPTY_WEEK: WeekSchedule = Object.fromEntries(DAYS.map(d => [d, []])) as WeekSchedule;
const DEFAULT_BLOCK: Block = { start: '09:00', end: '17:00' };

const QUICK_PRESETS = [
  { label: 'Mon–Fri 9–5',  days: ['monday','tuesday','wednesday','thursday','friday'], block: { start:'09:00', end:'17:00' } },
  { label: 'Mon–Fri 8–6',  days: ['monday','tuesday','wednesday','thursday','friday'], block: { start:'08:00', end:'18:00' } },
  { label: 'Mon–Sat 9–5',  days: ['monday','tuesday','wednesday','thursday','friday','saturday'], block: { start:'09:00', end:'17:00' } },
  { label: 'Clear All',     days: [], block: null },
];

const OVERRIDE_OPTIONS = [
  { label: '+2 hours',        hours: 2 },
  { label: '+4 hours',        hours: 4 },
  { label: 'End of day',      eod: true },
  { label: 'Turn off override', clear: true },
];

function fmtTime(t: string) {
  if (!t) return '';
  const [h, m] = t.split(':').map(Number);
  const ampm = h >= 12 ? 'PM' : 'AM';
  const h12 = h % 12 || 12;
  return `${h12}:${m.toString().padStart(2,'0')} ${ampm}`;
}

function isValidTime(t: string) { return /^\d{2}:\d{2}$/.test(t); }

export default function SchedulePage() {
  const { colors } = useThemeStore();
  const s = getStyles(colors);
  const router = useRouter();
  const { user } = useAuthStore();
  const { showToast } = useToast();

  const [loading, setLoading]     = useState(true);
  const [saving, setSaving]       = useState(false);
  const [quietMode, setQuietMode] = useState(false);
  const [smsUrgentEnabled, setSmsUrgentEnabled] = useState(true);
  const [timezone, setTimezone]   = useState('America/Denver');
  const [rotationEnabled, setRotationEnabled] = useState(false);
  const [rotationAnchor, setRotationAnchor]   = useState('');
  const [activeWeek, setActiveWeek]           = useState<'A'|'B'>('A');
  const [scheduleA, setScheduleA] = useState<WeekSchedule>({ ...EMPTY_WEEK });
  const [scheduleB, setScheduleB] = useState<WeekSchedule>({ ...EMPTY_WEEK });
  const [overrideUntil, setOverrideUntil] = useState<string|null>(null);
  const [isAvailable, setIsAvailable]     = useState(false);

  // Day editor modal
  const [editDay, setEditDay]       = useState<Day|null>(null);
  const [editBlocks, setEditBlocks] = useState<Block[]>([]);

  const currentSchedule = activeWeek === 'A' ? scheduleA : scheduleB;
  const setCurrentSchedule = activeWeek === 'A' ? setScheduleA : setScheduleB;

  useEffect(() => { if (user?._id) loadSchedule(); }, [user?._id]);

  const loadSchedule = async () => {
    try {
      const [schedRes, statusRes] = await Promise.all([
        api.get('/schedule/me', { headers: { 'X-User-ID': user?._id } }),
        api.get(`/schedule/status/${user?._id}`),
      ]);
      const d = schedRes.data;
      setQuietMode(d.notification_quiet || false);
      setSmsUrgentEnabled(d.sms_you_are_needed !== false); // default true
      setTimezone(d.timezone || 'America/Denver');
      setRotationEnabled(d.rotation_enabled || false);
      setRotationAnchor(d.rotation_anchor || '');
      setScheduleA(d.weekly_schedule || { ...EMPTY_WEEK });
      setScheduleB(d.schedule_b || { ...EMPTY_WEEK });
      setOverrideUntil(d.available_override_until || null);
      setIsAvailable(statusRes.data.available);
    } catch (e) {
      showToast('Failed to load schedule', 'error');
    } finally {
      setLoading(false);
    }
  };

  const save = async () => {
    setSaving(true);
    try {
      await api.put('/schedule/me', {
        timezone,
        notification_quiet: quietMode,
        weekly_schedule: scheduleA,
        rotation_enabled: rotationEnabled,
        rotation_anchor: rotationAnchor || null,
        schedule_b: scheduleB,
      }, { headers: { 'X-User-ID': user?._id } });
      // Save SMS urgent setting to user's notification_settings
      await api.patch(`/users/${user?._id}`, {
        notification_settings: { sms_you_are_needed: smsUrgentEnabled }
      }).catch(() => {});
      showToast('Schedule saved', 'success');
      // Refresh availability
      const r = await api.get(`/schedule/status/${user?._id}`);
      setIsAvailable(r.data.available);
    } catch (e: any) {
      showToast(e?.response?.data?.detail || 'Save failed', 'error');
    } finally {
      setSaving(false);
    }
  };

  const applyPreset = (preset: typeof QUICK_PRESETS[0]) => {
    const next = { ...EMPTY_WEEK };
    if (preset.block) {
      (preset.days as Day[]).forEach(d => { next[d] = [{ ...preset.block! }]; });
    }
    setCurrentSchedule(next);
  };

  const setOverride = async (opt: typeof OVERRIDE_OPTIONS[0]) => {
    try {
      const res = await api.post('/schedule/me/override',
        opt.clear ? { clear: true } : opt.eod ? { until_end_of_day: true } : { hours: opt.hours },
        { headers: { 'X-User-ID': user?._id } }
      );
      setOverrideUntil(res.data.available_override_until);
      setIsAvailable(res.data.available);
      showToast(opt.clear ? 'Override cleared' : 'Override set — you\'re available', 'success');
    } catch {
      showToast('Failed to set override', 'error');
    }
  };

  const openEdit = (day: Day) => {
    setEditDay(day);
    setEditBlocks(currentSchedule[day]?.length ? [...currentSchedule[day]] : []);
  };

  const saveEdit = () => {
    if (!editDay) return;
    const valid = editBlocks.filter(b => isValidTime(b.start) && isValidTime(b.end) && b.start < b.end);
    setCurrentSchedule(prev => ({ ...prev, [editDay]: valid }));
    setEditDay(null);
  };

  const dayStatus = (day: Day, sched: WeekSchedule) => {
    const blocks = sched[day] || [];
    if (!blocks.length) return null;
    return blocks.map(b => `${fmtTime(b.start)}–${fmtTime(b.end)}`).join(', ');
  };

  const overrideLabel = overrideUntil
    ? `Active until ${new Date(overrideUntil).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
    : null;

  if (loading) {
    return <View style={s.center}><ActivityIndicator color={colors.accent} /></View>;
  }

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      {/* Header */}
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.back}>
          <Ionicons name="chevron-back" size={28} color={colors.accent} />
        </TouchableOpacity>
        <Text style={s.title}>My Schedule</Text>
        <TouchableOpacity onPress={save} disabled={saving} style={s.saveBtn} data-testid="save-schedule-btn">
          {saving ? <ActivityIndicator size="small" color="#000" /> : <Text style={s.saveBtnText}>Save</Text>}
        </TouchableOpacity>
      </View>

      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16, paddingBottom: 60 }}>

        {/* Live status pill */}
        <View style={[s.statusPill, { backgroundColor: isAvailable ? '#34C75920' : '#FF3B3020', borderColor: isAvailable ? '#34C759' : '#FF3B30' }]}>
          <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: isAvailable ? '#34C759' : '#FF3B30', marginRight: 8 }} />
          <Text style={{ color: isAvailable ? '#34C759' : '#FF3B30', fontWeight: '700', fontSize: 15 }}>
            {isAvailable ? 'Available now' : 'Off shift'}
          </Text>
          {overrideLabel && <Text style={{ color: colors.textSecondary, fontSize: 12, marginLeft: 8 }}>({overrideLabel})</Text>}
        </View>

        {/* Quiet mode toggle */}
        <View style={s.card}>
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
            <View style={{ flex: 1 }}>
              <Text style={s.cardTitle}>Respect My Schedule</Text>
              <Text style={s.cardSub}>Hold pushes outside your active hours</Text>
            </View>
            <Switch
              value={quietMode}
              onValueChange={setQuietMode}
              trackColor={{ true: colors.accent }}
              data-testid="quiet-mode-toggle"
            />
          </View>
        </View>

        {/* SMS YOU'RE NEEDED toggle */}
        <View style={s.card}>
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
            <View style={{ flex: 1 }}>
              <Text style={s.cardTitle}>SMS Urgent Alerts</Text>
              <Text style={s.cardSub}>Get a text to your personal phone when a customer is waiting</Text>
            </View>
            <Switch
              value={smsUrgentEnabled}
              onValueChange={setSmsUrgentEnabled}
              trackColor={{ true: '#FF9500' }}
              data-testid="sms-urgent-toggle"
            />
          </View>
        </View>

        {/* Timezone */}
        <View style={[s.card, { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }]}>
          <View>
            <Text style={s.cardTitle}>Timezone</Text>
            <Text style={s.cardSub}>{timezone}</Text>
          </View>
          <Ionicons name="globe-outline" size={20} color={colors.textSecondary} />
        </View>

        {/* Rotation toggle */}
        <View style={s.card}>
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: rotationEnabled ? 12 : 0 }}>
            <View style={{ flex: 1 }}>
              <Text style={s.cardTitle}>Rotating Schedule</Text>
              <Text style={s.cardSub}>Alternate between two week patterns (Week A / Week B)</Text>
            </View>
            <Switch
              value={rotationEnabled}
              onValueChange={v => { setRotationEnabled(v); if (v && !rotationAnchor) setRotationAnchor(new Date().toISOString().split('T')[0]); }}
              trackColor={{ true: colors.accent }}
              data-testid="rotation-toggle"
            />
          </View>

          {rotationEnabled && (
            <View>
              <Text style={[s.cardSub, { marginBottom: 4 }]}>Week A starts on (YYYY-MM-DD):</Text>
              <TextInput
                style={[s.input, { marginBottom: 0 }]}
                value={rotationAnchor}
                onChangeText={setRotationAnchor}
                placeholder="2026-05-26"
                placeholderTextColor={colors.textSecondary}
              />
            </View>
          )}
        </View>

        {/* Week picker (only for rotation) */}
        {rotationEnabled && (
          <View style={s.weekTabs}>
            {(['A','B'] as const).map(w => (
              <TouchableOpacity
                key={w}
                onPress={() => setActiveWeek(w)}
                style={[s.weekTab, activeWeek === w && { backgroundColor: colors.accent }]}
                data-testid={`week-tab-${w}`}
              >
                <Text style={[s.weekTabText, activeWeek === w && { color: '#000' }]}>Week {w}</Text>
              </TouchableOpacity>
            ))}
          </View>
        )}

        {/* Quick presets */}
        <View style={{ marginBottom: 8 }}>
          <Text style={s.sectionLabel}>{rotationEnabled ? `Week ${activeWeek} — Quick Presets` : 'Quick Presets'}</Text>
          <View style={s.presetRow}>
            {QUICK_PRESETS.map(p => (
              <TouchableOpacity key={p.label} onPress={() => applyPreset(p)} style={s.presetChip}>
                <Text style={s.presetChipText}>{p.label}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Day grid */}
        <Text style={s.sectionLabel}>
          {rotationEnabled ? `Week ${activeWeek} Hours` : 'Weekly Hours'}
        </Text>
        <View style={s.dayGrid}>
          {DAYS.map(day => {
            const status = dayStatus(day, currentSchedule);
            return (
              <TouchableOpacity
                key={day}
                style={[s.dayCard, status && { borderColor: colors.accent }]}
                onPress={() => openEdit(day)}
                data-testid={`day-card-${day}`}
              >
                <Text style={s.dayLabel}>{DAY_LABELS[day]}</Text>
                {status ? (
                  <Text style={[s.dayHours, { color: colors.accent }]} numberOfLines={2}>{status}</Text>
                ) : (
                  <Text style={s.dayOff}>OFF</Text>
                )}
              </TouchableOpacity>
            );
          })}
        </View>

        {/* Override section */}
        <Text style={[s.sectionLabel, { marginTop: 24 }]}>Override — Available Right Now</Text>
        <View style={s.card}>
          <Text style={s.cardSub}>Force yourself available even if outside scheduled hours.</Text>
          <View style={s.overrideRow}>
            {OVERRIDE_OPTIONS.map(opt => (
              <TouchableOpacity
                key={opt.label}
                onPress={() => setOverride(opt)}
                style={[s.overrideChip, opt.clear && { borderColor: '#FF3B30' }]}
                data-testid={`override-${opt.clear ? 'clear' : opt.eod ? 'eod' : `${opt.hours}h`}`}
              >
                <Text style={[s.overrideText, opt.clear && { color: '#FF3B30' }]}>{opt.label}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

      </ScrollView>

      {/* Day Edit Modal */}
      <Modal visible={!!editDay} animationType="slide" transparent>
        <View style={s.overlay}>
          <View style={s.sheet}>
            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 16, borderBottomWidth: 1, borderBottomColor: colors.border }}>
              <Text style={s.sheetTitle}>{editDay ? DAY_FULL[editDay] : ''}</Text>
              <TouchableOpacity onPress={() => setEditDay(null)}>
                <Text style={{ color: '#FF3B30', fontWeight: '600' }}>Cancel</Text>
              </TouchableOpacity>
            </View>

            <ScrollView style={{ padding: 16 }}>
              {/* Mark as off */}
              <TouchableOpacity
                onPress={() => setEditBlocks([])}
                style={[s.offButton, !editBlocks.length && { backgroundColor: '#FF3B3020', borderColor: '#FF3B30' }]}
                data-testid="mark-day-off"
              >
                <Ionicons name="close-circle-outline" size={18} color={editBlocks.length ? colors.textSecondary : '#FF3B30'} />
                <Text style={{ color: editBlocks.length ? colors.textSecondary : '#FF3B30', fontWeight: '600', marginLeft: 6 }}>Mark as Off</Text>
              </TouchableOpacity>

              {editBlocks.map((block, i) => (
                <View key={i} style={s.blockRow}>
                  <View style={{ flex: 1 }}>
                    <Text style={s.blockLabel}>Start</Text>
                    <TextInput
                      style={s.timeInput}
                      value={block.start}
                      onChangeText={v => setEditBlocks(prev => prev.map((b, j) => j === i ? { ...b, start: v } : b))}
                      placeholder="09:00"
                      placeholderTextColor={colors.textSecondary}
                      keyboardType="numbers-and-punctuation"
                    />
                  </View>
                  <Text style={{ color: colors.textSecondary, paddingHorizontal: 8, paddingTop: 22 }}>–</Text>
                  <View style={{ flex: 1 }}>
                    <Text style={s.blockLabel}>End</Text>
                    <TextInput
                      style={s.timeInput}
                      value={block.end}
                      onChangeText={v => setEditBlocks(prev => prev.map((b, j) => j === i ? { ...b, end: v } : b))}
                      placeholder="17:00"
                      placeholderTextColor={colors.textSecondary}
                      keyboardType="numbers-and-punctuation"
                    />
                  </View>
                  <TouchableOpacity
                    onPress={() => setEditBlocks(prev => prev.filter((_, j) => j !== i))}
                    style={{ paddingTop: 22, paddingLeft: 8 }}
                  >
                    <Ionicons name="trash-outline" size={20} color="#FF3B30" />
                  </TouchableOpacity>
                </View>
              ))}

              <TouchableOpacity
                onPress={() => setEditBlocks(prev => [...prev, { ...DEFAULT_BLOCK }])}
                style={s.addShiftBtn}
                data-testid="add-shift-btn"
              >
                <Ionicons name="add-circle-outline" size={18} color={colors.accent} />
                <Text style={{ color: colors.accent, fontWeight: '600', marginLeft: 6 }}>Add Shift</Text>
              </TouchableOpacity>

              <TouchableOpacity onPress={saveEdit} style={s.doneBtn} data-testid="save-day-btn">
                <Text style={s.doneBtnText}>Done</Text>
              </TouchableOpacity>
            </ScrollView>
          </View>
        </View>
      </Modal>

    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container:    { flex: 1, backgroundColor: colors.bg },
  center:       { flex: 1, alignItems: 'center', justifyContent: 'center' },
  header:       { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.border },
  back:         { width: 40 },
  title:        { fontSize: 17, fontWeight: '700', color: colors.text },
  saveBtn:      { backgroundColor: colors.accent, borderRadius: 10, paddingHorizontal: 18, paddingVertical: 8 },
  saveBtnText:  { color: '#000', fontWeight: '700', fontSize: 15 },
  statusPill:   { flexDirection: 'row', alignItems: 'center', borderRadius: 20, borderWidth: 1, paddingHorizontal: 14, paddingVertical: 8, marginBottom: 16 },
  card:         { backgroundColor: colors.card, borderRadius: 14, padding: 16, marginBottom: 12 },
  cardTitle:    { fontSize: 16, fontWeight: '700', color: colors.text, marginBottom: 2 },
  cardSub:      { fontSize: 13, color: colors.textSecondary, lineHeight: 18 },
  input:        { backgroundColor: colors.surface, borderRadius: 10, padding: 12, color: colors.text, fontSize: 15, borderWidth: 1, borderColor: colors.border, marginTop: 8 },
  weekTabs:     { flexDirection: 'row', gap: 10, marginBottom: 12 },
  weekTab:      { flex: 1, borderRadius: 12, borderWidth: 2, borderColor: colors.accent, paddingVertical: 10, alignItems: 'center' },
  weekTabText:  { fontWeight: '700', color: colors.accent, fontSize: 15 },
  sectionLabel: { fontSize: 13, color: colors.textSecondary, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 10 },
  presetRow:    { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 16 },
  presetChip:   { backgroundColor: colors.surface, borderRadius: 20, paddingHorizontal: 14, paddingVertical: 8, borderWidth: 1, borderColor: colors.border },
  presetChipText: { color: colors.text, fontSize: 13, fontWeight: '600' },
  dayGrid:      { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 8 },
  dayCard:      { width: '13%', minWidth: 44, backgroundColor: colors.card, borderRadius: 12, padding: 8, alignItems: 'center', borderWidth: 1.5, borderColor: colors.border, minHeight: 72 },
  dayLabel:     { fontSize: 12, fontWeight: '700', color: colors.textSecondary, marginBottom: 4 },
  dayHours:     { fontSize: 11, color: colors.accent, textAlign: 'center', fontWeight: '600' },
  dayOff:       { fontSize: 11, color: colors.textSecondary, fontStyle: 'italic' },
  overrideRow:  { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 10 },
  overrideChip: { backgroundColor: colors.surface, borderRadius: 20, paddingHorizontal: 14, paddingVertical: 8, borderWidth: 1, borderColor: colors.accent },
  overrideText: { color: colors.accent, fontSize: 13, fontWeight: '600' },
  overlay:      { flex: 1, backgroundColor: 'rgba(0,0,0,0.7)', justifyContent: 'flex-end' },
  sheet:        { backgroundColor: colors.card, borderTopLeftRadius: 20, borderTopRightRadius: 20, maxHeight: '85%' },
  sheetTitle:   { fontSize: 17, fontWeight: '700', color: colors.text },
  offButton:    { flexDirection: 'row', alignItems: 'center', borderRadius: 12, borderWidth: 1, borderColor: colors.border, padding: 12, marginBottom: 16 },
  blockRow:     { flexDirection: 'row', alignItems: 'center', marginBottom: 12, backgroundColor: colors.surface, borderRadius: 12, padding: 12 },
  blockLabel:   { fontSize: 12, color: colors.textSecondary, marginBottom: 4, fontWeight: '600' },
  timeInput:    { backgroundColor: colors.card, borderRadius: 8, padding: 10, color: colors.text, fontSize: 16, fontWeight: '600', textAlign: 'center', borderWidth: 1, borderColor: colors.border },
  addShiftBtn:  { flexDirection: 'row', alignItems: 'center', padding: 12, borderRadius: 12, borderWidth: 1, borderColor: colors.accent, borderStyle: 'dashed', justifyContent: 'center', marginBottom: 16 },
  doneBtn:      { backgroundColor: colors.accent, borderRadius: 12, padding: 16, alignItems: 'center', marginBottom: 8 },
  doneBtnText:  { color: '#000', fontWeight: '800', fontSize: 16 },
});
