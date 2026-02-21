import { Platform, Alert } from 'react-native';

type AlertButton = {
  text: string;
  onPress?: () => void;
  style?: 'default' | 'cancel' | 'destructive';
};

/**
 * Cross-platform alert that works on both native and web
 * On web, uses window.confirm/alert which properly handles user interaction
 */
export function showAlert(
  title: string,
  message?: string,
  buttons?: AlertButton[]
) {
  if (Platform.OS === 'web') {
    // For web, we use window.confirm for two-button alerts and window.alert for single button
    if (buttons && buttons.length === 2) {
      // Find OK/confirm and Cancel buttons
      const cancelBtn = buttons.find(b => b.style === 'cancel' || b.text.toLowerCase() === 'cancel');
      const confirmBtn = buttons.find(b => b !== cancelBtn);
      
      const result = window.confirm(`${title}${message ? '\n\n' + message : ''}`);
      if (result && confirmBtn?.onPress) {
        confirmBtn.onPress();
      } else if (!result && cancelBtn?.onPress) {
        cancelBtn.onPress();
      }
    } else if (buttons && buttons.length === 1) {
      window.alert(`${title}${message ? '\n\n' + message : ''}`);
      if (buttons[0].onPress) {
        buttons[0].onPress();
      }
    } else {
      window.alert(`${title}${message ? '\n\n' + message : ''}`);
      // Call onPress for the first button if exists
      if (buttons && buttons[0]?.onPress) {
        buttons[0].onPress();
      }
    }
  } else {
    // Native - use React Native Alert
    Alert.alert(title, message, buttons);
  }
}

/**
 * Simple alert with just OK button - works on all platforms
 */
export function showSimpleAlert(title: string, message?: string, onOk?: () => void) {
  showAlert(title, message, [{ text: 'OK', onPress: onOk }]);
}

/**
 * Confirmation dialog - works on all platforms
 */
export function showConfirm(
  title: string,
  message: string,
  onConfirm: () => void,
  onCancel?: () => void,
  confirmText: string = 'OK',
  cancelText: string = 'Cancel'
) {
  showAlert(title, message, [
    { text: cancelText, style: 'cancel', onPress: onCancel },
    { text: confirmText, onPress: onConfirm },
  ]);
}
