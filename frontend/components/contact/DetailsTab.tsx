/**
 * DetailsTab ("Profile") — the record, in reading order: how to reach them, important dates, purchases, tags, notes, referrals,
 * campaigns, then a folded "More" (follow-up checklist, share profile, push to CRM).
 * Personal intelligence + relationship numbers live in the Snapshot card; voice memos live under History › Memos.
 * Extracted from contact/[id].tsx (render-only; all state lives in the parent).
 */
import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, Switch, Modal, Platform, Linking } from 'react-native';
import DateTimePicker from '@react-native-community/datetimepicker';
import { Ionicons } from '@expo/vector-icons';
import { tid } from '../scripts/shared';
import { useRouter } from 'expo-router';
import { format } from 'date-fns';
import { contactsAPI } from '../../services/api';
import { useThemeStore } from '../../store/themeStore';
import PurchaseHistorySection from './PurchaseHistorySection';
import CrmPushSection from './CrmPushSection';
import ShareProfileSection from './ShareProfileSection';

const ROLE_TAGS: Record<string, string> = { imos_user: 'User', imos_super_admin: 'Super Admin', imos_org_admin: 'Admin', imos_store_manager: 'Manager' };
const toYMD = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

export function prettyPhone(p?: string): string {
  const d = String(p || '').replace(/\D/g, '');
  if (d.length === 11 && d.startsWith('1')) return `(${d.slice(1, 4)}) ${d.slice(4, 7)}-${d.slice(7)}`;
  if (d.length === 10) return `(${d.slice(0, 3)}) ${d.slice(3, 6)}-${d.slice(6)}`;
  return p || '';
}

function BirthdayModal({ visible, onClose, onSave, current, s, colors, saving }: any) {
  const [dateStr, setDateStr] = useState('');
  const { mode } = useThemeStore();
  useEffect(() => {
    if (visible) setDateStr(current ? toYMD(new Date(current)) : '');
  }, [visible, current]);
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <TouchableOpacity style={s.labelOverlay} activeOpacity={1} onPress={onClose}>
        <TouchableOpacity activeOpacity={1} style={s.labelModal} onPress={() => {}}>
          <Text maxFontSizeMultiplier={1.0} style={s.labelTitle}>{current ? 'Edit Birthday' : 'Add Birthday'}</Text>
          <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 13, color: '#8E8E93', marginTop: 2, marginBottom: 8 }}>
            Powers the Birthdays smart list + automatic birthday texts
          </Text>
          {Platform.OS === 'web' ? (
            <input
              type="date"
              value={dateStr}
              onChange={(e: any) => setDateStr(e.target.value)}
              style={{ width: '100%', padding: 12, borderRadius: 10, backgroundColor: colors.surface, color: colors.text, border: '1px solid #3A3A3C', fontSize: 17, marginBottom: 12, marginTop: 4 }}
              {...tid('birthday-date-input')}
            />
          ) : (
            <DateTimePicker
              value={dateStr ? new Date(dateStr + 'T12:00:00') : new Date(1990, 0, 1)}
              mode="date"
              display={Platform.OS === 'ios' ? 'spinner' : 'default'}
              onChange={(_: any, d?: Date) => { if (d) setDateStr(toYMD(d)); }}
              textColor={colors.text}
              themeVariant={mode}
              style={{ height: 150, marginVertical: 8 }}
            />
          )}
          <View style={{ flexDirection: 'row', gap: 12, marginTop: 4 }}>
            {current ? (
              <TouchableOpacity style={[s.labelBtn, { backgroundColor: colors.surface }]} onPress={() => onSave(null)} disabled={saving} testID="birthday-clear-btn" dataSet={{ testid: 'birthday-clear-btn' }}>
                <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 16, fontWeight: '600', color: '#FF3B30' }}>Clear</Text>
              </TouchableOpacity>
            ) : null}
            <TouchableOpacity style={[s.labelBtn, { backgroundColor: dateStr ? '#FF9500' : 'rgba(128,128,128,0.3)' }]} onPress={() => dateStr && onSave(dateStr)} disabled={saving || !dateStr} testID="birthday-save-btn" dataSet={{ testid: 'birthday-save-btn' }}>
              <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 16, fontWeight: '700', color: '#000' }}>{saving ? 'Saving...' : 'Save'}</Text>
            </TouchableOpacity>
          </View>
        </TouchableOpacity>
      </TouchableOpacity>
    </Modal>
  );
}

function ContactRow({ s, icon, color, label, value, onPress, testid }: any) {
  if (!value) return null;
  const inner = (
    <>
      <Ionicons name={icon} size={16} color={color} />
      <Text style={s.viewRowLabel}>{label}</Text>
      <Text style={[s.viewRowValue, { flexShrink: 1, textAlign: 'right' }]} numberOfLines={2}>{value}</Text>
    </>
  );
  return onPress
    ? <TouchableOpacity style={s.viewRow} onPress={onPress} testID={testid} dataSet={{ testid } as any}>{inner}</TouchableOpacity>
    : <View style={s.viewRow} testID={testid} dataSet={{ testid } as any}>{inner}</View>;
}

export default function DetailsTab(props: any) {
  const {
    s, colors, contact, contactId, userId, isNewContact,
    referrals, contactEnrollments, toggleDateOptin, reloadContact, checklist, onDatePress,
    availableTags = [], onAddTag, onCall, onEmail,
  } = props;
  const router = useRouter();
  const [bdayModalOpen, setBdayModalOpen] = useState(false);
  const [savingBday, setSavingBday] = useState(false);
  const [showMore, setShowMore] = useState(false);
  const [showAutomations, setShowAutomations] = useState(false);
  const paused = (k: string) => (contact.disabled_automations || []).includes(k);

  const dateRow = (key: string, icon: any, color: string, label: string, value: Date, kind?: string) => {
    const isPaused = kind ? paused(kind) : false;
    const inner = (
      <>
        <Ionicons name={icon} size={16} color={isPaused ? '#8E8E93' : color} />
        <Text style={s.viewRowLabel}>{label}{isPaused ? '  ·  paused' : ''}</Text>
        <Text style={[s.viewRowValue, isPaused && { color: '#8E8E93' }]}>{format(value, 'MMM d, yyyy')}</Text>
        {kind ? <Ionicons name="chevron-forward" size={14} color="#8E8E93" style={{ marginLeft: 6 }} /> : null}
      </>
    );
    return kind ? (
      <TouchableOpacity key={key} style={s.viewRow} onPress={() => onDatePress?.(kind, label, color, value)} testID={`date-row-${key}`} dataSet={{ testid: `date-row-${key}` } as any}>{inner}</TouchableOpacity>
    ) : <View key={key} style={s.viewRow}>{inner}</View>;
  };

  const saveBirthday = async (dateStr: string | null) => {
    setSavingBday(true);
    try {
      await contactsAPI.updateBirthday(userId, contactId, dateStr);
      setBdayModalOpen(false);
      reloadContact?.();
    } catch {}
    setSavingBday(false);
  };

  const tl = (contact.tags || []).map((t: string) => (t || '').toLowerCase());
  const bOn = tl.includes('birthday');
  const aOn = tl.includes('anniversary');
  const address = [contact.address_street, [contact.address_city, contact.address_state].filter(Boolean).join(', '), contact.address_zip].filter(Boolean).join(' · ');
  const extraPhones = (contact.phones || []).filter((p: any) => p?.value && p.value !== contact.phone);
  const extraEmails = (contact.emails || []).filter((e: any) => e?.value && e.value !== contact.email);
  const work = [contact.occupation, contact.employer || contact.organization_name].filter(Boolean).join(' at ');
  const openMaps = () => Linking.openURL(`https://maps.apple.com/?q=${encodeURIComponent(address.replace(/ · /g, ' '))}`).catch(() => {});

  return (
    <>
      <View style={{ height: 10 }} />

      {/* How to reach them */}
      <View style={s.section} {...tid('profile-contact-section')}>
        <Text style={s.sectionHeader}>Contact</Text>
        <ContactRow s={s} icon="call" color="#32ADE6" label="Mobile" value={prettyPhone(contact.phone)} onPress={onCall} testid="profile-row-phone" />
        {extraPhones.map((p: any, i: number) => <ContactRow key={`p${i}`} s={s} icon="call-outline" color="#32ADE6" label={p.label || 'Phone'} value={prettyPhone(p.value)} testid={`profile-row-phone-${i}`} />)}
        <ContactRow s={s} icon="mail" color="#AF52DE" label="Email" value={contact.email} onPress={onEmail} testid="profile-row-email" />
        {extraEmails.map((e: any, i: number) => <ContactRow key={`e${i}`} s={s} icon="mail-outline" color="#AF52DE" label={e.label || 'Email'} value={e.value} testid={`profile-row-email-${i}`} />)}
        <ContactRow s={s} icon="location" color="#FF9500" label="Address" value={address} onPress={address ? openMaps : undefined} testid="profile-row-address" />
        <ContactRow s={s} icon="briefcase" color="#C9A962" label="Work" value={work} testid="profile-row-work" />
        <ContactRow s={s} icon="car-sport" color="#C9A962" label="Vehicle" value={contact.vehicle} testid="profile-row-vehicle" />
        <ContactRow s={s} icon="people" color="#34C759" label="Referred by" value={contact.referred_by_name} onPress={contact.referred_by ? () => router.push(`/contact/${contact.referred_by}`) : undefined} testid="profile-row-referred-by" />
        {!contact.phone && !contact.email && !address && !work && !contact.vehicle && (
          <Text style={{ fontSize: 13, color: colors.textTertiary }} {...tid('profile-contact-empty')}>No phone or email yet. Tap Edit to add them.</Text>
        )}
      </View>

      {/* Important Dates */}
      <View style={s.section} {...tid('profile-dates-section')}>
        <Text style={s.sectionHeader}>Important Dates</Text>
        {contact.birthday ? (
          <TouchableOpacity style={s.viewRow} onPress={() => setBdayModalOpen(true)} testID="birthday-row" dataSet={{ testid: 'birthday-row' }}>
            <Ionicons name="gift" size={16} color="#FF9500" />
            <Text style={s.viewRowLabel}>Birthday</Text>
            <Text style={s.viewRowValue}>{format(contact.birthday, 'MMM d, yyyy')}</Text>
            <Ionicons name="pencil" size={12} color="#8E8E93" style={{ marginLeft: 6 }} />
          </TouchableOpacity>
        ) : (
          <TouchableOpacity style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 8 }} onPress={() => setBdayModalOpen(true)} testID="add-birthday-btn" dataSet={{ testid: 'add-birthday-btn' }}>
            <View style={{ width: 26, height: 26, borderRadius: 13, backgroundColor: '#FF950022', alignItems: 'center', justifyContent: 'center' }}>
              <Ionicons name="gift" size={14} color="#FF9500" />
            </View>
            <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 15, fontWeight: '600', color: '#FF9500' }}>Add birthday</Text>
            <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 12, color: '#8E8E93', flex: 1 }} numberOfLines={1}>unlocks auto birthday texts</Text>
            <Ionicons name="chevron-forward" size={14} color="#8E8E93" />
          </TouchableOpacity>
        )}
        {contact.anniversary && dateRow('anniversary', 'heart', '#FF2D55', 'Anniversary', contact.anniversary, 'anniversary')}
        {contact.date_sold && dateRow('sold', 'car', '#34C759', 'Date sold', contact.date_sold, 'sold_date')}
        {(contact.custom_dates || []).map((cd: any, i: number) => cd.date && (
          <View key={i} style={s.viewRow}>
            <Ionicons name="calendar-outline" size={16} color="#007AFF" />
            <Text style={s.viewRowLabel}>{cd.name}</Text>
            <Text style={s.viewRowValue}>{format(cd.date, 'MMM d, yyyy')}</Text>
          </View>
        ))}

        {/* Automations: one summary row, toggles behind it. Date sends fire ONLY when these are ON. */}
        {(contact.birthday || contact.date_sold || contact.anniversary) && (
          <>
            <TouchableOpacity onPress={() => setShowAutomations(v => !v)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10 }} testID="automations-toggle" dataSet={{ testid: 'automations-toggle' } as any}>
              <Ionicons name="notifications-outline" size={16} color={colors.textSecondary} />
              <Text style={[s.viewRowLabel, { flex: 1 }]} numberOfLines={1}>
                Auto texts{contact.birthday ? ` · Birthday ${bOn ? 'ON' : 'off'}` : ''}{(contact.date_sold || contact.anniversary) ? ` · Anniversary ${aOn ? 'ON' : 'off'}` : ''}
              </Text>
              <Ionicons name={showAutomations ? 'chevron-up' : 'chevron-down'} size={14} color="#8E8E93" />
            </TouchableOpacity>
            {showAutomations && (
              <View style={{ paddingLeft: 26 }}>
                {contact.birthday && (
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 6 }} {...tid('birthday-optin-row')}>
                    <View style={{ flex: 1 }}>
                      <Text style={s.viewRowLabel} numberOfLines={1}>Birthday text + card</Text>
                      <Text style={{ fontSize: 11, color: '#8E8E93' }} numberOfLines={1}>{bOn ? 'Sends automatically on their birthday' : 'OFF, nothing sends'}</Text>
                    </View>
                    <Switch value={bOn} onValueChange={(v: boolean) => toggleDateOptin('birthday', v)} trackColor={{ false: 'rgba(128,128,128,0.3)', true: '#34C75966' }} thumbColor={bOn ? '#34C759' : '#f4f3f4'} {...tid('birthday-optin-switch')} />
                  </View>
                )}
                {(contact.date_sold || contact.anniversary) && (
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 6 }} {...tid('anniversary-optin-row')}>
                    <View style={{ flex: 1 }}>
                      <Text style={s.viewRowLabel} numberOfLines={1}>Anniversary text + card</Text>
                      <Text style={{ fontSize: 11, color: '#8E8E93' }} numberOfLines={1}>{aOn ? 'Sends yearly with their car photo' : 'OFF, nothing sends'}</Text>
                    </View>
                    <Switch value={aOn} onValueChange={(v: boolean) => toggleDateOptin('anniversary', v)} trackColor={{ false: 'rgba(128,128,128,0.3)', true: '#34C75966' }} thumbColor={aOn ? '#34C759' : '#f4f3f4'} {...tid('anniversary-optin-switch')} />
                  </View>
                )}
              </View>
            )}
          </>
        )}
      </View>

      {/* Purchases */}
      {!isNewContact && (
        <PurchaseHistorySection contactId={contactId} userId={userId} colors={colors} onChanged={() => reloadContact?.()} focusPurchaseId={props.focusPurchaseId} />
      )}

      {/* Tags: all of them (the hero shows the first three) */}
      {!isNewContact && (
        <View style={s.section} {...tid('profile-tags-section')}>
          <View style={s.sectionHeaderRow}>
            <Text style={[s.sectionHeader, { marginBottom: 0 }]}>Tags</Text>
            <Text style={s.sectionHeaderCount}>{(contact.tags || []).length}</Text>
          </View>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
            {(contact.tags || []).map((tag: string, i: number) => {
              const info = availableTags.find((t: any) => t.name === tag);
              const chipColor = info?.color || colors.textSecondary;
              return (
                <View key={`tag-${i}`} style={[s.heroTagChip, { borderColor: `${chipColor}40`, backgroundColor: `${chipColor}10` }]} {...tid(`profile-tag-${i}`)}>
                  <Ionicons name={(info?.icon || 'pricetag') as any} size={12} color={chipColor} />
                  <Text style={[s.heroTagChipText, { color: chipColor }]} numberOfLines={1}>{ROLE_TAGS[tag] || tag}</Text>
                </View>
              );
            })}
            <TouchableOpacity onPress={onAddTag} style={[s.heroTagChip, { borderColor: colors.border, backgroundColor: 'transparent', gap: 4 }]} {...tid('profile-add-tag-btn')}>
              <Ionicons name="add" size={13} color={colors.textSecondary} />
              <Text style={[s.heroTagChipText, { color: colors.textSecondary }]}>{(contact.tags || []).length ? 'Tag' : 'Add a tag'}</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}

      {contact.notes ? (
        <View style={s.section} {...tid('profile-notes-section')}>
          <Text style={s.sectionHeader}>Notes</Text>
          <Text style={s.viewText}>{contact.notes}</Text>
        </View>
      ) : null}

      {/* Referrals */}
      {(contact.referral_count > 0 || referrals.length > 0) && (
        <View style={s.section}>
          <Text style={s.sectionHeader}>Referrals</Text>
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
            <View key={i} style={s.viewRow} {...tid(`campaign-row-${i}`)}>
              <Ionicons name={e.status === 'completed' ? 'checkmark-circle' : 'play-circle'} size={16} color={e.status === 'completed' ? '#34C759' : '#007AFF'} />
              <Text style={[s.viewRowLabel, { color: colors.text }]} numberOfLines={1}>{e.campaign_name}</Text>
              <Text style={[s.viewRowValue, { color: colors.textSecondary, fontWeight: '500' }]}>{e.status === 'completed' ? 'Done' : `Step ${e.current_step} of ${e.total_steps}`}</Text>
            </View>
          ))}
        </View>
      )}

      {/* More: follow-up checklist, share this profile, push to a CRM */}
      {!isNewContact && (
        <View style={s.section}>
          <TouchableOpacity onPress={() => setShowMore(v => !v)} style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 6 }} testID="details-more-toggle" dataSet={{ testid: 'details-more-toggle' } as any}>
            <Text style={[s.sectionHeader, { marginBottom: 0, flex: 1 }]}>More</Text>
            <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>Checklist · Share profile · Push to CRM</Text>
            <Ionicons name={showMore ? 'chevron-up' : 'chevron-down'} size={16} color={colors.textSecondary} />
          </TouchableOpacity>
          {showMore && (
            <View style={{ marginHorizontal: -16, marginTop: 12 }} {...tid('details-more-body')}>
              {checklist}
              <ShareProfileSection userId={userId} contactId={contactId} contactName={`${contact?.first_name || ''} ${contact?.last_name || ''}`.trim()} colors={colors} s={s} />
              <CrmPushSection userId={userId} contactId={contactId} contactName={`${contact?.first_name || ''} ${contact?.last_name || ''}`.trim()} colors={colors} s={s} />
            </View>
          )}
        </View>
      )}

      <BirthdayModal visible={bdayModalOpen} onClose={() => setBdayModalOpen(false)} onSave={saveBirthday} current={contact.birthday} s={s} colors={colors} saving={savingBday} />
    </>
  );
}
