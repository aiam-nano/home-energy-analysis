# Data dictionary

Period: 21 October 2025 to 20 October 2026, 365 days, Salford, Greater Manchester. One row per calendar day (local date).

## daily_energy_weather.csv

| Column | Unit | Source and meaning |
|---|---|---|
| `date` | YYYY-MM-DD | Local calendar day |
| `solar_generated_kwh` | kWh | Tesla Powerwall gateway: total solar generated |
| `solar_to_house_kwh` | kWh | Solar used directly by the house |
| `solar_to_powerwall_kwh` | kWh | Solar that charged the Powerwall |
| `solar_exported_kwh` | kWh | Solar sent straight to the grid |
| `grid_import_kwh` | kWh | Gateway grid import. Includes Powerwall charging from the grid |
| `grid_export_kwh` | kWh | Gateway grid export. Includes Powerwall discharge as well as solar |
| `home_consumption_kwh` | kWh | Tesla "Home total" through the gateway. Includes about 1,200 kWh over the year that Tesla lists under "Charged". Excludes the car |
| `car_and_other_kwh` | kWh | Octopus meter import minus gateway import, negative values set to zero. This is the car plus anything else outside the gateway. Blank for 4 days where the meter record is incomplete |
| `temp_max_c` | °C | Open-Meteo daily maximum temperature for a point in Salford |
| `temp_min_c` | °C | Open-Meteo daily minimum temperature |
| `sunshine_hours` | hours | Open-Meteo daily sunshine duration (modelled, not a site sensor) |
| `away_from_home` | 0/1 | 1 for 22 July to 17 August 2026 (27 days), when the house was empty |

## car_reported_monthly_kwh.csv

| Column | Unit | Meaning |
|---|---|---|
| `billing_month` | YYYY-MM | Billing month, 21st to 20th, named for the month it ends in (`2025-11` is 21 October to 20 November 2025) |
| `car_reported_kwh` | kWh | Energy the car reports charging in that billing month |

## Derived quantities used in the analysis

- **Billing month**: from the date; days 21 to month end belong to the next month.
- **Mean temperature**: (`temp_max_c` + `temp_min_c`) / 2.
- **Powerwall export estimate**: `grid_export_kwh` minus `solar_exported_kwh`. A rough proxy, about 818 kWh over the year.
- **Heating degree days**: max(0, balance point minus mean temperature), balance point chosen by best fit (12.5 °C).

## Known caveats

- The Powerwall was set to cycle fully once a day between 25 May and 15 September 2026, exporting between 11 pm and midnight with a 20% reserve, and was refilled overnight from the grid. This shapes summer import and export.
- The heat pump is not metered separately.
- Temperatures and sunshine are modelled point values, not readings from the house.
