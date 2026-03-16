import { Redirect, useLocalSearchParams } from 'expo-router';

export default function StoreShowcaseRedirect() {
  const { slug } = useLocalSearchParams();
  return <Redirect href={`/showcase/${slug}?scope=store`} />;
}
