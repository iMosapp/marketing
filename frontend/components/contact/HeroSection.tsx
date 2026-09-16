/**
 * HeroSection — who this is, in one glance: photo, name, vehicle, where they are, how long you've known them, tags.
 * Dates and campaign progress live in Details (Important Dates / Campaigns); relationship numbers live in Details too.
 */
import React from 'react';
import { View, Text, TouchableOpacity, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Image } from 'expo-image';
import { resolvePhotoUrl } from '../../utils/photoUrl';
import { getTimeInSystem, getTimeInSystemLabel } from '../../utils/contactHelpers';

const ROLE_TAGS: Record<string, string> = { imos_user: 'User', imos_super_admin: 'Super Admin', imos_org_admin: 'Admin', imos_store_manager: 'Manager' };

export default function HeroSection(props: any) {
  const { s, colors, contact, stats, isEditing, isNewContact, fullName, initials, availableTags, pickImage, viewFullPhoto, onAddTag } = props;
  const meta = [
    [contact.address_city, contact.address_state].filter(Boolean).join(', '),
    [contact.occupation, contact.employer || contact.organization_name].filter(Boolean).join(' at '),
    !isNewContact && stats?.created_at ? `${getTimeInSystem(stats.created_at)} ${getTimeInSystemLabel(stats.created_at)} relationship` : '',
  ].filter(Boolean);

  return (
    <View style={[s.heroSection, { backgroundColor: colors.bg }]} data-testid="contact-hero">
      <View style={s.heroRow}>
        <View style={s.heroAvatarContainer}>
          <TouchableOpacity onPress={isEditing ? pickImage : viewFullPhoto} activeOpacity={isEditing ? 0.7 : 0.8} data-testid="contact-avatar-btn">
            {contact.photo ? (
              <Image source={{ uri: resolvePhotoUrl(contact.photo) }} style={s.heroAvatar} />
            ) : (
              <View style={s.heroAvatarPlaceholder}><Text style={s.heroInitials}>{initials}</Text></View>
            )}
            {isEditing && <View style={s.heroCameraBadge}><Ionicons name="camera" size={12} color={colors.text} /></View>}
          </TouchableOpacity>
          {!isNewContact && stats.total_touchpoints > 0 && (
            <View style={s.touchpointBadge} data-testid="touchpoint-badge"><Text style={s.touchpointBadgeText}>{stats.total_touchpoints}</Text></View>
          )}
        </View>

        <View style={s.heroInfo}>
          <Text style={[s.heroName, { color: colors.text }]} data-testid="contact-name" numberOfLines={2}>{fullName}</Text>
          {contact.vehicle ? (
            <View style={s.heroHighlight}>
              <Ionicons name="car-sport" size={13} color="#C9A962" />
              <Text style={s.heroHighlightText} numberOfLines={1}>{contact.vehicle}</Text>
            </View>
          ) : null}
          {meta.length > 0 && (
            <Text style={s.heroMetaText} numberOfLines={2} data-testid="contact-meta-line">{meta.join('  ·  ')}</Text>
          )}
        </View>
      </View>

      {!isNewContact && !isEditing && contact.linked_user_id && (
        <View style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: '#007AFF15', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 8, marginTop: 10, borderWidth: 1, borderColor: '#007AFF30' }} data-testid="linked-account-card">
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
        <View style={s.heroTagsStrip} data-testid="hero-tags-strip">
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6, paddingRight: 16, alignItems: 'center' }}>
            {contact.tags.map((tag: string, i: number) => {
              const info = availableTags.find((t: any) => t.name === tag);
              const chipColor = info?.color || colors.textSecondary;
              return (
                <View key={`tag-${i}`} style={[s.heroTagChip, { borderColor: `${chipColor}40`, backgroundColor: `${chipColor}10` }]}>
                  <Ionicons name={(info?.icon || 'pricetag') as any} size={12} color={chipColor} />
                  <Text style={[s.heroTagChipText, { color: chipColor }]} numberOfLines={1}>{ROLE_TAGS[tag] || tag}</Text>
                </View>
              );
            })}
            <TouchableOpacity onPress={onAddTag} style={[s.heroTagChip, { borderColor: colors.border, backgroundColor: 'transparent', gap: 4 }]} data-testid="hero-add-tag-btn">
              <Ionicons name="add" size={13} color={colors.textSecondary} />
              <Text style={[s.heroTagChipText, { color: colors.textSecondary }]}>{contact.tags.length ? 'Tag' : 'Add a tag'}</Text>
            </TouchableOpacity>
          </ScrollView>
        </View>
      )}
    </View>
  );
}
