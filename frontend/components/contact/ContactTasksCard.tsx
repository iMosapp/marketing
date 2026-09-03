/**
 * ContactTasksCard — "Up Next" for this contact: the featured open task (with Call / Write It / Done)
 * plus a slim list of the other open tasks. Arriving with ?taskId= features that exact task.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { format, isToday, isTomorrow, differenceInCalendarDays, startOfDay } from 'date-fns';
import api from '../../services/api';
import { DraftMessageSheet } from '../DraftMessageSheet';

const GOLD = '#C9A962';
const RED = '#FF453A';
const GREEN = '#34C759';

const TYPE_ICON: Record<string, string> = {
  call: 'call', text: 'chatbubble', appointment: 'calendar', task: 'checkbox',
  birthday: 'gift', anniversary: 'ribbon', follow_up: 'refresh',
};

export function taskKind(t: any): string {
  if (t.appointment_type) return t.appointment_type;
  if (['birthday', 'anniversary', 'follow_up'].includes(t.type)) return t.type;
  if (t.action_type === 'text' || t.action_type === 'call') return t.action_type;
  return 'task';
}

export function whenLabel(t: any): { text: string; overdue: boolean } {
  if (!t.due_date) return { text: 'Anytime', overdue: false };
  const d = new Date(t.due_date);
  const time = t.has_time ? format(d, 'h:mm a') : '';
  const now = new Date();
  if (t.is_overdue) {
    const days = differenceInCalendarDays(startOfDay(now), startOfDay(d));
    return { text: days <= 0 ? `Overdue · was ${time || 'today'}` : `Overdue · ${days} day${days === 1 ? '' : 's'}`, overdue: true };
  }
  const day = isToday(d) ? 'Today' : isTomorrow(d) ? 'Tomorrow'
    : differenceInCalendarDays(d, now) < 7 ? format(d, 'EEEE') : format(d, 'MMM d');
  return { text: time ? `${day} · ${time}` : day, overdue: false };
}

function ActionBtn({ icon, label, onPress, primary, green, testid, colors }: any) {
  const color = primary ? '#000' : green ? GREEN : colors.text;
  return (
    <TouchableOpacity
      onPress={onPress}
      activeOpacity={0.75}
      style={{
        flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 5,
        paddingVertical: 9, borderRadius: 10, borderWidth: 1,
        backgroundColor: primary ? GOLD : 'transparent',
        borderColor: primary ? GOLD : green ? `${GREEN}66` : colors.border,
      }}
      testID={testid}
      dataSet={{ testid } as any}
    >
      <Ionicons name={icon} size={14} color={color} />
      <Text style={{ fontSize: 12, fontWeight: '800', color }}>{label}</Text>
    </TouchableOpacity>
  );
}

export default function ContactTasksCard({ colors, userId, contactId, contact, featuredTaskId, refreshKey, onAddTask, showToast }: any) {
  const router = useRouter();
  const [tasks, setTasks] = useState<any[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [featuredId, setFeaturedId] = useState<string | null>(featuredTaskId || null);
  const [showAll, setShowAll] = useState(false);
  const [draftItem, setDraftItem] = useState<any>(null);
  const [undo, setUndo] = useState<any>(null);
  const undoTimer = useRef<any>(null);

  const load = useCallback(async () => {
    if (!userId || !contactId) return;
    try {
      const res = await api.get(`/tasks/${userId}/contact/${contactId}`);
      setTasks(res.data?.tasks || []);
    } catch {}
    setLoaded(true);
  }, [userId, contactId]);

  useEffect(() => { load(); }, [load, refreshKey]);
  useEffect(() => { if (featuredTaskId) setFeaturedId(featuredTaskId); }, [featuredTaskId]);
  // Twilio's "call connected" webhook lands a few seconds after hang-up, so re-check twice after focus.
  useFocusEffect(useCallback(() => {
    load();
    const t1 = setTimeout(load, 5000);
    const t2 = setTimeout(load, 15000);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [load]));

  const featured = useMemo(() => tasks.find(t => t._id === featuredId) || tasks[0] || null, [tasks, featuredId]);
  const others = tasks.filter(t => t !== featured);
  const visibleOthers = showAll ? others : others.slice(0, 2);
  const hiddenCount = others.length - visibleOthers.length;

  if (!loaded || (tasks.length === 0 && !undo)) return null;

  const name = `${contact?.first_name || ''} ${contact?.last_name || ''}`.trim();

  const complete = async (t: any) => {
    setTasks(prev => prev.filter(x => x._id !== t._id));
    setUndo({ ...t, _undoKind: 'done' });
    clearTimeout(undoTimer.current);
    undoTimer.current = setTimeout(() => setUndo(null), 6000);
    try { await api.patch(`/tasks/${userId}/${t._id}`, { action: 'complete' }); } catch { load(); }
  };

  const snoozeTarget = (kind: 'tomorrow' | 'next_week') => {
    const d = new Date();
    d.setHours(9, 0, 0, 0);
    if (kind === 'tomorrow') d.setDate(d.getDate() + 1);
    else d.setDate(d.getDate() + (((8 - d.getDay()) % 7) || 7));
    return d;
  };

  const snooze = async (t: any, kind: 'tomorrow' | 'next_week') => {
    const until = snoozeTarget(kind);
    setTasks(prev => prev
      .map(x => x._id === t._id ? { ...x, due_date: until.toISOString(), has_time: true, is_overdue: false, status: 'snoozed' } : x)
      .sort((a, b) => Number(!a.is_overdue) - Number(!b.is_overdue) || new Date(a.due_date || 0).getTime() - new Date(b.due_date || 0).getTime()));
    setUndo({ ...t, _undoKind: 'snooze', _label: kind === 'tomorrow' ? 'Tomorrow 9 AM' : `${format(until, 'EEE')} 9 AM` });
    clearTimeout(undoTimer.current);
    undoTimer.current = setTimeout(() => setUndo(null), 6000);
    try { await api.patch(`/tasks/${userId}/${t._id}`, { action: 'snooze', snooze_until: until.toISOString() }); } catch { load(); }
  };

  const undoLast = async () => {
    const t = undo;
    setUndo(null);
    clearTimeout(undoTimer.current);
    if (!t) return;
    try { await api.patch(`/tasks/${userId}/${t._id}`, { action: 'reopen', due_date: t.due_date }); } catch {}
    load();
  };

  const call = (t: any) => {
    if (!contact?.phone) { showToast?.('No phone number on this contact', 'error'); return; }
    router.push({ pathname: '/call-screen', params: { phone: contact.phone, contact_name: name, contact_id: contactId, task_id: t._id } } as any);
  };

  const writeIt = (t: any) => {
    const w = whenLabel(t);
    setDraftItem({
      contact_id: contactId, first_name: contact?.first_name, last_name: contact?.last_name, phone: contact?.phone,
      reason_key: t.type === 'birthday' ? 'birthday' : t.type === 'anniversary' ? 'anniversary' : 'touchpoint',
      reason_label: `${t.title} · ${w.text}`,
      context: [t.title, t.description, `Scheduled: ${w.text}`].filter(Boolean).join('. '),
      icon: TYPE_ICON[taskKind(t)] || 'checkbox', color: GOLD, task_id: t._id,
    });
  };

  const fw = featured ? whenLabel(featured) : null;
  const fKind = featured ? taskKind(featured) : 'task';
  const accent = fw?.overdue ? RED : GOLD;

  return (
    <View
      style={{ marginHorizontal: 16, marginBottom: 12, borderRadius: 16, backgroundColor: colors.card, borderWidth: 1, borderColor: `${accent}70`, overflow: 'hidden' }}
      testID="contact-tasks-card"
      dataSet={{ testid: 'contact-tasks-card' } as any}
    >
      {featured && fw && (
        <View style={{ flexDirection: 'row', gap: 12, padding: 14 }} testID="contact-task-featured" dataSet={{ testid: 'contact-task-featured' } as any}>
          <View style={{ width: 36, height: 36, borderRadius: 10, backgroundColor: `${accent}20`, alignItems: 'center', justifyContent: 'center' }}>
            <Ionicons name={(TYPE_ICON[fKind] || 'checkbox') as any} size={17} color={accent} />
          </View>
          <View style={{ flex: 1 }}>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
              <Text style={{ fontSize: 11, fontWeight: '800', letterSpacing: 0.8, color: accent }}>{fw.overdue ? 'OVERDUE' : 'UP NEXT'}</Text>
              <Text style={{ fontSize: 12, fontWeight: '700', color: fw.overdue ? RED : colors.textSecondary }} testID="contact-task-when" dataSet={{ testid: 'contact-task-when' } as any}>{fw.text}</Text>
            </View>
            <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text, marginTop: 4, lineHeight: 21 }} testID="contact-task-title" dataSet={{ testid: 'contact-task-title' } as any}>{featured.title}</Text>
            {!!featured.description && (
              <Text numberOfLines={3} style={{ fontSize: 13, color: colors.textSecondary, marginTop: 3, lineHeight: 18 }}>{featured.description}</Text>
            )}
            <View style={{ flexDirection: 'row', gap: 8, marginTop: 12 }}>
              {fKind === 'call' ? (
                <>
                  <ActionBtn primary icon="call" label="Call now" onPress={() => call(featured)} testid="contact-task-call-btn" colors={colors} />
                  <ActionBtn icon="sparkles" label="Write It" onPress={() => writeIt(featured)} testid="contact-task-write-btn" colors={colors} />
                </>
              ) : (
                <>
                  <ActionBtn primary icon="sparkles" label="Write It" onPress={() => writeIt(featured)} testid="contact-task-write-btn" colors={colors} />
                  <ActionBtn icon="call" label="Call" onPress={() => call(featured)} testid="contact-task-call-btn" colors={colors} />
                </>
              )}
              <ActionBtn green icon="checkmark" label="Done" onPress={() => complete(featured)} testid="contact-task-done-btn" colors={colors} />
            </View>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 10 }}>
              <Ionicons name="alarm-outline" size={13} color={colors.textTertiary} />
              <Text style={{ fontSize: 12, color: colors.textTertiary, fontWeight: '600' }}>Snooze</Text>
              {([['tomorrow', 'Tomorrow'], ['next_week', 'Next week']] as const).map(([k, label]) => (
                <TouchableOpacity
                  key={k}
                  onPress={() => snooze(featured, k)}
                  style={{ paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12, backgroundColor: colors.surface }}
                  testID={`contact-task-snooze-${k}`}
                  dataSet={{ testid: `contact-task-snooze-${k}` } as any}
                >
                  <Text style={{ fontSize: 12, fontWeight: '700', color: colors.text }}>{label}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
        </View>
      )}

      {visibleOthers.map(t => {
        const w = whenLabel(t);
        return (
          <TouchableOpacity
            key={t._id}
            onPress={() => setFeaturedId(t._id)}
            activeOpacity={0.7}
            style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 14, paddingVertical: 10, borderTopWidth: 1, borderTopColor: colors.border }}
            testID={`contact-task-row-${t._id}`}
            dataSet={{ testid: `contact-task-row-${t._id}` } as any}
          >
            <View style={{ width: 30, height: 30, borderRadius: 8, backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center' }}>
              <Ionicons name={(TYPE_ICON[taskKind(t)] || 'checkbox') as any} size={14} color={w.overdue ? RED : colors.textSecondary} />
            </View>
            <View style={{ flex: 1 }}>
              <Text numberOfLines={1} style={{ fontSize: 14, fontWeight: '600', color: colors.text }}>{t.title}</Text>
              <Text style={{ fontSize: 12, fontWeight: '700', color: w.overdue ? RED : colors.textSecondary, marginTop: 1 }}>{w.text}</Text>
            </View>
            <TouchableOpacity onPress={() => complete(t)} hitSlop={8} testID={`contact-task-check-${t._id}`} dataSet={{ testid: `contact-task-check-${t._id}` } as any}>
              <Ionicons name="ellipse-outline" size={24} color={colors.textTertiary} />
            </TouchableOpacity>
          </TouchableOpacity>
        );
      })}

      {(hiddenCount > 0 || showAll || onAddTask) && (
        <View style={{ flexDirection: 'row', justifyContent: 'center', gap: 18, paddingVertical: 10, borderTopWidth: 1, borderTopColor: colors.border }}>
          {hiddenCount > 0 && (
            <TouchableOpacity onPress={() => setShowAll(true)} testID="contact-tasks-show-more" dataSet={{ testid: 'contact-tasks-show-more' } as any}>
              <Text style={{ fontSize: 12, fontWeight: '700', color: GOLD }}>Show {hiddenCount} more</Text>
            </TouchableOpacity>
          )}
          {showAll && others.length > 2 && (
            <TouchableOpacity onPress={() => setShowAll(false)}>
              <Text style={{ fontSize: 12, fontWeight: '700', color: GOLD }}>Show less</Text>
            </TouchableOpacity>
          )}
          {onAddTask && (
            <TouchableOpacity onPress={onAddTask} testID="contact-tasks-add" dataSet={{ testid: 'contact-tasks-add' } as any}>
              <Text style={{ fontSize: 12, fontWeight: '700', color: GOLD }}>Add task +</Text>
            </TouchableOpacity>
          )}
        </View>
      )}

      {undo && (
        <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 14, paddingVertical: 9, backgroundColor: undo._undoKind === 'snooze' ? `${GOLD}15` : `${GREEN}15`, borderTopWidth: 1, borderTopColor: colors.border }} testID="contact-task-undo-bar" dataSet={{ testid: 'contact-task-undo-bar' } as any}>
          <Text style={{ fontSize: 13, color: undo._undoKind === 'snooze' ? GOLD : GREEN, fontWeight: '700', flex: 1, marginRight: 10 }} numberOfLines={1}>
            {undo._undoKind === 'snooze' ? `Snoozed to ${undo._label}: ${undo.title}` : `Done: ${undo.title}`}
          </Text>
          <TouchableOpacity onPress={undoLast} testID="contact-task-undo-btn" dataSet={{ testid: 'contact-task-undo-btn' } as any}>
            <Text style={{ fontSize: 13, fontWeight: '800', color: GOLD }}>Undo</Text>
          </TouchableOpacity>
        </View>
      )}

      <DraftMessageSheet userId={userId} item={draftItem} onClose={() => setDraftItem(null)} hideViewContact />
    </View>
  );
}
