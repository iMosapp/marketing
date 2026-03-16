import React, { useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  Platform,
  Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as Contacts from 'expo-contacts';
import * as DocumentPicker from 'expo-document-picker';
import { useAuthStore } from '../../store/authStore';
import { contactsAPI } from '../../services/api';
import { showAlert, showSimpleAlert } from '../../services/alert';
import { useThemeStore } from '../../store/themeStore';
import axios from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

interface PhoneContact {
  id: string;
  name: string;
  firstName?: string;
  lastName?: string;
  phone?: string;
  email?: string;
  selected: boolean;
}

interface CsvContact {
  first_name: string;
  last_name: string;
  organization_name?: string;
  phone: string;
  email?: string;
  phones: { label: string; value: string }[];
  emails: { label: string; value: string }[];
  birthday?: string;
  address_city?: string;
  address_state?: string;
  notes?: string;
  is_duplicate: boolean;
  selected: boolean;
}

export default function ImportContactsScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const user = useAuthStore((state) => state.user);

  const [importMode, setImportMode] = useState<'select' | 'phone' | 'csv'>('select');
  const [phoneContacts, setPhoneContacts] = useState<PhoneContact[]>([]);
  const [csvContacts, setCsvContacts] = useState<CsvContact[]>([]);
  const [csvStats, setCsvStats] = useState({ total_parsed: 0, new_contacts: 0, duplicates: 0, skipped_no_info: 0 });
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [selectAll, setSelectAll] = useState(false);

  // Phone contacts flow (unchanged)
  const requestContactsPermission = async () => {
    const { status } = await Contacts.requestPermissionsAsync();
    if (status !== 'granted') {
      showSimpleAlert('Permission Required', 'Please grant contacts permission to import from your phone.');
      return false;
    }
    return true;
  };

  const loadPhoneContacts = async () => {
    const hasPermission = await requestContactsPermission();
    if (!hasPermission) return;
    setLoading(true);
    try {
      const { data } = await Contacts.getContactsAsync({
        fields: [Contacts.Fields.FirstName, Contacts.Fields.LastName, Contacts.Fields.PhoneNumbers, Contacts.Fields.Emails],
      });
      const validContacts: PhoneContact[] = data
        .filter(c => c.phoneNumbers && c.phoneNumbers.length > 0)
        .map(c => ({
          id: c.id || String(Math.random()),
          name: c.name || `${c.firstName || ''} ${c.lastName || ''}`.trim() || 'Unknown',
          firstName: c.firstName || '',
          lastName: c.lastName || '',
          phone: c.phoneNumbers?.[0]?.number || '',
          email: c.emails?.[0]?.email || '',
          selected: false,
        }))
        .sort((a, b) => a.name.localeCompare(b.name));
      setPhoneContacts(validContacts);
      setImportMode('phone');
    } catch (error) {
      console.error('Failed to load contacts:', error);
      showSimpleAlert('Error', 'Failed to load contacts from phone');
    } finally {
      setLoading(false);
    }
  };

  // CSV flow — uses backend parser for Google Contacts format
  const pickCSVFile = async () => {
    if (!user?._id) return;
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: ['text/csv', 'text/comma-separated-values', 'application/csv', 'text/vcard', 'text/x-vcard', '*/*'],
        copyToCacheDirectory: true,
      });
      if (result.canceled) return;
      const file = result.assets[0];
      if (!file.uri) return;

      const fileName = (file.name || '').toLowerCase();
      const isVcf = fileName.endsWith('.vcf') || fileName.endsWith('.vcard');
      const isCsv = fileName.endsWith('.csv');
      if (!isVcf && !isCsv) {
        showSimpleAlert('Unsupported File', 'Please pick a .csv or .vcf file');
        return;
      }

      setLoading(true);

      // Upload to backend for parsing (auto-detect endpoint)
      const formData = new FormData();
      if (Platform.OS === 'web') {
        const response = await fetch(file.uri);
        const blob = await response.blob();
        formData.append('file', blob, file.name || (isVcf ? 'contacts.vcf' : 'contacts.csv'));
      } else {
        formData.append('file', { uri: file.uri, name: file.name || (isVcf ? 'contacts.vcf' : 'contacts.csv'), type: isVcf ? 'text/vcard' : 'text/csv' } as any);
      }

      const endpoint = isVcf
        ? `${API_URL}/api/contacts/${user._id}/import-vcf/preview`
        : `${API_URL}/api/contacts/${user._id}/import-csv/preview`;

      const res = await axios.post(
        endpoint,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );

      const data = res.data;
      setCsvStats({
        total_parsed: data.total_parsed,
        new_contacts: data.new_contacts,
        duplicates: data.duplicates,
        skipped_no_info: data.skipped_no_info,
      });

      // Pre-select new contacts, deselect duplicates
      const contacts: CsvContact[] = data.contacts.map((c: any, idx: number) => ({
        ...c,
        selected: !c.is_duplicate,
      }));
      setCsvContacts(contacts);
      setImportMode('csv');
    } catch (error: any) {
      console.error('Failed to parse CSV:', error);
      showSimpleAlert('Error', error?.response?.data?.detail || 'Failed to parse CSV file');
    } finally {
      setLoading(false);
    }
  };

  // Phone import handler
  const handlePhoneImport = async () => {
    if (!user) return;
    const selected = phoneContacts.filter(c => c.selected);
    if (selected.length === 0) { showSimpleAlert('No Selection', 'Please select contacts to import'); return; }
    setImporting(true);
    try {
      const payload = selected.map(c => ({
        first_name: c.firstName || c.name.split(' ')[0] || 'Unknown',
        last_name: c.lastName || c.name.split(' ').slice(1).join(' ') || '',
        phone: c.phone || '',
        email: c.email || '',
        tags: [],
        notes: '',
      }));
      const result = await contactsAPI.importContacts(user._id, payload);
      let msg = `Imported ${result.imported} contact${result.imported !== 1 ? 's' : ''}`;
      if (result.skipped > 0) msg += `\n${result.skipped} duplicate${result.skipped !== 1 ? 's' : ''} skipped`;
      showAlert('Import Complete', msg, [{ text: 'OK', onPress: () => router.back() }]);
    } catch (error) {
      showSimpleAlert('Error', 'Failed to import contacts');
    } finally {
      setImporting(false);
    }
  };

  // CSV import handler — uses backend confirm endpoint
  const handleCsvImport = async () => {
    if (!user) return;
    const selected = csvContacts.filter(c => c.selected);
    if (selected.length === 0) { showSimpleAlert('No Selection', 'Please select contacts to import'); return; }
    setImporting(true);
    try {
      const res = await axios.post(
        `${API_URL}/api/contacts/${user._id}/import-csv/confirm`,
        selected
      );
      const data = res.data;
      let msg = `Imported ${data.imported} contact${data.imported !== 1 ? 's' : ''}`;
      if (data.skipped > 0) msg += `\n${data.skipped} duplicate${data.skipped !== 1 ? 's' : ''} skipped`;
      showAlert('Import Complete', msg, [{ text: 'OK', onPress: () => router.back() }]);
    } catch (error) {
      showSimpleAlert('Error', 'Failed to import contacts');
    } finally {
      setImporting(false);
    }
  };

  // Toggle handlers
  const toggleCsvContact = (idx: number) => {
    setCsvContacts(prev => prev.map((c, i) => i === idx ? { ...c, selected: !c.selected } : c));
  };
  const togglePhoneContact = (id: string) => {
    setPhoneContacts(prev => prev.map(c => c.id === id ? { ...c, selected: !c.selected } : c));
  };
  const toggleSelectAllCsv = () => {
    const newVal = !selectAll;
    setSelectAll(newVal);
    setCsvContacts(prev => prev.map(c => ({ ...c, selected: newVal })));
  };
  const toggleSelectAllPhone = () => {
    const newVal = !selectAll;
    setSelectAll(newVal);
    setPhoneContacts(prev => prev.map(c => ({ ...c, selected: newVal })));
  };

  const selectedCsvCount = csvContacts.filter(c => c.selected).length;
  const selectedPhoneCount = phoneContacts.filter(c => c.selected).length;

  // ---- RENDER: Source selection ----
  if (importMode === 'select') {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
            <Ionicons name="chevron-back" size={28} color="#007AFF" />
          </TouchableOpacity>
          <Text style={styles.title}>Import Contacts</Text>
          <View style={{ width: 40 }} />
        </View>
        <View style={styles.optionsContainer}>
          <Text style={styles.optionsTitle}>Choose import source</Text>
          <TouchableOpacity style={styles.optionCard} onPress={loadPhoneContacts} data-testid="import-from-phone">
            <View style={[styles.optionIcon, { backgroundColor: '#007AFF20' }]}>
              <Ionicons name="people" size={32} color="#007AFF" />
            </View>
            <View style={styles.optionContent}>
              <Text style={styles.optionTitle}>From Phone</Text>
              <Text style={styles.optionDesc}>Import from your device's address book{'\n'}(Requires App Store version)</Text>
            </View>
            <Ionicons name="chevron-forward" size={24} color={colors.textSecondary} />
          </TouchableOpacity>
          <TouchableOpacity style={styles.optionCard} onPress={pickCSVFile} data-testid="import-from-csv">
            <View style={[styles.optionIcon, { backgroundColor: '#34C75920' }]}>
              <Ionicons name="document-text" size={32} color="#34C759" />
            </View>
            <View style={styles.optionContent}>
              <Text style={styles.optionTitle}>From File (CSV or VCF)</Text>
              <Text style={styles.optionDesc}>Google Contacts CSV, Apple Contacts VCF, or any standard export</Text>
            </View>
            <Ionicons name="chevron-forward" size={24} color={colors.textSecondary} />
          </TouchableOpacity>
          <View style={styles.csvHint}>
            <Ionicons name="information-circle" size={20} color={colors.textSecondary} />
            <Text style={styles.csvHintText}>
              Export your contacts from Google Contacts (.csv) or Apple Contacts (.vcf). We'll automatically detect names, phone numbers, emails, birthdays, and addresses. Personal imports stay with you, not the organization.
            </Text>
          </View>
          <TouchableOpacity
            style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, marginTop: 12, padding: 14, backgroundColor: colors.card, borderRadius: 12 }}
            onPress={() => {
              if (Platform.OS === 'web') { window.open('/import-guide/', '_blank'); }
              else { Linking.openURL(`${API_URL}/import-guide/`); }
            }}
            data-testid="how-to-export-guide"
          >
            <Ionicons name="help-circle-outline" size={20} color="#007AFF" />
            <Text style={{ fontSize: 15, color: '#007AFF', fontWeight: '600' }}>How to Export Your Contacts (Step-by-Step Guide)</Text>
          </TouchableOpacity>
        </View>
        {loading && (
          <View style={styles.loadingOverlay}>
            <ActivityIndicator size="large" color="#007AFF" />
            <Text style={styles.loadingText}>Parsing contacts...</Text>
          </View>
        )}
      </SafeAreaView>
    );
  }

  // ---- RENDER: Phone contacts list ----
  if (importMode === 'phone') {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => setImportMode('select')} style={styles.backButton}>
            <Ionicons name="chevron-back" size={28} color="#007AFF" />
          </TouchableOpacity>
          <Text style={styles.title}>Phone Contacts</Text>
          <TouchableOpacity onPress={handlePhoneImport} style={styles.importButton} disabled={importing || selectedPhoneCount === 0}>
            {importing ? <ActivityIndicator size="small" color="#007AFF" /> : (
              <Text style={[styles.importButtonText, selectedPhoneCount === 0 && styles.importButtonDisabled]}>Import</Text>
            )}
          </TouchableOpacity>
        </View>
        <View style={styles.selectionBar}>
          <TouchableOpacity style={styles.selectAllButton} onPress={toggleSelectAllPhone}>
            <View style={[styles.checkbox, selectAll && styles.checkboxSelected]}>
              {selectAll && <Ionicons name="checkmark" size={16} color="#fff" />}
            </View>
            <Text style={styles.selectAllText}>Select All</Text>
          </TouchableOpacity>
          <Text style={styles.selectedCount}>{selectedPhoneCount} of {phoneContacts.length} selected</Text>
        </View>
        <FlatList
          data={phoneContacts}
          keyExtractor={item => item.id}
          contentContainerStyle={styles.listContent}
          renderItem={({ item }) => (
            <TouchableOpacity
              style={[styles.contactItem, item.selected && styles.contactItemSelected]}
              onPress={() => togglePhoneContact(item.id)}
            >
              <View style={[styles.checkbox, item.selected && styles.checkboxSelected]}>
                {item.selected && <Ionicons name="checkmark" size={16} color="#fff" />}
              </View>
              <View style={styles.contactInfo}>
                <Text style={styles.contactName}>{item.name}</Text>
                <Text style={styles.contactPhone}>{item.phone}</Text>
                {item.email ? <Text style={styles.contactEmail}>{item.email}</Text> : null}
              </View>
            </TouchableOpacity>
          )}
        />
        {selectedPhoneCount > 0 && (
          <View style={styles.bottomBar}>
            <TouchableOpacity style={styles.importActionButton} onPress={handlePhoneImport} disabled={importing}>
              {importing ? <ActivityIndicator size="small" color="#fff" /> : (
                <>
                  <Ionicons name="download" size={20} color="#fff" />
                  <Text style={styles.importActionText}>Import {selectedPhoneCount} Contact{selectedPhoneCount !== 1 ? 's' : ''}</Text>
                </>
              )}
            </TouchableOpacity>
          </View>
        )}
      </SafeAreaView>
    );
  }

  // ---- RENDER: CSV contacts preview ----
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => { setImportMode('select'); setCsvContacts([]); }} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.title}>CSV Preview</Text>
        <TouchableOpacity onPress={handleCsvImport} style={styles.importButton} disabled={importing || selectedCsvCount === 0}>
          {importing ? <ActivityIndicator size="small" color="#007AFF" /> : (
            <Text style={[styles.importButtonText, selectedCsvCount === 0 && styles.importButtonDisabled]}>Import</Text>
          )}
        </TouchableOpacity>
      </View>

      {/* Stats bar */}
      <View style={styles.statsBar}>
        <View style={styles.statItem}>
          <Text style={styles.statNum}>{csvStats.total_parsed}</Text>
          <Text style={styles.statLabel}>Found</Text>
        </View>
        <View style={styles.statItem}>
          <Text style={[styles.statNum, { color: '#34C759' }]}>{csvStats.new_contacts}</Text>
          <Text style={styles.statLabel}>New</Text>
        </View>
        <View style={styles.statItem}>
          <Text style={[styles.statNum, { color: '#FF9500' }]}>{csvStats.duplicates}</Text>
          <Text style={styles.statLabel}>Duplicates</Text>
        </View>
        <View style={styles.statItem}>
          <Text style={[styles.statNum, { color: colors.textSecondary }]}>{csvStats.skipped_no_info}</Text>
          <Text style={styles.statLabel}>Skipped</Text>
        </View>
      </View>

      {/* Selection bar */}
      <View style={styles.selectionBar}>
        <TouchableOpacity style={styles.selectAllButton} onPress={toggleSelectAllCsv}>
          <View style={[styles.checkbox, selectAll && styles.checkboxSelected]}>
            {selectAll && <Ionicons name="checkmark" size={16} color="#fff" />}
          </View>
          <Text style={styles.selectAllText}>Select All</Text>
        </TouchableOpacity>
        <Text style={styles.selectedCount}>{selectedCsvCount} of {csvContacts.length} selected</Text>
      </View>

      <FlatList
        data={csvContacts}
        keyExtractor={(_, idx) => String(idx)}
        contentContainerStyle={styles.listContent}
        renderItem={({ item, index }) => {
          const name = `${item.first_name} ${item.last_name}`.trim() || item.organization_name || 'Unknown';
          const phoneCount = item.phones?.length || 0;
          const emailCount = item.emails?.length || 0;
          return (
            <TouchableOpacity
              style={[styles.contactItem, item.selected && styles.contactItemSelected, item.is_duplicate && styles.contactItemDuplicate]}
              onPress={() => toggleCsvContact(index)}
            >
              <View style={[styles.checkbox, item.selected && styles.checkboxSelected]}>
                {item.selected && <Ionicons name="checkmark" size={16} color="#fff" />}
              </View>
              <View style={styles.contactInfo}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                  <Text style={styles.contactName}>{name}</Text>
                  {item.is_duplicate && (
                    <View style={styles.dupBadge}><Text style={styles.dupBadgeText}>DUP</Text></View>
                  )}
                </View>
                {item.organization_name && item.first_name ? (
                  <Text style={styles.contactOrg}>{item.organization_name}</Text>
                ) : null}
                <Text style={styles.contactPhone}>
                  {item.phone || 'No phone'}{phoneCount > 1 ? ` (+${phoneCount - 1} more)` : ''}
                </Text>
                {item.email ? (
                  <Text style={styles.contactEmail}>
                    {item.email}{emailCount > 1 ? ` (+${emailCount - 1} more)` : ''}
                  </Text>
                ) : null}
                {item.birthday ? (
                  <Text style={styles.contactExtra}>Birthday: {item.birthday.split('T')[0]}</Text>
                ) : null}
                {item.address_city || item.address_state ? (
                  <Text style={styles.contactExtra}>{[item.address_city, item.address_state].filter(Boolean).join(', ')}</Text>
                ) : null}
              </View>
            </TouchableOpacity>
          );
        }}
        ListEmptyComponent={() => (
          <View style={styles.emptyContainer}>
            <Ionicons name="people-outline" size={64} color={colors.surface} />
            <Text style={styles.emptyText}>No contacts found in CSV</Text>
          </View>
        )}
      />

      {selectedCsvCount > 0 && (
        <View style={styles.bottomBar}>
          <TouchableOpacity style={styles.importActionButton} onPress={handleCsvImport} disabled={importing}>
            {importing ? <ActivityIndicator size="small" color="#fff" /> : (
              <>
                <Ionicons name="download" size={20} color="#fff" />
                <Text style={styles.importActionText}>Import {selectedCsvCount} Contact{selectedCsvCount !== 1 ? 's' : ''}</Text>
              </>
            )}
          </TouchableOpacity>
        </View>
      )}
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 16, borderBottomWidth: 1, borderBottomColor: colors.surface },
  backButton: { padding: 4 },
  title: { fontSize: 17, fontWeight: '600', color: colors.text },
  importButton: { padding: 4 },
  importButtonText: { fontSize: 17, fontWeight: '600', color: '#007AFF' },
  importButtonDisabled: { color: colors.borderLight },
  optionsContainer: { padding: 20 },
  optionsTitle: { fontSize: 15, color: colors.textSecondary, marginBottom: 20, textAlign: 'center' },
  optionCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, borderRadius: 12, padding: 16, marginBottom: 12 },
  optionIcon: { width: 56, height: 56, borderRadius: 12, alignItems: 'center', justifyContent: 'center', marginRight: 16 },
  optionContent: { flex: 1 },
  optionTitle: { fontSize: 17, fontWeight: '600', color: colors.text, marginBottom: 4 },
  optionDesc: { fontSize: 14, color: colors.textSecondary },
  csvHint: { flexDirection: 'row', alignItems: 'flex-start', marginTop: 20, padding: 16, backgroundColor: colors.card, borderRadius: 12, gap: 12 },
  csvHintText: { flex: 1, fontSize: 13, color: colors.textSecondary, lineHeight: 18 },
  loadingOverlay: { ...StyleSheet.absoluteFillObject, backgroundColor: 'rgba(0,0,0,0.8)', justifyContent: 'center', alignItems: 'center' },
  loadingText: { marginTop: 16, fontSize: 16, color: colors.text },
  statsBar: { flexDirection: 'row', paddingVertical: 12, paddingHorizontal: 16, backgroundColor: colors.card, borderBottomWidth: 1, borderBottomColor: colors.surface, justifyContent: 'space-around' },
  statItem: { alignItems: 'center' },
  statNum: { fontSize: 20, fontWeight: '700', color: colors.text },
  statLabel: { fontSize: 11, color: colors.textSecondary, marginTop: 2 },
  selectionBar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 12, paddingHorizontal: 16, backgroundColor: colors.card, borderBottomWidth: 1, borderBottomColor: colors.surface },
  selectAllButton: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  selectAllText: { fontSize: 15, color: colors.text, fontWeight: '500' },
  selectedCount: { fontSize: 14, color: colors.textSecondary },
  checkbox: { width: 24, height: 24, borderRadius: 12, borderWidth: 2, borderColor: colors.borderLight, alignItems: 'center', justifyContent: 'center' },
  checkboxSelected: { backgroundColor: '#007AFF', borderColor: '#007AFF' },
  listContent: { padding: 16 },
  contactItem: { flexDirection: 'row', alignItems: 'flex-start', backgroundColor: colors.card, borderRadius: 12, padding: 14, marginBottom: 8, gap: 12 },
  contactItemSelected: { backgroundColor: '#007AFF10', borderColor: '#007AFF', borderWidth: 1 },
  contactItemDuplicate: { opacity: 0.5 },
  contactInfo: { flex: 1 },
  contactName: { fontSize: 16, fontWeight: '600', color: colors.text },
  contactOrg: { fontSize: 13, color: colors.textSecondary, marginTop: 1 },
  contactPhone: { fontSize: 14, color: colors.textSecondary, marginTop: 3 },
  contactEmail: { fontSize: 13, color: colors.textSecondary, marginTop: 1 },
  contactExtra: { fontSize: 12, color: colors.textTertiary, marginTop: 1 },
  dupBadge: { backgroundColor: '#FF950030', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
  dupBadgeText: { fontSize: 10, fontWeight: '700', color: '#FF9500' },
  emptyContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingVertical: 64 },
  emptyText: { fontSize: 18, color: colors.textSecondary, marginTop: 16 },
  bottomBar: { padding: 16, paddingBottom: 32, borderTopWidth: 1, borderTopColor: colors.surface },
  importActionButton: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', backgroundColor: '#007AFF', borderRadius: 12, padding: 16, gap: 8 },
  importActionText: { fontSize: 17, fontWeight: '600', color: '#fff' },
});
