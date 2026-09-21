// Design tokens: one palette (Gold = primary, Red = urgent, Green = success), one spacing and type scale.
export const GOLD = '#C9A962';
export const RED = '#FF3B30';
export const GREEN = '#34C759';
export const INK = '#1A1A1A';

export const SPACE = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 } as const;
export const RADIUS = { sm: 10, md: 14, lg: 18, xl: 22 } as const;
export const TYPE = { title: 28, section: 17, body: 15, sub: 13, caption: 12, label: 11 } as const;

/** '#RRGGBB' + alpha (0..1) -> rgba() */
export const tint = (hex: string, alpha: number) => {
  const h = hex.replace('#', '');
  const r = parseInt(h.slice(0, 2), 16), g = parseInt(h.slice(2, 4), 16), b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r},${g},${b},${alpha})`;
};

export const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });
