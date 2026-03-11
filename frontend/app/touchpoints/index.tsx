import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, ScrollView, ActivityIndicator, Linking, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { tasksAPI, contactsAPI } from '../../services/api';
import api from '../../services/api';
import { showSimpleAlert } from '../../services/alert';

const IS_WEB = Platform.OS === 'web';

const SCORE_ITEMS_ACTIONS = [
  { key: 'calls', label: 'CALLS', color: '#007AFF' },
  { key: 'texts', label: 'TEXTS', color: '#34C759' },
  { key: 'emails', label: 'EMAILS', color: '#5AC8FA' },
  { key: 'cards', label: 'CARDS', color: '#C9A962' },
  { key: 'reviews', label: 'REVIEWS', color: '#FFD60A' },
];
const SCORE_ITEMS_ENGAGE = [
  { key: 'clicks', label: 'CLICKS', color: '#FF375F' },
  { key: 'opens', label: 'OPENS', color: '#AF52DE' },
  { key: 'replies', label: 'REPLIES', color: '#FF9500' },
  { key: 'new_leads', label: 'NEW LEADS', color: '#32ADE6' },
];

const FILTERS = ['All', 'Overdue', 'Campaigns', 'Birthdays', 'Follow-ups'];

function getInitials(name: string) {
  const parts = (name || '?').split(' ').filter(Boolean);
  return (parts[0]?.[0] || '?').toUpperCase() + (parts[1]?.[0] || '').toUpperCase();
}

function getAvatarColor(task: any) {
  if (task.status === 'overdue' || isOverdue(task)) return { bg: 'rgba(255,59,48,0.12)', text: '#FF3B30' };
  if (task.source === 'campaign') return { bg: 'rgba(201,169,98,0.12)', text: '#C9A962' };
  if (task.type === 'birthday') return { bg: 'rgba(52,199,89,0.12)', text: '#34C759' };
  if (task.type === 'anniversary') return { bg: 'rgba(255,45,85,0.12)', text: '#FF2D55' };
  if (task.source === 'system') return { bg: 'rgba(175,82,222,0.12)', text: '#AF52DE' };
  return { bg: 'rgba(201,169,98,0.12)', text: '#C9A962' };
}

function isOverdue(task: any) {
  if (!task.due_date) return false;
  const due = new Date(task.due_date);
  const todayStart = new Date(); todayStart.setHours(0, 0, 0, 0);
  return due < todayStart && task.status !== 'completed';
}

function getBadges(task: any) {
  const badges: { label: string; bg: string; color: string }[] = [];
  if (isOverdue(task)) badges.push({ label: 'Overdue', bg: 'rgba(255,59,48,0.12)', color: '#FF3B30' });
  if (task.source === 'campaign') badges.push({ label: task.campaign_name || 'Campaign', bg: 'rgba(175,82,222,0.12)', color: '#AF52DE' });
  if (task.type === 'birthday') badges.push({ label: 'Birthday', bg: 'rgba(201,169,98,0.12)', color: '#C9A962' });
  if (task.type === 'anniversary') badges.push({ label: 'Anniversary', bg: 'rgba(255,45,85,0.12)', color: '#FF2D55' });
  if (task.source === 'system' && task.type !== 'birthday' && task.type !== 'anniversary') badges.push({ label: 'System', bg: 'rgba(142,142,147,0.12)', color: '#8E8E93' });
  if (task.priority === 'high' && !isOverdue(task)) badges.push({ label: 'High', bg: 'rgba(255,150,0,0.12)', color: '#FF9500' });
  return badges;
}

function getDueLabel(task: any) {
  if (!task.due_date) return '';
  const due = new Date(task.due_date);
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const tomorrow = new Date(today); tomorrow.setDate(tomorrow.getDate() + 1);
  if (due < today) return 'Due yesterday';
  if (due < tomorrow) return 'Due today';
  return `Due ${due.toLocaleDateString([], { month: 'short', day: 'numeric' })}`;
}

export default function TouchpointsScreen() {
  const { colors } = useThemeStore();
  const router = useRouter();
  const { period: periodParam } = useLocalSearchParams<{ period?: string }>();
  const user = useAuthStore((s) => s.user);
  const [tasks, setTasks] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeFilter, setActiveFilter] = useState('All');

  const loadData = useCallback(async () => {
    if (!user?._id) return;
    setLoading(true);
    try {
      const [t, s] = await Promise.all([
        tasksAPI.getFiltered(user._id, 'today', 100),
        tasksAPI.getSummary(user._id),
      ]);
      setTasks(Array.isArray(t) ? t : []);
      setSummary(s);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [user?._id]);

  useFocusEffect(useCallback(() => { loadData(); }, [loadData]));

  const completeTask = async (taskId: string) => {
    if (!user?._id) return;
    try {
      await tasksAPI.patchTask(user._id, taskId, { action: 'complete' });
      setTasks(prev => prev.filter(t => t._id !== taskId));
      setSummary((s: any) => s ? { ...s, completed_today: s.completed_today + 1, pending_today: Math.max(0, s.pending_today - 1), progress_pct: Math.round(((s.completed_today + 1) / Math.max(s.total_today, 1)) * 100) } : s);
    } catch { showSimpleAlert('Error', 'Failed to complete task'); }
  };

  const snoozeTask = async (taskId: string) => {
    if (!user?._id) return;
    try {
      await tasksAPI.patchTask(user._id, taskId, { action: 'snooze', snooze_hours: 24 });
      setTasks(prev => prev.filter(t => t._id !== taskId));
    } catch { showSimpleAlert('Error', 'Failed to snooze task'); }
  };

  const handleCall = async (task: any) => {
    const phone = task.contact_phone;
    if (!phone) { showSimpleAlert('No Number', 'No phone number available.'); return; }
    // Log call_placed event before opening dialer
    if (user?._id && task.contact_id) {
      try {
        await contactsAPI.logEvent(user._id, task.contact_id, {
          event_type: 'call_placed',
          title: 'Outbound Call',
          description: `Called ${task.contact_name || phone}`,
          channel: 'call',
          category: 'message',
          icon: 'call',
          color: '#32ADE6',
        });
      } catch {}
    }
    const url = `tel:${phone.replace(/[^\d+]/g, '')}`;
    IS_WEB ? (window.location.href = url) : Linking.openURL(url);
    // Auto-complete after initiating the call
    completeTask(task._id);
  };

  const handleText = async (task: any) => {
    const phone = task.contact_phone;
    if (!phone) { showSimpleAlert('No Number', 'No phone number for this contact.'); return; }

    // Get the clean message for pre-fill (strip campaign prefix, replace template vars)
    let cleanMessage = task.suggested_message || task.description || '';
    // Strip "Campaign '...' step X:" prefix if present
    cleanMessage = cleanMessage.replace(/^Campaign\s+'[^']*'\s+step\s+\d+:\s*/i, '');
    // Replace template variables with actual contact data
    const firstName = (task.contact_name || '').split(' ')[0] || 'there';
    const lastName = (task.contact_name || '').split(' ').slice(1).join(' ') || '';
    cleanMessage = cleanMessage.replace(/\{name\}/gi, firstName);
    cleanMessage = cleanMessage.replace(/\{first_name\}/gi, firstName);
    cleanMessage = cleanMessage.replace(/\{last_name\}/gi, lastName);
    cleanMessage = cleanMessage.replace(/\{contact_name\}/gi, task.contact_name || '');

    // Build query params for the contact page composer
    const params: any = {};
    if (cleanMessage) params.prefill = cleanMessage;
    params.taskId = task._id;

    // If we already have a contact_id, go directly to their page
    if (task.contact_id) {
      const qs = new URLSearchParams(params).toString();
      router.push(`/contact/${task.contact_id}?${qs}` as any);
      return;
    }

    // No contact_id — look up by phone number first
    try {
      const res = await api.get(`/contacts/${user!._id}/check-duplicate`, { params: { phone } });
      const matches = res.data?.matches || [];
      if (matches.length > 0) {
        // Found the contact — navigate to their page
        const qs = new URLSearchParams(params).toString();
        router.push(`/contact/${matches[0].id}?${qs}` as any);
        return;
      }
    } catch {}

    // Contact not in CRM — create contact via find-or-create, then log the event
    try {
      const createRes = await api.post(`/contacts/${user!._id}/find-or-create-and-log`, {
        phone,
        name: task.contact_name || phone,
        event_type: 'sms_sent',
        event_title: 'SMS Sent',
        event_description: `Texted ${task.contact_name || phone}`,
        event_icon: 'chatbubble',
        event_color: '#007AFF',
      });
    } catch {}
    // Open native SMS app with message pre-filled
    if (IS_WEB && typeof window !== 'undefined') {
      const ua = window.navigator.userAgent.toLowerCase();
      const isIos = /iphone|ipad|ipod/.test(ua);
      const sep = isIos ? '&' : '?';
      const smsUrl = `sms:${encodeURIComponent(phone)}${sep}body=${encodeURIComponent(cleanMessage)}`;
      window.open(smsUrl, '_self');
    } else {
      const smsUrl = `sms:${phone.replace(/[^\d+]/g, '')}`;
      Linking.openURL(smsUrl);
    }
    // Auto-complete the task
    completeTask(task._id);
  };

  // Filter tasks client-side
  const filtered = tasks.filter(t => {
    if (activeFilter === 'All') return true;
    if (activeFilter === 'Overdue') return isOverdue(t);
    if (activeFilter === 'Campaigns') return t.source === 'campaign';
    if (activeFilter === 'Birthdays') return t.type === 'birthday';
    if (activeFilter === 'Follow-ups') return t.type === 'follow_up';
    return true;
  });

  // Group into overdue and today
  const overdueTasks = filtered.filter(t => isOverdue(t));
  const todayTasks = filtered.filter(t => !isOverdue(t));

  // Filter counts
  const filterCounts: Record<string, number> = {
    All: tasks.length,
    Overdue: tasks.filter(t => isOverdue(t)).length,
    Campaigns: tasks.filter(t => t.source === 'campaign').length,
    Birthdays: tasks.filter(t => t.type === 'birthday').length,
    'Follow-ups': tasks.filter(t => t.type === 'follow_up').length,
  };

  const act = summary?.activity || {};
  const scoreValues: Record<string, number> = {
    calls: act.calls || 0, texts: act.texts || 0, emails: act.emails || 0,
    cards: act.cards || 0, reviews: act.reviews || 0,
    clicks: act.clicks || 0, opens: act.opens || 0, replies: act.replies || 0, new_leads: act.new_leads || 0,
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      {/* Header */}
      <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 0.5, borderBottomColor: colors.border }} data-testid="touchpoints-header">
        <TouchableOpacity onPress={() => router.back()} style={{ padding: 4, marginRight: 8 }} data-testid="touchpoints-back-btn">
          <Ionicons name="chevron-back" size={24} color={colors.accent} />
        </TouchableOpacity>
        <Text style={{ fontSize: 18, fontWeight: '700', color: colors.text, flex: 1 }}>Today's Touchpoints</Text>
        <TouchableOpacity onPress={() => router.push('/touchpoints/add-task' as any)} style={{ padding: 4 }} data-testid="touchpoints-add-btn">
          <Ionicons name="add-circle-outline" size={24} color={colors.accent} />
        </TouchableOpacity>
      </View>

      {loading ? (
        <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      ) : (
        <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingBottom: 80 }} showsVerticalScrollIndicator={false}>
          {/* Scoreboard */}
          <View style={{ paddingTop: 16, paddingBottom: 12 }}>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: 16, gap: 6 }}>
              {SCORE_ITEMS_ACTIONS.map(s => (
                <View key={s.key} style={{ width: 68, backgroundColor: colors.card, borderRadius: 12, padding: 10, alignItems: 'center', borderWidth: 1, borderColor: colors.border }}>
                  <Text style={{ fontSize: 20, fontWeight: '700', color: s.color }}>{scoreValues[s.key]}</Text>
                  <Text style={{ fontSize: 9, color: colors.textSecondary, fontWeight: '600', letterSpacing: 0.3, marginTop: 1 }}>{s.label}</Text>
                </View>
              ))}
              <View style={{ width: 1, backgroundColor: colors.border, marginHorizontal: 4 }} />
              {SCORE_ITEMS_ENGAGE.map(s => (
                <View key={s.key} style={{ width: 68, backgroundColor: colors.card, borderRadius: 12, padding: 10, alignItems: 'center', borderWidth: 1, borderColor: colors.border }}>
                  <Text style={{ fontSize: 20, fontWeight: '700', color: s.color }}>{scoreValues[s.key]}</Text>
                  <Text style={{ fontSize: 9, color: colors.textSecondary, fontWeight: '600', letterSpacing: 0.3, marginTop: 1 }}>{s.label}</Text>
                </View>
              ))}
            </ScrollView>
            <Text style={{ textAlign: 'center', fontSize: 10, color: '#3A3A3C', marginTop: 4 }}>swipe for engagement stats</Text>
          </View>

          {/* Progress */}
          <View style={{ paddingHorizontal: 16, paddingBottom: 14 }}>
            <View style={{ backgroundColor: colors.border, borderRadius: 5, height: 8, overflow: 'hidden', marginBottom: 6 }}>
              <View style={{ height: '100%', backgroundColor: colors.accent, borderRadius: 5, width: `${summary?.progress_pct || 0}%` }} />
            </View>
            <Text style={{ fontSize: 12, color: colors.textSecondary, textAlign: 'center' }}>
              {summary?.completed_today || 0} of {summary?.total_today || 0} touchpoints completed
            </Text>
          </View>

          {/* My Performance Card */}
          <TouchableOpacity
            onPress={() => router.push(`/touchpoints/performance${periodParam ? `?period=${periodParam}` : ''}` as any)}
            style={{ flexDirection: 'row', alignItems: 'center', gap: 14, marginHorizontal: 16, marginBottom: 8, backgroundColor: colors.card, borderRadius: 14, padding: 14, paddingHorizontal: 16, borderWidth: 1, borderColor: colors.border }}
            activeOpacity={0.8}
            data-testid="my-performance-link"
          >
            <View style={{ width: 40, height: 40, borderRadius: 12, backgroundColor: 'rgba(52,199,89,0.12)', alignItems: 'center', justifyContent: 'center' }}>
              <Ionicons name="stats-chart" size={20} color="#34C759" />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 15, fontWeight: '600', color: colors.text }}>My Performance</Text>
              <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }}>Day / Week / Month stats + click-throughs</Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color="#48484A" />
          </TouchableOpacity>

          {/* Customer Performance Card */}
          <TouchableOpacity
            onPress={() => router.push('/touchpoints/customer-performance' as any)}
            style={{ flexDirection: 'row', alignItems: 'center', gap: 14, marginHorizontal: 16, marginBottom: 14, backgroundColor: colors.card, borderRadius: 14, padding: 14, paddingHorizontal: 16, borderWidth: 1, borderColor: colors.border }}
            activeOpacity={0.8}
            data-testid="customer-performance-link"
          >
            <View style={{ width: 40, height: 40, borderRadius: 12, backgroundColor: 'rgba(255,149,0,0.12)', alignItems: 'center', justifyContent: 'center' }}>
              <Ionicons name="people" size={20} color="#FF9500" />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 15, fontWeight: '600', color: colors.text }}>Customer Performance</Text>
              <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }}>Ranked engagement across your contacts</Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color="#48484A" />
          </TouchableOpacity>

          {/* Filters */}
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: 16, gap: 8, paddingBottom: 14 }}>
            {FILTERS.map(f => {
              const isActive = f === activeFilter;
              return (
                <TouchableOpacity
                  key={f}
                  onPress={() => setActiveFilter(f)}
                  style={{
                    paddingVertical: 6, paddingHorizontal: 14, borderRadius: 20, borderWidth: 1,
                    backgroundColor: isActive ? 'rgba(201,169,98,0.1)' : colors.card,
                    borderColor: isActive ? 'rgba(201,169,98,0.4)' : colors.border,
                  }}
                  data-testid={`filter-${f.toLowerCase()}`}
                >
                  <Text style={{ fontSize: 13, fontWeight: '600', color: isActive ? colors.accent : colors.textSecondary }}>
                    {f} ({filterCounts[f] || 0})
                  </Text>
                </TouchableOpacity>
              );
            })}
          </ScrollView>

          {/* Overdue Section */}
          {overdueTasks.length > 0 && (
            <>
              <Text style={{ fontSize: 11, fontWeight: '700', color: '#48484A', letterSpacing: 1.5, textTransform: 'uppercase', paddingHorizontal: 16, paddingTop: 8, paddingBottom: 6 }}>Overdue</Text>
              {overdueTasks.map(task => <TaskCard key={task._id} task={task} colors={colors} onComplete={completeTask} onSnooze={snoozeTask} onCall={handleCall} onText={handleText} />)}
            </>
          )}

          {/* Today Section */}
          {todayTasks.length > 0 && (
            <>
              <Text style={{ fontSize: 11, fontWeight: '700', color: '#48484A', letterSpacing: 1.5, textTransform: 'uppercase', paddingHorizontal: 16, paddingTop: 8, paddingBottom: 6 }}>Today</Text>
              {todayTasks.map(task => <TaskCard key={task._id} task={task} colors={colors} onComplete={completeTask} onSnooze={snoozeTask} onCall={handleCall} onText={handleText} />)}
            </>
          )}

          {filtered.length === 0 && (
            <View style={{ alignItems: 'center', paddingVertical: 40 }}>
              <Ionicons name="checkmark-done-circle-outline" size={48} color={colors.textTertiary} />
              <Text style={{ fontSize: 16, fontWeight: '600', color: colors.textSecondary, marginTop: 12 }}>All caught up!</Text>
              <Text style={{ fontSize: 13, color: colors.textTertiary, marginTop: 4 }}>No touchpoints for today</Text>
            </View>
          )}
        </ScrollView>
      )}

      {/* FAB */}
      <TouchableOpacity
        onPress={() => router.push('/touchpoints/add-task' as any)}
        style={{ position: 'absolute', bottom: 24, right: 24, width: 52, height: 52, borderRadius: 26, backgroundColor: colors.accent, alignItems: 'center', justifyContent: 'center', elevation: 4, shadowColor: colors.accent, shadowOpacity: 0.3, shadowRadius: 16, shadowOffset: { width: 0, height: 4 } }}
        activeOpacity={0.8}
        data-testid="touchpoints-fab"
      >
        <Ionicons name="add" size={26} color="#000" />
      </TouchableOpacity>
    </SafeAreaView>
  );
}

function TaskCard({ task, colors, onComplete, onSnooze, onCall, onText }: {
  task: any; colors: any; onComplete: (id: string) => void; onSnooze: (id: string) => void; onCall: (t: any) => void; onText: (t: any) => void;
}) {
  const overdue = isOverdue(task);
  const highPri = task.priority === 'high' && !overdue;
  const avatar = getAvatarColor(task);
  const badges = getBadges(task);
  const dueLabel = getDueLabel(task);
  const initials = getInitials(task.contact_name);

  // Determine which action buttons to show
  const showCall = task.action_type === 'call' || task.type === 'follow_up' || task.type === 'birthday' || overdue;
  const showText = true;
  const textLabel = task.source === 'campaign' ? 'Send Text' : 'Text';

  return (
    <View
      style={{
        marginHorizontal: 16, marginBottom: 10, backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: colors.border, overflow: 'hidden',
        borderLeftWidth: overdue ? 3 : highPri ? 3 : 1,
        borderLeftColor: overdue ? '#FF3B30' : highPri ? '#FF9500' : colors.border,
      }}
      data-testid={`task-card-${task._id}`}
    >
      {/* Top */}
      <View style={{ flexDirection: 'row', alignItems: 'flex-start', padding: 14, gap: 12 }}>
        <View style={{ width: 42, height: 42, borderRadius: 12, backgroundColor: avatar.bg, alignItems: 'center', justifyContent: 'center' }}>
          <Text style={{ fontWeight: '700', fontSize: 15, color: avatar.text }}>{initials}</Text>
        </View>
        <View style={{ flex: 1, minWidth: 0 }}>
          <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text }}>{task.contact_name || 'Unknown'}</Text>
          <Text style={{ fontSize: 13, color: '#AEAEB2', marginTop: 2 }} numberOfLines={2}>{task.description || task.title}</Text>
          <View style={{ flexDirection: 'row', gap: 6, marginTop: 6, alignItems: 'center', flexWrap: 'wrap' }}>
            {badges.map((b, i) => (
              <View key={i} style={{ backgroundColor: b.bg, paddingVertical: 3, paddingHorizontal: 8, borderRadius: 6 }}>
                <Text style={{ fontSize: 10, fontWeight: '700', color: b.color }}>{b.label}</Text>
              </View>
            ))}
            {dueLabel ? <Text style={{ fontSize: 11, color: '#636366' }}>{dueLabel}</Text> : null}
          </View>
        </View>
      </View>

      {/* Suggested Message */}
      {task.suggested_message ? (
        <View style={{ paddingHorizontal: 14, paddingBottom: 12 }}>
          <View style={{ backgroundColor: 'rgba(255,255,255,0.04)', borderRadius: 10, padding: 10, paddingHorizontal: 12 }}>
            <Text style={{ fontSize: 10, color: '#636366', fontWeight: '600', letterSpacing: 0.5, marginBottom: 3 }}>SUGGESTED MESSAGE</Text>
            <Text style={{ fontSize: 13, color: '#8E8E93', lineHeight: 18 }}>{task.suggested_message}</Text>
          </View>
        </View>
      ) : null}

      {/* Actions */}
      <View style={{ flexDirection: 'row', borderTopWidth: 1, borderTopColor: colors.border }}>
        {showCall && (
          <TouchableOpacity onPress={() => onCall(task)} style={{ flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 5, paddingVertical: 11, borderRightWidth: 1, borderRightColor: colors.border }} data-testid={`task-call-${task._id}`}>
            <Ionicons name="call" size={16} color="#007AFF" />
            <Text style={{ fontSize: 12, fontWeight: '600', color: '#007AFF' }}>Call</Text>
          </TouchableOpacity>
        )}
        {showText && (
          <TouchableOpacity onPress={() => onText(task)} style={{ flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 5, paddingVertical: 11, borderRightWidth: 1, borderRightColor: colors.border }} data-testid={`task-text-${task._id}`}>
            <Ionicons name="chatbubble" size={16} color="#34C759" />
            <Text style={{ fontSize: 12, fontWeight: '600', color: '#34C759' }}>{textLabel}</Text>
          </TouchableOpacity>
        )}
        <TouchableOpacity onPress={() => onComplete(task._id)} style={{ flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 5, paddingVertical: 11, borderRightWidth: 1, borderRightColor: colors.border }} data-testid={`task-done-${task._id}`}>
          <Ionicons name="checkmark-circle" size={16} color="#C9A962" />
          <Text style={{ fontSize: 12, fontWeight: '600', color: '#C9A962' }}>Done</Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={() => onSnooze(task._id)} style={{ flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 5, paddingVertical: 11 }} data-testid={`task-snooze-${task._id}`}>
          <Ionicons name="time-outline" size={16} color="#8E8E93" />
          <Text style={{ fontSize: 12, fontWeight: '600', color: '#8E8E93' }}>Snooze</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}
