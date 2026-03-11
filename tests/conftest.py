"""Mock Home Assistant modules so the package can be imported without HA installed."""

import sys
from unittest.mock import MagicMock

HA_MODULES = [
    "homeassistant",
    "homeassistant.config_entries",
    "homeassistant.const",
    "homeassistant.core",
    "homeassistant.exceptions",
    "homeassistant.helpers",
    "homeassistant.helpers.config_validation",
    "homeassistant.helpers.device_registry",
    "homeassistant.helpers.entity_platform",
    "homeassistant.helpers.event",
    "homeassistant.helpers.selector",
    "homeassistant.helpers.template",
    "homeassistant.helpers.typing",
    "homeassistant.helpers.update_coordinator",
    "homeassistant.components",
    "homeassistant.components.sensor",
    "homeassistant.util",
    "homeassistant.util.dt",
    "homeassistant.util.slugify",
    "async_timeout",
    "jinja2",
    "voluptuous",
]

for module in HA_MODULES:
    sys.modules[module] = MagicMock()
