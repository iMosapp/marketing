import { Platform } from 'react-native';

// Which bundle is this device actually running? Shown under the Tools footer so "I updated but see the old thing" is a 10-second check.
export const buildStamp = (): string => {
  if (Platform.OS === 'web') return '';
  try {
    const Updates = require('expo-updates');
    if (Updates.isEmbeddedLaunch || !Updates.updateId) return 'store build (no OTA update applied yet)';
    const when = Updates.createdAt ? new Date(Updates.createdAt).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '';
    return `update ${String(Updates.updateId).slice(0, 8)}${when ? ` · ${when}` : ''}`;
  } catch {
    return '';
  }
};
