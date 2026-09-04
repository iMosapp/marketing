"""Normalize fontSize values in the given files to the app type scale (constants/typography.ts).
Usage: python3 scripts/normalize_type_scale.py <files...>   (idempotent; prints per-file change counts)"""
import re, sys

SECONDARY = re.compile(r"textSecondary|textTertiary|#8E8E93|#999|#666|#AAA|#6E6E73|rgba\(255,\s*255,\s*255,\s*0\.[0-7]|hint|Hint|sub\b|Sub\b|subtitle|desc|Desc|helper|meta|Meta|caption|placeholder|footer|Footer|note|Note")
TITLE = re.compile(r"title|Title|header|Header|heading|Heading|modalName|screenName")
EMPTY = re.compile(r"empty|Empty")
BIG_NUMBER = re.compile(r"[Nn]umber|[Ss]core|[Ss]tat|[Cc]ount|[Vv]alue|[Ee]moji|[Dd]igit|[Bb]ig|[Aa]vatar|[Ii]nitial|[Tt]imer|[Cc]lock")

def target(size: float, ctx: str):
    if size in (8, 9, 10, 10.5): return 11
    if size == 12.5: return 12
    if size in (14.5, 15.5): return 15
    if size == 14: return 13 if SECONDARY.search(ctx) else 15
    if size in (17, 18): return 17 if TITLE.search(ctx) else 16
    if size in (19, 21, 22, 23):
        if EMPTY.search(ctx): return 17
        if BIG_NUMBER.search(ctx) and not TITLE.search(ctx): return 20
        return 20
    if size in (24, 25, 26):
        if BIG_NUMBER.search(ctx) and not TITLE.search(ctx): return None
        return 20
    return None

def run(path):
    lines = open(path).read().split('\n')
    key, changes = None, 0
    for i, l in enumerate(lines):
        m = re.match(r'^\s{2,6}(\w+):\s*\{', l)
        if m: key = m.group(1)
        def repl(mm):
            nonlocal changes
            size = float(mm.group(1))
            ctx = (key or '') + ' ' + l + ' ' + ' '.join(lines[max(i-2, 0):i])
            t = target(size, ctx)
            if t is None or t == size: return mm.group(0)
            changes += 1
            return f'fontSize: {t}'
        lines[i] = re.sub(r'fontSize:\s*([0-9.]+)', repl, l)
    open(path, 'w').write('\n'.join(lines))
    print(f'{path}: {changes} changed')

for p in sys.argv[1:]:
    run(p)
