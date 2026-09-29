import React, { useState } from 'react';
import { View, Text } from 'react-native';
import Svg, { Polyline, Line, Circle, Text as SvgText } from 'react-native-svg';
import { scoreColor, GOLD, GREEN, AMBER, tid } from './shared';
import { makeT, type Tr } from './i18n';

export type TrendPoint = { score: number; at?: string | null; label?: string; current?: boolean };

const PAD = { l: 30, r: 14, t: 16, b: 22 };
const dateOf = (p: TrendPoint) => p.label || (p.at ? new Date(p.at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : '');

// Every graded shop as a dot on one line, oldest to newest, with the 70 / 85 bands and the store line, so a climb (or a slide) reads in one glance.
export const ScoreTrendChart = ({ points, storeAvg, colors, height = 150, testID = 'score-trend-chart', tr = makeT('en') }: { points: TrendPoint[]; storeAvg?: number | null; colors: any; height?: number; testID?: string; tr?: Tr }) => {
  const [w, setW] = useState(0);
  const n = points.length;
  const iw = Math.max(0, w - PAD.l - PAD.r), ih = height - PAD.t - PAD.b;
  const x = (i: number) => PAD.l + (n <= 1 ? iw / 2 : (iw * i) / (n - 1));
  const y = (s: number) => PAD.t + ih * (1 - Math.max(0, Math.min(100, s)) / 100);
  const first = points[0]?.score, last = points[n - 1]?.score;
  const delta = n >= 2 ? last - first : null;
  return (
    <View style={{ gap: 6, width: '100%', maxWidth: 640 }} {...tid(testID)}>
      <View onLayout={e => setW(e.nativeEvent.layout.width)} style={{ height }}>
        {w > 0 && n > 0 && (
          <Svg width={w} height={height}>
            {[0, 50, 100].map(v => <Line key={v} x1={PAD.l} x2={w - PAD.r} y1={y(v)} y2={y(v)} stroke={colors.border} strokeWidth={1} />)}
            {[70, 85].map(v => <Line key={v} x1={PAD.l} x2={w - PAD.r} y1={y(v)} y2={y(v)} stroke={v === 70 ? AMBER : GREEN} strokeOpacity={0.4} strokeWidth={1} strokeDasharray="4 4" />)}
            {[0, 50, 100].map(v => <SvgText key={v} x={PAD.l - 6} y={y(v) + 4} fontSize={10} fill={colors.textSecondary} textAnchor="end">{String(v)}</SvgText>)}
            {storeAvg != null && <Line x1={PAD.l} x2={w - PAD.r} y1={y(storeAvg)} y2={y(storeAvg)} stroke={colors.text} strokeOpacity={0.5} strokeWidth={1.5} strokeDasharray="2 3" />}
            {n >= 2 && <Polyline points={points.map((p, i) => `${x(i)},${y(p.score)}`).join(' ')} fill="none" stroke={GOLD} strokeWidth={2.5} strokeLinejoin="round" strokeLinecap="round" />}
            {points.map((p, i) => <Circle key={i} cx={x(i)} cy={y(p.score)} r={p.current ? 7 : 4.5} fill={scoreColor(p.score)} stroke={p.current ? colors.text : colors.card} strokeWidth={2} />)}
            {n >= 2 && <SvgText x={x(0)} y={y(first) - 10} fontSize={11} fontWeight="700" fill={colors.textSecondary} textAnchor="start">{`${first}%`}</SvgText>}
            <SvgText x={x(n - 1)} y={y(last) - 11} fontSize={12} fontWeight="800" fill={scoreColor(last)} textAnchor={n === 1 ? 'middle' : 'end'}>{`${last}%`}</SvgText>
            <SvgText x={x(0)} y={height - 5} fontSize={10} fill={colors.textSecondary} textAnchor={n === 1 ? 'middle' : 'start'}>{dateOf(points[0])}</SvgText>
            {n >= 2 && <SvgText x={x(n - 1)} y={height - 5} fontSize={10} fill={colors.textSecondary} textAnchor="end">{dateOf(points[n - 1])}</SvgText>}
          </Svg>
        )}
      </View>
      <Text style={{ fontSize: 12, color: delta == null ? colors.textSecondary : delta > 0 ? GREEN : delta < 0 ? colors.textSecondary : colors.textSecondary, fontWeight: delta && delta > 0 ? '700' : '500' }} {...tid(`${testID}-caption`)}>
        {delta == null ? tr('chart.one') : delta > 0 ? tr('chart.up', { d: delta }) : delta < 0 ? tr('chart.down', { d: Math.abs(delta) }) : tr('chart.level')}
        {storeAvg != null && n >= 1 ? ` · ${tr('chart.store', { v: storeAvg })}` : ''}
      </Text>
    </View>
  );
};
