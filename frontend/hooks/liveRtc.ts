// Web: the browser's WebRTC, remote audio through a hidden <audio> element.
export type LiveRtc = { PeerConnection: any; getUserMedia: (c: any) => Promise<any>; MediaStream: any; answer: (sdp: string) => any };

export const getRtc = (): LiveRtc | null => {
  if (typeof window === 'undefined' || !(window as any).RTCPeerConnection || !(navigator as any)?.mediaDevices?.getUserMedia) return null;
  return {
    PeerConnection: (window as any).RTCPeerConnection,
    getUserMedia: (c: any) => navigator.mediaDevices.getUserMedia(c),
    MediaStream: (window as any).MediaStream,
    answer: (sdp: string) => ({ type: 'answer', sdp }),
  };
};

export const attachRemoteAudio = (connection: any): (() => void) => {
  const audio = document.createElement('audio');
  audio.autoplay = true;
  audio.style.display = 'none';
  document.body.appendChild(audio);
  connection.addEventListener('track', (e: any) => {
    audio.srcObject = e.streams?.[0] || new (window as any).MediaStream([e.track]);
    audio.play().catch(() => { /* autoplay blocked: user already tapped, so this rarely fires */ });
  });
  return () => { audio.srcObject = null; audio.remove(); };
};

export const startAudioSession = () => {};
export const stopAudioSession = () => {};
export const nativeRtcMissing = false;
export const nativeRtcReason = '';
