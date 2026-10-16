import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';

// Shown when the contact does not exist or belongs to someone else (the API answers 404): no empty editable shell.
export const ContactUnavailable = ({ colors, onBack }: { colors: any; onBack: () => void }) => (
  <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']} testID="contact-unavailable">
    <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 32 }}>
      <Ionicons name="lock-closed-outline" size={40} color="#C9A962" />
      <Text style={{ color: colors.text, fontSize: 18, fontWeight: '700', marginTop: 16, textAlign: 'center' }} testID="contact-unavailable-title">
        This contact isn't available
      </Text>
      <Text style={{ color: colors.textSecondary || colors.text, fontSize: 14, marginTop: 8, textAlign: 'center', opacity: 0.8 }}>
        It may have been removed, or it belongs to another salesperson.
      </Text>
      <TouchableOpacity onPress={onBack} testID="contact-unavailable-back-btn"
        style={{ marginTop: 24, paddingVertical: 12, paddingHorizontal: 28, borderRadius: 24, backgroundColor: '#C9A962' }}>
        <Text style={{ color: '#000', fontWeight: '700' }}>Go back</Text>
      </TouchableOpacity>
    </View>
  </SafeAreaView>
);
