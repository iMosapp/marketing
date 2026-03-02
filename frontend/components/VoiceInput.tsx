import React, { useState, useRef } from 'react';
import {
  View,
  TouchableOpacity,
  StyleSheet,
  Platform,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Audio } from 'expo-av';
import api from '../services/api';

import { useThemeStore } from '../store/themeStore';
const IS_WEB = Platform.OS === 'web';

interface VoiceInputProps {
  onTranscription: (text: string) => void;
  size?: 'small' | 'medium' | 'large';
  color?: string;
  style?: any;
  disabled?: boolean;
}

/**
 * Reusable Voice-to-Text Input Component
 * 
 * Usage:
 * <VoiceInput onTranscription={(text) => setMyText(prev => prev + ' ' + text)} />
 * 
 * Props:
 * - onTranscription: Callback with transcribed text
 * - size: 'small' | 'medium' | 'large' (default: 'medium')
 * - color: Icon color (default: '#8E8E93')
 * - style: Additional styles for the container
 * - disabled: Disable the button
 */
export default function VoiceInput({
  onTranscription,
  size = 'medium',
  color = '#8E8E93',
  style,
  disabled = false,
}: VoiceInputProps) {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const recordingRef = useRef<Audio.Recording | null>(null);

  const iconSize = size === 'small' ? 18 : size === 'large' ? 28 : 22;
  const buttonSize = size === 'small' ? 32 : size === 'large' ? 48 : 40;

  const handlePress = async () => {
    if (disabled || isTranscribing) return;

    try {
      if (isRecording) {
        // Stop recording and transcribe
        setIsRecording(false);

        if (recordingRef.current) {
          setIsTranscribing(true);

          await recordingRef.current.stopAndUnloadAsync();
          const uri = recordingRef.current.getURI();
          recordingRef.current = null;

          if (uri) {
            const formData = new FormData();
            
            if (IS_WEB) {
              // On web, uri is a blob URL
              const response = await fetch(uri);
              const blob = await response.blob();
              formData.append('file', blob, 'recording.webm');
            } else {
              formData.append('file', {
                uri,
                type: 'audio/m4a',
                name: 'recording.m4a',
              } as any);
            }

            try {
              const response = await api.post('/voice/transcribe', formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
              });

              if (response.data.success && response.data.text) {
                onTranscription(response.data.text);
              } else {
                Alert.alert('Error', response.data.error || 'Failed to transcribe');
              }
            } catch (error: any) {
              console.error('Transcription error:', error);
              Alert.alert('Error', 'Failed to transcribe audio');
            }
          }

          setIsTranscribing(false);
        }
      } else {
        // Start recording
        const { status } = await Audio.requestPermissionsAsync();
        if (status !== 'granted') {
          Alert.alert('Permission Denied', 'Microphone permission is required.');
          return;
        }

        await Audio.setAudioModeAsync({
          allowsRecordingIOS: true,
          playsInSilentModeIOS: true,
        });

        // Platform-specific recording options
        const recordingOptions = IS_WEB 
          ? {
              ...Audio.RecordingOptionsPresets.HIGH_QUALITY,
              isMeteringEnabled: false,
              web: {
                mimeType: 'audio/webm;codecs=opus',
                bitsPerSecond: 128000,
              },
            }
          : Audio.RecordingOptionsPresets.HIGH_QUALITY;

        const recording = new Audio.Recording();
        await recording.prepareToRecordAsync(recordingOptions);
        await recording.startAsync();

        recordingRef.current = recording;
        setIsRecording(true);
        
        // On web, auto-stop after 30 seconds
        if (IS_WEB) {
          setTimeout(() => {
            if (recordingRef.current) {
              handlePress(); // Stop recording
            }
          }, 30000);
        }
      }
    } catch (error) {
      console.error('Recording error:', error);
      setIsRecording(false);
      setIsTranscribing(false);
      if (IS_WEB) {
        Alert.alert('Microphone Error', 'Could not access microphone. Please ensure you have granted permission in your browser.');
      } else {
        Alert.alert('Error', 'Failed to record audio');
      }
    }
  };

  // Web-safe button rendering
  if (IS_WEB) {
    return (
      <button
        type="button"
        onClick={handlePress}
        disabled={disabled || isTranscribing}
        data-testid="voice-input-btn"
        style={{
          width: buttonSize,
          height: buttonSize,
          borderRadius: buttonSize / 2,
          border: 'none',
          background: isRecording ? '#FF3B3020' : 'transparent',
          cursor: disabled || isTranscribing ? 'not-allowed' : 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          opacity: disabled ? 0.5 : 1,
          ...style,
        }}
      >
        {isTranscribing ? (
          <ActivityIndicator size="small" color="#007AFF" />
        ) : (
          <Ionicons
            name={isRecording ? 'stop-circle' : 'mic-outline'}
            size={iconSize}
            color={isRecording ? '#FF3B30' : color}
          />
        )}
      </button>
    );
  }

  return (
    <TouchableOpacity
      style={[
        styles.button,
        { width: buttonSize, height: buttonSize, borderRadius: buttonSize / 2 },
        isRecording && styles.recording,
        style,
      ]}
      onPress={handlePress}
      disabled={disabled || isTranscribing}
      data-testid="voice-input-btn"
    >
      {isTranscribing ? (
        <ActivityIndicator size="small" color="#007AFF" />
      ) : (
        <Ionicons
          name={isRecording ? 'stop-circle' : 'mic-outline'}
          size={iconSize}
          color={isRecording ? '#FF3B30' : color}
        />
      )}
    </TouchableOpacity>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  button: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  recording: {
    backgroundColor: '#FF3B3020',
  },
});
