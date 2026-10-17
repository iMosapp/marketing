import React from 'react';
import { View, Text, TouchableOpacity, Modal, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { SheetGrabber } from '../common/SheetGrabber';
import { GOLD, tid } from '../inbox/ownership';
import type { ScanHint } from '../../hooks/useContactFileUpload';

type Up = { pickCamera: () => void; pickLibrary: () => void; pickDocument: () => void; scan: (h: ScanHint) => void };
type Props = { visible: boolean; onClose: () => void; colors: any; up: Up };

const SCANS: { hint: ScanHint; label: string; sub: string; icon: any }[] = [
  { hint: 'business_card', label: 'Business card', sub: 'Name, company, phone, email, address', icon: 'card-outline' },
  { hint: 'vin', label: 'VIN / odometer', sub: 'VIN, year, make, model, mileage', icon: 'barcode-outline' },
  { hint: 'trade_in', label: 'Trade-in', sub: 'Vehicle, condition, plate', icon: 'car-sport-outline' },
  { hint: 'document', label: 'Quote, invoice or screenshot', sub: 'Key dates and reminder ideas', icon: 'document-text-outline' },
];

// The one place to add something to a contact's files: pick a source, or pick a scan so Jessi knows what to pull out.
export const AddFileSheet = ({ visible, onClose, colors, up }: Props) => {
  const run = (fn: () => void) => { onClose(); setTimeout(fn, Platform.OS === 'web' ? 0 : 350); };
  const Row = ({ icon, label, sub, onPress, testId }: { icon: any; label: string; sub: string; onPress: () => void; testId: string }) => (
    <TouchableOpacity onPress={() => run(onPress)} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 11 }} {...tid(testId)}>
      <View style={{ width: 38, height: 38, borderRadius: 19, backgroundColor: GOLD + '1F', alignItems: 'center', justifyContent: 'center' }}><Ionicons name={icon} size={18} color={GOLD} /></View>
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text }}>{label}</Text>
        <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 1 }}>{sub}</Text>
      </View>
      <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
    </TouchableOpacity>
  );
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <TouchableOpacity activeOpacity={1} onPress={onClose} style={{ flex: 1, backgroundColor: '#0008' }} {...tid('add-file-backdrop')} />
      <View style={{ backgroundColor: colors.bg, borderTopLeftRadius: 22, borderTopRightRadius: 22, paddingHorizontal: 18, paddingBottom: 28 }} {...tid('add-file-sheet')}>
        <SheetGrabber onClose={onClose} color={colors.border} />
        <Text style={{ fontSize: 17, fontWeight: '800', color: colors.text, marginTop: 4 }}>Add to files</Text>
        <Text style={{ fontSize: 12.5, color: colors.textSecondary, marginTop: 2, marginBottom: 6 }}>Jessi reads whatever you add so you can ask her about it later.</Text>
        {Platform.OS !== 'web' ? <Row icon="camera" label="Take a photo" sub="Snap it now" onPress={up.pickCamera} testId="add-file-camera" /> : null}
        <Row icon="images-outline" label="Choose photos" sub={Platform.OS === 'web' ? 'Pictures from this computer' : 'From your photo library'} onPress={up.pickLibrary} testId="add-file-library" />
        <Row icon="document-attach-outline" label="File / PDF" sub="Quotes, contracts, statements" onPress={up.pickDocument} testId="add-file-document" />
        <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8, marginTop: 10, marginBottom: 2 }}>JESSI SCANS</Text>
        {SCANS.map(s => <Row key={s.hint} icon={s.icon} label={s.label} sub={s.sub} onPress={() => up.scan(s.hint)} testId={`add-file-scan-${s.hint}`} />)}
      </View>
    </Modal>
  );
};
