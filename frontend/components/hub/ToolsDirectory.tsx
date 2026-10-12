// All Tools as a directory: on a computer, a left rail of collapsible groups beside the selected group's tools;
// on a phone, one clean column of gold-labelled groups. Rows match the account sheet (icon, name, hairline divider).
import React, { useEffect, useMemo, useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView, useWindowDimensions, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

const GOLD = '#C9A962';
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });

export type ToolRow = { title: string; subtitle?: string; icon: string; color?: string; onPress: () => void; badge?: number; statusDot?: 'green' | 'red' | 'grey' };
export type ToolGroup = { id: string; title: string; icon: string; items: ToolRow[] };

type Props = { groups: ToolGroup[]; colors: any; query?: string; bottom?: React.ReactNode; pinnedIds?: string[]; onTogglePin?: (id: string) => void };

export const toolId = (title: string) => title.toLowerCase().replace(/&/g, 'and').replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');

const Row = ({ item, colors, last, detail, pinned, onPin }: { item: ToolRow; colors: any; last: boolean; detail?: boolean; pinned?: boolean; onPin?: () => void }) => (
  <TouchableOpacity onPress={item.onPress} activeOpacity={0.7}
    style={{ flexDirection: 'row', alignItems: 'center', gap: 14, paddingVertical: detail ? 12 : 13, borderBottomWidth: last ? 0 : 0.5, borderBottomColor: colors.border }}
    {...tid(`tool-row-${item.title.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`)}>
    <Ionicons name={item.icon as any} size={20} color={detail && item.color ? item.color : colors.textSecondary} style={{ width: 24, textAlign: 'center' }} />
    <View style={{ flex: 1, minWidth: 0 }}>
      <Text style={{ fontSize: 16, color: colors.text }} numberOfLines={1}>{item.title}</Text>
      {detail && !!item.subtitle && <Text style={{ fontSize: 12.5, color: colors.textSecondary, marginTop: 2 }} numberOfLines={1}>{item.subtitle}</Text>}
    </View>
    {!!item.badge && <View style={{ minWidth: 20, height: 20, borderRadius: 10, backgroundColor: '#FF3B30', alignItems: 'center', justifyContent: 'center', paddingHorizontal: 6 }}><Text style={{ fontSize: 11, fontWeight: '800', color: '#fff' }}>{item.badge}</Text></View>}
    {!!item.statusDot && <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: item.statusDot === 'green' ? '#34C759' : item.statusDot === 'red' ? '#FF3B30' : '#8E8E93' }} />}
    {!!onPin && (
      <TouchableOpacity onPress={(e: any) => { e?.stopPropagation?.(); onPin(); }} hitSlop={10} {...tid(`pin-${toolId(item.title)}`)}>
        <Ionicons name={pinned ? 'bookmark' : 'bookmark-outline'} size={16} color={pinned ? GOLD : colors.textTertiary} />
      </TouchableOpacity>
    )}
    <Ionicons name="chevron-forward" size={15} color={colors.border} />
  </TouchableOpacity>
);

const Label = ({ children }: { children: string }) => (
  <Text style={{ fontSize: 11, fontWeight: '700', letterSpacing: 1.4, color: GOLD, marginBottom: 6, textTransform: 'uppercase' }}>{children}</Text>
);

export function ToolsDirectory({ groups, colors, query = '', bottom, pinnedIds, onTogglePin }: Props) {
  const pinProps = (it: ToolRow) => onTogglePin ? { pinned: !!pinnedIds?.includes(toolId(it.title)), onPin: () => onTogglePin(toolId(it.title)) } : {};
  const { width } = useWindowDimensions();
  const wide = width >= 900;
  const q = query.trim().toLowerCase();
  const visible = useMemo(() => {
    if (!q) return groups.filter(g => g.items.length);
    return groups.map(g => ({ ...g, items: g.items.filter(i => `${i.title} ${i.subtitle || ''}`.toLowerCase().includes(q)) })).filter(g => g.items.length);
  }, [groups, q]);
  const [active, setActive] = useState<string>(visible[0]?.id || '');
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const { height } = useWindowDimensions();
  useEffect(() => { if (!visible.find(g => g.id === active) && visible[0]) setActive(visible[0].id); }, [visible, active]);
  const current = visible.find(g => g.id === active) || visible[0];

  if (!visible.length) {
    return <Text style={{ fontSize: 13, color: colors.textTertiary, textAlign: 'center', marginTop: 24 }} {...tid('tools-directory-empty')}>Nothing found{q ? ` for "${query.trim()}"` : ''}.</Text>;
  }

  if (!wide) {
    return (
      <View style={{ paddingHorizontal: 16, gap: 18 }} {...tid('tools-directory-phone')}>
        {visible.map(g => {
          const open = q ? true : !collapsed[g.id];
          return (
            <View key={g.id} {...tid(`tool-group-${g.id}`)}>
              <TouchableOpacity onPress={() => setCollapsed(c => ({ ...c, [g.id]: !c[g.id] }))} style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }} {...tid(`tool-group-toggle-${g.id}`)}>
                <View style={{ flex: 1 }}><Label>{g.title}</Label></View>
                <Text style={{ fontSize: 11, color: colors.textTertiary, marginBottom: 6 }}>{g.items.length}</Text>
                <Ionicons name={open ? 'chevron-up' : 'chevron-down'} size={14} color={colors.textTertiary} style={{ marginBottom: 6 }} />
              </TouchableOpacity>
              {open && <View style={{ backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 14 }}>{g.items.map((it, i) => <Row key={it.title} item={it} colors={colors} last={i === g.items.length - 1} {...pinProps(it)} />)}</View>}
            </View>
          );
        })}
        {bottom}
      </View>
    );
  }

  const twoCol = width >= 1240 && current && current.items.length > 6;
  const half = current ? Math.ceil(current.items.length / 2) : 0;
  const cols = current ? (twoCol ? [current.items.slice(0, half), current.items.slice(half)] : [current.items]) : [];
  return (
    <View style={{ flexDirection: 'row', alignItems: 'flex-start', paddingHorizontal: 16, gap: 18 }} {...tid('tools-directory-wide')}>
      <ScrollView style={{ width: 272, flexGrow: 0, flexShrink: 0, maxHeight: Math.max(360, height - 300), backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: colors.border }} contentContainerStyle={{ paddingVertical: 8, paddingHorizontal: 10 }} showsVerticalScrollIndicator={false} {...tid('tools-rail')}>
        {visible.map(g => {
          const isActive = g.id === current?.id;
          const open = q ? true : (expanded[g.id] ?? isActive);
          return (
            <View key={g.id} style={{ marginBottom: 2 }}>
              <TouchableOpacity onPress={() => { setActive(g.id); setExpanded(e => ({ ...e, [g.id]: isActive ? !(e[g.id] ?? true) : true })); }}
                style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10, paddingHorizontal: 10, borderRadius: 10, backgroundColor: isActive ? `${GOLD}1F` : 'transparent', borderWidth: 1, borderColor: isActive ? `${GOLD}55` : 'transparent' }}
                {...tid(`tools-rail-${g.id}`)}>
                <Ionicons name={g.icon as any} size={18} color={isActive ? GOLD : colors.textSecondary} />
                <Text style={{ flex: 1, fontSize: 15, fontWeight: isActive ? '700' : '600', color: isActive ? GOLD : colors.text }}>{g.title}</Text>
                <Ionicons name={open ? 'chevron-down' : 'chevron-forward'} size={14} color={colors.textTertiary} />
              </TouchableOpacity>
              {open && (
                <View style={{ paddingLeft: 38, paddingBottom: 6 }}>
                  {g.items.map(it => (
                    <TouchableOpacity key={it.title} onPress={it.onPress} style={{ paddingVertical: 6, flexDirection: 'row', alignItems: 'center', gap: 6 }} {...tid(`tools-rail-item-${it.title.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`)}>
                      <Text style={{ flex: 1, fontSize: 14, color: colors.textSecondary }} numberOfLines={1}>{it.title}</Text>
                      {!!it.badge && <View style={{ minWidth: 18, height: 18, borderRadius: 9, backgroundColor: '#FF3B30', alignItems: 'center', justifyContent: 'center', paddingHorizontal: 5 }}><Text style={{ fontSize: 10, fontWeight: '800', color: '#fff' }}>{it.badge}</Text></View>}
                    </TouchableOpacity>
                  ))}
                </View>
              )}
            </View>
          );
        })}
      </ScrollView>
      <View style={{ flex: 1, minWidth: 0, ...(Platform.OS === 'web' ? ({ position: 'sticky', top: 12 } as any) : {}) }}>
        {current && (
          <View style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 18 }} {...tid(`tools-detail-${current.id}`)}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 8 }}>
              <Ionicons name={current.icon as any} size={20} color={GOLD} />
              <Text style={{ fontSize: 20, fontWeight: '800', color: colors.text }}>{current.title}</Text>
              <Text style={{ fontSize: 12, color: colors.textTertiary }}>{current.items.length} tools</Text>
            </View>
            <View style={{ flexDirection: 'row', gap: 28 }}>
              {cols.map((col, ci) => (
                <View key={ci} style={{ flex: 1, minWidth: 0 }}>
                  {col.map((it, i) => <Row key={it.title} item={it} colors={colors} last={i === col.length - 1} detail {...pinProps(it)} />)}
                </View>
              ))}
            </View>
          </View>
        )}
        {bottom}
      </View>
    </View>
  );
}
