import { Stack } from 'expo-router';

export default function SettingsLayout() {
  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="my-profile" />
      <Stack.Screen name="tags" />
      <Stack.Screen name="persona" />
      <Stack.Screen name="templates" />
      <Stack.Screen name="calendar" />
      <Stack.Screen name="review-links" />
      <Stack.Screen name="review-approvals" />
      <Stack.Screen name="congrats-template" />
      <Stack.Screen name="security" />
      <Stack.Screen name="store-profile" />
      <Stack.Screen name="integrations" />
      <Stack.Screen name="create-card" />
      <Stack.Screen name="card-templates" />
      <Stack.Screen name="showroom-approvals" />
      <Stack.Screen name="showcase-approvals" />
    </Stack>
  );
}
