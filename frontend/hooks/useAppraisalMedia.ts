import { useState } from 'react';
import { Platform } from 'react-native';
import api from '../services/api';

export type MediaRole = 'vin_photo' | 'odometer_photo' | 'exterior' | 'interior' | 'photo' | 'walkaround_video' | 'other';
export type MediaSource = 'captured_by_rep' | 'uploaded_by_rep' | 'customer_supplied';
type Picked = { name: string; contentType: string; base64: string };

const PIECE = 500_000;
const blobToB64 = (blob: Blob) => new Promise<string>((res, rej) => { const fr = new FileReader(); fr.onload = () => res(String(fr.result).split(',')[1] || ''); fr.onerror = rej; fr.readAsDataURL(blob); });
const readUri = async (uri: string, webFile?: any): Promise<string> => {
  if (Platform.OS === 'web') return blobToB64(webFile instanceof Blob ? webFile : await fetch(uri).then(r => r.blob()));
  const { File: ExpoFile } = await import('expo-file-system');
  return new ExpoFile(uri).base64();
};
const isVideo = (a: any) => a?.type === 'video' || /^video\//.test(a?.mimeType || '') || /\.(mp4|mov|m4v|webm)$/i.test(a?.fileName || a?.name || a?.uri || '');
const nameFor = (a: any, i: number) => a.fileName || a.name || (isVideo(a) ? `video-${Date.now()}-${i + 1}.${(a.uri || '').split('.').pop()?.length === 3 ? (a.uri || '').split('.').pop() : 'mp4'}` : `photo-${Date.now()}-${i + 1}.jpg`);
const typeFor = (a: any) => a.mimeType || (isVideo(a) ? (/\.mov$/i.test(a.uri || a.fileName || '') ? 'video/quicktime' : 'video/mp4') : 'image/jpeg');

// One upload path for everything on an appraisal: camera capture, library import, customer-sent files, walkaround video. Provenance travels with every piece.
export function useAppraisalMedia(appraisalId: string | undefined, onError: (m: string) => void) {
  const [busy, setBusy] = useState<string | null>(null);

  const upload = async (p: Picked, role: MediaRole, source: MediaSource, prefix = ''): Promise<any | null> => {
    if (!appraisalId) return null;
    const total = Math.max(1, Math.ceil(p.base64.length / PIECE));
    const uploadId = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
    try {
      let last: any = null;
      for (let i = 0; i < total; i++) {
        setBusy(i === total - 1 ? (role === 'vin_photo' || role === 'odometer_photo' ? 'Jessi is reading it…' : `${prefix}Saving…`) : `${prefix}Uploading ${Math.round(((i + 1) / total) * 100)}%`);
        const r = await api.post(`/appraisals/${appraisalId}/media/chunk`, { upload_id: uploadId, index: i, total, data: p.base64.slice(i * PIECE, (i + 1) * PIECE), name: p.name, content_type: p.contentType, role, source }, { timeout: 180000 });
        last = r.data;
      }
      return last?.media || null;
    } catch (e: any) { onError(e?.response?.data?.detail || 'Could not save that file'); return null; }
    finally { setBusy(null); }
  };

  const fromAssets = (assets: any[]): Picked[] => assets.filter(a => a?.base64).map((a, i) => ({ name: nameFor(a, i), contentType: typeFor(a), base64: a.base64 }));
  const pickOne = async (a: any, i: number): Promise<Picked> => ({ name: nameFor(a, i), contentType: typeFor(a), base64: a.base64 || await readUri(a.uri, a.file) });

  // Upload several picked assets one after another, with "Photo 2 of 5" progress. Videos go through the same path.
  const uploadMany = async (assets: any[], roleFor: (a: any) => MediaRole, source: MediaSource): Promise<any[]> => {
    const out: any[] = [];
    for (let i = 0; i < assets.length; i++) {
      setBusy(`Preparing ${i + 1} of ${assets.length}…`);
      try {
        const p = await pickOne(assets[i], i);
        const m = await upload(p, roleFor(assets[i]), source, assets.length > 1 ? `${i + 1} of ${assets.length} · ` : '');
        if (m) out.push(m);
      } catch { onError(`Could not read ${nameFor(assets[i], i)}`); }
    }
    setBusy(null);
    return out;
  };

  // Phone camera, still photo. Source is always captured_by_rep.
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

  // RECORD WALKAROUND: phone camera in video mode (720p keeps a 90-second walk around 40 MB).
  const recordVideo = async (): Promise<any | null> => {
    try {
      const ImagePicker = await import('expo-image-picker');
      const perm = await ImagePicker.requestCameraPermissionsAsync();
      if (!perm.granted) { onError('Camera access is needed to record.'); return null; }
      const r = await ImagePicker.launchCameraAsync({ mediaTypes: ['videos'] as any, videoMaxDuration: 180, videoQuality: (ImagePicker as any).UIImagePickerControllerQualityType?.IFrame1280x720, exif: false } as any);
      if (r.canceled || !r.assets?.[0]) return null;
      const [m] = await uploadMany([r.assets[0]], () => 'walkaround_video', 'captured_by_rep');
      return m || null;
    } catch { onError('Could not open the camera.'); return null; }
  };

  // IMPORT WALKAROUND VIDEO from the photo library (customer-sent or the rep's own earlier recording).
  const importVideo = async (source: MediaSource): Promise<any | null> => {
    try {
      const ImagePicker = await import('expo-image-picker');
      const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['videos'] as any, allowsMultipleSelection: false, videoExportPreset: (ImagePicker as any).VideoExportPreset?.H264_1280x720, exif: false } as any);
      if (r.canceled || !r.assets?.[0]) return null;
      const [m] = await uploadMany([r.assets[0]], () => 'walkaround_video', source);
      return m || null;
    } catch { onError('Could not open your videos.'); return null; }
  };

  // Photo library, single image. The caller says whether the customer sent it or the rep is importing their own shot.
  const importOne = async (role: MediaRole, source: MediaSource): Promise<any | null> => {
    try {
      const ImagePicker = await import('expo-image-picker');
      const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'] as any, quality: 0.85, base64: true, allowsMultipleSelection: false, exif: false });
      if (r.canceled) return null;
      const [p] = fromAssets(r.assets);
      return p ? upload(p, role, source) : null;
    } catch { onError('Could not open your photos.'); return null; }
  };

  // IMPORT PHOTOS: several at once (exterior / interior decided by the caller or Jessi later).
  const importPhotos = async (role: MediaRole, source: MediaSource): Promise<any[]> => {
    try {
      const ImagePicker = await import('expo-image-picker');
      const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images', 'videos'] as any, quality: 0.8, allowsMultipleSelection: true, selectionLimit: 12, orderedSelection: true, exif: false } as any);
      if (r.canceled || !r.assets?.length) return [];
      return uploadMany(r.assets, a => (isVideo(a) ? 'walkaround_video' : role), source);
    } catch { onError('Could not open your photos.'); return []; }
  };

  // Files app (iCloud Drive, downloads, AirDrop'd clips). Photos or videos.
  const importFile = async (role: MediaRole, source: MediaSource, allowVideo = false): Promise<any | null> => {
    try {
      const DocumentPicker = await import('expo-document-picker');
      const r = await DocumentPicker.getDocumentAsync({ type: allowVideo ? ['image/*', 'video/*'] : ['image/*'], multiple: false, copyToCacheDirectory: true });
      if (r.canceled || !r.assets?.[0]) return null;
      const a = r.assets[0];
      const video = isVideo(a);
      return upload({ name: a.name || (video ? 'video.mp4' : 'photo.jpg'), contentType: a.mimeType || (video ? 'video/mp4' : 'image/jpeg'), base64: await readUri(a.uri, (a as any).file) }, video ? 'walkaround_video' : role, source);
    } catch { onError('Could not open that file.'); return null; }
  };

  return { busy, capture, recordVideo, importVideo, importOne, importPhotos, importFile };
}
