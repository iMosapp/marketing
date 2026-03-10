import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Pressable,
  ActivityIndicator,
  Animated,
  Dimensions,
  TextInput,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { Audio } from 'expo-av';
import * as Haptics from 'expo-haptics';
import { useAuthStore } from '../store/authStore';
import { useThemeStore } from '../store/themeStore';
import api from '../services/api';


const { width: SCREEN_WIDTH } = Dimensions.get('window');

type ConversationState = 'idle' | 'listening' | 'processing' | 'speaking';

// Voice Activity Detection settings
const SILENCE_THRESHOLD = -40; // dB level considered silence
const SILENCE_DURATION = 1200; // ms of silence before auto-send (reduced from 1500)
const MIN_RECORDING_TIME = 400; // minimum recording time before checking silence
const WEB_AUTO_STOP_DURATION = 10000; // On web, auto-stop after 10 seconds since metering isn't available
const IS_WEB = Platform.OS === 'web';

export default function JessiScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  const [textInput, setTextInput] = useState('');
  
  const [state, setState] = useState<ConversationState>('idle');
  const [transcript, setTranscript] = useState('');
  const [response, setResponse] = useState('');
  const [greeting, setGreeting] = useState("Tap to start talking");
  const [audioLevel, setAudioLevel] = useState(0);
  
  const recordingRef = useRef<Audio.Recording | null>(null);
  const soundRef = useRef<Audio.Sound | null>(null);
  const silenceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const meteringIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const recordingStartTimeRef = useRef<number>(0);
  const hasSpokenRef = useRef<boolean>(false);
  
  // Animations
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const glowAnim = useRef(new Animated.Value(0)).current;
  const levelAnim = useRef(new Animated.Value(0)).current;
  
  useFocusEffect(
    useCallback(() => {
      // Set initial greeting based on time of day
      const hour = new Date().getHours();
      if (hour < 12) {
        setGreeting("Good morning! Tap to talk");
      } else if (hour < 17) {
        setGreeting("Good afternoon! Tap to talk");
      } else {
        setGreeting("Good evening! Tap to talk");
      }
      
      // Setup audio mode
      Audio.setAudioModeAsync({
        allowsRecordingIOS: false,
        playsInSilentModeIOS: true,
        staysActiveInBackground: false,
        shouldDuckAndroid: false,
        playThroughEarpieceAndroid: false,
      });
      
      return () => {
        // Cleanup
        cleanup();
      };
    }, [])
  );
  
  const cleanup = () => {
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    if (meteringIntervalRef.current) {
      clearInterval(meteringIntervalRef.current);
      meteringIntervalRef.current = null;
    }
    if (soundRef.current) {
      soundRef.current.unloadAsync().catch(() => {});
    }
    if (recordingRef.current) {
      recordingRef.current.stopAndUnloadAsync().catch(() => {});
    }
  };
  
  // Pulse animation for idle state
  useEffect(() => {
    if (state === 'idle') {
      Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, { toValue: 1.05, duration: 2000, useNativeDriver: true }),
          Animated.timing(pulseAnim, { toValue: 1, duration: 2000, useNativeDriver: true }),
        ])
      ).start();
    } else {
      pulseAnim.setValue(1);
    }
  }, [state]);
  
  // Glow animation for listening/speaking
  useEffect(() => {
    if (state === 'listening' || state === 'speaking') {
      Animated.loop(
        Animated.sequence([
          Animated.timing(glowAnim, { toValue: 1, duration: 800, useNativeDriver: true }),
          Animated.timing(glowAnim, { toValue: 0.3, duration: 800, useNativeDriver: true }),
        ])
      ).start();
    } else {
      glowAnim.setValue(0);
    }
  }, [state]);
  
  // Audio level animation
  useEffect(() => {
    Animated.timing(levelAnim, {
      toValue: audioLevel,
      duration: 100,
      useNativeDriver: true,
    }).start();
  }, [audioLevel]);
  
  const startListening = async () => {
    if (state !== 'idle') return;
    
    try {
      // Clean up any existing recording first
      if (recordingRef.current) {
        try {
          await recordingRef.current.stopAndUnloadAsync();
        } catch (e) {
          // Ignore cleanup errors
        }
        recordingRef.current = null;
      }
      
      // Request permissions
      const { granted } = await Audio.requestPermissionsAsync();
      if (!granted) {
        alert('Please grant microphone permission to talk with Jessi');
        return;
      }
      
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });
      
      // Create recording with platform-specific options
      // On web, expo-av uses MediaRecorder API which works differently
      const recordingOptions = IS_WEB 
        ? {
            ...Audio.RecordingOptionsPresets.HIGH_QUALITY,
            isMeteringEnabled: false, // Metering not supported on web
            web: {
              mimeType: 'audio/webm;codecs=opus',
              bitsPerSecond: 128000,
            },
          }
        : {
            ...Audio.RecordingOptionsPresets.HIGH_QUALITY,
            isMeteringEnabled: true,
          };
      
      const { recording: newRecording } = await Audio.Recording.createAsync(recordingOptions);
      
      recordingRef.current = newRecording;
      recordingStartTimeRef.current = Date.now();
      hasSpokenRef.current = false;
      setState('listening');
      setTranscript('');
      setResponse('');
      
      // Start monitoring audio levels for VAD
      startVoiceActivityDetection();
      
    } catch (error) {
      console.error('Failed to start recording:', error);
      // Show user-friendly error on web
      if (IS_WEB) {
        setResponse("Couldn't access microphone. Please ensure you've granted microphone permission in your browser settings.");
      }
      setState('idle');
    }
  };
  
  const startVoiceActivityDetection = () => {
    // Clear any existing timers
    if (meteringIntervalRef.current) {
      clearInterval(meteringIntervalRef.current);
    }
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
    }
    
    // On web, metering is not supported by expo-av
    // Use a simple timer-based approach instead
    if (IS_WEB) {
      // For web: assume user is always speaking (skip VAD)
      hasSpokenRef.current = true;
      
      // Show a simple visual feedback animation
      let level = 0;
      meteringIntervalRef.current = setInterval(() => {
        // Simulate audio level with a pulsing animation
        level = 0.3 + Math.sin(Date.now() / 200) * 0.3;
        setAudioLevel(level);
      }, 100);
      
      // Auto-stop after WEB_AUTO_STOP_DURATION (user can also tap to stop earlier)
      silenceTimerRef.current = setTimeout(() => {
        stopAndProcess();
      }, WEB_AUTO_STOP_DURATION);
      
      return;
    }
    
    // Native: Monitor audio levels every 100ms for VAD
    meteringIntervalRef.current = setInterval(async () => {
      if (!recordingRef.current) return;
      
      try {
        const status = await recordingRef.current.getStatusAsync();
        if (!status.isRecording) return;
        
        const metering = status.metering || -160;
        
        // Normalize metering to 0-1 for visual display
        const normalizedLevel = Math.max(0, Math.min(1, (metering + 60) / 60));
        setAudioLevel(normalizedLevel);
        
        const timeSinceStart = Date.now() - recordingStartTimeRef.current;
        
        // Check if user has spoken (audio above threshold)
        if (metering > SILENCE_THRESHOLD) {
          hasSpokenRef.current = true;
          // Clear silence timer if user is speaking
          if (silenceTimerRef.current) {
            clearTimeout(silenceTimerRef.current);
            silenceTimerRef.current = null;
          }
        } else if (hasSpokenRef.current && timeSinceStart > MIN_RECORDING_TIME) {
          // User has spoken before and now it's quiet
          // Start silence timer if not already started
          if (!silenceTimerRef.current) {
            silenceTimerRef.current = setTimeout(() => {
              // Auto-send after silence duration
              stopAndProcess();
            }, SILENCE_DURATION);
          }
        }
      } catch (error) {
        // Ignore metering errors
      }
    }, 100);
  };
  
  const stopAndProcess = async () => {
    // Clear timers
    if (meteringIntervalRef.current) {
      clearInterval(meteringIntervalRef.current);
      meteringIntervalRef.current = null;
    }
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    
    if (!recordingRef.current) return;
    
    try {
      setState('processing');
      setAudioLevel(0);
      
      const recording = recordingRef.current;
      recordingRef.current = null;
      
      await recording.stopAndUnloadAsync();
      const uri = recording.getURI();
      
      if (uri && hasSpokenRef.current) {
        await processVoice(uri);
      } else {
        // No speech detected
        setResponse("I didn't hear anything. Tap to try again.");
        setState('idle');
      }
      
    } catch (error) {
      console.error('Failed to stop recording:', error);
      setState('idle');
    }
  };
  
  const cancelListening = async () => {
    // Cancel without processing
    cleanup();
    setState('idle');
    setAudioLevel(0);
  };
  
  const processVoice = async (audioUri: string) => {
    try {
      // Create form data for audio upload
      // On web, the audio is in webm format; on native, it's m4a
      const formData = new FormData();
      
      if (IS_WEB) {
        // On web, audioUri is a blob URL - we need to fetch it and create a proper file
        const response = await fetch(audioUri);
        const blob = await response.blob();
        formData.append('file', blob, 'recording.webm');
      } else {
        formData.append('file', {
          uri: audioUri,
          type: 'audio/m4a',
          name: 'recording.m4a',
        } as any);
      }
      
      formData.append('user_id', user?._id || '');
      
      // Transcribe with longer timeout
      const transcribeRes = await api.post('/voice/transcribe', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 30000, // 30 second timeout
      });
      
      const transcribedText = transcribeRes.data.text || transcribeRes.data.transcription;
      
      if (!transcribedText) {
        setResponse("I couldn't understand that. Tap to try again.");
        setState('idle');
        return;
      }
      
      setTranscript(transcribedText);
      
      // Get Jessi's response with voice - longer timeout for AI + TTS
      const chatRes = await api.post('/jessie/chat', {
        user_id: user?._id,
        message: transcribedText,
        include_voice: true,
      }, {
        timeout: 60000, // 60 second timeout for AI response + voice generation
      });
      
      setResponse(chatRes.data.text);
      
      // Play the audio response
      if (chatRes.data.audio_base64) {
        await playAudio(chatRes.data.audio_base64);
      } else {
        setState('idle');
        setGreeting("Tap to continue");
      }
      
    } catch (error: any) {
      console.error('Processing failed:', error);
      // More specific error message
      if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
        setResponse("Request timed out. Check your connection and try again.");
      } else if (error.response?.status === 500) {
        setResponse("Server error. Please try again in a moment.");
      } else {
        setResponse("Couldn't process that. Tap to try again.");
      }
      setState('idle');
    }
  };
  
  const sendTextMessage = async () => {
    if (!textInput.trim() || state !== 'idle') return;
    
    // Light haptic for sending
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    
    const message = textInput.trim();
    setTextInput('');
    setTranscript(message);
    setState('processing');
    
    try {
      const chatRes = await api.post('/jessie/chat', {
        user_id: user?._id,
        message: message,
        include_voice: false,  // Skip TTS for text input — instant response
      }, {
        timeout: 30000,
      });
      
      // Success haptic when Jessi responds
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      
      setResponse(chatRes.data.text);
      
      if (chatRes.data.audio_base64) {
        await playAudio(chatRes.data.audio_base64);
      } else {
        setState('idle');
        setGreeting("Tap to continue");
      }
    } catch (error: any) {
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      console.error('Text message failed:', error);
      if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
        setResponse("Request timed out. Check your connection.");
      } else {
        setResponse("Something went wrong. Try again.");
      }
      setState('idle');
    }
  };
  
  const playAudio = async (base64Audio: string) => {
    try {
      setState('speaking');
      
      // Unload previous sound
      if (soundRef.current) {
        await soundRef.current.unloadAsync();
        soundRef.current = null;
      }
      
      // Set audio mode for playback at max volume through speaker
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: false,
        playsInSilentModeIOS: true,
        staysActiveInBackground: false,
        shouldDuckAndroid: false,
        playThroughEarpieceAndroid: false,
      });
      
      const { sound: newSound } = await Audio.Sound.createAsync(
        { uri: `data:audio/mp3;base64,${base64Audio}` },
        { 
          shouldPlay: true,
          volume: 1.0,
          isMuted: false,
        }
      );
      
      soundRef.current = newSound;
      await newSound.setVolumeAsync(1.0);
      
      newSound.setOnPlaybackStatusUpdate((status) => {
        if (status.isLoaded && status.didJustFinish) {
          setState('idle');
          setGreeting("Tap to continue talking");
        }
      });
      
    } catch (error) {
      console.error('Failed to play audio:', error);
      setState('idle');
    }
  };
  
  const handleButtonPress = () => {
    if (state === 'idle') {
      startListening();
    } else if (state === 'listening') {
      // Manual stop - process immediately
      stopAndProcess();
    }
  };
  
  const handleBack = () => {
    cleanup();
    if (router.canGoBack()) {
      router.back();
    } else {
      router.replace('/(tabs)');
    }
  };
  
  const getStateColor = () => {
    switch (state) {
      case 'listening': return '#FF3B30';
      case 'processing': return '#FF9500';
      case 'speaking': return '#34C759';
      default: return '#C9A962';
    }
  };
  
  const getStateText = () => {
    switch (state) {
      case 'listening': 
        return IS_WEB 
          ? 'Listening... (tap mic to stop and send)' 
          : 'Listening... (will auto-send when you pause)';
      case 'processing': return 'Thinking...';
      case 'speaking': return 'Jessi is speaking';
      default: return greeting;
    }
  };
  
  const getStateIcon = () => {
    switch (state) {
      case 'listening': return 'mic';
      case 'processing': return 'ellipsis-horizontal';
      case 'speaking': return 'volume-high';
      default: return 'mic-outline';
    }
  };
  
  // Render audio level visualization
  const renderAudioBars = () => {
    if (state !== 'listening') return null;
    
    const bars = [0, 1, 2, 3, 4];
    return (
      <View style={styles.audioBarsContainer}>
        {bars.map((i) => (
          <Animated.View
            key={i}
            style={[
              styles.audioBar,
              {
                transform: [{
                  scaleY: levelAnim.interpolate({
                    inputRange: [0, 1],
                    outputRange: [0.2, 0.3 + (i === 2 ? 1 : i === 1 || i === 3 ? 0.7 : 0.4)],
                  })
                }],
                opacity: levelAnim.interpolate({
                  inputRange: [0, 0.3, 1],
                  outputRange: [0.3, 0.6, 1],
                }),
              }
            ]}
          />
        ))}
      </View>
    );
  };
  
  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.bg }]} edges={['top']}>
      <KeyboardAvoidingView 
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.keyboardView}
      >
        {/* Header */}
        <View style={[styles.header, { borderBottomColor: colors.border }]}>
          <TouchableOpacity onPress={handleBack} style={styles.backButton} data-testid="jessi-back-btn">
            <Ionicons name="chevron-back" size={28} color={colors.text} />
          </TouchableOpacity>
          
          <Text style={[styles.headerTitle, { color: colors.text }]}>Jessi</Text>
          
          {state === 'listening' ? (
            <TouchableOpacity onPress={cancelListening} style={styles.cancelButton}>
              <Ionicons name="close-circle" size={28} color="#FF3B30" />
            </TouchableOpacity>
          ) : (
            <View style={styles.placeholder} />
          )}
        </View>
        
        {/* Main Content */}
        <View style={styles.content}>
          {/* Response Text - Scrollable */}
          {response ? (
            <ScrollView 
              style={styles.responseScrollView}
              contentContainerStyle={styles.responseScrollContent}
              showsVerticalScrollIndicator={true}
            >
              {transcript ? (
                <Text style={styles.transcriptText}>"{transcript}"</Text>
              ) : null}
              <Text style={[styles.responseText, { color: colors.text }]}>{response}</Text>
            </ScrollView>
          ) : (
            <View style={styles.introContainer}>
              <Text style={[styles.introTitle, { color: colors.text }]}>Hi, I'm Jessi!</Text>
              <Text style={[styles.introText, { color: colors.textSecondary }]}>
                Your voice assistant for i'M On Social.{'\n'}
                Tap to talk or type below.
              </Text>
            </View>
          )}
          
          {/* Voice Button */}
          <View style={styles.buttonContainer}>
            {renderAudioBars()}
            
            <Animated.View
              style={[
                styles.glowRing,
                {
                  backgroundColor: getStateColor(),
                  opacity: glowAnim.interpolate({
                    inputRange: [0, 1],
                    outputRange: [0, 0.3]
                  }),
                  transform: [{ scale: glowAnim.interpolate({
                    inputRange: [0, 1],
                    outputRange: [1, 1.3]
                  })}]
                }
              ]}
            />
            
            <Animated.View style={{ transform: [{ scale: pulseAnim }] }}>
              {/* Web-compatible voice button */}
              {IS_WEB ? (
                <button
                  type="button"
                  onClick={handleButtonPress}
                  disabled={state === 'processing' || state === 'speaking'}
                  data-testid="jessi-voice-btn"
                  style={{
                    width: 100,
                    height: 100,
                    borderRadius: 50,
                    backgroundColor: getStateColor(),
                    border: 'none',
                    cursor: state === 'processing' || state === 'speaking' ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    boxShadow: `0 0 20px ${getStateColor()}80`,
                    transition: 'transform 0.1s ease, opacity 0.15s ease',
                    WebkitTapHighlightColor: 'transparent',
                    touchAction: 'manipulation',
                  }}
                  onMouseDown={(e) => {
                    e.currentTarget.style.transform = 'scale(0.95)';
                  }}
                  onMouseUp={(e) => {
                    e.currentTarget.style.transform = 'scale(1)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.transform = 'scale(1)';
                  }}
                >
                  {state === 'processing' ? (
                    <ActivityIndicator size="large" color={colors.text} />
                  ) : (
                    <Ionicons name={getStateIcon()} size={50} color={colors.text} />
                  )}
                </button>
              ) : (
                <TouchableOpacity
                  style={[
                    styles.voiceButton,
                    { backgroundColor: getStateColor() }
                  ]}
                  onPress={handleButtonPress}
                  disabled={state === 'processing' || state === 'speaking'}
                  activeOpacity={0.8}
                  data-testid="jessi-voice-btn"
                >
                  {state === 'processing' ? (
                    <ActivityIndicator size="large" color={colors.text} />
                  ) : (
                    <Ionicons name={getStateIcon()} size={50} color={colors.text} />
                  )}
                </TouchableOpacity>
              )}
            </Animated.View>
            
            <Text style={[styles.stateText, { color: getStateColor() }]}>
              {getStateText()}
            </Text>
          </View>
          
          {/* Text Input */}
          <View style={[styles.inputContainer, { backgroundColor: colors.bg, borderTopColor: colors.border }]}>
            <TextInput
              style={[styles.textInput, { backgroundColor: colors.card, color: colors.text }]}
              placeholder="Or type your question..."
              placeholderTextColor="#6E6E73"
              value={textInput}
              onChangeText={setTextInput}
              editable={state === 'idle'}
              returnKeyType="send"
              onSubmitEditing={sendTextMessage}
            />
            <TouchableOpacity
              style={[
                styles.sendButton,
                (!textInput.trim() || state !== 'idle') && styles.sendButtonDisabled
              ]}
              onPress={sendTextMessage}
              disabled={!textInput.trim() || state !== 'idle'}
            >
              <Ionicons name="send" size={20} color={textInput.trim() && state === 'idle' ? '#C9A962' : colors.borderLight} />
            </TouchableOpacity>
          </View>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
  },
  backButton: {
    padding: 4,
    width: 60,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
  },
  placeholder: {
    width: 60,
  },
  cancelButton: {
    padding: 4,
    width: 60,
    alignItems: 'flex-end',
  },
  cancelText: {
    color: '#FF3B30',
    fontSize: 16,
    fontWeight: '500',
  },
  content: {
    flex: 1,
    justifyContent: 'flex-end', // Anchor content to bottom
    paddingTop: 40,
  },
  introContainer: {
    alignItems: 'center',
    paddingHorizontal: 40,
    flex: 1,
    justifyContent: 'center',
  },
  introTitle: {
    fontSize: 32,
    fontWeight: '700',
    marginBottom: 12,
  },
  introText: {
    fontSize: 17,
    textAlign: 'center',
    lineHeight: 26,
  },
  responseScrollView: {
    flex: 1,
    maxHeight: 220,
  },
  responseScrollContent: {
    paddingHorizontal: 20,
    paddingVertical: 16,
    alignItems: 'center',
  },
  responseContainer: {
    paddingHorizontal: 24,
    alignItems: 'center',
    maxHeight: 200,
    flex: 1,
    justifyContent: 'center',
  },
  transcriptText: {
    fontSize: 14,
    color: colors.textSecondary,
    fontStyle: 'italic',
    marginBottom: 12,
    textAlign: 'center',
  },
  responseText: {
    fontSize: 17,
    textAlign: 'left',
    lineHeight: 26,
  },
  buttonContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 20,
    // Reduced height since we have text input now
    minHeight: 220,
  },
  glowRing: {
    position: 'absolute',
    width: 140,
    height: 140,
    borderRadius: 70,
  },
  voiceButton: {
    width: 100,
    height: 100,
    borderRadius: 50,
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#C9A962',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.5,
    shadowRadius: 20,
    elevation: 10,
  },
  stateText: {
    fontSize: 16,
    fontWeight: '600',
    marginTop: 24,
    textAlign: 'center',
    paddingHorizontal: 20,
  },
  hintText: {
    fontSize: 14,
    color: '#6E6E73',
    marginTop: 8,
  },
  audioBarsContainer: {
    position: 'absolute',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    top: -50,
  },
  audioBar: {
    width: 8,
    height: 40,
    backgroundColor: '#FF3B30',
    borderRadius: 4,
  },
  keyboardView: {
    flex: 1,
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderTopWidth: 1,
  },
  textInput: {
    flex: 1,
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 10,
    fontSize: 16,
    marginRight: 10,
  },
  sendButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
  },
  sendButtonDisabled: {
    opacity: 0.5,
  },
});
