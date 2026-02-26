# Home Assistant Energiedirect Dynamic Prices

Custom component for Home Assistant to fetch dynamic electricity and gas prices from [Energiedirect](https://www.energiedirect.nl/dynamische-tarieven).

Prices are updated hourly and can be used in automations to switch equipment based on cheap/expensive energy windows. The 24-hour price forecast is available as sensor attributes and can be visualized in a graph.

### No API Key Required

This integration uses the public Energiedirect pricing API. No registration or API key is needed.

### Data Source

Prices are fetched from:
```
https://www.energiedirect.nl/api/public/dynamicpricing/dynamic-prices/v1
```

The API returns data for yesterday, today, and tomorrow (when available). Prices are in EUR/kWh (electricity) or EUR/m³ (gas) including 21% BTW.

---

## Sensors

Each configured integration instance adds the following sensors (for electricity or gas):

- **Current market price** — price for the current hour
- **Next hour market price** — price for the next hour
- **Average price** — average over the configured calculation window (carries `prices_today`, `prices_tomorrow`, and `prices` as attributes)
- **Highest price** — maximum over the configured window
- **Lowest price** — minimum over the configured window
- **Current % of highest price** — percentage of current price relative to the maximum
- **Current % of price range** — percentage of current price within the min/max spread
- **Time of highest price** — timestamp of the most expensive hour
- **Time of lowest price** — timestamp of the cheapest hour

---

## Installation

### HACS (recommended)

1. In HACS, go to **Integrations → ⋮ → Custom repositories**
2. Add `https://github.com/davidvpe/hass-energiedirect` with category **Integration**
3. Install "Energiedirect Dynamic Prices" from HACS
4. Restart Home Assistant

### Manual

Copy the `custom_components/energiedirect` folder into your Home Assistant `custom_components` directory and restart Home Assistant.

---

## Configuration

Go to **Settings → Devices & Services → Add Integration** and search for "Energiedirect Dynamic Prices".

### Setup options

| Field | Description |
|---|---|
| **Name** | Optional label to distinguish multiple instances |
| **Energy type** | Electricity (kWh) or Gas (m³) |
| **Advanced options** | Enable to configure VAT, price modifier template, and calculation mode |

### Advanced options

| Field | Description |
|---|---|
| **Additional VAT** | Extra VAT multiplier on top of the already-included 21% BTW (default: 0) |
| **Price Modifier Template** | Jinja2 template to transform `current_price`, e.g. `{{current_price + 0.05}}` |
| **Currency** | Currency symbol for sensor units (default: EUR) |
| **Energy scale** | `kWh` or `MWh` for electricity sensors (default: kWh) |
| **Calculation mode** | Window used for min/max/avg calculations (see below) |

### Calculation modes

| Mode | Description |
|---|---|
| **publish** | Today's data when available, otherwise yesterday+today (48h window) |
| **rotation** | Always the 24 hours of the current calendar day |
| **sliding** | Only future prices from the current hour onward |

---

## Price Modifier Template

The `current_price` variable contains the raw price from the API (incl. 21% BTW). Use the template to add fixed costs or apply custom markup:

```
{{current_price + 0.03}}
```

---

## Multiple Instances

You can add the integration multiple times with different names to track both electricity and gas prices simultaneously.

---

## Disclaimer

This project is not affiliated with, endorsed by, or in any way associated with Energiedirect or its parent company. The use of the Energiedirect name is solely for descriptive purposes. This integration uses a publicly accessible API endpoint; use it at your own risk.

---

## Credits

This integration is based on [hass-entso-e](https://github.com/JaccoR/hass-entso-e) by [@JaccoR](https://github.com/JaccoR), licensed under Apache 2.0. The coordinator architecture, sensor structure, and calculation modes are derived from that work. The data source has been replaced with the public Energiedirect dynamic pricing API.
