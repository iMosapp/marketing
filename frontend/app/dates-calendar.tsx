import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { format } from 'date-fns';
import { useAuthStore } from '../store/authStore';
import { useThemeStore } from '../store/themeStore';
import api, { contactsAPI } from '../services/api';
import { showSimpleAlert } from '../services/alert';
import { Avatar } from '../components/Avatar';
import CalendarTaskModal from '../components/CalendarTaskModal';

const GOLD = '#C9A962';

const TYPE_META: Record<string, { color: string; icon: string; label: string }> = {
  birthday: { color: '#AF52DE', icon: 'gift', label: 'Birthday' },
  sold: { color: '#34C759', icon: 'car-sport', label: 'Sold' },
  anniversary: { color: '#FF2D55', icon: 'heart', label: 'Anniversary' },
  task: { color: GOLD, icon: 'checkbox', label: 'Tasks' },
};

const APPT_ICONS: Record<string, string> = {
  call: 'call', text: 'chatbubble', appointment: 'calendar', task: 'checkbox',
  test_drive: 'calendar', delivery: 'cube', meeting: 'people',
};

const tid = (id: string): any => ({ testID: id, dataSet: { testid: id } });

const fmtTime = (d: Date) => {
  const h = d.getHours() % 12 || 12;
  const m = String(d.getMinutes()).padStart(2, '0');
  return `${h}:${m} ${d.getHours() >= 12 ? 'PM' : 'AM'}`;
};

export default function CalendarScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const user = useAuthStore((state) => state.user);

  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1); // 1-12
  const [events, setEvents] = useState<any[]>([]);
  const [tasks, setTasks] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState<'all' | 'birthday' | 'sold' | 'anniversary' | 'task'>('all');
  const [selectedDay, setSelectedDay] = useState<number | null>(null);
  const [showAddTask, setShowAddTask] = useState(false);

  const load = useCallback(async () => {
    if (!user?._id) return;
    setLoading(true);
    try {
      const [datesRes, tasksRes] = await Promise.all([
        contactsAPI.getDatesCalendar(user._id, year, month),
        api.get(`/tasks/${user._id}/calendar?year=${year}&month=${month}`).then(r => r.data).catch(() => ({ tasks: [] })),
      ]);
      setEvents(datesRes.events || []);
      const mapped = (tasksRes.tasks || []).map((t: any) => {
        const local = new Date(t.due_at);
        if (local.getFullYear() !== year || local.getMonth() + 1 !== month) return null;
        return {
          type: 'task',
          day: local.getDate(),
          task_id: t.task_id,
          title: t.title,
          has_time: t.has_time,
          time_label: t.has_time ? fmtTime(local) : null,
          time_sort: t.has_time ? local.getHours() * 60 + local.getMinutes() : 9999,
          appointment_type: t.appointment_type,
          contact_id: t.contact_id,
          contact_name: t.contact_name,
          completed: t.completed,
        };
      }).filter(Boolean);
      setTasks(mapped);
    } catch {
      setEvents([]);
      setTasks([]);
    } finally {
      setLoading(false);
    }
  }, [user?._id, year, month]);

  useEffect(() => { load(); }, [load]);

  const changeMonth = (delta: number) => {
    let m = month + delta;
    let y = year;
    if (m < 1) { m = 12; y -= 1; }
    if (m > 12) { m = 1; y += 1; }
    setMonth(m); setYear(y); setSelectedDay(null);
  };

  const allItems = useMemo(() => [...tasks, ...events], [tasks, events]);

  const typeFiltered = useMemo(
    () => typeFilter === 'all' ? allItems : allItems.filter(e => e.type === typeFilter),
    [allItems, typeFilter]
  );

  const dayEvents = useMemo(() => {
    const map: Record<number, any[]> = {};
    typeFiltered.forEach(e => { (map[e.day] = map[e.day] || []).push(e); });
    return map;
  }, [typeFiltered]);

  const listEvents = selectedDay ? (dayEvents[selectedDay] || []) : typeFiltered;

  const counts = useMemo(() => ({
    birthday: events.filter(e => e.type === 'birthday').length,
    sold: events.filter(e => e.type === 'sold').length,
    anniversary: events.filter(e => e.type === 'anniversary').length,
    task: tasks.length,
  }), [events, tasks]);

  const toggleEnroll = async (ev: any) => {
    const enable = !ev.enrolled;
    setEvents(prev => prev.map(e =>
      e.contact_id === ev.contact_id && e.occasion === ev.occasion ? { ...e, enrolled: enable } : e
    ));
    try {
      await api.post(`/contacts/${user?._id}/date-optins/bulk`, {
        contact_ids: [ev.contact_id],
        occasion: ev.occasion,
        enable,
      });
    } catch {
      setEvents(prev => prev.map(e =>
        e.contact_id === ev.contact_id && e.occasion === ev.occasion ? { ...e, enrolled: !enable } : e
      ));
      showSimpleAlert('Error', 'Could not update. Please try again.');
    }
  };

  const completeTask = async (task: any) => {
    if (task.completed) return;
    setTasks(prev => prev.map(t => t.task_id === task.task_id ? { ...t, completed: true } : t));
    try {
      await api.patch(`/tasks/${user?._id}/${task.task_id}`, { action: 'complete' });
    } catch {
      setTasks(prev => prev.map(t => t.task_id === task.task_id ? { ...t, completed: false } : t));
      showSimpleAlert('Error', 'Could not complete. Please try again.');
    }
  };

  // ── month grid cells ──
  const grid = useMemo(() => {
    const firstDow = new Date(year, month - 1, 1).getDay();
    const daysInMonth = new Date(year, month, 0).getDate();
    const cells: (number | null)[] = Array(firstDow).fill(null);
    for (let d = 1; d <= daysInMonth; d++) cells.push(d);
    while (cells.length % 7 !== 0) cells.push(null);
    return cells;
  }, [year, month]);

  const isToday = (d: number) =>
    d === now.getDate() && month === now.getMonth() + 1 && year === now.getFullYear();

  const monthDate = new Date(year, month - 1, 1);

  const subtitleFor = (ev: any) => {
    const dateLabel = format(new Date(year, month - 1, ev.day), 'MMM d');
    if (ev.type === 'birthday') {
      return `Birthday · ${dateLabel}${ev.years ? ` · turns ${ev.years}` : ''}`;
    }
    if (ev.type === 'sold') {
      return `Sold${ev.vehicle ? ` ${ev.vehicle}` : ''} · ${dateLabel}${ev.years ? ` · ${ev.years} yr${ev.years === 1 ? '' : 's'}` : ''}`;
    }
    return `Anniversary · ${dateLabel}${ev.years ? ` · ${ev.years} yr${ev.years === 1 ? '' : 's'}` : ''}`;
  };

  // group list by day for agenda headers (days ascending; tasks first, timed before anytime)
  const grouped = useMemo(() => {
    const out: { day: number; items: any[] }[] = [];
    listEvents.forEach((e: any) => {
      const g = out.find(x => x.day === e.day);
      if (g) g.items.push(e);
      else out.push({ day: e.day, items: [e] });
    });
    out.sort((a, b) => a.day - b.day);
    out.forEach(g => g.items.sort((a: any, b: any) => {
      const aT = a.type === 'task' ? a.time_sort : 100000;
      const bT = b.type === 'task' ? b.time_sort : 100000;
      return aT - bT;
    }));
    return out;
  }, [listEvents]);

  const taskIcon = (t: any) =>
    (t.appointment_type && APPT_ICONS[t.appointment_type]) || 'checkbox';

  const taskSubtitle = (t: any) => {
    const parts = [t.time_label || 'Anytime'];
    if (t.appointment_type) {
      const label = { call: 'Call', text: 'Text', appointment: 'Appointment', task: 'Task', test_drive: 'Appointment', delivery: 'Delivery', meeting: 'Meeting' }[t.appointment_type as string];
      if (label) parts.push(label);
    }
    return parts.join(' · ');
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton} {...tid('dates-cal-back-btn')}>
          <Ionicons name="chevron-back" size={28} color={GOLD} />
        </TouchableOpacity>
        <Text maxFontSizeMultiplier={1.0} style={styles.headerTitle}>Calendar</Text>
        <TouchableOpacity onPress={() => setShowAddTask(true)} style={styles.addButton} {...tid('cal-add-task-btn')}>
          <Ionicons name="add" size={24} color="#000" />
        </TouchableOpacity>
      </View>

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingBottom: 32 }}>
        {/* Month nav */}
        <View style={styles.monthNav}>
          <TouchableOpacity onPress={() => changeMonth(-1)} style={styles.monthArrow} {...tid('dates-cal-prev-month')}>
            <Ionicons name="chevron-back" size={20} color={colors.textSecondary} />
          </TouchableOpacity>
          <Text maxFontSizeMultiplier={1.0} style={styles.monthTitle} {...tid('dates-cal-month-title')}>
            {format(monthDate, 'MMMM yyyy')}
          </Text>
          <TouchableOpacity onPress={() => changeMonth(1)} style={styles.monthArrow} {...tid('dates-cal-next-month')}>
            <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
          </TouchableOpacity>
        </View>

        {/* Grid */}
        <View style={styles.gridCard}>
          <View style={styles.dowRow}>
            {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((d, i) => (
              <Text key={i} maxFontSizeMultiplier={1.0} style={styles.dowText}>{d}</Text>
            ))}
          </View>
          <View style={styles.grid}>
            {grid.map((d, i) => {
              const evs = d ? (dayEvents[d] || []) : [];
              const dotTypes = Array.from(new Set(evs.map((e: any) => e.type))).slice(0, 3);
              const selected = d !== null && selectedDay === d;
              return (
                <TouchableOpacity
                  key={i}
                  style={styles.cell}
                  disabled={!d}
                  onPress={() => d && setSelectedDay(selected ? null : d)}
                  {...(d ? tid(`dates-cal-day-${d}`) : {})}
                >
                  {d ? (
                    <View style={[
                      styles.cellInner,
                      isToday(d) && styles.cellToday,
                      selected && styles.cellSelected,
                    ]}>
                      <Text maxFontSizeMultiplier={1.0} style={[
                        styles.cellText,
                        selected && { color: '#000', fontWeight: '800' },
                      ]}>{d}</Text>
                      <View style={styles.dotsRow}>
                        {dotTypes.map((t: string) => (
                          <View key={t} style={[styles.dot, { backgroundColor: TYPE_META[t].color }]} />
                        ))}
                      </View>
                    </View>
                  ) : null}
                </TouchableOpacity>
              );
            })}
          </View>
          {/* Legend */}
          <View style={styles.legend}>
            {(['task', 'birthday', 'sold', 'anniversary'] as const).map(t => (
              <View key={t} style={styles.legendItem}>
                <View style={[styles.dot, { backgroundColor: TYPE_META[t].color }]} />
                <Text maxFontSizeMultiplier={1.0} style={styles.legendText}>{TYPE_META[t].label}</Text>
              </View>
            ))}
          </View>
        </View>

        {/* Filter chips */}
        <View style={styles.chipsRow}>
          {([
            { key: 'all', label: `All · ${allItems.length}` },
            { key: 'task', label: `Tasks · ${counts.task}` },
            { key: 'birthday', label: `Birthdays · ${counts.birthday}` },
            { key: 'sold', label: `Sold · ${counts.sold}` },
            { key: 'anniversary', label: `Anniv · ${counts.anniversary}` },
          ] as const).map(c => (
            <TouchableOpacity
              key={c.key}
              onPress={() => setTypeFilter(c.key)}
              style={[styles.chip, typeFilter === c.key && styles.chipActive]}
              {...tid(`dates-cal-filter-${c.key}`)}
            >
              <Text maxFontSizeMultiplier={1.0} style={[styles.chipText, typeFilter === c.key && { color: '#000' }]}>
                {c.label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {selectedDay ? (
          <TouchableOpacity onPress={() => setSelectedDay(null)} style={styles.dayBanner} {...tid('dates-cal-clear-day')}>
            <Text maxFontSizeMultiplier={1.0} style={styles.dayBannerText}>
              Showing {format(new Date(year, month - 1, selectedDay), 'EEE, MMM d')} — tap to show whole month
            </Text>
            <Ionicons name="close-circle" size={16} color={GOLD} />
          </TouchableOpacity>
        ) : null}

        {/* Agenda list */}
        {loading ? (
          <ActivityIndicator size="large" color={GOLD} style={{ marginTop: 40 }} />
        ) : grouped.length === 0 ? (
          <View style={styles.empty} {...tid('dates-cal-empty')}>
            <Ionicons name="calendar-outline" size={48} color={colors.border} />
            <Text maxFontSizeMultiplier={1.0} style={styles.emptyTitle}>
              {selectedDay ? 'Nothing on this day' : `Nothing in ${format(monthDate, 'MMMM')}`}
            </Text>
            <Text maxFontSizeMultiplier={1.0} style={styles.emptySub}>
              Tasks, appointments, birthdays and sold dates will show up here
            </Text>
            <TouchableOpacity onPress={() => setShowAddTask(true)} style={styles.emptyAddBtn} {...tid('cal-empty-add-btn')}>
              <Ionicons name="add" size={16} color="#000" />
              <Text maxFontSizeMultiplier={1.0} style={styles.emptyAddText}>Add a task</Text>
            </TouchableOpacity>
          </View>
        ) : (
          grouped.map(group => (
            <View key={group.day}>
              <Text maxFontSizeMultiplier={1.0} style={styles.dayHeader}>
                {format(new Date(year, month - 1, group.day), 'EEE · MMM d').toUpperCase()}
              </Text>
              {group.items.map((ev: any, idx: number) => {
                if (ev.type === 'task') {
                  return (
                    <TouchableOpacity
                      key={`task-${ev.task_id}`}
                      style={[styles.eventRow, styles.taskRow, ev.completed && { opacity: 0.55 }]}
                      onPress={() => ev.contact_id && router.push(`/contact/${ev.contact_id}?taskId=${ev.task_id}` as any)}
                      activeOpacity={ev.contact_id ? 0.7 : 1}
                      {...tid(`cal-task-row-${ev.task_id}`)}
                    >
                      <View style={[styles.typeIcon, { backgroundColor: GOLD + '22' }]}>
                        <Ionicons name={taskIcon(ev) as any} size={16} color={GOLD} />
                      </View>
                      <View style={{ flex: 1 }}>
                        <Text maxFontSizeMultiplier={1.0} numberOfLines={1} style={[styles.eventName, ev.completed && styles.taskDone]}>
                          {ev.title}
                        </Text>
                        <Text maxFontSizeMultiplier={1.0} numberOfLines={1} style={styles.eventSub}>
                          {taskSubtitle(ev)}{ev.contact_name ? ` · ${ev.contact_name}` : ''}
                        </Text>
                      </View>
                      <TouchableOpacity
                        onPress={(e: any) => { e.stopPropagation?.(); completeTask(ev); }}
                        style={styles.checkBtn}
                        {...tid(`cal-task-complete-${ev.task_id}`)}
                      >
                        <Ionicons
                          name={ev.completed ? 'checkmark-circle' : 'ellipse-outline'}
                          size={26}
                          color={ev.completed ? '#34C759' : colors.textTertiary}
                        />
                      </TouchableOpacity>
                    </TouchableOpacity>
                  );
                }
                const meta = TYPE_META[ev.type];
                return (
                  <TouchableOpacity
                    key={`${ev.contact_id}-${ev.type}-${idx}`}
                    style={styles.eventRow}
                    onPress={() => router.push(`/contact/${ev.contact_id}`)}
                    activeOpacity={0.7}
                    {...tid(`dates-cal-event-${ev.contact_id}-${ev.type}`)}
                  >
                    <View style={[styles.typeIcon, { backgroundColor: meta.color + '22' }]}>
                      <Ionicons name={meta.icon as any} size={16} color={meta.color} />
                    </View>
                    <Avatar
                      photo={ev.photo_thumbnail}
                      name={`${ev.first_name} ${ev.last_name}`.trim()}
                      size="sm"
                      style={{ width: 36, height: 36, borderRadius: 12 } as any}
                    />
                    <View style={{ flex: 1, marginLeft: 10 }}>
                      <Text maxFontSizeMultiplier={1.0} numberOfLines={1} style={styles.eventName}>
                        {ev.first_name} {ev.last_name}
                      </Text>
                      <Text maxFontSizeMultiplier={1.0} numberOfLines={1} style={styles.eventSub}>
                        {subtitleFor(ev)}
                      </Text>
                    </View>
                    <TouchableOpacity
                      onPress={(e: any) => { e.stopPropagation?.(); toggleEnroll(ev); }}
                      style={[styles.autoPill, ev.enrolled ? styles.autoPillOn : styles.autoPillOff]}
                      {...tid(`dates-cal-toggle-${ev.contact_id}-${ev.type}`)}
                    >
                      {ev.enrolled && <Ionicons name="notifications" size={10} color="#34C759" />}
                      <Text maxFontSizeMultiplier={1.0} style={[styles.autoPillText, { color: ev.enrolled ? '#34C759' : colors.textTertiary }]}>
                        {ev.enrolled ? 'AUTO ON' : 'OFF'}
                      </Text>
                    </TouchableOpacity>
                  </TouchableOpacity>
                );
              })}
            </View>
          ))
        )}
      </ScrollView>

      <CalendarTaskModal
        visible={showAddTask}
        onClose={() => setShowAddTask(false)}
        colors={colors}
        userId={user?._id}
        defaultDate={selectedDay ? new Date(year, month - 1, selectedDay) : new Date()}
        onSaved={load}
      />
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 8, paddingVertical: 8,
  },
  backButton: { padding: 8 },
  headerTitle: { fontSize: 18, fontWeight: '800', color: colors.text },
  addButton: {
    width: 34, height: 34, borderRadius: 17, backgroundColor: GOLD,
    alignItems: 'center', justifyContent: 'center', marginRight: 8,
  },
  monthNav: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 20, marginBottom: 8,
  },
  monthArrow: { padding: 8, backgroundColor: colors.card, borderRadius: 10 },
  monthTitle: { fontSize: 19, fontWeight: '800', color: colors.text },
  gridCard: {
    backgroundColor: colors.card, borderRadius: 18, marginHorizontal: 16, padding: 12,
  },
  dowRow: { flexDirection: 'row', marginBottom: 4 },
  dowText: {
    flex: 1, textAlign: 'center', fontSize: 11, fontWeight: '700',
    color: colors.textTertiary,
  },
  grid: { flexDirection: 'row', flexWrap: 'wrap' },
  cell: { width: `${100 / 7}%`, aspectRatio: 0.9, alignItems: 'center', justifyContent: 'center' },
  cellInner: {
    width: 36, height: 40, borderRadius: 10, alignItems: 'center', justifyContent: 'center',
    paddingTop: 2,
  },
  cellToday: { borderWidth: 1, borderColor: GOLD },
  cellSelected: { backgroundColor: GOLD },
  cellText: { fontSize: 14, fontWeight: '600', color: colors.text },
  dotsRow: { flexDirection: 'row', gap: 2, height: 6, marginTop: 2 },
  dot: { width: 5, height: 5, borderRadius: 3 },
  legend: {
    flexDirection: 'row', justifyContent: 'center', gap: 14,
    marginTop: 8, paddingTop: 10, borderTopWidth: 1, borderTopColor: colors.border,
  },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  legendText: { fontSize: 12, color: colors.textSecondary, fontWeight: '600' },
  chipsRow: {
    flexDirection: 'row', gap: 6, paddingHorizontal: 16, marginTop: 14, marginBottom: 4,
    flexWrap: 'wrap',
  },
  chip: {
    paddingHorizontal: 11, paddingVertical: 6, borderRadius: 14, backgroundColor: colors.card,
  },
  chipActive: { backgroundColor: GOLD },
  chipText: { fontSize: 12.5, fontWeight: '700', color: colors.textSecondary },
  dayBanner: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    marginHorizontal: 16, marginTop: 8, paddingHorizontal: 12, paddingVertical: 8,
    backgroundColor: GOLD + '15', borderRadius: 10,
  },
  dayBannerText: { fontSize: 12.5, fontWeight: '600', color: GOLD },
  dayHeader: {
    fontSize: 12, fontWeight: '800', color: GOLD, letterSpacing: 0.8,
    paddingHorizontal: 20, marginTop: 16, marginBottom: 4,
  },
  eventRow: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: colors.card, borderRadius: 14,
    marginHorizontal: 16, marginBottom: 6, paddingHorizontal: 12, paddingVertical: 10,
    gap: 10,
  },
  taskRow: { borderWidth: 1, borderColor: GOLD + '33' },
  taskDone: { textDecorationLine: 'line-through' },
  checkBtn: { padding: 2 },
  typeIcon: {
    width: 32, height: 32, borderRadius: 10, alignItems: 'center', justifyContent: 'center',
  },
  eventName: { fontSize: 15, fontWeight: '700', color: colors.text },
  eventSub: { fontSize: 12.5, color: colors.textSecondary, marginTop: 1 },
  autoPill: {
    flexDirection: 'row', alignItems: 'center', gap: 3,
    paddingHorizontal: 9, paddingVertical: 5, borderRadius: 10,
  },
  autoPillOn: { backgroundColor: '#34C75922' },
  autoPillOff: { backgroundColor: colors.bg },
  autoPillText: { fontSize: 10.5, fontWeight: '800' },
  empty: { alignItems: 'center', paddingVertical: 48, paddingHorizontal: 32 },
  emptyTitle: { fontSize: 17, fontWeight: '700', color: colors.text, marginTop: 12 },
  emptySub: { fontSize: 13, color: colors.textSecondary, marginTop: 4, textAlign: 'center' },
  emptyAddBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 16,
    backgroundColor: GOLD, paddingHorizontal: 16, paddingVertical: 9, borderRadius: 18,
  },
  emptyAddText: { fontSize: 14, fontWeight: '700', color: '#000' },
});
