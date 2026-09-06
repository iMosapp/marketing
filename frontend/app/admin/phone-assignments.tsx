import { Redirect } from 'expo-router';

// Retired: buying, assigning and pooling numbers all live in Phone Numbers now.
export default function PhoneAssignmentsRedirect() {
  return <Redirect href={'/admin/twilio-numbers' as any} />;
}
