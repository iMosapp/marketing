/**
 * HeroSection — who this is, in one glance: photo, name, what they drive + when they bought, where they are, the top three tags (+N for the rest).
 * Relationship numbers live in the Snapshot card; every tag lives under Profile › Tags.
 */
import React, { useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { format } from 'date-fns';
import { tid } from '../scripts/shared';
import { Image } from 'expo-image';
import { resolvePhotoUrl } from '../../utils/photoUrl';

const ROLE_TAGS: Record<string, string> = { imos_user: 'User', imos_super_admin: 'Super Admin', imos_org_admin: 'Admin', imos_store_manager: 'Manager' };
const MAX_TAGS = 3;

export default function HeroSection(props: any) {
  const { s, colors, contact, stats, isEditing, isNewContact, fullName, initials, availableTags, pickImage, viewFullPhoto, onAddTag } = props;
  const [allTags, setAllTags] = useState(false);
  const soldLine = contact.date_sold ? `Sold ${format(new Date(contact.date_sold), 'MMM d')}` : '';
  const meta = [
    [contact.address_city, contact.address_state].filter(Boolean).join(', '),
    [contact.occupation, contact.employer || contact.organization_name].filter(Boolean).join(' at '),
  ].filter(Boolean);
  const tags: string[] = contact.tags || [];
  const shown = allTags || isEditing ? tags : tags.slice(0, MAX_TAGS);
  const hidden = tags.length - shown.length;

  return (
    <View style={[s.heroSection, { backgroundColor: colors.bg }]} {...tid('contact-hero')}>
      <View style={s.heroRow}>
        <View style={s.heroAvatarContainer}>
          <TouchableOpacity onPress={isEditing ? pickImage : viewFullPhoto} activeOpacity={isEditing ? 0.7 : 0.8} {...tid('contact-avatar-btn')}>
            {contact.photo ? (
              <Image source={{ uri: resolvePhotoUrl(contact.photo) }} style={s.heroAvatar} />
            ) : (
              <View style={s.heroAvatarPlaceholder}><Text style={s.heroInitials}>{initials}</Text></View>
            )}
            {isEditing && <View style={s.heroCameraBadge}><Ionicons name="camera" size={12} color={colors.text} /></View>}
          </TouchableOpacity>
          {!isNewContact && stats.total_touchpoints > 0 && (
            <View style={s.touchpointBadge} {...tid('touchpoint-badge')}><Text style={s.touchpointBadgeText}>{stats.total_touchpoints}</Text></View>
          )}
        </View>

        <View style={s.heroInfo}>
          <Text style={[s.heroName, { color: colors.text }]} {...tid('contact-name')} numberOfLines={2}>{fullName}</Text>
          {(contact.vehicle || soldLine) ? (
            <View style={s.heroHighlight} {...tid('contact-highlight-line')}>
              <Ionicons name="car-sport" size={13} color="#C9A962" />
              {!!contact.vehicle && <Text style={[s.heroHighlightText, { flexShrink: 1 }]} numberOfLines={1}>{contact.vehicle}</Text>}
              {!!soldLine && <Text style={[s.heroHighlightText, { flexShrink: 0 }]} numberOfLines={1}>{contact.vehicle ? `  ·  ${soldLine}` : soldLine}</Text>}
            </View>
          ) : null}
          {meta.length > 0 && (
            <Text style={s.heroMetaText} numberOfLines={1} {...tid('contact-meta-line')}>{meta.join('  ·  ')}</Text>
          )}
        </View>
      </View>

      {!isNewContact && !isEditing && contact.linked_user_id && (
        <View style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: '#007AFF15', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 8, marginTop: 10, borderWidth: 1, borderColor: '#007AFF30' }} {...tid('linked-account-card')}>
          <Ionicons name="shield-checkmark" size={18} color="#007AFF" />
          <View style={{ marginLeft: 8, flex: 1 }}>
            <Text style={{ color: '#007AFF', fontWeight: '600', fontSize: 13 }}>{(ROLE_TAGS[`imos_${contact.linked_role}`] || 'User')} Account</Text>
            {(contact.linked_store_name || contact.linked_org_name) && (
              <Text style={{ color: colors.textSecondary, fontSize: 12, marginTop: 1 }}>{[contact.linked_store_name, contact.linked_org_name].filter(Boolean).join(' · ')}</Text>
            )}
          </View>
        </View>
      )}

      {!isNewContact && (
        <View style={s.heroTagsStrip} {...tid('hero-tags-strip')}>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
            {shown.map((tag: string, i: number) => {
              const info = availableTags.find((t: any) => t.name === tag);
              const chipColor = info?.color || colors.textSecondary;
              return (
                <View key={`tag-${i}`} style={[s.heroTagChip, { borderColor: `${chipColor}40`, backgroundColor: `${chipColor}10` }]}>
                  <Ionicons name={(info?.icon || 'pricetag') as any} size={12} color={chipColor} />
                  <Text style={[s.heroTagChipText, { color: chipColor }]} numberOfLines={1}>{ROLE_TAGS[tag] || tag}</Text>
                </View>
              );
            })}
            {hidden > 0 && (
              <TouchableOpacity onPress={() => setAllTags(true)} style={[s.heroTagChip, { borderColor: colors.border, backgroundColor: colors.card }]} {...tid('hero-more-tags-btn')}>
                <Text style={[s.heroTagChipText, { color: colors.textSecondary }]}>+{hidden}</Text>
              </TouchableOpacity>
            )}
            {allTags && tags.length > MAX_TAGS && (
              <TouchableOpacity onPress={() => setAllTags(false)} style={[s.heroTagChip, { borderColor: colors.border, backgroundColor: 'transparent' }]} {...tid('hero-less-tags-btn')}>
                <Text style={[s.heroTagChipText, { color: colors.textSecondary }]}>Less</Text>
              </TouchableOpacity>
            )}
            <TouchableOpacity onPress={onAddTag} style={[s.heroTagChip, { borderColor: colors.border, backgroundColor: 'transparent', gap: 4 }]} {...tid('hero-add-tag-btn')}>
              <Ionicons name="add" size={13} color={colors.textSecondary} />
              <Text style={[s.heroTagChipText, { color: colors.textSecondary }]}>{tags.length ? 'Tag' : 'Add a tag'}</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}
    </View>
  );
}
