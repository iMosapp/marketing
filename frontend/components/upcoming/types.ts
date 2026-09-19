export type UpcomingItem = {
  kind: 'task' | 'appointment' | 'auto_text' | 'manual_text' | 'date';
  id: string;
  at: string;
  date: string;
  time: string | null;
  all_day?: boolean;
  owner: 'you' | 'jessi';
  title: string;
  subtitle?: string;
  body?: string;
  contact_id: string;
  contact_name: string;
  contact_phone?: string;
  task_type?: string;
  source?: string;
  channel?: string;
  step?: number;
  has_media?: boolean;
  occasion?: 'birthday' | 'sold' | 'anniversary';
  years?: number | null;
  handled?: boolean;
};

export type UpcomingGroup = { date: string; items: UpcomingItem[] };

export type UpcomingData = {
  timezone: string;
  today: string;
  days: number;
  counts: { you: number; jessi: number; dates: number; total: number };
  groups: UpcomingGroup[];
};

export type UpcomingFilter = 'All' | 'Needs me' | 'Jessi' | 'Dates' | 'Appointments';
export const UPCOMING_FILTERS: UpcomingFilter[] = ['All', 'Needs me', 'Jessi', 'Dates', 'Appointments'];

export const GOLD = '#C9A962';

export const matchesFilter = (item: UpcomingItem, f: UpcomingFilter) => {
  if (f === 'All') return true;
  if (f === 'Needs me') return item.owner === 'you';
  if (f === 'Jessi') return item.owner === 'jessi';
  if (f === 'Dates') return item.kind === 'date';
  if (f === 'Appointments') return item.kind === 'appointment';
  return true;
};

export const kindVisual = (item: UpcomingItem): { icon: string; color: string } => {
  if (item.kind === 'appointment') return { icon: 'calendar', color: '#007AFF' };
  if (item.kind === 'auto_text') return { icon: item.channel === 'email' ? 'mail-outline' : 'chatbubble-ellipses-outline', color: GOLD };
  if (item.kind === 'manual_text') return { icon: 'send-outline', color: '#FF9500' };
  if (item.kind === 'date') {
    if (item.occasion === 'birthday') return { icon: 'gift-outline', color: '#34C759' };
    if (item.occasion === 'sold') return { icon: 'car-sport-outline', color: '#AF52DE' };
    return { icon: 'heart-outline', color: '#FF2D55' };
  }
  return { icon: 'checkbox-outline', color: '#5AC8FA' };
};

const DOW = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export const parseDay = (iso: string) => {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(y, m - 1, d);
};

export const addDays = (iso: string, n: number) => {
  const d = parseDay(iso);
  d.setDate(d.getDate() + n);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

export const dayLabel = (iso: string, today: string) => {
  if (iso === addDays(today, 1)) return 'Tomorrow';
  const d = parseDay(iso);
  return `${DOW[d.getDay()]} ${MON[d.getMonth()]} ${d.getDate()}`;
};

export const shortDay = (iso: string) => {
  const d = parseDay(iso);
  return { dow: DOW[d.getDay()], num: d.getDate() };
};
