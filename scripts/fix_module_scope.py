#!/usr/bin/env python3
"""Fix module-scope colors.xxx references by reverting to hex values."""
import re, os

FRONTEND = '/app/frontend'

# Reverse mapping: colors.xxx → original hex value (quoted)
REVERSE_MAP = {
    'colors.card': "'#1C1C1E'",
    'colors.bg': "'#000000'",
    'colors.surface': "'#2C2C2E'",
    'colors.border': "'#2C2C2E'",
    'colors.borderLight': "'#3A3A3C'",
    'colors.text': "'#FFFFFF'",
    'colors.textSecondary': "'#8E8E93'",
    'colors.textTertiary': "'#636366'",
    'colors.accent': "'#C9A962'",
    'colors.success': "'#34C759'",
    'colors.danger': "'#FF3B30'",
    'colors.warning': "'#FF9500'",
    'colors.info': "'#007AFF'",
    'colors.inputBg': "'#1C1C1E'",
    'colors.modalBg': "'#1C1C1E'",
    'colors.searchBg': "'#1C1C1E'",
    'colors.skeleton': "'#2C2C2E'",
}

def is_inside_function(lines, line_idx):
    """Rough check: is this line inside a function body?
    Counts braces from top of file. If we're inside a function/arrow function,
    brace depth > 0 at the function level."""
    depth = 0
    in_function = False
    
    for i in range(line_idx):
        line = lines[i]
        # Detect function starts
        if re.search(r'(export\s+)?(default\s+)?function\s+\w+', line):
            in_function = True
        if re.search(r'const\s+getStyles\s*=\s*\(', line):
            in_function = True
        if re.search(r'const\s+\w+\s*=\s*\([^)]*\)\s*=>\s*\{', line):
            in_function = True
        
        # Count braces
        depth += line.count('{') - line.count('}')
        
        # If we come back to depth 0 after being in a function, we're out
        if in_function and depth <= 0:
            in_function = False
    
    return in_function or depth > 0


def fix_file(full_path, rel_path):
    with open(full_path, 'r') as f:
        content = f.read()
    
    original = content
    lines = content.split('\n')
    
    # Find the first function/component declaration line
    first_func_line = len(lines)  # default: end of file
    for i, line in enumerate(lines):
        if re.search(r'(export\s+)?(default\s+)?function\s+\w+', line):
            first_func_line = i
            break
        if re.search(r'const\s+getStyles\s*=', line):
            first_func_line = i
            break
    
    # Fix colors.xxx references BEFORE the first function
    new_lines = []
    changed = False
    for i, line in enumerate(lines):
        if i < first_func_line and 'colors.' in line:
            new_line = line
            for colors_ref, hex_val in REVERSE_MAP.items():
                if colors_ref in new_line:
                    new_line = new_line.replace(colors_ref, hex_val)
                    changed = True
            new_lines.append(new_line)
        else:
            new_lines.append(line)
    
    if changed:
        with open(full_path, 'w') as f:
            f.write('\n'.join(new_lines))
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
        rel_path = os.path.relpath(full_path, FRONTEND)
        
        if fix_file(full_path, rel_path):
            count += 1
            print(f"  FIXED: {rel_path}")

print(f"\nFixed {count} files with module-scope colors.xxx")
