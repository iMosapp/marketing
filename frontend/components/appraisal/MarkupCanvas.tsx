import React, { useEffect, useMemo, useRef, useState } from 'react';
import { View, Text, Image, PanResponder } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { Ionicons } from '@expo/vector-icons';
import { tid } from '../inbox/ownership';

export type Pt = { x: number; y: number };
export type Stroke = Pt[];
export const MARKUP_RED = '#FF3B30';

// Where the photo really sits inside its box with resizeMode "contain": strokes are stored in photo space (0..1) so they land on the same dent on every screen.
export const fitRect = (boxW: number, boxH: number, imgW?: number, imgH?: number) => {
  if (!imgW || !imgH) return { x: 0, y: 0, w: boxW, h: boxH };
  const s = Math.min(boxW / imgW, boxH / imgH);
  const w = imgW * s, h = imgH * s;
  return { x: (boxW - w) / 2, y: (boxH - h) / 2, w, h };
};

export const useImageSize = (uri?: string) => {
  const [size, setSize] = useState<{ w: number; h: number } | null>(null);
  useEffect(() => {
    let live = true;
    setSize(null);
    if (uri) Image.getSize(uri, (w, h) => { if (live) setSize({ w, h }); }, () => {});
    return () => { live = false; };
  }, [uri]);
  return size;
};

const toPath = (s: Stroke, w: number, h: number) => s.map((p, i) => `${i ? 'L' : 'M'}${(p.x * w).toFixed(1)} ${(p.y * h).toFixed(1)}`).join(' ');

type LayerProps = { rect: { x: number; y: number; w: number; h: number }; markups?: any[]; strokes?: Stroke[]; drawing?: boolean; color?: string; onStrokesChange?: (s: Stroke[]) => void; testId?: string };

// Red ink over a photo: everything already sent by a manager, plus whatever is being drawn right now. Finger down = new stroke; the box swallows touches only while drawing.
// `strokes` are the committed strokes (parent state, undo/clear work on them); the stroke under the finger lives here until release.
export const MarkupLayer = ({ rect, markups = [], strokes = [], drawing, color = MARKUP_RED, onStrokesChange, testId = 'markup-layer' }: LayerProps) => {
  const liveRef = useRef<Stroke>([]);
  const [live, setLive] = useState<Stroke>([]);
  const committed = useRef<Stroke[]>(strokes);
  const off = useRef<{ x: number; y: number } | null>(null);
  const box = useRef<View>(null);
  useEffect(() => { committed.current = strokes; }, [strokes]);
  const point = (e: any): Pt | null => {
    const n = e.nativeEvent || e;
    let x = n.locationX, y = n.locationY;
    if (!(Number.isFinite(x) && Number.isFinite(y)) && off.current) { x = n.pageX - off.current.x; y = n.pageY - off.current.y; }
    if (!(Number.isFinite(x) && Number.isFinite(y)) || !rect.w || !rect.h) return null;
    return { x: Math.min(1, Math.max(0, x / rect.w)), y: Math.min(1, Math.max(0, y / rect.h)) };
  };
  const pan = useMemo(() => PanResponder.create({
    onStartShouldSetPanResponder: () => !!drawing,
    onMoveShouldSetPanResponder: () => !!drawing,
    onPanResponderTerminationRequest: () => false,
    onPanResponderGrant: (e) => {
      box.current?.measureInWindow?.((x, y) => { off.current = { x, y }; });
      const p = point(e);
      liveRef.current = p ? [p] : [];
      setLive(liveRef.current);
    },
    onPanResponderMove: (e) => {
      const p = point(e);
      if (!p) return;
      const last = liveRef.current[liveRef.current.length - 1];
      if (last && Math.abs(last.x - p.x) < 0.002 && Math.abs(last.y - p.y) < 0.002) return;
      liveRef.current = [...liveRef.current, p];
      setLive(liveRef.current);
    },
    onPanResponderRelease: () => {
      if (liveRef.current.length >= 2) onStrokesChange?.([...committed.current, liveRef.current]);
      liveRef.current = [];
      setLive([]);
    },
    onPanResponderTerminate: () => { liveRef.current = []; setLive([]); },
  }), [drawing, rect.w, rect.h]);
  const sw = Math.max(2.5, rect.w / 160);
  const ink = live.length ? [...strokes, live] : strokes;
  return (
    <View ref={box} pointerEvents={drawing ? 'box-only' : 'none'} style={{ position: 'absolute', left: rect.x, top: rect.y, width: rect.w, height: rect.h }} {...(drawing ? pan.panHandlers : {})} {...tid(testId)}>
      <Svg width={rect.w} height={rect.h} pointerEvents="none">
        {markups.map((k: any) => (k.strokes || []).map((s: Stroke, i: number) => <Path key={`${k.id}-${i}`} d={toPath(s, rect.w, rect.h)} stroke={k.color || MARKUP_RED} strokeWidth={sw} fill="none" strokeLinecap="round" strokeLinejoin="round" />))}
        {ink.map((s, i) => <Path key={`live-${i}`} d={toPath(s, rect.w, rect.h)} stroke={color} strokeWidth={sw} fill="none" strokeLinecap="round" strokeLinejoin="round" strokeOpacity={0.95} />)}
      </Svg>
    </View>
  );
};

// Tiny pen badge on a thumbnail: a manager drew on this one.
export const MarkupBadge = ({ count, testId }: { count?: number; testId?: string }) => {
  if (!count) return null;
  return (
    <View style={{ position: 'absolute', right: 5, top: 5, flexDirection: 'row', alignItems: 'center', gap: 2, backgroundColor: MARKUP_RED, borderRadius: 7, paddingHorizontal: 5, paddingVertical: 2 }} {...(testId ? tid(testId) : {})}>
      <Ionicons name="brush" size={9} color="#fff" />{count > 1 ? <Text style={{ fontSize: 9.5, fontWeight: '800', color: '#fff' }}>{count}</Text> : null}
    </View>
  );
};
