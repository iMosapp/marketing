/**
 * EditFormBottom — edit-mode referral, notes, convert-to-user & delete actions.
 * Extracted from contact/[id].tsx (render-only; all state lives in the parent).
 */
import React from 'react';
import { View, Text, TextInput, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { showConfirm } from '../../services/alert';
import VoiceInput from '../VoiceInput';

export default function EditFormBottom(props: any) {
  const {
    s, colors, contact, setContact, isNewContact, user, contactId,
    onPickReferrer, clearReferrer, handleDelete,
  } = props;
  const router = useRouter();

  return (
    <>
      {/* Referral */}
      <View style={s.section}>
        <Text style={s.sectionHeader}>Referral</Text>
        <TouchableOpacity style={s.dateRow} onPress={onPickReferrer}>
          <View style={[s.dateRowIcon, { backgroundColor: '#34C75920' }]}>
            <Ionicons name="people" size={18} color="#34C759" />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={s.dateRowLabel}>Referred By</Text>
            <Text style={[s.dateRowValue, !contact.referred_by_name && { color: colors.textTertiary }]}>
              {contact.referred_by_name || 'Select referrer'}
            </Text>
          </View>
          {contact.referred_by ? (
            <TouchableOpacity onPress={clearReferrer} style={{ padding: 4 }}>
              <Ionicons name="close-circle" size={20} color={colors.textSecondary} />
            </TouchableOpacity>
          ) : (
            <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
          )}
        </TouchableOpacity>
        {contact.referred_by && (
          <View style={s.inputGroup}>
            <Text style={s.inputLabel}>Referral Notes</Text>
            <TextInput style={s.input} placeholder="How did they refer?" placeholderTextColor={colors.textTertiary}
              value={contact.referral_notes} onChangeText={(t: string) => setContact({ ...contact, referral_notes: t })} />
          </View>
        )}
      </View>

      {/* Notes */}
      <View style={s.section}>
        <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
          <Text style={[s.sectionHeader, { marginBottom: 0 }]}>Notes</Text>
          <VoiceInput
            onTranscription={(text: string) => setContact({ ...contact, notes: contact.notes + ' ' + text })}
            size="small" color={colors.textSecondary}
          />
        </View>
        <TextInput style={[s.input, { minHeight: 100, textAlignVertical: 'top', marginTop: 8 }]}
          placeholder="Add notes..." placeholderTextColor={colors.textTertiary} value={contact.notes}
          onChangeText={(t: string) => setContact({ ...contact, notes: t })} multiline data-testid="input-notes" />
      </View>

      {/* Convert to User (super_admin only) */}
      {!isNewContact && user?.role === 'super_admin' && (
        <TouchableOpacity
          onPress={() => {
            const fullName = `${contact.first_name || ''} ${contact.last_name || ''}`.trim();
            showConfirm(
              'Convert to User',
              `Create a user account for ${fullName}? This will let them log into I'm On Social.`,
              () => {
                router.push({
                  pathname: '/admin/users' as any,
                  params: {
                    importName: fullName,
                    importEmail: contact.email || '',
                    importPhone: contact.phone || '',
                    importContactId: contactId,
                  },
                });
              }
            );
          }}
          style={[s.deleteBtn, { borderColor: '#007AFF40', marginBottom: 8 }]}
          data-testid="convert-to-user-btn"
        >
          <Ionicons name="person-add-outline" size={18} color="#007AFF" />
          <Text style={[s.deleteBtnText, { color: '#007AFF' }]}>Convert to User Account</Text>
        </TouchableOpacity>
      )}

      {/* Delete */}
      {!isNewContact && (
        <TouchableOpacity onPress={handleDelete} style={s.deleteBtn} data-testid="delete-contact-button">
          <Ionicons name="trash-outline" size={18} color="#FF3B30" />
          <Text style={s.deleteBtnText}>Delete Contact</Text>
        </TouchableOpacity>
      )}
    </>
  );
}
