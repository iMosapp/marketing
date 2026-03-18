import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useThemeStore } from '../store/themeStore';
import api from '../services/api';
import { format, formatDistanceToNow, isPast, parseISO } from 'date-fns';

interface StepInfo {
  step: number;
  message: string;
  channel: string;
  delay_hours: number;
  delay_days: number;
  delay_months: number;
  ai_generated: boolean;
  step_context: string;
  status: 'sent' | 'pending_send' | 'next' | 'upcoming';
  sent_at?: string;
  queued_at?: string;
  scheduled_at?: string;
}

interface Journey {
  campaign_name: string;
  campaign_type: string;
  trigger_tag: string;
  ai_enabled: boolean;
  status: string;
  current_step: number;
  total_steps: number;
  enrolled_at: string;
  next_send_at: string | null;
  steps: StepInfo[];
}

interface Props {
  userId: string;
  contactId: string;
}

function formatDelay(s: StepInfo): string {
  const parts: string[] = [];
  if (s.delay_months) parts.push(`${s.delay_months}mo`);
  if (s.delay_days) parts.push(`${s.delay_days}d`);
  if (s.delay_hours) parts.push(`${s.delay_hours}h`);
  return parts.length > 0 ? `+${parts.join(' ')}` : 'Immediate';
}

function formatScheduledTime(iso: string): string {
  try {
    const date = parseISO(iso);
    if (isPast(date)) return 'Due now';
    return formatDistanceToNow(date, { addSuffix: true });
  } catch {
    return '';
  }
}

export default function CampaignJourney({ userId, contactId }: Props) {
  const { colors } = useThemeStore();
  const [journeys, setJourneys] = useState<Journey[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  useEffect(() => {
    loadJourneys();
  }, [userId, contactId]);

  const loadJourneys = async () => {
    try {
      const res = await api.get(`/contacts/${userId}/${contactId}/campaign-journey`);
      setJourneys(res.data);
      // Auto-expand active campaigns
      const exp: Record<string, boolean> = {};
      res.data.forEach((j: Journey, i: number) => {
        if (j.status === 'active') exp[i] = true;
      });
      setExpanded(exp);
    } catch (e) {
      console.error('Failed to load campaign journeys:', e);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <View style={[styles.container, { backgroundColor: colors.card, borderColor: colors.border }]}>
        <ActivityIndicator size="small" color={colors.textSecondary} />
      </View>
    );
  }

  if (journeys.length === 0) return null;

  const toggleExpand = (idx: number) => {
    setExpanded(prev => ({ ...prev, [idx]: !prev[idx] }));
  };

  return (
    <View style={styles.wrapper} data-testid="campaign-journey-section">
      <View style={styles.headerRow}>
        <Ionicons name="rocket" size={16} color="#AF52DE" />
        <Text style={[styles.headerText, { color: colors.text }]}>Campaign Journey</Text>
        <Text style={[styles.headerCount, { color: colors.textSecondary }]}>{journeys.length}</Text>
      </View>

      {journeys.map((journey, jIdx) => {
        const isExpanded = expanded[jIdx];
        const progress = journey.steps.filter(s => s.status === 'sent').length;
        const pendingCount = journey.steps.filter(s => s.status === 'pending_send').length;
        const progressPct = journey.total_steps > 0 ? (progress / journey.total_steps) * 100 : 0;
        const isActive = journey.status === 'active';
        const accentColor = isActive ? '#007AFF' : '#34C759';
        const nextStep = journey.steps.find(s => s.status === 'next');

        return (
          <View key={jIdx} style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]} data-testid={`journey-card-${jIdx}`}>
            {/* Campaign header — tappable to expand/collapse */}
            <TouchableOpacity onPress={() => toggleExpand(jIdx)} activeOpacity={0.7} style={styles.cardHeader}>
              <View style={styles.cardHeaderLeft}>
                <View style={[styles.statusDot, { backgroundColor: accentColor }]} />
                <View style={{ flex: 1 }}>
                  <Text style={[styles.campaignName, { color: colors.text }]} numberOfLines={1}>
                    {journey.campaign_name}
                  </Text>
                  <View style={styles.metaRow}>
                    <Text style={[styles.metaText, { color: colors.textSecondary }]}>
                      {isActive ? `Step ${journey.current_step} of ${journey.total_steps}` : 'Completed'}
                    </Text>
                    {journey.ai_enabled && (
                      <View style={styles.aiBadge}>
                        <Ionicons name="sparkles" size={10} color="#FFD60A" />
                        <Text style={styles.aiBadgeText}>AI</Text>
                      </View>
                    )}
                  </View>
                </View>
              </View>
              <Ionicons name={isExpanded ? 'chevron-up' : 'chevron-down'} size={18} color={colors.textSecondary} />
            </TouchableOpacity>

            {/* Progress bar */}
            <View style={[styles.progressBg, { backgroundColor: colors.background }]}>
              <View style={[styles.progressFill, { width: `${progressPct}%`, backgroundColor: accentColor }]} />
            </View>

            {/* Next up preview (always visible if active) */}
            {isActive && nextStep && !isExpanded && (
              <View style={[styles.nextUpPreview, { borderTopColor: colors.border }]}>
                <Ionicons name="time-outline" size={14} color="#FF9500" />
                <Text style={[styles.nextUpText, { color: colors.textSecondary }]} numberOfLines={1}>
                  Next: {nextStep.step_context || nextStep.message.slice(0, 40) + (nextStep.message.length > 40 ? '...' : '')}
                  {nextStep.scheduled_at ? ` — ${formatScheduledTime(nextStep.scheduled_at)}` : ''}
                </Text>
              </View>
            )}

            {/* Expanded step timeline */}
            {isExpanded && (
              <View style={styles.timeline} data-testid={`journey-timeline-${jIdx}`}>
                {journey.steps.map((step, sIdx) => {
                  const isSent = step.status === 'sent';
                  const isPendingSend = step.status === 'pending_send';
                  const isNext = step.status === 'next';
                  const stepColor = isSent ? '#34C759' : isPendingSend ? '#FF9500' : isNext ? '#FF9500' : colors.textTertiary || '#666';
                  const isLast = sIdx === journey.steps.length - 1;

                  return (
                    <View key={sIdx} style={styles.timelineStep} data-testid={`journey-step-${jIdx}-${sIdx}`}>
                      {/* Timeline connector line */}
                      <View style={styles.timelineLeft}>
                        <View style={[styles.timelineDot, { backgroundColor: stepColor, borderColor: isSent ? '#34C75940' : (isPendingSend || isNext) ? '#FF950040' : `${colors.border}` }]} />
                        {!isLast && (
                          <View style={[styles.timelineLine, { backgroundColor: isSent ? '#34C75930' : colors.border }]} />
                        )}
                      </View>

                      {/* Step content */}
                      <View style={[styles.timelineContent, (isNext || isPendingSend) && styles.timelineContentNext, (isNext || isPendingSend) && { borderColor: '#FF950040', backgroundColor: '#FF950008' }]}>
                        <View style={styles.stepHeaderRow}>
                          <Text style={[styles.stepLabel, { color: stepColor }]}>
                            {isSent ? 'Sent' : isPendingSend ? 'Ready to Send' : isNext ? 'Next' : `Step ${step.step}`}
                          </Text>
                          <View style={styles.stepMeta}>
                            <Ionicons name={step.channel === 'email' ? 'mail' : 'chatbubble'} size={11} color={colors.textTertiary || '#666'} />
                            {!isSent && !isPendingSend && <Text style={[styles.delayText, { color: colors.textTertiary || '#666' }]}>{formatDelay(step)}</Text>}
                          </View>
                        </View>

                        <Text style={[styles.stepMessage, { color: isSent ? colors.textSecondary : colors.text }]} numberOfLines={2}>
                          {step.step_context ? step.step_context : step.message.slice(0, 80) + (step.message.length > 80 ? '...' : '')}
                        </Text>

                        {/* Timestamp */}
                        {isSent && step.sent_at && (
                          <Text style={[styles.timestamp, { color: colors.textTertiary || '#666' }]}>
                            {format(parseISO(step.sent_at), 'MMM d, h:mm a')}
                          </Text>
                        )}
                        {isPendingSend && (
                          <Text style={[styles.timestamp, { color: '#FF9500' }]}>
                            In your Today's Touchpoints
                          </Text>
                        )}
                        {isNext && step.scheduled_at && (
                          <Text style={[styles.timestamp, { color: '#FF9500' }]}>
                            Scheduled {formatScheduledTime(step.scheduled_at)}
                          </Text>
                        )}
                      </View>
                    </View>
                  );
                })}
              </View>
            )}
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: { paddingHorizontal: 16, marginBottom: 12 },
  headerRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8 },
  headerText: { fontSize: 15, fontWeight: '700' },
  headerCount: { fontSize: 12, fontWeight: '600', marginLeft: 'auto' },
  container: { padding: 16, borderRadius: 12, borderWidth: 1 },
  card: { borderRadius: 12, borderWidth: 1, marginBottom: 8, overflow: 'hidden' },
  cardHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 12, paddingBottom: 8 },
  cardHeaderLeft: { flexDirection: 'row', alignItems: 'center', gap: 10, flex: 1 },
  statusDot: { width: 8, height: 8, borderRadius: 4 },
  campaignName: { fontSize: 14, fontWeight: '700' },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 2 },
  metaText: { fontSize: 12 },
  aiBadge: { flexDirection: 'row', alignItems: 'center', gap: 2, backgroundColor: '#FFD60A15', paddingHorizontal: 5, paddingVertical: 1, borderRadius: 4 },
  aiBadgeText: { fontSize: 10, fontWeight: '700', color: '#FFD60A' },
  progressBg: { height: 3, marginHorizontal: 12 },
  progressFill: { height: 3, borderRadius: 2 },
  nextUpPreview: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 8, borderTopWidth: 0.5 },
  nextUpText: { fontSize: 12, flex: 1 },
  timeline: { paddingHorizontal: 12, paddingBottom: 12, paddingTop: 8 },
  timelineStep: { flexDirection: 'row', minHeight: 48 },
  timelineLeft: { width: 20, alignItems: 'center' },
  timelineDot: { width: 10, height: 10, borderRadius: 5, borderWidth: 2, marginTop: 4 },
  timelineLine: { width: 1.5, flex: 1, marginVertical: 2 },
  timelineContent: { flex: 1, marginLeft: 8, marginBottom: 10, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8 },
  timelineContentNext: { borderWidth: 1, borderRadius: 8 },
  stepHeaderRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2 },
  stepLabel: { fontSize: 11, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5 },
  stepMeta: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  delayText: { fontSize: 10, fontWeight: '600' },
  stepMessage: { fontSize: 12, lineHeight: 17 },
  timestamp: { fontSize: 10, marginTop: 3 },
});
