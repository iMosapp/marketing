import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  TextInput,
  Modal,
  ActivityIndicator,
  ScrollView,
  Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useThemeStore } from '../store/themeStore';
import { useAuthStore } from '../store/authStore';
import api from '../services/api';

interface SoldWorkflowResult {
  status: string;
  event_id: string;
  missing_fields: string[];
  deal_or_stock_mode?: string;
}

interface Props {
  visible: boolean;
  onClose: () => void;
  onComplete: () => void;
  contactId: string;
  workflowResult: SoldWorkflowResult | null;
}

const FIELD_CONFIG: Record<string, { label: string; placeholder: string; icon: string; description: string }> = {
  customer_name: {
    label: 'Customer Name',
    placeholder: 'Enter customer name',
    icon: 'person-outline',
    description: 'Customer name is required to complete this Sold record.',
  },
  phone_number: {
    label: 'Phone Number',
    placeholder: 'Enter phone number',
    icon: 'call-outline',
    description: 'Phone number is required to complete this Sold record.',
  },
  full_size_image: {
    label: 'Full-Size Image',
    placeholder: '',
    icon: 'image-outline',
    description: 'A full-size image is required for this Sold workflow. Upload a high-resolution image for print use.',
  },
  stock_number: {
    label: 'Stock Number',
    placeholder: 'Enter stock number',
    icon: 'barcode-outline',
    description: 'A stock number is required to continue.',
  },
  deal_number: {
    label: 'Deal Number',
    placeholder: 'Enter deal number',
    icon: 'document-text-outline',
    description: 'A deal number is required to continue.',
  },
  external_account_id: {
    label: 'Partner Account ID',
    placeholder: '',
    icon: 'key-outline',
    description: 'This account is missing its partner store ID. Contact an admin or update account settings.',
  },
};

export function SoldWorkflowModal({ visible, onClose, onComplete, contactId, workflowResult }: Props) {
  const { colors } = useThemeStore();
  const user = useAuthStore((state) => state.user);
  const styles = getStyles(colors);

  const [fieldValues, setFieldValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const missingFields = workflowResult?.missing_fields || [];
  const dealOrStockMode = workflowResult?.deal_or_stock_mode || 'stock_number';

  useEffect(() => {
    if (visible) {
      setFieldValues({});
      setError('');
    }
  }, [visible]);

  const handleSave = async () => {
    setSaving(true);
    setError('');

    try {
      const headers = { 'X-User-ID': user?._id };
      const updateData: Record<string, any> = {};

      for (const field of missingFields) {
        if (field === 'customer_name') {
          const name = (fieldValues.customer_name || '').trim();
          if (!name) { setError('Customer name is required.'); setSaving(false); return; }
          const parts = name.split(' ');
          updateData.first_name = parts[0];
          updateData.last_name = parts.slice(1).join(' ');
        } else if (field === 'phone_number') {
          const phone = (fieldValues.phone_number || '').trim();
          if (!phone) { setError('Phone number is required.'); setSaving(false); return; }
          updateData.phone = phone;
        } else if (field === 'stock_number') {
          const val = (fieldValues.stock_number || '').trim();
          if (!val) { setError('Stock number is required.'); setSaving(false); return; }
          updateData.stock_number = val;
        } else if (field === 'deal_number') {
          const val = (fieldValues.deal_number || '').trim();
          if (!val) { setError('Deal number is required.'); setSaving(false); return; }
          updateData.deal_number = val;
        }
        // full_size_image and external_account_id can't be fixed from this modal
      }

      // Save the contact fields first
      if (Object.keys(updateData).length > 0) {
        await api.put(`/contacts/${user?._id}/${contactId}`, updateData, { headers });
      }

      // Re-validate the sold workflow
      const res = await api.post(`/sold-workflow/revalidate/${contactId}`, {}, { headers });
      const result = res.data;

      if (result.status === 'validation_failed') {
        setError(`Still missing: ${result.missing_fields.join(', ')}`);
        setSaving(false);
        return;
      }

      // Success — workflow queued
      onComplete();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to save. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const editableFields = missingFields.filter(
    f => !['full_size_image', 'external_account_id'].includes(f)
  );
  const nonEditableFields = missingFields.filter(
    f => ['full_size_image', 'external_account_id'].includes(f)
  );

  return (
    <Modal visible={visible} animationType="slide" transparent>
      <View style={styles.overlay}>
        <View style={styles.modal}>
          <ScrollView showsVerticalScrollIndicator={false}>
            {/* Header */}
            <View style={styles.header}>
              <View style={styles.headerIcon}>
                <Ionicons name="alert-circle" size={28} color="#FF9500" />
              </View>
              <Text style={styles.title}>Complete Sold Details</Text>
              <Text style={styles.subtitle}>
                This partner requires additional details before completing the Sold workflow.
              </Text>
            </View>

            {/* Missing fields summary */}
            <View style={styles.summaryBox}>
              <Text style={styles.summaryLabel}>Missing Required Information:</Text>
              {missingFields.map((field) => {
                const config = FIELD_CONFIG[field] || { label: field, icon: 'help-circle-outline' };
                return (
                  <View key={field} style={styles.summaryItem}>
                    <Ionicons name={config.icon as any} size={16} color="#FF3B30" />
                    <Text style={styles.summaryText}>{config.label}</Text>
                  </View>
                );
              })}
            </View>

            {/* Editable fields */}
            {editableFields.map((field) => {
              const config = FIELD_CONFIG[field] || { label: field, placeholder: '', icon: 'help', description: '' };
              return (
                <View key={field} style={styles.fieldGroup}>
                  <View style={styles.fieldHeader}>
                    <Ionicons name={config.icon as any} size={18} color="#FF9500" />
                    <Text style={styles.fieldLabel}>{config.label}</Text>
                  </View>
                  <Text style={styles.fieldDesc}>{config.description}</Text>
                  <TextInput
                    style={styles.input}
                    placeholder={config.placeholder}
                    placeholderTextColor={colors.textSecondary}
                    value={fieldValues[field] || ''}
                    onChangeText={(text) => setFieldValues(prev => ({ ...prev, [field]: text }))}
                    autoCapitalize={field === 'phone_number' ? 'none' : 'words'}
                    keyboardType={field === 'phone_number' ? 'phone-pad' : 'default'}
                    data-testid={`sold-modal-input-${field}`}
                  />
                </View>
              );
            })}

            {/* Non-editable fields (info only) */}
            {nonEditableFields.map((field) => {
              const config = FIELD_CONFIG[field] || { label: field, icon: 'help', description: '' };
              return (
                <View key={field} style={styles.fieldGroup}>
                  <View style={styles.fieldHeader}>
                    <Ionicons name={config.icon as any} size={18} color="#FF3B30" />
                    <Text style={styles.fieldLabel}>{config.label}</Text>
                  </View>
                  <Text style={styles.fieldDesc}>{config.description}</Text>
                  <View style={styles.infoBox}>
                    <Ionicons name="information-circle" size={16} color="#FF9500" />
                    <Text style={styles.infoText}>
                      {field === 'full_size_image'
                        ? 'Upload a high-resolution image from the congrats card flow.'
                        : 'Contact an admin to configure the partner account ID.'}
                    </Text>
                  </View>
                </View>
              );
            })}

            {/* Error */}
            {error ? (
              <View style={styles.errorBox}>
                <Ionicons name="warning" size={16} color="#FF3B30" />
                <Text style={styles.errorText}>{error}</Text>
              </View>
            ) : null}

            {/* Actions */}
            <View style={styles.actions}>
              <TouchableOpacity
                style={styles.cancelBtn}
                onPress={onClose}
                data-testid="sold-modal-cancel"
              >
                <Text style={styles.cancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.saveBtn, saving && { opacity: 0.6 }]}
                onPress={handleSave}
                disabled={saving || editableFields.length === 0}
                data-testid="sold-modal-save"
              >
                {saving ? (
                  <ActivityIndicator size="small" color="#FFF" />
                ) : (
                  <>
                    <Ionicons name="checkmark-circle" size={18} color="#FFF" />
                    <Text style={styles.saveText}>Save and Continue</Text>
                  </>
                )}
              </TouchableOpacity>
            </View>
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  modal: {
    backgroundColor: colors.bg,
    borderRadius: 16,
    padding: 24,
    width: '100%',
    maxWidth: 480,
    maxHeight: '85%',
  },
  header: { alignItems: 'center', marginBottom: 20 },
  headerIcon: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: '#FF950015',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 12,
  },
  title: { fontSize: 21, fontWeight: '700', color: colors.text, marginBottom: 6 },
  subtitle: { fontSize: 16, color: colors.textSecondary, textAlign: 'center', lineHeight: 20 },
  summaryBox: {
    backgroundColor: '#FF3B3010',
    borderRadius: 10,
    padding: 14,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#FF3B3030',
  },
  summaryLabel: { fontSize: 15, fontWeight: '700', color: '#FF3B30', marginBottom: 8 },
  summaryItem: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 },
  summaryText: { fontSize: 15, color: colors.text },
  fieldGroup: { marginBottom: 18 },
  fieldHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 },
  fieldLabel: { fontSize: 16, fontWeight: '600', color: colors.text },
  fieldDesc: { fontSize: 14, color: colors.textSecondary, marginBottom: 8, lineHeight: 18 },
  input: {
    backgroundColor: colors.card,
    borderRadius: 10,
    padding: 12,
    fontSize: 17,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.card,
  },
  infoBox: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
    backgroundColor: '#FF950010',
    borderRadius: 8,
    padding: 10,
  },
  infoText: { fontSize: 14, color: '#FF9500', flex: 1, lineHeight: 18 },
  errorBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#FF3B3010',
    borderRadius: 8,
    padding: 10,
    marginBottom: 16,
  },
  errorText: { fontSize: 15, color: '#FF3B30', flex: 1 },
  actions: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 8,
  },
  cancelBtn: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 10,
    backgroundColor: colors.card,
    alignItems: 'center',
  },
  cancelText: { fontSize: 17, fontWeight: '600', color: colors.text },
  saveBtn: {
    flex: 2,
    paddingVertical: 14,
    borderRadius: 10,
    backgroundColor: '#34C759',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  saveText: { fontSize: 17, fontWeight: '700', color: '#FFF' },
});
