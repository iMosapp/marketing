import React, { useRef } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Swipeable, RectButton } from 'react-native-gesture-handler';
import { WebSwipeableItem, wasRecentSwipe } from '../WebSwipeableItem';
import { useThemeStore } from '../../store/themeStore';

const GOLD = '#C9A962';
const RED = '#FF3B30';
const GRAY = '#8E8E93';

export interface AlertItem {
  id: string;
  type: string;
  bucket: 'now' | 'today' | 'later';
  title: string;
  context?: string;
  body?: string;
  link?: string | null;
  action?: { label: string; icon: string; link?: string | null } | null;
  contact_name?: string | null;
  contact_id?: string;
  demo_request_id?: string;
  timestamp: string;
  read: boolean;
}

const BUCKET_COLOR: Record<string, string> = { now: RED, today: GOLD, later: GRAY };

const TYPE_ICON: Record<string, string> = {
  you_are_needed: 'chatbubble', customer_reply: 'chatbubble', call_retry_replied: 'chatbubble',
  slow_lead: 'flash', ai_draft_approval_required: 'sparkles', jump_ball: 'hand-left',
  new_lead: 'person-add', lead_assigned: 'person-add', lead_reassigned: 'swap-horizontal',
  keyword_alert: 'key', engagement_signal: 'flame', new_demo_request: 'person-add',
  appointment_extracted: 'calendar', task_reminder: 'alarm', manager_nudge: 'megaphone',
  task_overdue: 'alert-circle', task_due_soon: 'time',
};

export function formatAlertTime(iso: string) {
  try {
    const d = new Date(iso);
    const diff = Date.now() - d.getTime();
    if (diff < 60000) return 'now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h`;
    if (diff < 7 * 86400000) return `${Math.floor(diff / 86400000)}d`;
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch { return ''; }
}

interface Props {
  item: AlertItem;
  onOpen: (item: AlertItem) => void;
  onDismiss: (item: AlertItem) => void;
}

export function AlertRow({ item, onOpen, onDismiss }: Props) {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const swipeRef = useRef<Swipeable>(null);
  const tint = BUCKET_COLOR[item.bucket] || GRAY;
  const icon = item.action?.icon || TYPE_ICON[item.type] || 'notifications';
  const context = item.context || item.body || item.contact_name || '';

  const row = (
    <TouchableOpacity
      style={[styles.row, !item.read && { borderLeftColor: tint }, item.read && { opacity: 0.72 }]}
      onPress={() => { if (Platform.OS === 'web' && wasRecentSwipe()) return; onOpen(item); }}
      activeOpacity={0.75}
      testID={`alert-row-${item.id}`}
      {...({ dataSet: { testid: `alert-row-${item.id}` } } as any)}
    >
      <View style={[styles.iconWrap, { backgroundColor: tint + '22' }]}>
        <Ionicons name={icon as any} size={17} color={tint} />
      </View>
      <View style={{ flex: 1, minWidth: 0 }}>
        <Text maxFontSizeMultiplier={1} style={styles.title} numberOfLines={1}>{item.title}</Text>
        {context ? (
          <Text maxFontSizeMultiplier={1} style={styles.context} numberOfLines={2}>{context}</Text>
        ) : null}
        <Text maxFontSizeMultiplier={1} style={styles.time}>{formatAlertTime(item.timestamp)}</Text>
      </View>
      {item.action ? (
        <TouchableOpacity
          style={styles.actionBtn}
          onPress={() => onOpen(item)}
          hitSlop={{ top: 6, bottom: 6, left: 4, right: 4 }}
          testID={`alert-action-${item.id}`}
          {...({ dataSet: { testid: `alert-action-${item.id}` } } as any)}
        >
          <Text maxFontSizeMultiplier={1} style={styles.actionText}>{item.action.label}</Text>
        </TouchableOpacity>
      ) : (
        <Ionicons name="chevron-forward" size={18} color={colors.textTertiary} />
      )}
    </TouchableOpacity>
  );

  if (Platform.OS === 'web') {
    return (
      <View style={styles.swipeWrap}>
        <WebSwipeableItem
          rightActions={[{ key: `dismiss-${item.id}`, icon: 'close', label: 'Dismiss', color: '#fff', bgColor: RED, onPress: () => onDismiss(item) }]}
        >
          {row}
        </WebSwipeableItem>
      </View>
    );
  }

  return (
    <View style={styles.swipeWrap}>
      <Swipeable
        ref={swipeRef}
        friction={2}
        rightThreshold={48}
        overshootRight={false}
        onSwipeableOpen={(dir) => { if (dir === 'right') { swipeRef.current?.close(); onDismiss(item); } }}
        renderRightActions={() => (
          <RectButton style={styles.dismissPane} onPress={() => { swipeRef.current?.close(); onDismiss(item); }}>
            <Ionicons name="close" size={22} color="#fff" />
            <Text maxFontSizeMultiplier={1} style={styles.dismissText}>Dismiss</Text>
          </RectButton>
        )}
      >
        {row}
      </Swipeable>
    </View>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  swipeWrap: { marginHorizontal: 16, marginBottom: 8, borderRadius: 16, overflow: 'hidden' },
  row: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    backgroundColor: colors.card, borderRadius: 16,
    paddingHorizontal: 12, paddingVertical: 12,
    borderLeftWidth: 3, borderLeftColor: 'transparent',
  },
  iconWrap: { width: 36, height: 36, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 15, fontWeight: '700', color: colors.text },
  context: { fontSize: 13, color: colors.textSecondary, lineHeight: 17, marginTop: 2 },
  time: { fontSize: 11, color: colors.textTertiary, marginTop: 3 },
  actionBtn: { backgroundColor: GOLD, borderRadius: 14, paddingHorizontal: 13, paddingVertical: 8, minWidth: 64, alignItems: 'center' },
  actionText: { fontSize: 13, fontWeight: '800', color: '#000' },
  dismissPane: { width: 88, backgroundColor: RED, alignItems: 'center', justifyContent: 'center', gap: 3 },
  dismissText: { color: '#fff', fontSize: 12, fontWeight: '700' },
});

export default AlertRow;
