// iOS / Android: react-native-webrtc for the peer connection, InCallManager for the speaker route.
// Both are required lazily so an OTA update never crashes a binary that was built without them.
import { NativeModules } from 'react-native';
import type { LiveRtc } from './liveRtc';

let webrtc: any = null;
let incall: any = null;
let reason = '';
try { webrtc = require('react-native-webrtc'); } catch (e: any) { webrtc = null; reason = String(e?.message || e || 'require failed').split('\n')[0]; }
try { incall = require('react-native-incall-manager').default; } catch { incall = null; }
if (webrtc && !NativeModules.WebRTCModule) { webrtc = null; reason = 'WebRTC native module is not in this build'; }
// InCallManager shipped in the same commit: "missing too" = binary predates both, "present" = only WebRTC failed to link.
if (!webrtc) reason = `${reason.replace(/\.$/, '')}; InCallManager ${NativeModules.InCallManager ? 'present' : 'missing too'}`;

export type { LiveRtc };

export const nativeRtcMissing = !webrtc;
// Why the native module is unusable ("WebRTC native module not found." on binaries built before it was added).
export const nativeRtcReason = reason;

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
