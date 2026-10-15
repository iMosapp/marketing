// Every place that opens the phone's own Messages app asks the server first (POST /messages/native-authorize) and fails closed.
import { Platform, Linking } from 'react-native';
import api from './api';
import { showSimpleAlert } from './alert';

export const NATIVE_CHECK_FAILED = "Couldn't check this contact's texting status. Try again.";

export type NativeTarget = { phone?: string; contactId?: string; purpose?: string; systemKind?: string; pendingSendId?: string };
export type NativeAuth = { ok: true; phones: string[] } | { ok: false; reason: 'refused' | 'invalid' | 'unavailable'; message: string };

async function authorizeOne(t: NativeTarget): Promise<string> {
  const res = await api.post('/messages/native-authorize', {
    phone: t.phone || undefined, contact_id: t.contactId || undefined, purpose: t.purpose || undefined,
    system_kind: t.systemKind || undefined, pending_send_id: t.pendingSendId || undefined,
  }, { timeout: 15000 });
  if (!res.data?.authorized || !res.data?.phone) throw new Error('native-authorize: no authorization');
  return res.data.phone;
}

export async function authorizeNativeMessages(targets: NativeTarget[]): Promise<NativeAuth> {
  try {
    const phones: string[] = [];
    for (const t of targets) phones.push(await authorizeOne(t));
    return { ok: true, phones };
  } catch (err: any) {
    const status = err?.response?.status;
    if (err?.compliance) {
      const message = err.complianceMessage || 'This text was not sent.';
      if (!err.consentDeclined) showSimpleAlert('Text not sent', message);  // otherwise the consent / STOP sheet already explained it
      return { ok: false, reason: 'refused', message };
    }
    if (status === 403 && err.response.data?.reason === 'billing_locked') {
      return { ok: false, reason: 'refused', message: 'Texting is paused for this account.' };
    }
    if (status === 400 || status === 403 || status === 404) {
      const d = err.response.data?.detail;
      const message = typeof d === 'string' && d ? d : 'This contact can\'t be texted from here.';
      showSimpleAlert('Text not sent', message);
      return { ok: false, reason: 'invalid', message };
    }
    showSimpleAlert(NATIVE_CHECK_FAILED);
    return { ok: false, reason: 'unavailable', message: NATIVE_CHECK_FAILED };
  }
}

const isIos = () => Platform.OS === 'ios'
  || (Platform.OS === 'web' && typeof navigator !== 'undefined' && /iphone|ipad|ipod/i.test(navigator.userAgent || ''));

export function smsUrl(phones: string[], body?: string): string {
  const to = phones.join(',');
  return body ? `sms:${to}${isIos() ? '&' : '?'}body=${encodeURIComponent(body)}` : `sms:${to}`;
}

export async function openAuthorizedMessages(phones: string[], body?: string): Promise<boolean> {
  const url = smsUrl(phones, body);
  if (Platform.OS === 'web' && typeof window !== 'undefined') {
    window.location.href = url;
    return true;
  }
  try { await Linking.openURL(url); return true; } catch { showSimpleAlert('Could not open Messages'); return false; }
}

export async function openNativeMessages(targets: NativeTarget | NativeTarget[], body?: string): Promise<boolean> {
  const auth = await authorizeNativeMessages(Array.isArray(targets) ? targets : [targets]);
  return auth.ok ? openAuthorizedMessages(auth.phones, body) : false;
}
