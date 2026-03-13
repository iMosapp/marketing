import React, { useState, useEffect, useMemo } from 'react';
import {
  View, Text, TouchableOpacity, Platform, Linking, Dimensions,
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
const { width: SCREEN_W } = Dimensions.get('window');
const PAD_SIDE = Math.min(SCREEN_W, 420);
const BTN_SIZE = Math.min(Math.floor((PAD_SIDE - 80) / 3), 80);
const BTN_GAP = Math.floor((PAD_SIDE - 64 - BTN_SIZE * 3) / 2);

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
    }).slice(0, 5);
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

    // Log call activity BEFORE opening dialer (await ensures it completes)
    if (user?._id) {
      const digits = numberToCall.replace(/\D/g, '');
      const suffix = digits.length >= 10 ? digits.slice(-10) : digits;
      const match = contacts.find((c: any) => {
        const cDigits = (c.phone || '').replace(/\D/g, '');
        return cDigits.endsWith(suffix);
      });
      const contactName = match ? `${match.first_name || ''} ${match.last_name || ''}`.trim() : '';
      try {
        await api.post(`/contacts/${user._id}/find-or-create-and-log`, {
          phone: numberToCall, name: contactName,
          event_type: 'call_placed', event_title: 'Call Placed',
          event_description: `Called ${contactName || numberToCall} from dialer`,
          event_icon: 'call', event_color: '#34C759',
          event_channel: 'call',
        });
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
          <Text style={{ fontSize: 16, color: colors.textSecondary, textAlign: 'center', lineHeight: 24 }}>
            Your account is being reviewed. You'll have full access once configured.
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  // Format number for display — iOS style
  const formatDisplay = (num: string) => {
    const d = num.replace(/\D/g, '');
    if (d.length <= 3) return d;
    if (d.length <= 6) return `${d.slice(0, 3)}-${d.slice(3)}`;
    if (d.length <= 10) return `(${d.slice(0, 3)}) ${d.slice(3, 6)}-${d.slice(6)}`;
    return `+${d.slice(0, d.length - 10)} (${d.slice(-10, -7)}) ${d.slice(-7, -4)}-${d.slice(-4)}`;
  };

  // Format phone for contact match display
  const formatPhone = (p: string) => {
    const d = (p || '').replace(/\D/g, '');
    if (d.length === 11 && d[0] === '1') return `(${d.slice(1, 4)}) ${d.slice(4, 7)}-${d.slice(7)}`;
    if (d.length === 10) return `(${d.slice(0, 3)}) ${d.slice(3, 6)}-${d.slice(6)}`;
    return p;
  };

  // Truncate name for compact display
  const truncName = (c: any) => {
    const full = `${c.first_name || ''} ${c.last_name || ''}`.trim();
    return full.length > 14 ? full.slice(0, 12) + '...' : full;
  };

  const showMatches = matchingContacts.length > 0 && phoneNumber.length >= 3;
  const visibleMatches = matchingContacts.slice(0, 2);
  const moreCount = matchingContacts.length - 2;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']} data-testid="dialer-screen">
      <View style={{ flex: 1, justifyContent: 'flex-end' }}>

        {/* ─── Number Display ─── */}
        <View style={{ alignItems: 'center', paddingHorizontal: 24, paddingBottom: 4, minHeight: 56 }}>
          {phoneNumber ? (
            <Text
              style={{
                fontSize: phoneNumber.length > 10 ? 34 : 42,
                fontWeight: '200',
                color: colors.text,
                letterSpacing: 1.5,
                fontVariant: ['tabular-nums'],
              }}
              numberOfLines={1}
              adjustsFontSizeToFit
              data-testid="dialer-number-display"
            >
              {formatDisplay(phoneNumber)}
            </Text>
          ) : (
            <Text style={{ fontSize: 42, fontWeight: '200', color: colors.text, opacity: 0 }}>{'\u00A0'}</Text>
          )}
        </View>

        {/* ─── Contact Matches (fixed height so keypad never moves) ─── */}
        <View style={{ height: 90, marginHorizontal: 32, marginBottom: 6, justifyContent: 'flex-end' }} data-testid="dialer-matches-container">
          {showMatches && (
            <View style={{ backgroundColor: colors.card, borderRadius: 10, overflow: 'hidden' }} data-testid="dialer-matches">
            {visibleMatches.map((c: any, i: number) => (
              <TouchableOpacity
                key={c._id}
                style={{
                  flexDirection: 'row', alignItems: 'center',
                  paddingHorizontal: 12, paddingVertical: 9,
                  borderTopWidth: i > 0 ? 0.5 : 0, borderTopColor: colors.border,
                }}
                onPress={() => { setPhoneNumber(c.phone || ''); handleCall(c.phone); }}
                activeOpacity={0.6}
                data-testid={`dialer-match-${i}`}
              >
                <Ionicons name="person-circle" size={20} color={colors.textSecondary} style={{ marginRight: 8 }} />
                <Text style={{ fontSize: 15, fontWeight: '400', color: colors.text, marginRight: 6 }} numberOfLines={1}>
                  {truncName(c)}
                </Text>
                <Text style={{ fontSize: 15, color: colors.textSecondary, flex: 1 }} numberOfLines={1}>
                  {formatPhone(c.phone)}
                </Text>
              </TouchableOpacity>
            ))}
            {moreCount > 0 && (
              <View style={{
                flexDirection: 'row', alignItems: 'center',
                paddingHorizontal: 12, paddingVertical: 8,
                borderTopWidth: 0.5, borderTopColor: colors.border,
              }}>
                <Ionicons name="search" size={16} color={colors.textSecondary} style={{ marginRight: 8 }} />
                <Text style={{ fontSize: 14, color: colors.textSecondary }}>
                  {moreCount} More Result{moreCount > 1 ? 's' : ''}
                </Text>
              </View>
            )}
          </View>
          )}
        </View>

        {/* ─── Dial Pad ─── */}
        <View style={{ alignSelf: 'center', width: PAD_SIDE, paddingHorizontal: 32, paddingTop: 8, paddingBottom: 4 }}>
          {[0, 1, 2, 3].map(row => (
            <View key={row} style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 14 }}>
              {DIAL_KEYS.slice(row * 3, row * 3 + 3).map(key => (
                <TouchableOpacity
                  key={key.num}
                  style={{
                    width: BTN_SIZE, height: BTN_SIZE, borderRadius: BTN_SIZE / 2,
                    backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center',
                  }}
                  onPress={() => handleDialPress(key.num)}
                  activeOpacity={0.5}
                  data-testid={`dial-${key.num === '*' ? 'star' : key.num === '#' ? 'hash' : key.num}`}
                >
                  <Text style={{ fontSize: 30, fontWeight: '400', color: colors.text, lineHeight: 34 }}>
                    {key.num}
                  </Text>
                  {key.letters ? (
                    <Text style={{ fontSize: 10, fontWeight: '700', color: colors.textSecondary, letterSpacing: 1.5, marginTop: -1 }}>
                      {key.letters}
                    </Text>
                  ) : null}
                </TouchableOpacity>
              ))}
            </View>
          ))}

          {/* ─── Bottom Row: [empty] | Call | Backspace ─── */}
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 2 }}>
            <View style={{ width: BTN_SIZE, height: BTN_SIZE }} />
            <TouchableOpacity
              style={{
                width: BTN_SIZE, height: BTN_SIZE, borderRadius: BTN_SIZE / 2,
                backgroundColor: '#34C759', alignItems: 'center', justifyContent: 'center',
                opacity: phoneNumber ? 1 : 0.4,
              }}
              onPress={() => handleCall()}
              disabled={!phoneNumber}
              data-testid="dialer-call-btn"
            >
              <Ionicons name="call" size={32} color="#FFF" />
            </TouchableOpacity>
            {phoneNumber ? (
              <TouchableOpacity
                style={{
                  width: BTN_SIZE, height: BTN_SIZE, borderRadius: BTN_SIZE / 2,
                  alignItems: 'center', justifyContent: 'center',
                }}
                onPress={handleBackspace}
                onLongPress={() => { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium); setPhoneNumber(''); }}
                data-testid="dialer-backspace-btn"
              >
                <Ionicons name="backspace-outline" size={26} color={colors.text} />
              </TouchableOpacity>
            ) : (
              <View style={{ width: BTN_SIZE, height: BTN_SIZE }} />
            )}
          </View>
        </View>

        {/* Bottom spacer */}
        <View style={{ height: 8 }} />
      </View>
    </SafeAreaView>
  );
}
