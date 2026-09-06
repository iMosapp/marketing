import AsyncStorage from '@react-native-async-storage/async-storage';
import { Platform } from 'react-native';
import * as Application from 'expo-application';
import api from './api';

const KEY_ID = 'imos_install_id';
const KEY_SENT = 'imos_install_first_open_sent';
const KEY_CLAIMED = 'imos_install_claimed_for';

async function installId(): Promise<string> {
  let id = await AsyncStorage.getItem(KEY_ID);
  if (!id) {
    id = `${Platform.OS}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
    await AsyncStorage.setItem(KEY_ID, id);
  }
  return id;
}

// Once per device: lets the backend match this install to a recent share-link tap.
export async function reportFirstOpen(): Promise<void> {
  if (Platform.OS === 'web') return;
  try {
    if (await AsyncStorage.getItem(KEY_SENT)) return;
    const id = await installId();
    await api.post('/app-installs/first-open', {
      install_id: id,
      platform: Platform.OS,
      os_version: String(Platform.Version),
      app_version: Application.nativeApplicationVersion,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      locale: Intl.DateTimeFormat().resolvedOptions().locale,
    });
    await AsyncStorage.setItem(KEY_SENT, '1');
  } catch {}
}

// After sign-in: attach the signed-in user to the install so the link owner learns who joined.
export async function claimInstall(userId: string): Promise<void> {
  if (Platform.OS === 'web' || !userId) return;
  try {
    if ((await AsyncStorage.getItem(KEY_CLAIMED)) === userId) return;
    const id = await AsyncStorage.getItem(KEY_ID);
    if (!id) return;
    await api.post('/app-installs/claim', { install_id: id });
    await AsyncStorage.setItem(KEY_CLAIMED, userId);
  } catch {}
}
