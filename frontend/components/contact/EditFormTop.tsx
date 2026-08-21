/**
 * EditFormTop — edit-mode basic info, employment, address, tags & dates.
 * Extracted from contact/[id].tsx (render-only; all state lives in the parent).
 */
import React from 'react';
import { View, Text, TextInput, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

export default function EditFormTop(props: any) {
  const {
    s, colors, contact, setContact, isNewContact, showMoreDetails, setShowMoreDetails,
    availableTags, removeTag, onAddTag, openDatePicker, formatDateDisplay,
    clearDate, removeCustomDateField, onAddCustomDate,
  } = props;

  return (
    <>
      {/* Quick Add - Essential Fields */}
      <View style={s.section}>
        {isNewContact && <Text style={[s.sectionHeader, { fontSize: 19, marginBottom: 12 }]}>Quick Add</Text>}
        {!isNewContact && <Text style={s.sectionHeader}>Basic Info</Text>}
        <View style={s.inputGroup}>
          <Text style={s.inputLabel}>First Name *</Text>
          <TextInput style={s.input} placeholder="First name" placeholderTextColor={colors.textTertiary}
            value={contact.first_name} onChangeText={(t: string) => setContact({ ...contact, first_name: t })} autoFocus={isNewContact} data-testid="input-first-name" />
        </View>
        <View style={s.inputGroup}>
          <Text style={s.inputLabel}>Last Name</Text>
          <TextInput style={s.input} placeholder="Last name" placeholderTextColor={colors.textTertiary}
            value={contact.last_name} onChangeText={(t: string) => setContact({ ...contact, last_name: t })} data-testid="input-last-name" />
        </View>
        <View style={s.inputGroup}>
          <Text style={s.inputLabel}>Phone</Text>
          <TextInput style={s.input} placeholder="+1 (555) 123-4567" placeholderTextColor={colors.textTertiary}
            value={contact.phone} onChangeText={(t: string) => setContact({ ...contact, phone: t })} keyboardType="phone-pad" data-testid="input-phone" />
        </View>
        <View style={s.inputGroup}>
          <Text style={s.inputLabel}>Email</Text>
          <TextInput style={s.input} placeholder="email@example.com" placeholderTextColor={colors.textTertiary}
            value={contact.email} onChangeText={(t: string) => setContact({ ...contact, email: t })} keyboardType="email-address" autoCapitalize="none" data-testid="input-email" />
        </View>
      </View>

      {/* Collapsible More Details - Vehicle, Address, Tags, Dates */}
      {isNewContact && !showMoreDetails && (
        <TouchableOpacity
          style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 14, marginHorizontal: 16, marginBottom: 8, borderRadius: 12, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border }}
          onPress={() => setShowMoreDetails(true)}
          data-testid="show-more-details-btn"
        >
          <Ionicons name="add-circle-outline" size={20} color="#007AFF" style={{ marginRight: 8 }} />
          <Text style={{ fontSize: 17, fontWeight: '600', color: '#007AFF' }}>More Details (optional)</Text>
        </TouchableOpacity>
      )}

      {(!isNewContact || showMoreDetails) && (
        <>
          {isNewContact && (
            <TouchableOpacity
              style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 10, marginHorizontal: 16, marginBottom: 4 }}
              onPress={() => setShowMoreDetails(false)}
              data-testid="hide-more-details-btn"
            >
              <Ionicons name="chevron-up" size={18} color={colors.textSecondary} style={{ marginRight: 6 }} />
              <Text style={{ fontSize: 16, color: colors.textSecondary }}>Hide Details</Text>
            </TouchableOpacity>
          )}

          <View style={s.section}>
            {!isNewContact && <View />}
            <View style={s.inputGroup}>
              <Text style={s.inputLabel}>Vehicle</Text>
              <TextInput style={s.input} placeholder="e.g., 2023 Toyota RAV4" placeholderTextColor={colors.textTertiary}
                value={contact.vehicle} onChangeText={(t: string) => setContact({ ...contact, vehicle: t })} data-testid="input-vehicle" />
            </View>
          </View>

          {/* Employment Section */}
          <View style={s.section}>
            <Text style={s.sectionHeader}>Employment</Text>
            <View style={s.inputGroup}>
              <Text style={s.inputLabel}>Organization Name</Text>
              <TextInput style={s.input} placeholder="e.g., Hertz, Goldman Sachs" placeholderTextColor={colors.textTertiary}
                value={contact.organization_name} onChangeText={(t: string) => setContact({ ...contact, organization_name: t })} data-testid="input-organization-name" />
            </View>
            <View style={s.inputGroup}>
              <Text style={s.inputLabel}>Job Title / Occupation</Text>
              <TextInput style={s.input} placeholder="e.g., Senior Manager" placeholderTextColor={colors.textTertiary}
                value={contact.occupation} onChangeText={(t: string) => setContact({ ...contact, occupation: t })} data-testid="input-occupation" />
            </View>
            <View style={s.inputGroup}>
              <Text style={s.inputLabel}>Employer / Company</Text>
              <TextInput style={s.input} placeholder="e.g., Goldman Sachs" placeholderTextColor={colors.textTertiary}
                value={contact.employer} onChangeText={(t: string) => setContact({ ...contact, employer: t })} data-testid="input-employer" />
            </View>
          </View>

          {/* Additional Phone Numbers */}
          {contact.phones.length > 0 && (
            <View style={s.section}>
              <Text style={s.sectionHeader}>Additional Phone Numbers</Text>
              {contact.phones.map((p: any, idx: number) => (
                <View key={`phone-${idx}`} style={s.inputGroup}>
                  <Text style={s.inputLabel}>{p.label || 'Phone'}</Text>
                  <TextInput style={s.input} value={p.value} keyboardType="phone-pad"
                    onChangeText={(t: string) => {
                      const updated = [...contact.phones];
                      updated[idx] = { ...updated[idx], value: t };
                      setContact({ ...contact, phones: updated });
                    }}
                    data-testid={`input-phone-${idx}`} />
                </View>
              ))}
            </View>
          )}

          {/* Additional Email Addresses */}
          {contact.emails.length > 0 && (
            <View style={s.section}>
              <Text style={s.sectionHeader}>Additional Email Addresses</Text>
              {contact.emails.map((e: any, idx: number) => (
                <View key={`email-${idx}`} style={s.inputGroup}>
                  <Text style={s.inputLabel}>{e.label || 'Email'}</Text>
                  <TextInput style={s.input} value={e.value} keyboardType="email-address" autoCapitalize="none"
                    onChangeText={(t: string) => {
                      const updated = [...contact.emails];
                      updated[idx] = { ...updated[idx], value: t };
                      setContact({ ...contact, emails: updated });
                    }}
                    data-testid={`input-email-${idx}`} />
                </View>
              ))}
            </View>
          )}

          {/* Address Section */}
          <View style={s.section}>
            <Text style={s.sectionHeader}>Address</Text>
            <View style={s.inputGroup}>
              <Text style={s.inputLabel}>Street</Text>
              <TextInput style={s.input} placeholder="123 Main St" placeholderTextColor={colors.textTertiary}
                value={contact.address_street} onChangeText={(t: string) => setContact({ ...contact, address_street: t })} data-testid="input-address-street" />
            </View>
            <View style={{ flexDirection: 'row', gap: 10 }}>
              <View style={[s.inputGroup, { flex: 1 }]}>
                <Text style={s.inputLabel}>City</Text>
                <TextInput style={s.input} placeholder="City" placeholderTextColor={colors.textTertiary}
                  value={contact.address_city} onChangeText={(t: string) => setContact({ ...contact, address_city: t })} data-testid="input-address-city" />
              </View>
              <View style={[s.inputGroup, { flex: 0.5 }]}>
                <Text style={s.inputLabel}>State</Text>
                <TextInput style={s.input} placeholder="ST" placeholderTextColor={colors.textTertiary}
                  value={contact.address_state} onChangeText={(t: string) => setContact({ ...contact, address_state: t })} autoCapitalize="characters" data-testid="input-address-state" />
              </View>
            </View>
            <View style={{ flexDirection: 'row', gap: 10 }}>
              <View style={[s.inputGroup, { flex: 1 }]}>
                <Text style={s.inputLabel}>ZIP Code</Text>
                <TextInput style={s.input} placeholder="12345" placeholderTextColor={colors.textTertiary}
                  value={contact.address_zip} onChangeText={(t: string) => setContact({ ...contact, address_zip: t })} keyboardType="number-pad" data-testid="input-address-zip" />
              </View>
              <View style={[s.inputGroup, { flex: 1 }]}>
                <Text style={s.inputLabel}>Country</Text>
                <TextInput style={s.input} placeholder="US" placeholderTextColor={colors.textTertiary}
                  value={contact.address_country} onChangeText={(t: string) => setContact({ ...contact, address_country: t })} data-testid="input-address-country" />
              </View>
            </View>
          </View>
        </>
      )}

      {/* Tags (edit mode  - at top) */}
      {(!isNewContact || showMoreDetails) && (
      <View style={s.section}>
        <Text style={s.sectionHeader}>Tags</Text>
        <View style={s.tagsWrap}>
          {contact.tags.map((tag: string, i: number) => {
            const info = availableTags.find((t: any) => t.name === tag);
            return (
              <View key={i} style={[s.tagPill, info?.color && { borderColor: info.color }]}>
                {info?.icon && <Ionicons name={info.icon as any} size={13} color={info.color || colors.textSecondary} />}
                <Text style={[s.tagPillText, info?.color && { color: info.color }]}>{tag}</Text>
                <TouchableOpacity onPress={() => removeTag(tag)} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
                  <Ionicons name="close-circle" size={15} color={colors.textSecondary} />
                </TouchableOpacity>
              </View>
            );
          })}
          <TouchableOpacity style={s.addTagChip} onPress={onAddTag} data-testid="add-tag-button-top">
            <Ionicons name="add" size={16} color="#007AFF" />
            <Text style={s.addTagChipText}>Add</Text>
          </TouchableOpacity>
        </View>
      </View>
      )}

      {/* Important Dates (edit mode  - at top) */}
      {(!isNewContact || showMoreDetails) && (
      <View style={s.section}>
        <Text style={s.sectionHeader}>Important Dates</Text>
        {[
          { field: 'birthday', label: 'Birthday', icon: 'gift', color: '#FF9500' },
          { field: 'anniversary', label: 'Anniversary', icon: 'heart', color: '#FF2D55' },
          { field: 'date_sold', label: 'Date Sold', icon: 'car', color: '#34C759' },
        ].map(d => (
          <TouchableOpacity key={d.field} style={s.dateRow} onPress={() => openDatePicker(d.field, (contact as any)[d.field], d.label)}>
            <View style={[s.dateRowIcon, { backgroundColor: `${d.color}20` }]}>
              <Ionicons name={d.icon as any} size={18} color={d.color} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={s.dateRowLabel}>{d.label}</Text>
              <Text style={[s.dateRowValue, !(contact as any)[d.field] && { color: colors.textTertiary }]}>
                {formatDateDisplay((contact as any)[d.field])}
              </Text>
            </View>
            {(contact as any)[d.field] && (
              <TouchableOpacity onPress={() => clearDate(d.field)} style={{ padding: 4, marginRight: 8 }}>
                <Ionicons name="close-circle" size={20} color={colors.textSecondary} />
              </TouchableOpacity>
            )}
            <Ionicons name="calendar" size={20} color={colors.textSecondary} />
          </TouchableOpacity>
        ))}
        {contact.custom_dates.map((cd: any, i: number) => (
          <TouchableOpacity key={i} style={s.dateRow} onPress={() => openDatePicker(`custom_${i}`, cd.date)}>
            <View style={[s.dateRowIcon, { backgroundColor: '#007AFF20' }]}>
              <Ionicons name="calendar-outline" size={18} color="#007AFF" />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={s.dateRowLabel}>{cd.name}</Text>
              <Text style={[s.dateRowValue, !cd.date && { color: colors.textTertiary }]}>{formatDateDisplay(cd.date)}</Text>
            </View>
            <TouchableOpacity onPress={() => removeCustomDateField(i)} style={{ padding: 4 }}>
              <Ionicons name="trash-outline" size={18} color="#FF3B30" />
            </TouchableOpacity>
          </TouchableOpacity>
        ))}
        <TouchableOpacity style={s.addBtn} onPress={onAddCustomDate}>
          <Ionicons name="add-circle" size={20} color="#007AFF" />
          <Text style={s.addBtnText}>Add Custom Date</Text>
        </TouchableOpacity>
      </View>
      )}
    </>
  );
}
