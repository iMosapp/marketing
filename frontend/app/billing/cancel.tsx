import React from 'react';
import { Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';

export default function BillingCancel() {
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: '#0E0E10', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
      <View style={{ maxWidth: 440, width: '100%', backgroundColor: '#17171A', borderRadius: 16, padding: 28, gap: 14, borderWidth: 1, borderColor: '#2A2A2E' }} data-testid="billing-cancel-card">
        <Ionicons name="close-circle" size={44} color="#8E8E93" />
        <Text style={{ color: '#FFF', fontSize: 22, fontWeight: '800' }} data-testid="billing-cancel-title">No payment was made</Text>
        <Text style={{ color: '#C7C7CC', fontSize: 16, lineHeight: 23 }}>Nothing was charged. Reopen the payment link whenever you are ready, or ask your I'm On Social contact to send a fresh one.</Text>
      </View>
    </SafeAreaView>
  );
}
