import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView, useWindowDimensions } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import api from '../../../services/api';
import { useThemeStore } from '../../../store/themeStore';
import { useToast } from '../../../components/common/Toast';
import { CcShell } from '../../../components/command-center/CcShell';
import { Roster } from '../../../components/command-center/team/Roster';
import { useAsk } from '../../../components/command-center/team/AskExecutive';
import { Roundtables } from '../../../components/command-center/team/Roundtables';
import { RoundtableView } from '../../../components/command-center/team/RoundtableView';
import { Decisions } from '../../../components/command-center/team/Decisions';
import { Knowledge } from '../../../components/command-center/team/Knowledge';
import { Controls } from '../../../components/command-center/team/Controls';
import { OperatingReview } from '../../../components/command-center/team/OperatingReview';
import { GOLD, RED, detail, bounceIfPrivate, tid, type Executive, type TeamControls } from '../../../components/command-center/shared';

const VIEWS = [['roster', 'Team'], ['ask', 'Ask'], ['roundtables', 'Roundtables'], ['decisions', 'Decisions'], ['knowledge', 'Knowledge'], ['controls', 'Controls']] as const;
type ViewKey = typeof VIEWS[number][0];

// THE LEADERSHIP TEAM: seven AI executives who read the company, advise, challenge each other and prepare decisions. You decide; nothing changes without your click.
export default function LeadershipTeam() {
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const router = useRouter();
  const params = useLocalSearchParams<{ view?: string; exec?: string; thread?: string; rt?: string }>();
  const { width } = useWindowDimensions();
  const wide = width >= 1024;
  const [execs, setExecs] = useState<Executive[] | null>(null);
  const [controls, setControls] = useState<TeamControls | null>(null);
  const [spend, setSpend] = useState(0);
  const [view, setView] = useState<ViewKey>((VIEWS.some(([k]) => k === params.view) ? params.view : 'roster') as ViewKey);
  const [askKey, setAskKey] = useState<string | undefined>(params.exec);
  const [askThread, setAskThread] = useState<string | undefined>(params.thread);
  const [rtId, setRtId] = useState<string | null>(params.rt || null);
  const [prefill, setPrefill] = useState('');

  const load = useCallback(async () => {
    try { const r = (await api.get('/command-center/team/roster')).data; setExecs(r.executives); setControls(r.controls); setSpend(r.month_spend_usd); }
    catch (e: any) { if (!bounceIfPrivate(e, router)) showToast(detail(e, 'Could not load the team'), 'error'); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const goAsk = (key: string) => { setAskKey(key); setAskThread(undefined); setView('ask'); };
  const ask = useAsk({ execs: execs || [], colors, wide, initialKey: askKey, initialThread: askThread, onConvene: (q, threadId) => { setPrefill(q); setRtId(null); setView('roundtables'); if (threadId) setAskThread(threadId); } });
  const openRt = (id: string) => { setRtId(id); setView('roundtables'); };
  const n = (execs || []).filter(e => e.enabled && !e.is_orchestrator).length;
  const subtitle = execs ? `${n} executives on the team · $${spend.toFixed(2)} this month${controls?.stopped ? ' · EMERGENCY STOP ON' : ''}` : undefined;

  const Nav = (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6 }} {...tid('cc-team-views')}>
      {VIEWS.map(([k, label]) => (
        <TouchableOpacity key={k} onPress={() => { setView(k); if (k !== 'roundtables') setRtId(null); }} style={{ paddingHorizontal: 12, height: 30, borderRadius: 15, alignItems: 'center', justifyContent: 'center', backgroundColor: view === k ? colors.text : 'transparent', borderWidth: 1, borderColor: view === k ? colors.text : colors.border }} {...tid(`cc-team-view-${k}`)}>
          <Text style={{ fontSize: 12.5, fontWeight: '800', color: view === k ? colors.bg : colors.textSecondary }}>{label}</Text>
        </TouchableOpacity>
      ))}
    </ScrollView>
  );
  const body = () => {
    if (!execs) return null;
    switch (view) {
      case 'roster': return <View style={{ gap: 16 }}><OperatingReview colors={colors} execs={execs} /><Roster execs={execs} colors={colors} onAsk={goAsk} onTalk={k => { goAsk(k); setTimeout(() => ask.talk(k), 50); }} onChanged={load} /></View>;
      case 'ask': return wide ? <View style={{ flexDirection: 'row', gap: 20 }}>{ask.Threads}{ask.Chat}</View> : ask.Chat;
      case 'roundtables': return rtId ? <RoundtableView id={rtId} colors={colors} execs={execs} onBack={() => setRtId(null)} onChanged={load} /> : <Roundtables colors={colors} execs={execs} prefill={prefill} onOpen={openRt} />;
      case 'decisions': return <Decisions colors={colors} onOpen={openRt} />;
      case 'knowledge': return <Knowledge colors={colors} onChanged={load} />;
      case 'controls': return <Controls colors={colors} onChanged={load} />;
    }
  };
  return (
    <CcShell title="Leadership Team" subtitle={subtitle} loading={execs === null} footer={view === 'ask' ? ask.Composer : undefined}>
      {controls?.stopped && <View style={{ padding: 10, borderRadius: 12, backgroundColor: RED + '1A', borderWidth: 1, borderColor: RED }} {...tid('cc-stop-banner')}><Text style={{ fontSize: 13, fontWeight: '800', color: RED }}>Emergency stop is on. No executive answers until you resume it in Controls.</Text></View>}
      {Nav}
      {body()}
    </CcShell>
  );
}
