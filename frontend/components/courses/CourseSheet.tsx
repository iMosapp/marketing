import React, { useEffect, useState } from 'react';
import { View, Text } from 'react-native';
import api from '../../services/api';
import { useToast } from '../common/Toast';
import { Sheet, Field, Label, Chip, GoldButton, tid, industries, industryOfDept, deptsFor, loadIndustries } from '../mystery-shops/shared';
import type { Course } from './shared';

const blank = { title: '', description: '', department: 'sales', pass_pct: '80', badge_label: '' };

// Create or edit a course's basics. Challenges are added on the course page.
// Courses are built by iMOS admins for every client, so the department picker is industry first, then that industry's departments (or Mixed).
export const CourseSheet = ({ visible, onClose, colors, course, onSaved }: { visible: boolean; onClose: () => void; colors: any; course?: Course | null; onSaved: (c: Course) => void }) => {
  const { showToast } = useToast();
  const [f, setF] = useState<any>(blank);
  const [industry, setIndustry] = useState('automotive');
  const [busy, setBusy] = useState(false);
  const [, setTick] = useState(0);
  const set = (k: string, v: any) => setF((x: any) => ({ ...x, [k]: v }));
  useEffect(() => {
    if (!visible) return;
    loadIndustries().then(() => setTick(t => t + 1));
    setF(course ? { title: course.title, description: course.description, department: course.department, pass_pct: String(course.pass_pct), badge_label: course.badge_label } : blank);
    setIndustry(course && course.department !== 'mixed' ? industryOfDept(course.department).key : 'automotive');
  }, [visible, course?.id]);
  const depts = deptsFor(industry);
  const pickIndustry = (key: string) => { setIndustry(key); if (f.department !== 'mixed') set('department', deptsFor(key)[0]?.key || 'sales'); };

  const save = async () => {
    setBusy(true);
    try {
      const payload = { title: f.title, description: f.description, department: f.department, pass_pct: Math.max(50, Math.min(100, Number(f.pass_pct) || 80)), badge_label: f.badge_label.trim() || `Certified: ${f.title.trim()}` };
      const r = course ? await api.put(`/courses/${course.id}`, payload) : await api.post('/courses', payload);
      onSaved(r.data); onClose(); showToast(course ? 'Saved' : 'Course created', 'success');
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not save', 'error'); }
    finally { setBusy(false); }
  };
  return (
    <Sheet visible={visible} onClose={onClose} title={course ? 'Edit course' : 'New course'} colors={colors} testID="course-sheet" footer={<GoldButton label={course ? 'Save' : 'Create course'} onPress={save} busy={busy} disabled={f.title.trim().length < 3} testID="course-save" />}>
      <Field label="COURSE NAME" value={f.title} onChange={(v: string) => set('title', v)} colors={colors} placeholder={industry === 'automotive' ? 'Inbound Sales Certification' : `${depts[0]?.label || 'Phone'} Certification`} testID="course-title" />
      <Field label="WHAT IT COVERS (SHOWS ON THE CERTIFICATE)" value={f.description} onChange={(v: string) => set('description', v)} colors={colors} multiline placeholder={industry === 'automotive' ? 'Every inbound phone-up a salesperson will face: availability, payment, trade, price match, the early looker.' : `Every ${depts[0]?.call || 'call'} ${(depts[0]?.rep || 'a team member').replace(/^(a|an) /, 'a ')} will face.`} testID="course-description" />
      <View style={{ gap: 8 }}><Label t="INDUSTRY" colors={colors} /><View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap' }}>{industries().map(i => <Chip key={i.key} label={i.label} small active={industry === i.key} onPress={() => pickIndustry(i.key)} colors={colors} testID={`course-industry-${i.key}`} />)}</View></View>
      <View style={{ gap: 8 }}><Label t="DEPARTMENT" colors={colors} /><View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
        {depts.map(d => <Chip key={d.key} label={d.label} active={f.department === d.key} onPress={() => set('department', d.key)} colors={colors} testID={`course-dept-${d.key}`} />)}
        <Chip label="Mixed" active={f.department === 'mixed'} onPress={() => set('department', 'mixed')} colors={colors} testID="course-dept-mixed" />
      </View></View>
      <View style={{ flexDirection: 'row', gap: 10 }}>
        <View style={{ flex: 1 }}><Field label="PASS MARK (%)" value={f.pass_pct} onChange={(v: string) => set('pass_pct', v.replace(/[^0-9]/g, ''))} colors={colors} keyboardType="number-pad" placeholder="80" testID="course-pass" /></View>
        <View style={{ flex: 2 }}><Field label="BADGE LABEL" value={f.badge_label} onChange={(v: string) => set('badge_label', v)} colors={colors} placeholder={`Certified: ${f.title || depts[0]?.label || 'Inbound Sales'}`} testID="course-badge" /></View>
      </View>
      <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }}>Every challenge has to be passed at the pass mark or better. Best attempt counts, unlimited retries. Reps practice by phone with Jessi; mystery-shop people simply get called with each challenge until they pass.</Text>
    </Sheet>
  );
};
