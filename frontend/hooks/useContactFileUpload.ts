import { useRef, useState } from 'react';
import { Platform } from 'react-native';
import api from '../services/api';

export type ScanHint = 'business_card' | 'vin' | 'trade_in' | 'id_document' | 'insurance_card' | 'credit_app' | 'receipt' | 'document' | 'photo';
type Opts = { userId?: string; contactId?: string; onSaved: (file: any) => void; onError: (msg: string) => void };
export type Picked = { name: string; contentType: string; base64: string };

const PIECE = 500_000;
const MAX_BYTES = 25 * 1024 * 1024;

const blobToB64 = (blob: Blob) => new Promise<string>((res, rej) => { const fr = new FileReader(); fr.onload = () => res(String(fr.result).split(',')[1] || ''); fr.onerror = rej; fr.readAsDataURL(blob); });

const readUri = async (uri: string, webFile?: any): Promise<string> => {
  if (Platform.OS === 'web') return blobToB64(webFile instanceof Blob ? webFile : await fetch(uri).then(r => r.blob()));
  const { File: ExpoFile } = await import('expo-file-system');
  return new ExpoFile(uri).base64();
};

export const fromImagePicker = (assets: any[]): Picked[] => assets.filter(a => a?.base64).map((a, i) => ({ name: a.fileName || `photo-${Date.now()}-${i + 1}.jpg`, contentType: a.mimeType || 'image/jpeg', base64: a.base64 }));

// Shared pickers (Files and Scan with Jessi). Each returns [] when cancelled and throws an Error with a message to show.
export const takePhoto = async (): Promise<Picked[]> => {
  const ImagePicker = await import('expo-image-picker');
  const perm = await ImagePicker.requestCameraPermissionsAsync();
  if (!perm.granted) throw new Error('Camera access is needed to scan.');
  const r = await ImagePicker.launchCameraAsync({ quality: 0.85, base64: true, exif: false });
  return r.canceled ? [] : fromImagePicker(r.assets);
};
export const choosePhotos = async (multiple = true): Promise<Picked[]> => {
  const ImagePicker = await import('expo-image-picker');
  const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ImagePicker.MediaTypeOptions.Images, quality: 0.85, base64: true, allowsMultipleSelection: multiple, selectionLimit: multiple ? 10 : 1, exif: false });
  return r.canceled ? [] : fromImagePicker(r.assets);
};
export const chooseFiles = async (multiple = true, onSkip?: (msg: string) => void): Promise<Picked[]> => {
  const DocumentPicker = await import('expo-document-picker');
  const r = await DocumentPicker.getDocumentAsync({ type: ['application/pdf', 'image/*'], multiple, copyToCacheDirectory: true });
  if (r.canceled) return [];
  const items: Picked[] = [];
  for (const a of r.assets || []) {
    if ((a.size || 0) > MAX_BYTES) { onSkip?.(`${a.name} is over 25 MB`); continue; }
    items.push({ name: a.name || 'document', contentType: a.mimeType || (a.name?.toLowerCase().endsWith('.pdf') ? 'application/pdf' : 'image/jpeg'), base64: await readUri(a.uri, (a as any).file) });
  }
  return items;
};
const errMsg = (e: any, fallback: string) => (e instanceof Error && e.message.startsWith('Camera access') ? e.message : fallback);

// Camera / photo library / Files app -> base64 pieces -> /contact-files. Jessi reads each file on the last piece.
export function useContactFileUpload({ userId, contactId, onSaved, onError }: Opts) {
  const [busy, setBusy] = useState<string | null>(null);
  const queue = useRef<Promise<void>>(Promise.resolve());

  const upload = async (p: Picked, hint?: ScanHint) => {
    if (!userId || !contactId) return;
    if (p.base64.length * 0.75 > MAX_BYTES) { onError(`${p.name} is over 25 MB`); return; }
    const total = Math.max(1, Math.ceil(p.base64.length / PIECE));
    const uploadId = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
    try {
      let last: any = null;
      for (let i = 0; i < total; i++) {
        setBusy(i === total - 1 ? `Jessi is reading ${p.name}…` : `Uploading ${p.name} ${Math.round(((i + 1) / total) * 100)}%`);
        const r = await api.post(`/contact-files/${userId}/chunk`, { upload_id: uploadId, index: i, total, data: p.base64.slice(i * PIECE, (i + 1) * PIECE), name: p.name, content_type: p.contentType, contact_id: contactId, hint }, { timeout: 180000 });
        last = r.data;
      }
      if (last?.file) onSaved(last.file);
    } catch (e: any) { onError(e?.response?.data?.detail || `Could not save ${p.name}`); }
  };
  const enqueue = (items: Picked[], hint?: ScanHint) => {
    queue.current = queue.current.then(async () => { for (const p of items) await upload(p, hint); }).finally(() => setBusy(null));
  };

  const pickCamera = async (hint?: ScanHint) => {
    try { enqueue(await takePhoto(), hint); } catch (e) { onError(errMsg(e, 'Could not open the camera.')); }
  };
  const pickLibrary = async (hint?: ScanHint) => {
    try { enqueue(await choosePhotos(true), hint); } catch (e) { onError(errMsg(e, 'Could not open your photos.')); }
  };
  const pickDocument = async (hint?: ScanHint) => {
    try { const items = await chooseFiles(true, onError); if (items.length) enqueue(items, hint); } catch (e) { onError(errMsg(e, 'Could not open that file.')); }
  };

  // "Scan" = camera on a phone, photo library on the web (no camera roll there)
  const scan = (hint: ScanHint) => (Platform.OS === 'web' ? pickLibrary(hint) : pickCamera(hint));
  return { busy, pickCamera, pickLibrary, pickDocument, scan };
}
