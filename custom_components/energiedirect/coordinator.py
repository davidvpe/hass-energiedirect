from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

import aiohttp
import async_timeout
import homeassistant.helpers.config_validation as cv
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.template import Template
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt
from jinja2 import pass_context

from .api_client import EnergieDirectClient
from .const import (
    CALCULATION_MODE,
    DEFAULT_MODIFYER,
    ENERGY_SCALES,
    ENERGY_TYPE_GAS,
)
from .utils import bucket_time

MIN_HOURS = 20
PERIOD_MINUTES = 60


class EnergieDirectCoordinator(DataUpdateCoordinator):
    """Get the latest data and update the states."""

    def __init__(
            self,
            hass: HomeAssistant,
            energy_type: str,
            energy_scale: str,
            modifyer,
            calculation_mode=CALCULATION_MODE["default"],
            VAT=0,
    ) -> None:
        """Initialize the data object."""
        self.hass = hass
        self.energy_type = energy_type
        self.modifyer = modifyer
        self.energy_scale = energy_scale
        self.calculation_mode = calculation_mode
        self.vat = VAT
        self.calculator_last_sync = None
        self.filtered_hourprices = []
        self.lock = asyncio.Lock()
        self._last_cleanup_date = None
        self.breakdown_data: dict = {}

        if not isinstance(self.modifyer, Template):
            if self.modifyer in (None, ""):
                self.modifyer = DEFAULT_MODIFYER
            self.modifyer = cv.template(self.modifyer)
        else:
            if self.modifyer.template in ("", None):
                self.modifyer = cv.template(DEFAULT_MODIFYER)

        logger = logging.getLogger(__name__)
        super().__init__(
            hass,
            logger,
            name="Energiedirect coordinator",
            update_interval=timedelta(minutes=PERIOD_MINUTES),
        )

    def _get_scale_factor(self) -> float:
        """Return the scale factor for the price. Gas prices are always in EUR/m³."""
        if self.energy_type == ENERGY_TYPE_GAS:
            return 1.0
        return ENERGY_SCALES.get(self.energy_scale, 1)

    def calc_price(self, value, fake_dt=None, no_template=False) -> float:
        """Calculate price based on the users settings."""
        if no_template:
            return round(value * self._get_scale_factor(), 5)

        price = value * self._get_scale_factor()
        if fake_dt is not None:
            def faker():
                def inner(*args, **kwargs):
                    return fake_dt
                return pass_context(inner)

            template_value = self.modifyer.async_render(
                now=faker(), current_price=price
            )
        else:
            template_value = self.modifyer.async_render(current_price=price)

        try:
            price = round(float(template_value) * (1 + self.vat), 5)
        except (ValueError, TypeError) as exc:
            self.logger.error(
                f"Failed to convert template result '{template_value}' to float. "
                f"Please check your price modifier template. Error: {exc}"
            )
            raise

        return price

    def parse_hourprices(self, hourprices):
        return {hour: self.calc_price(value=price, fake_dt=hour) for hour, price in hourprices.items()}

    async def _async_update_data(self) -> dict:
        """Get the latest data from Energiedirect."""
        self.logger.debug("Energiedirect DataUpdateCoordinator data update")

        now = dt.now()
        if self.check_update_needed(now) is False:
            self.logger.debug("Skipping api fetch. All data is already available")
            return self.data

        data = await self.fetch_prices()
        self.logger.debug(f"received data = {data}")

        if data is not None:
            if data is self.data:
                self.logger.debug("Using cached data from degraded mode")
                return data
            parsed_data = self.parse_hourprices(data)
            self.logger.debug(
                f"received pricing data from Energiedirect for {len(data)} hours ({self.energy_type})"
            )
            self.data = parsed_data
            return parsed_data

        return self.data if self.data is not None else {}

    def check_update_needed(self, now):
        if self.data is None:
            return True
        if len(self.get_data_today()) < MIN_HOURS:
            return True
        if len(self.get_data_tomorrow()) < MIN_HOURS and now.hour > 11:
            return True
        return False

    async def fetch_prices(self):
        try:
            async with async_timeout.timeout(10):
                client = EnergieDirectClient()
                all_prices = await client.fetch_prices()
                self.breakdown_data = all_prices.get(f"{self.energy_type}_breakdown", {})
                return all_prices.get(self.energy_type, {})

        except Exception as exc:
            if self.data is not None and len(self.data) > 0:
                newest_timestamp = max(self.data.keys())
                if newest_timestamp > dt.now():
                    self.logger.warning(
                        f"Warning: running in degraded mode (using stored data) since fetching "
                        f"Energiedirect prices failed: {exc}."
                    )
                    return self.data
                else:
                    raise UpdateFailed(
                        f"The latest available data is older than the current time. "
                        f"Entities will no longer update. Error: {exc}"
                    ) from exc
            else:
                self.logger.error("Failed fetching data from Energiedirect")
                raise UpdateFailed("Fetching data from Energiedirect failed.") from exc

    @property
    def today(self):
        return dt.now().replace(hour=0, minute=0, second=0, microsecond=0)

    def get_data(self, date):
        return {k: v for k, v in self.data.items() if k.date() == date.date()}

    def get_data_today(self):
        return self.get_data(self.today)

    def get_data_tomorrow(self):
        return self.get_data(self.today + timedelta(days=1))

    def get_data_yesterday(self):
        return self.get_data(self.today - timedelta(days=1))

    def today_data_available(self):
        return len(self.get_data_today()) > MIN_HOURS

    @property
    def current_bucket_time(self):
        return bucket_time(dt.now(), PERIOD_MINUTES)

    @property
    def period_minutes(self):
        return PERIOD_MINUTES

    def get_current_price(self) -> float | None:
        return self.data.get(self.current_bucket_time)

    def get_next_price(self) -> float | None:
        return self.data.get(
            self.current_bucket_time + timedelta(minutes=PERIOD_MINUTES)
        )

    def get_prices_today(self):
        return self.get_timestamped_prices(self.get_data_today())

    def get_prices_tomorrow(self):
        return self.get_timestamped_prices(self.get_data_tomorrow())

    def get_prices(self):
        return self.get_timestamped_prices(
            {hour: price for hour, price in self.data.items() if hour >= self.today}
        )

    def get_timestamped_prices(self, hourprices):
        result = []
        for hour, price in hourprices.items():
            entry = {"time": str(hour), "price": price}
            breakdown = self.breakdown_data.get(hour)
            if breakdown:
                entry["market_price"] = breakdown.get("market_price")
                entry["purchasing_fee"] = breakdown.get("purchasing_fee")
                entry["energy_tax"] = breakdown.get("energy_tax")
            result.append(entry)
        return result

    async def sync_calculator(self):
        now = dt.now()
        bucket = self.current_bucket_time
        async with self.lock:
            if (
                self.calculator_last_sync is None
                or self.calculator_last_sync != bucket
            ):
                self.logger.debug("The calculator needs to be synced with the current time")
                if not self.data:
                    self.logger.debug("no data available yet, fetching data")
                    try:
                        await self._async_update_data()
                    except UpdateFailed as exc:
                        self.logger.warning(
                            f"Failed to fetch initial data during calculator sync: {exc}"
                        )
                        return

                current_date = now.date()
                if self._last_cleanup_date is None or self._last_cleanup_date != current_date:
                    self.logger.debug("new day detected: cleanup stale data")
                    self._last_cleanup_date = current_date

                    self.data = {
                        hour: price
                        for hour, price in self.data.items()
                        if hour >= self.today - timedelta(days=1)
                    }

            self.calculator_last_sync = bucket

    @property
    def _filtered_prices(self) -> dict:
        if self.calculation_mode == CALCULATION_MODE["rotation"]:
            return {
                ts: price
                for ts, price in self.data.items()
                if self.today <= ts < self.today + timedelta(days=1)
            }
        elif self.calculation_mode == CALCULATION_MODE["sliding"]:
            return {ts: price for ts, price in self.data.items() if ts >= self.current_bucket_time}
        elif (
                self.calculation_mode == CALCULATION_MODE["publish"] and len(self.data) > 48
        ):
            return {ts: price for ts, price in self.data.items() if ts >= self.today}
        elif self.calculation_mode == CALCULATION_MODE["publish"]:
            return {
                ts: price
                for ts, price in self.data.items()
                if ts >= self.today - timedelta(days=1)
            }

        self.logger.error("Unknown calculation mode, returning empty filtered prices")
        return {}

    def get_max_price(self):
        prices = self._filtered_prices
        if not prices:
            return None
        return max(prices.values())

    def get_min_price(self):
        prices = self._filtered_prices
        if not prices:
            return None
        return min(prices.values())

    def get_max_time(self):
        prices = self._filtered_prices
        if not prices:
            return None
        return max(prices, key=prices.get)

    def get_min_time(self):
        prices = self._filtered_prices
        if not prices:
            return None
        return min(prices, key=prices.get)

    def get_avg_price(self):
        prices = self._filtered_prices
        if not prices:
            return None
        return round(sum(prices.values()) / len(prices.values()), 5)

    def get_percentage_of_max(self):
        current_price = self.get_current_price()
        max_price = self.get_max_price()
        if current_price is None or max_price is None or max_price == 0:
            return None
        return round(current_price / max_price * 100, 1)

    def get_percentage_of_range(self):
        current_price = self.get_current_price()
        min_price = self.get_min_price()
        max_price = self.get_max_price()
        if current_price is None or min_price is None or max_price is None:
            return None
        spread = max_price - min_price
        if spread == 0:
            return 100.0
        return round((current_price - min_price) / spread * 100, 1)

    async def get_energy_prices(self, start_date, end_date):
        if (
                len(self.get_data(start_date)) > MIN_HOURS
                and len(self.get_data(end_date)) > MIN_HOURS
        ):
            self.logger.debug("return prices from coordinator cache.")
            return {
                k: v
                for k, v in self.data.items()
                if k.date() >= start_date.date() and k.date() <= end_date.date()
            }
        try:
            data = await self.fetch_prices()
        except UpdateFailed as exc:
            raise HomeAssistantError(
                f"Failed to fetch energy prices from Energiedirect: {exc}"
            ) from exc
        if data is self.data:
            return {
                k: v
                for k, v in data.items()
                if k.date() >= start_date.date() and k.date() <= end_date.date()
            }
        return self.parse_hourprices(data)
