import React, { useState, useEffect, useMemo } from 'react';
import {
  View, Text, TouchableOpacity, Platform, Linking, Dimensions, TextInput, ScrollView, Keyboard, ActivityIndicator,
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
const { width: SCREEN_W, height: SCREEN_H } = Dimensions.get('window');
const PAD_SIDE = Math.min(SCREEN_W, 420);
// Cap keypad button size by HEIGHT too so the pad never overflows the top of the screen
// Chrome above/below keypad: safe areas + search + toggle + indicator + number + matches + tab bar
const CHROME_H = 470;
const HEIGHT_BTN = Math.floor((SCREEN_H - CHROME_H - 58) / 5);
const BTN_SIZE = Math.max(52, Math.min(Math.floor((PAD_SIDE - 80) / 3), 80, HEIGHT_BTN));
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
  const [searchQuery, setSearchQuery] = useState('');
  const [searchFocused, setSearchFocused] = useState(false);
  const [serverResults, setServerResults] = useState<any[]>([]);
  const [searching, setSearching] = useState(false);
  const [dialMatches, setDialMatches] = useState<any[]>([]);
  const [viewMode, setViewMode] = useState<'keypad' | 'recents'>('keypad');
  const [recentCalls, setRecentCalls] = useState<any[]>([]);
  const [recentsLoading, setRecentsLoading] = useState(false);
  const [activeCall, setActiveCall] = useState<{ sid: string; name: string; number: string; status: string } | null>(null);

  const isPending = user?.status === 'pending';

  useEffect(() => {
    if (user && !isPending) {
      contactsAPI.getAll(user._id).then(data => setContacts(Array.isArray(data) ? data : (data?.contacts || []))).catch(() => {});
    }
  }, [user, isPending]);

  // Server-side name/number search — searches the FULL contact book, not just loaded page
  useEffect(() => {
    const q = searchQuery.trim();
    if (q.length < 2 || !user?._id) { setServerResults([]); return; }
    const qSend = /^[\d\s\-()+.]+$/.test(q) ? q.replace(/\D/g, '') : q;
    const t = setTimeout(async () => {
      try {
        setSearching(true);
        const data = await contactsAPI.getAll(user._id, qSend, undefined, undefined, 0, 30);
        const results = (Array.isArray(data) ? data : (data?.contacts || []))
          .filter((c: any) => (c.phone || '').replace(/\D/g, '').length >= 7);
        setServerResults(results);
      } catch { /* keep last results */ } finally {
        setSearching(false);
      }
    }, 250);
    return () => clearTimeout(t);
  }, [searchQuery, user?._id]);

  // Server-side match as user dials digits on the keypad
  useEffect(() => {
    const digits = phoneNumber.replace(/\D/g, '');
    if (digits.length < 3 || !user?._id) { setDialMatches([]); return; }
    const t = setTimeout(async () => {
      try {
        const data = await contactsAPI.getAll(user._id, digits, undefined, undefined, 0, 10);
        setDialMatches(Array.isArray(data) ? data : (data?.contacts || []));
      } catch { /* keep last */ }
    }, 250);
    return () => clearTimeout(t);
  }, [phoneNumber, user?._id]);

  const matchingContacts = useMemo(() => {
    if (!phoneNumber || phoneNumber.replace(/\D/g, '').length < 3) return [];
    return dialMatches.slice(0, 5);
  }, [phoneNumber, dialMatches]);

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

    // Find matching contact for logging — check live search results first, then loaded page
    const digits = numberToCall.replace(/\D/g, '');
    const suffix = digits.length >= 10 ? digits.slice(-10) : digits;
    const match = [...dialMatches, ...serverResults, ...contacts].find(
      (c: any) => (c.phone || '').replace(/\D/g, '').endsWith(suffix)
    );
    const contactName = match ? `${match.first_name || ''} ${match.last_name || ''}`.trim() : '';
    const contactId = match?._id || '';

    // Use Twilio Click-to-Call if rep has a dedicated number
    const twilioNumber = (user as any)?.twilio_number || (user as any)?.mvpline_number;
    if (twilioNumber && user?._id) {
      try {
        const resp = await api.post('/webhooks/twilio/call', {
          rep_user_id: user._id,
          customer_phone: numberToCall,
          contact_id: contactId,
        });
        if (resp.data?.call_sid) {
          setActiveCall({ sid: resp.data.call_sid, name: contactName, number: numberToCall, status: 'ringing' });
        }
        // Log activity
        if (user._id) {
          api.post(`/contacts/${user._id}/find-or-create-and-log`, {
            phone: numberToCall, name: contactName,
            event_type: 'call_placed', event_title: 'Call Placed',
            event_description: `Called ${contactName || numberToCall} via Twilio`,
            event_icon: 'call', event_color: '#34C759', event_channel: 'call',
          }).catch(() => {});
        }
        return; // Twilio will ring your personal phone — pick up to connect
      } catch (err: any) {
        const msg = err?.response?.data?.detail || 'Could not start call via Twilio. Falling back to native dialer.';
        console.warn('[Dialer] Twilio call failed:', msg);
        // Fall through to native dialer below
      }
    }

    // Fallback: native phone dialer
    if (user?._id) {
      api.post(`/contacts/${user._id}/find-or-create-and-log`, {
        phone: numberToCall, name: contactName,
        event_type: 'call_placed', event_title: 'Call Placed',
        event_description: `Called ${contactName || numberToCall} from dialer`,
        event_icon: 'call', event_color: '#34C759', event_channel: 'call',
      }).catch(() => {});
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

  // Poll live call status while a click-to-call is active
  useEffect(() => {
    if (!activeCall?.sid) return;
    const iv = setInterval(async () => {
      try {
        const r = await api.get(`/webhooks/twilio/call-progress/${activeCall.sid}`);
        const st = r.data?.status || '';
        if (['completed', 'busy', 'failed', 'no-answer', 'canceled'].includes(st)) {
          setActiveCall(null);
        } else if (st && st !== 'unknown') {
          setActiveCall((p) => (p && p.status !== st ? { ...p, status: st } : p));
        }
      } catch { /* keep polling */ }
    }, 2000);
    return () => clearInterval(iv);
  }, [activeCall?.sid]);

  const hangUp = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);
    const sid = activeCall?.sid;
    setActiveCall(null);
    if (sid) api.post('/webhooks/twilio/call-cancel', { call_sid: sid }).catch(() => {});
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
          <Text style={{ fontSize: 18, color: colors.textSecondary, textAlign: 'center', lineHeight: 24 }}>
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

  // Name search matches — server results (full contact book)
  const nameMatches = useMemo(() => {
    if (searchQuery.trim().length < 2) return [];
    return serverResults.slice(0, 20);
  }, [searchQuery, serverResults]);

  const handleSearchCall = (c: any) => {
    Keyboard.dismiss();
    setSearchQuery('');
    setPhoneNumber(c.phone || '');
    setViewMode('keypad');
  };

  useEffect(() => {
    if (viewMode === 'recents' && user?._id) {
      setRecentsLoading(true);
      api.get(`/contacts/${user._id}/recent-calls?limit=50`)
        .then(r => {
          const raw = r.data?.calls || [];
          // Collapse consecutive calls to the same contact into one row with a count
          const grouped: any[] = [];
          for (const c of raw) {
            const last = grouped[grouped.length - 1];
            if (last && last.contact_id === c.contact_id && last.direction === c.direction) {
              last.count += 1;
            } else {
              grouped.push({ ...c, count: 1 });
            }
          }
          setRecentCalls(grouped);
        })
        .catch(() => {})
        .finally(() => setRecentsLoading(false));
    }
  }, [viewMode, user?._id]);

  const timeAgo = (iso: string) => {
    try {
      const diffMin = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
      if (diffMin < 1) return 'now';
      if (diffMin < 60) return `${diffMin}m`;
      const hrs = Math.floor(diffMin / 60);
      if (hrs < 24) return `${hrs}h`;
      const days = Math.floor(hrs / 24);
      if (days < 7) return `${days}d`;
      return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    } catch { return ''; }
  };

  const showMatches = matchingContacts.length > 0 && phoneNumber.length >= 3;
  const visibleMatches = matchingContacts.slice(0, 2);
  const moreCount = matchingContacts.length - 2;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']} data-testid="dialer-screen">
      {/* ─── Name Search Bar ─── */}
      <View style={{ flexDirection: 'row', alignItems: 'center', marginHorizontal: 20, marginTop: 8, backgroundColor: colors.card, borderRadius: 12, paddingHorizontal: 12, height: 42 }}>
        <Ionicons name="search" size={18} color={colors.textSecondary} />
        <TextInput
          style={{ flex: 1, fontSize: 16, color: colors.text, marginLeft: 8, height: 42 }}
          placeholder="Search by name or number"
          placeholderTextColor={colors.textTertiary || colors.textSecondary}
          value={searchQuery}
          onChangeText={setSearchQuery}
          onFocus={() => setSearchFocused(true)}
          onBlur={() => setSearchFocused(false)}
          autoCorrect={false}
          autoCapitalize="words"
          returnKeyType="search"
          maxFontSizeMultiplier={1.2}
          data-testid="dialer-name-search-input"
        />
        {searchQuery.length > 0 && (
          <TouchableOpacity onPress={() => { setSearchQuery(''); Keyboard.dismiss(); }} data-testid="dialer-search-clear-btn">
            <Ionicons name="close-circle" size={18} color={colors.textSecondary} />
          </TouchableOpacity>
        )}
      </View>

      {/* ─── Keypad / Recents Toggle ─── */}
      <View style={{ flexDirection: 'row', alignSelf: 'center', marginTop: 10, backgroundColor: colors.card, borderRadius: 10, padding: 3 }}>
        {([['keypad', 'Keypad', 'keypad-outline'], ['recents', 'Recents', 'time-outline']] as const).map(([m, label, icon]) => (
          <TouchableOpacity
            key={m}
            onPress={() => setViewMode(m)}
            style={{
              flexDirection: 'row', alignItems: 'center', gap: 6,
              paddingVertical: 7, paddingHorizontal: 26, borderRadius: 8,
              backgroundColor: viewMode === m ? colors.bg : 'transparent',
            }}
            data-testid={`dialer-tab-${m}`}
          >
            <Ionicons name={icon as any} size={15} color={viewMode === m ? colors.text : colors.textSecondary} />
            <Text style={{ fontSize: 14, fontWeight: '600', color: viewMode === m ? colors.text : colors.textSecondary }} numberOfLines={1} maxFontSizeMultiplier={1.15}>{label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {(searchFocused || searchQuery.trim().length > 0) ? (
        /* ─── Search Results (also shown while search is focused so the keypad never overlaps the keyboard) ─── */
        <ScrollView
          style={{ flex: 1, marginTop: 10 }}
          contentContainerStyle={{ paddingHorizontal: 20, paddingBottom: 24 }}
          keyboardShouldPersistTaps="handled"
          data-testid="dialer-search-results"
        >
          {searchQuery.trim().length < 2 ? (
            <View style={{ alignItems: 'center', paddingTop: 40 }}>
              <Ionicons name="search" size={32} color={colors.textTertiary || colors.textSecondary} />
              <Text style={{ fontSize: 16, color: colors.textSecondary, marginTop: 8 }}>Type a name or number</Text>
            </View>
          ) : searching && nameMatches.length === 0 ? (
            <ActivityIndicator size="small" color={colors.textSecondary} style={{ marginTop: 40 }} />
          ) : nameMatches.length === 0 ? (
            <View style={{ alignItems: 'center', paddingTop: 40 }}>
              <Ionicons name="person-outline" size={32} color={colors.textTertiary || colors.textSecondary} />
              <Text style={{ fontSize: 16, color: colors.textSecondary, marginTop: 8 }}>No contacts found</Text>
            </View>
          ) : (
            nameMatches.map((c: any, i: number) => (
              <TouchableOpacity
                key={c._id}
                style={{
                  flexDirection: 'row', alignItems: 'center', paddingVertical: 12,
                  borderBottomWidth: 0.5, borderBottomColor: colors.border,
                }}
                onPress={() => handleSearchCall(c)}
                activeOpacity={0.6}
                data-testid={`dialer-search-result-${i}`}
              >
                <Ionicons name="person-circle" size={36} color={colors.textSecondary} style={{ marginRight: 10 }} />
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 17, fontWeight: '600', color: colors.text }} numberOfLines={1}>
                    {`${c.first_name || ''} ${c.last_name || ''}`.trim() || 'Unnamed'}
                  </Text>
                  <Text style={{ fontSize: 14, color: colors.textSecondary, marginTop: 1 }} numberOfLines={1}>
                    {formatPhone(c.phone)}
                  </Text>
                </View>
                <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: '#34C75920', alignItems: 'center', justifyContent: 'center' }}>
                  <Ionicons name="call" size={18} color="#34C759" />
                </View>
              </TouchableOpacity>
            ))
          )}
        </ScrollView>
      ) : viewMode === 'recents' ? (
        /* ─── Recent Calls ─── */
        <ScrollView
          style={{ flex: 1, marginTop: 10 }}
          contentContainerStyle={{ paddingHorizontal: 20, paddingBottom: 24 }}
          data-testid="dialer-recents-list"
        >
          {recentsLoading ? (
            <ActivityIndicator size="small" color={colors.textSecondary} style={{ marginTop: 40 }} />
          ) : recentCalls.length === 0 ? (
            <View style={{ alignItems: 'center', paddingTop: 40 }}>
              <Ionicons name="call-outline" size={32} color={colors.textTertiary || colors.textSecondary} />
              <Text style={{ fontSize: 16, color: colors.textSecondary, marginTop: 8 }}>No recent calls</Text>
            </View>
          ) : (
            recentCalls.map((c: any, i: number) => (
              <TouchableOpacity
                key={`${c.contact_id}-${i}`}
                style={{
                  flexDirection: 'row', alignItems: 'center', paddingVertical: 12,
                  borderBottomWidth: 0.5, borderBottomColor: colors.border,
                }}
                onPress={() => { setPhoneNumber(c.phone || ''); setViewMode('keypad'); }}
                activeOpacity={0.6}
                data-testid={`dialer-recent-${i}`}
              >
                <Ionicons
                  name={c.direction === 'outgoing' ? 'arrow-up-circle-outline' : 'arrow-down-circle-outline'}
                  size={22}
                  color={c.direction === 'outgoing' ? '#34C759' : '#007AFF'}
                  style={{ marginRight: 10 }}
                />
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 17, fontWeight: '600', color: colors.text }} numberOfLines={1}>
                    {c.name}{c.count > 1 ? ` (${c.count})` : ''}
                  </Text>
                  <Text style={{ fontSize: 14, color: colors.textSecondary, marginTop: 1 }} numberOfLines={1}>{formatPhone(c.phone)}</Text>
                </View>
                <Text style={{ fontSize: 13, color: colors.textSecondary, marginRight: 12 }}>{timeAgo(c.timestamp)}</Text>
                <TouchableOpacity
                  onPress={() => handleCall(c.phone)}
                  style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: '#34C75920', alignItems: 'center', justifyContent: 'center' }}
                  data-testid={`dialer-recent-call-${i}`}
                >
                  <Ionicons name="call" size={18} color="#34C759" />
                </TouchableOpacity>
              </TouchableOpacity>
            ))
          )}
        </ScrollView>
      ) : (
      <View style={{ flex: 1, justifyContent: 'flex-end', overflow: 'hidden' }}>

        {/* Twilio number indicator / live call status */}
        {activeCall ? (
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingTop: 8, paddingBottom: 4 }} data-testid="dialer-active-call-status">
            <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: '#FF9500' }} />
            <Text style={{ fontSize: 13, color: '#FF9500', fontWeight: '600' }} numberOfLines={1}>
              {activeCall.status === 'in-progress'
                ? `On the line — press 1 to reach ${activeCall.name || formatPhone(activeCall.number)}`
                : 'Calling your phone… answer & press 1 to connect'}
            </Text>
          </View>
        ) : ((user as any)?.twilio_number || (user as any)?.mvpline_number) ? (
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingTop: 8, paddingBottom: 4 }}>
            <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: '#34C759' }} />
            <Text style={{ fontSize: 13, color: '#34C759', fontWeight: '600' }}>
              Calling from {(user as any)?.twilio_number || (user as any)?.mvpline_number}
            </Text>
          </View>
        ) : (
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingTop: 8, paddingBottom: 4 }}>
            <Ionicons name="warning-outline" size={14} color="#FF9500" />
            <Text style={{ fontSize: 13, color: '#FF9500' }}>No Twilio number — using native dialer</Text>
          </View>
        )}

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
                onPress={() => setPhoneNumber(c.phone || '')}
                activeOpacity={0.6}
                data-testid={`dialer-match-${i}`}
              >
                <Ionicons name="person-circle" size={20} color={colors.textSecondary} style={{ marginRight: 8 }} />
                <Text style={{ fontSize: 17, fontWeight: '400', color: colors.text, marginRight: 6 }} numberOfLines={1}>
                  {truncName(c)}
                </Text>
                <Text style={{ fontSize: 17, color: colors.textSecondary, flex: 1 }} numberOfLines={1}>
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
                <Text style={{ fontSize: 16, color: colors.textSecondary }}>
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
                    <Text style={{ fontSize: 12, fontWeight: '700', color: colors.textSecondary, letterSpacing: 1.5, marginTop: -1 }}>
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
            {activeCall ? (
              <TouchableOpacity
                style={{
                  width: BTN_SIZE, height: BTN_SIZE, borderRadius: BTN_SIZE / 2,
                  backgroundColor: '#FF3B30', alignItems: 'center', justifyContent: 'center',
                }}
                onPress={hangUp}
                data-testid="dialer-hangup-btn"
              >
                <Ionicons name="call" size={32} color="#FFF" style={{ transform: [{ rotate: '135deg' }] }} />
              </TouchableOpacity>
            ) : (
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
            )}
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
      )}
    </SafeAreaView>
  );
}
