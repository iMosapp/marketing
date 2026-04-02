import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ActivityIndicator, Modal, ScrollView, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useThemeStore } from '../store/themeStore';
import api from '../services/api';
import { format, formatDistanceToNow, isPast, parseISO } from 'date-fns';
import * as Clipboard from 'expo-clipboard';
import { showSimpleAlert, showAlert } from '../services/alert';

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
  enrollment_id?: string;
  campaign_id?: string;
  pending_send_id?: string;
  full_message?: string;
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
  enrollment_id: string;
  steps: StepInfo[];
}

interface Props {
  userId: string;
  contactId: string;
  onEnrollmentRemoved?: () => void;
  onPrePopulateComposer?: (message: string) => void;  // Pre-fills SMS composer instead of copying
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

export default function CampaignJourney({ userId, contactId, onEnrollmentRemoved, onPrePopulateComposer }: Props) {
  const { colors } = useThemeStore();
  const [journeys, setJourneys] = useState<Journey[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [selectedStep, setSelectedStep] = useState<StepInfo | null>(null);
  const [marking, setMarking] = useState(false);
  const [removing, setRemoving] = useState<string | null>(null);

  const loadJourneys = useCallback(async () => {
    try {
      const res = await api.get(`/contacts/${userId}/${contactId}/campaign-journey`);
      setJourneys(res.data);
      // Collapsed by default — user explicitly taps to expand
    } catch (e) {
      console.error('Failed to load campaign journeys:', e);
    } finally {
      setLoading(false);
    }
  }, [userId, contactId]);

  useEffect(() => { loadJourneys(); }, [loadJourneys]);

  if (loading) return (
    <View style={[s.loadingWrap, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <ActivityIndicator size="small" color={colors.textSecondary} />
    </View>
  );

  if (journeys.length === 0) return null;

  const toggleExpand = (idx: number) => {
    setExpanded(prev => ({ ...prev, [idx]: !prev[idx] }));
  };

  const handleStepTap = (step: StepInfo) => {
    if (step.status === 'pending_send' || step.status === 'next') {
      setSelectedStep(step);
    }
  };

  const handleSendMessage = () => {
    if (!selectedStep) return;
    const msg = selectedStep.full_message || selectedStep.message;
    setSelectedStep(null);  // Close the step modal
    if (onPrePopulateComposer) {
      onPrePopulateComposer(msg);  // Drop message into SMS composer bar
    }
  };

  const handleMarkSent = async () => {
    if (!selectedStep?.enrollment_id) return;
    setMarking(true);
    try {
      await api.post(`/contacts/${userId}/${contactId}/campaign-journey/mark-sent`, {
        enrollment_id: selectedStep.enrollment_id,
        step: selectedStep.step,
        pending_send_id: selectedStep.pending_send_id || '',
      });
      setSelectedStep(null);
      await loadJourneys();
    } catch (e) {
      console.error('Mark sent failed:', e);
      showSimpleAlert('Error', 'Failed to mark as sent');
    }
    setMarking(false);
  };

  const handleRemoveCampaign = async (journey: Journey) => {
    showAlert(
      'Remove Campaign',
      `Remove "${journey.campaign_name}" from this contact? History will be archived. Any pending sends will be cancelled.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Remove',
          style: 'destructive',
          onPress: async () => {
            setRemoving(journey.enrollment_id);
            try {
              await api.post(`/contacts/${userId}/${contactId}/campaign-journey/remove`, {
                enrollment_id: journey.enrollment_id,
              });
              await loadJourneys();
              showSimpleAlert('Done', `"${journey.campaign_name}" removed. You can re-add it anytime.`);
              onEnrollmentRemoved?.(); // Refresh parent's enrollment list so campaign reappears in picker
            } catch (e) {
              console.error('Remove campaign failed:', e);
              showSimpleAlert('Error', 'Failed to remove campaign');
            } finally {
              setRemoving(null);
            }
          },
        },
      ]
    );
  };

  const stepMessage = selectedStep?.full_message || selectedStep?.message || '';

  return (
    <View style={s.wrapper} data-testid="campaign-journey-section">
      <View style={s.headerRow}>
        <Ionicons name="rocket" size={16} color="#AF52DE" />
        <Text style={[s.headerText, { color: colors.text }]}>Campaign Journey</Text>
        <Text style={[s.headerCount, { color: colors.textSecondary }]}>{journeys.length}</Text>
      </View>

      {journeys.map((journey, jIdx) => {
        const isExpanded = expanded[jIdx];
        const sentCount = journey.steps.filter(st => st.status === 'sent').length;
        const pendingCount = journey.steps.filter(st => st.status === 'pending_send').length;
        const progressPct = journey.total_steps > 0 ? (sentCount / journey.total_steps) * 100 : 0;
        const isActive = journey.status === 'active';
        const accentColor = isActive ? '#007AFF' : '#34C759';

        return (
          <View key={jIdx} style={[s.card, { backgroundColor: colors.card, borderColor: colors.border }]} data-testid={`journey-card-${jIdx}`}>
            {/* Campaign header — tappable to expand/collapse */}
            <TouchableOpacity onPress={() => toggleExpand(jIdx)} activeOpacity={0.7} style={s.cardHeader}>
              <View style={s.cardHeaderLeft}>
                <View style={[s.statusDot, { backgroundColor: accentColor }]} />
                <View style={{ flex: 1 }}>
                  <Text style={[s.campaignName, { color: colors.text }]} numberOfLines={1}>
                    {journey.campaign_name}
                  </Text>
                  <View style={s.metaRow}>
                    <Text style={[s.metaText, { color: colors.textSecondary }]}>
                      {isActive ? `${sentCount}/${journey.total_steps} sent` : 'Completed'}
                    </Text>
                    {pendingCount > 0 && (
                      <View style={s.pendingBadge}>
                        <Text style={s.pendingBadgeText}>{pendingCount} to send</Text>
                      </View>
                    )}
                    {journey.ai_enabled && (
                      <View style={s.aiBadge}>
                        <Ionicons name="sparkles" size={10} color="#FFD60A" />
                        <Text style={s.aiBadgeText}>AI</Text>
                      </View>
                    )}
                  </View>
                </View>
              </View>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <TouchableOpacity
                  data-testid={`remove-campaign-${jIdx}`}
                  onPress={() => handleRemoveCampaign(journey)}
                  hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
                  disabled={removing === journey.enrollment_id}
                  style={s.removeBtn}
                >
                  {removing === journey.enrollment_id ? (
                    <ActivityIndicator size="small" color="#FF3B30" />
                  ) : (
                    <Ionicons name="trash-outline" size={16} color="#FF3B30" />
                  )}
                </TouchableOpacity>
                <Ionicons name={isExpanded ? 'chevron-up' : 'chevron-down'} size={18} color={colors.textSecondary} />
              </View>
            </TouchableOpacity>

            {/* Progress bar */}
            <View style={[s.progressBg, { backgroundColor: colors.background }]}>
              <View style={[s.progressFill, { width: `${progressPct}%`, backgroundColor: accentColor }]} />
            </View>

            {/* Expanded step timeline */}
            {isExpanded && (
              <View style={s.timeline} data-testid={`journey-timeline-${jIdx}`}>
                {journey.steps.map((step, sIdx) => {
                  const isSent = step.status === 'sent';
                  const isPending = step.status === 'pending_send';
                  const isNext = step.status === 'next';
                  const isTappable = isPending || isNext;
                  const stepColor = isSent ? '#34C759' : (isPending || isNext) ? '#FF9500' : colors.textTertiary || '#666';
                  const isLast = sIdx === journey.steps.length - 1;

                  const StepWrapper = isTappable ? TouchableOpacity : View;
                  const wrapperProps = isTappable ? { onPress: () => handleStepTap(step), activeOpacity: 0.6 } : {};

                  return (
                    <StepWrapper key={sIdx} style={s.timelineStep} {...wrapperProps} data-testid={`journey-step-${jIdx}-${sIdx}`}>
                      <View style={s.timelineLeft}>
                        <View style={[s.timelineDot, { backgroundColor: stepColor, borderColor: isSent ? '#34C75940' : (isPending || isNext) ? '#FF950040' : `${colors.border}` }]} />
                        {!isLast && (
                          <View style={[s.timelineLine, { backgroundColor: isSent ? '#34C75930' : colors.border }]} />
                        )}
                      </View>
                      <View style={[s.timelineContent, (isPending || isNext) && s.timelineContentActive, (isPending || isNext) && { borderColor: '#FF950040', backgroundColor: '#FF950008' }]}>
                        <View style={s.stepHeaderRow}>
                          <Text style={[s.stepLabel, { color: stepColor }]}>
                            {isSent ? 'Sent' : isPending ? 'Ready to Send' : isNext ? 'Next Up' : step.scheduled_at ? `Sends ${new Date(step.scheduled_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}` : `Step ${step.step}`}
                          </Text>
                          <View style={s.stepMeta}>
                            <Ionicons name={step.channel === 'email' ? 'mail' : 'chatbubble'} size={11} color={colors.textTertiary || '#666'} />
                            {!isSent && !isPending && <Text style={[s.delayText, { color: colors.textTertiary || '#666' }]}>{formatDelay(step)}</Text>}
                            {isTappable && <Ionicons name="chevron-forward" size={14} color="#FF9500" style={{ marginLeft: 4 }} />}
                          </View>
                        </View>
                        <Text style={[s.stepMessage, { color: isSent ? colors.textSecondary : colors.text }]} numberOfLines={2}>
                          {step.step_context || step.message.slice(0, 80) + (step.message.length > 80 ? '...' : '')}
                        </Text>
                        {isSent && step.sent_at && (
                          <Text style={[s.timestamp, { color: colors.textTertiary || '#666' }]}>
                            {format(parseISO(step.sent_at), 'MMM d, h:mm a')}
                          </Text>
                        )}
                        {isPending && (
                          <Text style={[s.timestamp, { color: '#FF9500' }]}>Tap to send or mark as sent</Text>
                        )}
                        {isNext && step.scheduled_at && (
                          <Text style={[s.timestamp, { color: '#FF9500' }]}>
                            {formatScheduledTime(step.scheduled_at)}
                          </Text>
                        )}
                      </View>
                    </StepWrapper>
                  );
                })}
              </View>
            )}
          </View>
        );
      })}

      {/* Step Action Modal */}
      <Modal visible={!!selectedStep} animationType="slide" presentationStyle="pageSheet" transparent>
        <View style={s.modalOverlay}>
          <View style={[s.modalContainer, { backgroundColor: colors.card }]}>
            <View style={[s.modalHeader, { borderBottomColor: colors.surface }]}>
              <TouchableOpacity onPress={() => setSelectedStep(null)} data-testid="modal-close-btn">
                <Text style={s.modalClose}>Close</Text>
              </TouchableOpacity>
              <Text style={[s.modalTitle, { color: colors.text }]} numberOfLines={1}>
                Step {selectedStep?.step}
              </Text>
              <View style={{ width: 50 }} />
            </View>

            <ScrollView style={s.modalBody}>
              {selectedStep?.step_context ? (
                <Text style={[s.modalContext, { color: colors.textSecondary }]}>{selectedStep.step_context}</Text>
              ) : null}
              <View style={[s.messageBox, { backgroundColor: colors.surface }]}>
                <Text style={[s.messageText, { color: colors.text }]}>{stepMessage}</Text>
              </View>
              <Text style={[s.channelLabel, { color: colors.textSecondary }]}>
                via {selectedStep?.channel?.toUpperCase() || 'SMS'}
              </Text>
            </ScrollView>

            <View style={[s.modalActions, { borderTopColor: colors.surface }]}>
              {Platform.OS === 'web' ? (
                <>
                  <button
                    type="button"
                    data-testid="send-message-btn"
                    onClick={() => handleSendMessage()}
                    style={{
                      flex: 1, padding: 14, borderRadius: 12, border: 'none',
                      backgroundColor: '#007AFF', cursor: 'pointer',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                    }}
                  >
                    <Text style={s.actionBtnText}>Send Message</Text>
                  </button>
                  <button
                    type="button"
                    data-testid="mark-sent-btn"
                    disabled={marking}
                    onClick={() => handleMarkSent()}
                    style={{
                      flex: 1, padding: 14, borderRadius: 12, border: 'none',
                      backgroundColor: '#34C759', cursor: marking ? 'not-allowed' : 'pointer',
                      opacity: marking ? 0.6 : 1,
                      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                    }}
                  >
                    {marking ? (
                      <ActivityIndicator size="small" color="#fff" />
                    ) : (
                      <Text style={s.actionBtnText}>Mark as Sent</Text>
                    )}
                  </button>
                </>
              ) : (
                <>
                  <TouchableOpacity style={[s.actionBtn, { backgroundColor: '#007AFF' }]} onPress={handleSendMessage} data-testid="send-message-btn">
                    <Ionicons name="chatbubble-outline" size={18} color="#fff" />
                    <Text style={s.actionBtnText}>Send Message</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={[s.actionBtn, { backgroundColor: '#34C759' }]} onPress={handleMarkSent} disabled={marking} data-testid="mark-sent-btn">
                    {marking ? <ActivityIndicator size="small" color="#fff" /> : <Ionicons name="checkmark-circle" size={18} color="#fff" />}
                    <Text style={s.actionBtnText}>Mark as Sent</Text>
                  </TouchableOpacity>
                </>
              )}
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const s = StyleSheet.create({
  wrapper: { paddingHorizontal: 16, marginBottom: 12 },
  loadingWrap: { padding: 16, borderRadius: 12, borderWidth: 1 },
  headerRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8 },
  headerText: { fontSize: 17, fontWeight: '700' },
  headerCount: { fontSize: 14, fontWeight: '600', marginLeft: 'auto' },
  card: { borderRadius: 12, borderWidth: 1, marginBottom: 8, overflow: 'hidden' },
  cardHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 12, paddingBottom: 8 },
  cardHeaderLeft: { flexDirection: 'row', alignItems: 'center', gap: 10, flex: 1 },
  removeBtn: { padding: 4 },
  statusDot: { width: 8, height: 8, borderRadius: 4 },
  campaignName: { fontSize: 16, fontWeight: '700' },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 2 },
  metaText: { fontSize: 14 },
  pendingBadge: { backgroundColor: '#FF950020', paddingHorizontal: 6, paddingVertical: 1, borderRadius: 4 },
  pendingBadgeText: { fontSize: 12, fontWeight: '700', color: '#FF9500' },
  aiBadge: { flexDirection: 'row', alignItems: 'center', gap: 2, backgroundColor: '#FFD60A15', paddingHorizontal: 5, paddingVertical: 1, borderRadius: 4 },
  aiBadgeText: { fontSize: 12, fontWeight: '700', color: '#FFD60A' },
  progressBg: { height: 3, marginHorizontal: 12 },
  progressFill: { height: 3, borderRadius: 2 },
  timeline: { paddingHorizontal: 12, paddingBottom: 12, paddingTop: 8 },
  timelineStep: { flexDirection: 'row', minHeight: 48 },
  timelineLeft: { width: 20, alignItems: 'center' },
  timelineDot: { width: 10, height: 10, borderRadius: 5, borderWidth: 2, marginTop: 4 },
  timelineLine: { width: 1.5, flex: 1, marginVertical: 2 },
  timelineContent: { flex: 1, marginLeft: 8, marginBottom: 10, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8 },
  timelineContentActive: { borderWidth: 1, borderRadius: 8 },
  stepHeaderRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2 },
  stepLabel: { fontSize: 13, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5 },
  stepMeta: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  delayText: { fontSize: 12, fontWeight: '600' },
  stepMessage: { fontSize: 14, lineHeight: 17 },
  timestamp: { fontSize: 12, marginTop: 3 },

  // Modal
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  modalContainer: { borderTopLeftRadius: 20, borderTopRightRadius: 20, maxHeight: '80%' },
  modalHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 16, borderBottomWidth: 1 },
  modalClose: { fontSize: 18, color: '#007AFF', fontWeight: '500' },
  modalTitle: { fontSize: 18, fontWeight: '600' },
  modalBody: { padding: 16 },
  modalContext: { fontSize: 15, marginBottom: 12, lineHeight: 18 },
  messageBox: { padding: 16, borderRadius: 12, marginBottom: 8 },
  messageText: { fontSize: 17, lineHeight: 22 },
  channelLabel: { fontSize: 14, marginBottom: 12 },
  modalActions: { flexDirection: 'row', gap: 10, padding: 16, borderTopWidth: 1 },
  actionBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, padding: 14, borderRadius: 12 },
  actionBtnText: { color: '#fff', fontSize: 17, fontWeight: '600' },
});
