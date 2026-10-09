import { useEffect } from 'react';
import { useRouter } from 'expo-router';

// The Advisor tab became the Team tab (Leadership Team Phase 1); old deep links land on Ask with the Strategic Advisor.
export default function AdvisorRedirect() {
  const router = useRouter();
  useEffect(() => { router.replace('/admin/command-center/team?view=ask&exec=strategic_advisor' as any); }, []);
  return null;
}
