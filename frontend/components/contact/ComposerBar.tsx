/**
 * ComposerBar — inline SMS/Email composer with AI suggestions and toolbar.
 * Extracted from contact/[id].tsx (render-only; all state lives in the parent).
 */
import React from 'react';
import { View, Text, TextInput, TouchableOpacity, ActivityIndicator, KeyboardAvoidingView, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Image } from 'expo-image';
import { useRouter } from 'expo-router';
import { showSimpleAlert } from '../../services/alert';

const IS_WEB = Platform.OS === 'web';

export default function ComposerBar(props: any) {
  const {
    s, colors, contact, contactId,
    composerMode, setComposerMode, composerMessage, setComposerMessage, composerSending,
    selectedMedia, setSelectedMedia,
    showAISuggestion, setShowAISuggestion, aiSuggestion, setAiSuggestion,
    loadingAI, loadAISuggestionForComposer, handleComposerSend,
    handleAttachPhoto, onOpenTemplates, onOpenReviewLinks, openBusinessCardPicker,
    handleVoiceToText, isVoiceRecording, voiceTranscribing, inputRef,
  } = props;
  const router = useRouter();

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      keyboardVerticalOffset={0}
    >
    <View style={s.composerContainer} data-testid="contact-composer">
      {/* SMS/Email mode toggle */}
      <View style={s.composerModeRow}>
        <TouchableOpacity
          style={[s.composerModeBtn, composerMode === 'sms' && s.composerModeBtnActive]}
          onPress={() => setComposerMode('sms')}
          data-testid="composer-mode-sms"
        >
          <Ionicons name="chatbubble" size={14} color={composerMode === 'sms' ? '#34C759' : colors.textTertiary} />
          <Text style={[s.composerModeBtnText, composerMode === 'sms' && { color: '#34C759' }]}>SMS</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[s.composerModeBtn, composerMode === 'email' && s.composerModeBtnActive]}
          onPress={() => setComposerMode('email')}
          data-testid="composer-mode-email"
        >
          <Ionicons name="mail" size={14} color={composerMode === 'email' ? '#AF52DE' : colors.textTertiary} />
          <Text style={[s.composerModeBtnText, composerMode === 'email' && { color: '#AF52DE' }]}>Email</Text>
        </TouchableOpacity>
        <View style={{ flex: 1 }} />
        <TouchableOpacity
          style={s.composerCallBtn}
          onPress={() => {
            if (!contact.phone) { showSimpleAlert('Missing Info', 'No phone number'); return; }
            const contactName = `${contact.first_name || ''} ${contact.last_name || ''}`.trim();
            router.push(`/call-screen?contact_id=${contactId}&contact_name=${encodeURIComponent(contactName)}&phone=${encodeURIComponent(contact.phone)}`);
          }}
          data-testid="composer-call-btn"
        >
          <Ionicons name="call" size={16} color="#32ADE6" />
        </TouchableOpacity>
      </View>

      {/* AI Suggestion bubble */}
      {showAISuggestion && aiSuggestion ? (
        <View style={s.aiSuggestionBubble} data-testid="ai-suggestion-bubble">
          <View style={s.aiSuggestionHeader}>
            <Ionicons name="sparkles" size={14} color="#34C759" />
            <Text style={s.aiSuggestionLabel}>AI Suggestion</Text>
            <TouchableOpacity onPress={() => { setShowAISuggestion(false); setAiSuggestion(''); }}>
              <Ionicons name="close-circle" size={16} color={colors.textTertiary} />
            </TouchableOpacity>
          </View>
          <Text style={s.aiSuggestionText}>{aiSuggestion}</Text>
          <View style={s.aiSuggestionActions}>
            <TouchableOpacity
              style={s.aiActionBtn}
              onPress={() => { setComposerMessage(aiSuggestion); setShowAISuggestion(false); }}
              data-testid="ai-edit-btn"
            >
              <Ionicons name="pencil" size={14} color="#007AFF" />
              <Text style={s.aiActionBtnText}>Edit</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[s.aiActionBtn, s.aiActionBtnSend]}
              onPress={() => { handleComposerSend(aiSuggestion); setShowAISuggestion(false); setAiSuggestion(''); }}
              data-testid="ai-send-btn"
            >
              <Ionicons name="send" size={14} color={colors.text} />
              <Text style={[s.aiActionBtnText, { color: colors.text }]}>Send Now</Text>
            </TouchableOpacity>
          </View>
        </View>
      ) : null}

      {/* Composer box */}
      <View style={[s.composerBox, { backgroundColor: colors.card, borderColor: colors.border }]}>
        {/* Photo attachment preview */}
        {selectedMedia?.uri && (
          <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingTop: 10, gap: 8 }} data-testid="composer-photo-preview">
            <Image source={{ uri: selectedMedia.uri }} style={{ width: 60, height: 60, borderRadius: 8 }} />
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 15, fontWeight: '600', color: colors.text }}>Photo attached</Text>
              <Text style={{ fontSize: 13, color: colors.textTertiary }}>Will be sent with your message</Text>
            </View>
            <TouchableOpacity onPress={() => setSelectedMedia(null)} style={{ padding: 4 }} data-testid="remove-photo-btn">
              <Ionicons name="close-circle" size={22} color="#FF3B30" />
            </TouchableOpacity>
          </View>
        )}
        <TextInput
          ref={inputRef}
          style={[s.composerInput, {
            color: colors.text,
            minHeight: 44,
            maxHeight: 180,
          }]}
          placeholder="Type your message..."
          placeholderTextColor={colors.textTertiary}
          value={composerMessage}
          onChangeText={setComposerMessage}
          multiline
          maxLength={1600}
          scrollEnabled
          data-testid="composer-input"
        />
        <View style={[s.composerToolbar, { backgroundColor: colors.bg, borderTopColor: colors.border }]}>
          <View style={s.composerTools}>
            {/* Photo */}
            <TouchableOpacity style={s.composerToolBtn} onPress={handleAttachPhoto} data-testid="toolbar-photo-btn">
              <Ionicons name="image-outline" size={22} color={colors.textSecondary} />
            </TouchableOpacity>
            {/* Templates */}
            <TouchableOpacity style={s.composerToolBtn} onPress={onOpenTemplates} data-testid="toolbar-templates-btn">
              <Ionicons name="document-text-outline" size={22} color={colors.textSecondary} />
            </TouchableOpacity>
            {/* Review Link */}
            <TouchableOpacity style={s.composerToolBtn} onPress={onOpenReviewLinks} data-testid="toolbar-review-btn">
              <Ionicons name="star-outline" size={22} color={colors.textSecondary} />
            </TouchableOpacity>
            {/* Business Card */}
            <TouchableOpacity style={s.composerToolBtn} onPress={openBusinessCardPicker} data-testid="toolbar-card-btn">
              <Ionicons name="card-outline" size={22} color={colors.textSecondary} />
            </TouchableOpacity>
            {/* Voice to Text */}
            <TouchableOpacity
              style={[s.composerToolBtn, isVoiceRecording && { backgroundColor: '#FF3B3020', borderRadius: 16 }]}
              onPress={handleVoiceToText}
              data-testid="toolbar-voice-btn"
            >
              {voiceTranscribing ? (
                <ActivityIndicator size="small" color="#FF9500" />
              ) : (
                <Ionicons name={isVoiceRecording ? 'stop-circle' : 'mic-outline'} size={22} color={isVoiceRecording ? '#FF3B30' : colors.textSecondary} />
              )}
            </TouchableOpacity>
            {/* AI Sparkle */}
            <TouchableOpacity
              style={[s.composerToolBtn, loadingAI && { opacity: 0.5 }]}
              onPress={loadAISuggestionForComposer}
              disabled={loadingAI}
              data-testid="ai-sparkle-btn"
            >
              {loadingAI ? (
                <ActivityIndicator size="small" color="#AF52DE" />
              ) : (
                <Ionicons name="sparkles" size={20} color="#AF52DE" />
              )}
            </TouchableOpacity>
          </View>
          {/* Send button */}
          {IS_WEB ? (
            <button
              type="button"
              onClick={() => handleComposerSend()}
              disabled={(!composerMessage.trim() && !selectedMedia) || composerSending}
              data-testid="composer-send-btn"
              style={{
                width: 36, height: 36, borderRadius: 18,
                backgroundColor: (composerMessage.trim() || selectedMedia) && !composerSending
                  ? (composerMode === 'sms' ? '#34C759' : '#AF52DE')
                  : colors.borderLight,
                border: 'none',
                cursor: (!composerMessage.trim() && !selectedMedia) || composerSending ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}
            >
              {composerSending ? (
                <ActivityIndicator size="small" color={colors.text} />
              ) : (
                <Ionicons
                  name={composerMode === 'sms' ? 'send' : 'mail'}
                  size={18}
                  color={composerMessage.trim() ? '#FFF' : '#6E6E73'}
                />
              )}
            </button>
          ) : (
            <TouchableOpacity
              style={[s.composerSendBtn, { backgroundColor: composerMode === 'sms' ? '#34C759' : '#AF52DE' },
                (!composerMessage.trim() || composerSending) && { backgroundColor: colors.borderLight }]}
              onPress={() => handleComposerSend()}
              disabled={!composerMessage.trim() || composerSending}
              data-testid="composer-send-btn"
            >
              {composerSending ? (
                <ActivityIndicator size="small" color={colors.text} />
              ) : (
                <Ionicons name={composerMode === 'sms' ? 'send' : 'mail'} size={18} color={composerMessage.trim() ? '#FFF' : '#6E6E73'} />
              )}
            </TouchableOpacity>
          )}
        </View>
      </View>
    </View>
    </KeyboardAvoidingView>
  );
}
