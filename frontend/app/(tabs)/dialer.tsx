import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  FlatList,
  Alert,
  Modal,
  Pressable,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { format } from 'date-fns';
import { useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { contactsAPI } from '../../services/api';
import api from '../../services/api';
import { Linking } from 'react-native';

const IS_WEB = Platform.OS === 'web';

// Web-safe icon button for header actions
const WebIconButton: React.FC<{
  onPress: () => void;
  iconName: keyof typeof Ionicons.glyphMap;
  iconSize?: number;
  iconColor: string;
  testID?: string;
}> = ({ onPress, iconName, iconSize = 24, iconColor, testID }) => {
  if (IS_WEB) {
    return (
      <button
        type="button"
        onClick={onPress}
        data-testid={testID}
        style={{
          background: 'none',
          border: 'none',
          padding: 8,
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Ionicons name={iconName} size={iconSize} color={iconColor} />
      </button>
    );
  }
  return (
    <TouchableOpacity onPress={onPress} style={{ padding: 8 }} data-testid={testID}>
      <Ionicons name={iconName} size={iconSize} color={iconColor} />
    </TouchableOpacity>
  );
};

const mockCallLogs = [
  {
    id: '1',
    contact: { name: 'John Smith', phone: '+15551234567' },
    type: 'outbound',
    duration: 245,
    timestamp: new Date(),
  },
  {
    id: '2',
    contact: { name: 'Sarah Johnson', phone: '+15559876543' },
    type: 'inbound',
    duration: 180,
    timestamp: new Date(Date.now() - 3600000),
  },
  {
    id: '3',
    contact: { name: 'Unknown', phone: '+15555551234' },
    type: 'missed',
    duration: 0,
    timestamp: new Date(Date.now() - 7200000),
  },
  {
    id: '4',
    contact: { name: 'Mike Davis', phone: '+15552223333' },
    type: 'outbound',
    duration: 120,
    timestamp: new Date(Date.now() - 86400000),
  },
  {
    id: '5',
    contact: { name: 'Lisa Chen', phone: '+15554445555' },
    type: 'inbound',
    duration: 300,
    timestamp: new Date(Date.now() - 172800000),
  },
];

export default function DialerScreen() {
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  const colors = useThemeStore((s) => s.colors);
  const inputRef = useRef<TextInput>(null);
  
  const [phoneNumber, setPhoneNumber] = useState('');
  const [showCallLog, setShowCallLog] = useState(false);
  const [showSearchModal, setShowSearchModal] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [contacts, setContacts] = useState<any[]>([]);
  const [loadingContacts, setLoadingContacts] = useState(false);
  const [callLogSearch, setCallLogSearch] = useState('');
  
  // Check if user has restricted access
  const isPending = user?.status === 'pending';
  
  useEffect(() => {
    if (user && !isPending) {
      loadContacts();
    }
  }, [user, isPending]);
  
  const loadContacts = async () => {
    if (!user) return;
    
    try {
      setLoadingContacts(true);
      const data = await contactsAPI.getAll(user._id);
      setContacts(data);
    } catch (error) {
      console.error('Failed to load contacts:', error);
    } finally {
      setLoadingContacts(false);
    }
  };
  
  // Show restricted access screen for pending users
  if (isPending) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: colors.bg }]} edges={['top']}>
        <View style={[styles.restrictedContainer, { backgroundColor: colors.bg }]}>
          <View style={styles.restrictedIcon}>
            <Ionicons name="lock-closed" size={48} color="#FF9500" />
          </View>
          <Text style={[styles.restrictedTitle, { color: colors.text }]}>Access Pending</Text>
          <Text style={[styles.restrictedText, { color: colors.textSecondary }]}>
            Your account is being reviewed by an admin. You'll have full access to calls once your account is configured.
          </Text>
          <TouchableOpacity 
            style={styles.restrictedButton}
            onPress={() => router.push('/onboarding')}
          >
            <Text style={styles.restrictedButtonText}>Complete Your Profile</Text>
            <Ionicons name="arrow-forward" size={18} color="#007AFF" />
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }
  
  const handleDialPress = (num: string) => {
    setPhoneNumber(phoneNumber + num);
  };
  
  const handleBackspace = () => {
    setPhoneNumber(phoneNumber.slice(0, -1));
  };
  
  const [matchModalVisible, setMatchModalVisible] = useState(false);
  const [matchInfo, setMatchInfo] = useState<any>(null);
  const [pendingCallPayload, setPendingCallPayload] = useState<any>(null);

  const handleCall = async (number?: string) => {
    const numberToCall = number || phoneNumber;
    if (!numberToCall) return;

    // Strong haptic for phone call action
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);

    // Log call activity FIRST with keepalive (completes even if browser navigates away)
    if (user?._id) {
      const digits = numberToCall.replace(/\D/g, '');
      const suffix = digits.length >= 10 ? digits.slice(-10) : digits;
      const match = contacts.find((c: any) => {
        const cDigits = (c.phone || '').replace(/\D/g, '');
        return cDigits.endsWith(suffix);
      });
      const contactName = match ? `${match.first_name || ''} ${match.last_name || ''}`.trim() : '';

      const apiBase = Platform.OS === 'web' ? '/api' : `${process.env.EXPO_PUBLIC_BACKEND_URL || ''}/api`;
      try {
        fetch(`${apiBase}/contacts/${user._id}/find-or-create-and-log`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            phone: numberToCall,
            name: contactName,
            event_type: 'call_placed',
            event_title: 'Call Placed',
            event_description: `Called ${contactName || numberToCall} from dialer`,
            event_icon: 'call',
            event_color: '#34C759',
          }),
          keepalive: true,
        }).catch(() => {});
      } catch {}
    }

    // Open native phone dialer (this may navigate away from the browser)
    const telUrl = `tel:${numberToCall}`;
    if (Platform.OS === 'web') {
      const a = document.createElement('a');
      a.href = telUrl;
      a.target = '_self';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } else {
      Linking.openURL(telUrl);
    }
  };

  const resolveDialerMatch = async (action: string) => {
    setMatchModalVisible(false);
    if (!pendingCallPayload || !user?._id) return;
    try {
      await api.post(`/contacts/${user._id}/find-or-create-and-log`, {
        ...pendingCallPayload,
        force_action: action,
      });
    } catch {}
    setMatchInfo(null);
    setPendingCallPayload(null);
  };
  
  const selectContact = (contact: any) => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setPhoneNumber(contact.phone);
    setShowSearchModal(false);
    setSearchQuery('');
  };
  
  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };
  
  const getCallIcon = (type: string) => {
    switch (type) {
      case 'inbound':
        return <Ionicons name="arrow-down" size={16} color="#34C759" />;
      case 'outbound':
        return <Ionicons name="arrow-up" size={16} color="#007AFF" />;
      case 'missed':
        return <Ionicons name="close" size={16} color="#FF3B30" />;
      default:
        return null;
    }
  };
  
  // Filter contacts based on search query
  const getMatchingContacts = () => {
    if (!searchQuery || searchQuery.length < 2) return contacts.slice(0, 10);
    
    const query = searchQuery.toLowerCase();
    const digitsOnly = searchQuery.replace(/\D/g, '');
    
    return contacts.filter(c => {
      const name = `${c.first_name} ${c.last_name || ''}`.toLowerCase();
      const phone = (c.phone || '').replace(/\D/g, '');
      
      return name.includes(query) || (digitsOnly.length >= 2 && phone.includes(digitsOnly));
    }).slice(0, 15);
  };
  
  const matchingContacts = getMatchingContacts();
  
  const filteredCallLogs = mockCallLogs.filter(log => {
    if (!callLogSearch) return true;
    const search = callLogSearch.toLowerCase();
    return log.contact.name.toLowerCase().includes(search) || 
           log.contact.phone.includes(search);
  });
  
  const renderCallLog = ({ item }: { item: typeof mockCallLogs[0] }) => (
    <TouchableOpacity 
      style={styles.callLogItem}
      onPress={() => {
        setPhoneNumber(item.contact.phone);
        setShowCallLog(false);
      }}
    >
      <View style={styles.callIcon}>{getCallIcon(item.type)}</View>
      
      <View style={styles.callInfo}>
        <Text style={styles.callName}>{item.contact.name}</Text>
        <Text style={styles.callPhone}>{item.contact.phone}</Text>
      </View>
      
      <View style={styles.callMeta}>
        <Text style={styles.callTime}>
          {format(item.timestamp, 'h:mm a')}
        </Text>
        {item.duration > 0 && (
          <Text style={styles.callDuration}>
            {formatDuration(item.duration)}
          </Text>
        )}
      </View>
      
      <TouchableOpacity
        style={styles.callButton}
        onPress={() => handleCall(item.contact.phone)}
      >
        <Ionicons name="call" size={20} color="#007AFF" />
      </TouchableOpacity>
    </TouchableOpacity>
  );
  
  const renderContactItem = ({ item }: { item: any }) => (
    <TouchableOpacity
      style={styles.contactItem}
      onPress={() => selectContact(item)}
    >
      <View style={styles.contactAvatar}>
        <Text style={styles.contactAvatarText}>
          {item.first_name?.[0]}{item.last_name?.[0] || ''}
        </Text>
      </View>
      <View style={styles.contactInfo}>
        <Text style={styles.contactName}>
          {item.first_name} {item.last_name || ''}
        </Text>
        <Text style={styles.contactPhone}>{item.phone}</Text>
      </View>
      <TouchableOpacity 
        style={styles.contactCallButton}
        onPress={() => {
          handleCall(item.phone);
          setShowSearchModal(false);
        }}
      >
        <Ionicons name="call" size={18} color="#34C759" />
      </TouchableOpacity>
    </TouchableOpacity>
  );
  
  const dialPad = [
    ['1', '2', '3'],
    ['4', '5', '6'],
    ['7', '8', '9'],
    ['*', '0', '#'],
  ];
  
  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.bg }]} edges={['top']}>
      {/* Header Icons */}
      <View style={[styles.headerIcons, { backgroundColor: colors.bg }]}>
        <WebIconButton 
          onPress={() => setShowSearchModal(true)}
          iconName="search"
          iconSize={24}
          iconColor="#007AFF"
          testID="dialer-search-btn"
        />
        <WebIconButton 
          onPress={() => {
            setShowCallLog(!showCallLog);
            setCallLogSearch('');
          }}
          iconName={showCallLog ? 'keypad' : 'time'}
          iconSize={24}
          iconColor="#007AFF"
          testID="dialer-toggle-btn"
        />
      </View>
      
      {!showCallLog ? (
        <View style={styles.dialerContainer}>
          {/* Number Display - moved up */}
          <View style={[styles.numberDisplay, { backgroundColor: colors.bg }]}>
            <Text style={[styles.numberText, { color: colors.text }]} numberOfLines={1} adjustsFontSizeToFit>
              {phoneNumber || '\u00A0'}
            </Text>
          </View>
          
          {/* Dial Pad */}
          <View style={styles.dialPadWrapper}>
            <View style={styles.dialPad}>
              {dialPad.map((row, rowIndex) => (
                <View key={rowIndex} style={styles.dialRow}>
                  {row.map((num) => (
                    <TouchableOpacity
                      key={num}
                      style={[styles.dialButton, { backgroundColor: colors.card }]}
                      onPress={() => handleDialPress(num)}
                    >
                      <Text style={[styles.dialButtonText, { color: colors.text }]}>{num}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              ))}
            </View>
            
            {/* Bottom row: empty, call button, backspace */}
            <View style={styles.bottomRow}>
              <View style={styles.bottomPlaceholder} />
              
              <TouchableOpacity
                style={[
                  styles.callActionButton,
                  !phoneNumber && styles.callActionButtonDisabled,
                ]}
                onPress={() => handleCall()}
                disabled={!phoneNumber}
              >
                <Ionicons name="call" size={32} color="#FFF" />
              </TouchableOpacity>
              
              <TouchableOpacity
                style={styles.backspaceButton}
                onPress={handleBackspace}
                disabled={!phoneNumber}
              >
                <Ionicons 
                  name="backspace-outline" 
                  size={28} 
                  color={phoneNumber ? '#FFF' : '#3A3A3C'} 
                />
              </TouchableOpacity>
            </View>
          </View>
        </View>
      ) : (
        <View style={styles.callLogContainer}>
          {/* Search bar for call history */}
          <View style={styles.callLogSearchContainer}>
            <View style={styles.searchBar}>
              <Ionicons name="search" size={20} color="#8E8E93" />
              <TextInput
                style={styles.searchInput}
                placeholder="Search call history"
                placeholderTextColor="#8E8E93"
                value={callLogSearch}
                onChangeText={setCallLogSearch}
              />
              {callLogSearch.length > 0 && (
                <TouchableOpacity onPress={() => setCallLogSearch('')}>
                  <Ionicons name="close-circle" size={20} color="#8E8E93" />
                </TouchableOpacity>
              )}
            </View>
          </View>
          
          <FlatList
            data={filteredCallLogs}
            renderItem={renderCallLog}
            keyExtractor={(item) => item.id}
            contentContainerStyle={styles.callLogContent}
            ItemSeparatorComponent={() => <View style={styles.separator} />}
            ListEmptyComponent={() => (
              <View style={styles.emptyContainer}>
                <Ionicons name="call-outline" size={48} color="#2C2C2E" />
                <Text style={styles.emptyText}>No calls found</Text>
              </View>
            )}
          />
        </View>
      )}
      
      {/* Contact Search Modal */}
      <Modal
        visible={showSearchModal}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setShowSearchModal(false)}
      >
        <SafeAreaView style={styles.modalContainer}>
          <View style={styles.modalHeader}>
            <TouchableOpacity 
              style={styles.modalCloseButton}
              onPress={() => {
                setShowSearchModal(false);
                setSearchQuery('');
              }}
            >
              <Ionicons name="close" size={28} color="#007AFF" />
            </TouchableOpacity>
            <Text style={styles.modalTitle}>Find Contact</Text>
            <View style={{ width: 28 }} />
          </View>
          
          <View style={styles.modalSearchContainer}>
            <View style={styles.searchBar}>
              <Ionicons name="search" size={20} color="#8E8E93" />
              <TextInput
                style={styles.searchInput}
                placeholder="Search by name or number"
                placeholderTextColor="#8E8E93"
                value={searchQuery}
                onChangeText={setSearchQuery}
                autoFocus
                autoCorrect={false}
                autoCapitalize="none"
              />
              {searchQuery.length > 0 && (
                <TouchableOpacity onPress={() => setSearchQuery('')}>
                  <Ionicons name="close-circle" size={20} color="#8E8E93" />
                </TouchableOpacity>
              )}
            </View>
          </View>
          
          <FlatList
            data={matchingContacts}
            renderItem={renderContactItem}
            keyExtractor={(item) => item._id}
            contentContainerStyle={styles.contactList}
            ItemSeparatorComponent={() => <View style={styles.separator} />}
            ListEmptyComponent={() => (
              <View style={styles.emptyContainer}>
                <Ionicons name="people-outline" size={48} color="#2C2C2E" />
                <Text style={styles.emptyText}>No contacts found</Text>
              </View>
            )}
            keyboardShouldPersistTaps="handled"
          />
        </SafeAreaView>
      </Modal>

      {/* Contact Match Modal */}
      {matchModalVisible && matchInfo && (
        <View style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.7)', justifyContent: 'center', alignItems: 'center', zIndex: 9999 }}>
          <View style={{ backgroundColor: '#1C1C1E', borderRadius: 16, padding: 24, width: '90%', maxWidth: 380 }} data-testid="dialer-match-modal">
            <View style={{ alignItems: 'center', marginBottom: 16 }}>
              <View style={{ width: 64, height: 64, borderRadius: 32, backgroundColor: '#FF950015', alignItems: 'center', justifyContent: 'center' }}>
                <Ionicons name="person-circle" size={44} color="#FF9500" />
              </View>
            </View>
            <Text style={{ fontSize: 18, fontWeight: '700', color: '#FFF', textAlign: 'center', marginBottom: 8 }}>Contact Already Exists</Text>
            <Text style={{ fontSize: 14, color: '#8E8E93', textAlign: 'center', marginBottom: 16 }}>A contact with this number already exists:</Text>
            <View style={{ backgroundColor: '#2C2C2E', borderRadius: 10, padding: 14, alignItems: 'center' }}>
              <Text style={{ fontSize: 10, fontWeight: '700', color: '#6E6E73', letterSpacing: 1, marginBottom: 6 }}>EXISTING CONTACT</Text>
              <Text style={{ fontSize: 17, fontWeight: '600', color: '#FFF' }}>{matchInfo.existing_name}</Text>
              {matchInfo.phone ? <Text style={{ fontSize: 13, color: '#8E8E93', marginTop: 2 }}>{matchInfo.phone}</Text> : null}
            </View>
            <View style={{ flexDirection: 'row', alignItems: 'center', marginVertical: 12 }}>
              <View style={{ flex: 1, height: 1, backgroundColor: '#2C2C2E' }} />
              <Text style={{ fontSize: 12, color: '#6E6E73', marginHorizontal: 12 }}>You entered</Text>
              <View style={{ flex: 1, height: 1, backgroundColor: '#2C2C2E' }} />
            </View>
            <View style={{ backgroundColor: '#2C2C2E', borderRadius: 10, padding: 14, alignItems: 'center', marginBottom: 20 }}>
              <Text style={{ fontSize: 17, fontWeight: '600', color: '#FF9500' }}>{matchInfo.provided_name}</Text>
            </View>
            <TouchableOpacity style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: '#2C2C2E', padding: 14, borderRadius: 10, gap: 10, marginBottom: 8 }} onPress={() => resolveDialerMatch('use_existing')}>
              <Ionicons name="checkmark-circle" size={20} color="#34C759" />
              <Text style={{ fontSize: 15, color: '#FFF', fontWeight: '500', flex: 1 }}>Use Existing Contact</Text>
            </TouchableOpacity>
            <TouchableOpacity style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: '#2C2C2E', padding: 14, borderRadius: 10, gap: 10, marginBottom: 8 }} onPress={() => resolveDialerMatch('update_name')}>
              <Ionicons name="create" size={20} color="#007AFF" />
              <Text style={{ fontSize: 15, color: '#FFF', fontWeight: '500', flex: 1 }}>Update to "{matchInfo.provided_name}"</Text>
            </TouchableOpacity>
            <TouchableOpacity style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: '#2C2C2E', padding: 14, borderRadius: 10, gap: 10, marginBottom: 8 }} onPress={() => resolveDialerMatch('create_new')}>
              <Ionicons name="person-add" size={20} color="#FF9500" />
              <Text style={{ fontSize: 15, color: '#FFF', fontWeight: '500', flex: 1 }}>Create New Contact</Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={() => { setMatchModalVisible(false); setMatchInfo(null); }} style={{ marginTop: 4, padding: 12, alignItems: 'center' }}>
              <Text style={{ fontSize: 15, color: '#8E8E93' }}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
  },
  headerIcons: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    paddingHorizontal: 16,
    paddingVertical: 12,
    paddingTop: 8,
    gap: 16,
    zIndex: 10,
  },
  headerButton: {
    padding: 4,
  },
  dialerContainer: {
    flex: 1,
    justifyContent: 'flex-end',
    paddingBottom: 20,
  },
  numberDisplay: {
    paddingHorizontal: 32,
    paddingVertical: 16,
    paddingTop: 24,
    alignItems: 'center',
    minHeight: 60,
    marginTop: 8,
  },
  numberText: {
    fontSize: 36,
    fontWeight: '300',
    color: '#FFF',
    letterSpacing: 2,
  },
  dialPadWrapper: {
    paddingHorizontal: 24,
    paddingBottom: 0,
  },
  dialPad: {
    gap: 12,
  },
  dialRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
  },
  dialButton: {
    width: 75,
    height: 75,
    borderRadius: 38,
    backgroundColor: '#1C1C1E',
    alignItems: 'center',
    justifyContent: 'center',
  },
  dialButtonText: {
    fontSize: 28,
    color: '#FFF',
    fontWeight: '400',
  },
  bottomRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignItems: 'center',
    marginTop: 16,
  },
  bottomPlaceholder: {
    width: 75,
    height: 75,
  },
  callActionButton: {
    width: 75,
    height: 75,
    borderRadius: 38,
    backgroundColor: '#34C759',
    alignItems: 'center',
    justifyContent: 'center',
  },
  callActionButtonDisabled: {
    opacity: 0.5,
  },
  backspaceButton: {
    width: 75,
    height: 75,
    borderRadius: 38,
    alignItems: 'center',
    justifyContent: 'center',
  },
  // Call Log styles
  callLogContainer: {
    flex: 1,
  },
  callLogSearchContainer: {
    paddingHorizontal: 16,
    paddingBottom: 8,
  },
  searchBar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    paddingHorizontal: 12,
    gap: 8,
  },
  searchInput: {
    flex: 1,
    paddingVertical: 12,
    fontSize: 16,
    color: '#FFF',
  },
  callLogContent: {
    paddingBottom: 16,
  },
  callLogItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
  },
  callIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: '#1C1C1E',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  callInfo: {
    flex: 1,
  },
  callName: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 2,
  },
  callPhone: {
    fontSize: 14,
    color: '#8E8E93',
  },
  callMeta: {
    alignItems: 'flex-end',
    marginRight: 12,
  },
  callTime: {
    fontSize: 14,
    color: '#8E8E93',
    marginBottom: 2,
  },
  callDuration: {
    fontSize: 12,
    color: '#8E8E93',
  },
  callButton: {
    padding: 8,
  },
  separator: {
    height: 1,
    backgroundColor: '#2C2C2E',
    marginLeft: 60,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 64,
  },
  emptyText: {
    fontSize: 16,
    color: '#8E8E93',
    marginTop: 16,
  },
  // Modal styles
  modalContainer: {
    flex: 1,
    backgroundColor: '#000',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  modalCloseButton: {
    padding: 4,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFF',
  },
  modalSearchContainer: {
    padding: 16,
  },
  contactList: {
    paddingBottom: 24,
  },
  contactItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
  },
  contactAvatar: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#2C2C2E',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  contactAvatarText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  contactInfo: {
    flex: 1,
  },
  contactName: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  contactPhone: {
    fontSize: 14,
    color: '#8E8E93',
    marginTop: 2,
  },
  contactCallButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#34C75920',
    alignItems: 'center',
    justifyContent: 'center',
  },
  
  // Restricted Access
  restrictedContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 32,
  },
  restrictedIcon: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: '#FF950020',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 24,
  },
  restrictedTitle: {
    fontSize: 24,
    fontWeight: '700',
    color: '#FFF',
    marginBottom: 12,
  },
  restrictedText: {
    fontSize: 16,
    color: '#8E8E93',
    textAlign: 'center',
    lineHeight: 24,
    marginBottom: 32,
  },
  restrictedButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#007AFF20',
    paddingVertical: 16,
    paddingHorizontal: 24,
    borderRadius: 12,
    gap: 8,
  },
  restrictedButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#007AFF',
  },
});
