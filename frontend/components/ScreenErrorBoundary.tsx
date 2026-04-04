/**
 * ScreenErrorBoundary.tsx
 * 
 * Reusable error boundary for screens.
 * Catches React render errors and shows a recovery UI
 * instead of a full white screen / "Something went wrong".
 * 
 * Usage:
 *   <ScreenErrorBoundary screenName="Contact Detail">
 *     <ContactDetailScreen />
 *   </ScreenErrorBoundary>
 */

import React, { Component, ErrorInfo, ReactNode } from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

interface Props {
  children: ReactNode;
  screenName?: string;
  onReset?: () => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ScreenErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({ errorInfo });
    // Report to error tracking
    try {
      const { reportError } = require('../services/errorReporter');
      reportError({
        error_message: `Screen crash [${this.props.screenName || 'unknown'}]: ${error.message}`,
        error_type: 'screen_crash',
        extra: {
          screen: this.props.screenName,
          component_stack: errorInfo.componentStack?.slice(0, 500),
        },
      });
    } catch {}
    console.error(`[ScreenErrorBoundary] ${this.props.screenName}:`, error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    this.props.onReset?.();
  };

  render() {
    if (this.state.hasError) {
      return (
        <View style={s.container}>
          <View style={s.card}>
            <View style={s.iconWrap}>
              <Ionicons name="warning" size={36} color="#FF9500" />
            </View>
            <Text style={s.title}>Something went wrong</Text>
            <Text style={s.screen}>{this.props.screenName}</Text>
            <Text style={s.message} numberOfLines={3}>
              {this.state.error?.message || 'An unexpected error occurred.'}
            </Text>
            <TouchableOpacity style={s.btn} onPress={this.handleReset}>
              <Ionicons name="refresh" size={18} color="#fff" />
              <Text style={s.btnText}>Try Again</Text>
            </TouchableOpacity>
          </View>
        </View>
      );
    }
    return this.props.children;
  }
}

const s = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24, backgroundColor: '#0a0a0a' },
  card:      { backgroundColor: '#1c1c1e', borderRadius: 20, padding: 28, alignItems: 'center', maxWidth: 320, width: '100%' },
  iconWrap:  { width: 64, height: 64, borderRadius: 32, backgroundColor: '#FF950018', justifyContent: 'center', alignItems: 'center', marginBottom: 16 },
  title:     { fontSize: 20, fontWeight: '700', color: '#fff', marginBottom: 4 },
  screen:    { fontSize: 13, fontWeight: '600', color: '#FF9500', marginBottom: 12, textTransform: 'uppercase', letterSpacing: 0.8 },
  message:   { fontSize: 14, color: '#8E8E93', textAlign: 'center', lineHeight: 20, marginBottom: 24 },
  btn:       { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#C9A962', paddingHorizontal: 24, paddingVertical: 12, borderRadius: 12 },
  btnText:   { fontSize: 16, fontWeight: '700', color: '#000' },
});
