import { useEffect } from 'react';
import { create } from 'zustand';

type S = { blockers: number; offset: number; block: () => void; unblock: () => void; setOffset: (n: number) => void };
export const useHomeFabStore = create<S>(set => ({
  blockers: 0,
  offset: 0,
  block: () => set(s => ({ blockers: s.blockers + 1 })),
  unblock: () => set(s => ({ blockers: Math.max(0, s.blockers - 1) })),
  setOffset: offset => set({ offset }),
}));

// Mount inside any composer / sheet that owns the bottom-right corner: the Home pill hides while it is on screen.
export const useHideHomeFab = (active = true) => {
  useEffect(() => {
    if (!active) return;
    const { block, unblock } = useHomeFabStore.getState();
    block();
    return unblock;
  }, [active]);
};

// Mount inside a fixed bottom bar and feed it the bar's height: the Home pill floats above the bar instead of on it.
export const useHomeFabOffset = () => {
  const setOffset = useHomeFabStore(s => s.setOffset);
  useEffect(() => () => setOffset(0), [setOffset]);
  return (height: number) => setOffset(Math.round(height));
};
