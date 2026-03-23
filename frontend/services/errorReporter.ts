/**
 * Error Reporter — sends crash/error data to the backend for production diagnostics.
 * 
 * Usage:
 *   import { reportError, initGlobalErrorHandlers } from './errorReporter';
 *   
 *   // Call once at app startup:
 *   initGlobalErrorHandlers();
 *   
 *   // Or report manually:
 *   reportError({ error_message: '...', error_type: 'api_error', page: '/contacts' });
 */
import { Platform } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

interface ErrorReport {
  error_message: string;
  error_stack?: string;
  component_stack?: string;
  error_type: 'render_crash' | 'unhandled_rejection' | 'api_error' | 'js_error';
  page?: string;
  extra?: Record<string, any>;
}

// Debounce: don't flood the server with duplicate errors
const _recentErrors = new Set<string>();

function _dedupeKey(msg: string): string {
  return msg.slice(0, 120);
}

async function _getUserInfo() {
  try {
    const userStr = await AsyncStorage.getItem('user');
    if (userStr) {
      const user = JSON.parse(userStr);
      return { user_id: user._id, user_email: user.email, user_name: user.name };
    }
  } catch {}
  return {};
}

/**
 * Send an error report to POST /api/errors/report.
 * Fires and forgets — never throws.
 */
export async function reportError(report: ErrorReport) {
  try {
    const key = _dedupeKey(report.error_message);
    if (_recentErrors.has(key)) return; // skip duplicate within session
    _recentErrors.add(key);
    // Auto-clear after 60s so repeated errors eventually get re-reported
    setTimeout(() => _recentErrors.delete(key), 60000);

    const userInfo = await _getUserInfo();

    const payload = {
      ...report,
      ...userInfo,
      platform: Platform.OS,
      page: report.page || (typeof window !== 'undefined' ? window.location?.pathname : 'native'),
    };

    // Use fetch directly (not axios) to avoid circular issues with api interceptors
    const baseUrl = Platform.OS === 'web' ? '' : (process.env.EXPO_PUBLIC_BACKEND_URL || '');
    await fetch(`${baseUrl}/api/errors/report`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  } catch {
    // Never throw from the error reporter itself
  }
}

/**
 * Initialize global error handlers for unhandled JS errors and promise rejections.
 * Call once at app startup (e.g., in _layout.tsx).
 */
export function initGlobalErrorHandlers() {
  if (Platform.OS === 'web' && typeof window !== 'undefined') {
    // Unhandled JS errors
    window.addEventListener('error', (event) => {
      reportError({
        error_message: event.message || 'Unknown JS error',
        error_stack: event.error?.stack || `${event.filename}:${event.lineno}:${event.colno}`,
        error_type: 'js_error',
      });
    });

    // Unhandled promise rejections
    window.addEventListener('unhandledrejection', (event) => {
      const reason = event.reason;
      reportError({
        error_message: reason?.message || String(reason) || 'Unhandled promise rejection',
        error_stack: reason?.stack || '',
        error_type: 'unhandled_rejection',
      });
    });
  }
}
