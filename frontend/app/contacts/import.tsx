import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  Platform,
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
interface PhoneContact {
  id: string;
  name: string;
  firstName?: string;
  lastName?: string;
  phone?: string;
  email?: string;
  selected: boolean;
}

export default function ImportContactsScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  
  const [importMode, setImportMode] = useState<'select' | 'phone' | 'csv'>('select');
  const [phoneContacts, setPhoneContacts] = useState<PhoneContact[]>([]);
  const [csvContacts, setCsvContacts] = useState<PhoneContact[]>([]);
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [selectAll, setSelectAll] = useState(false);
  
  const contacts = importMode === 'phone' ? phoneContacts : csvContacts;
  const setContacts = importMode === 'phone' ? setPhoneContacts : setCsvContacts;
  
  const selectedCount = contacts.filter(c => c.selected).length;
  
  const requestContactsPermission = async () => {
    const { status } = await Contacts.requestPermissionsAsync();
    if (status !== 'granted') {
      showSimpleAlert(
        'Permission Required',
        'Please grant contacts permission to import from your phone.'
      );
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
        fields: [
          Contacts.Fields.FirstName,
          Contacts.Fields.LastName,
          Contacts.Fields.PhoneNumbers,
          Contacts.Fields.Emails,
        ],
      });
      
      // Filter contacts that have at least a phone number
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
  
  const parseCSV = (content: string): PhoneContact[] => {
    const lines = content.split('\n').filter(line => line.trim());
    if (lines.length < 2) return [];
    
    // Parse header
    const header = lines[0].toLowerCase().split(',').map(h => h.trim().replace(/"/g, ''));
    
    // Find column indices
    const firstNameIdx = header.findIndex(h => h.includes('first') || h === 'firstname');
    const lastNameIdx = header.findIndex(h => h.includes('last') || h === 'lastname');
    const nameIdx = header.findIndex(h => h === 'name' || h === 'full name' || h === 'fullname');
    const phoneIdx = header.findIndex(h => h.includes('phone') || h.includes('mobile') || h.includes('cell'));
    const emailIdx = header.findIndex(h => h.includes('email'));
    
    if (phoneIdx === -1) {
      showSimpleAlert('Invalid CSV', 'CSV must contain a phone column');
      return [];
    }
    
    // Parse data rows
    const contacts: PhoneContact[] = [];
    for (let i = 1; i < lines.length; i++) {
      const values = lines[i].split(',').map(v => v.trim().replace(/"/g, ''));
      
      const firstName = firstNameIdx !== -1 ? values[firstNameIdx] : '';
      const lastName = lastNameIdx !== -1 ? values[lastNameIdx] : '';
      const fullName = nameIdx !== -1 ? values[nameIdx] : '';
      const phone = phoneIdx !== -1 ? values[phoneIdx] : '';
      const email = emailIdx !== -1 ? values[emailIdx] : '';
      
      if (!phone) continue;
      
      const name = fullName || `${firstName} ${lastName}`.trim() || 'Unknown';
      
      contacts.push({
        id: String(i),
        name,
        firstName: firstName || fullName.split(' ')[0] || '',
        lastName: lastName || fullName.split(' ').slice(1).join(' ') || '',
        phone,
        email,
        selected: false,
      });
    }
    
    return contacts;
  };
  
  const pickCSVFile = async () => {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: ['text/csv', 'text/comma-separated-values', 'application/csv', '*/*'],
        copyToCacheDirectory: true,
      });
      
      if (result.canceled) return;
      
      const file = result.assets[0];
      if (!file.uri) return;
      
      setLoading(true);
      
      // Read file content
      const response = await fetch(file.uri);
      const content = await response.text();
      
      const parsedContacts = parseCSV(content);
      
      if (parsedContacts.length === 0) {
        showSimpleAlert('No Contacts', 'No valid contacts found in the CSV file');
        setLoading(false);
        return;
      }
      
      setCsvContacts(parsedContacts);
      setImportMode('csv');
      
      showSimpleAlert('CSV Loaded', `Found ${parsedContacts.length} contacts`);
    } catch (error) {
      console.error('Failed to parse CSV:', error);
      showSimpleAlert('Error', 'Failed to parse CSV file');
    } finally {
      setLoading(false);
    }
  };
  
  const toggleContact = (id: string) => {
    setContacts(contacts.map(c => 
      c.id === id ? { ...c, selected: !c.selected } : c
    ));
  };
  
  const toggleSelectAll = () => {
    const newValue = !selectAll;
    setSelectAll(newValue);
    setContacts(contacts.map(c => ({ ...c, selected: newValue })));
  };
  
  const handleImport = async () => {
    if (!user) {
      showSimpleAlert('Error', 'Please log in to import contacts');
      return;
    }
    
    const selectedContacts = contacts.filter(c => c.selected);
    if (selectedContacts.length === 0) {
      showSimpleAlert('No Selection', 'Please select contacts to import');
      return;
    }
    
    setImporting(true);
    
    try {
      // Use bulk import API for efficiency
      const contactsToImport = selectedContacts.map(contact => ({
        first_name: contact.firstName || contact.name.split(' ')[0] || 'Unknown',
        last_name: contact.lastName || contact.name.split(' ').slice(1).join(' ') || '',
        phone: contact.phone || '',
        email: contact.email || '',
        tags: [],
        notes: '',
      }));
      
      const result = await contactsAPI.importContacts(user._id, contactsToImport);
      
      let message = `Imported ${result.imported} contact${result.imported !== 1 ? 's' : ''}`;
      if (result.skipped > 0) {
        message += `\n${result.skipped} duplicate${result.skipped !== 1 ? 's' : ''} skipped`;
      }
      
      showAlert('Import Complete', message, [
        { text: 'OK', onPress: () => router.back() },
      ]);
    } catch (error) {
      console.error('Import failed:', error);
      showSimpleAlert('Error', 'Failed to import contacts');
    } finally {
      setImporting(false);
    }
  };
  
  const renderContact = ({ item }: { item: PhoneContact }) => (
    <TouchableOpacity
      style={[styles.contactItem, item.selected && styles.contactItemSelected]}
      onPress={() => toggleContact(item.id)}
    >
      <View style={[styles.checkbox, item.selected && styles.checkboxSelected]}>
        {item.selected && <Ionicons name="checkmark" size={16} color={colors.text} />}
      </View>
      
      <View style={styles.contactInfo}>
        <Text style={styles.contactName}>{item.name}</Text>
        <Text style={styles.contactPhone}>{item.phone}</Text>
        {item.email && <Text style={styles.contactEmail}>{item.email}</Text>}
      </View>
    </TouchableOpacity>
  );
  
  // Selection mode UI
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
          
          <TouchableOpacity style={styles.optionCard} onPress={loadPhoneContacts}>
            <View style={[styles.optionIcon, { backgroundColor: '#007AFF20' }]}>
              <Ionicons name="people" size={32} color="#007AFF" />
            </View>
            <View style={styles.optionContent}>
              <Text style={styles.optionTitle}>From Phone</Text>
              <Text style={styles.optionDesc}>Import contacts from your device's address book{'\n'}(Requires App Store version  - not available on web)</Text>
            </View>
            <Ionicons name="chevron-forward" size={24} color={colors.textSecondary} />
          </TouchableOpacity>
          
          <TouchableOpacity style={styles.optionCard} onPress={pickCSVFile}>
            <View style={[styles.optionIcon, { backgroundColor: '#34C75920' }]}>
              <Ionicons name="document-text" size={32} color="#34C759" />
            </View>
            <View style={styles.optionContent}>
              <Text style={styles.optionTitle}>From CSV File</Text>
              <Text style={styles.optionDesc}>Import from a spreadsheet or RMS export</Text>
            </View>
            <Ionicons name="chevron-forward" size={24} color={colors.textSecondary} />
          </TouchableOpacity>
          
          <View style={styles.csvHint}>
            <Ionicons name="information-circle" size={20} color={colors.textSecondary} />
            <Text style={styles.csvHintText}>
              CSV should have columns: first_name, last_name, phone, email (at minimum phone is required)
            </Text>
          </View>
        </View>
        
        {loading && (
          <View style={styles.loadingOverlay}>
            <ActivityIndicator size="large" color="#007AFF" />
            <Text style={styles.loadingText}>Loading contacts...</Text>
          </View>
        )}
      </SafeAreaView>
    );
  }
  
  // Contact list UI
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => setImportMode('select')} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.title}>
          {importMode === 'phone' ? 'Phone Contacts' : 'CSV Contacts'}
        </Text>
        <TouchableOpacity onPress={handleImport} style={styles.importButton} disabled={importing || selectedCount === 0}>
          {importing ? (
            <ActivityIndicator size="small" color="#007AFF" />
          ) : (
            <Text style={[styles.importButtonText, selectedCount === 0 && styles.importButtonDisabled]}>
              Import
            </Text>
          )}
        </TouchableOpacity>
      </View>
      
      {/* Selection Bar */}
      <View style={styles.selectionBar}>
        <TouchableOpacity style={styles.selectAllButton} onPress={toggleSelectAll}>
          <View style={[styles.checkbox, selectAll && styles.checkboxSelected]}>
            {selectAll && <Ionicons name="checkmark" size={16} color={colors.text} />}
          </View>
          <Text style={styles.selectAllText}>Select All</Text>
        </TouchableOpacity>
        
        <Text style={styles.selectedCount}>
          {selectedCount} of {contacts.length} selected
        </Text>
      </View>
      
      <FlatList
        data={contacts}
        renderItem={renderContact}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.listContent}
        ListEmptyComponent={() => (
          <View style={styles.emptyContainer}>
            <Ionicons name="people-outline" size={64} color={colors.surface} />
            <Text style={styles.emptyText}>No contacts found</Text>
          </View>
        )}
      />
      
      {/* Bottom Action Bar */}
      {selectedCount > 0 && (
        <View style={styles.bottomBar}>
          <TouchableOpacity
            style={styles.importActionButton}
            onPress={handleImport}
            disabled={importing}
          >
            {importing ? (
              <ActivityIndicator size="small" color={colors.text} />
            ) : (
              <>
                <Ionicons name="download" size={20} color={colors.text} />
                <Text style={styles.importActionText}>
                  Import {selectedCount} Contact{selectedCount !== 1 ? 's' : ''}
                </Text>
              </>
            )}
          </TouchableOpacity>
        </View>
      )}
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: colors.surface,
  },
  backButton: {
    padding: 4,
  },
  title: {
    fontSize: 17,
    fontWeight: '600',
    color: colors.text,
  },
  importButton: {
    padding: 4,
  },
  importButtonText: {
    fontSize: 17,
    fontWeight: '600',
    color: '#007AFF',
  },
  importButtonDisabled: {
    color: colors.borderLight,
  },
  optionsContainer: {
    padding: 20,
  },
  optionsTitle: {
    fontSize: 15,
    color: colors.textSecondary,
    marginBottom: 20,
    textAlign: 'center',
  },
  optionCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
  },
  optionIcon: {
    width: 56,
    height: 56,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 16,
  },
  optionContent: {
    flex: 1,
  },
  optionTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 4,
  },
  optionDesc: {
    fontSize: 14,
    color: colors.textSecondary,
  },
  csvHint: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginTop: 20,
    padding: 16,
    backgroundColor: colors.card,
    borderRadius: 12,
    gap: 12,
  },
  csvHintText: {
    flex: 1,
    fontSize: 13,
    color: colors.textSecondary,
    lineHeight: 18,
  },
  loadingOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,0.8)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 16,
    fontSize: 16,
    color: colors.text,
  },
  selectionBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 12,
    paddingHorizontal: 16,
    backgroundColor: colors.card,
    borderBottomWidth: 1,
    borderBottomColor: colors.surface,
  },
  selectAllButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  selectAllText: {
    fontSize: 15,
    color: colors.text,
    fontWeight: '500',
  },
  selectedCount: {
    fontSize: 14,
    color: colors.textSecondary,
  },
  checkbox: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 2,
    borderColor: colors.borderLight,
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkboxSelected: {
    backgroundColor: '#007AFF',
    borderColor: '#007AFF',
  },
  listContent: {
    padding: 16,
  },
  contactItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginBottom: 8,
    gap: 12,
  },
  contactItemSelected: {
    backgroundColor: '#007AFF15',
    borderColor: '#007AFF',
    borderWidth: 1,
  },
  contactInfo: {
    flex: 1,
  },
  contactName: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 4,
  },
  contactPhone: {
    fontSize: 14,
    color: colors.textSecondary,
  },
  contactEmail: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 2,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 64,
  },
  emptyText: {
    fontSize: 18,
    color: colors.textSecondary,
    marginTop: 16,
  },
  bottomBar: {
    padding: 16,
    paddingBottom: 32,
    borderTopWidth: 1,
    borderTopColor: colors.surface,
  },
  importActionButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#007AFF',
    borderRadius: 12,
    padding: 16,
    gap: 8,
  },
  importActionText: {
    fontSize: 17,
    fontWeight: '600',
    color: colors.text,
  },
});
