import React from 'react';
import { View, Text, TouchableOpacity, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, tid } from '../inbox/ownership';
import { BigButton } from './shared';
import type { useAppraisalMedia, MediaSource } from '../../hooks/useAppraisalMedia';

type Props = { colors: any; mode: string; media: ReturnType<typeof useAppraisalMedia>; source: MediaSource; onSource: (s: MediaSource) => void; onDone: () => void; disabled?: boolean };

// RECORD WALKAROUND · TAKE PHOTOS (vehicle here) and IMPORT WALKAROUND VIDEO · IMPORT PHOTOS (customer sent). Both sets are always available so a rep
// can add tire shots to a customer's video. The source selector decides how imported files are tagged.
export const InspectionCapture = ({ colors, mode, media, source, onSource, onDone, disabled }: Props) => {
  const here = mode === 'vehicle_here';
  const native = Platform.OS !== 'web';
  const after = (p: Promise<any>) => p.then(r => { if (r && (!Array.isArray(r) || r.length)) onDone(); });
  const importLabel = source === 'customer_supplied' ? 'customer' : 'my';
  const live = native ? (
    <>
      <BigButton colors={colors} icon="videocam" label="Record walkaround" sub="Slow lap around the car, phone in landscape" onPress={() => after(media.recordVideo())} primary={here} disabled={disabled} testId="inspect-record-video" />
      <BigButton colors={colors} icon="camera" label="Take photos" sub="Tires, windshield, seats, anything you want on the record" onPress={() => after(media.capture('photo'))} primary={false} disabled={disabled} testId="inspect-take-photo" />
    </>
  ) : null;
  const imports = (
    <>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }} {...tid('inspect-source-picker')}>
        <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6 }}>IMPORTING</Text>
        {([['customer_supplied', 'Customer sent it'], ['uploaded_by_rep', 'My library']] as [MediaSource, string][]).map(([s, l]) => (
          <TouchableOpacity key={s} onPress={() => onSource(s)} style={{ paddingHorizontal: 10, paddingVertical: 6, borderRadius: 10, backgroundColor: source === s ? GOLD : colors.card, borderWidth: 1, borderColor: source === s ? GOLD : colors.border }} {...tid(`inspect-source-${s}`)}>
            <Text style={{ fontSize: 12, fontWeight: '800', color: source === s ? '#0B0B0D' : colors.text }}>{l}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <BigButton colors={colors} icon="film-outline" label="Import walkaround video" sub={`From ${importLabel} photo library`} onPress={() => after(media.importVideo(source))} primary={!here || !native} disabled={disabled} testId="inspect-import-video" />
      <BigButton colors={colors} icon="images-outline" label="Import photos" sub="Pick several at once · videos too" onPress={() => after(media.importPhotos('photo', source))} primary={false} disabled={disabled} testId="inspect-import-photos" />
      <TouchableOpacity onPress={() => after(media.importFile('photo', source, true))} disabled={disabled} style={{ alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 6 }} {...tid('inspect-import-file')}>
        <Ionicons name="folder-open-outline" size={14} color={GOLD} /><Text style={{ fontSize: 13, fontWeight: '700', color: GOLD }}>From Files (AirDrop, iCloud, downloads)</Text>
      </TouchableOpacity>
    </>
  );
  return <View style={{ gap: 10 }} {...tid('inspect-capture')}>{here ? <>{live}{imports}</> : <>{imports}{live}</>}</View>;
};
