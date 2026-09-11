import React, { useRef } from 'react';
import { InputAccessoryView, Keyboard, Platform, Text, TouchableOpacity, View } from 'react-native';
import { useThemeStore } from '../../store/themeStore';

let seq = 0;

// Injected around every multiline <TextInput> by babel-plugin-keyboard.js: iOS gets a "Done" bar above the keyboard.
export function KeyboardDoneWrap({ render }: { render: (id: string | undefined) => React.ReactNode }) {
  const id = useRef(`kb-done-${++seq}`).current;
  const mode = useThemeStore((s) => s.mode);
  if (Platform.OS !== 'ios') return <>{render(undefined)}</>;
  const dark = mode !== 'light';
  return (
    <>
      {render(id)}
      <InputAccessoryView nativeID={id} backgroundColor={dark ? '#1C1C1E' : '#F2F2F7'}>
        <View style={{ flexDirection: 'row', justifyContent: 'flex-end', alignItems: 'center', paddingHorizontal: 12, height: 40, borderTopWidth: 0.5, borderTopColor: dark ? '#3A3A3C' : '#C6C6C8' }}>
          <TouchableOpacity onPress={() => Keyboard.dismiss()} hitSlop={10} style={{ paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8 }} testID="keyboard-done-btn">
            <Text style={{ fontSize: 16, fontWeight: '700', color: '#C9A962' }}>Done</Text>
          </TouchableOpacity>
        </View>
      </InputAccessoryView>
    </>
  );
}
