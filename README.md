# Home energy analysis: solar, Powerwall, heat pump and EV

One house in Salford, Greater Manchester: 24 JA Solar 450 W panels (10.8 kWp; 14 on a south-east roof and 10 on a north-east roof), a Tesla Powerwall 3, an Octopus Cosy 9 heat pump and a Tesla Model Y charged through a Hypervolt Home 3 Pro. This repository holds the open data and analysis code behind a series of posts about a year of its energy use, **21 October 2025 to 20 October 2026**.

## Posts

| # | Post | Status |
|---|------|--------|
| 1 | A year of solar, a Powerwall and a heat pump: what 365 days of data say | draft; link to be added |
| 2 | Choosing when to switch between Octopus Cosy and Intelligent Go: a case study and the principles behind the model | planned |
| 3 | A more general seasonal tariff-switching tool for Octopus customers | depends on community interest |

## What is here

```
data/
  daily_energy_weather.csv        365 daily rows: solar, grid, home, car and weather
  car_reported_monthly_kwh.csv    EV charging as reported by the car, per billing month
  DATA_DICTIONARY.md              every column, its unit and how it was derived
analysis/
  stats.py                        reproduces every statistic quoted in post 1
  make_charts.py                  reproduces the nine post 1 charts from the CSV
charts/post1/                     the nine charts as published (PNG)
```

## Reproduce the results

```
pip install -r requirements.txt
python analysis/stats.py
python analysis/make_charts.py
```

`make_charts.py` rewrites the PNGs in `charts/post1/` from the CSV.

## The headline findings (post 1)

- Solar generated 9,109 kWh, from 160 kWh in the weakest billing month to 1,563 kWh in the strongest.
- Daily solar output follows daily sunshine hours (r = 0.89), but a sunshine hour is worth about 1.3 kWh in winter and about 3.1 kWh in summer.
- Whole-house consumption follows the cold: below about 12.5 °C each degree colder adds roughly 4.3 kWh a day (R² = 0.80, 338 days at home).
- The house imported 10,457 kWh and exported 6,176 kWh; it was a net exporter in five billing months (May to September).
- From 22 July to 17 August the house was empty and drew a flat 9.6 kWh a day.

## Things to know before reusing the data

- **Billing months run from the 21st to the 20th** and are named for the month they end in.
- Import includes electricity the Powerwall charged from the grid, and export includes Powerwall discharge. Between 25 May and 15 September the Powerwall was set to cycle fully once a day, exporting between 11 pm and midnight (20% reserve kept), and it was refilled overnight from the grid.
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

Bills, tariff rates, costs, account and meter identifiers, API keys and half-hourly data. Never commit those: the `.gitignore` in this repo blocks common patterns, but check before every push.

## Licences

- Data (`data/`, `charts/`): [CC BY 4.0](LICENSE-DATA.md). Please credit the author and Open-Meteo.
- Code (`analysis/`): [MIT](LICENSE).

## Author

Aravind Vijayaraghavan. Corrections and comparisons with similar homes are welcome via issues.
