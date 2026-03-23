import React, { Component, ErrorInfo, ReactNode } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView, Platform } from 'react-native';
import { reportError } from '../services/errorReporter';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('[ErrorBoundary] Caught error:', error, errorInfo);
    // Send crash report to backend
    reportError({
      error_message: error.message,
      error_stack: error.stack || '',
      component_stack: errorInfo.componentStack || '',
      error_type: 'render_crash',
      page: typeof window !== 'undefined' ? window.location?.pathname || 'unknown' : 'native',
    });
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      return (
        <View style={styles.container}>
          <Text style={styles.icon}>!</Text>
          <Text style={styles.title}>Something went wrong</Text>
          <Text style={styles.message}>
            The app encountered an unexpected error. Tap below to try again.
          </Text>
          {__DEV__ && this.state.error && (
            <ScrollView style={styles.errorBox}>
              <Text style={styles.errorText}>{this.state.error.toString()}</Text>
            </ScrollView>
          )}
          <TouchableOpacity style={styles.button} onPress={this.handleRetry} data-testid="error-boundary-retry">
            <Text style={styles.buttonText}>Try Again</Text>
          </TouchableOpacity>
        </View>
      );
    }

    return this.props.children;
  }
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
    backgroundColor: '#000',
  },
  icon: {
    fontSize: 48,
    fontWeight: '700',
    color: '#FF3B30',
    marginBottom: 16,
    width: 72,
    height: 72,
    lineHeight: 72,
    textAlign: 'center',
    borderRadius: 36,
    borderWidth: 3,
    borderColor: '#FF3B30',
    overflow: 'hidden',
  },
  title: {
    fontSize: 20,
    fontWeight: '700',
    color: '#FFF',
    marginBottom: 8,
  },
  message: {
    fontSize: 14,
    color: '#999',
    textAlign: 'center',
    marginBottom: 24,
    lineHeight: 20,
  },
  errorBox: {
    maxHeight: 120,
    width: '100%',
    backgroundColor: '#1A1A1A',
    borderRadius: 8,
    padding: 12,
    marginBottom: 24,
  },
  errorText: {
    fontSize: 11,
    color: '#FF6B6B',
    fontFamily: 'monospace',
  },
  button: {
    backgroundColor: '#007AFF',
    paddingHorizontal: 32,
    paddingVertical: 14,
    borderRadius: 12,
  },
  buttonText: {
    color: '#FFF',
    fontSize: 16,
    fontWeight: '600',
  },
});
