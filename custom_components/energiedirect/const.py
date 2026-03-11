from homeassistant.const import CURRENCY_EURO

ATTRIBUTION = "Data provided by Energiedirect"
DOMAIN = "energiedirect"
UNIQUE_ID = f"{DOMAIN}_component"
COMPONENT_TITLE = "Energiedirect Dynamic Prices"

CONF_ENTITY_NAME = "name"
CONF_MODIFYER = "modifyer"
CONF_CURRENCY = "currency"
CONF_ENERGY_SCALE = "energy_scale"
CONF_ADVANCED_OPTIONS = "advanced_options"
CONF_CALCULATION_MODE = "calculation_mode"
CONF_VAT_VALUE = "VAT_value"
CONF_ENERGY_TYPE = "energy_type"

ENERGY_TYPE_ELECTRICITY = "electricity"
ENERGY_TYPE_GAS = "gas"
ENERGY_TYPES = {
    ENERGY_TYPE_ELECTRICITY: "Electricity (kWh)",
    ENERGY_TYPE_GAS: "Gas (m³)",
}

DEFAULT_MODIFYER = "{{current_price}}"
DEFAULT_CURRENCY = CURRENCY_EURO
DEFAULT_ENERGY_SCALE = "kWh"
DEFAULT_ENERGY_TYPE = ENERGY_TYPE_ELECTRICITY
DEFAULT_VAT = 0.21

# default is only for internal use / backwards compatibility
CALCULATION_MODE = {
    "default": "publish",
    "rotation": "rotation",
    "sliding": "sliding",
    "publish": "publish",
}

ENERGY_SCALES = {"kWh": 1, "MWh": 0.001}
