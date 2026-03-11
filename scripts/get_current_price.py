"""Dev script: fetch Energiedirect API and print sensor values for current + nearby hours.

Uses the same pricing functions as the coordinator so values match the integration exactly.

Usage:
    python3 scripts/get_current_price.py
    python3 scripts/get_current_price.py --vat 0.21
    python3 scripts/get_current_price.py --type gas
    python3 scripts/get_current_price.py --all
"""

import argparse
import asyncio
import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytz  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).parent.parent
COMPONENTS = REPO_ROOT / "custom_components" / "energiedirect"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, COMPONENTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


api_client_mod = _load("api_client")
pricing_mod = _load("pricing")

EnergieDirectClient = api_client_mod.EnergieDirectClient
parse_hourprices = pricing_mod.parse_hourprices
get_breakdown_for_hour = pricing_mod.get_breakdown_for_hour

AMSTERDAM_TZ = pytz.timezone("Europe/Amsterdam")
IDENTITY = lambda price: price  # noqa: E731


def bucket_time(dt):
    return dt.replace(minute=0, second=0, microsecond=0)


def format_price(value, unit):
    if value is None:
        return f"{'n/a':>8}     "
    return f"{value:8.5f} {unit}"


async def main():
    parser = argparse.ArgumentParser(
        description="Fetch Energiedirect prices and show sensor values"
    )
    parser.add_argument("--vat", type=float, default=0.21, help="VAT rate (default: 0.21)")
    parser.add_argument(
        "--type", choices=["electricity", "gas", "both"], default="both",
        help="Energy type to display (default: both)",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Show all available hours (default: current ±3h)",
    )
    args = parser.parse_args()

    print("Fetching prices from Energiedirect API...")
    client = EnergieDirectClient()
    try:
        data = await client.fetch_prices()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    now = AMSTERDAM_TZ.localize(datetime.now(AMSTERDAM_TZ).replace(tzinfo=None))
    current = bucket_time(now)

    types = []
    if args.type in ("electricity", "both"):
        types.append(("electricity", "€/kWh", 1.0))
    if args.type in ("gas", "both"):
        types.append(("gas", "€/m³", 1.0))

    for energy_type, unit, scale in types:
        raw_prices = data.get(energy_type, {})
        breakdown_data = data.get(f"{energy_type}_breakdown", {})

        # parse_hourprices mirrors exactly what the coordinator does (identity modifier, no extra modifier)
        total_prices = parse_hourprices(
            raw_prices, breakdown_data, scale=scale, vat=args.vat,
            make_modifier=lambda _: IDENTITY,
        )

        if args.all:
            hours = sorted(raw_prices.keys())
        else:
            hours = sorted(
                h for h in raw_prices.keys()
                if current - timedelta(hours=3) <= h <= current + timedelta(hours=3)
            )

        print(f"\n{'='*110}")
        print(f"  {energy_type.upper()}  |  VAT: {args.vat*100:.0f}%  |  {len(raw_prices)} hours available")
        print(f"{'='*110}")
        print(
            f"  {'':9}  {'TIME':<20}  "
            f"{'BEURSPRIJS':>14}  {'INKOOP':>14}  {'BELASTING':>14}  {'TOTAAL':>14}"
        )
        print(f"  {'-'*95}")

        if not hours:
            print("  No data available for this window.")
            continue

        for h in hours:
            is_current = (h == current)
            marker = " <<" if is_current else "   "
            label = "[CURRENT]" if is_current else "         "

            breakdown = get_breakdown_for_hour(
                breakdown_data, h, scale=scale, vat=args.vat, modifier_fn=IDENTITY
            )

            beursprijs = breakdown.get("price") if breakdown else None
            inkoop = breakdown.get("purchasing_fee") if breakdown else None
            belasting = breakdown.get("energy_tax") if breakdown else None
            totaal = total_prices.get(h)

            print(
                f"  {label}  {h.strftime('%Y-%m-%d %H:%M')}{marker}  "
                f"{format_price(beursprijs, unit)}  "
                f"{format_price(inkoop, unit)}  "
                f"{format_price(belasting, unit)}  "
                f"{format_price(totaal, unit)}"
            )

    print()


if __name__ == "__main__":
    asyncio.run(main())
