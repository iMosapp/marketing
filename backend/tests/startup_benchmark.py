"""Startup benchmark (preview only). Usage: python tests/startup_benchmark.py [--boot] [--runs N] [--label X]
import: wall + CPU seconds of `import server` (warm = cached bytecode, cold = app code recompiled, site-packages cached like a pip-installed image).
--boot: `supervisorctl restart backend` and time until GET /api/health on :8001 answers 200."""
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
import urllib.request

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBE = "import resource, time; t = time.time(); import server; r = resource.getrusage(resource.RUSAGE_SELF); print(round(time.time() - t, 2), round(r.ru_utime + r.ru_stime, 2))"


def _import_once(cwd: str, cold: bool) -> tuple[float, float]:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"} if cold else dict(os.environ)
    out = subprocess.run([sys.executable, "-c", PROBE], cwd=cwd, env=env, capture_output=True, text=True, timeout=180).stdout.strip().splitlines()[-1]
    wall, cpu = out.split()
    return float(wall), float(cpu)


def _cold_copy() -> str:
    dst = "/tmp/startup_bench_backend"
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(BACKEND, dst, ignore=shutil.ignore_patterns("__pycache__", "tests", "*.pyc"))
    return dst


def _boot_once() -> float:
    t = time.time()
    subprocess.run(["sudo", "supervisorctl", "restart", "backend"], capture_output=True, timeout=120)
    while time.time() - t < 240:
        try:
            with urllib.request.urlopen("http://localhost:8001/api/health", timeout=2) as r:
                if r.status == 200:
                    return round(time.time() - t, 2)
        except Exception:
            pass
        time.sleep(0.25)
    return -1.0


def main():
    runs = int(sys.argv[sys.argv.index("--runs") + 1]) if "--runs" in sys.argv else 5
    label = sys.argv[sys.argv.index("--label") + 1] if "--label" in sys.argv else "run"
    _import_once(BACKEND, False)  # make sure the warm cache exists
    warm = [_import_once(BACKEND, False) for _ in range(runs)]
    cold_dir = _cold_copy()
    cold = [_import_once(cold_dir, True) for _ in range(runs)]
    res = {
        "label": label,
        "warm_import_wall_s": statistics.median(w for w, _ in warm), "warm_import_cpu_s": statistics.median(c for _, c in warm),
        "cold_import_wall_s": statistics.median(w for w, _ in cold), "cold_import_cpu_s": statistics.median(c for _, c in cold),
    }
    if "--boot" in sys.argv:
        boots = [_boot_once() for _ in range(3)]
        res["boot_to_health_s"] = boots
        res["boot_to_health_median_s"] = statistics.median(boots)
    print(json.dumps(res))
    with open("/app/memory/startup_benchmark.jsonl", "a") as f:
        f.write(json.dumps(res) + "\n")


if __name__ == "__main__":
    main()
