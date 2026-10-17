"""Compare two run_ab / run_regression_detail logs (baseline vs candidate): per module summary, failures only on the candidate (new),
failures only on the baseline (fixed). Usage: python tests/compare_ab_logs.py baseline.log candidate.log"""
import re
import sys


def parse(path):
    mods, fails, cur = {}, {}, None
    for line in open(path):
        if line.startswith("    "):
            m = re.match(r"\s+(FAILED|ERROR) (\S+)", line)
            if m and cur:
                fails[cur].add(m.group(2).split(" - ")[0])
        elif "|" in line:
            cur = line.split("|")[0].strip()
            mods[cur] = line.split("|")[2].strip()
            fails[cur] = set()
    return mods, fails


def main(base, cand):
    bm, bf = parse(base)
    cm, cf = parse(cand)
    new, fixed = [], []
    print(f"{'module':48} | {'baseline (production)':38} | candidate")
    for m in bm:
        print(f"{m:48} | {bm[m][:38]:38} | {cm.get(m, 'MISSING')}")
        new += [(m, t) for t in sorted(cf.get(m, set()) - bf[m])]
        fixed += [(m, t) for t in sorted(bf[m] - cf.get(m, set()))]
    print(f"\nFAIL ON CANDIDATE ONLY ({len(new)}):")
    for m, t in new:
        print("  ", t)
    print(f"\nFAIL ON BASELINE ONLY = fixed by candidate ({len(fixed)}):")
    for m, t in fixed:
        print("  ", t)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
