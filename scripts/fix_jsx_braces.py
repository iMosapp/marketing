#!/usr/bin/env python3
"""Fix JSX props missing curly braces after theme refactor."""
import re, os

FRONTEND = '/app/frontend'

# Pattern to find JSX props like: color=colors.xxx or placeholderTextColor=colors.xxx  
# These need to be wrapped in curly braces: color={colors.xxx}
JSX_PROP_PATTERN = re.compile(
    r'(\b(?:color|placeholderTextColor|thumbColor|tintColor|selectionColor)\s*)=\s*(colors\.\w+)'
)

def fix_file(full_path):
    with open(full_path, 'r') as f:
        content = f.read()
    
    original = content
    
    # Fix JSX props: prop=colors.xxx → prop={colors.xxx}
    content = JSX_PROP_PATTERN.sub(r'\1={{\2}}', content)
    
    # Also fix: size="small" color=colors.xxx patterns
    # And standalone =colors.xxx that aren't in curly braces already
    
    if content != original:
        with open(full_path, 'w') as f:
            f.write(content)
        return True
    return False

count = 0
for root, dirs, files in os.walk(FRONTEND):
    if 'node_modules' in root:
        continue
    for fname in files:
        if not fname.endswith('.tsx'):
            continue
        full_path = os.path.join(root, fname)
        if fix_file(full_path):
            count += 1
            rel = os.path.relpath(full_path, FRONTEND)
            print(f"  FIXED: {rel}")

print(f"\nFixed {count} files")
