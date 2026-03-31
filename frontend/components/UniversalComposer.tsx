/**
 * UniversalComposer — one composer bar used everywhere.
 *
 * Used in:
 *   - contact/[id].tsx  (pass contactId + contact)
 *   - thread/[id].tsx   (pass conversationId)
 *
 * Features identical in both:
 *   📷 Photo  📄 Templates  ⭐ Quick Links  🎴 Cards  🎤 Voice  ✨ AI  ▶ Send
 */
import React, { useState, useRef, useCallback, useEffect } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ScrollView, ActivityIndicator, Modal, Platform, Image, Linking,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import api, { messagesAPI } from '../services/api';
import { showSimpleAlert } from '../services/alert';
import useAuthStore from '../store/authStore';

const IS_WEB = Platform.OS === 'web';
const APP_BASE = 'https://app.imonsocial.com';

// ── Props ──────────────────────────────────────────────────────────────────
export interface UniversalComposerProps {
  // Identity — provide one or both
  contactId?: string;
  conversationId?: string;
  // Contact data for personalization + channel routing
  contact?: {
    first_name?: string; last_name?: string;
    phone?: string; email?: string;
  };
  storeId?: string;
  orgId?: string;
  colors: any;
  // Pre-populated state (e.g. from campaign step)
  initialMessage?: string;
  initialEventType?: string;
  initialEventTitle?: string;
  // Completed task ID — auto-completed after send
  taskId?: string;
  onMessageSent?: () => void;
}

// ── Component ──────────────────────────────────────────────────────────────
export default function UniversalComposer({
  contactId, conversationId, contact,
  storeId, orgId, colors,
  initialMessage = '', initialEventType, initialEventTitle,
  taskId, onMessageSent,
}: UniversalComposerProps) {
  const { user } = useAuthStore();
  const userId = user?._id || '';

  // Core composer state
  const [message, setMessage] = useState(initialMessage);
  const [inputHeight, setInputHeight] = useState(36);
  const [mode, setMode] = useState<'sms' | 'email'>('sms');
  const [sending, setSending] = useState(false);
  const [eventType, setEventType] = useState<string | null>(initialEventType || null);
  const [eventTitle, setEventTitle] = useState<string | null>(initialEventTitle || null);
  const [media, setMedia] = useState<{ uri: string; type?: string; name?: string } | null>(null);

  // Picker modals
  const [showTemplates, setShowTemplates] = useState(false);
  const [showLinks, setShowLinks] = useState(false);
  const [showCards, setShowCards] = useState(false);

  // Data
  const [templates, setTemplates] = useState<any[]>([]);
  const [customCards, setCustomCards] = useState<any[]>([]);
  const [reviewLinks, setReviewLinks] = useState<any[]>([]);

  // AI
  const [loadingAI, setLoadingAI] = useState(false);
  const [aiSuggestion, setAiSuggestion] = useState('');
  const [showAISuggestion, setShowAISuggestion] = useState(false);

  // Voice
  const [transcribing, setTranscribing] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorderRef = useRef<any>(null);

  // Sync initialMessage changes (e.g. campaign step pre-populate)
  useEffect(() => {
    if (initialMessage) setMessage(initialMessage);
    if (initialEventType) setEventType(initialEventType);
    if (initialEventTitle) setEventTitle(initialEventTitle);
  }, [initialMessage, initialEventType, initialEventTitle]);

  // Load templates & custom cards
  useEffect(() => {
    if (!userId) return;
    api.get(`/templates/${userId}`).then(r => {
      const all = Array.isArray(r.data) ? r.data : r.data?.templates || [];
      setTemplates(all);
    }).catch(() => {});

    const entityId = storeId || orgId;
    if (entityId) {
      api.get(`/congrats/templates/all/${entityId}`).then(r => {
        const TYPE_META_KEYS = new Set(['congrats','birthday','anniversary','thankyou','thank_you','holiday','welcome']);
        const custom = (r.data || []).filter((t: any) => !TYPE_META_KEYS.has(t.card_type) && t.headline);
        setCustomCards(custom);
      }).catch(() => {});
    }
  }, [userId, storeId, orgId]);

  // Load store review links for quick link section
  useEffect(() => {
    if (!storeId) return;
    api.get(`/admin/stores/${storeId}`).then(r => {
      const rl = r.data?.review_links || {};
      const links: any[] = [];
      if (rl.google) links.push({ id: 'google', name: 'Google', icon: 'logo-google', url: rl.google });
      if (rl.yelp) links.push({ id: 'yelp', name: 'Yelp', icon: 'star', url: rl.yelp });
      if (rl.facebook) links.push({ id: 'facebook', name: 'Facebook', icon: 'logo-facebook', url: rl.facebook });
      (rl.custom || []).forEach((c: any) => links.push({ id: c.id, name: c.name, icon: 'link', url: c.url }));
      setReviewLinks(links);
    }).catch(() => {});
  }, [storeId]);

  // ── Helpers ──────────────────────────────────────────────────────────────
  const resolvePersonalization = (text: string) => {
    if (!contact) return text;
    return text
      .replace(/\{first_name\}/g, contact.first_name || '')
      .replace(/\{last_name\}/g, contact.last_name || '')
      .replace(/\{full_name\}/g, `${contact.first_name || ''} ${contact.last_name || ''}`.trim())
      .replace(/\{phone\}/g, contact.phone || '')
      .replace(/\{email\}/g, contact.email || '')
      .replace(/\{my_name\}/g, (user as any)?.name || '')
      .replace(/\{my_phone\}/g, (user as any)?.phone || '')
      .replace(/\{name\}/g, contact.first_name || '');
  };

  const getOrCreateConversation = async () => {
    if (conversationId) return conversationId;
    if (!contactId) throw new Error('No contact or conversation provided');
    const conv = await messagesAPI.createConversation(userId, {
      contact_id: contactId,
      contact_phone: contact?.phone,
    });
    return conv._id || conv.id;
  };

  // ── Photo pick ────────────────────────────────────────────────────────────
  const pickPhoto = async () => {
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: true, quality: 0.7,
      });
      if (!result.canceled && result.assets?.[0]) {
        const a = result.assets[0];
        setMedia({ uri: a.uri, type: a.mimeType || 'image/jpeg', name: a.fileName || 'photo.jpg' });
      }
    } catch { showSimpleAlert('Error', 'Could not open photo library'); }
  };

  // ── Voice to text ─────────────────────────────────────────────────────────
  const handleVoiceToText = async () => {
    if (!IS_WEB) { showSimpleAlert('Voice', 'Voice-to-text is available on the web app'); return; }
    if (isRecording) {
      mediaRecorderRef.current?.stop();
      setIsRecording(false);
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      const chunks: BlobPart[] = [];
      recorder.ondataavailable = e => chunks.push(e.data);
      recorder.onstop = async () => {
        setTranscribing(true);
        stream.getTracks().forEach(t => t.stop());
        const blob = new Blob(chunks, { type: 'audio/webm' });
        const fd = new FormData();
        fd.append('file', blob, 'voice.webm');
        try {
          const r = await api.post('/voice/transcribe', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
          if (r.data?.text) setMessage(prev => prev ? `${prev} ${r.data.text}` : r.data.text);
        } catch { showSimpleAlert('Error', 'Transcription failed. Try again.'); }
        finally { setTranscribing(false); }
      };
      recorder.start();
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
    } catch { showSimpleAlert('Permission', 'Microphone access is required for voice-to-text'); }
  };

  // ── AI suggestion ──────────────────────────────────────────────────────────
  const loadAISuggestion = async () => {
    if (!userId || !contactId) return;
    setLoadingAI(true);
    try {
      const r = await api.post('/jessi/suggest-message', { user_id: userId, contact_id: contactId });
      if (r.data?.message) { setAiSuggestion(r.data.message); setShowAISuggestion(true); }
    } catch { showSimpleAlert('AI', 'Could not generate a suggestion right now.'); }
    finally { setLoadingAI(false); }
  };

  // ── Review link insert ────────────────────────────────────────────────────
  const insertReviewLink = async (link: { id: string; name: string; url: string }) => {
    setShowLinks(false);
    setEventType('review_request_sent');
    const firstName = contact?.first_name || 'there';
    try {
      const r = await api.post('/s/create', {
        original_url: link.url, link_type: 'review_request',
        user_id: userId, reference_id: contactId,
        metadata: { contact_id: contactId, platform: link.id },
      });
      const trackableUrl = r.data?.short_url || link.url;
      setMessage(`Hey ${firstName}! We'd love your feedback. Leave us a review here: ${trackableUrl}`);
    } catch {
      setMessage(`Hey ${firstName}! Leave us a review: ${link.url}`);
    }
  };

  // ── Card send ─────────────────────────────────────────────────────────────
  const sendCard = async (cardType: string, headline: string) => {
    setShowCards(false);
    if (!contactId) return;
    try {
      const fd = new FormData();
      fd.append('salesman_id', userId);
      fd.append('customer_name', `${contact?.first_name || ''} ${contact?.last_name || ''}`.trim());
      fd.append('card_type', cardType);
      if (contact?.phone) fd.append('customer_phone', contact.phone);
      const r = await api.post('/congrats/create', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      if (r.data?.short_url) {
        setMessage(`Hey ${contact?.first_name || 'there'}! ${headline} ${r.data.short_url}`);
        setEventType(`${cardType}_card_sent`);
        setEventTitle(`'${headline}' Card Sent`);
      }
    } catch (e: any) {
      showSimpleAlert('Error', e?.response?.data?.detail || 'Could not create card');
    }
  };

  // ── SEND ──────────────────────────────────────────────────────────────────
  const handleSend = async (textOverride?: string) => {
    let content = resolvePersonalization(textOverride || message.trim());
    if (!content && !media) return;
    if (!userId) return;

    if (mode === 'sms' && !contact?.phone && !conversationId) {
      showSimpleAlert('Missing Info', 'No phone number saved for this contact.');
      return;
    }
    if (mode === 'email' && !contact?.email) {
      showSimpleAlert('Missing Info', 'No email address available for this contact.');
      return;
    }

    setSending(true);
    try {
      // Upload photo if attached
      let photoUrl = '';
      if (media?.uri) {
        try {
          const fd = new FormData();
          if (IS_WEB) {
            const blob = await (await fetch(media.uri)).blob();
            fd.append('file', blob, 'photo.jpg');
          } else {
            fd.append('file', { uri: media.uri, type: 'image/jpeg', name: 'photo.jpg' } as any);
          }
          const up = await api.post('/images/upload', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
          photoUrl = up.data?.original_url || up.data?.url || '';
          if (photoUrl.startsWith('/')) photoUrl = `${APP_BASE}${photoUrl}`;
        } catch {}
      }

      const messageContent = photoUrl ? `${content || ''}\n${photoUrl}`.trim() : (content || '');
      const convId = await getOrCreateConversation();

      const payload: any = {
        conversation_id: convId,
        content: messageContent,
        channel: mode === 'email' ? 'email' : 'sms_personal',
      };
      if (eventType) payload.event_type = eventType;
      if (eventTitle) payload.event_title = eventTitle;

      await messagesAPI.send(userId, payload);

      if (mode === 'sms' && contact?.phone) {
        // Open native SMS on mobile / copy on web
        const smsUrl = IS_WEB
          ? `sms:${contact.phone}${/iphone|ipad|ipod/.test(navigator.userAgent.toLowerCase()) ? '&' : '?'}body=${encodeURIComponent(messageContent)}`
          : `sms:${contact.phone}?body=${encodeURIComponent(messageContent)}`;
        try { if (IS_WEB) window.location.href = smsUrl; else Linking.openURL(smsUrl); } catch {}
        try { if (IS_WEB && navigator.clipboard) await navigator.clipboard.writeText(messageContent); } catch {}
      } else if (mode === 'email') {
        // Email sent via backend — just notify
      }

      // Auto-complete task if applicable
      if (taskId) {
        api.patch(`/tasks/${userId}/${taskId}`, { action: 'complete' }).catch(() => {});
      }

      // Reset
      setMessage(''); setInputHeight(36); setEventType(null); setEventTitle(null);
      setMedia(null); setShowAISuggestion(false); setAiSuggestion('');
      onMessageSent?.();
    } catch (e: any) {
      showSimpleAlert('Send Failed', e?.response?.data?.detail || 'Could not send message');
    } finally {
      setSending(false);
    }
  };

  const canSend = (message.trim().length > 0 || !!media) && !sending;
  const firstName = contact?.first_name || 'there';

  // ── Render ──────────────────────────────────────────────────────────────
  return (
    <View style={[s.root, { backgroundColor: colors.bg, borderTopColor: colors.borderLight }]}>

      {/* AI suggestion banner */}
      {showAISuggestion && aiSuggestion ? (
        <View style={[s.aiBar, { backgroundColor: '#34C75918', borderColor: '#34C75940' }]}>
          <Text style={[s.aiText, { color: colors.text }]} numberOfLines={2}>{aiSuggestion}</Text>
          <View style={s.aiActions}>
            <TouchableOpacity style={[s.aiBtn, { backgroundColor: '#34C759' }]}
              onPress={() => { setMessage(aiSuggestion); setShowAISuggestion(false); }}>
              <Text style={s.aiBtnText}>Use</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[s.aiBtn, { backgroundColor: '#007AFF' }]}
              onPress={() => { handleSend(aiSuggestion); setShowAISuggestion(false); }}>
              <Text style={s.aiBtnText}>Send</Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={() => setShowAISuggestion(false)}>
              <Ionicons name="close" size={18} color={colors.textSecondary} />
            </TouchableOpacity>
          </View>
        </View>
      ) : null}

      {/* Media preview */}
      {media ? (
        <View style={s.mediaPreview}>
          <Image source={{ uri: media.uri }} style={s.mediaThumb} />
          <TouchableOpacity onPress={() => setMedia(null)} style={s.mediaRemove}>
            <Ionicons name="close-circle" size={20} color="#FF3B30" />
          </TouchableOpacity>
        </View>
      ) : null}

      {/* Input box */}
      <View style={[s.inputRow, { backgroundColor: colors.surface }]}>
        <TextInput
          style={[s.input, { color: colors.text, height: Math.max(36, Math.min(inputHeight, 150)) }]}
          value={message}
          onChangeText={setMessage}
          placeholder={media ? 'Add a caption…' : `Message ${firstName}…`}
          placeholderTextColor={colors.textTertiary}
          multiline
          onContentSizeChange={e => setInputHeight(e.nativeEvent.contentSize.height)}
          data-testid="composer-input"
        />
      </View>

      {/* Toolbar */}
      <View style={[s.toolbar, { borderTopColor: colors.borderLight }]}>
        <View style={s.tools}>
          {/* Photo */}
          <ToolBtn onPress={pickPhoto} testID="photo-btn">
            <Ionicons name="image-outline" size={22} color={colors.textSecondary} />
          </ToolBtn>

          {/* Templates */}
          <ToolBtn onPress={() => setShowTemplates(true)} testID="templates-btn">
            <Ionicons name="document-text-outline" size={22} color={colors.textSecondary} />
          </ToolBtn>

          {/* Quick Links (review links) */}
          {(reviewLinks.length > 0 || contactId) ? (
            <ToolBtn onPress={() => setShowLinks(true)} testID="links-btn">
              <Ionicons name="star-outline" size={22} color={colors.textSecondary} />
            </ToolBtn>
          ) : null}

          {/* Cards */}
          {(customCards.length > 0 || storeId) ? (
            <ToolBtn onPress={() => setShowCards(true)} testID="cards-btn">
              <Ionicons name="card-outline" size={22} color={colors.textSecondary} />
            </ToolBtn>
          ) : null}

          {/* Voice to text */}
          <ToolBtn onPress={handleVoiceToText} disabled={transcribing} isRecording={isRecording} testID="voice-btn">
            {transcribing
              ? <ActivityIndicator size="small" color="#C9A962" />
              : <Ionicons name={isRecording ? 'stop-circle' : 'mic-outline'} size={22}
                  color={isRecording ? '#FF3B30' : colors.textSecondary} />
            }
          </ToolBtn>

          {/* AI suggest — only available when there's a contact for context */}
          {contactId ? (
            <ToolBtn onPress={loadAISuggestion} disabled={loadingAI} testID="ai-btn">
              {loadingAI
                ? <ActivityIndicator size="small" color="#34C759" />
                : <Ionicons name="sparkles" size={20} color="#34C759" />
              }
            </ToolBtn>
          ) : null}
        </View>

        {/* Send button */}
        <TouchableOpacity
          style={[s.sendBtn, { backgroundColor: canSend ? (mode === 'email' ? '#34C759' : '#007AFF') : colors.borderLight }]}
          onPress={() => handleSend()}
          disabled={!canSend}
          data-testid="send-btn"
        >
          {sending
            ? <ActivityIndicator size="small" color="#fff" />
            : <Ionicons name="send" size={18} color={canSend ? '#fff' : colors.textTertiary} />
          }
        </TouchableOpacity>
      </View>

      {/* ── TEMPLATES MODAL ─────────────────────────────────────────────── */}
      <Modal visible={showTemplates} animationType="slide" transparent onRequestClose={() => setShowTemplates(false)}>
        <View style={s.modalOverlay}>
          <View style={[s.modalSheet, { backgroundColor: colors.bg }]}>
            <View style={s.modalHeader}>
              <Text style={[s.modalTitle, { color: colors.text }]}>Templates</Text>
              <TouchableOpacity onPress={() => setShowTemplates(false)}>
                <Ionicons name="close" size={24} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>
            <ScrollView style={{ flex: 1 }} keyboardShouldPersistTaps="handled">
              {templates.map((t: any) => (
                <TouchableOpacity key={t._id} style={[s.templateRow, { borderBottomColor: colors.borderLight }]}
                  onPress={() => { setMessage(t.content || t.body || ''); setShowTemplates(false); }}
                  data-testid={`template-${t._id}`}>
                  <Text style={[s.templateName, { color: colors.text }]}>{t.name}</Text>
                  <Text style={[s.templatePreview, { color: colors.textSecondary }]} numberOfLines={2}>
                    {t.content || t.body || ''}
                  </Text>
                </TouchableOpacity>
              ))}
              {templates.length === 0 && (
                <Text style={[s.emptyNote, { color: colors.textSecondary }]}>No templates yet</Text>
              )}
            </ScrollView>
          </View>
        </View>
      </Modal>

      {/* ── QUICK LINKS MODAL ───────────────────────────────────────────── */}
      <Modal visible={showLinks} animationType="slide" transparent onRequestClose={() => setShowLinks(false)}>
        <View style={s.modalOverlay}>
          <View style={[s.modalSheet, { backgroundColor: colors.bg }]}>
            <View style={s.modalHeader}>
              <Text style={[s.modalTitle, { color: colors.text }]}>Quick Links</Text>
              <TouchableOpacity onPress={() => setShowLinks(false)}>
                <Ionicons name="close" size={24} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>
            <ScrollView style={{ flex: 1 }}>
              {reviewLinks.map(link => (
                <TouchableOpacity key={link.id} style={[s.templateRow, { borderBottomColor: colors.borderLight }]}
                  onPress={() => insertReviewLink(link)}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                    <Ionicons name={link.icon} size={20} color="#C9A962" />
                    <Text style={[s.templateName, { color: colors.text }]}>Ask for {link.name} Review</Text>
                  </View>
                </TouchableOpacity>
              ))}
              {reviewLinks.length === 0 && (
                <Text style={[s.emptyNote, { color: colors.textSecondary }]}>
                  Add review links in Store Profile → Review Links
                </Text>
              )}
            </ScrollView>
          </View>
        </View>
      </Modal>

      {/* ── CARDS MODAL ─────────────────────────────────────────────────── */}
      <Modal visible={showCards} animationType="slide" transparent onRequestClose={() => setShowCards(false)}>
        <View style={s.modalOverlay}>
          <View style={[s.modalSheet, { backgroundColor: colors.bg }]}>
            <View style={s.modalHeader}>
              <Text style={[s.modalTitle, { color: colors.text }]}>Send a Card</Text>
              <TouchableOpacity onPress={() => setShowCards(false)}>
                <Ionicons name="close" size={24} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>
            <ScrollView style={{ flex: 1 }}>
              {/* Standard card types */}
              {[
                { type: 'congrats', label: 'Congratulations', icon: 'ribbon-outline', color: '#C9A962' },
                { type: 'birthday', label: 'Happy Birthday', icon: 'gift-outline', color: '#FF6B6B' },
                { type: 'anniversary', label: 'Anniversary', icon: 'heart-outline', color: '#FF9500' },
                { type: 'thankyou', label: 'Thank You', icon: 'happy-outline', color: '#34C759' },
                { type: 'welcome', label: 'Welcome', icon: 'hand-left-outline', color: '#007AFF' },
              ].map(c => (
                <TouchableOpacity key={c.type} style={[s.templateRow, { borderBottomColor: colors.borderLight }]}
                  onPress={() => sendCard(c.type, c.label)}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                    <View style={{ width: 36, height: 36, borderRadius: 10, backgroundColor: c.color + '20', alignItems: 'center', justifyContent: 'center' }}>
                      <Ionicons name={c.icon as any} size={20} color={c.color} />
                    </View>
                    <Text style={[s.templateName, { color: colors.text }]}>{c.label} Card</Text>
                  </View>
                </TouchableOpacity>
              ))}
              {/* Custom cards */}
              {customCards.length > 0 && (
                <>
                  <Text style={[s.sectionLabel, { color: colors.textTertiary }]}>MY CUSTOM CARDS</Text>
                  {customCards.map((t: any) => (
                    <TouchableOpacity key={t.card_type} style={[s.templateRow, { borderBottomColor: colors.borderLight }]}
                      onPress={() => sendCard(t.card_type, t.headline)}>
                      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                        <View style={{ width: 36, height: 36, borderRadius: 10, backgroundColor: (t.accent_color || '#C9A962') + '20', alignItems: 'center', justifyContent: 'center' }}>
                          <Ionicons name="gift-outline" size={20} color={t.accent_color || '#C9A962'} />
                        </View>
                        <Text style={[s.templateName, { color: colors.text }]}>{t.headline}</Text>
                      </View>
                    </TouchableOpacity>
                  ))}
                </>
              )}
            </ScrollView>
          </View>
        </View>
      </Modal>
    </View>
  );
}

// ── Tool button helper ────────────────────────────────────────────────────
function ToolBtn({ onPress, disabled, isRecording, testID, children }: any) {
  return IS_WEB ? (
    <button type="button" onClick={onPress} disabled={disabled} data-testid={testID}
      style={{ background: 'none', border: 'none', padding: 8, cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.5 : 1, display: 'flex', alignItems: 'center' }}>
      {children}
    </button>
  ) : (
    <TouchableOpacity onPress={onPress} disabled={disabled} style={{ padding: 8, opacity: disabled ? 0.5 : 1 }} data-testid={testID}>
      {children}
    </TouchableOpacity>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────
const s = StyleSheet.create({
  root: { borderTopWidth: 1 },
  aiBar: { flexDirection: 'row', alignItems: 'center', padding: 10, borderWidth: 1, margin: 8, borderRadius: 12, gap: 8 },
  aiText: { flex: 1, fontSize: 14 },
  aiActions: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  aiBtn: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 14 },
  aiBtnText: { color: '#fff', fontSize: 13, fontWeight: '700' },
  mediaPreview: { flexDirection: 'row', alignItems: 'center', padding: 8, gap: 8 },
  mediaThumb: { width: 56, height: 56, borderRadius: 8 },
  mediaRemove: { padding: 4 },
  inputRow: { marginHorizontal: 8, marginTop: 8, borderRadius: 20, paddingHorizontal: 14, paddingVertical: 6 },
  input: { fontSize: 16, lineHeight: 22 },
  toolbar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 8, paddingVertical: 8, borderTopWidth: 1 },
  tools: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', flex: 1 },
  sendBtn: { width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center', marginLeft: 8 },
  // Modals
  modalOverlay: { flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(0,0,0,0.5)' },
  modalSheet: { borderTopLeftRadius: 20, borderTopRightRadius: 20, maxHeight: '75%', paddingBottom: 34 },
  modalHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 16, borderBottomWidth: 1, borderBottomColor: 'rgba(128,128,128,0.2)' },
  modalTitle: { fontSize: 18, fontWeight: '700' },
  templateRow: { padding: 14, borderBottomWidth: 1 },
  templateName: { fontSize: 15, fontWeight: '600', marginBottom: 2 },
  templatePreview: { fontSize: 13 },
  emptyNote: { textAlign: 'center', padding: 24, fontSize: 14 },
  sectionLabel: { fontSize: 11, fontWeight: '700', letterSpacing: 1, paddingHorizontal: 14, paddingTop: 16, paddingBottom: 6 },
});
