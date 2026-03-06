import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet, FlatList,
  Platform, Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { contactsAPI } from '../../services/api';
import api from '../../services/api';

const IS_WEB = Platform.OS === 'web';

const DIAL_KEYS: { num: string; letters: string }[] = [
  { num: '1', letters: '' },
  { num: '2', letters: 'ABC' },
  { num: '3', letters: 'DEF' },
  { num: '4', letters: 'GHI' },
  { num: '5', letters: 'JKL' },
  { num: '6', letters: 'MNO' },
  { num: '7', letters: 'PQRS' },
  { num: '8', letters: 'TUV' },
  { num: '9', letters: 'WXYZ' },
  { num: '*', letters: '' },
  { num: '0', letters: '+' },
  { num: '#', letters: '' },
];

export default function DialerScreen() {
  const { colors } = useThemeStore();
  const router = useRouter();
  const user = useAuthStore((state) => state.user);

  const [phoneNumber, setPhoneNumber] = useState('');
  const [contacts, setContacts] = useState<any[]>([]);

  const isPending = user?.status === 'pending';

  useEffect(() => {
    if (user && !isPending) {
      contactsAPI.getAll(user._id).then(setContacts).catch(() => {});
    }
  }, [user, isPending]);

  // Matching contacts as user dials
  const matchingContacts = useMemo(() => {
    if (!phoneNumber || phoneNumber.length < 3) return [];
    const digits = phoneNumber.replace(/\D/g, '');
    return contacts.filter(c => {
      const cDigits = (c.phone || '').replace(/\D/g, '');
      return cDigits.includes(digits);
    }).slice(0, 3);
  }, [phoneNumber, contacts]);

  const handleDialPress = (num: string) => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setPhoneNumber(prev => prev + num);
  };

  const handleBackspace = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setPhoneNumber(prev => prev.slice(0, -1));
  };

  const handleCall = async (number?: string) => {
    const numberToCall = number || phoneNumber;
    if (!numberToCall) return;
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);

    // Log call activity
    if (user?._id) {
      const digits = numberToCall.replace(/\D/g, '');
      const suffix = digits.length >= 10 ? digits.slice(-10) : digits;
      const match = contacts.find((c: any) => {
        const cDigits = (c.phone || '').replace(/\D/g, '');
        return cDigits.endsWith(suffix);
      });
      const contactName = match ? `${match.first_name || ''} ${match.last_name || ''}`.trim() : '';
      const apiBase = IS_WEB ? '/api' : `${process.env.EXPO_PUBLIC_BACKEND_URL || ''}/api`;
      try {
        fetch(`${apiBase}/contacts/${user._id}/find-or-create-and-log`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            phone: numberToCall, name: contactName,
            event_type: 'call_placed', event_title: 'Call Placed',
            event_description: `Called ${contactName || numberToCall} from dialer`,
            event_icon: 'call', event_color: '#34C759',
          }),
          keepalive: true,
        }).catch(() => {});
      } catch {}
    }

    const telUrl = `tel:${numberToCall}`;
    if (IS_WEB) {
      const a = document.createElement('a');
      a.href = telUrl; a.target = '_self';
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
    } else {
      Linking.openURL(telUrl);
    }
  };

  // Restricted access for pending users
  if (isPending) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32 }}>
          <View style={{ width: 100, height: 100, borderRadius: 50, backgroundColor: '#FF950020', alignItems: 'center', justifyContent: 'center', marginBottom: 24 }}>
            <Ionicons name="lock-closed" size={48} color="#FF9500" />
          </View>
          <Text style={{ fontSize: 24, fontWeight: '700', color: colors.text, marginBottom: 12 }}>Access Pending</Text>
          <Text style={{ fontSize: 16, color: colors.textSecondary, textAlign: 'center', lineHeight: 24, marginBottom: 32 }}>
            Your account is being reviewed. You'll have full access to calls once configured.
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  // Format number for display (like iPhone: groups of 3)
  const formatDisplay = (num: string) => {
    const d = num.replace(/\D/g, '');
    if (d.length <= 3) return d;
    if (d.length <= 6) return `${d.slice(0, 3)}-${d.slice(3)}`;
    return `(${d.slice(0, 3)}) ${d.slice(3, 6)}-${d.slice(6, 10)}`;
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']} data-testid="dialer-screen">
      <View style={{ flex: 1, justifyContent: 'flex-end' }}>
        {/* Number Display */}
        <View style={{ alignItems: 'center', paddingHorizontal: 24, paddingTop: 16, minHeight: 60 }}>
          <Text
            style={{ fontSize: phoneNumber.length > 10 ? 32 : 40, fontWeight: '300', color: colors.text, letterSpacing: 2 }}
            numberOfLines={1} adjustsFontSizeToFit
            data-testid="dialer-number-display"
          >
            {phoneNumber ? formatDisplay(phoneNumber) : '\u00A0'}
          </Text>
        </View>

        {/* Matching Contacts */}
        {matchingContacts.length > 0 && (
          <View style={{ marginHorizontal: 24, marginTop: 8, marginBottom: 4, backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: colors.border, overflow: 'hidden' }} data-testid="dialer-matches">
            {matchingContacts.map((c, i) => (
              <TouchableOpacity
                key={c._id}
                style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 14, paddingVertical: 10, borderTopWidth: i > 0 ? 1 : 0, borderTopColor: colors.border }}
                onPress={() => { setPhoneNumber(c.phone || ''); }}
                data-testid={`dialer-match-${i}`}
              >
                <Ionicons name="person-circle-outline" size={22} color={colors.textSecondary} style={{ marginRight: 10 }} />
                <Text style={{ fontSize: 15, fontWeight: '500', color: colors.text, flex: 1 }} numberOfLines={1}>
                  {c.first_name} {c.last_name || ''}
                </Text>
                <Text style={{ fontSize: 14, color: colors.textSecondary, marginLeft: 8 }}>
                  {c.phone}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        )}

        {/* Dial Pad */}
        <View style={{ paddingHorizontal: 32, paddingTop: 12, paddingBottom: 8 }}>
          {[0, 1, 2, 3].map(row => (
            <View key={row} style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 14 }}>
              {DIAL_KEYS.slice(row * 3, row * 3 + 3).map(key => (
                <TouchableOpacity
                  key={key.num}
                  style={{
                    width: 80, height: 80, borderRadius: 40,
                    backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center',
                  }}
                  onPress={() => handleDialPress(key.num)}
                  activeOpacity={0.6}
                  data-testid={`dial-${key.num === '*' ? 'star' : key.num === '#' ? 'hash' : key.num}`}
                >
                  <Text style={{ fontSize: 32, fontWeight: '300', color: colors.text, lineHeight: 36 }}>
                    {key.num}
                  </Text>
                  {key.letters ? (
                    <Text style={{ fontSize: 10, fontWeight: '600', color: colors.textSecondary, letterSpacing: 2, marginTop: -2 }}>
                      {key.letters}
                    </Text>
                  ) : null}
                </TouchableOpacity>
              ))}
            </View>
          ))}

          {/* Bottom Row: empty | Call | Backspace */}
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 4 }}>
            <View style={{ width: 80, height: 80 }} />
            <TouchableOpacity
              style={{
                width: 80, height: 80, borderRadius: 40,
                backgroundColor: '#34C759', alignItems: 'center', justifyContent: 'center',
                opacity: phoneNumber ? 1 : 0.5,
              }}
              onPress={() => handleCall()}
              disabled={!phoneNumber}
              data-testid="dialer-call-btn"
            >
              <Ionicons name="call" size={34} color="#FFF" />
            </TouchableOpacity>
            {phoneNumber ? (
              <TouchableOpacity
                style={{ width: 80, height: 80, borderRadius: 40, alignItems: 'center', justifyContent: 'center' }}
                onPress={handleBackspace}
                data-testid="dialer-backspace-btn"
              >
                <Ionicons name="backspace-outline" size={28} color={colors.text} />
              </TouchableOpacity>
            ) : (
              <View style={{ width: 80, height: 80 }} />
            )}
          </View>
        </View>
      </View>
    </SafeAreaView>
  );
}
