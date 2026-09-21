import { create } from 'zustand';

type AccountSheetState = { visible: boolean; open: () => void; close: () => void };

export const useAccountSheet = create<AccountSheetState>((set) => ({
  visible: false,
  open: () => set({ visible: true }),
  close: () => set({ visible: false }),
}));
