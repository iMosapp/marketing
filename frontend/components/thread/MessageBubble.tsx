import React from 'react';
import { View, Text, TouchableOpacity, Platform, Linking } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { format } from 'date-fns';
import { Image } from 'expo-image';
import { router } from 'expo-router';
import { API_BASE_URL } from '../../services/api';

const URL_RE = /(https?:\/\/[^\s<>"')\]]+)/g;
const openUrl = (url: string) => { if (Platform.OS === 'web') window.open(url, '_blank'); else Linking.openURL(url); };
const CARD_LABEL: Record<string, string> = { congrats: 'Congrats card', birthday: 'Birthday card', anniversary: 'Anniversary card', thank_you: 'Thank-you card', thankyou: 'Thank-you card', welcome: 'Welcome card', holiday: 'Holiday card' };

// A sent card, shown as the actual card so the rep can see (and reopen) exactly what the customer got.
const CardTile = ({ card, colors }: { card: any; colors: any }) => {
  const label = CARD_LABEL[card.card_type] || `${String(card.card_type || 'custom').replace(/_/g, ' ')} card`;
  const open = () => router.push(`/congrats/${card.card_id}?preview=rep` as any);
  return (
    <TouchableOpacity activeOpacity={0.9} onPress={open} style={{ flexDirection: 'row', gap: 12, backgroundColor: colors.bg, borderRadius: 14, padding: 10, marginBottom: 8, borderWidth: 1, borderColor: colors.border }} testID="card-preview-tile" dataSet={{ testid: 'card-preview-tile' }}>
      <Image source={{ uri: card.image_path ? `${API_BASE_URL}${card.image_path}` : card.image_url }} style={{ width: 72, height: 90, borderRadius: 10, backgroundColor: card.background || '#111' }} contentFit="cover" transition={200} />
      <View style={{ flex: 1, justifyContent: 'center', gap: 3 }}>
        <Text style={{ fontSize: 11, fontWeight: '800', letterSpacing: 0.4, textTransform: 'uppercase', color: card.accent || '#C9A962' }}>{label}</Text>
        <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }} numberOfLines={2}>{card.headline || `For ${card.customer_name || 'your customer'}`}</Text>
        <Text style={{ fontSize: 12, color: card.views > 0 ? '#34C759' : colors.textTertiary }} testID="card-preview-opens">{card.views > 0 ? `Opened ${card.views}\u00d7` : 'Not opened yet'}</Text>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 2 }}>
          <Ionicons name="eye-outline" size={14} color="#007AFF" />
          <Text style={{ fontSize: 12, fontWeight: '700', color: '#007AFF' }}>View card</Text>
        </View>
      </View>
    </TouchableOpacity>
  );
};

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
  onShowDelivery?: (item: any) => void;
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
  contactName, myPhoto, userName, highlight, isCurrentMatch, onShowDelivery,
}: Props) => {
  const hasMedia = item.has_media && item.media_urls && item.media_urls.length > 0;
  const status = (item as any).status as string | undefined;
  const cardLink = (item.links || []).find((l: any) => l && l.card);
  const linkify = (text: string) => text.split(URL_RE).map((seg, i) => /^https?:\/\//.test(seg)
    ? <Text key={i} onPress={() => openUrl(seg)} style={{ textDecorationLine: 'underline', fontWeight: '600' }} testID="message-link" dataSet={{ testid: 'message-link' }}>{highlight(seg)}</Text>
    : <React.Fragment key={i}>{highlight(seg)}</React.Fragment>);
  const canInspect = isUser && !!onShowDelivery && !!item._id && item.channel !== 'sms_personal' && item.channel !== 'email';
  const Bubble: any = canInspect ? TouchableOpacity : View;

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

        <Bubble
          {...(canInspect ? { activeOpacity: 0.85, onPress: () => onShowDelivery!(item), testID: 'outbound-message-bubble', dataSet: { testid: 'outbound-message-bubble' } } : {})}
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

          {cardLink ? <CardTile card={cardLink.card} colors={colors} /> : null}

          {/* Text content */}
          {item.content ? (
            <Text style={[
              styles.messageText,
              isRichContent
                ? { color: colors.text }
                : isUser ? { color: colors.userBubbleText } : { color: colors.contactBubbleText },
            ]}>
              {linkify(item.content)}
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

          {item.channel === 'email' && !isUser && (
            <View style={styles.personalSmsBadge} testID="message-email-reply-badge" dataSet={{ testid: 'message-email-reply-badge' } as any}>
              <Ionicons name="mail-open-outline" size={10} color="#AF52DE" />
              <Text style={[styles.personalSmsText, { color: '#AF52DE', flexShrink: 1 }]} numberOfLines={1}>Replied via email{(item as any).subject ? ` · ${(item as any).subject}` : ''}</Text>
            </View>
          )}

          {isUser && status === 'delivered' && (
            <View style={styles.personalSmsBadge} data-testid="message-delivered-badge">
              <Ionicons name="checkmark-done" size={12} color="#34C759" />
              <Text style={[styles.personalSmsText, { color: '#34C759' }]}>Delivered</Text>
            </View>
          )}

          {canInspect && (status === 'sent' || status === 'sending') && (
            <View style={styles.personalSmsBadge} data-testid="message-sent-badge">
              <Ionicons name="checkmark" size={12} color={colors.textTertiary} />
              <Text style={[styles.personalSmsText, { color: colors.textTertiary }]}>{status === 'sending' ? 'Sending' : 'Sent'} · tap for details</Text>
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

          {isUser && (item as any).resent_as && (
            <View style={styles.personalSmsBadge} data-testid="message-resent-badge">
              <Ionicons name="refresh" size={10} color={colors.textTertiary} />
              <Text style={[styles.personalSmsText, { color: colors.textTertiary }]}>Resent as plain text</Text>
            </View>
          )}
        </Bubble>

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
