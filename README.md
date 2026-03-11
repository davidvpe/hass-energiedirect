# Home Assistant Energiedirect Dynamic Prices

Custom component for Home Assistant to fetch dynamic electricity and gas prices from [Energiedirect](https://www.energiedirect.nl/dynamische-tarieven).

Prices are updated hourly and can be used in automations to switch equipment based on cheap/expensive energy windows. The 24-hour price forecast is available as sensor attributes and can be visualized in a graph.

Although this integration uses the Energiedirect API, the underlying hourly spot prices (APX for electricity, TTF for gas) are the same across all Dutch dynamic pricing providers. This means it can also be used by customers of other providers such as Vandebron, Tibber, or any other supplier that passes through the same market rate — just use the price modifier template to add your provider's fixed costs on top.

### No API Key Required

This integration uses the public Energiedirect pricing API. No registration or API key is needed.

### Data Source

Prices are fetched from:
```
https://www.energiedirect.nl/api/public/dynamicpricing/dynamic-prices/v1
```

The API returns data for yesterday, today, and tomorrow (when available). Prices are in EUR/kWh (electricity) or EUR/m³ (gas). The integration uses the ex-VAT price and applies 21% BTW by default.

---

## Sensors

Each configured integration instance adds the following sensors (for electricity or gas).

- **Current market price** — spot market price for the current hour, with the price modifier template and VAT applied. Useful as the main price signal for automations, especially for non-Energiedirect providers.
- **Next hour market price** — same as above but for the next hour
- **Average price** — average total price over the configured calculation window
- **Highest price** — maximum total price over the configured window
- **Lowest price** — minimum total price over the configured window
- **Current % of highest price** — percentage of current price relative to the maximum
- **Current % of price range** — percentage of current price within the min/max spread
- **Time of highest price** — timestamp of the most expensive hour
- **Time of lowest price** — timestamp of the cheapest hour

### Sensor attributes

The **Current market price** sensor exposes a price breakdown as attributes:

| Attribute | Description |
|---|---|
| `price` | Market price with template modifier and VAT applied |
| `purchasing_fee` | Provider purchasing fee (scaled, no template) |
| `energy_tax` | Provider energy tax (scaled, no template) |
| `provider_total_price` | Sum of all three components |

The **Average price** sensor exposes `prices_today` and `prices_tomorrow` as attributes. Each entry in these lists contains the same four fields: `provider_total_price`, `price`, `purchasing_fee`, and `energy_tax`.

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
| **VAT (BTW)** | VAT rate applied to the market price component (default: 0.21). The API returns prices excluding VAT, so 21% is applied by default. Adjust only if your situation requires a different rate. |
| **Price Modifier Template** | Jinja2 template applied exclusively to the market price component, e.g. `{{current_price + 0.05}}` |
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

The `current_price` variable in the template contains the **raw spot market price** (EUR/kWh or EUR/m³, scaled to your chosen unit, excluding VAT). The API returns prices excluding BTW — VAT (default 21%) is applied automatically. The template modifier and the VAT field apply **exclusively to this market price component**. The provider's purchasing fee and energy tax are added on top without modification.

This means the total sensor value is:

```
total = template(market_price) × (1 + VAT) + purchasing_fee + energy_tax
```

Use the template to add your provider's fixed costs or supplier margin on top of the spot rate:

```
{{current_price + 0.13656}}
```

If you are an Energiedirect customer, the `provider_total_price` attribute already reflects the full Energiedirect price. If you are with another provider (Vandebron, Tibber, etc.), use the **Current market price** sensor with your provider's template to get the correct total for your bill.

---

## Multiple Instances

You can add the integration multiple times with different names to track both electricity and gas prices simultaneously.

---

## Disclaimer

This project is not affiliated with, endorsed by, or in any way associated with Energiedirect or its parent company. The use of the Energiedirect name is solely for descriptive purposes. This integration uses a publicly accessible API endpoint; use it at your own risk.

---

## Credits

This integration is based on [hass-entso-e](https://github.com/JaccoR/hass-entso-e) by [@JaccoR](https://github.com/JaccoR), licensed under Apache 2.0. The coordinator architecture, sensor structure, and calculation modes are derived from that work. The data source has been replaced with the public Energiedirect dynamic pricing API.
