/**
 * FeedTab — activity feed, suggested actions, intel pill & log-reply composer.
 * Extracted from contact/[id].tsx (render-only; all state lives in the parent).
 */
import React from 'react';
import { View, Text, TextInput, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Image } from 'expo-image';
import { useRouter } from 'expo-router';
import api, { messagesAPI } from '../../services/api';
import { showSimpleAlert } from '../../services/alert';
import { formatEventTime, EVENT_CATEGORY_ICON, getEventTitle } from '../../utils/contactHelpers';
import CampaignJourney from '../CampaignJourney';

export default function FeedTab(props: any) {
  const {
    s, colors, contact, user, contactId, isNewContact,
    suggestedActions, handleSuggestedAction,
    taskTitle, prefill,
    setSoldWorkflowResult, setShowSoldModal, loadContact, showToast,
    loadCampaignsAndEnrollments, setComposerMessage, setComposerMode,
    events, feedSearch, setFeedSearch, feedQuery, filteredEvents, eventDateGroups,
    eventsLoading, expandedEvents, setExpandedEvents,
    collapsedDateGroups, setCollapsedDateGroups,
    hasMoreEvents, loadMoreEvents, loadingMoreEvents,
    showLogReply, setShowLogReply, replyText, setReplyText,
    replyPhoto, setReplyPhoto, submittingReply, handleLogReply, pickReplyPhoto,
    setShowAddTask,
  } = props;
  const router = useRouter();

  return (
    <>
      {/* Suggested Actions (inline at top of feed) */}
      {suggestedActions.length > 0 && (
        <View style={[s.section, { paddingTop: 4 }]} data-testid="suggested-actions">
          {suggestedActions.map((action: any, i: number) => (
            <TouchableOpacity
              key={i}
              style={s.suggestedCard}
              onPress={() => handleSuggestedAction(action)}
              activeOpacity={0.7}
              data-testid={`suggested-action-${i}`}
            >
              <View style={[s.suggestedIcon, { backgroundColor: `${action.color}20` }]}>
                <Ionicons name={action.icon as any} size={20} color={action.color} />
              </View>
              <View style={{ flex: 1, marginLeft: 12 }}>
                <Text style={s.suggestedTitle}>{action.title}</Text>
                <Text style={s.suggestedDesc}>{action.description}</Text>
                {action.suggested_message && (
                  <View style={s.suggestedMsgPreview}>
                    <Text style={s.suggestedMsgText} numberOfLines={2}>"{action.suggested_message}"</Text>
                  </View>
                )}
              </View>
              <View style={[s.suggestedArrow, { backgroundColor: `${action.color}15` }]}>
                <Ionicons name="arrow-forward" size={16} color={action.color} />
              </View>
            </TouchableOpacity>
          ))}
        </View>
      )}

      {/* Pinned Notes (view-only, inside feed) */}
      {contact.notes ? (
        <View style={[s.section, { paddingTop: 0 }]} data-testid="pinned-notes">
          <View style={s.pinnedNote}>
            <Ionicons name="document-text" size={14} color="#C9A962" style={{ marginTop: 2 }} />
            <Text style={s.pinnedNoteText} numberOfLines={3}>{contact.notes}</Text>
          </View>
        </View>
      ) : null}

      {/* Task Context Banner — shows when navigating from a task notification */}
      {taskTitle ? (
        <View style={s.taskBanner} data-testid="task-context-banner">
          <View style={s.taskBannerIcon}>
            <Ionicons name="alert-circle" size={20} color="#FF9500" />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={s.taskBannerLabel}>Pending Task</Text>
            <Text style={s.taskBannerTitle}>{decodeURIComponent(taskTitle as string)}</Text>
            {prefill ? <Text style={s.taskBannerDesc} numberOfLines={2}>{decodeURIComponent(prefill as string)}</Text> : null}
          </View>
          <TouchableOpacity
            onPress={() => router.setParams({ taskTitle: '', taskId: '', prefill: '' })}
            style={s.taskBannerClose}
            data-testid="task-banner-dismiss"
          >
            <Ionicons name="close" size={16} color={colors.textSecondary} />
          </TouchableOpacity>
        </View>
      ) : null}

      {/* Sold Workflow Status */}
      {!isNewContact && contact.sold_workflow_status && contact.sold_workflow_status !== 'not_applicable' && (
        <View style={{ marginHorizontal: 16, marginBottom: 12, backgroundColor: colors.card, borderRadius: 12, padding: 14 }} data-testid="sold-workflow-status">
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <Ionicons 
                name={
                  contact.sold_workflow_status === 'delivery_success' ? 'checkmark-circle' :
                  contact.sold_workflow_status === 'delivery_pending' ? 'time' :
                  contact.sold_workflow_status === 'validation_failed' ? 'alert-circle' :
                  contact.sold_workflow_status === 'delivery_failed' ? 'close-circle' : 'help-circle'
                }
                size={20}
                color={
                  contact.sold_workflow_status === 'delivery_success' ? '#34C759' :
                  contact.sold_workflow_status === 'delivery_pending' ? '#FF9500' :
                  contact.sold_workflow_status === 'validation_failed' ? '#FF9500' :
                  '#FF3B30'
                }
              />
              <Text style={{ fontSize: 16, fontWeight: '600', color: colors.text }}>
                Sold Workflow: {contact.sold_workflow_status.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())}
              </Text>
            </View>
            {(contact.sold_workflow_status === 'validation_failed' || contact.sold_workflow_status === 'delivery_failed') && (
              <TouchableOpacity
                onPress={() => {
                  if (contact.sold_workflow_status === 'validation_failed') {
                    setSoldWorkflowResult({
                      status: 'validation_failed',
                      event_id: contact.sold_workflow_event_id,
                      missing_fields: contact.sold_validation_missing_fields || [],
                    });
                    setShowSoldModal(true);
                  } else {
                    // Manual retry for delivery_failed
                    api.post(`/sold-workflow/retry/${contact.sold_workflow_event_id}`, {}, { headers: { 'X-User-ID': user?._id } })
                      .then(() => { showToast('Delivery retry initiated'); loadContact(); })
                      .catch(() => showSimpleAlert('Error', 'Retry failed'));
                  }
                }}
                style={{ backgroundColor: '#FF950020', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8 }}
                data-testid="sold-workflow-retry-btn"
              >
                <Text style={{ fontSize: 14, fontWeight: '600', color: '#FF9500' }}>
                  {contact.sold_workflow_status === 'validation_failed' ? 'Fix & Complete' : 'Retry'}
                </Text>
              </TouchableOpacity>
            )}
          </View>
          {contact.sold_workflow_last_error && (
            <Text style={{ fontSize: 14, color: '#FF3B30', marginTop: 6 }}>
              {contact.sold_workflow_last_error}
            </Text>
          )}
        </View>
      )}

      {/* Campaign Journey — upcoming campaign activities */}
      {!isNewContact && user && (
        <CampaignJourney
          userId={user._id}
          contactId={contactId}
          onEnrollmentRemoved={loadCampaignsAndEnrollments}
          onPrePopulateComposer={(msg: string) => {
            setComposerMessage(msg);
            setComposerMode('sms');
          }}
        />
      )}

      {/* Relationship Feed (Activity) */}
      <View style={[s.section, { paddingTop: 0 }]} data-testid="activity-feed">
        <View style={s.sectionHeaderRow}>
          <Text style={s.sectionHeader}>Activity</Text>
          <Text style={s.sectionHeaderCount}>{events.length} events</Text>
        </View>

        {/* Feed Action Row */}
        <View style={s.feedActionRow}>
          <TouchableOpacity
            style={[s.logReplyBtn, { backgroundColor: '#FF950015', borderColor: '#FF950050' }]}
            onPress={() => setShowAddTask(true)}
            data-testid="add-task-btn"
          >
            <Ionicons name="add-circle" size={16} color="#FF9500" />
            <Text style={[s.logReplyBtnText, { color: '#FF9500' }]}>Add Task</Text>
          </TouchableOpacity>
          {events.length > 0 && (
            <View style={s.feedSearchRowCompact}>
              <Ionicons name="search" size={14} color={colors.textTertiary} />
              <TextInput
                style={s.feedSearchInputCompact}
                placeholder="Search..."
                placeholderTextColor={colors.textTertiary}
                value={feedSearch}
                onChangeText={setFeedSearch}
                data-testid="feed-search-input"
              />
              {feedSearch.length > 0 && (
                <TouchableOpacity onPress={() => setFeedSearch('')}>
                  <Ionicons name="close-circle" size={14} color={colors.textTertiary} />
                </TouchableOpacity>
              )}
            </View>
          )}
        </View>

        {/* Log Reply Inline Composer  - Chat Bubble Style */}
        {showLogReply && (
          <View style={s.logReplyBubble} data-testid="log-reply-composer">
            <View style={s.bubbleTail} />
            <View style={s.bubbleHeader}>
              <Ionicons name="arrow-down-circle" size={18} color="#30D158" />
              <Text style={s.bubbleHeaderText}>Customer said...</Text>
              <TouchableOpacity onPress={() => { setShowLogReply(false); setReplyText(''); setReplyPhoto(null); }} style={s.bubbleClose}>
                <Ionicons name="close-circle" size={22} color={colors.textTertiary} />
              </TouchableOpacity>
            </View>
            <View style={s.bubbleInputWrap}>
              <TextInput
                style={s.bubbleInput}
                placeholder="Paste what they said..."
                placeholderTextColor={colors.textTertiary}
                value={replyText}
                onChangeText={setReplyText}
                multiline
                data-testid="log-reply-input"
              />
            </View>
            {replyPhoto && (
              <View style={s.bubblePhotoPreview}>
                <Image source={{ uri: replyPhoto }} style={s.bubblePhotoThumb} contentFit="cover" />
                <TouchableOpacity style={s.bubblePhotoRemove} onPress={() => setReplyPhoto(null)}>
                  <Ionicons name="close-circle" size={22} color="#FF3B30" />
                </TouchableOpacity>
              </View>
            )}
            <View style={s.bubbleFooter}>
              <TouchableOpacity style={s.bubblePhotoBtn} onPress={pickReplyPhoto} data-testid="log-reply-photo-btn">
                <Ionicons name="image" size={20} color={colors.textTertiary} />
              </TouchableOpacity>
              <TouchableOpacity
                style={[s.bubbleSaveBtn, (!replyText.trim() && !replyPhoto) && { opacity: 0.35 }]}
                onPress={handleLogReply}
                disabled={(!replyText.trim() && !replyPhoto) || submittingReply}
                data-testid="log-reply-submit"
              >
                {submittingReply ? (
                  <ActivityIndicator size="small" color={colors.text} />
                ) : (
                  <>
                    <Text style={s.bubbleSaveText}>Save Reply</Text>
                    <Ionicons name="arrow-up-circle" size={22} color={colors.text} />
                  </>
                )}
              </TouchableOpacity>
            </View>
          </View>
        )}

        {eventsLoading ? (
          <ActivityIndicator size="small" color="#C9A962" style={{ marginTop: 16 }} />
        ) : filteredEvents.length === 0 ? (
          <View style={s.emptyFeed}>
            <Ionicons name={feedQuery ? 'search-outline' : 'time-outline'} size={36} color={colors.surface} />
            <Text style={s.emptyFeedText}>{feedQuery ? 'No matching events' : 'No activity yet'}</Text>
            <Text style={s.emptyFeedSub}>{feedQuery ? 'No results for "' + feedSearch + '"' : 'Send a message or enroll in a campaign to get started'}</Text>
          </View>
        ) : (
          <View style={s.feedTimeline}>
            {(() => {
              const ENGAGEMENT_SET = new Set(['digital_card_viewed', 'showcase_viewed', 'link_page_viewed', 'link_clicked', 'review_link_clicked', 'congrats_card_viewed', 'review_page_viewed', 'training_video_clicked']);
              const MILESTONE_SET = new Set(['new_contact_added', 'campaign_enrolled', 'review_submitted', 'referral_made']);
              return eventDateGroups.map((group: any) => {
              const isCollapsed = collapsedDateGroups[group.label] === true;
              const groupEvents = group.events; // Show ALL events — no artificial cap
              if (groupEvents.length === 0) return null;
              return (
                <View key={group.label}>
                  <TouchableOpacity
                    style={s.feedDateHeader}
                    onPress={() => setCollapsedDateGroups((prev: any) => ({ ...prev, [group.label]: !prev[group.label] }))}
                    activeOpacity={0.7}
                    data-testid={`feed-date-${group.label}`}
                  >
                    <View style={s.feedDateLine} />
                    <Text style={s.feedDateText}>{group.label}</Text>
                    <Text style={s.feedDateCount}>{group.events.length}</Text>
                    <Ionicons name={isCollapsed ? 'chevron-down' : 'chevron-up'} size={14} color={colors.textTertiary} />
                    <View style={s.feedDateLine} />
                  </TouchableOpacity>

                  {!isCollapsed && (
                    <View style={{ marginHorizontal: 4, marginBottom: 8, borderRadius: 14, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, overflow: 'hidden' }}>
                  {groupEvents.map((evt: any, i: number) => {
              const evtKey = `${group.label}-${i}`;
              const isExpanded = expandedEvents[evtKey] === true;
              const isInbound = evt.direction === 'inbound' || evt.event_type === 'customer_reply';
              const et = evt.event_type;
              const catStyle = EVENT_CATEGORY_ICON[evt.category] || EVENT_CATEGORY_ICON.custom;
              const isCustomerAction = ENGAGEMENT_SET.has(et) || isInbound || evt.category === 'customer_activity';

              // ── Clean, unified row (Activity-tab style) ────────────────
              const rowColor  = isCustomerAction ? '#34C759' : (MILESTONE_SET.has(et) ? '#C9A962' : '#007AFF');
              const rowIcon   = (evt.icon || catStyle.icon || (isInbound ? 'arrow-down-circle' : 'flag')) as any;

              // Clean label — no "Customer:" / "You:" prefix
              let cleanLabel = getEventTitle(evt);
              if (!cleanLabel) cleanLabel = et.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase());

              const hasDetail = !!(evt.description || evt.full_content);
              const isLast = i === groupEvents.length - 1;

              return (
                <TouchableOpacity
                  key={evtKey}
                  activeOpacity={hasDetail ? 0.6 : 1}
                  onPress={() => hasDetail && setExpandedEvents((prev: any) => ({ ...prev, [evtKey]: !prev[evtKey] }))}
                  style={{
                    flexDirection: 'row',
                    alignItems: 'center',
                    paddingVertical: 10,
                    paddingHorizontal: 8,
                    borderBottomWidth: isLast ? 0 : 0.5,
                    borderBottomColor: colors.border,
                  }}
                  data-testid={`feed-event-${evtKey}`}
                >
                  {/* Icon */}
                  <View style={{ width: 30, height: 30, borderRadius: 15, backgroundColor: rowColor + '18', alignItems: 'center', justifyContent: 'center', marginRight: 10, flexShrink: 0 }}>
                    <Ionicons name={rowIcon} size={14} color={rowColor} />
                  </View>

                  {/* Label + optional expanded content */}
                  <View style={{ flex: 1 }}>
                    <Text style={{ fontSize: 14, fontWeight: '500', color: colors.text }} numberOfLines={isExpanded ? undefined : 1}>
                      {cleanLabel}
                    </Text>
                    {isExpanded && hasDetail && (
                      <View style={{ marginTop: 6, padding: 10, borderRadius: 10, backgroundColor: colors.surface }}>
                        <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 19 }}>
                          {evt.full_content || evt.description}
                        </Text>
                        {evt.has_photo && (
                          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 4 }}>
                            <Ionicons name="image" size={13} color={rowColor} />
                            <Text style={{ fontSize: 12, color: rowColor }}>Photo attached</Text>
                          </View>
                        )}
                        {evt.link && (
                          <TouchableOpacity style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 6 }} onPress={() => router.push(evt.link as any)}>
                            <Ionicons name="open-outline" size={14} color="#007AFF" />
                            <Text style={{ fontSize: 13, fontWeight: '600', color: '#007AFF' }}>View Card</Text>
                          </TouchableOpacity>
                        )}
                      </View>
                    )}
                  </View>

                  {/* Time + optional expand chevron */}
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginLeft: 8 }}>
                    <Text style={{ fontSize: 12, color: colors.textTertiary }}>{formatEventTime(evt.timestamp)}</Text>
                    {hasDetail ? <Ionicons name={isExpanded ? 'chevron-up' : 'chevron-down'} size={12} color={colors.textTertiary} /> : null}
                  </View>
                </TouchableOpacity>
              );
            })}
                    </View>
                  )}
                </View>
              );
            });
            })()}
            {/* Load Older History button */}
            {hasMoreEvents && (
              <TouchableOpacity
                style={s.showMoreBtn}
                onPress={loadMoreEvents}
                disabled={loadingMoreEvents}
                data-testid="load-more-events-button"
              >
                {loadingMoreEvents ? (
                  <ActivityIndicator size="small" color="#007AFF" />
                ) : (
                  <>
                    <Ionicons name="time-outline" size={16} color="#007AFF" />
                    <Text style={s.showMoreText}>Load Older History</Text>
                  </>
                )}
              </TouchableOpacity>
            )}
          </View>
        )}
      </View>

      {/* Conversations Link */}
      <TouchableOpacity
        style={s.conversationLink}
        onPress={async () => {
          // Get the actual conversation ID (not contact ID) so thread loads messages correctly
          try {
            const conv = await messagesAPI.createConversation(user._id, {
              contact_id: contactId,
              contact_phone: contact?.phone || undefined,
            });
            const conversationId = conv._id || conv.id;
            router.push({
              pathname: `/thread/${conversationId}`,
              params: {
                contact_name: `${contact.first_name} ${contact.last_name || ''}`.trim(),
                contact_phone: contact.phone || '',
                contact_email: contact.email || contact.email_work || '',
              }
            });
          } catch {
            // Fallback to contact ID
            router.push({
              pathname: `/thread/${contactId}`,
              params: {
                contact_name: `${contact.first_name} ${contact.last_name || ''}`.trim(),
                contact_phone: contact.phone || '',
                contact_email: contact.email || contact.email_work || '',
              }
            });
          }
        }}
        data-testid="go-to-conversation"
      >
        <View style={[s.quickActionIcon, { backgroundColor: '#007AFF20' }]}>
          <Ionicons name="chatbubbles" size={20} color="#007AFF" />
        </View>
        <View style={{ flex: 1, marginLeft: 12 }}>
          <Text style={s.conversationLinkTitle}>View Conversation</Text>
          <Text style={s.conversationLinkSub}>Open full message thread</Text>
        </View>
        <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
      </TouchableOpacity>
    </>
  );
}
