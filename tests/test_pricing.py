"""Tests for pricing.py — pure functions, no Home Assistant mocking needed."""

import pytest
import pytz
from datetime import datetime, timedelta

from custom_components.energiedirect.pricing import (
    calc_price,
    get_avg_price,
    get_breakdown_for_hour,
    get_max_price,
    get_max_time,
    get_min_price,
    get_min_time,
    get_percentage_of_max,
    get_percentage_of_range,
    get_timestamped_prices,
    parse_hourprices,
)

AMSTERDAM_TZ = pytz.timezone("Europe/Amsterdam")

H0 = AMSTERDAM_TZ.localize(datetime(2026, 3, 11, 10, 0, 0))
H1 = H0 + timedelta(hours=1)
H2 = H0 + timedelta(hours=2)

IDENTITY = lambda price: price          # noqa: E731
MARKUP_05 = lambda price: price + 0.05  # noqa: E731
DOUBLE = lambda price: price * 2        # noqa: E731

IDENTITY_FACTORY = lambda _: IDENTITY        # noqa: E731
MARKUP_05_FACTORY = lambda _: MARKUP_05      # noqa: E731


def bd(market_price, purchasing_fee=0.0, energy_tax=0.0):
    """Shorthand for a breakdown dict."""
    return {"market_price": market_price, "purchasing_fee": purchasing_fee, "energy_tax": energy_tax}


# ---------------------------------------------------------------------------
# calc_price
# ---------------------------------------------------------------------------

class TestCalcPrice:

    def test_identity_no_vat(self):
        assert calc_price(0.10, scale=1, modifier_fn=IDENTITY, vat=0) == pytest.approx(0.10)

    def test_identity_with_vat(self):
        assert calc_price(0.10, scale=1, modifier_fn=IDENTITY, vat=0.21) == pytest.approx(0.10 * 1.21)

    def test_no_template_ignores_modifier_and_vat(self):
        assert calc_price(0.10, scale=1, modifier_fn=DOUBLE, vat=0.21, no_template=True) == pytest.approx(0.10)

    def test_kwh_scale_1(self):
        assert calc_price(0.10, scale=1, modifier_fn=IDENTITY, vat=0) == pytest.approx(0.10)

    def test_mwh_scale_0001(self):
        assert calc_price(0.10, scale=0.001, modifier_fn=IDENTITY, vat=0) == pytest.approx(0.0001)

    def test_gas_scale_1(self):
        assert calc_price(1.0, scale=1, modifier_fn=IDENTITY, vat=0) == pytest.approx(1.0)

    def test_custom_modifier_adds_amount(self):
        assert calc_price(0.10, scale=1, modifier_fn=MARKUP_05, vat=0) == pytest.approx(0.15)

    def test_custom_modifier_with_vat(self):
        # VAT applied before modifier: modifier(0.10 * 1.21) = 0.121 + 0.05 = 0.171
        assert calc_price(0.10, scale=1, modifier_fn=MARKUP_05, vat=0.21) == pytest.approx(0.10 * 1.21 + 0.05)

    def test_scale_applied_before_modifier(self):
        # scale=0.001, value=100 → scaled=0.1 → modifier(0.1)=0.1+0.05=0.15
        assert calc_price(100, scale=0.001, modifier_fn=MARKUP_05, vat=0) == pytest.approx(0.15)


# ---------------------------------------------------------------------------
# parse_hourprices
# ---------------------------------------------------------------------------

class TestParseHourprices:

    def test_with_breakdown_identity_no_vat(self):
        breakdown_data = {H0: bd(market_price=0.05, purchasing_fee=0.10, energy_tax=0.05)}
        result = parse_hourprices({H0: 0.05}, breakdown_data, scale=1, vat=0, make_modifier=IDENTITY_FACTORY)
        assert result[H0] == pytest.approx(0.20)

    def test_vat_applied_to_all_components(self):
        breakdown_data = {H0: bd(market_price=0.05, purchasing_fee=0.10, energy_tax=0.05)}
        result = parse_hourprices({H0: 0.05}, breakdown_data, scale=1, vat=0.21, make_modifier=IDENTITY_FACTORY)
        expected = 0.05 * 1.21 + 0.10 * 1.21 + 0.05 * 1.21
        assert result[H0] == pytest.approx(expected)

    def test_modifier_applied_to_market_only(self):
        breakdown_data = {H0: bd(market_price=0.05, purchasing_fee=0.10, energy_tax=0.05)}
        result = parse_hourprices({H0: 0.05}, breakdown_data, scale=1, vat=0, make_modifier=MARKUP_05_FACTORY)
        # market: 0.05+0.05=0.10; fee: 0.10; tax: 0.05 → 0.25
        assert result[H0] == pytest.approx(0.25)

    def test_fallback_to_total_when_no_breakdown(self):
        result = parse_hourprices({H0: 0.20}, {}, scale=1, vat=0.21, make_modifier=IDENTITY_FACTORY)
        assert result[H0] == pytest.approx(0.20 * 1.21)

    def test_mwh_scale_applied_to_all_components(self):
        breakdown_data = {H0: bd(market_price=0.05, purchasing_fee=0.10, energy_tax=0.05)}
        result = parse_hourprices({H0: 0.05}, breakdown_data, scale=0.001, vat=0, make_modifier=IDENTITY_FACTORY)
        assert result[H0] == pytest.approx(0.20 * 0.001, abs=1e-8)

    def test_multiple_hours_each_get_own_modifier(self):
        # make_modifier returns a different multiplier per hour to verify each hour uses its own
        def hour_aware_factory(hour):
            multiplier = 2 if hour == H0 else 1
            return lambda price: price * multiplier

        breakdown_data = {
            H0: bd(market_price=0.10, purchasing_fee=0, energy_tax=0),
            H1: bd(market_price=0.10, purchasing_fee=0, energy_tax=0),
        }
        result = parse_hourprices({H0: 0.10, H1: 0.10}, breakdown_data, scale=1, vat=0, make_modifier=hour_aware_factory)
        assert result[H0] == pytest.approx(0.20)  # doubled
        assert result[H1] == pytest.approx(0.10)  # identity

    def test_gas_scale_1(self):
        breakdown_data = {H0: bd(market_price=0.50, purchasing_fee=0.30, energy_tax=0.20)}
        result = parse_hourprices({H0: 0.50}, breakdown_data, scale=1, vat=0, make_modifier=IDENTITY_FACTORY)
        assert result[H0] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# get_breakdown_for_hour
# ---------------------------------------------------------------------------

class TestGetBreakdownForHour:

    def test_returns_none_when_no_breakdown(self):
        assert get_breakdown_for_hour({}, H0, scale=1, vat=0, modifier_fn=IDENTITY) is None

    def test_all_keys_present(self):
        result = get_breakdown_for_hour({H0: bd(0.05, 0.10, 0.03)}, H0, scale=1, vat=0, modifier_fn=IDENTITY)
        assert result is not None
        assert set(result.keys()) == {"price", "purchasing_fee", "energy_tax", "provider_total_price"}

    def test_price_has_modifier_applied(self):
        result = get_breakdown_for_hour({H0: bd(0.05, 0.10, 0.03)}, H0, scale=1, vat=0, modifier_fn=MARKUP_05)
        assert result is not None
        assert result["price"] == pytest.approx(0.10)

    def test_price_has_vat_applied(self):
        result = get_breakdown_for_hour({H0: bd(0.05, 0.10, 0.03)}, H0, scale=1, vat=0.21, modifier_fn=IDENTITY)
        assert result is not None
        assert result["price"] == pytest.approx(0.05 * 1.21)

    def test_provider_total_price_is_sum_of_components(self):
        result = get_breakdown_for_hour({H0: bd(0.05, 0.10, 0.03)}, H0, scale=1, vat=0.21, modifier_fn=IDENTITY)
        assert result is not None
        assert result["provider_total_price"] == pytest.approx(0.05 * 1.21 + 0.10 * 1.21 + 0.03 * 1.21)

    def test_fee_has_vat_applied(self):
        result = get_breakdown_for_hour({H0: bd(0.05, 0.10, 0.03)}, H0, scale=1, vat=0.21, modifier_fn=DOUBLE)
        assert result is not None
        assert result["purchasing_fee"] == pytest.approx(0.10 * 1.21)

    def test_tax_has_vat_applied(self):
        result = get_breakdown_for_hour({H0: bd(0.05, 0.10, 0.03)}, H0, scale=1, vat=0.21, modifier_fn=DOUBLE)
        assert result is not None
        assert result["energy_tax"] == pytest.approx(0.03 * 1.21)

    def test_missing_market_price_excluded(self):
        result = get_breakdown_for_hour({H0: {"purchasing_fee": 0.10, "energy_tax": 0.03}}, H0, scale=1, vat=0, modifier_fn=IDENTITY)
        assert result is not None
        assert "price" not in result

    def test_empty_breakdown_returns_none(self):
        assert get_breakdown_for_hour({H0: {}}, H0, scale=1, vat=0, modifier_fn=IDENTITY) is None

    def test_breakdown_with_only_unknown_keys_returns_none(self):
        assert get_breakdown_for_hour({H0: {"unknown_key": 1.0}}, H0, scale=1, vat=0, modifier_fn=IDENTITY) is None

    def test_mwh_scale_on_fee_and_tax(self):
        result = get_breakdown_for_hour({H0: bd(0.05, 0.10, 0.05)}, H0, scale=0.001, vat=0, modifier_fn=IDENTITY)
        assert result is not None
        assert result["purchasing_fee"] == pytest.approx(0.10 * 0.001, abs=1e-8)
        assert result["energy_tax"] == pytest.approx(0.05 * 0.001, abs=1e-8)

    def test_gas_scale_1_vat_on_all_components(self):
        result = get_breakdown_for_hour({H0: bd(0.50, 0.30, 0.20)}, H0, scale=1, vat=0.21, modifier_fn=IDENTITY)
        assert result is not None
        assert result["price"] == pytest.approx(0.50 * 1.21)
        assert result["purchasing_fee"] == pytest.approx(0.30 * 1.21)
        assert result["energy_tax"] == pytest.approx(0.20 * 1.21)
        assert result["provider_total_price"] == pytest.approx(0.50 * 1.21 + 0.30 * 1.21 + 0.20 * 1.21)


# ---------------------------------------------------------------------------
# get_timestamped_prices
# ---------------------------------------------------------------------------

class TestGetTimestampedPrices:

    def test_price_has_modifier_applied(self):
        breakdown_data = {H0: bd(0.05, 0.10, 0.03)}
        result = get_timestamped_prices({H0: 0.18}, breakdown_data, scale=1, vat=0, make_modifier=MARKUP_05_FACTORY)
        assert result[0]["price"] == pytest.approx(0.10)

    def test_price_has_vat_applied(self):
        breakdown_data = {H0: bd(0.05, 0.10, 0.03)}
        result = get_timestamped_prices({H0: 0.18}, breakdown_data, scale=1, vat=0.21, make_modifier=IDENTITY_FACTORY)
        assert result[0]["price"] == pytest.approx(0.05 * 1.21)

    def test_provider_total_price_is_total(self):
        breakdown_data = {H0: bd(0.05, 0.10, 0.03)}
        result = get_timestamped_prices({H0: 0.18}, breakdown_data, scale=1, vat=0, make_modifier=IDENTITY_FACTORY)
        assert result[0]["provider_total_price"] == pytest.approx(0.18)

    def test_fee_has_vat_applied(self):
        breakdown_data = {H0: bd(0.05, 0.10, 0.03)}
        result = get_timestamped_prices({H0: 0.05}, breakdown_data, scale=1, vat=0.21, make_modifier=lambda _: DOUBLE)
        assert result[0]["purchasing_fee"] == pytest.approx(0.10 * 1.21)

    def test_tax_has_vat_applied(self):
        breakdown_data = {H0: bd(0.05, 0.10, 0.03)}
        result = get_timestamped_prices({H0: 0.05}, breakdown_data, scale=1, vat=0.21, make_modifier=lambda _: DOUBLE)
        assert result[0]["energy_tax"] == pytest.approx(0.03 * 1.21)

    def test_price_none_when_market_price_key_missing(self):
        breakdown_data = {H0: {"purchasing_fee": 0.10}}
        result = get_timestamped_prices({H0: 0.10}, breakdown_data, scale=1, vat=0, make_modifier=IDENTITY_FACTORY)
        assert result[0]["price"] is None

    def test_no_breakdown_no_extra_fields(self):
        result = get_timestamped_prices({H0: 0.20}, {}, scale=1, vat=0, make_modifier=IDENTITY_FACTORY)
        assert "price" not in result[0]
        assert "purchasing_fee" not in result[0]

    def test_provider_total_price_always_present(self):
        result = get_timestamped_prices({H0: 0.20}, {}, scale=1, vat=0, make_modifier=IDENTITY_FACTORY)
        assert result[0]["provider_total_price"] == 0.20

    def test_mwh_scale_on_fee_and_tax(self):
        breakdown_data = {H0: bd(0.05, 0.10, 0.05)}
        result = get_timestamped_prices({H0: 0.05}, breakdown_data, scale=0.001, vat=0, make_modifier=IDENTITY_FACTORY)
        assert result[0]["purchasing_fee"] == pytest.approx(0.10 * 0.001, abs=1e-8)
        assert result[0]["energy_tax"] == pytest.approx(0.05 * 0.001, abs=1e-8)

    def test_multiple_hours_count(self):
        result = get_timestamped_prices({H0: 0.10, H1: 0.20, H2: 0.30}, {}, scale=1, vat=0, make_modifier=IDENTITY_FACTORY)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# Aggregates
# ---------------------------------------------------------------------------

class TestAggregates:

    PRICES = {H0: 0.20, H1: 0.10, H2: 0.30}

    def test_min_price(self):
        assert get_min_price(self.PRICES) == pytest.approx(0.10)

    def test_max_price(self):
        assert get_max_price(self.PRICES) == pytest.approx(0.30)

    def test_avg_price(self):
        assert get_avg_price(self.PRICES) == pytest.approx(0.20)

    def test_min_time(self):
        assert get_min_time(self.PRICES) == H1

    def test_max_time(self):
        assert get_max_time(self.PRICES) == H2

    def test_returns_none_when_empty(self):
        assert get_min_price({}) is None
        assert get_max_price({}) is None
        assert get_avg_price({}) is None
        assert get_min_time({}) is None
        assert get_max_time({}) is None

    def test_percentage_of_max(self):
        assert get_percentage_of_max(0.50, 1.00) == pytest.approx(50.0)

    def test_percentage_of_max_none_when_max_zero(self):
        assert get_percentage_of_max(0.50, 0) is None

    def test_percentage_of_max_none_when_inputs_none(self):
        assert get_percentage_of_max(None, 1.0) is None
        assert get_percentage_of_max(0.5, None) is None

    def test_percentage_of_range(self):
        # min=0.20, max=1.00, current=0.60 → (0.60-0.20)/(0.80) = 50%
        assert get_percentage_of_range(0.60, 0.20, 1.00) == pytest.approx(50.0)

    def test_percentage_of_range_zero_spread(self):
        assert get_percentage_of_range(0.20, 0.20, 0.20) == pytest.approx(100.0)

    def test_percentage_of_range_none_when_inputs_none(self):
        assert get_percentage_of_range(None, 0.10, 1.0) is None
