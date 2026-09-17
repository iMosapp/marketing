// iOS / Android: react-native-webrtc for the peer connection, InCallManager for the speaker route.
// Both are required lazily so an OTA update never crashes a binary that was built without them.
import type { LiveRtc } from './liveRtc';

let webrtc: any = null;
let incall: any = null;
try { webrtc = require('react-native-webrtc'); } catch { webrtc = null; }
try { incall = require('react-native-incall-manager').default; } catch { incall = null; }

export type { LiveRtc };

export const nativeRtcMissing = !webrtc;

export const getRtc = (): LiveRtc | null => {
  if (!webrtc?.RTCPeerConnection || !webrtc?.mediaDevices?.getUserMedia) return null;
  return {
    PeerConnection: webrtc.RTCPeerConnection,
    getUserMedia: (c: any) => webrtc.mediaDevices.getUserMedia(c),
    MediaStream: webrtc.MediaStream,
    answer: (sdp: string) => (webrtc.RTCSessionDescription ? new webrtc.RTCSessionDescription({ type: 'answer', sdp }) : { type: 'answer', sdp }),
  };
};

// Remote audio tracks play on their own on native; nothing to attach.
export const attachRemoteAudio = (_connection: any): (() => void) => () => {};

export const startAudioSession = () => {
  try { incall?.start({ media: 'audio' }); incall?.setForceSpeakerphoneOn(true); } catch { /* speaker route is best effort */ }
};

export const stopAudioSession = () => {
  try { incall?.setForceSpeakerphoneOn(null); incall?.stop(); } catch { /* noop */ }
};
