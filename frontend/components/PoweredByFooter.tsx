import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Linking, Platform } from 'react-native';
import { BRAND } from '../config/brand';

import { useThemeStore } from '../store/themeStore';
interface Props {
  light?: boolean;
}

export function PoweredByFooter({ light }: Props) {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const handlePress = () => {
    if (Platform.OS === 'web') {
      window.open(BRAND.url, '_blank');
    } else {
      Linking.openURL(BRAND.url);
    }
  };

  return (
    <View style={styles.container}>
      <TouchableOpacity onPress={handlePress} data-testid="powered-by-footer">
        <Text style={[styles.text, light && styles.textLight]}>
          {BRAND.poweredByText}
        </Text>
      </TouchableOpacity>
    </View>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: { paddingVertical: 20, alignItems: 'center' },
  text: { fontSize: 11, color: colors.borderLight, letterSpacing: 0.5 },
  textLight: { color: colors.textSecondary },
});
