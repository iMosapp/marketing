/**
 * Biometric Authentication Utility
 * Handles Face ID / Touch ID / Fingerprint authentication
 */
import * as LocalAuthentication from 'expo-local-authentication';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

const BIOMETRIC_CREDENTIALS_KEY = 'mvpline_biometric_credentials';
const BIOMETRIC_ENABLED_KEY = 'mvpline_biometric_enabled';

export interface BiometricCredentials {
  email: string;
  password: string;
}

export interface BiometricStatus {
  isAvailable: boolean;
  isEnabled: boolean;
  biometricType: 'faceid' | 'fingerprint' | 'iris' | 'none';
  biometricLabel: string;
}

/**
 * Check if device supports biometric authentication
 */
export async function checkBiometricSupport(): Promise<BiometricStatus> {
  try {
    // Check if hardware is available
    const hasHardware = await LocalAuthentication.hasHardwareAsync();
    if (!hasHardware) {
      return {
        isAvailable: false,
        isEnabled: false,
        biometricType: 'none',
        biometricLabel: 'Biometric login not available',
      };
    }

    // Check if biometrics are enrolled
    const isEnrolled = await LocalAuthentication.isEnrolledAsync();
    if (!isEnrolled) {
      return {
        isAvailable: false,
        isEnabled: false,
        biometricType: 'none',
        biometricLabel: 'No biometrics enrolled on device',
      };
    }

    // Get supported authentication types
    const supportedTypes = await LocalAuthentication.supportedAuthenticationTypesAsync();
    
    let biometricType: 'faceid' | 'fingerprint' | 'iris' | 'none' = 'none';
    let biometricLabel = 'Biometric Login';

    if (supportedTypes.includes(LocalAuthentication.AuthenticationType.FACIAL_RECOGNITION)) {
      biometricType = 'faceid';
      biometricLabel = Platform.OS === 'ios' ? 'Face ID' : 'Face Recognition';
    } else if (supportedTypes.includes(LocalAuthentication.AuthenticationType.FINGERPRINT)) {
      biometricType = 'fingerprint';
      biometricLabel = Platform.OS === 'ios' ? 'Touch ID' : 'Fingerprint';
    } else if (supportedTypes.includes(LocalAuthentication.AuthenticationType.IRIS)) {
      biometricType = 'iris';
      biometricLabel = 'Iris Recognition';
    }

    // Check if user has enabled biometric login
    const isEnabled = await isBiometricEnabled();

    return {
      isAvailable: true,
      isEnabled,
      biometricType,
      biometricLabel,
    };
  } catch (error) {
    console.error('Error checking biometric support:', error);
    return {
      isAvailable: false,
      isEnabled: false,
      biometricType: 'none',
      biometricLabel: 'Biometric check failed',
    };
  }
}

/**
 * Check if biometric login is enabled for this user
 */
export async function isBiometricEnabled(): Promise<boolean> {
  try {
    const enabled = await SecureStore.getItemAsync(BIOMETRIC_ENABLED_KEY);
    return enabled === 'true';
  } catch (error) {
    console.error('Error checking biometric enabled status:', error);
    return false;
  }
}

/**
 * Enable biometric login and store credentials securely
 */
export async function enableBiometricLogin(credentials: BiometricCredentials): Promise<boolean> {
  try {
    // First authenticate to confirm user identity
    const authResult = await authenticateWithBiometric('Confirm your identity to enable biometric login');
    
    if (!authResult.success) {
      return false;
    }

    // Store credentials securely
    await SecureStore.setItemAsync(
      BIOMETRIC_CREDENTIALS_KEY,
      JSON.stringify(credentials)
    );
    
    // Mark biometric as enabled
    await SecureStore.setItemAsync(BIOMETRIC_ENABLED_KEY, 'true');
    
    return true;
  } catch (error) {
    console.error('Error enabling biometric login:', error);
    return false;
  }
}

/**
 * Disable biometric login and remove stored credentials
 */
export async function disableBiometricLogin(): Promise<boolean> {
  try {
    await SecureStore.deleteItemAsync(BIOMETRIC_CREDENTIALS_KEY);
    await SecureStore.setItemAsync(BIOMETRIC_ENABLED_KEY, 'false');
    return true;
  } catch (error) {
    console.error('Error disabling biometric login:', error);
    return false;
  }
}

/**
 * Authenticate using biometric and return stored credentials
 */
export async function authenticateWithBiometric(
  promptMessage?: string
): Promise<{ success: boolean; credentials?: BiometricCredentials; error?: string }> {
  try {
    const result = await LocalAuthentication.authenticateAsync({
      promptMessage: promptMessage || 'Login with biometrics',
      cancelLabel: 'Cancel',
      disableDeviceFallback: false, // Allow PIN/password fallback
      fallbackLabel: 'Use Password',
    });

    if (!result.success) {
      return {
        success: false,
        error: result.error || 'Authentication failed',
      };
    }

    // Get stored credentials
    const storedCredentials = await SecureStore.getItemAsync(BIOMETRIC_CREDENTIALS_KEY);
    
    if (!storedCredentials) {
      return {
        success: false,
        error: 'No stored credentials found',
      };
    }

    const credentials: BiometricCredentials = JSON.parse(storedCredentials);
    
    return {
      success: true,
      credentials,
    };
  } catch (error) {
    console.error('Error during biometric authentication:', error);
    return {
      success: false,
      error: 'Biometric authentication failed',
    };
  }
}

/**
 * Get the appropriate icon name for the biometric type
 */
export function getBiometricIcon(biometricType: string): string {
  switch (biometricType) {
    case 'faceid':
      return 'scan-outline'; // Face scan icon
    case 'fingerprint':
      return 'finger-print-outline';
    case 'iris':
      return 'eye-outline';
    default:
      return 'lock-closed-outline';
  }
}

/**
 * Clear all biometric data (for logout)
 */
export async function clearBiometricData(): Promise<void> {
  try {
    await SecureStore.deleteItemAsync(BIOMETRIC_CREDENTIALS_KEY);
    // Note: We don't delete BIOMETRIC_ENABLED_KEY so user preference persists
  } catch (error) {
    console.error('Error clearing biometric data:', error);
  }
}
