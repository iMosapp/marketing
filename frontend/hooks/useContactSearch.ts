import { useEffect, useRef } from 'react';
import { contactsAPI } from '../services/api';

// Server-side contact search — searches the FULL contact book, not just the first 50 loaded.
// When the query is cleared, restores the default first page.
export function useContactSearch(
  userId: string | undefined,
  query: string,
  setContacts: (contacts: any[]) => void,
  enabled: boolean = true,
) {
  const didSearch = useRef(false);
  useEffect(() => {
    if (!enabled || !userId) return;
    const q = query.trim();
    const searching = q.length >= 2;
    if (!searching && !didSearch.current) return;
    didSearch.current = searching;
    // Numeric queries: strip formatting so phone search matches; multi-word names: search first word (local filter narrows the rest)
    let qSend = /^[\d\s\-()+.]+$/.test(q) ? q.replace(/\D/g, '') : q;
    if (qSend.includes(' ')) qSend = qSend.split(/\s+/)[0];
    const t = setTimeout(async () => {
      try {
        const data = await contactsAPI.getAll(userId, searching ? qSend : undefined);
        setContacts(Array.isArray(data) ? data : ((data as any)?.contacts || []));
      } catch {}
    }, 250);
    return () => clearTimeout(t);
  }, [userId, query, enabled]);
}
