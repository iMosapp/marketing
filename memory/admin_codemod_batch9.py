import re, os, sys

ROOT = '/app/frontend/app/'
GOLD = '#C9A962'

def read(p): return open(ROOT + p).read()
def write(p, s): open(ROOT + p, 'w').write(s)

def find_block(lines, start_idx):
    """Given index of a line containing an opening <View ...>, return index of its closing </View> at same indent."""
    indent = len(lines[start_idx]) - len(lines[start_idx].lstrip())
    for j in range(start_idx + 1, len(lines)):
        l = lines[j]
        if l.strip() == '</View>' and (len(l) - len(l.lstrip())) == indent:
            return j
    raise Exception('no closing view for line %d' % start_idx)

def replace_header(s, start_pat, replacement, occurrence=1, drop_comment=True):
    lines = s.split('\n')
    seen = 0
    for i, l in enumerate(lines):
        if re.search(start_pat, l):
            seen += 1
            if seen == occurrence:
                j = find_block(lines, i)
                indent = ' ' * (len(l) - len(l.lstrip()))
                new = [indent + replacement] if replacement else []
                k = i
                if drop_comment and i > 0 and lines[i-1].strip() in ('{/* Header */}',):
                    k = i - 1
                return '\n'.join(lines[:k] + new + lines[j+1:])
    raise Exception('header not found: ' + start_pat)

def add_imports(s, rel, need_tid, extra=''):
    imp = "import { ScreenHeader, HeaderIconButton, HeaderTextButton } from '%s/components/common/ScreenHeader';" % rel
    if 'ScreenHeader' not in s.split('export default')[0] or 'common/ScreenHeader' not in s:
        # insert after last top-level import line
        lines = s.split('\n')
        last = 0
        for i, l in enumerate(lines[:80]):
            if l.startswith('import ') or (l.startswith("} from '") ):
                last = i
        lines.insert(last + 1, imp + extra)
        s = '\n'.join(lines)
    if need_tid and 'const tid = ' not in s:
        s = s.replace(imp + extra, imp + extra + "\n\nconst tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });", 1)
    return s

def testids_to_tid(s):
    # only convert on RN elements; web <div>/<button>/<input> keep data-testid
    out = []
    for line in s.split('\n'):
        if re.search(r'<(div|button|input|span|a|label|select|textarea)\b', line):
            out.append(line); continue
        line = re.sub(r'data-testid="([^"]+)"', r"{...tid('\1')}", line)
        line = re.sub(r'data-testid=\{([^}]+)\}', r"{...tid(\1)}", line)
        out.append(line)
    return '\n'.join(out)

def gold(s, keep_lines=()):
    lines = s.split('\n')
    for i, l in enumerate(lines):
        if (i + 1) in keep_lines: continue
        lines[i] = l.replace('#007AFF', GOLD)
    return '\n'.join(lines)

def process(path, header_specs, keep_blue=(), extra=None, rel='../..'):
    s = read(path)
    for spec in header_specs:
        s = replace_header(s, *spec)
    s = gold(s, keep_blue)
    if extra: s = extra(s)
    need_tid = 'data-testid' in s or 'tid(' in s
    s = testids_to_tid(s)
    s = add_imports(s, rel, need_tid or 'tid(' in s)
    write(path, s)
    left = [ (i+1) for i,l in enumerate(s.split('\n')) if '—' in l ]
    print('%-30s ok | em-dash lines: %s | blue left: %d' % (path, left, s.count('#007AFF')))

# ---------------- specs ----------------
ICONS2 = lambda a, b: "right={<View style={{ flexDirection: 'row' }}>%s%s</View>}" % (a, b)

# system-logs
process('admin/system-logs.tsx', [
  (r"<View style=\{\[s\.header, \{ borderBottomColor: colors\.border \}\]\}>",
   '<ScreenHeader title="System Logs" testID="system-logs-header" right={<HeaderTextButton label="Clear" onPress={clearLogs} color="#FF3B30" testID="system-logs-clear" />} />'),
], keep_blue=(16, 21), extra=lambda s: s.replace("{item.category || '—'}", "{item.category || '-'}").replace('No logs — everything is clean', 'No logs. Everything is clean'))

# onboarding-hub: header lives inside the ScrollView; hoist it above
def hub_extra(s):
    s = s.replace("<SafeAreaView style={[styles.safe, { backgroundColor: colors.bg }]}>\n      <ScrollView style={styles.scroll} contentContainerStyle={styles.content}>",
                  "<SafeAreaView style={[styles.safe, { backgroundColor: colors.bg }]} edges={['top']}>\n      <ScreenHeader title=\"Onboarding Hub\" subtitle=\"All account creation in one place\" testID=\"onboarding-hub-header\" />\n      <ScrollView style={styles.scroll} contentContainerStyle={styles.content}>")
    return s
process('admin/onboarding-hub.tsx', [(r"<View style=\{styles\.header\}>", '')], keep_blue=(90, 101), extra=hub_extra)

# account-health: hoist header, keep period toggle (and fix its style order so the active state actually shows)
def ah_extra(s):
    s = s.replace("<SafeAreaView style={[styles.safe, { backgroundColor: colors.bg }]}>\n      <ScrollView style={styles.scroll} contentContainerStyle={styles.content}>",
                  "<SafeAreaView style={[styles.safe, { backgroundColor: colors.bg }]} edges={['top']}>\n      <ScreenHeader title=\"Account Health\" subtitle={`${stats.total} accounts tracked`} testID=\"account-health-header\" />\n      <ScrollView style={styles.scroll} contentContainerStyle={styles.content}>")
    s = s.replace("style={[styles.periodBtn, period === p && { backgroundColor: '#C9A962', borderColor: '#C9A962' }, { borderColor: colors.surface, backgroundColor: colors.card }]}>\n                <Text style={{ fontSize: 13, fontWeight: '600', color: period === p ? '#FFF' : colors.textSecondary }}>{p}d</Text>",
                  "style={[styles.periodBtn, { borderColor: colors.border, backgroundColor: colors.card }, period === p && { backgroundColor: '#C9A962', borderColor: '#C9A962' }]} {...tid(`period-${p}`)}>\n                <Text style={{ fontSize: 13, fontWeight: '700', color: period === p ? '#000' : colors.textSecondary }}>{p}d</Text>")
    s = s.replace("{s.recipient_email} {s.note ? `— \"${s.note}\"` : ''}", "{s.recipient_email} {s.note ? `(\"${s.note}\")` : ''}")
    return s
def ah_header(s):
    # replace header block with just the period row (right-aligned)
    lines = s.split('\n')
    i = next(k for k,l in enumerate(lines) if '<View style={styles.header}>' in l)
    j = find_block(lines, i)
    block = lines[i:j+1]
    pi = next(k for k,l in enumerate(block) if '<View style={styles.periodRow}>' in l)
    pj = find_block(block, pi)
    period = [l[2:] if l.startswith('  ') else l for l in block[pi:pj+1]]
    period[0] = period[0].replace('<View style={styles.periodRow}>', "<View style={[styles.periodRow, { alignSelf: 'flex-end', marginBottom: 12 }]}>")
    k = i - 1 if lines[i-1].strip() == '{/* Header */}' else i
    return '\n'.join(lines[:k] + period + lines[j+1:])
s = read('admin/account-health.tsx'); s = ah_header(s); write('admin/account-health.tsx', s)
process('admin/account-health.tsx', [], keep_blue=(358, 442, 443), extra=ah_extra)

# admin dashboard
process('admin/index.tsx', [
  (r"<View style=\{styles\.header\}>", '<ScreenHeader title="Admin Dashboard" subtitle={getRoleDisplay()} onBack={handleBack} testID="admin-dashboard-header" />'),
], keep_blue=(317, 365, 399, 411, 419, 453, 584))

process('admin/organizations.tsx', [
  (r"<View style=\{styles\.header\}>", '<ScreenHeader title="Organizations" testID="organizations-header" ' + ICONS2('<HeaderIconButton icon="search" onPress={() => setShowSearch(!showSearch)} testID="organizations-search-btn" />', '<HeaderIconButton icon="add-circle" onPress={() => setShowCreateModal(true)} testID="organizations-add-btn" />') + ' />'),
], keep_blue=(188, 192))

process('admin/stores.tsx', [
  (r"<View style=\{styles\.header\}>", '<ScreenHeader title="Accounts" testID="accounts-header" ' + ICONS2('<HeaderIconButton icon="search" onPress={() => setShowSearch(!showSearch)} testID="accounts-search-btn" />', '<HeaderIconButton icon="add-circle" onPress={() => setShowCreateModal(true)} testID="accounts-add-btn" />') + ' />'),
])

process('admin/individuals.tsx', [
  (r"<View style=\{styles\.header\}>", '<ScreenHeader title="Individuals" testID="individuals-header" right={<HeaderIconButton icon="add-circle" onPress={() => setShowAddModal(true)} testID="add-individual-btn" />} />'),
])

process('admin/pending-users.tsx', [
  (r"<View style=\{styles\.header\}>", '<ScreenHeader title="Pending Users" subtitle={`${pendingUsers.length} waiting`} testID="pending-users-header" />'),
])

def lt_extra(s):
    s = s.replace("<View style={[s.container, { backgroundColor: colors.bg }]}>\n      {/* Header */}", "<SafeAreaView style={[s.container, { backgroundColor: colors.bg }]} edges={['top']}>")
    # close tag: last </View> before end of component
    idx = s.rfind("\n    </View>\n  );\n}")
    if idx == -1: raise Exception('lead-tracking close not found')
    s = s[:idx] + "\n    </SafeAreaView>\n  );\n}" + s[idx + len("\n    </View>\n  );\n}"):]
    if "from 'react-native-safe-area-context'" not in s:
        s = s.replace("import { Ionicons } from '@expo/vector-icons';", "import { Ionicons } from '@expo/vector-icons';\nimport { SafeAreaView } from 'react-native-safe-area-context';", 1)
    return s
process('admin/lead-tracking.tsx', [
  (r"<View style=\{\[s\.header, \{ borderBottomColor: colors\.border \}\]\}>", '<ScreenHeader title="Lead Tracking" subtitle="Demo requests and attribution" testID="lead-tracking-header" right={<HeaderIconButton icon="refresh" onPress={fetchData} testID="lead-tracking-refresh" />} />'),
], keep_blue=(19, 30, 212, 276), extra=lt_extra)

def hl_extra(s):
    s = s.replace("""  return (
    <ScrollView
      style={styles.container}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor="#C9A962" />}
    >""", """  return (
    <SafeAreaView style={styles.container} edges={['top']}>
    <ScreenHeader title="Engagement Intelligence" subtitle="Know when customers are thinking about you" testID="hot-leads-header" />
    <ScrollView
      style={{ flex: 1 }}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor="#C9A962" />}
    >""")
    idx = s.rfind("\n    </ScrollView>\n  );\n}")
    if idx == -1: raise Exception('hot-leads close not found')
    s = s[:idx] + "\n    </ScrollView>\n    </SafeAreaView>\n  );\n}" + s[idx + len("\n    </ScrollView>\n  );\n}"):]
    if "from 'react-native-safe-area-context'" not in s:
        s = s.replace("import { Ionicons } from '@expo/vector-icons';", "import { Ionicons } from '@expo/vector-icons';\nimport { SafeAreaView } from 'react-native-safe-area-context';", 1)
    return s
process('admin/hot-leads.tsx', [
  (r'<View style=\{styles\.header\} data-testid="hot-leads-header">', ''),
], keep_blue=(10, 13, 18, 147, 186, 213), extra=hl_extra)

process('partner/dashboard.tsx', [
  (r"<View style=\{s\.header\}>", '<ScreenHeader title="Partner Portal" testID="partner-portal-header" />'),
])

process('admin/partner-agreements.tsx', [
  (r"<View style=\{styles\.header\}>", '<ScreenHeader title="Partner Agreements" testID="partner-agreements-header" />', 1),
  (r"<View style=\{styles\.header\}>", '<ScreenHeader title="Partner Agreements" testID="partner-agreements-header" right={<HeaderIconButton icon="add" onPress={() => setShowCreateModal(true)} testID="partner-agreements-add-btn" />} />', 1),
], keep_blue=(157,), extra=lambda s: s.replace('Exhibit A — Custom Terms (Optional)', 'Exhibit A: Custom Terms (Optional)').replace('Appears in Exhibit A as "Special Terms" — visible to partner when signing.', 'Appears in Exhibit A as "Special Terms", visible to the partner when signing.'))

process('admin/white-label.tsx', [
  (r"<View style=\{s\.header\}>", "<ScreenHeader title=\"White Label Partners\" testID=\"white-label-header\" right={<HeaderIconButton icon={showForm ? 'close' : 'add'} onPress={() => { setEditing(null); setShowForm(!showForm); }} testID=\"white-label-add-btn\" />} />"),
])

process('admin/billing.tsx', [
  (r"<View style=\{styles\.header\}>", '<ScreenHeader title="Billing & Revenue" testID="billing-header" />'),
])
process('admin/forecasting.tsx', [
  (r"<View style=\{styles\.header\}>", '<ScreenHeader title="Revenue Forecast" testID="forecasting-header" />'),
])
process('admin/quotes.tsx', [
  (r"<View style=\{styles\.header\}>", "<ScreenHeader title=\"Quotes\" testID=\"quotes-header\" right={<HeaderIconButton icon=\"add\" onPress={() => router.push('/admin/create-quote')} testID=\"quotes-add-btn\" />} />"),
], keep_blue=(119,), extra=lambda s: s.replace("<SafeAreaView style={styles.container}>", "<SafeAreaView style={styles.container} edges={['top']}>"))
process('admin/create-quote.tsx', [
  (r"<View style=\{styles\.header\}>", '<ScreenHeader title="Create Quote" testID="create-quote-header" />'),
], extra=lambda s: s.replace("<SafeAreaView style={styles.container}>", "<SafeAreaView style={styles.container} edges={['top']}>"))
process('admin/discount-codes.tsx', [
  (r"<View style=\{styles\.header\}>", "<ScreenHeader title=\"Discount Codes\" testID=\"discount-codes-header\" right={<HeaderIconButton icon={showCreateForm ? 'close' : 'add'} onPress={() => setShowCreateForm(!showCreateForm)} testID=\"discount-codes-add-btn\" />} />"),
], keep_blue=(333,), extra=lambda s: s.replace("<SafeAreaView style={styles.container}>", "<SafeAreaView style={styles.container} edges={['top']}>"))
process('admin/shared-inboxes.tsx', [
  (r"<View style=\{styles\.header\}>", '<ScreenHeader title="Shared Inboxes" testID="shared-inboxes-header" right={<HeaderIconButton icon="add-circle" onPress={() => setShowCreateModal(true)} testID="create-inbox-btn" />} />'),
], extra=lambda s: s.replace("<SafeAreaView style={styles.container}>", "<SafeAreaView style={styles.container} edges={['top']}>", 1).replace(" — ", ": "))
process('admin/bulk-transfer.tsx', [
  (r"<View style=\{styles\.header\}>", '<ScreenHeader title="Bulk Transfer" testID="bulk-transfer-header" />'),
], extra=lambda s: s.replace("<SafeAreaView style={styles.container}>", "<SafeAreaView style={styles.container} edges={['top']}>"))
process('admin/app-directory.tsx', [
  (r"<View style=\{styles\.header\}>", '<ScreenHeader title="App Directory" subtitle={`${totalPages} pages`} testID="app-directory-header" />'),
], keep_blue=(60, 74, 79, 86, 89, 105, 112, 131, 133, 180, 194, 204, 217, 230, 235, 252))
process('admin/brand-assets.tsx', [
  (r"<View style=\{styles\.header\}>", "<ScreenHeader title=\"Brand Assets\" testID=\"brand-assets-header\" right={<HeaderIconButton icon=\"color-palette-outline\" onPress={() => router.push('/settings/brand-kit' as any)} testID=\"brand-kit-link\" />} />"),
], extra=lambda s: s.replace(' — ', ': '))
process('admin/error-reports.tsx', [
  (r"<View style=\{\[styles\.header, \{ borderBottomColor: colors\.border \}\]\}>", "<ScreenHeader title=\"Error Reports\" subtitle={`${count} report${count !== 1 ? 's' : ''} captured`} testID=\"error-reports-header\" right={<HeaderIconButton icon=\"trash-outline\" color=\"#FF3B30\" onPress={handleClear} testID=\"error-reports-clear\" />} />"),
], extra=lambda s: s.replace("<SafeAreaView style={[styles.container, { backgroundColor: colors.bg }]}>", "<SafeAreaView style={[styles.container, { backgroundColor: colors.bg }]} edges={['top']}>").replace('{/* Copy Button — big and prominent */}', '{/* Copy button */}'))
process('admin/bug-reports.tsx', [
  (r"<View style=\{\{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, gap: 12 \}\}>", '<ScreenHeader title="Bug Reports" testID="bug-reports-header" />'),
], keep_blue=(29,))
process('admin/sops.tsx', [
  (r"<View style=\{s\.header\}>", '<ScreenHeader title="SOPs & Guides" testID="sops-header" />', 2),
], extra=lambda s: s.replace("colors.primary || '#C9A962'", "colors.accent"))
process('admin/manage-training.tsx', [
  (r"<View style=\{s\.header\}>", '<ScreenHeader title="Edit Lesson" onBack={() => setEditingLesson(null)} testID="edit-lesson-header" right={<HeaderTextButton label={saving ? \'Saving...\' : \'Save\'} onPress={saveLesson} disabled={saving} testID="save-lesson-btn" />} />', 1),
  (r"<View style=\{s\.header\}>", '<ScreenHeader title="Edit Track" onBack={() => setEditingTrack(null)} testID="edit-track-header" right={<HeaderTextButton label={saving ? \'Saving...\' : \'Save\'} onPress={saveTrack} disabled={saving} testID="save-track-btn" />} />', 1),
  (r"<View style=\{s\.header\}>", '<ScreenHeader title="New Track" onBack={() => setShowNewTrack(false)} testID="new-track-header" right={<HeaderTextButton label={saving ? \'Creating...\' : \'Create\'} onPress={createTrack} disabled={saving || !newTrackTitle.trim()} testID="create-track-btn" />} />', 1),
  (r"<View style=\{s\.header\}>", '<ScreenHeader title="Manage Training" testID="manage-training-header" right={<HeaderIconButton icon="add" onPress={() => setShowNewTrack(true)} testID="add-track-btn" />} />', 1),
], keep_blue=(257, 299))
process('admin/training-reports.tsx', [
  (r"<View style=\{s\.header\}>", '<ScreenHeader title="Training Report" subtitle="Video engagement analytics" testID="training-reports-header" />'),
])
print('ALL DONE')
