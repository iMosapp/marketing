import React from 'react';
import { TouchableOpacity, Image, Text, View } from 'react-native';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { resolveUserPhotoUrl } from '../../utils/photoUrl';
import { tid } from '../scripts/shared';
import { useAccountSheet } from './accountSheetStore';

const GOLD = '#C9A962';

/** The rep's photo, top-left on every tab. Tap = account sheet (profile, VA, settings, manage). */
export const AvatarButton = ({ size = 34 }: { size?: number }) => {
  const { user, isImpersonating } = useAuthStore();
  const { colors } = useThemeStore();
  const open = useAccountSheet(s => s.open);
  const uri = resolveUserPhotoUrl(user as any);
  const initials = (user?.name || user?.email || '?').split(' ').map((p: string) => p[0]).join('').slice(0, 2).toUpperCase();
  const impersonating = isImpersonating || (user as any)?.isImpersonating === true;
  const ring = impersonating ? '#FF3B30' : 'rgba(201,169,98,0.55)';
  return (
    <TouchableOpacity onPress={open} hitSlop={10} activeOpacity={0.75} style={{ width: size, height: size }} {...tid('avatar-button')}>
      {uri ? (
        <Image source={{ uri }} style={{ width: size, height: size, borderRadius: size / 2, borderWidth: impersonating ? 2.5 : 1.5, borderColor: ring }} />
      ) : (
        <View style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: 'rgba(201,169,98,0.16)', borderWidth: impersonating ? 2.5 : 1.5, borderColor: ring, alignItems: 'center', justifyContent: 'center' }}>
          <Text style={{ fontSize: size * 0.36, fontWeight: '800', color: GOLD }}>{initials}</Text>
        </View>
      )}
      <View style={{ position: 'absolute', right: -1, bottom: -1, width: 12, height: 12, borderRadius: 6, backgroundColor: colors.bg, alignItems: 'center', justifyContent: 'center' }} {...tid(impersonating ? 'avatar-impersonating-dot' : 'avatar-dot')}>
        <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: impersonating ? '#FF3B30' : GOLD }} />
      </View>
    </TouchableOpacity>
  );
};
