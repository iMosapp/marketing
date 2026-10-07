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

let av: any = null;
try { av = require('expo-av'); } catch { av = null; }
// Ports that mean "the rep is wearing something": AirPods / car / wired. Everything else = hold the phone, so loudspeaker.
const HEADSET_PORTS = new Set(['BluetoothHFP', 'BluetoothLE', 'BluetoothA2DP', 'Headphones', 'HeadsetMic', 'CarAudio', 'USBAudio']);
let routeTimer: ReturnType<typeof setInterval> | null = null;
let speakerForced: boolean | null = null;

const headsetConnected = async (): Promise<boolean> => {
  try {
    const inputs: { type?: string }[] = await new av.Audio.Recording().getAvailableInputs();
    return inputs.some(i => HEADSET_PORTS.has(String(i?.type || '')));
  } catch { return false; }
};

// Loudspeaker only when nothing is worn; with AirPods or a car connected the system route wins. Re-checked while live so
// putting AirPods in (or taking them out) mid-conversation follows along.
export const applyAudioRoute = async () => {
  if (!incall) return;
  const headset = av ? await headsetConnected() : false;
  const force = !headset;
  if (speakerForced === force) return;
  speakerForced = force;
  try { incall.setForceSpeakerphoneOn(force ? true : null); } catch { /* best effort */ }
};

export const startAudioSession = () => {
  try { incall?.start({ media: 'audio' }); } catch { /* speaker route is best effort */ }
  speakerForced = null;
  applyAudioRoute();
  if (routeTimer) clearInterval(routeTimer);
  routeTimer = setInterval(applyAudioRoute, 3000);
};

export const stopAudioSession = () => {
  if (routeTimer) { clearInterval(routeTimer); routeTimer = null; }
  speakerForced = null;
  try { incall?.setForceSpeakerphoneOn(null); incall?.stop(); } catch { /* noop */ }
};
