import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, ScrollView, ActivityIndicator,
  TextInput, Image, StyleSheet, Linking,
} from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';

const EVENT_ICONS: Record<string, { icon: string; color: string }> = {
  // Salesperson outbound actions
  call_placed: { icon: 'call-outline', color: '#30D158' },
  call_made: { icon: 'call-outline', color: '#34C759' },
  personal_sms: { icon: 'chatbubble-outline', color: '#5856D6' },
  sms_sent: { icon: 'chatbubble-outline', color: '#5856D6' },
  email_sent: { icon: 'mail-outline', color: '#FF9500' },
  personal_email: { icon: 'mail-outline', color: '#FF9500' },
  message_outbound: { icon: 'chatbubble-outline', color: '#007AFF' },
  // Customer inbound signals
  call_received: { icon: 'call-outline', color: '#007AFF' },
  sms_received: { icon: 'chatbubble-outline', color: '#007AFF' },
  email_opened: { icon: 'mail-open-outline', color: '#34C759' },
  message_inbound: { icon: 'chatbubble-outline', color: '#8E8E93' },
  customer_reply: { icon: 'chatbubble-ellipses-outline', color: '#30D158' },
  // Cards & links
  congrats_card_sent: { icon: 'gift-outline', color: '#C9A962' },
  birthday_card_sent: { icon: 'gift-outline', color: '#FF9500' },
  holiday_card_sent: { icon: 'gift-outline', color: '#5AC8FA' },
  thankyou_card_sent: { icon: 'gift-outline', color: '#34C759' },
  thank_you_card_sent: { icon: 'gift-outline', color: '#34C759' },
  welcome_card_sent: { icon: 'gift-outline', color: '#007AFF' },
  anniversary_card_sent: { icon: 'heart-outline', color: '#FF2D55' },
  review_request_sent: { icon: 'star-outline', color: '#FFD60A' },
  review_link_shared: { icon: 'star-outline', color: '#FFD60A' },
  review_link_clicked: { icon: 'star', color: '#34C759' },
  review_submitted: { icon: 'star', color: '#FFD60A' },
  digital_card_sent: { icon: 'card-outline', color: '#007AFF' },
  digital_card_shared: { icon: 'card-outline', color: '#007AFF' },
  digital_card_viewed: { icon: 'eye-outline', color: '#007AFF' },
  congrats_card_viewed: { icon: 'eye-outline', color: '#C9A962' },
  birthday_card_viewed: { icon: 'eye-outline', color: '#FF9500' },
  thankyou_card_viewed: { icon: 'eye-outline', color: '#34C759' },
  holiday_card_viewed: { icon: 'eye-outline', color: '#5AC8FA' },
  welcome_card_viewed: { icon: 'eye-outline', color: '#007AFF' },
  anniversary_card_viewed: { icon: 'eye-outline', color: '#FF2D55' },
  review_page_viewed: { icon: 'eye-outline', color: '#FFD60A' },
  showcase_shared: { icon: 'images-outline', color: '#AF52DE' },
  showcase_viewed: { icon: 'eye-outline', color: '#AF52DE' },
  link_page_shared: { icon: 'link-outline', color: '#5856D6' },
  link_page_viewed: { icon: 'eye-outline', color: '#5856D6' },
  vcard_sent: { icon: 'person-outline', color: '#007AFF' },
  // Campaigns & broadcasts
  campaign_enrolled: { icon: 'rocket-outline', color: '#AF52DE' },
  campaign_message_sent: { icon: 'megaphone-outline', color: '#FF9500' },
  campaign_completed: { icon: 'checkmark-circle-outline', color: '#34C759' },
  broadcast_sent: { icon: 'megaphone-outline', color: '#FF2D55' },
  // Tasks & notes
  task_created: { icon: 'checkbox-outline', color: '#FF9500' },
  task_completed: { icon: 'checkmark-done-outline', color: '#34C759' },
  note_added: { icon: 'document-text-outline', color: '#8E8E93' },
  note_updated: { icon: 'document-text-outline', color: '#8E8E93' },
  voice_note: { icon: 'mic-outline', color: '#FF9500' },
  tag_applied: { icon: 'pricetag-outline', color: '#5856D6' },
  lead_created: { icon: 'person-add-outline', color: '#007AFF' },
  lead_reassigned: { icon: 'swap-horizontal-outline', color: '#C9A962' },
  new_contact: { icon: 'person-add-outline', color: '#007AFF' },
  new_contact_added: { icon: 'person-add-outline', color: '#007AFF' },
};

function getEventMeta(type: string) {
  return EVENT_ICONS[type] || { icon: 'ellipse-outline', color: '#8E8E93' };
}

function formatDate(iso: string) {
  if (!iso) return '';
  const d = new Date(iso);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  const days = Math.floor(diff / 86400000);
  if (days === 0) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days < 7) return `${days} days ago`;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: d.getFullYear() !== now.getFullYear() ? 'numeric' : undefined });
}

function formatTime(iso: string) {
  if (!iso) return '';
  return new Date(iso).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
}

function formatEventType(type: string) {
  return type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

// Group events by date
function groupByDate(events: any[]) {
  const groups: Record<string, any[]> = {};
  for (const e of events) {
    const d = e.timestamp ? new Date(e.timestamp).toISOString().split('T')[0] : 'unknown';
    if (!groups[d]) groups[d] = [];
    groups[d].push(e);
  }
  return Object.entries(groups).sort(([a], [b]) => b.localeCompare(a));
}

// ─── PIN Screen ──────────────────────────────────────────────────────

function PinScreen({ storeName, storeLogo, onVerify, error }: any) {
  const [pin, setPin] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    setLoading(true);
    await onVerify(pin);
    setLoading(false);
  };

  return (
    <View style={s.pinContainer}>
      {storeLogo ? (
        <Image source={{ uri: storeLogo }} style={s.pinLogo} resizeMode="contain" />
      ) : (
        <View style={s.pinIconWrap}>
          <Ionicons name="shield-checkmark-outline" size={48} color="#C9A962" />
        </View>
      )}
      <Text style={s.pinTitle}>Protected Timeline</Text>
      <Text style={s.pinSubtitle}>
        {storeName ? `Enter the PIN for ${storeName}` : 'Enter your store PIN to continue'}
      </Text>
      <TextInput
        style={s.pinInput}
        value={pin}
        onChangeText={setPin}
        placeholder="Enter PIN"
        placeholderTextColor="#666"
        keyboardType="number-pad"
        maxLength={8}
        secureTextEntry
        data-testid="crm-pin-input"
      />
      {error ? <Text style={s.pinError}>{error}</Text> : null}
      <TouchableOpacity
        style={[s.pinButton, (!pin || loading) && { opacity: 0.5 }]}
        onPress={handleSubmit}
        disabled={!pin || loading}
        data-testid="crm-pin-submit"
      >
        {loading ? <ActivityIndicator color="#000" /> : <Text style={s.pinButtonText}>Continue</Text>}
      </TouchableOpacity>
    </View>
  );
}

// ─── Main Timeline Page ──────────────────────────────────────────────

export default function TimelinePage() {
  const { token } = useLocalSearchParams<{ token: string }>();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [pinRequired, setPinRequired] = useState(false);
  const [pinMeta, setPinMeta] = useState<any>({});
  const [pinError, setPinError] = useState('');
  const [sessionToken, setSessionToken] = useState('');

  const loadTimeline = useCallback(async (pin?: string) => {
    if (!token) return;
    try {
      setLoading(true);
      const params: any = {};
      if (pin) params.pin = pin;
      if (sessionToken) params.pin = 'session'; // Will be handled differently

      // First check if we have a valid session
      if (sessionToken && !pin) {
        try {
          const sessionCheck = await api.get(`/crm/timeline/${token}/check-session?session=${sessionToken}`);
          if (sessionCheck.data?.valid) {
            // Session valid — load without PIN
            const res = await api.get(`/crm/timeline/${token}`);
            if (res.data?.pin_required) {
              // Need to pass PIN via session — re-fetch with stored session
              const res2 = await api.get(`/crm/timeline/${token}?pin=${sessionToken}`);
              setData(res2.data);
              setPinRequired(false);
              return;
            }
            setData(res.data);
            setPinRequired(false);
            return;
          }
        } catch {}
      }

      const res = await api.get(`/crm/timeline/${token}${pin ? `?pin=${pin}` : ''}`);

      if (res.data?.pin_required) {
        setPinRequired(true);
        setPinMeta(res.data);
        return;
      }

      setData(res.data);
      setPinRequired(false);
    } catch (err: any) {
      if (err?.response?.status === 403) {
        setPinError('Invalid PIN. Please try again.');
        setPinRequired(true);
      }
    } finally {
      setLoading(false);
    }
  }, [token, sessionToken]);

  useEffect(() => {
    // Check localStorage for session token
    try {
      const saved = typeof window !== 'undefined' ? localStorage.getItem(`crm_session_${token}`) : null;
      if (saved) setSessionToken(saved);
    } catch {}
  }, [token]);

  useEffect(() => {
    loadTimeline();
  }, [loadTimeline]);

  const handlePinVerify = async (pin: string) => {
    try {
      const res = await api.post(`/crm/timeline/${token}/verify-pin`, { pin });
      if (res.data?.verified) {
        const st = res.data.session_token || '';
        setSessionToken(st);
        if (st && typeof window !== 'undefined') {
          localStorage.setItem(`crm_session_${token}`, st);
        }
        await loadTimeline(pin);
      }
    } catch (err: any) {
      setPinError(err?.response?.data?.detail || 'Invalid PIN');
    }
  };

  if (loading && !pinRequired) {
    return (
      <View style={s.loadingWrap}>
        <ActivityIndicator size="large" color="#C9A962" />
        <Text style={s.loadingText}>Loading timeline...</Text>
      </View>
    );
  }

  if (pinRequired) {
    return (
      <PinScreen
        storeName={pinMeta.store_name}
        storeLogo={pinMeta.store_logo}
        onVerify={handlePinVerify}
        error={pinError}
      />
    );
  }

  if (!data) {
    return (
      <View style={s.loadingWrap}>
        <Ionicons name="alert-circle-outline" size={48} color="#FF3B30" />
        <Text style={s.loadingText}>Timeline not found</Text>
      </View>
    );
  }

  const { contact, salesperson, store, events, notes, total_events } = data;
  const grouped = groupByDate(events || []);
  const storeColor = store?.color || '#007AFF';

  // Count outbound (salesperson) vs inbound (customer) for stats
  const outboundCount = (events || []).filter((e: any) => e.direction === 'outbound').length;
  const inboundCount = (events || []).filter((e: any) => e.direction === 'inbound').length;

  return (
    <ScrollView style={s.page} data-testid="crm-timeline-page">
      {/* Header */}
      <View style={[s.header, { backgroundColor: storeColor }]}>
        {store?.logo ? (
          <Image source={{ uri: store.logo }} style={s.storeLogo} resizeMode="contain" />
        ) : null}
        <Text style={s.storeName}>{store?.name || ''}</Text>
      </View>

      {/* Contact Info */}
      <View style={s.contactCard}>
        <View style={s.contactRow}>
          {contact?.photo ? (
            <Image source={{ uri: contact.photo }} style={s.contactAvatar} />
          ) : (
            <View style={[s.contactAvatarPlaceholder, { backgroundColor: storeColor + '20' }]}>
              <Text style={[s.contactInitials, { color: storeColor }]}>
                {(contact?.name || '?').split(' ').map((w: string) => w[0]).join('').slice(0, 2).toUpperCase()}
              </Text>
            </View>
          )}
          <View style={s.contactInfo}>
            <Text style={s.contactName} data-testid="crm-contact-name">{contact?.name || 'Unknown'}</Text>
            {contact?.phone ? <Text style={s.contactDetail}>{contact.phone}</Text> : null}
            {contact?.email ? <Text style={s.contactDetail}>{contact.email}</Text> : null}
          </View>
        </View>
        {salesperson?.name ? (
          <View style={s.spRow}>
            <Ionicons name="person-outline" size={14} color="#8E8E93" />
            <Text style={s.spText}>Managed by {salesperson.name}{salesperson.title ? ` · ${salesperson.title}` : ''}</Text>
          </View>
        ) : null}
        {contact?.tags?.length > 0 ? (
          <View style={s.tagsRow}>
            {contact.tags.map((t: string, i: number) => (
              <View key={i} style={[s.tag, { backgroundColor: storeColor + '15', borderColor: storeColor + '30' }]}>
                <Text style={[s.tagText, { color: storeColor }]}>{t}</Text>
              </View>
            ))}
          </View>
        ) : null}
      </View>

      {/* Stats bar */}
      <View style={s.statsBar}>
        <View style={s.statItem}>
          <Text style={s.statNum}>{total_events || 0}</Text>
          <Text style={s.statLabel}>Total Activities</Text>
        </View>
        <View style={s.statDivider} />
        <View style={s.statItem}>
          <Text style={s.statNum}>{outboundCount}</Text>
          <Text style={s.statLabel}>Salesperson</Text>
        </View>
        <View style={s.statDivider} />
        <View style={s.statItem}>
          <Text style={s.statNum}>{inboundCount}</Text>
          <Text style={s.statLabel}>Customer</Text>
        </View>
        <View style={s.statDivider} />
        <View style={s.statItem}>
          <Text style={s.statNum}>{notes?.length || 0}</Text>
          <Text style={s.statLabel}>Notes</Text>
        </View>
      </View>

      {/* Activity Timeline */}
      <View style={s.section}>
        <Text style={s.sectionTitle}>Activity Timeline</Text>
        {grouped.length === 0 ? (
          <View style={s.emptyState}>
            <Ionicons name="time-outline" size={40} color="#444" />
            <Text style={s.emptyText}>No activity recorded yet</Text>
          </View>
        ) : (
          grouped.map(([date, dayEvents]) => (
            <View key={date} style={s.dayGroup}>
              <Text style={s.dayLabel}>{formatDate(date + 'T00:00:00Z')}</Text>
              {dayEvents.map((evt: any, idx: number) => {
                const meta = getEventMeta(evt.event_type);
                const isInbound = evt.direction === 'inbound';
                return (
                  <View key={idx} style={s.eventRow} data-testid={`timeline-event-${idx}`}>
                    <View style={[s.eventDot, { backgroundColor: meta.color + '20' }]}>
                      <Ionicons name={meta.icon as any} size={16} color={meta.color} />
                    </View>
                    <View style={s.eventContent}>
                      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                        <Text style={s.eventTitle}>{evt.title || formatEventType(evt.event_type)}</Text>
                        {isInbound ? (
                          <View style={s.dirBadgeIn}><Text style={s.dirBadgeTextIn}>Customer</Text></View>
                        ) : (
                          <View style={s.dirBadgeOut}><Text style={s.dirBadgeTextOut}>Salesperson</Text></View>
                        )}
                      </View>
                      {evt.description ? <Text style={s.eventDesc} numberOfLines={3}>{evt.description}</Text> : null}
                      {evt.full_content && evt.full_content !== evt.description ? (
                        <Text style={s.eventBody} numberOfLines={4}>{evt.full_content}</Text>
                      ) : null}
                      {evt.channel ? <Text style={s.eventChannel}>via {evt.channel.toUpperCase()}</Text> : null}
                    </View>
                    <Text style={s.eventTime}>{formatTime(evt.timestamp)}</Text>
                  </View>
                );
              })}
            </View>
          ))
        )}
      </View>

      {/* Notes section */}
      {notes && notes.length > 0 ? (
        <View style={s.section}>
          <Text style={s.sectionTitle}>Notes</Text>
          {notes.map((note: any, idx: number) => (
            <View key={idx} style={s.noteCard}>
              <Text style={s.noteText}>{note.text || note.type || 'Note'}</Text>
              <Text style={s.noteDate}>{formatDate(note.created_at)}</Text>
            </View>
          ))}
        </View>
      ) : null}

      {/* Footer */}
      <View style={s.footer}>
        <Text style={s.footerText}>Powered by i'M On Social</Text>
        <Text style={s.footerSub}>This timeline updates in real-time</Text>
      </View>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  page: { flex: 1, backgroundColor: '#0A0A0A' },
  // Loading
  loadingWrap: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#0A0A0A', minHeight: 400, gap: 12 },
  loadingText: { color: '#999', fontSize: 16 },
  // PIN
  pinContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#0A0A0A', padding: 32, minHeight: 500 },
  pinLogo: { width: 120, height: 60, marginBottom: 24 },
  pinIconWrap: { marginBottom: 24 },
  pinTitle: { fontSize: 22, fontWeight: '800', color: '#FFFFFF', marginBottom: 8 },
  pinSubtitle: { fontSize: 16, color: '#999', textAlign: 'center', marginBottom: 24, maxWidth: 280 },
  pinInput: { width: 200, height: 50, backgroundColor: '#1C1C1E', borderRadius: 12, color: '#FFFFFF', fontSize: 21, textAlign: 'center', letterSpacing: 8, borderWidth: 1, borderColor: '#333', marginBottom: 12 },
  pinError: { color: '#FF3B30', fontSize: 15, marginBottom: 8 },
  pinButton: { backgroundColor: '#C9A962', paddingHorizontal: 40, paddingVertical: 14, borderRadius: 12, marginTop: 8 },
  pinButtonText: { color: '#000', fontSize: 18, fontWeight: '700' },
  // Header
  header: { paddingVertical: 20, paddingHorizontal: 20, alignItems: 'center', gap: 8 },
  storeLogo: { width: 140, height: 50 },
  storeName: { fontSize: 18, fontWeight: '700', color: '#FFFFFF', letterSpacing: 1 },
  // Contact card
  contactCard: { margin: 16, backgroundColor: '#1C1C1E', borderRadius: 16, padding: 16 },
  contactRow: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  contactAvatar: { width: 56, height: 56, borderRadius: 28 },
  contactAvatarPlaceholder: { width: 56, height: 56, borderRadius: 28, justifyContent: 'center', alignItems: 'center' },
  contactInitials: { fontSize: 21, fontWeight: '800' },
  contactInfo: { flex: 1 },
  contactName: { fontSize: 21, fontWeight: '800', color: '#FFFFFF' },
  contactDetail: { fontSize: 15, color: '#8E8E93', marginTop: 2 },
  spRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 12, paddingTop: 12, borderTopWidth: 1, borderTopColor: '#2C2C2E' },
  spText: { fontSize: 15, color: '#8E8E93' },
  tagsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 10 },
  tag: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12, borderWidth: 1 },
  tagText: { fontSize: 13, fontWeight: '600' },
  // Stats
  statsBar: { flexDirection: 'row', marginHorizontal: 16, backgroundColor: '#1C1C1E', borderRadius: 12, padding: 14, marginBottom: 16 },
  statItem: { flex: 1, alignItems: 'center' },
  statNum: { fontSize: 19, fontWeight: '800', color: '#FFFFFF' },
  statLabel: { fontSize: 13, color: '#8E8E93', marginTop: 2 },
  statDivider: { width: 1, backgroundColor: '#2C2C2E', marginVertical: 2 },
  // Section
  section: { marginHorizontal: 16, marginBottom: 20 },
  sectionTitle: { fontSize: 18, fontWeight: '700', color: '#FFFFFF', marginBottom: 12, letterSpacing: 0.5 },
  // Day group
  dayGroup: { marginBottom: 16 },
  dayLabel: { fontSize: 14, fontWeight: '700', color: '#C9A962', marginBottom: 8, letterSpacing: 1, textTransform: 'uppercase' },
  // Event row
  eventRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, marginBottom: 10, paddingLeft: 4 },
  eventDot: { width: 32, height: 32, borderRadius: 16, justifyContent: 'center', alignItems: 'center' },
  eventContent: { flex: 1 },
  eventTitle: { fontSize: 16, fontWeight: '600', color: '#FFFFFF' },
  eventDesc: { fontSize: 14, color: '#8E8E93', marginTop: 2 },
  eventTime: { fontSize: 13, color: '#666', minWidth: 60, textAlign: 'right' },
  // Direction badges
  dirBadgeOut: { backgroundColor: '#007AFF20', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6 },
  dirBadgeTextOut: { fontSize: 9, fontWeight: '700', color: '#007AFF', letterSpacing: 0.5 },
  dirBadgeIn: { backgroundColor: '#30D15820', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6 },
  dirBadgeTextIn: { fontSize: 9, fontWeight: '700', color: '#30D158', letterSpacing: 0.5 },
  // Message body & channel
  eventBody: { fontSize: 14, color: '#AAA', marginTop: 4, fontStyle: 'italic', lineHeight: 17 },
  eventChannel: { fontSize: 12, color: '#555', marginTop: 3, textTransform: 'uppercase', letterSpacing: 0.5 },
  // Empty
  emptyState: { alignItems: 'center', paddingVertical: 40, gap: 8 },
  emptyText: { fontSize: 16, color: '#666' },
  // Notes
  noteCard: { backgroundColor: '#1C1C1E', borderRadius: 10, padding: 12, marginBottom: 8 },
  noteText: { fontSize: 16, color: '#FFFFFF', lineHeight: 20 },
  noteDate: { fontSize: 13, color: '#666', marginTop: 6 },
  // Footer
  footer: { alignItems: 'center', paddingVertical: 32, gap: 4 },
  footerText: { fontSize: 15, color: '#444', fontWeight: '600' },
  footerSub: { fontSize: 13, color: '#333' },
});
