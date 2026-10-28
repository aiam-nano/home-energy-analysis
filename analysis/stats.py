"""Headline statistics quoted in the post 'A year of solar, a Powerwall and a heat pump'.
Run from the repo root:  python analysis/stats.py
"""
import os
import numpy as np, pandas as pd
from scipy import stats

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = pd.read_csv(os.path.join(ROOT, 'data', 'daily_energy_weather.csv'))
d['dt'] = pd.to_datetime(d.date)
d['tmean'] = (d.temp_max_c + d.temp_min_c) / 2
d['month'] = d.dt.dt.month
away = d.away_from_home == 1
d['powerwall_export_est'] = d.grid_export_kwh - d.solar_exported_kwh   # export minus solar sent straight to the grid

def line(label, value): print(f'{label:<62}{value}')

print('--- Totals (kWh) ---')
for col in ['solar_generated_kwh', 'solar_to_house_kwh', 'solar_to_powerwall_kwh', 'solar_exported_kwh', 'grid_import_kwh', 'grid_export_kwh', 'home_consumption_kwh', 'car_and_other_kwh']:
    line(col, f'{d[col].sum():,.0f}')
line('share of solar kept on site (house + Powerwall)', f"{(d.solar_to_house_kwh.sum() + d.solar_to_powerwall_kwh.sum()) / d.solar_generated_kwh.sum():.0%}")

print('\n--- Solar against sunshine ---')
r = stats.linregress(d.sunshine_hours, d.solar_generated_kwh)
line('all days: r, slope kWh per sunshine hour', f'{r.rvalue:.2f}, {r.slope:.2f}')
for name, m in [('Nov-Feb', d.month.isin([11, 12, 1, 2])), ('Mar, Oct', d.month.isin([3, 10])), ('Apr-Sep', d.month.between(4, 9))]:
    r = stats.linregress(d[m].sunshine_hours, d[m].solar_generated_kwh)
    line(f'{name}: r, slope, intercept (kWh)', f'{r.rvalue:.2f}, {r.slope:.2f}, {r.intercept:.2f}')
line('max temperature against sunshine, r', f"{stats.pearsonr(d.sunshine_hours, d.temp_max_c)[0]:.2f}")

print('\n--- Home consumption against temperature (away days excluded) ---')
x = d[~away]
best = None
for T0 in np.arange(10, 19.1, 0.5):
    hdd = np.maximum(0, T0 - x.tmean)
    r = stats.linregress(hdd, x.home_consumption_kwh)
    if best is None or r.rvalue > best[1].rvalue: best = (T0, r)
T0, r = best
line('balance point (deg C), slope kWh per degree-day, intercept, R2', f'{T0:.1f}, {r.slope:.2f}, {r.intercept:.1f}, {r.rvalue**2:.2f}')
line('days used', len(x))
A = np.c_[np.ones(len(x)), np.maximum(0, 12.5 - x.tmean), x.sunshine_hours]
c = np.linalg.lstsq(A, x.home_consumption_kwh, rcond=None)[0]
line('with sunshine added: kWh per sunshine hour (at 12.5 C balance point)', f'{c[2]:.2f}')

print('\n--- Away period (flag in the CSV) ---')
a = d[away]
line('days, dates', f"{len(a)}, {a.date.min()} to {a.date.max()}")
line('home consumption mean, sd (kWh/day)', f'{a.home_consumption_kwh.mean():.2f}, {a.home_consumption_kwh.std():.2f}')
line('generated, exported, imported, consumed (kWh)', f'{a.solar_generated_kwh.sum():,.0f}, {a.grid_export_kwh.sum():,.0f}, {a.grid_import_kwh.sum():,.0f}, {a.home_consumption_kwh.sum():,.0f}')

print('\n--- Powerwall daily cycle window, 5 April to 17 September 2026 ---')
# Octopus half-hourly export shows the nightly discharge: an evening export on 5-6 April, then a
# 23:30-00:30 dump from 12 April to 17 September. 5 April is also the day the house moved to Intelligent Go.
START, END = '2026-04-05', '2026-09-17'
w = (d.date >= START) & (d.date <= END)
line('days in window', f'{w.sum()}')
line('Powerwall export estimate: year, in window, before, after (kWh)',
     f"{d.powerwall_export_est.sum():,.0f}, {d[w].powerwall_export_est.sum():,.0f}, {d[d.date < START].powerwall_export_est.sum():,.0f}, {d[d.date > END].powerwall_export_est.sum():,.0f}")
line('days above 1 kWh, mean per day, mean on those days (kWh)',
     f"{(d[w].powerwall_export_est > 1).sum()}, {d[w].powerwall_export_est.mean():.1f}, {d[w][d[w].powerwall_export_est > 1].powerwall_export_est.mean():.1f}")
line('import in window: mean, median, 10th and 90th percentile (kWh/day)',
     f"{d[w].grid_import_kwh.mean():.1f}, {d[w].grid_import_kwh.median():.1f}, {d[w].grid_import_kwh.quantile(.1):.1f}, {d[w].grid_import_kwh.quantile(.9):.1f}")
m = d[w].assign(month=d[w].date.astype(str).str[:7]).groupby('month')
print(m.agg(days=('date', 'size'), pw_export=('powerwall_export_est', 'sum'), mean_import=('grid_import_kwh', 'mean'), sd_import=('grid_import_kwh', 'std')).round(1).to_string())
