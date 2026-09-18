import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { useRouter, usePathname } from 'expo-router';
import { useLiveJessi, LiveOptions, OpenTarget } from '../../hooks/useLiveJessi';
import { LiveJessiSheet } from './LiveJessiSheet';
import { LiveJessiPill } from './LiveJessiPill';

export type LiveLaunch = { options: LiveOptions; title?: string; who?: string; hint?: string; onClose?: () => void };
type Ctx = { open: (launch: LiveLaunch) => void; active: boolean };

const LiveJessiContext = createContext<Ctx>({ open: () => {}, active: false });
export const useLiveJessiLauncher = () => useContext(LiveJessiContext);

export const pathFor = (t: OpenTarget): string | null => {
  if (t.kind === 'contact' && t.id) return `/contact/${t.id}`;
  if (t.kind === 'thread' && t.id) return `/thread/${t.id}`;
  if (t.kind === 'task') return t.id ? `/touchpoints?highlight=${t.id}` : '/touchpoints';
  if (t.kind === 'tasks') return '/touchpoints';
  if (t.kind === 'home') return '/(tabs)/home';
  if (t.kind === 'inbox') return '/(tabs)/inbox';
  if (t.kind === 'duplicates') return '/contacts/duplicates';
  if (t.kind === 'mentions') return `/memory-search?q=${encodeURIComponent(t.query || '')}`;
  return null;
};

// App-wide home for the live conversation: it survives navigation, so Jessi can open a contact, a thread or a task
// underneath while the sheet shrinks into a floating pill and the rep keeps talking.
export const LiveJessiProvider = ({ children }: { children: React.ReactNode }) => {
  const router = useRouter();
  const pathname = usePathname();
  const pathRef = useRef(pathname);
  pathRef.current = pathname;
  const [launch, setLaunch] = useState<LiveLaunch | null>(null);
  const [expanded, setExpanded] = useState(true);
  const [target, setTarget] = useState<OpenTarget | null>(null);
  const launchRef = useRef<LiveLaunch | null>(null);

  const onOpen = useCallback((t: OpenTarget) => {
    const path = pathFor(t);
    if (!path) return;
    setTarget(t);
    setExpanded(false);
    const current = pathRef.current || '';
    const same = path.split('?')[0].replace('/(tabs)', '') === current.replace('/(tabs)', '');
    if (!same) setTimeout(() => { try { router.push(path as any); } catch { /* route missing on this platform */ } }, 120);
  }, [router]);

  const live = useLiveJessi({ onOpen });

  const close = useCallback(() => {
    launchRef.current?.onClose?.();
    launchRef.current = null;
    setLaunch(null);
    setExpanded(true);
    setTarget(null);
  }, []);

  const open = useCallback((l: LiveLaunch) => {
    if (launchRef.current && (live.state === 'live' || live.state === 'connecting')) { setExpanded(true); return; }
    launchRef.current = l;
    setLaunch(l);
    setTarget(null);
    setExpanded(true);
    live.start(l.options);
  }, [live]);

  // Ended while shrunk: leave the pill up for a moment so the rep sees why, then clear it.
  useEffect(() => {
    if (!launch || expanded || !(live.state === 'ended' || live.state === 'error')) return;
    const t = setTimeout(close, 3500);
    return () => clearTimeout(t);
  }, [launch, expanded, live.state, close]);

  return (
    <LiveJessiContext.Provider value={{ open, active: !!launch }}>
      {children}
      {launch && (
        <LiveJessiSheet visible={expanded} live={live} title={launch.title} who={launch.who} hint={launch.hint} onClose={close} onRetry={() => live.start(launch.options)}
          onCollapse={() => setExpanded(false)} />
      )}
      {launch && !expanded && <LiveJessiPill live={live} target={target} who={launch.who} onExpand={() => setExpanded(true)} onEnd={() => (live.state === 'live' || live.state === 'connecting' ? live.stop('close_requested') : close())} />}
    </LiveJessiContext.Provider>
  );
};
