from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict

import aiohttp
import pytz
from aiohttp import ClientError

_LOGGER = logging.getLogger(__name__)

API_URL = "https://www.energiedirect.nl/api/public/dynamicpricing/dynamic-prices/v1"
AMSTERDAM_TZ = pytz.timezone("Europe/Amsterdam")


class EnergieDirectException(Exception):
    pass


class EnergieDirectClient:

    async def fetch_prices(self) -> Dict[str, Dict[datetime, float]]:
        """
        Fetch dynamic prices from Energiedirect API.

        Returns a dict with two keys: 'electricity' and 'gas',
        each mapping datetime -> Beursprijs amountEx (market price excl. VAT).
        Datetimes are timezone-aware (Europe/Amsterdam).
        """
        timeout = aiohttp.ClientTimeout(total=10, connect=5)
        headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
        }

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(API_URL, headers=headers, raise_for_status=True) as response:
                    data = await response.json()
        except aiohttp.ClientResponseError as exc:
            raise EnergieDirectException(f"HTTP error fetching Energiedirect prices: {exc}") from exc
        except ClientError as exc:
            raise EnergieDirectException(f"Connection error fetching Energiedirect prices: {exc}") from exc

        return self._parse_response(data)

    def _parse_response(self, data: dict) -> dict:
        electricity: Dict[datetime, float] = {}
        gas: Dict[datetime, float] = {}
        electricity_breakdown: Dict[datetime, dict] = {}
        gas_breakdown: Dict[datetime, dict] = {}

        breakdown_targets = {
            "electricity": electricity_breakdown,
            "gas": gas_breakdown,
        }

        _GROUP_TYPE_MAP = {
            "MARKET_PRICE": "market_price",
            "PURCHASING_FEE": "purchasing_fee",
            "TAX": "energy_tax",
        }

        for day_entry in data.get("prices", []):
            for energy_type, target in (("electricity", electricity), ("gas", gas)):
                energy_data = day_entry.get(energy_type)
                if not energy_data:
                    continue
                for tariff in energy_data.get("tariffs", []):
                    start_str = tariff.get("startDateTime")
                    if start_str is None:
                        continue

                    breakdown = {}
                    for group in tariff.get("groups", []):
                        key = _GROUP_TYPE_MAP.get(group.get("type"))
                        if key is not None and group.get("amountEx") is not None:
                            breakdown[key] = group["amountEx"]

                    market_price = breakdown.get("market_price")
                    if market_price is None:
                        continue

                    dt = datetime.strptime(start_str, "%Y-%m-%dT%H:%M:%S")
                    dt_aware = AMSTERDAM_TZ.localize(dt)
                    target[dt_aware] = market_price
                    breakdown_targets[energy_type][dt_aware] = breakdown

        return {
            "electricity": electricity,
            "gas": gas,
            "electricity_breakdown": electricity_breakdown,
            "gas_breakdown": gas_breakdown,
        }
