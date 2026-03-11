"""Pure price calculation functions — no Home Assistant dependencies."""

from __future__ import annotations

from datetime import datetime
from typing import Callable


def calc_price(
    value: float,
    scale: float,
    modifier_fn: Callable[[float], float],
    vat: float,
    no_template: bool = False,
) -> float:
    """Apply scale, optional modifier, and VAT to a raw price component.

    Template + VAT apply only when no_template is False (the default).
    Used for market_price, where the modifier represents the user's pricing formula.
    """
    scaled = value * scale
    if no_template:
        return round(scaled, 5)
    scaled_with_vat = scaled * (1 + vat)
    modified = float(modifier_fn(scaled_with_vat))
    return round(modified, 5)


def parse_hourprices(
    hourprices: dict,
    breakdown_data: dict,
    scale: float,
    vat: float,
    make_modifier: Callable[[datetime], Callable[[float], float]],
) -> dict:
    """Reconstruct total prices from breakdown components.

    Template + VAT are applied only to market_price.
    purchasing_fee and energy_tax are scaled but not modified.
    Falls back to raw total * scale when no breakdown is available.

    make_modifier: callable(hour) -> callable(price) -> float
    """
    result = {}
    for hour, total_amount in hourprices.items():
        breakdown = breakdown_data.get(hour)
        if breakdown and breakdown.get("market_price") is not None:
            modifier_fn = make_modifier(hour)
            modified_market = calc_price(breakdown["market_price"], scale, modifier_fn, vat)
            fee = breakdown.get("purchasing_fee") or 0
            tax = breakdown.get("energy_tax") or 0
            result[hour] = round(modified_market + scale * fee + scale * tax, 5)
        else:
            result[hour] = round(total_amount * scale * (1 + vat), 5)
    return result


def get_breakdown_for_hour(
    breakdown_data: dict,
    hour: datetime,
    scale: float,
    vat: float,
    modifier_fn: Callable[[float], float],
) -> dict | None:
    """Return the price breakdown for a specific hour.

    price: market price with modifier + VAT applied.
    purchasing_fee / energy_tax: scaled only, no modifier or VAT.
    provider_total_price: sum of all three components.
    """
    breakdown = breakdown_data.get(hour)
    if not breakdown:
        return None
    result = {}
    market_price = breakdown.get("market_price")
    if market_price is not None:
        result["price"] = calc_price(market_price, scale, modifier_fn, vat)
    for key in ("purchasing_fee", "energy_tax"):
        value = breakdown.get(key)
        if value is not None:
            result[key] = round(value * scale, 5)
    if not result:
        return None
    result["provider_total_price"] = round(
        result.get("price", 0) + result.get("purchasing_fee", 0) + result.get("energy_tax", 0),
        5,
    )
    return result


def get_timestamped_prices(
    hourprices: dict,
    breakdown_data: dict,
    scale: float,
    vat: float,
    make_modifier: Callable[[datetime], Callable[[float], float]],
) -> list:
    """Return list of {time, provider_total_price, price?, purchasing_fee?, energy_tax?}.

    provider_total_price: total price (market + fee + tax, as calculated by parse_hourprices).
    price: market price with modifier + VAT applied.
    purchasing_fee / energy_tax: scaled only, no modifier or VAT.
    make_modifier: callable(hour) -> callable(price) -> float
    """
    result = []
    for hour, total_price in hourprices.items():
        entry = {"time": str(hour), "provider_total_price": total_price}
        breakdown = breakdown_data.get(hour)
        if breakdown:
            modifier_fn = make_modifier(hour)
            market_price = breakdown.get("market_price")
            entry["price"] = (
                calc_price(market_price, scale, modifier_fn, vat)
                if market_price is not None
                else None
            )
            fee = breakdown.get("purchasing_fee")
            entry["purchasing_fee"] = round(fee * scale, 5) if fee is not None else None
            tax = breakdown.get("energy_tax")
            entry["energy_tax"] = round(tax * scale, 5) if tax is not None else None
        result.append(entry)
    return result


def get_min_price(prices: dict) -> float | None:
    if not prices:
        return None
    return min(prices.values())


def get_max_price(prices: dict) -> float | None:
    if not prices:
        return None
    return max(prices.values())


def get_avg_price(prices: dict) -> float | None:
    if not prices:
        return None
    return round(sum(prices.values()) / len(prices), 5)


def get_min_time(prices: dict):
    if not prices:
        return None
    return min(prices, key=prices.get)


def get_max_time(prices: dict):
    if not prices:
        return None
    return max(prices, key=prices.get)


def get_percentage_of_max(
    current_price: float | None,
    max_price: float | None,
) -> float | None:
    if current_price is None or max_price is None or max_price == 0:
        return None
    return round(current_price / max_price * 100, 1)


def get_percentage_of_range(
    current_price: float | None,
    min_price: float | None,
    max_price: float | None,
) -> float | None:
    if current_price is None or min_price is None or max_price is None:
        return None
    spread = max_price - min_price
    if spread == 0:
        return 100.0
    return round((current_price - min_price) / spread * 100, 1)
