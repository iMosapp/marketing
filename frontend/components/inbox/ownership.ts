import api from '../../services/api';

export const GOLD = '#C9A962';
export const tid = (id: string) => ({ testID: id, dataSet: { testid: id } } as any);

export type RepCard = { id: string; name: string; role?: string; photo?: string | null; has_number?: boolean; active?: boolean; title?: string };
export type InboxLite = { id: string; name: string; color: string; members: string[]; phone_number?: string; counts?: { open: number; unassigned: number; mine: number } };
export type Ownership = {
  conversation_id: string;
  inbox: any | null;
  graduated: boolean;
  graduated_from: any | null;
  from_number?: string | null;
  owner: RepCard | null;
  collaborators: RepCard[];
  history: any[];
  handoff_note?: any;
  can: { claim: boolean; assign: boolean; release: boolean; move: boolean; share: boolean; graduate: boolean };
  inboxes: InboxLite[];
  members: RepCard[];
};

export const ownershipAPI = {
  get: (convId: string) => api.get(`/inboxes/conversations/${convId}/ownership`).then(r => r.data as Ownership),
  claim: (convId: string) => api.post(`/inboxes/conversations/${convId}/claim`).then(r => r.data),
  assign: (convId: string, user_id: string, note = '') => api.post(`/inboxes/conversations/${convId}/assign`, { user_id, note }).then(r => r.data),
  release: (convId: string, note = '') => api.post(`/inboxes/conversations/${convId}/release`, { note }).then(r => r.data),
  move: (convId: string, inbox_id: string, user_id: string | null, note = '') => api.post(`/inboxes/conversations/${convId}/move`, { inbox_id, user_id, note }).then(r => r.data),
  collaborator: (convId: string, user_id: string, add: boolean) => api.post(`/inboxes/conversations/${convId}/collaborators`, { user_id, add }).then(r => r.data),
  graduate: (convId: string) => api.post(`/inboxes/conversations/${convId}/graduate`).then(r => r.data),
  listInboxes: () => api.get('/inboxes').then(r => r.data),
  inboxConversations: (inboxId: string, view: string) => api.get(`/inboxes/${inboxId}/conversations`, { params: { view } }).then(r => r.data),
  teammates: () => api.get('/inboxes/members/options').then(r => (r.data?.users || []) as RepCard[]),
};

export const errText = (e: any, fallback = 'Something went wrong') => {
  const d = e?.response?.data?.detail;
  return typeof d === 'string' ? d : fallback;
};

export const fmtPhone = (p?: string | null) => (p || '').replace(/^\+?1?(\d{3})(\d{3})(\d{4})$/, '($1) $2-$3') || p || '';

export const firstName = (n?: string | null) => (n || '').trim().split(' ')[0] || 'Rep';

export const timeAgo = (ts?: string | null) => {
  if (!ts) return '';
  const ms = Date.now() - new Date(ts).getTime();
  const m = Math.floor(ms / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
};
