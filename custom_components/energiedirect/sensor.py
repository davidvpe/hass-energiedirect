"""Energiedirect current electricity and gas price information service."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HassJob, HomeAssistant
from homeassistant.helpers import event
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import utcnow, slugify

from .utils import bucket_time
from .const import (
    ATTRIBUTION,
    CONF_CURRENCY,
    CONF_ENERGY_SCALE,
    CONF_ENERGY_TYPE,
    CONF_ENTITY_NAME,
    DEFAULT_CURRENCY,
    DEFAULT_ENERGY_SCALE,
    DEFAULT_ENERGY_TYPE,
    DOMAIN,
    ENERGY_TYPE_GAS,
)
from .coordinator import EnergieDirectCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class EnergieDirectEntityDescription(SensorEntityDescription):
    """Describes Energiedirect sensor entity."""

    value_fn: Callable[[EnergieDirectCoordinator], StateType] = None


def sensor_descriptions(
    energy_label: str, currency: str, unit: str
) -> tuple[EnergieDirectEntityDescription, ...]:
    """Construct EnergieDirectEntityDescription."""
    return (
        EnergieDirectEntityDescription(
            key="current_price",
            name=f"Current {energy_label} market price",
            native_unit_of_measurement=f"{currency}/{unit}",
            state_class=SensorStateClass.MEASUREMENT,
            icon="mdi:currency-eur",
            suggested_display_precision=3,
            value_fn=lambda coordinator: coordinator.get_current_price(),
        ),
        EnergieDirectEntityDescription(
            key="next_hour_price",
            name=f"Next hour {energy_label} market price",
            native_unit_of_measurement=f"{currency}/{unit}",
            state_class=SensorStateClass.MEASUREMENT,
            icon="mdi:currency-eur",
            suggested_display_precision=3,
            value_fn=lambda coordinator: coordinator.get_next_price(),
        ),
        EnergieDirectEntityDescription(
            key="min_price",
            name=f"Lowest {energy_label} price",
            native_unit_of_measurement=f"{currency}/{unit}",
            state_class=SensorStateClass.MEASUREMENT,
            icon="mdi:currency-eur",
            suggested_display_precision=3,
            value_fn=lambda coordinator: coordinator.get_min_price(),
        ),
        EnergieDirectEntityDescription(
            key="max_price",
            name=f"Highest {energy_label} price",
            native_unit_of_measurement=f"{currency}/{unit}",
            state_class=SensorStateClass.MEASUREMENT,
            icon="mdi:currency-eur",
            suggested_display_precision=3,
            value_fn=lambda coordinator: coordinator.get_max_price(),
        ),
        EnergieDirectEntityDescription(
            key="avg_price",
            name=f"Average {energy_label} price",
            native_unit_of_measurement=f"{currency}/{unit}",
            state_class=SensorStateClass.MEASUREMENT,
            icon="mdi:currency-eur",
            suggested_display_precision=3,
            value_fn=lambda coordinator: coordinator.get_avg_price(),
        ),
        EnergieDirectEntityDescription(
            key="percentage_of_max",
            name=f"Current percentage of highest {energy_label} price",
            native_unit_of_measurement=f"{PERCENTAGE}",
            icon="mdi:percent",
            suggested_display_precision=1,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda coordinator: coordinator.get_percentage_of_max(),
        ),
        EnergieDirectEntityDescription(
            key="percentage_of_range",
            name=f"Current percentage in {energy_label} price range",
            native_unit_of_measurement=f"{PERCENTAGE}",
            icon="mdi:percent",
            suggested_display_precision=1,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda coordinator: coordinator.get_percentage_of_range(),
        ),
        EnergieDirectEntityDescription(
            key="highest_price_time_today",
            name=f"Time of highest {energy_label} price",
            device_class=SensorDeviceClass.TIMESTAMP,
            icon="mdi:clock",
            value_fn=lambda coordinator: coordinator.get_max_time(),
        ),
        EnergieDirectEntityDescription(
            key="lowest_price_time_today",
            name=f"Time of lowest {energy_label} price",
            device_class=SensorDeviceClass.TIMESTAMP,
            icon="mdi:clock",
            value_fn=lambda coordinator: coordinator.get_min_time(),
        ),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Energiedirect price sensor entries."""
    coordinator: EnergieDirectCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    energy_type = config_entry.options.get(CONF_ENERGY_TYPE, DEFAULT_ENERGY_TYPE)
    currency = config_entry.options.get(CONF_CURRENCY, DEFAULT_CURRENCY)
    energy_scale = config_entry.options.get(CONF_ENERGY_SCALE, DEFAULT_ENERGY_SCALE)

    if energy_type == ENERGY_TYPE_GAS:
        energy_label = "gas"
        unit = "m³"
    else:
        energy_label = "electricity"
        unit = energy_scale

    entities = []
    for description in sensor_descriptions(energy_label=energy_label, currency=currency, unit=unit):
        entities.append(
            EnergieDirectSensor(
                coordinator, description, config_entry.options[CONF_ENTITY_NAME]
            )
        )

    async_add_entities(entities, True)


class EnergieDirectSensor(CoordinatorEntity, RestoreSensor):
    """Representation of an Energiedirect sensor."""

    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: EnergieDirectCoordinator,
        description: EnergieDirectEntityDescription,
        name: str = "",
    ) -> None:
        """Initialize the sensor."""
        self.description = description
        self.last_update_success = True

        if name not in (None, ""):
            self.entity_id = f"{DOMAIN}.{slugify(name)}_{slugify(description.name)}"
            self._attr_unique_id = f"energiedirect.{name}_{description.key}"
            self._attr_name = f"{description.name} ({name})"
        else:
            self.entity_id = f"{DOMAIN}.{slugify(description.name)}"
            self._attr_unique_id = f"energiedirect.{description.key}"
            self._attr_name = f"{description.name}"

        self.entity_description: EnergieDirectEntityDescription = description
        self._attr_icon = description.icon
        self._attr_suggested_display_precision = (
            description.suggested_display_precision
            if description.suggested_display_precision is not None
            else 2
        )

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={
                (
                    DOMAIN,
                    f"{coordinator.config_entry.entry_id}_energiedirect",
                )
            },
            manufacturer="Energiedirect",
            model="",
            name="Energiedirect" + ((" (" + name + ")") if name != "" else ""),
        )

        self._update_job = HassJob(self.async_schedule_update_ha_state)
        self._unsub_update = None

        super().__init__(coordinator)

    async def async_added_to_hass(self) -> None:
        """Restore last known state on startup."""
        await super().async_added_to_hass()
        if (last_sensor_data := await self.async_get_last_sensor_data()) is not None:
            self._attr_native_value = last_sensor_data.native_value

    async def async_will_remove_from_hass(self) -> None:
        """Cancel scheduled updates when entity is removed."""
        if self._unsub_update:
            self._unsub_update()
            self._unsub_update = None
        await super().async_will_remove_from_hass()

    async def async_update(self) -> None:
        """Get the latest data and updates the states."""
        if self._unsub_update:
            self._unsub_update()
            self._unsub_update = None

        self._unsub_update = event.async_track_point_in_utc_time(
            self.hass,
            self._update_job,
            bucket_time(utcnow(), self.coordinator.period_minutes)
            + self.coordinator.update_interval,
        )

        await self.coordinator.sync_calculator()

        if (
            self.coordinator.data is not None
            and self.coordinator.today_data_available()
        ):
            value: Any = None
            try:
                value = self.entity_description.value_fn(self.coordinator)
                self._attr_native_value = value
                self.last_update_success = True
                _LOGGER.debug(f"updated '{self.entity_id}' to value: {value}")

            except Exception as exc:
                self.last_update_success = False
                _LOGGER.warning(
                    f"Unable to update entity '{self.entity_id}', value: {value} and error: {exc}, data: {self.coordinator.data}"
                )
        else:
            _LOGGER.warning(
                f"Unable to update entity '{self.entity_id}': No valid data for today available."
            )
            self.last_update_success = False

    @property
    def extra_state_attributes(self):
        if self.description.key != "avg_price":
            return None
        if self.native_value is None or self.coordinator.data is None:
            return None
        return {
            "prices_today": self.coordinator.get_prices_today(),
            "prices_tomorrow": self.coordinator.get_prices_tomorrow(),
        }

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.last_update_success
