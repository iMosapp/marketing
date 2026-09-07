import React, { useEffect, useRef, useState } from 'react';
import { Modal, View, Text, TouchableOpacity, useWindowDimensions, ActivityIndicator, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Video, ResizeMode, AVPlaybackStatus, Audio } from 'expo-av';
import { API_BASE_URL } from '../../services/api';

const GOLD = '#C9A962';
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });

export const WELCOME_VIDEO_URL = `${API_BASE_URL}/promo-videos/rep-welcome-9x16.mp4`;
export const WELCOME_VIDEO_POSTER = `${API_BASE_URL}/promo-videos/rep-welcome-poster.jpg`;
export const welcomeVideoKey = (userId: string) => `welcome_video_v1_${userId}`;

interface Props { visible: boolean; onClose: () => void; onShowCards?: () => void; }

export function WelcomeVideo({ visible, onClose, onShowCards }: Props) {
  const { width, height } = useWindowDimensions();
  const ref = useRef<Video>(null);
  const [ready, setReady] = useState(false);
  const [finished, setFinished] = useState(false);
  const [muted, setMuted] = useState(Platform.OS === 'web');
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!visible) return;
    setReady(false); setFinished(false); setFailed(false);
    if (Platform.OS !== 'web') Audio.setAudioModeAsync({ playsInSilentModeIOS: true }).catch(() => {});
  }, [visible]);

  const videoH = Math.min(height - 250, (width - 48) * 16 / 9);
  const videoW = videoH * 9 / 16;

  const onStatus = (st: AVPlaybackStatus) => {
    if (!st.isLoaded) return;
    if (!ready && (st.isPlaying || st.positionMillis > 0)) setReady(true);
    if (st.didJustFinish) setFinished(true);
  };

  const replay = () => { setFinished(false); ref.current?.replayAsync(); };
  const unmute = () => { setMuted(false); ref.current?.setIsMutedAsync(false); };

  return (
    <Modal visible={visible} animationType="fade" transparent statusBarTranslucent onRequestClose={onClose}>
      <View style={{ flex: 1, backgroundColor: '#0B0B0B' }} {...tid('welcome-video')}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 20, paddingTop: 58 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            <Ionicons name="play-circle" size={15} color={GOLD} />
            <Text style={{ fontSize: 12, fontWeight: '800', color: GOLD, letterSpacing: 1 }}>YOUR HOME IN 60 SECONDS</Text>
          </View>
          <TouchableOpacity onPress={onClose} hitSlop={10} {...tid('welcome-video-skip')}>
            <Text style={{ fontSize: 14, fontWeight: '600', color: '#8E8E93' }}>Skip</Text>
          </TouchableOpacity>
        </View>

        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <View style={{ width: videoW, height: videoH, borderRadius: 28, overflow: 'hidden', backgroundColor: '#000', borderWidth: 1, borderColor: '#2A2A2A' }}>
            {visible && (
              <Video
                ref={ref}
                source={{ uri: WELCOME_VIDEO_URL }}
                posterSource={{ uri: WELCOME_VIDEO_POSTER }}
                usePoster={!ready}
                posterStyle={{ resizeMode: 'cover' }}
                style={{ width: '100%', height: '100%' }}
                resizeMode={ResizeMode.CONTAIN}
                shouldPlay
                isMuted={muted}
                useNativeControls={Platform.OS !== 'web'}
                onPlaybackStatusUpdate={onStatus}
                onError={() => setFailed(true)}
                {...tid('welcome-video-player')}
              />
            )}
            {!ready && (
              <View style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, alignItems: 'center', justifyContent: 'center' }} {...tid('welcome-video-loading')}>
                {failed ? (
                  <View style={{ backgroundColor: 'rgba(0,0,0,0.75)', borderRadius: 14, paddingHorizontal: 16, paddingVertical: 12, marginHorizontal: 24 }}>
                    <Text style={{ fontSize: 13, fontWeight: '600', color: '#fff', textAlign: 'center' }}>The video could not load. Check your connection and try again from Help Center.</Text>
                  </View>
                ) : <ActivityIndicator color={GOLD} />}
              </View>
            )}
            {muted && ready && !finished && (
              <TouchableOpacity onPress={unmute} activeOpacity={0.85}
                style={{ position: 'absolute', bottom: 16, left: 16, right: 16, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: GOLD, borderRadius: 24, paddingVertical: 12 }}
                {...tid('welcome-video-unmute')}>
                <Ionicons name="volume-high" size={18} color="#000" />
                <Text style={{ fontSize: 14, fontWeight: '800', color: '#000' }}>Tap for sound</Text>
              </TouchableOpacity>
            )}
            {finished && (
              <TouchableOpacity onPress={replay} activeOpacity={0.85}
                style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(0,0,0,0.55)' }}
                {...tid('welcome-video-replay')}>
                <Ionicons name="refresh-circle" size={64} color={GOLD} />
                <Text style={{ fontSize: 14, fontWeight: '700', color: '#fff', marginTop: 6 }}>Watch again</Text>
              </TouchableOpacity>
            )}
          </View>
        </View>

        <View style={{ paddingHorizontal: 24, paddingBottom: 44 }}>
          <TouchableOpacity onPress={onClose} activeOpacity={0.85}
            style={{ backgroundColor: GOLD, borderRadius: 28, paddingVertical: 16, alignItems: 'center' }} {...tid('welcome-video-done')}>
            <Text style={{ fontSize: 16, fontWeight: '800', color: '#000' }}>Let's go</Text>
          </TouchableOpacity>
          {onShowCards ? (
            <TouchableOpacity onPress={onShowCards} hitSlop={8} style={{ alignItems: 'center', marginTop: 14 }} {...tid('welcome-video-show-cards')}>
              <Text style={{ fontSize: 13, fontWeight: '600', color: '#8E8E93' }}>Prefer to read? Show me the three cards</Text>
            </TouchableOpacity>
          ) : (
            <Text style={{ textAlign: 'center', fontSize: 12, color: '#666', marginTop: 12 }}>Replay anytime from Tools &gt; Help Center.</Text>
          )}
        </View>
      </View>
    </Modal>
  );
}

export async function shouldShowWelcomeVideo(userId: string) {
  try { return !(await AsyncStorage.getItem(welcomeVideoKey(userId))); } catch { return false; }
}

export async function markWelcomeVideoSeen(userId: string) {
  try { await AsyncStorage.setItem(welcomeVideoKey(userId), new Date().toISOString()); } catch {}
}
