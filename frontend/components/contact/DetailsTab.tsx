/**
 * DetailsTab — voice memos, personal intel, purchases, dates, referrals & campaigns.
 * Extracted from contact/[id].tsx (render-only; all state lives in the parent).
 */
import React from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator, Switch } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { format } from 'date-fns';
import { formatEventTime } from '../../utils/contactHelpers';
import PersonalIntelSection from '../PersonalIntelSection';
import PurchaseHistorySection from './PurchaseHistorySection';

export default function DetailsTab(props: any) {
  const {
    s, colors, contact, contactId, userId, isNewContact,
    voiceNotes, voiceNotesLoading, isRecording, recordingTime, uploadingVoiceNote,
    playingNoteId, showAllNotes, startRecording, stopRecording, playVoiceNote,
    deleteVoiceNote, formatRecordingTime, maxRecordingSeconds,
    referrals, contactEnrollments, toggleDateOptin,
  } = props;
  const router = useRouter();

  return (
    <>
      {/* Voice Notes — full history, all visible */}
      <View style={[s.section, { paddingTop: 4 }]} data-testid="voice-notes-section">
          <View style={s.sectionHeaderRow}>
            <View style={{ flex: 1 }}>
              <Text style={s.sectionHeader}>Relationship Voice Memos</Text>
              <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }}>
                Spouse · Kids · Pets · Hobbies · What matters to them
              </Text>
            </View>
            <Text style={s.sectionHeaderCount}>{voiceNotes.length}</Text>
          </View>

          {isRecording ? (
            <View style={s.vnRecording} data-testid="voice-recording-indicator">
              <View style={s.vnRecordingDot} />
              <Text style={s.vnRecordingTime}>{formatRecordingTime(recordingTime)}</Text>
              <Text style={s.vnRecordingLimit}>/ {formatRecordingTime(maxRecordingSeconds)}</Text>
              <TouchableOpacity style={s.vnStopBtn} onPress={stopRecording} data-testid="stop-recording-btn">
                <Ionicons name="stop" size={18} color={colors.text} />
                <Text style={s.vnStopText}>Stop</Text>
              </TouchableOpacity>
            </View>
          ) : uploadingVoiceNote ? (
            <View style={s.vnRecording}>
              <ActivityIndicator size="small" color="#34C759" />
              <Text style={[s.vnRecordingTime, { marginLeft: 8 }]}>Saving & transcribing...</Text>
            </View>
          ) : (
            <TouchableOpacity style={s.vnRecordBtn} onPress={startRecording} data-testid="start-recording-btn">
              <Ionicons name="mic" size={20} color="#34C759" />
              <Text style={s.vnRecordText}>Record a Voice Note</Text>
            </TouchableOpacity>
          )}

          {voiceNotesLoading ? (
            <ActivityIndicator size="small" color="#C9A962" style={{ marginTop: 12 }} />
          ) : voiceNotes.length > 0 ? (
            <View style={{ marginTop: 12 }}>
              {(showAllNotes ? voiceNotes : voiceNotes.slice(0, 1)).map((note: any, i: number) => {
                const isPlaying = playingNoteId === note.id;
                return (
                  <View key={note.id} style={s.vnCard} data-testid={`voice-note-${i}`}>
                    <View style={s.vnCardHeader}>
                      <TouchableOpacity
                        style={[s.vnPlayBtn, isPlaying && s.vnPlayBtnActive]}
                        onPress={() => playVoiceNote(note.id, note.audio_url)}
                        data-testid={`play-voice-note-${i}`}
                      >
                        <Ionicons name={isPlaying ? 'pause' : 'play'} size={16} color={isPlaying ? '#000' : '#34C759'} />
                      </TouchableOpacity>
                      <View style={{ flex: 1, marginLeft: 10 }}>
                        <Text style={s.vnCardDate}>{formatEventTime(note.created_at)}</Text>
                        <Text style={s.vnCardDuration}>{formatRecordingTime(Math.round(note.duration))}</Text>
                      </View>
                      <TouchableOpacity
                        onPress={(e: any) => {
                          e.stopPropagation?.();
                          deleteVoiceNote(note.id);
                        }}
                        style={{ padding: 12, margin: -8, zIndex: 10 }}
                        hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
                        data-testid={`delete-voice-note-${i}`}
                      >
                        <Ionicons name="trash-outline" size={18} color="#FF3B30" />
                      </TouchableOpacity>
                    </View>
                    {note.transcript ? (
                      <Text style={s.vnTranscript}>
                        {note.transcript}
                      </Text>
                    ) : (
                      <Text style={[s.vnTranscript, { fontStyle: 'italic', color: colors.textTertiary }]}>Transcribing...</Text>
                    )}
                    {note.transcript && (
                      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 6 }}>
                        <Ionicons name="sparkles" size={11} color="#AF52DE" />
                        <Text style={{ fontSize: 11, color: '#AF52DE', fontStyle: 'italic' }}>AI has learned from this memo</Text>
                      </View>
                    )}
                  </View>
                );
              })}
            </View>
          ) : null}
        </View>

      {/* Personal Intelligence (from voice memo extraction) */}
      <PersonalIntelSection contactId={contactId} userId={userId} colors={colors} />

      {/* Purchase History */}
      {!isNewContact && (
        <PurchaseHistorySection
          contactId={contactId}
          userId={userId}
          colors={colors}
        />
      )}

      {/* Notes (editable view in details) */}
      {contact.notes ? (
        <View style={s.section}>
          <Text style={s.sectionHeader}>Notes</Text>
          <Text style={s.viewText}>{contact.notes}</Text>
        </View>
      ) : null}

      {/* Important Dates */}
      {(contact.birthday || contact.anniversary || contact.date_sold || contact.custom_dates.length > 0) && (
        <View style={s.section}>
          <Text style={s.sectionHeader}>Important Dates</Text>
          {contact.birthday && (
            <View style={s.viewRow}>
              <Ionicons name="gift" size={16} color="#FF9500" />
              <Text style={s.viewRowLabel}>Birthday</Text>
              <Text style={s.viewRowValue}>{format(contact.birthday, 'MMM d, yyyy')}</Text>
            </View>
          )}
          {contact.anniversary && (
            <View style={s.viewRow}>
              <Ionicons name="heart" size={16} color="#FF2D55" />
              <Text style={s.viewRowLabel}>Anniversary</Text>
              <Text style={s.viewRowValue}>{format(contact.anniversary, 'MMM d, yyyy')}</Text>
            </View>
          )}
          {contact.date_sold && (
            <View style={s.viewRow}>
              <Ionicons name="car" size={16} color="#34C759" />
              <Text style={s.viewRowLabel}>Date Sold</Text>
              <Text style={s.viewRowValue}>{format(contact.date_sold, 'MMM d, yyyy')}</Text>
            </View>
          )}
          {contact.custom_dates.map((cd: any, i: number) => cd.date && (
            <View key={i} style={s.viewRow}>
              <Ionicons name="calendar-outline" size={16} color="#007AFF" />
              <Text style={s.viewRowLabel}>{cd.name}</Text>
              <Text style={s.viewRowValue}>{format(cd.date, 'MMM d, yyyy')}</Text>
            </View>
          ))}

          {/* Opt-in toggles: date sends fire ONLY when these are ON */}
          {(() => {
            const tl = (contact.tags || []).map((t: string) => (t || '').toLowerCase());
            const bOn = tl.includes('birthday');
            const aOn = tl.includes('anniversary');
            return (
              <View style={{ marginTop: 10, paddingTop: 10, borderTopWidth: 1, borderTopColor: 'rgba(128,128,128,0.15)' }}>
                {contact.birthday && (
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 6 }} data-testid="birthday-optin-row">
                    <Ionicons name={bOn ? 'notifications' : 'notifications-off'} size={16} color={bOn ? '#34C759' : '#8E8E93'} />
                    <View style={{ flex: 1 }}>
                      <Text style={s.viewRowLabel} numberOfLines={1}>Birthday text + card</Text>
                      <Text style={{ fontSize: 11, color: '#8E8E93' }} numberOfLines={1}>
                        {bOn ? 'Sends automatically on their birthday' : 'OFF — nothing sends'}
                      </Text>
                    </View>
                    <Switch
                      value={bOn}
                      onValueChange={(v: boolean) => toggleDateOptin('birthday', v)}
                      trackColor={{ false: 'rgba(128,128,128,0.3)', true: '#34C75966' }}
                      thumbColor={bOn ? '#34C759' : '#f4f3f4'}
                      data-testid="birthday-optin-switch"
                    />
                  </View>
                )}
                {(contact.date_sold || contact.anniversary) && (
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 6 }} data-testid="anniversary-optin-row">
                    <Ionicons name={aOn ? 'notifications' : 'notifications-off'} size={16} color={aOn ? '#34C759' : '#8E8E93'} />
                    <View style={{ flex: 1 }}>
                      <Text style={s.viewRowLabel} numberOfLines={1}>Anniversary text + card</Text>
                      <Text style={{ fontSize: 11, color: '#8E8E93' }} numberOfLines={1}>
                        {aOn ? 'Sends yearly with their car photo' : 'OFF — nothing sends'}
                      </Text>
                    </View>
                    <Switch
                      value={aOn}
                      onValueChange={(v: boolean) => toggleDateOptin('anniversary', v)}
                      trackColor={{ false: 'rgba(128,128,128,0.3)', true: '#34C75966' }}
                      thumbColor={aOn ? '#34C759' : '#f4f3f4'}
                      data-testid="anniversary-optin-switch"
                    />
                  </View>
                )}
              </View>
            );
          })()}
        </View>
      )}

      {/* Referrals */}
      {(contact.referred_by_name || referrals.length > 0) && (
        <View style={s.section}>
          <Text style={s.sectionHeader}>Referrals</Text>
          {contact.referred_by_name && (
            <View style={s.viewRow}>
              <Ionicons name="people" size={16} color="#34C759" />
              <Text style={s.viewRowLabel}>Referred by</Text>
              <Text style={s.viewRowValue}>{contact.referred_by_name}</Text>
            </View>
          )}
          {contact.referral_count > 0 && (
            <View style={s.viewRow}>
              <Ionicons name="trophy" size={16} color="#FF9500" />
              <Text style={s.viewRowLabel}>Referred</Text>
              <Text style={s.viewRowValue}>{contact.referral_count} customer{contact.referral_count > 1 ? 's' : ''}</Text>
            </View>
          )}
          {referrals.map((r: any) => (
            <TouchableOpacity key={r._id} style={s.referralItem} onPress={() => router.push(`/contact/${r._id}`)}>
              <View style={s.referralAvatar}><Text style={s.referralAvatarText}>{r.first_name?.[0]}{r.last_name?.[0]}</Text></View>
              <Text style={s.referralName}>{r.first_name} {r.last_name || ''}</Text>
              <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
            </TouchableOpacity>
          ))}
        </View>
      )}

      {/* Campaigns */}
      {contactEnrollments.length > 0 && (
        <View style={s.section}>
          <Text style={s.sectionHeader}>Campaigns</Text>
          {contactEnrollments.map((e: any, i: number) => (
            <View key={i} style={s.campaignCard}>
              <View style={[s.quickActionIcon, { backgroundColor: e.status === 'completed' ? '#34C75920' : '#007AFF20' }]}>
                <Ionicons name={e.status === 'completed' ? 'checkmark-circle' : 'play-circle'} size={18}
                  color={e.status === 'completed' ? '#34C759' : '#007AFF'} />
              </View>
              <View style={{ flex: 1, marginLeft: 12 }}>
                <Text style={s.campaignName}>{e.campaign_name}</Text>
                <Text style={s.campaignSub}>
                  {e.status === 'completed' ? 'Completed' : `Step ${e.current_step} of ${e.total_steps}`}
                </Text>
              </View>
            </View>
          ))}
        </View>
      )}
    </>
  );
}
