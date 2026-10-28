"""Check the battery planner against what the house was actually billed. Percentages only. Needs private files.

Run from the repository root:
    python switch_model/validate_planner.py --bills bill_daily.json --halfhour halfhour.csv.gz

Replays every day with the day's actual home load, solar and car kWh (data/daily_energy_weather.csv) on the tariff the house was on,
at the half-hourly import and export rates actually charged that day, and compares the planner's cost with the billed energy cost
(import cost minus export income, standing charge excluded on both sides).
bill_daily.json: one row per day with date, cost_in, inc_out and cov (share of the day's half hours with a meter reading).
halfhour.csv.gz: columns t (UTC timestamp), rate_in, rate_out (pence per kWh) for each half hour.
Both files stay out of the repository (see .gitignore). This script uses only the planner, so it tests the dispatch logic
independently of the rate-history table used in the switching analysis.
"""
import os, sys, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import sim, model as M, tariffs as T

ap = argparse.ArgumentParser(); ap.add_argument('--bills', required=True); ap.add_argument('--halfhour', required=True); ap.add_argument('--out'); ap.add_argument('--export-grid', action='store_true', help='let the battery export energy bought from the grid (mixed-integer planner)')
args = ap.parse_args()

c = pd.read_csv(os.path.join(M.ROOT, 'data', 'daily_energy_weather.csv'), parse_dates=['date']).set_index('date')
D = M.load_inputs()
h = pd.read_csv(args.halfhour); h['t'] = pd.to_datetime(h.t, utc=True).dt.tz_convert('Europe/London')
h['date'] = h.t.dt.date; h['hh'] = h.t.dt.hour * 2 + h.t.dt.minute // 30
R = h.groupby(['date', 'hh']).rate_in.mean().unstack(); XR = h.groupby(['date', 'hh']).rate_out.mean().unstack().mean(axis=1)
b = pd.read_json(args.bills); b['date'] = pd.to_datetime(b.date); b = b.set_index('date')
tariff = b['tariff'].reindex(D.index).replace({'iog': 'go'})      # the tariff each day was billed on
good = (b['cov'].reindex(D.index) >= 0.99) & D.car.notna() & R.reindex(D.index.date).notna().all(axis=1).values

rows = []
for d in D.index[good.values]:
    r = R.loc[d.date()].values
    off = pd.Timestamp(d).tz_localize('Europe/London').replace(hour=12).utcoffset().total_seconds() / 3600
    res = sim.solve_day(D.home[d] * sim.load_shape(T.FLAT_LOAD), D.sol[d] * sim.solar_shape(d, off), r, XR.loc[d.date()], B=T.BATTERY_KWH, P=T.POWER_KW,
                        Pd=T.POWER_KW, eta_c=T.EFFICIENCY, eta_d=T.EFFICIENCY, window=(r <= r.min() + 0.01), export_grid=args.export_grid)
    rows.append(dict(date=d, tariff=tariff[d], sim=res['cost'] + D.car[d] * r.min() / 100, billed=b.cost_in[d] - b.inc_out[d],
                     sim_imp=res['imp'], gate_imp=c.grid_import_kwh[d], sim_exp=res['exp'], gate_exp=c.grid_export_kwh[d]))
V = pd.DataFrame(rows).set_index('date'); e = V.sim - V.billed
avg_day = V.billed.sum() / len(V)
out = []
def line(name, m):
    """net error = planner minus billed, summed over the subset, as a share of the whole year's billed total (a subset's own billed total can be
    near zero or negative when export income exceeds import cost, so a share of its own total is not meaningful)."""
    isMonth = name[:2] == '20'
    out.append(dict(subset=name, days=int(m.sum()), net_error_pct_of_annual_billed=100 * e[m].sum() / V.billed.sum(),
                    net_error_pct_of_avg_month=(100 * e[m].sum() / (V.billed.sum() / 12)) if isMonth else np.nan,
                    mean_abs_daily_error_pct_of_avg_day=100 * e[m].abs().mean() / avg_day,
                    import_bias_kwh_per_day=(V.sim_imp - V.gate_imp)[m].mean(), export_bias_kwh_per_day=(V.sim_exp - V.gate_exp)[m].mean()))
line('all validated days', V.index == V.index)
for t in ('cosy', 'go'): line('days on ' + t, (V.tariff == t).values)
for mth, g in V.groupby(V.index.to_period('M')): line(str(mth), (V.index.to_period('M') == mth))
O = pd.DataFrame(out).round(2); print(O.to_string(index=False))
if args.out: O.to_csv(args.out, index=False)
