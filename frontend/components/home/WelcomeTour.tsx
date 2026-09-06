import React, { useEffect, useRef, useState } from 'react';
import { Modal, View, Text, TouchableOpacity, ScrollView, useWindowDimensions, NativeSyntheticEvent, NativeScrollEvent } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';

const GOLD = '#C9A962';
const RED = '#FF453A';
const GREEN = '#34C759';
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });

export const welcomeTourKey = (userId: string) => `welcome_tour_v1_${userId}`;

function MockCard({ children, style }: any) {
  return <View style={[{ width: '100%', borderRadius: 18, backgroundColor: '#161616', borderWidth: 1, borderColor: '#2A2A2A', padding: 14 }, style]}>{children}</View>;
}

function Pill({ label, color, dark }: { label: string; color: string; dark?: boolean }) {
  return (
    <View style={{ backgroundColor: color, borderRadius: 18, paddingHorizontal: 14, paddingVertical: 8 }}>
      <Text style={{ fontSize: 13, fontWeight: '800', color: dark ? '#000' : '#fff' }}>{label}</Text>
    </View>
  );
}

function Circle({ icon, color }: { icon: any; color: string }) {
  return (
    <View style={{ width: 32, height: 32, borderRadius: 16, borderWidth: 1, borderColor: color + '77', alignItems: 'center', justifyContent: 'center' }}>
      <Ionicons name={icon} size={16} color={color} />
    </View>
  );
}

const SLIDES = [
  {
    key: 'next',
    eyebrow: 'CARD 1',
    title: 'Do This Next',
    body: 'One action, already picked for you. Tap the gold button and it is done. Not today? Tap Skip.',
    mock: (
      <MockCard style={{ borderColor: GOLD + '66', borderWidth: 2, backgroundColor: GOLD + '10' }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 10 }}>
          <Ionicons name="arrow-forward-circle" size={14} color={GOLD} />
          <Text style={{ flex: 1, fontSize: 12, fontWeight: '700', color: GOLD, letterSpacing: 0.8 }}>DO THIS NEXT</Text>
          <Text style={{ fontSize: 12, fontWeight: '700', color: '#8E8E93' }}>Skip  ×</Text>
        </View>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
          <View style={{ width: 44, height: 44, borderRadius: 13, backgroundColor: GOLD + '22', alignItems: 'center', justifyContent: 'center' }}>
            <Ionicons name="chatbubble" size={22} color={GOLD} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 15, fontWeight: '800', color: '#fff' }}>Text Sarah Miller</Text>
            <Text style={{ fontSize: 12, color: '#8E8E93', marginTop: 2 }}>Opened the Tacoma link 20 min ago</Text>
          </View>
          <Pill label="Text" color={GOLD} />
        </View>
      </MockCard>
    ),
  },
  {
    key: 'my3',
    eyebrow: 'CARD 2',
    title: 'Your 3 for Today',
    body: 'Three people worth a 30-second text, with the reason. Text sends a message already written for you. The check means you handled it. X skips. Clear all three to keep your streak.',
    mock: (
      <MockCard>
        <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
          <Text style={{ fontSize: 15, fontWeight: '700', color: '#fff' }}>Your 3 for Today</Text>
          <View style={{ backgroundColor: GOLD + '20', borderRadius: 20, paddingHorizontal: 10, paddingVertical: 3 }}>
            <Text style={{ fontSize: 12, fontWeight: '700', color: GOLD }}>3/3</Text>
          </View>
        </View>
        <View style={{ borderRadius: 14, backgroundColor: '#1E1E1E', borderWidth: 1, borderColor: '#2E2E2E', overflow: 'hidden' }}>
          <View style={{ height: 3, backgroundColor: '#FF9500' }} />
          <View style={{ padding: 12 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <View style={{ width: 38, height: 38, borderRadius: 19, backgroundColor: '#FF950020', alignItems: 'center', justifyContent: 'center' }}>
                <Ionicons name="gift" size={18} color="#FF9500" />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 15, fontWeight: '700', color: '#fff' }}>Mike Torres</Text>
                <Text style={{ fontSize: 12, color: '#FF9500', marginTop: 1 }}>Birthday tomorrow</Text>
              </View>
            </View>
            <View style={{ flexDirection: 'row', justifyContent: 'flex-end', alignItems: 'center', gap: 8, marginTop: 10 }}>
              <Pill label="Text" color="#FF9500" />
              <Circle icon="checkmark" color={GREEN} />
              <Circle icon="close" color="#8E8E93" />
            </View>
          </View>
        </View>
      </MockCard>
    ),
  },
  {
    key: 'reply',
    eyebrow: 'CARD 3',
    title: 'Needs a Reply',
    body: 'Jessi, your AI assistant, answers texts for you 24/7. When a customer needs a real person you see a red WAITING badge. Tap it, reply, done. Sold a car? Hit the gold + and SOLD!',
    mock: (
      <MockCard>
        <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
          <Text style={{ fontSize: 15, fontWeight: '700', color: '#fff' }}>Needs a Reply</Text>
          <Text style={{ fontSize: 12, fontWeight: '700', color: GOLD }}>Open Inbox →</Text>
        </View>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 8 }}>
          <View style={{ width: 38, height: 38, borderRadius: 19, backgroundColor: '#2A2A2A', alignItems: 'center', justifyContent: 'center' }}>
            <Text style={{ fontSize: 13, fontWeight: '800', color: '#fff' }}>JW</Text>
          </View>
          <View style={{ flex: 1 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
              <Text style={{ fontSize: 15, fontWeight: '700', color: '#fff' }}>Jessi Ward</Text>
              <View style={{ backgroundColor: RED + '22', borderRadius: 6, paddingHorizontal: 6, paddingVertical: 2 }}>
                <Text style={{ fontSize: 10, fontWeight: '800', color: RED }}>WAITING 4m</Text>
              </View>
            </View>
            <Text style={{ fontSize: 12, color: '#8E8E93', marginTop: 2 }} numberOfLines={1}>"What's your best price on the truck?"</Text>
          </View>
          <Pill label="Reply" color={RED} />
        </View>
      </MockCard>
    ),
  },
];

interface Props { visible: boolean; onClose: () => void; }

export function WelcomeTour({ visible, onClose }: Props) {
  const { width } = useWindowDimensions();
  const [page, setPage] = useState(0);
  const scrollRef = useRef<ScrollView>(null);
  const last = page === SLIDES.length - 1;

  useEffect(() => { if (visible) { setPage(0); scrollRef.current?.scrollTo({ x: 0, animated: false }); } }, [visible]);

  const goTo = (i: number) => { scrollRef.current?.scrollTo({ x: i * width, animated: true }); setPage(i); };
  const onScroll = (e: NativeSyntheticEvent<NativeScrollEvent>) => setPage(Math.round(e.nativeEvent.contentOffset.x / width));

  return (
    <Modal visible={visible} animationType="fade" transparent statusBarTranslucent onRequestClose={onClose}>
      <View style={{ flex: 1, backgroundColor: '#0B0B0B' }} {...tid('welcome-tour')}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 20, paddingTop: 58 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            <Ionicons name="sparkles" size={14} color={GOLD} />
            <Text style={{ fontSize: 12, fontWeight: '800', color: GOLD, letterSpacing: 1 }}>WELCOME</Text>
          </View>
          <TouchableOpacity onPress={onClose} hitSlop={10} {...tid('welcome-tour-skip')}>
            <Text style={{ fontSize: 14, fontWeight: '600', color: '#8E8E93' }}>Skip</Text>
          </TouchableOpacity>
        </View>

        <ScrollView ref={scrollRef} horizontal pagingEnabled showsHorizontalScrollIndicator={false} onMomentumScrollEnd={onScroll} style={{ flex: 1 }}>
          {SLIDES.map((s, i) => (
            <View key={s.key} style={{ width, paddingHorizontal: 24, paddingTop: 28 }} {...tid(`welcome-tour-slide-${i}`)}>
              <Text style={{ fontSize: 12, fontWeight: '800', color: GOLD, letterSpacing: 1.2 }}>{s.eyebrow}</Text>
              <Text style={{ fontSize: 32, fontWeight: '800', color: '#fff', marginTop: 6, letterSpacing: -0.5 }}>{s.title}</Text>
              <Text style={{ fontSize: 16, lineHeight: 24, color: '#B0B0B0', marginTop: 12, marginBottom: 28 }}>{s.body}</Text>
              {s.mock}
            </View>
          ))}
        </ScrollView>

        <View style={{ paddingHorizontal: 24, paddingBottom: 44 }}>
          <View style={{ flexDirection: 'row', justifyContent: 'center', gap: 8, marginBottom: 20 }}>
            {SLIDES.map((_, i) => (
              <View key={i} style={{ width: i === page ? 22 : 8, height: 8, borderRadius: 4, backgroundColor: i === page ? GOLD : '#333' }} />
            ))}
          </View>
          <TouchableOpacity onPress={() => (last ? onClose() : goTo(page + 1))} activeOpacity={0.85}
            style={{ backgroundColor: GOLD, borderRadius: 28, paddingVertical: 16, alignItems: 'center' }} {...tid('welcome-tour-next')}>
            <Text style={{ fontSize: 16, fontWeight: '800', color: '#000' }}>{last ? "Let's go" : 'Next'}</Text>
          </TouchableOpacity>
          <Text style={{ textAlign: 'center', fontSize: 12, color: '#666', marginTop: 12 }}>
            {last ? 'Replay anytime from Tools > Learning > Help Center.' : `${page + 1} of ${SLIDES.length}`}
          </Text>
        </View>
      </View>
    </Modal>
  );
}

export async function shouldShowWelcomeTour(userId: string) {
  try { return !(await AsyncStorage.getItem(welcomeTourKey(userId))); } catch { return false; }
}

export async function markWelcomeTourSeen(userId: string) {
  try { await AsyncStorage.setItem(welcomeTourKey(userId), new Date().toISOString()); } catch {}
}
