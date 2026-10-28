"""Knockout (ablation) tests of the tariff-switch model. Everything is reported as a percentage, never in pounds.

Run from the repository root:   python switch_model/knockout.py
Needs only data/daily_energy_weather.csv and data/tariff_rates_history.csv. It writes
    data/knockout_percent.csv        one row per variant of the model (see docs/METHODS_tariff_switch_model.md, section 8)
    data/ev_reblocking_percent.csv   car charging under charger-power and plug-in-window limits (section 6)
Optional extras (each is skipped if its file is not given):
    --import-csv F --export-csv F    Octopus half-hourly consumption exports (columns interval_start, kwh_or_units).
                                     Adds the 'naive reprice' variant, the shape check and data/naive_vs_planner_percent.csv.
    --bills F                        a bill_daily.json (private) for the naive-reprice-against-bill sanity check.
    --pounds-out F                   also write the same tables in pounds to F (keep private; the name must match *PRIVATE*).

Definitions used by every variant (section 7 of the methods document):
    reference            actual home load, solar and car kWh of each day, battery 12 kWh / 5 kW / 95% one way, load shape 80% flat,
                         priced at the rates in force on that day, car at the cheapest rate of the day's tariff.
    base                 annual cost of the reference on the tariffs actually used (Go to 22 Oct, Cosy 23 Oct to 4 Apr, Go from 5 Apr).
                         All costs below are percentages of base. 'avg day' means base / 365.
    saving               Cosy cost minus Go cost; positive means Go is cheaper.
    day_MAE_pct          mean absolute error of the daily saving against the reference, as % of the average day.
    sign7 / corr7        agreement in sign / correlation of the 7-day centred mean saving with the reference.
    switch dates         hindsight-best single switch in each window (autumn 21 Oct-28 Feb from Go to Cosy, spring 1 Feb-30 Jun
                         from Cosy to Go) according to the variant.
    regret_pct           what following the variant's dates costs, evaluated on the reference savings, as % of base.
"""
import os, sys, argparse, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import sim, model as M, tariffs as T

ap = argparse.ArgumentParser()
ap.add_argument('--import-csv'); ap.add_argument('--export-csv'); ap.add_argument('--bills'); ap.add_argument('--pounds-out')
args = ap.parse_args()
OUT = os.path.join(M.ROOT, 'data')

D = M.load_inputs(); dates = D.index
carA = D.car.fillna(D.car.median())                  # 4 days have an incomplete meter record: filled with the median
KEYS = ('cosy', 'iog')
ACTUAL = ('2025-10-23', '2026-04-05')                # dates the tariffs were actually changed
act = pd.Series(np.where((dates >= ACTUAL[0]) & (dates < ACTUAL[1]), 'cosy', 'iog'), index=dates)
RT = {k: {d: T.rates_on(k, d) for d in dates} for k in KEYS}     # (48 rates p/kWh, standing p/day) in force on each day
SH = {d: sim.solar_shape(d, pd.Timestamp(d).tz_localize('Europe/London').replace(hour=12).utcoffset().total_seconds() / 3600) for d in dates}

# ---------------------------------------------------------------- planner wrapper with overridable physical parameters
def plan(d, home, sol, key, B=T.BATTERY_KWH, flat=T.FLAT_LOAD, P=T.POWER_KW, xr=T.EXPORT_RATE, eta=T.EFFICIENCY, anywin=False, xor=False, xgrid=False):
    r, sc = RT[key][d]
    res = sim.solve_day(home * sim.load_shape(flat), sol * SH[d], r, xr, B=B, P=P, Pd=P, eta_c=eta, eta_d=eta,
                        window=None if anywin else (r <= r.min() + 0.01), xor=xor, export_grid=xgrid)
    return res, r, sc

def day_cost(d, home, sol, car, key, **kw):
    res, r, sc = plan(d, home, sol, key, **kw)
    return res['cost'] + car * r.min() / 100 + sc / 100

def year(Ds, Ss, Cs, **kw):
    return pd.DataFrame({k: [day_cost(d, Ds[d], Ss[d], Cs[d], k, **kw) for d in dates] for k in KEYS}, index=dates)

# ---------------------------------------------------------------- hindsight switch search and metrics
WIN = [(('2025-10-21', '2026-02-28'), 'iog'), (('2026-02-01', '2026-06-30'), 'cosy')]
def best_switch(sav, win, frm):
    """Gain from switching away from `frm` on each date in the window, relative to staying (sav = Cosy minus Go, daily)."""
    s = sav.loc[win[0]:win[1]]; sign = 1 if frm == 'cosy' else -1
    return pd.Series({d: sign * s.loc[d:].sum() for d in s.index})

def metrics(V, ref, name, base):
    sav = V.cosy - V.iog; rs = ref.cosy - ref.iog
    w = pd.concat([sav, rs], axis=1).rolling(7, center=True).mean().dropna()
    avg_day = base / len(dates)
    o = dict(variant=name, cosy_pct=100 * V.cosy.sum() / base, go_pct=100 * V.iog.sum() / base, saving_pct=100 * sav.sum() / base,
             d_saving_pct=100 * (sav.sum() - rs.sum()) / base, day_MAE_pct=100 * (sav - rs).abs().mean() / avg_day,
             sign7=((w.iloc[:, 0] > 0) == (w.iloc[:, 1] > 0)).mean(), corr7=w.iloc[:, 0].corr(w.iloc[:, 1]))
    reg = 0; ds = []
    for win, frm in WIN:
        gv = best_switch(sav, win, frm); gr = best_switch(rs, win, frm); dv = gv.idxmax()
        ds.append(dv.strftime('%d %b')); reg += gr.max() - gr.loc[dv]
    o['switch_dates'] = ' / '.join(ds); o['regret_pct'] = 100 * reg / base
    o['_pounds'] = dict(cosy=V.cosy.sum(), go=V.iog.sum(), saving=sav.sum(), d_saving=sav.sum() - rs.sum(), day_MAE=(sav - rs).abs().mean(), regret=reg)
    return o

# ---------------------------------------------------------------- EV: re-blocking the car's kWh into each tariff's cheap slots
def alloc(kwh, r, mask, pmax):
    """Deliver `kwh` to the car in the cheapest allowed slots. At most pmax*0.5 kWh per half hour. Returns (kWh per slot, kWh that did
    not fit inside the allowed slots). Overflow is placed in the cheapest remaining slots anywhere, so the kWh delivered never changes.
    Filling slots cheapest-first is the exact optimum for a linear cost with a per-slot cap."""
    cap = pmax * 0.5; a = np.zeros(48); rem = kwh
    for j in np.argsort(r, kind='stable'):
        if not mask[j]: continue
        x = min(cap, rem); a[j] = x; rem -= x
        if rem <= 1e-9: break
    spill = max(rem, 0.0)
    if rem > 1e-9:
        for j in np.argsort(r, kind='stable'):
            x = min(cap - a[j], rem); a[j] += x; rem -= x
            if rem <= 1e-9: break
    assert abs(a.sum() - kwh) < 1e-6, 'kWh not conserved'
    return a, spill

ALL = np.ones(48, bool); NIGHT = np.zeros(48, bool); NIGHT[44:48] = True; NIGHT[0:14] = True    # plugged in 22:00-07:00
EV_SCEN = [('any slot 7.4 kW', ALL, 7.4), ('any slot 3.6 kW', ALL, 3.6), ('plugged in 22:00-07:00, 7.4 kW', NIGHT, 7.4), ('plugged in 22:00-07:00, 3.6 kW', NIGHT, 3.6)]

def ev_adjust(REF, mask, pmax):
    """Reference costs with the car re-blocked under a charger-power / plug-in limit instead of priced at the day's cheapest rate."""
    Y = REF.copy()
    for k in KEYS:
        for d in dates:
            r = RT[k][d][0]; a, _ = alloc(carA[d], r, mask, pmax)
            Y.loc[d, k] += (a * r).sum() / 100 - carA[d] * r.min() / 100
    return Y

if __name__ == '__main__':
    t0 = time.time()
    # ---- reference, checked against the cached counterfactual of analysis.py when that exists
    REF = year(D.home, D.sol, carA)
    base = REF.cosy[act == 'cosy'].sum() + REF.iog[act == 'iog'].sum()
    chk = os.path.join(M.ROOT, 'switch_model', 'cache', 'truth_costs_hist.pkl')
    if os.path.exists(chk):
        C = pd.read_pickle(chk); assert np.allclose(C.values, REF.values, atol=1e-9), 'reference differs from model.counterfactual'
        print('reference matches model.counterfactual to 1e-9 on all', len(C), 'days')
    print('reference switch dates', [best_switch(REF.cosy - REF.iog, w, f).idxmax().date() for w, f in WIN], round(time.time() - t0), 's', flush=True)

    P = M.fit_chain(D)
    Dh = pd.Series([M.predict_DS(P, d, D.tmax[d], D.tmin[d], D.sun_h[d])[0] for d in dates], index=dates)
    Sh = pd.Series([M.predict_DS(P, d, D.tmax[d], D.tmin[d], D.sun_h[d])[1] for d in dates], index=dates)
    cm = carA.mean()
    mm = lambda s: s.groupby(s.index.month).transform('mean')
    const = lambda v: pd.Series(v, index=dates)
    netkeep = lambda S: (D.home - D.sol + S).clip(lower=3)          # meter-only tier: keep net = load - solar, change the solar estimate
    ZERO = const(0.0)
    VARIANTS = [   # (variant, group, inputs)
        ('reference (actual load, solar, car; 12 kWh; shape 80/20)', 'reference', dict(Ds=D.home, Ss=D.sol, Cs=carA)),
        # --- A. what if the inputs come from the weather instead of the meter
        ('weather-predicted load and solar, actual car', 'A weather chain', dict(Ds=Dh, Ss=Sh, Cs=carA)),
        ('weather-predicted load and solar, mean car (the weather chain)', 'A weather chain', dict(Ds=Dh, Ss=Sh, Cs=const(cm))),
        ('weather-predicted, load x0.8', 'A weather chain', dict(Ds=Dh * 0.8, Ss=Sh, Cs=const(cm))),
        ('weather-predicted, load x1.2', 'A weather chain', dict(Ds=Dh * 1.2, Ss=Sh, Cs=const(cm))),
        ('weather-predicted, solar x0.8', 'A weather chain', dict(Ds=Dh, Ss=Sh * 0.8, Cs=const(cm))),
        ('weather-predicted, solar x1.2', 'A weather chain', dict(Ds=Dh, Ss=Sh * 1.2, Cs=const(cm))),
        # --- B. what if there is no weather at all, only averages
        ('no weather: monthly-mean load, solar and car', 'B averages only', dict(Ds=mm(D.home), Ss=mm(D.sol), Cs=mm(carA))),
        ('monthly-mean load only (actual solar)', 'B averages only', dict(Ds=mm(D.home), Ss=D.sol, Cs=carA)),
        ('monthly-mean solar only (actual load)', 'B averages only', dict(Ds=D.home, Ss=mm(D.sol), Cs=carA)),
        ('constant annual-mean load (actual solar)', 'B averages only', dict(Ds=const(D.home.mean()), Ss=D.sol, Cs=carA)),
        # --- C. the within-day load shape
        ('load shape fully flat', 'C load shape', dict(Ds=D.home, Ss=D.sol, Cs=carA, flat=1.0)),
        ('load shape 50/50', 'C load shape', dict(Ds=D.home, Ss=D.sol, Cs=carA, flat=0.5)),
        ('load shape fully typical-profile (0/100)', 'C load shape', dict(Ds=D.home, Ss=D.sol, Cs=carA, flat=0.0)),
        # --- D. the battery
        ('battery 0 kWh (no battery)', 'D battery', dict(Ds=D.home, Ss=D.sol, Cs=carA, B=0.0)),
        ('battery 6 kWh', 'D battery', dict(Ds=D.home, Ss=D.sol, Cs=carA, B=6.0)),
        ('battery 8.4 kWh (-30%)', 'D battery', dict(Ds=D.home, Ss=D.sol, Cs=carA, B=8.4)),
        ('battery 15.6 kWh (+30%)', 'D battery', dict(Ds=D.home, Ss=D.sol, Cs=carA, B=15.6)),
        ('battery 20 kWh', 'D battery', dict(Ds=D.home, Ss=D.sol, Cs=carA, B=20.0)),
        ('battery power 2.5 kW', 'D battery', dict(Ds=D.home, Ss=D.sol, Cs=carA, P=2.5)),
        ('battery one-way efficiency 90% (instead of 95%)', 'D battery', dict(Ds=D.home, Ss=D.sol, Cs=carA, eta=0.90)),
        ('battery may charge from the grid in any slot (no window rule)', 'D battery', dict(Ds=D.home, Ss=D.sol, Cs=carA, anywin=True)),
        # --- D2. export price (import-or-export per half hour: with a plain linear programme an export price above the cheap import price lets the
        #         planner import and export in the same half hour, which a meter would net off)
        ('export rate 6 p/kWh (instead of 12)', 'D2 export price', dict(Ds=D.home, Ss=D.sol, Cs=carA, xr=6.0, xor=True)),
        ('export rate 15 p/kWh (instead of 12)', 'D2 export price', dict(Ds=D.home, Ss=D.sol, Cs=carA, xr=15.0, xor=True)),
        # --- D3. exporting energy bought from the grid (mixed-integer planner; section 3.3)
        ('import-or-export per half hour (solar-only export, as the default otherwise)', 'D3 grid export', dict(Ds=D.home, Ss=D.sol, Cs=carA, xor=True)),
        ('battery may export energy bought from the grid (12 p flat export)', 'D3 grid export', dict(Ds=D.home, Ss=D.sol, Cs=carA, xgrid=True)),
        ('battery may export grid-bought energy, export 15 p', 'D3 grid export', dict(Ds=D.home, Ss=D.sol, Cs=carA, xgrid=True, xr=15.0)),
        ('battery may export grid-bought energy, efficiency 90%', 'D3 grid export', dict(Ds=D.home, Ss=D.sol, Cs=carA, xgrid=True, eta=0.90)),
        # --- E. the car and the solar as inputs
        ('no car', 'E car and solar', dict(Ds=D.home, Ss=D.sol, Cs=ZERO)),
        ('mean car (constant)', 'E car and solar', dict(Ds=D.home, Ss=D.sol, Cs=const(cm))),
        ('no solar (panels ignored)', 'E car and solar', dict(Ds=D.home, Ss=ZERO, Cs=carA)),
        ('car left inside home load (not separated)', 'E car and solar', dict(Ds=D.home + carA, Ss=D.sol, Cs=ZERO)),
        ('car left inside home load, 50/50 shape', 'E car and solar', dict(Ds=D.home + carA, Ss=D.sol, Cs=ZERO, flat=0.5)),
        # --- F. meter-only: keep the net (load minus solar) the meter sees, change only how it is split
        ('meter-only: solar x0.8, load adjusted to keep net', 'F meter-only', dict(Ds=netkeep(D.sol * 0.8), Ss=D.sol * 0.8, Cs=carA)),
        ('meter-only: solar x1.2, load adjusted to keep net', 'F meter-only', dict(Ds=netkeep(D.sol * 1.2), Ss=D.sol * 1.2, Cs=carA)),
        ('meter-only: solar from weather model, net kept', 'F meter-only', dict(Ds=netkeep(Sh), Ss=Sh, Cs=carA)),
    ]
    rows = []; groups = {}
    for n, g, kw in VARIANTS:
        Y = year(**kw); rows.append(metrics(Y, REF, n, base)); groups[n] = g
        print(n, round(time.time() - t0), 's', flush=True)
    for nm, mask, pm in [('EV 3.6 kW charger, any slot', ALL, 3.6), ('EV 7.4 kW, plugged in 22:00-07:00 only', NIGHT, 7.4),
                         ('EV 3.6 kW, plugged in 22:00-07:00 only', NIGHT, 3.6)]:      # charger and plug-in limits applied to the reference (section 6)
        Y = ev_adjust(REF, mask, pm); rows.append(metrics(Y, REF, nm, base)); groups[nm] = 'G EV limits'

    # ---- optional: the naive 'reprice what the meter recorded' comparison (needs the user's own Octopus half-hourly files)
    NV = None
    if args.import_csv and args.export_csv:
        def load_hh(f):
            x = pd.read_csv(f); t = pd.to_datetime(x.interval_start, utc=True).dt.tz_convert('Europe/London')
            x['d'] = t.dt.tz_localize(None).dt.normalize(); x['s'] = t.dt.hour * 2 + t.dt.minute // 30
            return x.pivot_table(index='d', columns='s', values='kwh_or_units', aggfunc='sum').reindex(index=dates, columns=range(48)).fillna(0)
        IMP = load_hh(args.import_csv); EXP = load_hh(args.export_csv)
        NV = pd.DataFrame({k: pd.Series({d: (IMP.loc[d].values * RT[k][d][0]).sum() / 100 - EXP.loc[d].sum() * T.EXPORT_RATE / 100 + RT[k][d][1] / 100 for d in dates}) for k in KEYS})
        nrow = metrics(NV, REF, 'NAIVE: reprice the metered half-hourly import (comparison-site method)', base); groups[nrow['variant']] = 'N naive'
        rows.insert(0, nrow)
        own = pd.Series({d: NV.loc[d, act[d]] for d in dates})
        print('\nNAIVE vs PLANNER by tariff of origin (% of base)')
        naive_rows = []
        for t in KEYS:
            m = act == t; o = 'iog' if t == 'cosy' else 'cosy'
            r_ = dict(days_on=t, n_days=int(m.sum()),
                      own_tariff_naive_pct=100 * own[m].sum() / base, own_tariff_planner_pct=100 * REF.loc[m, t].sum() / base,
                      other_tariff_naive_pct=100 * NV.loc[m, o].sum() / base, other_tariff_planner_pct=100 * REF.loc[m, o].sum() / base)
            r_['other_naive_minus_planner_pct'] = r_['other_tariff_naive_pct'] - r_['other_tariff_planner_pct']
            r_['own_planner_vs_naive_pct'] = 100 * (REF.loc[m, t].sum() / own[m].sum() - 1)
            naive_rows.append(r_); print({k: (round(v, 2) if isinstance(v, float) else v) for k, v in r_.items()})
        mon = pd.concat([NV.cosy - NV.iog, REF.cosy - REF.iog], axis=1, keys=['naive_saving_pct', 'planner_saving_pct']).resample('MS').sum() / base * 100
        mon.round(2).rename_axis('month').to_csv(os.path.join(OUT, 'naive_vs_planner_percent.csv'))
        pd.DataFrame(naive_rows).round(2).to_csv(os.path.join(OUT, 'naive_by_tariff_of_origin_percent.csv'), index=False)
        if args.bills:
            b = pd.read_json(args.bills); b['date'] = pd.to_datetime(b.date); b = b.set_index('date')
            billed = (b.cost_in + b.standing - b.inc_out).reindex(dates); ok = billed.notna()
            print('naive own-tariff reprice vs billed: ', round(100 * (own[ok].sum() / billed[ok].sum() - 1), 2), '% over', int(ok.sum()), 'days')
        # shape check: does the planner put the import in the slots where the meter saw it?
        MOD = np.zeros((len(dates), 48))
        for i, d in enumerate(dates):
            res, r, sc = plan(d, D.home[d], D.sol[d], act[d]); a, _ = alloc(carA[d], r, ALL, 7.4); MOD[i] = res['g'] + a
        shape = []
        for t in KEYS:
            m = (act == t).values; a_ = IMP[m].mean().values; b_ = MOD[m].mean(axis=0)
            rr = RT[t][dates[m][0]][0]; ch = rr <= rr.min() + 0.01
            shape.append(dict(tariff=t, slot_profile_corr=np.corrcoef(a_, b_)[0, 1], daily_import_metered=a_.sum(), daily_import_planner=b_.sum(),
                              cheap_share_metered=a_[ch].sum() / a_.sum(), cheap_share_planner=b_[ch].sum() / b_.sum()))
        sa = [IMP.loc[d].values[RT[act[d]][d][0] <= RT[act[d]][d][0].min() + 0.01].sum() / max(IMP.loc[d].sum(), 1e-9) for d in dates]
        sm = [MOD[i][RT[act[d]][d][0] <= RT[act[d]][d][0].min() + 0.01].sum() / max(MOD[i].sum(), 1e-9) for i, d in enumerate(dates)]
        shape.append(dict(tariff='per-day cheap-share correlation', slot_profile_corr=np.corrcoef(sa, sm)[0, 1]))
        pd.DataFrame(shape).round(3).to_csv(os.path.join(OUT, 'planner_shape_check.csv'), index=False); print(pd.DataFrame(shape).round(3).to_string())

    # ---- write the knockout table
    T_ = pd.DataFrame(rows); T_['group'] = T_.variant.map(groups)
    pub = T_.drop(columns=['_pounds']).round({'cosy_pct': 1, 'go_pct': 1, 'saving_pct': 1, 'd_saving_pct': 1, 'day_MAE_pct': 1, 'sign7': 2, 'corr7': 2, 'regret_pct': 1})
    pub = pub[['group', 'variant'] + [c for c in pub.columns if c not in ('group', 'variant')]]
    pub.to_csv(os.path.join(OUT, 'knockout_percent.csv'), index=False)
    pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 70); print(pub.to_string(index=False))

    # ---- EV re-blocking table (section 6)
    base_car = {k: sum(RT[k][d][0].min() * carA[d] / 100 for d in dates) for k in KEYS}
    ev = []
    for name, mask, pm in EV_SCEN:
        row = dict(scenario=name)
        for k in KEYS:
            cost = 0; nsp = 0; dev = 0; spill = 0
            for d in dates:
                r = RT[k][d][0]; a, s = alloc(carA[d], r, mask, pm)
                cost += (a * r).sum() / 100; spill += s; nsp += s > 1e-6; dev += (a * (r > r.min() + 0.01)).sum()
            row[k + '_car_cost_above_cheapest_pct_of_base'] = 100 * (cost - base_car[k]) / base
            row[k + '_days_overflow'] = nsp; row[k + '_kwh_outside_cheap_window'] = dev; row[k + '_kwh_delivered'] = carA.sum()
        row['d_saving_pct'] = row['cosy_car_cost_above_cheapest_pct_of_base'] - row['iog_car_cost_above_cheapest_pct_of_base']
        ev.append(row)
    EV = pd.DataFrame(ev).round(1); EV.to_csv(os.path.join(OUT, 'ev_reblocking_percent.csv'), index=False); print(EV.to_string(index=False))
    print('car kWh per year', round(carA.sum()), 'max per day', round(carA.max(), 1), 'on', carA.idxmax().date(), '| median charging day', round(carA[carA > 1].median(), 1))
    d2 = pd.Timestamp('2026-02-05')
    for k in KEYS:
        r = RT[k][d2][0]; a, s = alloc(carA[d2], r, NIGHT, 7.4)
        print(' example', k, d2.date(), round(carA[d2], 1), 'kWh ->', ['%02d:%02d %.1f' % (j // 2, 30 * (j % 2), a[j]) for j in np.nonzero(a)[0]])
    if args.pounds_out:
        assert 'PRIVATE' in os.path.basename(args.pounds_out), 'name the pounds file *PRIVATE* so .gitignore keeps it out of the repository'
        P_ = pd.DataFrame([{'variant': r['variant'], **{k: round(v, 2) for k, v in r['_pounds'].items()}} for r in rows])
        P_.to_csv(args.pounds_out, index=False)
        print('base (annual cost on tariffs used), pounds:', round(base, 2))
    print('done', round(time.time() - t0), 's')
