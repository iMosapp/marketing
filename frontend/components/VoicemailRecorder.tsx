import React, { useState, useRef, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Platform,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Audio, AVPlaybackStatus } from 'expo-av';
import api from '../services/api';
import { useAuthStore } from '../store/authStore';

/**
 * Voicemail Recorder Component
 * 
 * Features:
 * - Record voicemail greeting (up to 60 seconds)
 * - Play back recorded greeting
 * - Save to user profile
 * - Delete existing greeting
 */
export default function VoicemailRecorder() {
  const { user } = useAuthStore();
  const [isRecording, setIsRecording] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [hasRecording, setHasRecording] = useState(false);
  const [recordingDuration, setRecordingDuration] = useState(0);
  const [playbackDuration, setPlaybackDuration] = useState(0);
  const [recordingUri, setRecordingUri] = useState<string | null>(null);
  
  const recordingRef = useRef<Audio.Recording | null>(null);
  const soundRef = useRef<Audio.Sound | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    // Check if user has existing voicemail
    checkExistingVoicemail();
    
    return () => {
      // Cleanup
      if (timerRef.current) clearInterval(timerRef.current);
      if (soundRef.current) soundRef.current.unloadAsync();
    };
  }, [user?._id]);

  const checkExistingVoicemail = async () => {
    if (!user?._id) return;
    
    try {
      const response = await api.get(`/voice/voicemail/${user._id}`);
      if (response.data?.voicemail_url) {
        setHasRecording(true);
        setRecordingUri(response.data.voicemail_url);
      }
    } catch (error) {
      // No voicemail exists
    }
  };

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const startRecording = async () => {
    if (Platform.OS === 'web') {
      Alert.alert('Not Available', 'Voicemail recording is only available on mobile devices.');
      return;
    }

    try {
      const { status } = await Audio.requestPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permission Denied', 'Microphone permission is required.');
        return;
      }

      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });

      const recording = new Audio.Recording();
      await recording.prepareToRecordAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY);
      await recording.startAsync();

      recordingRef.current = recording;
      setIsRecording(true);
      setRecordingDuration(0);

      // Start duration timer
      timerRef.current = setInterval(() => {
        setRecordingDuration(prev => {
          if (prev >= 60) {
            // Auto-stop at 60 seconds
            stopRecording();
            return prev;
          }
          return prev + 1;
        });
      }, 1000);

    } catch (error) {
      console.error('Recording error:', error);
      Alert.alert('Error', 'Failed to start recording.');
    }
  };

  const stopRecording = async () => {
    if (!recordingRef.current) return;

    try {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }

      await recordingRef.current.stopAndUnloadAsync();
      const uri = recordingRef.current.getURI();
      recordingRef.current = null;

      setIsRecording(false);
      
      if (uri) {
        setRecordingUri(uri);
        setHasRecording(true);
      }
    } catch (error) {
      console.error('Stop recording error:', error);
      setIsRecording(false);
    }
  };

  const playRecording = async () => {
    if (!recordingUri) return;

    try {
      if (soundRef.current) {
        await soundRef.current.unloadAsync();
      }

      const { sound } = await Audio.Sound.createAsync(
        { uri: recordingUri },
        { shouldPlay: true },
        onPlaybackStatusUpdate
      );

      soundRef.current = sound;
      setIsPlaying(true);

    } catch (error) {
      console.error('Playback error:', error);
      Alert.alert('Error', 'Failed to play recording.');
    }
  };

  const onPlaybackStatusUpdate = (status: AVPlaybackStatus) => {
    if (status.isLoaded) {
      if (status.didJustFinish) {
        setIsPlaying(false);
        setPlaybackDuration(0);
      } else if (status.positionMillis) {
        setPlaybackDuration(Math.floor(status.positionMillis / 1000));
      }
    }
  };

  const stopPlayback = async () => {
    if (soundRef.current) {
      await soundRef.current.stopAsync();
      setIsPlaying(false);
      setPlaybackDuration(0);
    }
  };

  const saveVoicemail = async () => {
    if (!recordingUri || !user?._id) return;

    setIsSaving(true);
    try {
      const formData = new FormData();
      formData.append('file', {
        uri: recordingUri,
        type: 'audio/m4a',
        name: 'voicemail.m4a',
      } as any);

      await api.post(`/voice/voicemail/${user._id}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      Alert.alert('Success', 'Voicemail greeting saved!');
    } catch (error) {
      console.error('Save error:', error);
      Alert.alert('Error', 'Failed to save voicemail.');
    } finally {
      setIsSaving(false);
    }
  };

  const deleteVoicemail = () => {
    Alert.alert(
      'Delete Voicemail',
      'Are you sure you want to delete your voicemail greeting?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              if (user?._id) {
                await api.delete(`/voice/voicemail/${user._id}`);
              }
              setHasRecording(false);
              setRecordingUri(null);
              setRecordingDuration(0);
              Alert.alert('Deleted', 'Voicemail greeting removed.');
            } catch (error) {
              Alert.alert('Error', 'Failed to delete voicemail.');
            }
          },
        },
      ]
    );
  };

  return (
    <View style={styles.container}>
      {/* Recording Status */}
      {isRecording && (
        <View style={styles.recordingIndicator}>
          <View style={styles.recordingDot} />
          <Text style={styles.recordingText}>Recording... {formatDuration(recordingDuration)}</Text>
        </View>
      )}

      {/* Playback Status */}
      {isPlaying && (
        <View style={styles.playbackIndicator}>
          <Ionicons name="volume-high" size={20} color="#007AFF" />
          <Text style={styles.playbackText}>Playing... {formatDuration(playbackDuration)}</Text>
        </View>
      )}

      {/* Has Recording UI */}
      {hasRecording && !isRecording && !isPlaying && (
        <View style={styles.hasRecordingInfo}>
          <Ionicons name="checkmark-circle" size={20} color="#34C759" />
          <Text style={styles.hasRecordingText}>Voicemail greeting saved</Text>
        </View>
      )}

      {/* Controls */}
      <View style={styles.controls}>
        {/* Record/Stop Button */}
        <TouchableOpacity
          style={[styles.recordButton, isRecording && styles.recordButtonActive]}
          onPress={isRecording ? stopRecording : startRecording}
          disabled={isPlaying || isSaving}
        >
          <Ionicons
            name={isRecording ? 'stop' : 'mic'}
            size={28}
            color={isRecording ? '#FFF' : '#FF3B30'}
          />
        </TouchableOpacity>

        {/* Play/Stop Playback Button */}
        {hasRecording && !isRecording && (
          <TouchableOpacity
            style={styles.playButton}
            onPress={isPlaying ? stopPlayback : playRecording}
            disabled={isSaving}
          >
            <Ionicons
              name={isPlaying ? 'stop' : 'play'}
              size={24}
              color="#007AFF"
            />
          </TouchableOpacity>
        )}

        {/* Save Button */}
        {hasRecording && !isRecording && !isPlaying && (
          <TouchableOpacity
            style={styles.saveButton}
            onPress={saveVoicemail}
            disabled={isSaving}
          >
            {isSaving ? (
              <ActivityIndicator size="small" color="#FFF" />
            ) : (
              <>
                <Ionicons name="cloud-upload" size={20} color="#FFF" />
                <Text style={styles.saveButtonText}>Save</Text>
              </>
            )}
          </TouchableOpacity>
        )}

        {/* Delete Button */}
        {hasRecording && !isRecording && !isPlaying && (
          <TouchableOpacity
            style={styles.deleteButton}
            onPress={deleteVoicemail}
            disabled={isSaving}
          >
            <Ionicons name="trash-outline" size={20} color="#FF3B30" />
          </TouchableOpacity>
        )}
      </View>

      <Text style={styles.hint}>
        {isRecording 
          ? 'Tap stop when finished (max 60 seconds)'
          : hasRecording 
            ? 'Tap play to preview, or record a new greeting'
            : 'Tap the microphone to record your greeting'
        }
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginTop: 8,
  },
  recordingIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
    gap: 8,
  },
  recordingDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: '#FF3B30',
  },
  recordingText: {
    color: '#FF3B30',
    fontSize: 14,
    fontWeight: '500',
  },
  playbackIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
    gap: 8,
  },
  playbackText: {
    color: '#007AFF',
    fontSize: 14,
    fontWeight: '500',
  },
  hasRecordingInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
    gap: 8,
  },
  hasRecordingText: {
    color: '#34C759',
    fontSize: 14,
    fontWeight: '500',
  },
  controls: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 16,
    marginBottom: 12,
  },
  recordButton: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: '#FF3B3020',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: '#FF3B30',
  },
  recordButtonActive: {
    backgroundColor: '#FF3B30',
  },
  playButton: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: '#007AFF20',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: '#007AFF',
  },
  saveButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#34C759',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 8,
    gap: 6,
  },
  saveButtonText: {
    color: '#FFF',
    fontSize: 14,
    fontWeight: '600',
  },
  deleteButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#FF3B3020',
    alignItems: 'center',
    justifyContent: 'center',
  },
  hint: {
    fontSize: 12,
    color: '#8E8E93',
    textAlign: 'center',
  },
});
