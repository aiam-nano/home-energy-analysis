"""Does heating-degree-days (HDD) fit the home's daily consumption better than daily mean temperature? Percentages and kWh only.

Run from the repository root:   python switch_model/hdd_fit.py --hdd path/to/03351_HDD.csv
Inputs: data/daily_energy_weather.csv (public) and, optionally, a degreedays.net export for the nearest station (not redistributed here:
download your own at degreedays.net, bases 12.5-18.5 C, daily). Without --hdd only the Open-Meteo variants are run.
Writes   data/hdd_vs_mean_temperature.csv   one row per temperature representation
         charts/methods/hdd_vs_mean_temperature.png
Only days when someone was home are used for the fits (the away_from_home days sit at the house's standby load whatever the weather).

Representations compared (all fitted to the same days, same target, ordinary least squares):
    T mean, linear           load = a + b * Tmean
    T mean, hinge            load = a + b * max(0, T0 - Tmean)           T0 searched 8-19 C in 0.25 steps
    T mean, two slopes       load = a + b * max(0, T0 - Tmean) + b2 * max(0, Tmean - T0)   (is it flat above T0?)
    HDD from Open-Meteo      Met Office-style degree days from the day's max and min, base searched 12.5-18.5 C
    HDD degreedays.net       station figures (hourly-based), base searched 12.5-18.5 C
and each with the extra terms the switching model uses (HDD x sunshine fraction and the day's temperature range).
Cross-validation: 10-fold, repeated 20 times, with the base temperature chosen inside each training fold.
"""
import os, sys, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import model as M

ap = argparse.ArgumentParser(); ap.add_argument('--hdd'); ap.add_argument('--no-chart', action='store_true'); ap.add_argument('--switch', action='store_true', help='also rerun the switching verdict with each load model (about 1 minute)')
args = ap.parse_args()
ROOT = M.ROOT
c = pd.read_csv(os.path.join(ROOT, 'data', 'daily_energy_weather.csv'), parse_dates=['date']).set_index('date')
D = M.load_inputs(); home = c.away_from_home.astype(bool).values == False
D = D[home]; y = D.home.values; n = len(y)
dl = M.daylen(D.index.dayofyear.values.astype(float)); frac = np.clip(D.sun_h.values / dl, 0, 1); rng = (D.tmax - D.tmin).values
tm, tx, tn = D.tmean.values, D.tmax.values, D.tmin.values

def met_hdd(b):
    """Degree days from daily max and min (Met Office / Day-Haylock style approximation)."""
    h = np.where(b >= tx, b - tm, np.where(tm <= b, (b - tn) / 2 - (tx - b) / 4, np.where(tn < b, (b - tn) / 4, 0.0)))
    return np.clip(h, 0, None)

REP = {}                                   # name -> (list of candidate bases, function base -> hdd vector)
REP['Tmean hinge'] = (np.arange(8, 19.01, 0.25), lambda b: np.clip(b - tm, 0, None))
REP['HDD from Open-Meteo max/min'] = (np.arange(12.5, 18.51, 0.5), met_hdd)
if args.hdd:
    h = pd.read_csv(args.hdd, skiprows=6, parse_dates=['Date'], dayfirst=True).set_index('Date').reindex(D.index)
    assert h.notna().all().all(), 'HDD file does not cover every day'
    REP['HDD degreedays.net (station)'] = (np.arange(12.5, 18.51, 0.5), lambda b, h=h: h['HDD %s' % (('%.1f' % b).rstrip('0').rstrip('.'))].values)

def design(hdd, extras):
    X = [np.ones(n), hdd]
    if extras: X += [hdd * frac, rng]
    return np.column_stack(X)

def fit_pred(Xtr, ytr, Xte):
    b = np.linalg.lstsq(Xtr, ytr, rcond=None)[0]; return Xte @ b, b

def best_base(rep, idx, extras):
    bases, f = REP[rep]; best = None
    for b in bases:
        X = design(f(b), extras)[idx]; r = y[idx] - X @ np.linalg.lstsq(X, y[idx], rcond=None)[0]
        if best is None or (r ** 2).sum() < best[0]: best = ((r ** 2).sum(), b)
    return best[1]

rows = []
allidx = np.arange(n)
def score(name, extras, rep=None, X=None):
    if rep is not None:
        b = best_base(rep, allidx, extras); X = design(REP[rep][1](b), extras)
    else: b = np.nan
    pred, beta = fit_pred(X, y, X); e = y - pred
    k = X.shape[1]
    out = dict(representation=name, extras='+ sunshine and range' if extras else 'single term', best_base_C=b, n_days=n,
               R2=1 - e.var() / y.var(), RMSE_kwh=np.sqrt((e ** 2).mean()), slope_kwh_per_degC=beta[1])
    # repeated 10-fold CV, base chosen inside the training fold
    cv = []
    for seed in range(20):
        perm = np.random.RandomState(seed).permutation(n); folds = np.array_split(perm, 10); se = 0
        for te in folds:
            tr = np.setdiff1d(allidx, te)
            if rep is not None:
                bb = best_base(rep, tr, extras); Xf = design(REP[rep][1](bb), extras)
            else: Xf = X
            p, _ = fit_pred(Xf[tr], y[tr], Xf[te]); se += ((y[te] - p) ** 2).sum()
        cv.append(np.sqrt(se / n))
    out['CV_RMSE_kwh'] = np.mean(cv)
    rows.append(out); return out

score('Tmean, linear (no hinge)', False, X=np.column_stack([np.ones(n), tm]))
for ex in (False, True):
    for rep in REP: score(rep, ex, rep=rep)

# two-slope test: is the load really flat above the break?
best = None
for t0 in np.arange(8, 19.01, 0.25):
    X = np.column_stack([np.ones(n), np.clip(t0 - tm, 0, None), np.clip(tm - t0, 0, None)])
    b = np.linalg.lstsq(X, y, rcond=None)[0]; r = y - X @ b
    if best is None or (r ** 2).sum() < best[0]: best = ((r ** 2).sum(), t0, b, X, r)
_, t0, b, X, r = best
# bootstrap the slope above the break
bs = []
for s in range(500):
    i = np.random.RandomState(s).randint(0, n, n); Xb = np.column_stack([np.ones(n), np.clip(t0 - tm[i], 0, None), np.clip(tm[i] - t0, 0, None)])
    bs.append(np.linalg.lstsq(Xb, y[i], rcond=None)[0][2])
two = dict(break_C=t0, slope_below=b[1], slope_above=b[2], slope_above_ci95=(np.percentile(bs, 2.5), np.percentile(bs, 97.5)), R2=1 - r.var() / y.var())
rows.append(dict(representation='Tmean, two slopes (break at %.2f C)' % t0, extras='single term', best_base_C=t0, n_days=n, R2=two['R2'],
                 RMSE_kwh=np.sqrt((r ** 2).mean()), slope_kwh_per_degC=b[1], CV_RMSE_kwh=np.nan))
R = pd.DataFrame(rows)
pd.set_option('display.width', 220)
print(R.round(3).to_string(index=False))
print('two-slope test: slope below break %.2f kWh/degC, above %.2f kWh/degC (95%% bootstrap %.2f to %.2f)' % (two['slope_below'], two['slope_above'], *two['slope_above_ci95']))
R.round(3).to_csv(os.path.join(ROOT, 'data', 'hdd_vs_mean_temperature.csv'), index=False)
pd.Series(dict(break_C=t0, slope_below=b[1], slope_above=b[2], slope_above_lo=two['slope_above_ci95'][0], slope_above_hi=two['slope_above_ci95'][1])).round(3).to_csv(
    os.path.join(ROOT, 'data', 'hdd_two_slope_test.csv'), header=['value'])


# ---------------------------------------------------------------- chart
if not args.no_chart:
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    BG, INK, MUT, BL, OR = '#fcfcfb', '#1f2328', '#6b7280', '#2a78d6', '#eb6834'
    fig, ax = plt.subplots(1, 2, figsize=(12.5, 5.2), facecolor=BG, gridspec_kw=dict(width_ratios=[1.45, 1]))
    a = ax[0]; a.set_facecolor(BG)
    cc_ = pd.read_csv(os.path.join(ROOT, 'data', 'daily_energy_weather.csv'), parse_dates=['date']).set_index('date'); Da = M.load_inputs()
    away = cc_.away_from_home.astype(bool).values
    a.scatter(Da.tmean[away], Da.home[away], s=22, facecolor='none', edgecolor=MUT, lw=1, label='away from home (%d days, not fitted)' % away.sum(), zorder=2)
    a.scatter(tm, y, s=16, color=BL, alpha=.55, lw=0, label='at home (%d days)' % n, zorder=3)
    bins = np.arange(-4, 24, 2.0); mid = (bins[:-1] + bins[1:]) / 2; med = [np.median(y[(tm >= lo) & (tm < hi)]) if ((tm >= lo) & (tm < hi)).sum() > 2 else np.nan for lo, hi in zip(bins[:-1], bins[1:])]
    a.plot(mid, med, 'o', color=INK, ms=5, label='median of each 2 C band', zorder=5)
    xs = np.linspace(-4, 24, 200); a.plot(xs, b[0] + b[1] * np.clip(t0 - xs, 0, None) + b[2] * np.clip(xs - t0, 0, None), color=OR, lw=2.4, label='two-slope fit', zorder=4)
    a.axvline(t0, color=OR, lw=1, ls=':');     a.text(25.5, 48, 'slope above the break\n%+.2f kWh per C\n(95%% range %+.2f to %+.2f)' % (two['slope_above'], *two['slope_above_ci95']), color=INK, fontsize=9.5, ha='right')
    a.set_xlabel('daily mean outdoor temperature (C)', color=INK); a.set_ylabel('home consumption (kWh per day)', color=INK)
    a.set_title('Consumption stops falling once it is warmer than about 13 C', loc='left', color=INK, fontsize=12.5, fontweight='bold')
    a.legend(frameon=False, fontsize=9, loc='upper right', bbox_to_anchor=(1, .9)); a.text(t0 + .3, 100, 'break %.1f C' % t0, color=OR, fontsize=10, va='top'); a.grid(alpha=.18)
    z = ax[1]; z.set_facecolor(BG)
    Rr = R[R.CV_RMSE_kwh.notna()].copy(); Rr['lab'] = Rr.representation.str.replace(' + sunshine and range', '') + np.where(Rr.extras.str.startswith('+'), '\n+ sunshine and range', '')
    Rr = Rr.iloc[::-1]; yy_ = np.arange(len(Rr)); cols = [OR if 'degreedays' in l else BL for l in Rr.representation]
    z.hlines(yy_, Rr.CV_RMSE_kwh.min() - 1.0, Rr.CV_RMSE_kwh, color=cols, lw=1.2, alpha=.5); z.scatter(Rr.CV_RMSE_kwh, yy_, s=70, color=cols, zorder=3)
    for i, v in zip(yy_, Rr.CV_RMSE_kwh): z.text(v + .08, i + .02, '%.2f' % v, va='center', color=INK, fontsize=9.5)
    z.set_yticks(yy_); z.set_yticklabels(Rr.lab, fontsize=8.5, color=INK); z.set_xlim(Rr.CV_RMSE_kwh.min() - 0.5, Rr.CV_RMSE_kwh.max() + .6)
    z.set_xlabel('error on days not used for the fit (kWh/day, lower is better)', color=INK, fontsize=9.5)
    z.set_title('HDD does not fit better than the hinge', loc='left', color=INK, fontsize=12.5, fontweight='bold'); z.grid(axis='x', alpha=.18); z.text(0.0, -0.2, 'blue: weather at the house location; orange: Rostherne station HDD', transform=z.transAxes, fontsize=8.5, color=MUT)
    for q in ax: [q.spines[k].set_visible(False) for k in ('top', 'right')]; q.tick_params(colors=MUT)
    fig.tight_layout(); fig.savefig(os.path.join(ROOT, 'charts', 'methods', 'hdd_vs_mean_temperature.png'), dpi=170, facecolor=BG)

# ---------------------------------------------------------------- does the choice of temperature representation move the switching verdict?
if args.switch:
    sys.argv = [sys.argv[0]]                      # knockout.py parses its own (optional) arguments on import
    import knockout as K
    Dall = M.load_inputs(); dates = Dall.index; homeall = (c.away_from_home.astype(bool).values == False)
    dla = M.daylen(dates.dayofyear.values.astype(float)); fra = np.clip(Dall.sun_h.values / dla, 0, 1); rnga = (Dall.tmax - Dall.tmin).values
    tma = Dall.tmean.values
    hall = None
    if args.hdd:
        hall = pd.read_csv(args.hdd, skiprows=6, parse_dates=['Date'], dayfirst=True).set_index('Date').reindex(dates)
    def station(b): return hall['HDD %s' % (('%.1f' % b).rstrip('0').rstrip('.'))].values
    def load_model(hdd_of, bases, mask, extras=True):
        """Fit load = a + b HDD (+ c HDD x sunshine + d range) on the days in mask, base chosen by least squares; return the predicted load for every day."""
        yy = Dall.home.values; best = None
        for b in bases:
            h = hdd_of(b); X = np.column_stack([np.ones(len(yy)), h] + ([h * fra, rnga] if extras else []))
            beta = np.linalg.lstsq(X[mask], yy[mask], rcond=None)[0]; r = yy[mask] - X[mask] @ beta
            if best is None or (r ** 2).sum() < best[0]: best = ((r ** 2).sum(), b, beta, X)
        _, b, beta, X = best
        return pd.Series(np.maximum(5.0, X @ beta), index=dates), b
    allm = np.ones(len(dates), bool)
    hinge = lambda b: np.clip(b - tma, 0, None)
    cands = [('chain as published: hinge on mean temperature, all 365 days, base 12-19 C', *load_model(hinge, np.arange(12, 19, 0.5), allm)),
             ('hinge on mean temperature, at-home days only', *load_model(hinge, np.arange(8, 19.01, 0.25), homeall)),
             ('hinge on mean temperature, at-home days only, single term (no sunshine, range)', *load_model(hinge, np.arange(8, 19.01, 0.25), homeall, False))]
    if hall is not None:
        cands.append(('degreedays.net station HDD, at-home days only', *load_model(station, np.arange(12.5, 18.51, 0.5), homeall)))
    P = M.fit_chain(Dall)
    Sh = pd.Series([M.predict_DS(P, d, Dall.tmax[d], Dall.tmin[d], Dall.sun_h[d])[1] for d in dates], index=dates)
    REF = K.year(K.D.home, K.D.sol, K.carA); base = REF.cosy[K.act == 'cosy'].sum() + REF.iog[K.act == 'iog'].sum()
    cm = K.carA.mean(); out = []
    for name, Dh, b in cands:
        Y = K.year(Dh, Sh, pd.Series(cm, index=dates))
        m = K.metrics(Y, REF, name, base); m.pop('_pounds'); m['base_C'] = b
        m['load_MAE_kwh_at_home_days'] = float((Dh - Dall.home).abs()[homeall].mean()); out.append(m)
        print(name, round(b, 2), {k: (round(v, 2) if isinstance(v, float) else v) for k, v in m.items() if k != 'variant'}, flush=True)
    pd.DataFrame(out).round(2).to_csv(os.path.join(ROOT, 'data', 'hdd_switch_effect_percent.csv'), index=False)
