import React from 'react';
import { View, Text, TouchableOpacity, Platform, Linking } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { format } from 'date-fns';
import { Image } from 'expo-image';

type Props = {
  item: any;
  isUser: boolean;
  timestamp: Date;
  showDateSep: boolean;
  dateLabel: string;
  styles: any;
  colors: any;
  contactName: string;
  myPhoto: string | null;
  userName?: string;
  highlight: (text: string) => React.ReactNode;
  isCurrentMatch: boolean;
};

const CARD_DISPLAY: Record<string, { icon: string; color: string; label: string }> = {
  congrats: { icon: 'trophy', color: '#C9A962', label: 'Congrats Card' },
  birthday: { icon: 'gift', color: '#FF2D55', label: 'Birthday Card' },
  anniversary: { icon: 'heart', color: '#AF52DE', label: 'Anniversary Card' },
  thankyou: { icon: 'thumbs-up', color: '#34C759', label: 'Thank You Card' },
  welcome: { icon: 'hand-left', color: '#007AFF', label: 'Welcome Card' },
  holiday: { icon: 'snow', color: '#5AC8FA', label: 'Holiday Card' },
};

const KNOWN_CARD_TYPES = ['congrats', 'birthday', 'anniversary', 'thankyou', 'welcome', 'holiday'];

const detectFromContent = (text: string): string => {
  if (text.includes('holiday card') || text.includes('happy holiday')) return 'holiday';
  if (text.includes('birthday card') || text.includes('happy birthday')) return 'birthday';
  if (text.includes('anniversary card') || text.includes('happy anniversary')) return 'anniversary';
  if (text.includes('thank you card') || text.includes('thankyou card')) return 'thankyou';
  if (text.includes('welcome card')) return 'welcome';
  return '';
};

export const MessageBubble = ({
  item, isUser, timestamp, showDateSep, dateLabel, styles, colors,
  contactName, myPhoto, userName, highlight, isCurrentMatch,
}: Props) => {
  const hasMedia = item.has_media && item.media_urls && item.media_urls.length > 0;

  // Detect rich content types
  const content = item.content || '';
  const eventType = item.event_type || '';
  const contentLower = content.toLowerCase();
  const isReviewLink = content.includes('/review/') || contentLower.includes('review link') || eventType.includes('review');
  const isDigitalCard = content.includes('/card/') || content.includes('/p/') || contentLower.includes('digital card') || contentLower.includes('digital business card') || contentLower.includes('save my contact') || eventType === 'digital_card_shared' || eventType === 'digital_card_sent';

  let detectedCardType = '';
  if (eventType.includes('_card_sent') || eventType.includes('_card_shared')) {
    const typeFromEvent = eventType.replace('_card_sent', '').replace('_card_shared', '');
    if (KNOWN_CARD_TYPES.includes(typeFromEvent) && typeFromEvent !== 'congrats') {
      detectedCardType = typeFromEvent;
    } else if (typeFromEvent === 'congrats') {
      if (!isDigitalCard) {
        detectedCardType = detectFromContent(contentLower) || 'congrats';
      }
    }
  } else if (content.includes('/congrats/')) {
    if (!isDigitalCard) {
      detectedCardType = detectFromContent(contentLower) || 'congrats';
    }
  } else if (!isDigitalCard && (contentLower.includes('congrats') || contentLower.includes('congratulations'))) {
    detectedCardType = 'congrats';
  }
  const isCongratsCard = detectedCardType !== '';
  const isRichContent = isReviewLink || isCongratsCard || isDigitalCard;

  let richIcon = 'chatbubble';
  let richColor = '#007AFF';
  let richLabel = 'Message';
  if (isReviewLink) { richIcon = 'star'; richColor = '#FFD60A'; richLabel = 'Review Link'; }
  else if (isDigitalCard) { richIcon = 'card'; richColor = '#6FA8FF'; richLabel = 'Digital Card'; }
  else if (isCongratsCard) {
    const cardDisplay = CARD_DISPLAY[detectedCardType] || CARD_DISPLAY.congrats;
    richIcon = cardDisplay.icon; richColor = cardDisplay.color; richLabel = cardDisplay.label;
  }

  return (
    <>
      {showDateSep && (
        <View style={styles.dateSeparatorRow}>
          <View style={[styles.dateSeparatorLine, { backgroundColor: colors.border }]} />
          <Text style={[styles.dateSeparatorText, { color: colors.textTertiary, backgroundColor: colors.bg }]}>
            {dateLabel}
          </Text>
          <View style={[styles.dateSeparatorLine, { backgroundColor: colors.border }]} />
        </View>
      )}
      <View
        style={[
          styles.messageContainer,
          isUser ? styles.userMessageContainer : styles.contactMessageContainer,
        ]}
      >
        {/* Sender label */}
        <Text style={[styles.senderLabel, isUser ? styles.senderLabelRight : styles.senderLabelLeft]}>
          {isUser ? (item.ai_generated ? 'Jessi AI' : 'You') : contactName} · {format(timestamp, 'h:mm a')}
        </Text>

        <View
          style={[
            styles.messageBubble,
            isUser ? styles.userMessageBubble : styles.contactMessageBubble,
            isRichContent && styles.richMessageBubble,
            isRichContent && { borderLeftColor: richColor },
            isCurrentMatch && { borderWidth: 2, borderColor: '#FFD60A' },
          ]}
        >
          {/* Rich content header */}
          {isRichContent && (
            <View style={styles.richContentHeader}>
              <View style={[styles.richContentIcon, { backgroundColor: `${richColor}20` }]}>
                <Ionicons name={richIcon as any} size={14} color={richColor} />
              </View>
              <Text style={[styles.richContentLabel, { color: richColor }]}>{richLabel}</Text>
            </View>
          )}

          {item.ai_generated && !isRichContent && (
            <View style={styles.aiIndicator}>
              <Ionicons name="sparkles" size={12} color="#34C759" />
              <Text style={styles.aiIndicatorText}>AI</Text>
            </View>
          )}

          {/* Render attached images */}
          {hasMedia && item.media_urls && item.media_urls.length > 0 && (
            <View style={styles.mediaContainer}>
              {item.media_urls.map((url: string, mediaIdx: number) => {
                // Ensure absolute URL — some old messages stored relative paths
                const absUrl = url && url.startsWith('http')
                  ? url
                  : url ? `https://app.imonsocial.com${url.startsWith('/') ? '' : '/'}${url}` : '';
                if (!absUrl) return null;

                // Contact card (.vcf) — render a contact-card tile instead of an image
                const lower = absUrl.toLowerCase();
                const isVcard = lower.includes('.vcf') || lower.includes('/vcard');
                if (isVcard) {
                  return (
                    <TouchableOpacity
                      key={mediaIdx}
                      activeOpacity={0.9}
                      data-testid="vcard-media-tile"
                      onPress={() => {
                        if (Platform.OS === 'web') { window.open(absUrl, '_blank'); }
                        else { Linking.openURL(absUrl); }
                      }}
                      style={styles.vcardTile}
                    >
                      {myPhoto ? (
                        <Image source={{ uri: myPhoto }} style={styles.vcardAvatar} contentFit="cover" transition={200} />
                      ) : (
                        <View style={[styles.vcardAvatar, styles.vcardAvatarFallback]}>
                          <Ionicons name="person" size={26} color="#8E8E93" />
                        </View>
                      )}
                      <View style={{ flex: 1 }}>
                        <Text style={styles.vcardTitle} numberOfLines={1}>{userName || 'Contact Card'}</Text>
                        <Text style={styles.vcardSubtitle}>Contact Card · Tap to save</Text>
                      </View>
                      <Ionicons name="person-add" size={20} color="#007AFF" />
                    </TouchableOpacity>
                  );
                }

                return (
                  <TouchableOpacity
                    key={mediaIdx}
                    activeOpacity={0.9}
                    onPress={() => {
                      if (Platform.OS === 'web') { window.open(absUrl, '_blank'); }
                      else { Linking.openURL(absUrl); }
                    }}
                  >
                    <View style={styles.mediaImageWrapper}>
                      <Image
                        source={{ uri: absUrl }}
                        style={styles.mediaImage}
                        contentFit="cover"
                        cachePolicy="none"
                        transition={300}
                        onError={(e) => console.log('[Media] Load error:', absUrl, e)}
                      />
                    </View>
                  </TouchableOpacity>
                );
              })}
            </View>
          )}

          {/* Show image icon if media exists but no text content */}
          {hasMedia && !item.content && (
            <View style={styles.mediaOnlyIndicator}>
              <Ionicons name="image" size={14} color={isUser ? colors.userBubbleText : colors.textSecondary} />
              <Text style={[styles.mediaOnlyText, { color: isUser ? colors.userBubbleText : colors.contactBubbleText }]}>Photo</Text>
            </View>
          )}

          {/* Text content */}
          {item.content ? (
            <Text style={[
              styles.messageText,
              isRichContent
                ? { color: colors.text }
                : isUser ? { color: colors.userBubbleText } : { color: colors.contactBubbleText },
            ]}>
              {highlight(item.content)}
            </Text>
          ) : null}

          {item.intent_detected && (
            <View style={styles.intentBadge}>
              <Ionicons name="flag" size={10} color="#FF9500" />
              <Text style={styles.intentText}>{item.intent_detected}</Text>
            </View>
          )}

          {item.channel === 'sms_personal' && isUser && (
            <View style={styles.personalSmsBadge}>
              <Ionicons name="phone-portrait-outline" size={10} color={colors.textSecondary} />
              <Text style={styles.personalSmsText}>Sent from your phone</Text>
            </View>
          )}

          {item.channel === 'email' && isUser && (
            <View style={styles.personalSmsBadge}>
              <Ionicons name="mail-outline" size={10} color="#AF52DE" />
              <Text style={[styles.personalSmsText, { color: '#AF52DE' }]}>Sent via email</Text>
            </View>
          )}

          {isUser && (item as any).status === 'failed' && (
            <View style={styles.personalSmsBadge} data-testid="message-failed-badge">
              <Ionicons name="alert-circle" size={10} color="#FF453A" />
              <Text style={[styles.personalSmsText, { color: '#FF453A', flexShrink: 1 }]} numberOfLines={2}>Not delivered{(item as any).error_message ? ` · ${String((item as any).error_message).slice(0, 60)}` : ''}</Text>
            </View>
          )}

          {isUser && (item as any).media_dropped && (
            <View style={styles.personalSmsBadge} data-testid="message-media-dropped-badge">
              <Ionicons name="image-outline" size={10} color="#FF9F0A" />
              <Text style={[styles.personalSmsText, { color: '#FF9F0A', flexShrink: 1 }]} numberOfLines={2}>Sent without the photo (carrier rejected it)</Text>
            </View>
          )}
        </View>

        {/* Auto-applied keyword tags */}
        {item.auto_tags?.length > 0 && (
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginTop: 3, justifyContent: isUser ? 'flex-end' : 'flex-start' }} data-testid="message-auto-tags">
            {item.auto_tags.map((t: string) => (
              <View key={t} style={{ flexDirection: 'row', alignItems: 'center', gap: 3, backgroundColor: '#5856D620', borderRadius: 8, paddingHorizontal: 6, paddingVertical: 2 }}>
                <Ionicons name="pricetag" size={9} color="#5856D6" />
                <Text style={{ fontSize: 11, color: '#5856D6', fontWeight: '600' }}>{t}</Text>
              </View>
            ))}
          </View>
        )}
      </View>
    </>
  );
};
