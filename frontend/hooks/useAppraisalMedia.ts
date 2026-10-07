import { useState } from 'react';
import { Platform } from 'react-native';
import api from '../services/api';

export type MediaRole = 'vin_photo' | 'odometer_photo' | 'exterior' | 'interior' | 'walkaround_video' | 'other';
export type MediaSource = 'captured_by_rep' | 'uploaded_by_rep' | 'customer_supplied';
type Picked = { name: string; contentType: string; base64: string };

const PIECE = 500_000;
const blobToB64 = (blob: Blob) => new Promise<string>((res, rej) => { const fr = new FileReader(); fr.onload = () => res(String(fr.result).split(',')[1] || ''); fr.onerror = rej; fr.readAsDataURL(blob); });
const readUri = async (uri: string, webFile?: any): Promise<string> => {
  if (Platform.OS === 'web') return blobToB64(webFile instanceof Blob ? webFile : await fetch(uri).then(r => r.blob()));
  const { File: ExpoFile } = await import('expo-file-system');
  return new ExpoFile(uri).base64();
};

// One upload path for everything on an appraisal: camera capture, library import, customer-sent files. Provenance travels with every piece.
export function useAppraisalMedia(appraisalId: string | undefined, onError: (m: string) => void) {
  const [busy, setBusy] = useState<string | null>(null);

  const upload = async (p: Picked, role: MediaRole, source: MediaSource): Promise<any | null> => {
    if (!appraisalId) return null;
    const total = Math.max(1, Math.ceil(p.base64.length / PIECE));
    const uploadId = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
    try {
      let last: any = null;
      for (let i = 0; i < total; i++) {
        setBusy(i === total - 1 ? (role === 'vin_photo' || role === 'odometer_photo' ? 'Jessi is reading it…' : 'Saving…') : `Uploading ${Math.round(((i + 1) / total) * 100)}%`);
        const r = await api.post(`/appraisals/${appraisalId}/media/chunk`, { upload_id: uploadId, index: i, total, data: p.base64.slice(i * PIECE, (i + 1) * PIECE), name: p.name, content_type: p.contentType, role, source }, { timeout: 180000 });
        last = r.data;
      }
      return last?.media || null;
    } catch (e: any) { onError(e?.response?.data?.detail || 'Could not save that file'); return null; }
    finally { setBusy(null); }
  };

  const fromAssets = (assets: any[]): Picked[] => assets.filter(a => a?.base64).map((a, i) => ({ name: a.fileName || `photo-${Date.now()}-${i + 1}.jpg`, contentType: a.mimeType || 'image/jpeg', base64: a.base64 }));

  // Phone camera. Source is always captured_by_rep.
  const capture = async (role: MediaRole): Promise<any | null> => {
    try {
      const ImagePicker = await import('expo-image-picker');
      const perm = await ImagePicker.requestCameraPermissionsAsync();
      if (!perm.granted) { onError('Camera access is needed to scan.'); return null; }
      const r = await ImagePicker.launchCameraAsync({ quality: 0.85, base64: true, exif: false });
      if (r.canceled) return null;
      const [p] = fromAssets(r.assets);
      return p ? upload(p, role, 'captured_by_rep') : null;
    } catch { onError('Could not open the camera.'); return null; }
  };

  // Photo library / Files. The caller says whether the customer sent it or the rep is importing their own shot.
  const importOne = async (role: MediaRole, source: MediaSource): Promise<any | null> => {
    try {
      const ImagePicker = await import('expo-image-picker');
      const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ImagePicker.MediaTypeOptions.Images, quality: 0.85, base64: true, allowsMultipleSelection: false, exif: false });
      if (r.canceled) return null;
      const [p] = fromAssets(r.assets);
      return p ? upload(p, role, source) : null;
    } catch { onError('Could not open your photos.'); return null; }
  };

  const importFile = async (role: MediaRole, source: MediaSource): Promise<any | null> => {
    try {
      const DocumentPicker = await import('expo-document-picker');
      const r = await DocumentPicker.getDocumentAsync({ type: ['image/*'], multiple: false, copyToCacheDirectory: true });
      if (r.canceled || !r.assets?.[0]) return null;
      const a = r.assets[0];
      return upload({ name: a.name || 'photo', contentType: a.mimeType || 'image/jpeg', base64: await readUri(a.uri, (a as any).file) }, role, source);
    } catch { onError('Could not open that file.'); return null; }
  };

  return { busy, capture, importOne, importFile };
}
