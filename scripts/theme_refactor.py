#!/usr/bin/env python3
"""
Automated Light Mode Theme Refactor for iMOs App.
Adds useThemeStore, converts StyleSheet to dynamic, replaces hardcoded colors.
"""
import re, os, sys

FRONTEND = '/app/frontend'

SKIP_FILES = {
    'store/themeStore.ts',
    'app/+html.tsx',
    'app/index.tsx',
}

SKIP_PREFIXES = [
    'app/imos/', 'app/card/', 'app/congrats/', 'app/birthday/',
    'app/review/', 'app/l/', 'app/p/', 'app/showcase/',
    'app/nda/', 'app/partner/', 'app/join/',
    'app/imos-landing-legacy.tsx',
    'app/terms.tsx', 'app/privacy.tsx',
]

# Unambiguous global replacements - safe in any property context
GLOBAL_REPLACEMENTS = [
    # Must process longer hex first to avoid partial matches
    ('#1C1C1E', 'colors.card'), ('#1c1c1e', 'colors.card'),
    ('#1A1A1E', 'colors.card'), ('#1a1a1e', 'colors.card'),
    ('#1a1a1a', 'colors.card'), ('#1e1e1e', 'colors.card'),
    ('#111111', 'colors.card'),
    ('#2C2C2E', 'colors.surface'), ('#2c2c2e', 'colors.surface'),
    ('#2a2a2a', 'colors.surface'), ('#222222', 'colors.surface'),
    ('#3A3A3C', 'colors.borderLight'), ('#3a3a3c', 'colors.borderLight'),
    ('#333333', 'colors.surface'),
    ('#48484A', 'colors.surface'), ('#48484a', 'colors.surface'),
    ('#8E8E93', 'colors.textSecondary'), ('#8e8e93', 'colors.textSecondary'),
    ('#636366', 'colors.textTertiary'),
    ('#6C6C70', 'colors.textSecondary'), ('#6c6c70', 'colors.textSecondary'),
    ('#EBEBF5', 'colors.text'),
    ('#0A0A0A', 'colors.bg'), ('#0a0a0a', 'colors.bg'),
    ('#D1D1D6', 'colors.border'), ('#d1d1d6', 'colors.border'),
    ('#E5E5EA', 'colors.borderLight'), ('#e5e5ea', 'colors.borderLight'),
    ('#F2F2F7', 'colors.bg'), ('#f2f2f7', 'colors.bg'),
    # Short hex - process after longer ones
    ('#111', 'colors.card'),
    ('#222', 'colors.surface'),
    ('#333', 'colors.surface'),
]

# Ambiguous colors that need property context
BG_AMBIGUOUS = [
    ('#000000', 'colors.bg'), ('#000', 'colors.bg'),
    ('#FFFFFF', 'colors.card'), ('#FFF', 'colors.card'),
    ('#fff', 'colors.card'), ('#ffffff', 'colors.card'),
]

TEXT_AMBIGUOUS = [
    ('#FFFFFF', 'colors.text'), ('#FFF', 'colors.text'),
    ('#fff', 'colors.text'), ('#ffffff', 'colors.text'),
    ('#000000', 'colors.text'), ('#000', 'colors.text'),
]

BORDER_AMBIGUOUS = [
    ('#000000', 'colors.border'), ('#000', 'colors.border'),
    ('#FFFFFF', 'colors.border'), ('#FFF', 'colors.border'),
]

BORDER_PROPS = ['borderColor', 'borderBottomColor', 'borderTopColor',
                'borderLeftColor', 'borderRightColor']


def get_import_path(rel_path):
    parts = [p for p in os.path.dirname(rel_path).split('/') if p]
    depth = len(parts)
    if depth == 0:
        return './store/themeStore'
    return '/'.join(['..'] * depth) + '/store/themeStore'


def should_skip(rel_path):
    if rel_path in SKIP_FILES:
        return True
    for prefix in SKIP_PREFIXES:
        if rel_path.startswith(prefix):
            return True
    return False


def do_global_replacements(content):
    for old_hex, new_val in GLOBAL_REPLACEMENTS:
        for q in ["'", '"']:
            content = content.replace(f'{q}{old_hex}{q}', new_val)
    return content


def do_contextual_replacements(content):
    # backgroundColor
    for old_hex, new_val in BG_AMBIGUOUS:
        for q in ["'", '"']:
            content = content.replace(f'backgroundColor: {q}{old_hex}{q}', f'backgroundColor: {new_val}')
            content = content.replace(f'backgroundColor:{q}{old_hex}{q}', f'backgroundColor: {new_val}')

    # standalone color: (text) - negative lookbehind for letters
    for old_hex, new_val in TEXT_AMBIGUOUS:
        for q in ["'", '"']:
            pattern = rf'(?<![a-zA-Z])(color:\s*){q}{re.escape(old_hex)}{q}'
            content = re.sub(pattern, rf'\g<1>{new_val}', content)

    # tintColor
    for old_hex, new_val in TEXT_AMBIGUOUS:
        for q in ["'", '"']:
            content = content.replace(f'tintColor: {q}{old_hex}{q}', f'tintColor: {new_val}')

    # Border colors
    for prop in BORDER_PROPS:
        for old_hex, new_val in BORDER_AMBIGUOUS:
            for q in ["'", '"']:
                content = content.replace(f'{prop}: {q}{old_hex}{q}', f'{prop}: {new_val}')

    # JSX color prop: color="#FFF" → color={colors.text}
    for old_hex, new_val in TEXT_AMBIGUOUS:
        for q in ["'", '"']:
            content = content.replace(f'color={q}{old_hex}{q}', f'color={{{new_val}}}')

    # placeholderTextColor
    for q in ["'", '"']:
        for old_hex in ['#8E8E93', '#8e8e93', '#636366', '#999', '#666', '#aaa']:
            val = 'colors.textSecondary' if old_hex not in ['#636366'] else 'colors.textTertiary'
            content = content.replace(f'placeholderTextColor={q}{old_hex}{q}', f'placeholderTextColor={{{val}}}')

    return content


def add_import_and_hook(content, rel_path):
    """Add useThemeStore import and hook. Returns (content, hook_added)."""
    has_theme = 'useThemeStore' in content
    has_jsx = bool(re.search(
        r'<(View|Text|SafeAreaView|ScrollView|TouchableOpacity|Pressable|Modal|FlatList|KeyboardAvoidingView|Animated\.View|Image|TextInput)',
        content
    ))

    if not has_jsx:
        return content, has_theme  # not a component file

    # Add import
    if not has_theme:
        import_path = get_import_path(rel_path)
        import_matches = list(re.finditer(
            r"^import\s+.*?from\s+['\"].*?['\"];?\s*$", content, re.MULTILINE
        ))
        if import_matches:
            pos = import_matches[-1].end()
            content = content[:pos] + f"\nimport {{ useThemeStore }} from '{import_path}';" + content[pos:]

    # Add hook in component
    has_colors = bool(re.search(r'const\s*\{[^}]*colors[^}]*\}\s*=\s*useThemeStore', content))
    hook_added = has_colors

    if not has_colors:
        comp_patterns = [
            r'(export\s+default\s+function\s+\w+\s*\([^)]*\)\s*\{)',
            r'(export\s+function\s+\w+\s*\([^)]*\)\s*\{)',
            r'(function\s+\w+Screen\s*\([^)]*\)\s*\{)',
            r'(function\s+\w+Page\s*\([^)]*\)\s*\{)',
        ]
        for pat in comp_patterns:
            match = re.search(pat, content)
            if match:
                pos = match.end()
                content = content[:pos] + '\n  const { colors } = useThemeStore();' + content[pos:]
                hook_added = True
                break

    return content, hook_added


def convert_stylesheet(content, hook_added):
    """Convert static StyleSheet to dynamic. Only if hook was added."""
    if not hook_added:
        return content

    if 'getStyles' in content:
        return content

    if 'const styles = StyleSheet.create(' not in content:
        return content

    content = content.replace(
        'const styles = StyleSheet.create(',
        'const getStyles = (colors: any) => StyleSheet.create('
    )

    # Add styles = getStyles(colors) after theme hook
    hook_match = re.search(
        r'(const\s*\{[^}]*colors[^}]*\}\s*=\s*useThemeStore\(\);?)', content
    )
    if hook_match:
        pos = hook_match.end()
        next_chunk = content[pos:pos+60]
        if 'getStyles' not in next_chunk:
            content = content[:pos] + '\n  const styles = getStyles(colors);' + content[pos:]

    return content


def process_file(rel_path, full_path):
    with open(full_path, 'r') as f:
        content = f.read()

    original = content

    # Step 1: Global color replacements
    content = do_global_replacements(content)

    # Step 2: Context-aware replacements
    content = do_contextual_replacements(content)

    # Step 3: Add import and hook
    content, hook_added = add_import_and_hook(content, rel_path)

    # Step 4: Convert StyleSheet (only if hook was added)
    content = convert_stylesheet(content, hook_added)

    if content != original:
        with open(full_path, 'w') as f:
            f.write(content)
        return True
    return False


def main():
    modified = 0
    skipped = 0
    errors = []

    for root, dirs, files in os.walk(FRONTEND):
        for fname in files:
            if not fname.endswith('.tsx'):
                continue

            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, FRONTEND)

            if should_skip(rel_path):
                skipped += 1
                continue

            try:
                if process_file(rel_path, full_path):
                    modified += 1
                    print(f"  MODIFIED: {rel_path}")
            except Exception as e:
                errors.append((rel_path, str(e)))
                print(f"  ERROR: {rel_path}: {e}")

    print(f"\nDone. Modified: {modified}, Skipped: {skipped}, Errors: {len(errors)}")
    if errors:
        for path, err in errors:
            print(f"  - {path}: {err}")


if __name__ == '__main__':
    main()
