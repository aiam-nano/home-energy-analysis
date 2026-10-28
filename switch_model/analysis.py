"""Switching analysis for post 2: everything is reported as a percentage, never in pounds.

Run from the repository root:  python switch_model/analysis.py
Reads data/daily_energy_weather.csv, prices every day on each tariff at the rates in force that day, and writes
percentage-only results to data/switch_*.csv. Costs are cached in switch_model/cache/ (git-ignored).
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import model as M, tariffs as T
from scipy.optimize import brentq

CACHE = os.path.join(M.ROOT, 'switch_model', 'cache'); os.makedirs(CACHE, exist_ok=True)
OUT = os.path.join(M.ROOT, 'data')

def cached(name, fn):
    p = os.path.join(CACHE, name + '.pkl')
    if os.path.exists(p): return pd.read_pickle(p)
    v = fn(); v.to_pickle(p); return v

D = M.load_inputs()
C = cached('truth_costs_hist', lambda: M.counterfactual(D))                 # actual home/solar/car on each tariff, rates of the day
CC = cached('truth_costs_current', lambda: M.counterfactual(D, ('cosy', 'iog', 'iogvar'), hist=False))   # same at 27 Oct 2026 rates (forward-looking example only)
P = M.fit_chain(D)
F = cached('chain_costs_hist', lambda: M.predicted_costs(D, P))                  # weather-predicted home/solar on each tariff
idx = C.index

# ---- schedules: IOG, then Cosy from date a to date b (exclusive), then IOG again
def schedule_cost(a, b, df=C, cosy='cosy', iog='iog'):
    m = (idx >= pd.Timestamp(a)) & (idx < pd.Timestamp(b))
    return df[cosy][m].sum() + df[iog][~m].sum()

ACTUAL = ('2025-10-23', '2026-04-05')            # the dates actually used
base = schedule_cost(*ACTUAL)

def best_two_switch(df):
    cs = df.cosy.cumsum().values; ci = df.iog.cumsum().values; n = len(df)
    cs0 = np.concatenate([[0], cs]); ci0 = np.concatenate([[0], ci])
    best = (1e18, None)
    for i in range(n + 1):
        j = np.arange(i, n + 1)
        cost = ci0[i] + (cs0[j] - cs0[i]) + (ci0[-1] - ci0[j])
        k = cost.argmin()
        if cost[k] < best[0]: best = (cost[k], (i, int(j[k])))
    i, j = best[1]
    return best[0], idx[i] if i < n else None, idx[j] if j < n else None

hind_cost, hind_a, hind_b = best_two_switch(C)
model_cost_at_own, mod_a, mod_b = best_two_switch(F)      # best dates according to the weather-predicted costs
model_dates_truth_cost = schedule_cost(mod_a, mod_b)       # what those dates would really have saved

rows = [
    ('Cosy all year', C.cosy.sum()),
    ('Intelligent Go all year', C.iog.sum()),
    ('Your switch dates (23 Oct, 5 Apr)', base),
    ('Best dates in hindsight (%s, %s)' % (hind_a.strftime('%-d %b'), hind_b.strftime('%-d %b')), hind_cost),
    ('Best dates chosen from weather model (%s, %s)' % (mod_a.strftime('%-d %b'), mod_b.strftime('%-d %b')), model_dates_truth_cost),
]
strat = pd.DataFrame([(n, 100 * v / base, 100 * (v / base - 1)) for n, v in rows], columns=['strategy', 'cost_vs_actual_pct', 'difference_pct'])
strat.round(1).to_csv(os.path.join(OUT, 'switch_strategies_percent.csv'), index=False)

# per-switch regret as % of the annual cost on the user's schedule
def gain_curve(sav, start, end, frm):
    s = sav.loc[start:end]; sign = 1 if frm == 'cosy' else -1
    return pd.Series({d: sign * s.loc[d:].sum() for d in s.index})
sav = C.cosy - C.iog
g_aut = gain_curve(sav, '2025-10-21', '2026-02-28', 'iog'); g_spr = gain_curve(sav, '2026-02-01', '2026-06-30', 'cosy')
reg = {'autumn_best': str(g_aut.idxmax().date()), 'autumn_actual': '2025-10-23', 'autumn_regret_pct': round(100 * (g_aut.max() - g_aut.loc['2025-10-23']) / base, 1),
       'spring_best': str(g_spr.idxmax().date()), 'spring_actual': '2026-04-05', 'spring_regret_pct': round(100 * (g_spr.max() - g_spr.loc['2026-04-05']) / base, 1)}

# sensitivity: move both hindsight-best switch dates together by k days
shifts = list(range(-42, 43, 7))
sens = pd.DataFrame({'shift_days': shifts, 'cost_above_best_pct': [100 * (schedule_cost(hind_a + pd.Timedelta(days=k), hind_b + pd.Timedelta(days=k)) / hind_cost - 1) for k in shifts]}).round(2)
sens.to_csv(os.path.join(OUT, 'switch_sensitivity_percent.csv'), index=False)

# weather chain accuracy
w = pd.concat([(C.cosy - C.iog), (F.cosy - F.iog)], axis=1, keys=['truth', 'model']).rolling(7, center=True).mean().dropna()
daily = pd.concat([(C.cosy - C.iog), (F.cosy - F.iog)], axis=1, keys=['truth', 'model'])
acc = {'corr_daily': round(daily.truth.corr(daily.model), 2), 'corr_7day': round(w.truth.corr(w.model), 2),
       'sign_agree_7day': round(float(((w.truth > 0) == (w.model > 0)).mean()), 3),
       'home_r2': round(P['r2_home'], 2), 'solar_r2': round(P['r2_solar'], 2), 'balance_point_c': float(P['T0'])}

# ---- fixed vs flexible Cosy example: leave in spring, rates rise on 21 January
FX = T.COSY_FIXED; sc_flex = T.TARIFFS['cosy']['sc'] / 100; sc_fix = FX['sc'] / 100
ratio = FX['cheap'] / 14.0651
energy = CC.cosy - sc_flex                                   # daily energy cost on flexible Cosy, standing charge removed
def fixed_vs_flex(exit_md, u, start_md=(10, 28), rise_md=(1, 21), fee=True):
    """Dearer-by fraction of fixed Cosy against flexible Cosy from 28 Oct to exit, if flexible rates rise by u on 21 Jan.
    The model year (Oct 2025 to Oct 2026) stands in for the coming winter."""
    ew = energy[(idx >= pd.Timestamp(2025, *start_md)) & (idx < pd.Timestamp(2026, *exit_md))]
    rise = pd.Timestamp(2026, *rise_md); pre = ew[ew.index < rise]; post = ew[ew.index >= rise]; n = len(ew)
    flex = pre.sum() + sc_flex * len(pre) + (post.sum() + sc_flex * len(post)) * (1 + u)
    fixed = ew.sum() * ratio + sc_fix * n + (FX['exit_fee_pounds'] if fee else 0)
    return (fixed - flex) / flex * 100, flex
exits = {'exit 1 Mar': (3, 1), 'exit 5 Apr': (4, 5)}
us = [0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35]
ff = pd.DataFrame([{'exit': k, 'flexible_rise_pct': 100 * u, 'fixed_dearer_pct_with_fee': fixed_vs_flex(e, u)[0], 'fixed_dearer_pct_no_fee': fixed_vs_flex(e, u, fee=False)[0]} for k, e in exits.items() for u in us]).round(1)
ff.to_csv(os.path.join(OUT, 'switch_fixed_vs_flexible_percent.csv'), index=False)
be = {k: {'with_fee': round(100 * brentq(lambda u: fixed_vs_flex(e, u)[0], 0, 1), 1), 'no_fee': round(100 * brentq(lambda u: fixed_vs_flex(e, u, fee=False)[0], 0, 1), 1)} for k, e in exits.items()}
fee_share = {k: round(100 * FX['exit_fee_pounds'] / fixed_vs_flex(e, 0)[1], 1) for k, e in exits.items()}

summary = dict(strategies=strat.round(1).to_dict('records'), regret=reg, chain_accuracy=acc, hindsight=[str(hind_a.date()), str(hind_b.date())],
               model_dates=[str(mod_a.date()), str(mod_b.date())], fixed_rate_premium_pct=round(100 * (ratio - 1), 1), fixed_sc_premium_pct=round(100 * (sc_fix / sc_flex - 1), 1),
               breakeven_rise_pct=be, exit_fee_share_of_flexible_cost_pct=fee_share)
print(json.dumps(summary, indent=1))
print(sens.to_string(index=False)); print(ff.to_string(index=False))
