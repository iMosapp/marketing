import React from 'react';
import { KeyboardAvoidingView, Platform } from 'react-native';

// Injected around every <Modal>'s children by babel-plugin-modal-kav.js: on iOS the sheet slides up with the keyboard so
// no field is ever hidden while typing. Android resizes the window itself and web has no soft keyboard, so they get the children as-is.
export function ModalKeyboardWrap({ children }: { children: React.ReactNode }) {
  if (Platform.OS !== 'ios') return <>{children}</>;
  return <KeyboardAvoidingView style={{ flex: 1 }} behavior="padding">{children}</KeyboardAvoidingView>;
}
