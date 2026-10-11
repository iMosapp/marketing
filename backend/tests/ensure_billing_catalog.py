"""Create or verify the pilot catalog in the billing Stripe account (test mode). Idempotent: a second run creates nothing.
Run: cd /app/backend && set -a && . ./.env && set +a && python tests/ensure_billing_catalog.py [--dry-run]"""
import argparse
import sys

from services import billing

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    sc = billing.client()
    acct = sc.v1.balance.retrieve()
    print(f"livemode={acct.livemode}")
    if acct.livemode:
        print("Refusing to touch a live-mode account from this script")
        sys.exit(2)
    for key, info in billing.ensure_catalog_sync(sc, dry_run=args.dry_run).items():
        print(f"{key:28s} ${info['unit_amount'] / 100:>8.2f}/mo  price={info['price_id'] or '-':32s} created={info['created']}")
    sys.exit(0)
