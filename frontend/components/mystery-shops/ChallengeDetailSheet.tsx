import React from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Sheet, Label, GoldButton, deptLabel, industryOfDept, industries, GOLD, RED, AMBER, GREEN, PURPLE, tid, type Challenge, type Dept } from './shared';

export const needsReview = (c: Challenge) => c.review?.status === 'needs_review';
const LANG_NAME: Record<string, string> = { nl: 'DUTCH', 'en-GB': 'BRITISH ENGLISH' };

// Read-only view of one challenge with edit + delete/hide in the footer. Localized drafts get an Approve button for the native reviewer.
export const ChallengeDetailSheet = ({ open, onClose, colors, onEdit, onDelete, onApprove }: { open: Challenge | null; onClose: () => void; colors: any; onEdit: (c: Challenge) => void; onDelete: (c: Challenge) => void; onApprove?: (c: Challenge, approved: boolean) => void }) => (
  <Sheet visible={!!open} onClose={onClose} title={open?.title || ''} colors={colors} testID="challenge-detail"
    footer={open ? (
      <View style={{ gap: 10 }}>
        {!!onApprove && open.language && open.language !== 'en' && (needsReview(open)
          ? <GoldButton label="Approve, sounds like a native speaker" onPress={() => onApprove(open, true)} testID="challenge-approve" icon="checkmark-circle" color={GREEN} />
          : <GoldButton label="Send back for review" onPress={() => onApprove(open, false)} testID="challenge-unapprove" icon="arrow-undo-outline" outline color={AMBER} />)}
        <View style={{ flexDirection: 'row', gap: 10 }}>
          <View style={{ flex: 1 }}><GoldButton label="Edit" onPress={() => onEdit(open)} testID="challenge-edit" icon="create-outline" /></View>
          <View style={{ flex: 1 }}><GoldButton label={open.client_specific ? 'Delete' : 'Hide everywhere'} onPress={() => onDelete(open)} testID="challenge-delete" outline color={RED} icon="trash-outline" /></View>
        </View>
      </View>
    ) : undefined}>
    {open && (
      <>
        <Text style={{ fontSize: 12.5, fontWeight: '800', color: GOLD }}>{industryOfDept(open.department).label.toUpperCase()} · {(open.department_label || deptLabel(open.department)).toUpperCase()}{open.direction === 'outbound' ? ' · OUTBOUND (REP CALLS THEM)' : ' · INBOUND (THEY CALL IN)'}{open.runtime ? ` · ${open.runtime}` : ''}{open.generated ? ' · WRITTEN BY JESSI' : ''}{open.language && open.language !== 'en' ? ` · ${LANG_NAME[open.language] || open.language.toUpperCase()}` : ''}</Text>
        {open.language && open.language !== 'en' && (
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: (needsReview(open) ? AMBER : GREEN) + '1A', borderRadius: 12, padding: 10, borderWidth: 1, borderColor: (needsReview(open) ? AMBER : GREEN) + '66' }} {...tid('challenge-review-state')}>
            <Ionicons name={needsReview(open) ? 'eye-outline' : 'checkmark-circle'} size={16} color={needsReview(open) ? AMBER : GREEN} />
            <Text style={{ flex: 1, fontSize: 12.5, color: colors.text, lineHeight: 17 }}>{needsReview(open) ? 'Jessi adapted this from the English version. A native speaker needs to read it before the caller uses it. Edit anything that sounds off, then approve.' : `Approved${open.review?.by_name ? ` by ${open.review.by_name}` : ''}. The caller can use it.`}</Text>
          </View>
        )}
        {!!open.purpose && <Text style={{ fontSize: 14.5, color: colors.textSecondary, fontStyle: 'italic', lineHeight: 20 }}>{open.purpose}</Text>}
        <View style={{ gap: 4 }}><Label t="WHAT A GREAT REP DOES" colors={colors} /><Text style={{ fontSize: 14.5, color: colors.text, lineHeight: 21 }}>{open.body}</Text></View>
        {open.success_points?.length > 0 && <View style={{ gap: 4 }}><Label t="GRADED POINTS" colors={colors} />{open.success_points.map((p, i) => <Text key={i} style={{ fontSize: 13.5, color: colors.text }}>• {p}</Text>)}</View>}
        {!!open.curveballs?.length && <View style={{ gap: 4 }}><Label t="CURVEBALLS" colors={colors} />{open.curveballs.map((p, i) => <Text key={i} style={{ fontSize: 13.5, color: colors.text }}>• {p}</Text>)}</View>}
        {open.persona && (
          <View style={{ gap: 4, backgroundColor: colors.card, borderRadius: 14, padding: 12, borderWidth: 1, borderColor: colors.border }}>
            <Label t={`THE ${industryOfDept(open.department).customer.toUpperCase()} · ${open.persona.name}`} colors={colors} />
            <Text style={{ fontSize: 13.5, color: colors.text, lineHeight: 19 }}>{open.persona.summary}</Text>
            {!!open.persona.goals && <Text style={{ fontSize: 13, color: colors.textSecondary }}>Wants: {open.persona.goals}</Text>}
            {!!open.persona.opening_line && <Text style={{ fontSize: 13, color: colors.textSecondary }}>Opens with: "{open.persona.opening_line}"</Text>}
            {(open.persona.objections || []).map((o: string, i: number) => <Text key={i} style={{ fontSize: 13, color: colors.textSecondary }}>Pushback: {o}</Text>)}
          </View>
        )}
      </>
    )}
  </Sheet>
);

// Challenges grouped by department, with the purple THIS CLIENT badge for client-only ones and an amber NEEDS REVIEW badge for unapproved translations.
// `departments` = the account's (or the picked industry's) departments; without it every industry that has rows is shown.
export const ChallengeGroups = ({ rows, colors, onOpen, emptyHint, departments, renderEmpty }: { rows: Challenge[] | null; colors: any; onOpen: (c: Challenge) => void; emptyHint?: string; departments?: Dept[]; renderEmpty?: (d: Dept) => React.ReactNode }) => {
  if (rows === null) return <ActivityIndicator color={GOLD} />;
  const known = new Set(departments?.map(d => d.key) || industries().flatMap(i => i.departments.map(d => d.key)));
  const stray = [...new Set(rows.map(r => r.department).filter(k => !known.has(k)))].map(k => ({ key: k, label: deptLabel(k) }));
  const groups: Dept[] = departments ? [...departments, ...stray] : [...industries().flatMap(i => i.departments.filter(d => rows.some(r => r.department === d.key))), ...stray];
  return (
    <>
      {groups.map(d => {
        const list = rows.filter(r => r.department === d.key);
        const who = industryOfDept(d.key).customer;
        return (
          <View key={d.key} style={{ gap: 8 }} {...tid(`challenge-group-${d.key}`)}>
            <Label t={`${d.label.toUpperCase()} · ${list.length} IN THE POOL`} colors={colors} />
            {list.length === 0 && (renderEmpty ? renderEmpty(d) : <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>{emptyHint || 'Nothing here yet.'}</Text>)}
            {list.map(c => (
              <TouchableOpacity key={c.id} onPress={() => onOpen(c)} style={{ backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: needsReview(c) ? AMBER + '88' : c.client_specific ? PURPLE + '88' : colors.border, padding: 12, gap: 4 }} {...tid(`challenge-${c.id}`)}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                  <Text style={{ flex: 1, fontSize: 14.5, fontWeight: '800', color: colors.text }}>{c.title}</Text>
                  {c.generated && <Ionicons name="sparkles" size={14} color={GOLD} />}
                  {needsReview(c) && <View style={{ paddingHorizontal: 8, height: 22, borderRadius: 11, backgroundColor: AMBER + '22', justifyContent: 'center' }} {...tid(`challenge-needs-review-${c.id}`)}><Text style={{ fontSize: 10.5, fontWeight: '800', color: AMBER }}>NEEDS REVIEW</Text></View>}
                  {c.client_specific && <View style={{ paddingHorizontal: 8, height: 22, borderRadius: 11, backgroundColor: PURPLE + '22', justifyContent: 'center' }}><Text style={{ fontSize: 10.5, fontWeight: '800', color: PURPLE }}>THIS CLIENT</Text></View>}
                </View>
                <Text style={{ fontSize: 12.5, color: colors.textSecondary }} numberOfLines={2}>{c.purpose}</Text>
                {c.persona?.name && <Text style={{ fontSize: 12, color: colors.textSecondary }} numberOfLines={1}>{who.replace(/^\w/, x => x.toUpperCase())}: {c.persona.name} · "{c.persona.opening_line}"</Text>}
              </TouchableOpacity>
            ))}
          </View>
        );
      })}
    </>
  );
};
