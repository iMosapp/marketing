import React, { useState } from 'react';
import { View, Text, Modal, TouchableOpacity, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useThemeStore } from '../../store/themeStore';

const GOLD = '#C9A962';

export interface FabAction {
  key: string;
  icon: string;
  label: string;
  color: string;
  onPress: () => void;
}

export function QuickActionsFab({ actions }: { actions: FabAction[] }) {
  const { colors } = useThemeStore();
  const [open, setOpen] = useState(false);

  const run = (a: FabAction) => {
    setOpen(false);
    setTimeout(a.onPress, Platform.OS === 'web' ? 50 : 250);
  };

  return (
    <>
      <TouchableOpacity
        onPress={() => setOpen(true)}
        activeOpacity={0.85}
        style={{
          position: 'absolute',
          bottom: 22,
          right: 18,
          width: 56,
          height: 56,
          borderRadius: 28,
          backgroundColor: GOLD,
          alignItems: 'center',
          justifyContent: 'center',
          shadowColor: '#000',
          shadowOpacity: 0.4,
          shadowRadius: 10,
          shadowOffset: { width: 0, height: 4 },
          elevation: 8,
          zIndex: 100,
        }}
        testID="home-fab"
        dataSet={{ testid: 'home-fab' } as any}
      >
        <Ionicons name="add" size={30} color="#000" />
      </TouchableOpacity>

      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <TouchableOpacity
          style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.72)' }}
          activeOpacity={1}
          onPress={() => setOpen(false)}
          testID="home-fab-backdrop"
          dataSet={{ testid: 'home-fab-backdrop' } as any}
        >
          <View style={{ position: 'absolute', bottom: 92, right: 18, alignItems: 'flex-end', gap: 12 }}>
            {actions.map((a) => (
              <TouchableOpacity
                key={a.key}
                onPress={() => run(a)}
                activeOpacity={0.8}
                style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}
                testID={`fab-action-${a.key}`}
                dataSet={{ testid: `fab-action-${a.key}` } as any}
              >
                <View style={{
                  backgroundColor: colors.card,
                  borderRadius: 12,
                  paddingHorizontal: 14,
                  paddingVertical: 8,
                }}>
                  <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 15, fontWeight: '700', color: colors.text }}>
                    {a.label}
                  </Text>
                </View>
                <View style={{
                  width: 46, height: 46, borderRadius: 23,
                  backgroundColor: a.color,
                  alignItems: 'center', justifyContent: 'center',
                }}>
                  <Ionicons name={a.icon as any} size={21} color="#fff" />
                </View>
              </TouchableOpacity>
            ))}
            <TouchableOpacity
              onPress={() => setOpen(false)}
              style={{
                width: 56, height: 56, borderRadius: 28,
                backgroundColor: GOLD,
                alignItems: 'center', justifyContent: 'center',
                marginTop: 2,
              }}
              testID="home-fab-close"
              dataSet={{ testid: 'home-fab-close' } as any}
            >
              <Ionicons name="close" size={28} color="#000" />
            </TouchableOpacity>
          </View>
        </TouchableOpacity>
      </Modal>
    </>
  );
}
