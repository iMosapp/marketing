import React, { useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { LiveJessiPill } from '../components/jessi/LiveJessiPill';
import { useHomeFabOffset } from '../store/homeFabStore';

// TEMPORARY test harness for the Live Jessi bar (preview has no live voice). Delete after testing.
export default function DevPillPreview() {
  const lift = useHomeFabOffset();
  const [warn, setWarn] = useState(false);
  const [taps, setTaps] = useState(0);
  const live: any = { rows: [{ role: 'jessi', text: 'Brian is up. What do you want to do?' }], state: 'live', quiet: { level: warn ? 'warning' : 'ok', closeIn: 8 }, seconds: 15, working: '', keepGoing: () => {} };
  return (
    <View style={{ flex: 1, backgroundColor: '#000' }}>
      <View style={{ flex: 1, padding: 20, gap: 12 }}>
        <Text style={{ color: '#fff', fontSize: 28 }}>Brian King</Text>
        <Text style={{ color: '#fff' }} testID="dev-expand-count">expand taps: {taps}</Text>
        <TouchableOpacity onPress={() => setWarn(w => !w)} testID="dev-toggle-warning"><Text style={{ color: '#C9A962' }}>Toggle silence warning ({warn ? 'on' : 'off'})</Text></TouchableOpacity>
      </View>
      <View onLayout={e => lift(e.nativeEvent.layout.height)} style={{ paddingTop: 8, paddingBottom: 14, paddingHorizontal: 12, borderTopWidth: 1, borderTopColor: '#222' }}>
        <View style={{ height: 52, borderRadius: 26, backgroundColor: '#1C1C1E', justifyContent: 'center', paddingLeft: 20, marginRight: 70 }}><Text style={{ color: '#8E8E93', fontSize: 17 }}>Message Brian...</Text></View>
      </View>
      <LiveJessiPill live={live} target={{ kind: 'contact', first: 'Brian' } as any} onExpand={() => setTaps(t => t + 1)} onEnd={() => {}} />
    </View>
  );
}
