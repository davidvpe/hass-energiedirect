"""Tests for EnergieDirectClient._parse_response()"""

import pytest
import pytz
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.energiedirect.api_client import EnergieDirectClient, EnergieDirectException

AMSTERDAM_TZ = pytz.timezone("Europe/Amsterdam")

SAMPLE_RESPONSE = {
    "prices": [
        {
            "date": "2026-02-25",
            "electricity": {
                "energyType": "electricity",
                "unitOfMeasurement": "kWh",
                "vatPercentage": 21,
                "tariffs": [
                    {
                        "startDateTime": "2026-02-25T00:00:00",
                        "endDateTime": "2026-02-25T01:00:00",
                        "totalAmount": 0.23335,
                        "totalAmountEx": 0.19285,
                        "totalAmountVat": 0.0405,
                        "groups": []
                    },
                    {
                        "startDateTime": "2026-02-25T01:00:00",
                        "endDateTime": "2026-02-25T02:00:00",
                        "totalAmount": 0.21100,
                        "totalAmountEx": 0.17438,
                        "totalAmountVat": 0.03662,
                        "groups": []
                    },
                ],
            },
            "gas": {
                "energyType": "gas",
                "unitOfMeasurement": "m³",
                "vatPercentage": 21,
                "tariffs": [
                    {
                        "startDateTime": "2026-02-25T00:00:00",
                        "endDateTime": "2026-02-25T01:00:00",
                        "totalAmount": 1.17091,
                        "totalAmountEx": 0.96769,
                        "totalAmountVat": 0.20322,
                        "groups": []
                    },
                ],
            }
        },
        {
            "date": "2026-02-26",
            "electricity": {
                "energyType": "electricity",
                "unitOfMeasurement": "kWh",
                "vatPercentage": 21,
                "tariffs": [
                    {
                        "startDateTime": "2026-02-26T00:00:00",
                        "endDateTime": "2026-02-26T01:00:00",
                        "totalAmount": 0.25597,
                        "totalAmountEx": 0.21154,
                        "totalAmountVat": 0.04443,
                        "groups": []
                    },
                ],
            },
            "gas": {
                "energyType": "gas",
                "unitOfMeasurement": "m³",
                "vatPercentage": 21,
                "tariffs": [
                    {
                        "startDateTime": "2026-02-26T00:00:00",
                        "endDateTime": "2026-02-26T01:00:00",
                        "totalAmount": 1.16492,
                        "totalAmountEx": 0.96274,
                        "totalAmountVat": 0.20218,
                        "groups": []
                    },
                ],
            }
        }
    ]
}


class TestParseResponse:

    def setup_method(self):
        self.client = EnergieDirectClient()

    def test_returns_electricity_and_gas_keys(self):
        result = self.client._parse_response(SAMPLE_RESPONSE)
        assert "electricity" in result
        assert "gas" in result

    def test_electricity_entry_count(self):
        result = self.client._parse_response(SAMPLE_RESPONSE)
        assert len(result["electricity"]) == 3  # 2 from day 1 + 1 from day 2

    def test_gas_entry_count(self):
        result = self.client._parse_response(SAMPLE_RESPONSE)
        assert len(result["gas"]) == 2  # 1 from day 1 + 1 from day 2

    def test_electricity_price_value(self):
        result = self.client._parse_response(SAMPLE_RESPONSE)
        dt = AMSTERDAM_TZ.localize(datetime(2026, 2, 25, 0, 0, 0))
        assert result["electricity"][dt] == pytest.approx(0.23335)

    def test_gas_price_value(self):
        result = self.client._parse_response(SAMPLE_RESPONSE)
        dt = AMSTERDAM_TZ.localize(datetime(2026, 2, 25, 0, 0, 0))
        assert result["gas"][dt] == pytest.approx(1.17091)

    def test_datetimes_are_timezone_aware(self):
        result = self.client._parse_response(SAMPLE_RESPONSE)
        for dt in result["electricity"]:
            assert dt.tzinfo is not None
        for dt in result["gas"]:
            assert dt.tzinfo is not None

    def test_datetimes_are_amsterdam_timezone(self):
        result = self.client._parse_response(SAMPLE_RESPONSE)
        for dt in result["electricity"]:
            assert dt.tzinfo.zone == "Europe/Amsterdam"

    def test_empty_prices_list(self):
        result = self.client._parse_response({"prices": []})
        assert result["electricity"] == {}
        assert result["gas"] == {}

    def test_missing_prices_key(self):
        result = self.client._parse_response({})
        assert result["electricity"] == {}
        assert result["gas"] == {}

    def test_missing_electricity_key(self):
        data = {
            "prices": [
                {
                    "date": "2026-02-25",
                    "gas": SAMPLE_RESPONSE["prices"][0]["gas"]
                }
            ]
        }
        result = self.client._parse_response(data)
        assert result["electricity"] == {}
        assert len(result["gas"]) == 1

    def test_missing_gas_key(self):
        data = {
            "prices": [
                {
                    "date": "2026-02-25",
                    "electricity": SAMPLE_RESPONSE["prices"][0]["electricity"]
                }
            ]
        }
        result = self.client._parse_response(data)
        assert len(result["electricity"]) == 2
        assert result["gas"] == {}

    def test_tariff_with_missing_total_amount_is_skipped(self):
        data = {
            "prices": [
                {
                    "date": "2026-02-25",
                    "electricity": {
                        "tariffs": [{"startDateTime": "2026-02-25T00:00:00"}]
                    },
                    "gas": {"tariffs": []}
                }
            ]
        }
        result = self.client._parse_response(data)
        assert result["electricity"] == {}

    def test_tariff_with_missing_start_datetime_is_skipped(self):
        data = {
            "prices": [
                {
                    "date": "2026-02-25",
                    "electricity": {
                        "tariffs": [{"totalAmount": 0.23335}]
                    },
                    "gas": {"tariffs": []}
                }
            ]
        }
        result = self.client._parse_response(data)
        assert result["electricity"] == {}

    def test_multiple_days_merged(self):
        result = self.client._parse_response(SAMPLE_RESPONSE)
        dates = {dt.date() for dt in result["electricity"]}
        assert len(dates) == 2

    def test_second_day_electricity_price(self):
        result = self.client._parse_response(SAMPLE_RESPONSE)
        dt = AMSTERDAM_TZ.localize(datetime(2026, 2, 26, 0, 0, 0))
        assert result["electricity"][dt] == pytest.approx(0.25597)

    def test_groups_breakdown_parsed(self):
        data = {
            "prices": [{
                "date": "2026-02-25",
                "electricity": {
                    "tariffs": [{
                        "startDateTime": "2026-02-25T00:00:00",
                        "totalAmount": 0.23335,
                        "groups": [
                            {"type": "MARKET_PRICE", "amount": 0.05},
                            {"type": "PURCHASING_FEE", "amount": 0.10},
                            {"type": "TAX", "amount": 0.08},
                        ],
                    }]
                },
                "gas": {"tariffs": []},
            }]
        }
        result = self.client._parse_response(data)
        dt = AMSTERDAM_TZ.localize(datetime(2026, 2, 25, 0, 0, 0))
        breakdown = result["electricity_breakdown"][dt]
        assert breakdown["market_price"] == pytest.approx(0.05)
        assert breakdown["purchasing_fee"] == pytest.approx(0.10)
        assert breakdown["energy_tax"] == pytest.approx(0.08)

    def test_groups_with_unknown_type_ignored(self):
        data = {
            "prices": [{
                "date": "2026-02-25",
                "electricity": {
                    "tariffs": [{
                        "startDateTime": "2026-02-25T00:00:00",
                        "totalAmount": 0.23335,
                        "groups": [
                            {"type": "UNKNOWN_TYPE", "amount": 0.99},
                            {"type": "MARKET_PRICE", "amount": 0.05},
                        ],
                    }]
                },
                "gas": {"tariffs": []},
            }]
        }
        result = self.client._parse_response(data)
        dt = AMSTERDAM_TZ.localize(datetime(2026, 2, 25, 0, 0, 0))
        breakdown = result["electricity_breakdown"][dt]
        assert "market_price" in breakdown
        assert len(breakdown) == 1


@pytest.mark.asyncio
class TestFetchPrices:

    def _make_session_mock(self, get_cm):
        """Build an aiohttp.ClientSession async context manager mock."""
        mock_session = MagicMock()
        mock_session.get.return_value = get_cm

        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=False)
        return mock_session_cm

    async def test_fetch_prices_raises_on_http_error(self):
        import aiohttp
        client = EnergieDirectClient()

        # With raise_for_status=True, aiohttp raises ClientResponseError on __aenter__
        get_cm = MagicMock()
        get_cm.__aenter__ = AsyncMock(
            side_effect=aiohttp.ClientResponseError(
                request_info=MagicMock(), history=(), status=500
            )
        )
        get_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=self._make_session_mock(get_cm)):
            with pytest.raises(EnergieDirectException):
                await client.fetch_prices()

    async def test_fetch_prices_raises_on_connection_error(self):
        import aiohttp
        client = EnergieDirectClient()

        get_cm = MagicMock()
        get_cm.__aenter__ = AsyncMock(
            side_effect=aiohttp.ClientConnectorError(
                connection_key=MagicMock(), os_error=OSError()
            )
        )
        get_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=self._make_session_mock(get_cm)):
            with pytest.raises(EnergieDirectException):
                await client.fetch_prices()

    async def test_fetch_prices_returns_parsed_data_on_success(self):
        client = EnergieDirectClient()

        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value=SAMPLE_RESPONSE)

        get_cm = MagicMock()
        get_cm.__aenter__ = AsyncMock(return_value=mock_response)
        get_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=self._make_session_mock(get_cm)):
            result = await client.fetch_prices()

        assert "electricity" in result
        assert "gas" in result
        assert len(result["electricity"]) == 3
