import { Redirect } from 'expo-router';

// The VA Library became the Agent Hub.
export default function VALibraryRedirect() {
  return <Redirect href={'/admin/agents' as any} />;
}
