import React from 'react';
import { View, Text, TouchableOpacity, TextInput, Image } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { resolvePhotoUrl } from '../../utils/photoUrl';
import { GOLD, tid } from '../inbox/ownership';
import { ScanMatch } from '../../hooks/useScanWithJessi';

const AMBER = '#FF9500';
const ORDER = ['first_name', 'last_name', 'company', 'title', 'phone', 'phone_office', 'email', 'website', 'address_street', 'address_city', 'address_state', 'address_zip'];

type Props = { scan: any; values: Record<string, string>; setValue: (k: string, v: string) => void; matches: ScanMatch[]; colors: any;
  onCreate: () => void; onUpdate: (m: ScanMatch) => void; onDiscard: () => void };

const Label = ({ text, colors }: any) => <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8, marginTop: 14, marginBottom: 6 }}>{text}</Text>;

// Jessi found / suggested information (editable) / possible existing contacts / what to do with it.
export const ScanReview = ({ scan, values, setValue, matches, colors, onCreate, onUpdate, onDiscard }: Props) => {
  const keys = ORDER.filter(k => k in values);
  const thumb = resolvePhotoUrl(scan.thumb_url || scan.url) || '';
  return (
    <View {...tid('scan-review')}>
      <View style={{ flexDirection: 'row', gap: 12, alignItems: 'flex-start' }}>
        {!!thumb && <Image source={{ uri: thumb }} style={{ width: 64, height: 64, borderRadius: 10, backgroundColor: colors.card }} />}
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 0.8 }}>JESSI FOUND</Text>
          <Text style={{ fontSize: 14, color: colors.text, marginTop: 3, lineHeight: 20 }} {...tid('scan-summary')}>
            {scan.sensitive ? 'This looks like a private document (an ID, insurance or a financial form). Jessi did not keep any details from it.'
              : scan.paused ? 'Jessi is not reading photos right now. Try again a little later.'
              : scan.status !== 'ready' ? 'Jessi could not read this one. Try again in better light, flat and in focus.'
              : scan.summary || scan.title || 'Read it.'}
          </Text>
          {scan.reused && <Text style={{ fontSize: 11.5, color: colors.textSecondary, marginTop: 2 }}>Same picture as before, so Jessi reused her reading.</Text>}
        </View>
      </View>

      {scan.is_card && keys.length > 0 && (
        <>
          <Label text="CARD DETAILS · CHECK AND EDIT" colors={colors} />
          {scan.check && (
            <View style={{ flexDirection: 'row', gap: 6, alignItems: 'center', marginBottom: 6 }} {...tid('scan-check-warning')}>
              <Ionicons name="alert-circle" size={14} color={AMBER} />
              <Text style={{ fontSize: 12.5, color: AMBER, fontWeight: '700' }}>Hard to read in places. Double-check these.</Text>
            </View>
          )}
          <View style={{ backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: colors.border }}>
            {keys.map((k, i) => (
              <View key={k} style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, borderTopWidth: i ? 1 : 0, borderTopColor: colors.border }}>
                <Text style={{ width: 104, fontSize: 12.5, color: colors.textSecondary }}>{scan.labels?.[k] || k}</Text>
                <TextInput value={values[k]} onChangeText={t => setValue(k, t)} style={{ flex: 1, fontSize: 15, color: colors.text, paddingVertical: 10 }}
                  autoCapitalize={k === 'email' || k === 'website' ? 'none' : 'words'} {...tid(`scan-field-${k}`)} />
              </View>
            ))}
          </View>
        </>
      )}
      {!scan.is_card && !scan.sensitive && scan.status === 'ready' && (
        <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 12, lineHeight: 18 }} {...tid('scan-not-card')}>
          This doesn't look like a business card. Scanning documents and other photos is coming next; for now add them from the contact's Files.
        </Text>
      )}

      {matches.length > 0 && (
        <>
          <Label text="ALREADY IN YOUR CONTACTS?" colors={colors} />
          {matches.map(m => (
            <TouchableOpacity key={m.id} onPress={() => onUpdate(m)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, borderRadius: 12, borderWidth: 1, borderColor: AMBER, backgroundColor: `${AMBER}14`, marginBottom: 8 }} {...tid(`scan-match-${m.id}`)}>
              <Ionicons name="person-circle" size={28} color={AMBER} />
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text }}>{m.name}</Text>
                <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>{[m.why.join(', '), m.company || m.phone || m.email].filter(Boolean).join(' · ')}</Text>
              </View>
              <Text style={{ fontSize: 13, fontWeight: '800', color: AMBER }}>Update</Text>
            </TouchableOpacity>
          ))}
        </>
      )}

      <View style={{ gap: 8, marginTop: 16 }}>
        {scan.is_card && (
          <TouchableOpacity onPress={onCreate} style={{ height: 48, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center' }} {...tid('scan-create-contact')}>
            <Text style={{ fontSize: 15.5, fontWeight: '800', color: '#111' }}>{matches.length ? 'Create a new contact anyway' : 'Create contact'}</Text>
          </TouchableOpacity>
        )}
        <TouchableOpacity onPress={onDiscard} style={{ height: 44, borderRadius: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid('scan-discard')}>
          <Text style={{ fontSize: 14.5, fontWeight: '700', color: colors.text }}>{scan.is_card ? 'Discard' : 'Close'}</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
};
