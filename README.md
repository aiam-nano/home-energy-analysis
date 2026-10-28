# Home energy analysis: solar, Powerwall, heat pump and EV

One house in Salford, Greater Manchester: 24 JA Solar 450 W panels (10.8 kWp; 14 on a south-east roof and 10 on a north-east roof), a Tesla Powerwall 3, an Octopus Cosy 9 heat pump and a Tesla Model Y charged through a Hypervolt Home 3 Pro. This repository holds the open data and analysis code behind a series of posts about a year of its energy use, **21 October 2025 to 20 October 2026**.

## Posts

| # | Post | Status |
|---|------|--------|
| 1 | A year of living green with solar, battery, heat pump and EV: what 365 days of data say | [published](https://aiamnano.substack.com/p/a-year-of-living-green) |
| 2 | Choosing when to switch between Octopus Cosy and Intelligent Go: a case study and the principles behind the model | in preparation |

## What is here

```
data/
  daily_energy_weather.csv        365 daily rows: solar, grid, home, car and weather
  car_reported_monthly_kwh.csv    EV charging as reported by the car, per billing month
  DATA_DICTIONARY.md              every column, its unit and how it was derived
analysis/
  stats.py                        reproduces every statistic quoted in post 1
  make_charts.py                  reproduces the nine post 1 charts from the CSV
  switch_strategies_percent.csv   post 2: annual cost of each switching strategy, in per cent
  switch_sensitivity_percent.csv  post 2: cost of moving the switch dates, in per cent
  switch_fixed_vs_flexible_percent.csv  post 2: fixed against flexible Cosy, in per cent
  tariff_rates_history.csv        post 2: Cosy and Go rates and standing charges in force on each date (public prices, region G)
switch_model/
  tariffs.py                      Octopus tariff rates: the history actually in force (data/tariff_rates_history.csv) and the 27 Oct 2026 prices
  sim.py                          half-hourly battery planner, one day on one tariff (linear programme)
  model.py                        daily cost of each tariff for this house, plus the weather-to-load/solar chain
  analysis.py                     strategies, hindsight dates, sensitivity, fixed against flexible Cosy
  make_charts_post2.py            the nine post 2 charts
  knockout.py                     knockout (ablation) tests, EV re-blocking tests, optional naive-method and shape checks
  validate_planner.py             planner against billed costs (needs private bill files; percentages only)
                                  --export-grid lets the battery sell grid-bought energy
  hdd_fit.py                      degree-days versus mean temperature for the home load (needs your own degreedays.net file for the station comparison)
  plot_knockout.py                redraws charts/methods/knockout_summary_percent.png from data/knockout_percent.csv
charts/post1/                     the nine post 1 charts as published (PNG)
charts/post2/                     the nine post 2 charts (PNG)
charts/methods/                   three charts for the methods document (PNG)
docs/
  METHODS_tariff_switch_model.md  how the model works, how the battery and car are handled, every test, and where each number comes from
```

## Reproduce the results

```
pip install -r requirements.txt
python analysis/stats.py
python analysis/make_charts.py
```

`make_charts.py` rewrites the PNGs in `charts/post1/` from the CSV.

Post 2 (switching analysis, about a minute):

```
python switch_model/analysis.py
python switch_model/make_charts_post2.py
```

The knockout and EV tests (about nine minutes, public data only; group D3 solves a mixed-integer programme for every day):

```
python switch_model/knockout.py
```

See `docs/METHODS_tariff_switch_model.md` for what each variant tests and how to switch on the optional checks that use your own Octopus files.

`analysis.py` prices every day on each tariff at the Cosy and Go rates that were in force on that day (`data/tariff_rates_history.csv`), using the daily CSV only, and writes percentage-only results to `data/switch_*.csv`. Go is the variable product before 5 April 2026 and the 12-month fixed product from then. The forward-looking fixed-versus-flexible example uses the rates published on 27 October 2026 (`COSY_FIXED` and `TARIFFS` in `switch_model/tariffs.py`). It caches daily simulated costs in `switch_model/cache/`, which is git-ignored; delete that folder to recompute.

## The headline findings (post 1)

- Solar generated 9,109 kWh, from 160 kWh in the weakest billing month to 1,563 kWh in the strongest.
- Daily solar output follows daily sunshine hours (r = 0.89), but a sunshine hour is worth about 1.3 kWh in winter and about 3.1 kWh in summer.
- Whole-house consumption follows the cold: below about 12.5 °C each degree colder adds roughly 4.3 kWh a day (R² = 0.80, 338 days at home).
- The house imported 10,457 kWh and exported 6,176 kWh; it was a net exporter in five billing months (May to September).
- From 22 July to 17 August the house was empty and drew a flat 9.6 kWh a day.

## Switching analysis (post 2)

- Costs are simulated at the Octopus rates in force on each day, using each day's actual home load, solar and car charging, with a planner that charges the battery in the cheap windows. They are not the bills actually paid, and the results are reported only as percentages.
- Against my two actual switches (23 Oct and 5 Apr), staying on Cosy all year would have cost about 16% more and staying on Intelligent Go all year about 5% less. The best dates in hindsight (22 Nov and 10 Feb) would have cost about 8% less than mine, and dates chosen from the weather model about the same (7.6% less).
- The planner knows each day's load and solar in advance, so it is an upper bound on what a real battery controller achieves. It was checked against the actual bills privately (not included here).
- Early termination fees can change the picture substantially; the fixed against flexible Cosy example shows how.

## Things to know before reusing the data

- **Billing months run from the 21st to the 20th** and are named for the month they end in.
- Import includes electricity the Powerwall charged from the grid, and export includes Powerwall discharge. From 5 April to 17 September the Powerwall was set to cycle fully once a day (a discharge to the grid in the evening or around 11:30 pm to midnight, 20% reserve kept), and it was refilled overnight from the grid. This coincides with the move to Intelligent Go on 5 April.
- Home consumption is Tesla's "Home total" and includes about 1,200 kWh filed under Tesla's "Charged" label that I could not separate.
- Sunshine is modelled (Open-Meteo), not measured on site.
- The heat pump is not metered separately, so no coefficient of performance can be derived from this data.
- The away-from-home flag is inferred from the data (a flat consumption plateau) and confirmed by the owner.

See `data/DATA_DICTIONARY.md` for details.

## Credits and AI assistance

- Weather data by [Open-Meteo.com](https://open-meteo.com/), licensed CC BY 4.0.
- Energy data from a Tesla Powerwall gateway and an Octopus Energy smart meter.
- Data processing, statistics, charts and first drafts of the posts were produced with Claude Sonnet 5.5 (Anthropic), directed and reviewed by the author.

## What is deliberately left out

Bills and the costs actually paid, account and meter identifiers, API keys and half-hourly meter data. (The tariff rates in `data/tariff_rates_history.csv` and `switch_model/tariffs.py` are Octopus's public prices, and simulated costs are reported only as percentages.) Never commit the private items: the `.gitignore` in this repo blocks common patterns, but check before every push.

## Licences

- Data (`data/`, `charts/`): [CC BY 4.0](LICENSE-DATA.md). Please credit the author and Open-Meteo.
- Code (`analysis/`, `switch_model/`): [MIT](LICENSE).

## Author

Aravind Vijayaraghavan. Corrections and comparisons with similar homes are welcome via issues.
