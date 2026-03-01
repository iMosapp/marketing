import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Linking, Platform } from 'react-native';
import { BRAND } from '../config/brand';

interface Props {
  light?: boolean;
}

export function PoweredByFooter({ light }: Props) {
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

const styles = StyleSheet.create({
  container: { paddingVertical: 20, alignItems: 'center' },
  text: { fontSize: 11, color: '#3A3A3C', letterSpacing: 0.5 },
  textLight: { color: '#8E8E93' },
});
