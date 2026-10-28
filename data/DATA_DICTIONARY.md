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

- The Powerwall was set to cycle fully once a day from 5 April to 17 September 2026, exporting in the evening (5 and 6 April) and then between about 11:30 pm and 12:30 am (from 12 April) with a 20% reserve, and was refilled overnight from the grid. This shapes spring and summer import and export.
- The heat pump is not metered separately.
- Temperatures and sunshine are modelled point values, not readings from the house.

## Post 2 result files (percentages only)

- `tariff_rates_history.csv`: Cosy and Intelligent Go rates (pence per kWh including VAT) and standing charges (pence per day) in force between `from_date` and `to_date`, region G. `low_p_per_kwh`, `mid_p_per_kwh` and `peak_p_per_kwh` are the cheap, standard and peak rates for Cosy and the night and day rates for Go (Go has no peak). Go is the variable product before 5 April 2026 and the 12-month fixed product from 5 April 2026.
- `switch_strategies_percent.csv`: annual simulated cost of each strategy as a percentage of the cost with the switch dates actually used (23 Oct and 5 Apr), and the difference from that baseline.
- `switch_sensitivity_percent.csv`: how much dearer the year is, in per cent, if both hindsight-best switch dates are moved together by `shift_days`.
- `switch_fixed_vs_flexible_percent.csv`: for leaving Cosy on 1 March or 5 April, how much dearer fixed Cosy (12 months, 50 pound exit fee) is than flexible Cosy from 28 October, in per cent, for each assumed rise in flexible rates on 21 January. Columns show the result with and without the exit fee.

## Methods result files (percentages only)

- `knockout_percent.csv`: one row per knockout variant. `cosy_pct` and `go_pct` are the year on each tariff as a percentage of the reference's annual cost on the tariffs actually used; `saving_pct` is Cosy minus Go; `d_saving_pct` is the change in that gap against the reference; `day_MAE_pct` is the mean absolute daily error as a percentage of an average day; `sign7` and `corr7` compare the 7-day mean saving with the reference; `switch_dates` are the hindsight-best autumn and spring switch dates; `regret_pct` is what those dates cost on the reference savings. Edge dates (28 Feb, 1 Feb) mean the search found no interior optimum.
- `ev_reblocking_percent.csv`: the car's charging under charger-power and plug-in limits. Cost columns are the extra cost over charging at the cheapest rate, as a percentage of the same base; `days_overflow` counts days the allowed slots could not hold the day's kWh; `kwh_outside_cheap_window` is energy placed in dearer slots; `kwh_delivered` is constant by construction.
- `naive_vs_planner_percent.csv`, `naive_by_tariff_of_origin_percent.csv`, `planner_shape_check.csv`: the naive-method comparison and the import-shape check. These need Octopus half-hourly files to reproduce.
- `planner_validation_percent.csv`: the planner against billed energy cost. `net_error_pct_of_annual_billed` is planner minus billed, summed over the subset, as a share of the whole year's billed total; `net_error_pct_of_avg_month` is the same against an average month (month rows only). Needs private bill files to reproduce.
- `planner_validation_gridexport_percent.csv`: the same with the battery allowed to sell energy bought from the grid (`--export-grid`).
- `hdd_vs_mean_temperature.csv`, `hdd_two_slope_test.csv`: fits of the home's daily load to mean temperature and to heating degree-days on the days someone was home, and the test of whether load is flat above the break. `hdd_switch_effect_percent.csv`: the switching verdict with each load model feeding the weather chain. The degree-day file itself is not included (download from degreedays.net).
