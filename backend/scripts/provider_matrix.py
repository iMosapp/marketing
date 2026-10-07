"""Provider validation matrix: run a deliberate list of real vehicles through BOTH live market providers and write a side-by-side CSV + Markdown report.

  cd /app/backend && set -a && . ./.env && set +a
  python scripts/provider_matrix.py --file scripts/provider_matrix_vehicles.csv --zip 84070            # plan + confirmation prompt
  python scripts/provider_matrix.py --file ... --zip 84070 --yes                                        # run without the prompt
  python scripts/provider_matrix.py --file ... --zip 84070 --dry-run                                    # plan only, zero API calls
  python scripts/provider_matrix.py --file ... --zip 84070 --probe-zip 1FTEW1EP5KFA12345                # one extra VinAudit call WITH zip, to see if it matters

CSV columns: vin, mileage, zip (optional), year, make, model, trim (optional; decoded from the VIN when missing). Max 25 rows per run, on purpose.
Results: /app/memory/provider_matrix_<timestamp>.csv and .md (no credentials anywhere) and one `market_provider_comparisons` row per vehicle (purpose=matrix).
Nothing here touches any appraisal, snapshot-of-record or the engine."""
import argparse
import asyncio
import csv
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from services.appraisals import market, market_providers as mp  # noqa: E402
from services.appraisals import providers as identity  # noqa: E402

MAX_ROWS = 25
OUT_DIR = "/app/memory"


def _money(v):
    return f"${v:,.0f}" if isinstance(v, (int, float)) and v else ""


async def _admin_user(db):
    me = await db.users.find_one({"role": "super_admin"}, sort=[("created_at", 1)])
    if not me:
        raise SystemExit("No super_admin user in this database; the matrix runs as the platform admin.")
    return me


def _plan(rows: list, probe_vin: str | None) -> dict:
    mc, va = mp.PROVIDERS["marketcheck"], mp.PROVIDERS["vinaudit"]
    per_vehicle = (mc.calls_per_fetch if mc.configured() else 0) + (len(mp.VA_VALUE_TYPES) if va.configured() else 0)
    total = per_vehicle * len(rows) + (1 if probe_vin and va.configured() else 0)
    return {"vehicles": len(rows), "marketcheck": "configured" if mc.configured() else "NOT configured (skipped)", "vinaudit": "configured" if va.configured() else "NOT configured (skipped)",
            "calls_per_vehicle": per_vehicle, "total_calls": total}


async def run(args):
    with open(args.file, newline="") as f:
        rows = [{k.strip().lower(): (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)]
    rows = [r for r in rows if r.get("vin") or (r.get("year") and r.get("make") and r.get("model"))][:MAX_ROWS]
    if not rows:
        raise SystemExit("No usable rows (need a VIN or year/make/model).")
    plan = _plan(rows, args.probe_zip)
    print(f"PLAN: {plan['vehicles']} vehicles · MarketCheck {plan['marketcheck']} · VinAudit {plan['vinaudit']} · {plan['calls_per_vehicle']} paid calls per vehicle · {plan['total_calls']} calls total")
    if args.dry_run:
        return
    if not args.yes:
        if input(f"Spend ~{plan['total_calls']} paid API calls now? Type RUN to continue: ").strip() != "RUN":
            print("Stopped. Nothing was called.")
            return
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    me = await _admin_user(db)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    out_rows = []
    for i, r in enumerate(rows, 1):
        vin = (r.get("vin") or "").upper() or None
        vehicle = {"vin": vin, "year": int(r["year"]) if r.get("year") else None, "make": r.get("make") or None, "model": r.get("model") or None, "trim": r.get("trim") or None}
        if vin and not (vehicle["year"] and vehicle["make"] and vehicle["model"]):
            try:
                dec = await identity.decode_vin(db, vin)
                vehicle.update({k: dec.get(k) for k in ("year", "make", "model", "trim") if dec.get(k)})
            except Exception as e:  # noqa: BLE001
                print(f"[{i}] {vin}: VIN decode failed ({e}); add year/make/model to the CSV. Skipped.")
                continue
        mileage = int(r["mileage"]) if r.get("mileage") else None
        zip_code = r.get("zip") or args.zip
        probe = bool(args.probe_zip and vin and args.probe_zip.upper() == vin)
        try:
            comp = await market.compare(db, me, vehicle=vehicle, mileage=mileage, zip_code=zip_code, radius=args.radius, force=args.force, purpose="matrix", probe_zip=probe)
        except Exception as e:  # noqa: BLE001
            print(f"[{i}] {vin or vehicle}: {e}")
            continue
        cards = {c["provider"]: c for c in comp["providers"]}
        mc, va, d = cards.get("marketcheck", {}), cards.get("vinaudit", {}), comp.get("difference") or {}
        row = {"vin": vin or "", "year": vehicle.get("year"), "make": vehicle.get("make"), "model": vehicle.get("model"), "trim": vehicle.get("trim") or "", "mileage": mileage or "", "zip": zip_code,
               "mc_status": mc.get("status"), "mc_retail": mc.get("estimated_retail") or "", "mc_comps_median": mc.get("comps_median") or "", "mc_comps_avg": mc.get("comps_average") or "",
               "mc_range": f"{mc.get('price_range', {}).get('low', '')}-{mc.get('price_range', {}).get('high', '')}" if mc.get("price_range") else "", "mc_comps": mc.get("comps_count") or "",
               "mc_confidence": (mc.get("confidence") or {}).get("level") or "", "mc_ms": mc.get("response_ms") or "", "mc_calls": mc.get("calls") or 0, "mc_error": mc.get("error") or "",
               "va_status": va.get("status"), "va_retail": va.get("estimated_retail") or "", "va_tradein": va.get("estimated_trade_in") or "", "va_band": f"{va.get('price_range', {}).get('low', '')}-{va.get('price_range', {}).get('high', '')}" if va.get("price_range") else "",
               "va_records": va.get("comps_count") or "", "va_certainty": va.get("provider_certainty") or "", "va_confidence": (va.get("confidence") or {}).get("level") or "",
               "va_ms": va.get("response_ms") or "", "va_calls": va.get("calls") or 0, "va_error": va.get("error") or "",
               "diff_dollars": d.get("dollars") if d.get("available") else "", "diff_percent": d.get("percent") if d.get("available") else "", "calls_total": comp.get("calls_total"), "comparison_id": comp["id"]}
        out_rows.append(row)
        print(f"[{i}] {vehicle.get('year')} {vehicle.get('make')} {vehicle.get('model')} {vin or ''}: MC {_money(mc.get('estimated_retail')) or mc.get('status')} · VA {_money(va.get('estimated_retail')) or va.get('status')}"
              f"{' · trade-in ' + _money(va.get('estimated_trade_in')) if va.get('estimated_trade_in') else ''} · diff {_money(d.get('dollars')) if d.get('available') else 'n/a'} · {comp.get('calls_total')} calls")
        await asyncio.sleep(args.pause)
    if not out_rows:
        print("Nothing to write.")
        return
    os.makedirs(OUT_DIR, exist_ok=True)
    csv_path, md_path = f"{OUT_DIR}/provider_matrix_{stamp}.csv", f"{OUT_DIR}/provider_matrix_{stamp}.md"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)
    diffs = [r["diff_dollars"] for r in out_rows if r["diff_dollars"] != ""]
    pcts = [r["diff_percent"] for r in out_rows if r["diff_percent"] != ""]
    with open(md_path, "w") as f:
        f.write(f"# Provider matrix {stamp} UTC\n\n{len(out_rows)} vehicles · ZIP default {args.zip} · radius {args.radius} mi · {sum(int(r['calls_total'] or 0) for r in out_rows)} paid calls\n\n")
        f.write("| # | Vehicle | VIN | Miles | MarketCheck retail | MC comps (median) | MC conf | VinAudit retail | VA trade-in | VA records (certainty) | Diff $ | Diff % | ms MC/VA |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")
        for i, r in enumerate(out_rows, 1):
            f.write(f"| {i} | {r['year']} {r['make']} {r['model']} {r['trim']} | {r['vin']} | {r['mileage']} | {_money(r['mc_retail']) or r['mc_status']} | {r['mc_comps']} ({_money(r['mc_comps_median'])}) | {r['mc_confidence']} | "
                    f"{_money(r['va_retail']) or r['va_status']} | {_money(r['va_tradein'])} | {r['va_records']} ({r['va_certainty']}%) | {_money(r['diff_dollars'])} | {r['diff_percent']} | {r['mc_ms']}/{r['va_ms']} |\n")
        if diffs:
            higher_mc = sum(1 for x in diffs if x > 0)
            f.write(f"\nBoth providers answered on {len(diffs)} vehicles. MarketCheck higher on {higher_mc}, VinAudit higher on {len(diffs) - higher_mc}. "
                    f"Median absolute gap {_money(sorted(abs(x) for x in diffs)[len(diffs) // 2])} ({sorted(pcts)[len(pcts) // 2]}%). Each number is the provider's own; nothing was averaged.\n")
        errs = [(r['vin'], r['mc_error'] or r['va_error']) for r in out_rows if r['mc_error'] or r['va_error']]
        if errs:
            f.write("\nProvider errors:\n" + "".join(f"- {v}: {e}\n" for v, e in errs))
    print(f"\nWrote {csv_path}\n      {md_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", required=True, help="CSV of vehicles (vin, mileage, zip, year, make, model, trim)")
    ap.add_argument("--zip", required=True, help="Default 5-digit ZIP when a row has none")
    ap.add_argument("--radius", type=int, default=100)
    ap.add_argument("--pause", type=float, default=1.0, help="Seconds between vehicles (rate-limit courtesy)")
    ap.add_argument("--force", action="store_true", help="Ignore the 24h comparison cache (spends calls again)")
    ap.add_argument("--probe-zip", default=None, help="VIN for which VinAudit is ALSO called with zip, to see whether ZIP changes its answer")
    ap.add_argument("--dry-run", action="store_true", help="Print the plan only; zero API calls")
    ap.add_argument("--yes", action="store_true", help="Skip the confirmation prompt")
    asyncio.run(run(ap.parse_args()))
