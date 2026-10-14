"""One-off sweep: replace QA password literals in backend/tests/*.py with qa_creds.password_for("<email>").
Mapping comes from the gitignored /app/memory/test_credentials.md. Only standalone STRING tokens are touched (f-strings and
shell snippets are reported, not edited); every edited file must still compile."""
import io
import py_compile
import re
import sys
import tokenize
from pathlib import Path

ROOT = Path("/app/backend/tests")
creds = Path("/app/memory/test_credentials.md").read_text()
pw2email = {}
for m in re.finditer(r"- Email:\s*(\S+)\s*\n(?:.*\n){0,2}?- Password:\s*(\S+)", creds):
    pw2email.setdefault(m.group(2).strip("`*"), m.group(1).strip("`*"))
for m in re.finditer(r"([A-Za-z0-9._+-]+@[A-Za-z0-9.-]+)\s*/\s*([^\s*`,)]+)", creds):
    pw2email.setdefault(m.group(2), m.group(1))

IMPORT = "from tests import qa_creds\n"
edited, leftovers = [], []
for path in sorted(ROOT.glob("*.py")):
    if path.name in ("qa_creds.py",):
        continue
    src = path.read_text()
    if not any(pw in src for pw in pw2email):
        continue
    repl = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type != tokenize.STRING:
            continue
        inner = tok.string
        if len(inner) >= 2 and inner[0] in "\"'" and inner[-1] == inner[0] and inner[1:-1] in pw2email:
            repl.append((tok.start, tok.end, f'qa_creds.password_for("{pw2email[inner[1:-1]]}")'))
    if not repl:
        leftovers.append(path.name)
        continue
    lines = src.split("\n")
    for (sl, sc), (el, ec), new in sorted(repl, reverse=True):
        assert sl == el
        lines[sl - 1] = lines[sl - 1][:sc] + new + lines[sl - 1][ec:]
    out = "\n".join(lines)
    if IMPORT not in out and "import qa_creds" not in out:
        # after the last top-level import in the leading import block
        ls = out.split("\n")
        idx = 0
        i = 0
        while i < len(ls):
            line = ls[i]
            if line.startswith(("import ", "from ")) and not line.rstrip().endswith("("):
                idx = i + 1
            elif line.startswith(("import ", "from ")) and line.rstrip().endswith("("):
                while i < len(ls) and ")" not in ls[i]:
                    i += 1
                idx = i + 1
            elif line.strip() == "" or line.startswith("#"):
                pass
            elif line.startswith(('"""', "'''")) and i == 0:
                # module docstring: skip to its end
                q = line[:3]
                if line.count(q) >= 2 and len(line.strip()) > 3:
                    idx = i + 1
                else:
                    i += 1
                    while i < len(ls) and q not in ls[i]:
                        i += 1
                    idx = i + 1
            elif idx:
                break
            else:
                break
            i += 1
        ls.insert(idx, IMPORT.rstrip("\n"))
        out = "\n".join(ls)
    path.write_text(out)
    try:
        py_compile.compile(str(path), doraise=True)
    except py_compile.PyCompileError as e:
        print("COMPILE FAIL", path.name, e)
        sys.exit(1)
    if any(pw in out for pw in pw2email):
        leftovers.append(path.name)
    edited.append(path.name)

print(f"edited {len(edited)} files; leftovers (non-token occurrences): {leftovers}")
