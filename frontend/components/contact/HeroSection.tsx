/**
 * HeroSection — compact profile hero for the contact detail screen.
 * Extracted from contact/[id].tsx (render-only; all state lives in the parent).
 */
import React from 'react';
import { View, Text, TouchableOpacity, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Image } from 'expo-image';
import { useRouter } from 'expo-router';
import { showSimpleAlert } from '../../services/alert';
import { resolvePhotoUrl } from '../../utils/photoUrl';
import { getTimeInSystem, getTimeInSystemLabel, formatDateUTC } from '../../utils/contactHelpers';

export default function HeroSection(props: any) {
  const {
    s, colors, contact, stats, isEditing, isNewContact, fullName, initials,
    intelData, availableTags, contactEnrollments, isRecording, contactId,
    pickImage, viewFullPhoto, startRecording, stopRecording,
    handleAutomationChipPress, onAddTag,
  } = props;
  const router = useRouter();
  const timeValue = getTimeInSystem(stats.created_at);
  const timeLabel = getTimeInSystemLabel(stats.created_at);

  return (
    <View style={[s.heroSection, { backgroundColor: colors.bg }]} data-testid="contact-hero">
      <View style={s.heroRow}>
        {/* Left: Avatar */}
        <View style={s.heroAvatarContainer}>
          <TouchableOpacity onPress={isEditing ? pickImage : viewFullPhoto} activeOpacity={isEditing ? 0.7 : 0.8} data-testid="contact-avatar-btn">
            {contact.photo ? (
              <Image source={{ uri: resolvePhotoUrl(contact.photo) }} style={s.heroAvatar} />
            ) : (
              <View style={s.heroAvatarPlaceholder}>
                <Text style={s.heroInitials}>{initials}</Text>
              </View>
            )}
            {isEditing && (
              <View style={s.heroCameraBadge}>
                <Ionicons name="camera" size={12} color={colors.text} />
              </View>
            )}
          </TouchableOpacity>
          {!isNewContact && stats.total_touchpoints > 0 && (
            <View style={s.touchpointBadge} data-testid="touchpoint-badge">
              <Text style={s.touchpointBadgeText}>{stats.total_touchpoints}</Text>
            </View>
          )}
        </View>

        {/* Right: Name + Info */}
        <View style={s.heroInfo}>
          <Text style={[s.heroName, { color: colors.text }]} data-testid="contact-name" numberOfLines={1}>{fullName}</Text>

          {/* Vehicle / Product / Highlight */}
          {contact.vehicle ? (
            <View style={s.heroHighlight}>
              <Ionicons name="pricetag" size={12} color="#C9A962" />
              <Text style={s.heroHighlightText} numberOfLines={1}>{contact.vehicle}</Text>
            </View>
          ) : null}

          {/* Location + Time compact */}
          <View style={s.heroMetaRow}>
            {(contact.address_city || contact.address_state) ? (
              <View style={s.heroMetaItem}>
                <Ionicons name="location-outline" size={11} color={colors.textTertiary} />
                <Text style={s.heroMetaText}>{[contact.address_city, contact.address_state].filter(Boolean).join(', ')}</Text>
              </View>
            ) : null}
            {(contact.occupation || contact.employer || contact.organization_name) ? (
              <View style={s.heroMetaItem}>
                <Ionicons name="briefcase-outline" size={11} color={colors.textTertiary} />
                <Text style={s.heroMetaText}>{[contact.occupation, contact.employer || contact.organization_name].filter(Boolean).join(' at ')}</Text>
              </View>
            ) : null}
            {!isNewContact && (
              <View style={s.heroMetaItem}>
                <Ionicons name="time-outline" size={11} color={colors.textTertiary} />
                <Text style={s.heroMetaText}>{timeValue} {timeLabel} relationship</Text>
              </View>
            )}
          </View>
        </View>

        {/* Phone + Voice Note icons next to contact name */}
        {!isEditing && !isNewContact && (
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginLeft: 8 }}>
            {/* Click-to-Call */}
            <TouchableOpacity
              onPress={() => {
                const phone = contact?.phone || '';
                const name  = contact?.name || `${contact?.first_name || ''} ${contact?.last_name || ''}`.trim();
                const cid   = contactId;
                if (phone) {
                  router.push({ pathname: '/call-screen', params: { phone, contact_name: name, contact_id: cid } } as any);
                } else {
                  showSimpleAlert('No Phone', 'This contact has no phone number saved.');
                }
              }}
              activeOpacity={0.7}
              style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: '#007AFF', alignItems: 'center', justifyContent: 'center', shadowColor: '#007AFF', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.4, shadowRadius: 6, elevation: 4 }}
              data-testid="hero-call-btn"
            >
              <Ionicons name="call" size={20} color="#FFF" />
            </TouchableOpacity>

            {/* Voice Note — green mic button */}
            <TouchableOpacity
              onPress={isRecording ? stopRecording : startRecording}
              activeOpacity={0.7}
              hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
              style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: isRecording ? '#FF3B30' : '#34C759', alignItems: 'center', justifyContent: 'center', shadowColor: isRecording ? '#FF3B30' : '#34C759', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.4, shadowRadius: 6, elevation: 4, zIndex: 10 }}
              data-testid="hero-record-btn"
            >
              <Ionicons name={isRecording ? 'stop' : 'mic'} size={22} color="#FFF" />
            </TouchableOpacity>
          </View>
        )}
      </View>

      {/* Compact stats line */}
      {!isNewContact && (
        <View style={s.heroStatsLine} data-testid="contact-stats-row">
          <View style={s.heroStatChip}>
            <Text style={s.heroStatVal}>{stats.total_touchpoints}</Text>
            <Text style={s.heroStatLbl}>tchs</Text>
          </View>
          <Text style={s.heroStatDot}>·</Text>
          <View style={s.heroStatChip}>
            <Text style={s.heroStatVal}>{stats.messages_sent}</Text>
            <Text style={s.heroStatLbl}>msgs</Text>
          </View>
          <Text style={s.heroStatDot}>·</Text>
          <View style={s.heroStatChip}>
            <Text style={s.heroStatVal}>{stats.link_clicks}</Text>
            <Text style={s.heroStatLbl}>clks</Text>
          </View>
          <Text style={s.heroStatDot}>·</Text>
          <View style={s.heroStatChip}>
            <Text style={s.heroStatVal}>{stats.campaigns}</Text>
            <Text style={s.heroStatLbl}>cmpn</Text>
          </View>
          <Text style={s.heroStatDot}>·</Text>
          <View style={s.heroStatChip}>
            <Text style={s.heroStatVal}>{stats.referral_count ?? contact.referral_count}</Text>
            <Text style={s.heroStatLbl}>refs</Text>
          </View>
        </View>
      )}

      {/* Linked App Account Card */}
      {!isNewContact && !isEditing && contact.linked_user_id && (
        <View
          style={{
            flexDirection: 'row', alignItems: 'center',
            backgroundColor: '#007AFF15', borderRadius: 10,
            paddingHorizontal: 12, paddingVertical: 8, marginTop: 8,
            borderWidth: 1, borderColor: '#007AFF30',
          }}
          data-testid="linked-account-card"
        >
          <Ionicons name="shield-checkmark" size={18} color="#007AFF" />
          <View style={{ marginLeft: 8, flex: 1 }}>
            <Text style={{ color: '#007AFF', fontWeight: '600', fontSize: 13 }}>
              {contact.linked_role ? (contact.linked_role === 'super_admin' ? 'Super Admin' : contact.linked_role === 'org_admin' ? 'Admin' : contact.linked_role === 'store_manager' ? 'Manager' : 'User') : 'User'} Account
            </Text>
            {(contact.linked_store_name || contact.linked_org_name) && (
              <Text style={{ color: colors.textSecondary, fontSize: 12, marginTop: 1 }}>
                {[contact.linked_store_name, contact.linked_org_name].filter(Boolean).join(' · ')}
              </Text>
            )}
          </View>
        </View>
      )}

      {/* AI Relationship Summary — auto-displays below name when intel is cached */}
      {!isNewContact && intelData?.summary ? (
        <View style={{ marginHorizontal: 16, marginTop: 4, marginBottom: 4 }}>
          <Text
            style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18, textAlign: 'center', fontStyle: 'italic' }}
            numberOfLines={3}
            data-testid="contact-intel-summary"
          >
            {intelData.summary.split('\n')[0]}
          </Text>
        </View>
      ) : null}

      {/* Tags + Automations Strip (merged) */}
      {!isNewContact && (
        <View style={s.heroTagsStrip} data-testid="hero-tags-strip">
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6, paddingBottom: 4, paddingRight: 16, alignItems: 'center' }}>
            {contact.tags.map((tag: string, i: number) => {
              const info = availableTags.find((t: any) => t.name === tag);
              const chipColor = info?.color || colors.textSecondary;
              const displayTag = tag === 'imos_user' ? 'User' : tag === 'imos_super_admin' ? 'Super Admin' : tag === 'imos_org_admin' ? 'Admin' : tag === 'imos_store_manager' ? 'Manager' : tag;
              return (
                <View key={`tag-${i}`} style={[s.heroTagChip, { borderColor: `${chipColor}40`, backgroundColor: `${chipColor}10` }]}>
                  <Ionicons name={(info?.icon || 'pricetag') as any} size={13} color={chipColor} />
                  <Text style={[s.heroTagChipText, { color: chipColor }]} numberOfLines={1}>{displayTag}</Text>
                </View>
              );
            })}
            {contact.birthday && (() => {
              const isPaused = contact.disabled_automations.includes('birthday');
              return (
              <TouchableOpacity
                style={[s.heroTagChip, {
                  borderColor: isPaused ? '#FF950040' : '#FF2D5540',
                  backgroundColor: isPaused ? '#FF950008' : '#FF2D5510',
                  borderStyle: 'dashed',
                }]}
                onPress={() => handleAutomationChipPress('birthday', 'Birthday', '#FF2D55', contact.birthday)}
                activeOpacity={0.7}
                data-testid="auto-birthday"
              >
                {isPaused && <Ionicons name="pause-circle" size={14} color="#FF9500" style={{ marginRight: 1 }} />}
                <Ionicons name="gift" size={13} color={isPaused ? '#999' : '#FF2D55'} />
                <Text style={[s.heroTagChipText, { color: isPaused ? '#999' : '#FF2D55', textDecorationLine: isPaused ? 'line-through' : 'none' }]} numberOfLines={1}>{formatDateUTC(contact.birthday)}</Text>
              </TouchableOpacity>
              );
            })()}
            {contact.anniversary && (() => {
              const isPaused = contact.disabled_automations.includes('anniversary');
              return (
              <TouchableOpacity
                style={[s.heroTagChip, {
                  borderColor: isPaused ? '#FF950040' : '#FF6B6B40',
                  backgroundColor: isPaused ? '#FF950008' : '#FF6B6B10',
                  borderStyle: 'dashed',
                }]}
                onPress={() => handleAutomationChipPress('anniversary', 'Anniversary', '#FF6B6B', contact.anniversary)}
                activeOpacity={0.7}
                data-testid="auto-anniversary"
              >
                {isPaused && <Ionicons name="pause-circle" size={14} color="#FF9500" style={{ marginRight: 1 }} />}
                <Ionicons name="heart" size={13} color={isPaused ? '#999' : '#FF6B6B'} />
                <Text style={[s.heroTagChipText, { color: isPaused ? '#999' : '#FF6B6B', textDecorationLine: isPaused ? 'line-through' : 'none' }]} numberOfLines={1}>{formatDateUTC(contact.anniversary)}</Text>
              </TouchableOpacity>
              );
            })()}
            {contact.date_sold && (() => {
              const isPaused = contact.disabled_automations.includes('sold_date');
              return (
              <TouchableOpacity
                style={[s.heroTagChip, {
                  borderColor: isPaused ? '#FF950040' : '#34C75940',
                  backgroundColor: isPaused ? '#FF950008' : '#34C75910',
                  borderStyle: 'dashed',
                }]}
                onPress={() => handleAutomationChipPress('sold_date', 'Sold Date', '#34C759', contact.date_sold)}
                activeOpacity={0.7}
                data-testid="auto-sold"
              >
                {isPaused && <Ionicons name="pause-circle" size={14} color="#FF9500" style={{ marginRight: 1 }} />}
                <Ionicons name="car-sport" size={13} color={isPaused ? '#999' : '#34C759'} />
                <Text style={[s.heroTagChipText, { color: isPaused ? '#999' : '#34C759', textDecorationLine: isPaused ? 'line-through' : 'none' }]} numberOfLines={1}>{formatDateUTC(contact.date_sold)}</Text>
              </TouchableOpacity>
              );
            })()}
            {contactEnrollments.map((e: any, i: number) => {
              const chipColor = e.status === 'completed' ? '#34C759' : '#007AFF';
              return (
                <View key={`camp-${i}`} style={[s.heroTagChip, { borderColor: `${chipColor}40`, backgroundColor: `${chipColor}10`, borderStyle: 'dashed' }]} data-testid={`campaign-chip-${i}`}>
                  <Ionicons name={e.status === 'completed' ? 'checkmark-circle' : 'play-circle'} size={13} color={chipColor} />
                  <Text style={[s.heroTagChipText, { color: chipColor }]} numberOfLines={1}>{e.campaign_name}</Text>
                  {e.status !== 'completed' && (
                    <Text style={{ fontSize: 12, color: chipColor, fontWeight: '600' }}>{e.current_step}/{e.total_steps}</Text>
                  )}
                </View>
              );
            })}
            <TouchableOpacity onPress={onAddTag} style={[s.heroTagChip, { borderColor: '#007AFF40', backgroundColor: '#007AFF08' }]} data-testid="hero-add-tag-btn">
              <Ionicons name="add" size={14} color="#007AFF" />
            </TouchableOpacity>
          </ScrollView>
        </View>
      )}
    </View>
  );
}
