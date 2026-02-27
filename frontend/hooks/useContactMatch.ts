import { useState } from 'react';
import api from '../services/api';

type MatchData = {
  contact_id: string;
  existing_name: string;
  provided_name: string;
  phone?: string;
  email?: string;
};

type EventPayload = {
  phone?: string;
  email?: string;
  name?: string;
  event_type: string;
  event_title: string;
  event_description: string;
  event_icon: string;
  event_color: string;
};

export function useContactMatch(userId: string | undefined) {
  const [matchData, setMatchData] = useState<MatchData | null>(null);
  const [showMatchModal, setShowMatchModal] = useState(false);
  const [pendingPayload, setPendingPayload] = useState<EventPayload | null>(null);
  const [pendingCallback, setPendingCallback] = useState<(() => void) | null>(null);

  const findOrCreateAndLog = async (
    payload: EventPayload,
    onComplete?: () => void,
  ): Promise<boolean> => {
    if (!userId) return false;
    if (!payload.phone && !payload.email) return false;

    try {
      const res = await api.post(`/contacts/${userId}/find-or-create-and-log`, payload);

      if (res.data.needs_confirmation) {
        setMatchData(res.data);
        setPendingPayload(payload);
        setPendingCallback(() => onComplete || null);
        setShowMatchModal(true);
        return false; // Not done yet — needs user input
      }

      return true; // Success — event logged
    } catch (err) {
      console.error('Failed to find-or-create contact:', err);
      return false;
    }
  };

  const resolveMatch = async (action: 'use_existing' | 'update_name' | 'create_new') => {
    if (!userId || !pendingPayload) return;

    try {
      await api.post(`/contacts/${userId}/find-or-create-and-log`, {
        ...pendingPayload,
        force_action: action,
      });
    } catch (err) {
      console.error('Failed to resolve contact match:', err);
    }

    setShowMatchModal(false);
    setMatchData(null);
    setPendingPayload(null);
    if (pendingCallback) {
      pendingCallback();
      setPendingCallback(null);
    }
  };

  const cancelMatch = () => {
    setShowMatchModal(false);
    setMatchData(null);
    setPendingPayload(null);
    setPendingCallback(null);
  };

  return {
    matchData,
    showMatchModal,
    findOrCreateAndLog,
    resolveMatch,
    cancelMatch,
  };
}
