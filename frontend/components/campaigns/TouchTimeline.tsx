import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Touch, touchMinutes, whenLabel, renderSample, Sample, CARD_TYPES, GOLD, GREEN, PURPLE, tid } from './utils';

type Props = {
  touches: Touch[];
  aiPersonalizes: boolean;
  preview: boolean;
  sample: Sample;
  editable: boolean;
  colors: any;
  onEdit: (t: Touch, index: number) => void;
  onAddAfter: (index: number) => void;
};

// Gold rail timeline (same rhythm as the Workflows screen): when · dot · what
export function TouchTimeline({ touches, aiPersonalizes, preview, sample, editable, colors, onEdit, onAddAfter }: Props) {
  return (
    <View {...tid('touch-timeline')}>
      {touches.map((t, i) => {
        const instant = touchMinutes(t) === 0;
        const isCard = t.actionType === 'send_card';
        const card = CARD_TYPES.find(c => c.key === t.cardType);
        const body = isCard ? '' : preview ? renderSample(t.message, sample) : t.message;
        const last = i === touches.length - 1;
        return (
          <View key={t.id} style={{ flexDirection: 'row', gap: 10 }} {...tid(`touch-row-${i}`)}>
            <View style={{ width: 56, alignItems: 'flex-end', paddingTop: 14 }}>
              <Text style={{ fontSize: 12, fontWeight: '800', color: instant ? GREEN : GOLD }}>{whenLabel(t)}</Text>
            </View>
            <View style={{ width: 14, alignItems: 'center' }}>
              <View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: instant ? GREEN : isCard ? PURPLE : GOLD, marginTop: 16, shadowColor: GOLD, shadowOpacity: 0.5, shadowRadius: 4 }} />
              <View style={{ flex: 1, width: 2, backgroundColor: colors.border, marginTop: 4, opacity: last ? 0 : 1 }} />
            </View>
            <View style={{ flex: 1, paddingBottom: last ? 0 : 6 }}>
              <TouchableOpacity onPress={() => onEdit(t, i)} activeOpacity={0.8} style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 12, gap: 8 }} {...tid(`touch-card-${i}`)}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                  <View style={{ paddingHorizontal: 8, paddingVertical: 3, borderRadius: 7, backgroundColor: isCard ? PURPLE + '22' : GREEN + '22' }}>
                    <Text style={{ fontSize: 10, fontWeight: '800', color: isCard ? PURPLE : GREEN, letterSpacing: 0.6 }}>{isCard ? 'CARD' : 'TEXT'}</Text>
                  </View>
                  {!isCard && aiPersonalizes ? (
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 7, backgroundColor: GOLD + '22' }}>
                      <Ionicons name="sparkles" size={10} color={GOLD} />
                      <Text style={{ fontSize: 10, fontWeight: '800', color: GOLD, letterSpacing: 0.6 }}>JESSI PERSONALIZES</Text>
                    </View>
                  ) : null}
                  {t.media_urls?.length ? (
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 7, backgroundColor: colors.surface }}>
                      <Ionicons name="image" size={10} color={colors.textSecondary} />
                      <Text style={{ fontSize: 10, fontWeight: '800', color: colors.textSecondary }}>{t.media_urls.length > 1 ? `${t.media_urls.length} PHOTOS` : 'PHOTO'}</Text>
                    </View>
                  ) : null}
                  <View style={{ flex: 1 }} />
                  {editable ? <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} /> : null}
                </View>
                {isCard ? (
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                    <View style={{ width: 34, height: 34, borderRadius: 10, backgroundColor: (card?.color || PURPLE) + '22', alignItems: 'center', justifyContent: 'center' }}>
                      <Ionicons name={(card?.icon as any) || 'gift'} size={16} color={card?.color || PURPLE} />
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>{card ? `${card.label} card` : 'Pick a card'}</Text>
                      <Text style={{ fontSize: 12, color: colors.textSecondary }} numberOfLines={1}>{t.message ? (preview ? renderSample(t.message, sample) : t.message) : 'Your photo + a link they can open'}</Text>
                    </View>
                  </View>
                ) : (
                  <Text style={{ fontSize: 14, color: body ? colors.text : colors.textTertiary, lineHeight: 20, fontStyle: body ? 'normal' : 'italic' }} numberOfLines={preview ? undefined : 3}>
                    {body || 'Tap to write this text'}
                  </Text>
                )}
              </TouchableOpacity>
              {editable ? (
                <TouchableOpacity onPress={() => onAddAfter(i)} hitSlop={6} style={{ alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: 4, paddingVertical: 6, paddingHorizontal: 4 }} {...tid(`touch-add-after-${i}`)}>
                  <Ionicons name="add-circle-outline" size={16} color={colors.textTertiary} />
                  <Text style={{ fontSize: 11, color: colors.textTertiary, fontWeight: '600' }}>{last ? 'Add a touch' : 'Insert a touch here'}</Text>
                </TouchableOpacity>
              ) : <View style={{ height: 8 }} />}
            </View>
          </View>
        );
      })}
    </View>
  );
}
