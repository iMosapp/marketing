/**
 * ComposerCollapsed — the resting state of the composer: one 44pt "Message Forest…" bar plus a call button.
 * Tapping it opens the full ComposerBar (modes, toolbar, AI suggestions). Keeps the page readable.
 */
import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

export default function ComposerCollapsed({ s, colors, firstName, draft, onOpen, onCall }: any) {
  return (
    <View style={[s.composerContainer, { paddingTop: 8, paddingBottom: 14 }]} testID="contact-composer-collapsed" dataSet={{ testid: 'contact-composer-collapsed' } as any}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
        <TouchableOpacity
          onPress={onOpen}
          activeOpacity={0.8}
          style={{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: 10, height: 44, paddingHorizontal: 14, borderRadius: 22, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border }}
          testID="composer-open-btn" dataSet={{ testid: 'composer-open-btn' } as any}
        >
          <Ionicons name="chatbubble-ellipses-outline" size={18} color="#34C759" />
          <Text style={{ flex: 1, fontSize: 15, color: draft ? colors.text : colors.textTertiary }} numberOfLines={1}>
            {draft || `Message ${firstName || 'them'}…`}
          </Text>
          <Ionicons name="sparkles" size={16} color="#AF52DE" />
        </TouchableOpacity>
        <TouchableOpacity onPress={onCall} activeOpacity={0.8} style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: '#32ADE620', alignItems: 'center', justifyContent: 'center' }} testID="composer-collapsed-call-btn" dataSet={{ testid: 'composer-collapsed-call-btn' } as any}>
          <Ionicons name="call" size={18} color="#32ADE6" />
        </TouchableOpacity>
      </View>
    </View>
  );
}
