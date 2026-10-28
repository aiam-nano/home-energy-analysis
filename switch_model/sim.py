"""Half-hourly battery planner: one day, one tariff, solved as a linear programme.

Given the day's household load, solar output and a 48-slot price curve it chooses when to charge and
discharge the battery (and when to export) to minimise cost minus export income, with the battery
allowed to charge from the grid only in the tariff's cheap window.
"""
import numpy as np, pandas as pd, math
from scipy.optimize import linprog, milp, LinearConstraint, Bounds
from scipy.sparse import lil_matrix, csr_matrix

LAT = 53.53
NS = 48

def solar_shape(date, offset_h):
    """48 half-hour weights (local clock) proportional to sin(elevation), zero at night."""
    doy = pd.Timestamp(date).dayofyear
    dec = math.radians(23.44) * math.sin(2 * math.pi * (doy - 81) / 365)
    phi = math.radians(LAT)
    w = np.zeros(NS)
    for i in range(NS):
        t_local = (i + 0.5) / 2.0
        t_utc = t_local - offset_h
        ha = math.radians(15 * (t_utc - 12.16))        # solar noon at about 12:10 UTC for 2.4 W
        s = math.sin(phi) * math.sin(dec) + math.cos(phi) * math.cos(dec) * math.cos(ha)
        w[i] = max(0.0, s) ** 1.2
    return w / w.sum() if w.sum() > 0 else w

def load_shape(flat=0.5):
    """Typical household load profile: a flat share plus a morning and evening peak."""
    hrs = (np.arange(NS) + 0.5) / 2.0
    typ = np.select([hrs < 5, hrs < 7, hrs < 9, hrs < 16, hrs < 18, hrs < 22], [0.6, 1.0, 1.6, 0.9, 1.3, 1.9], 1.0)
    typ = typ / typ.sum()
    return flat / NS + (1 - flat) * typ

def solve_day(L, sol, rate, xrate, B=12.0, P=5.0, Pd=5.0, eta_c=0.95, eta_d=0.95, smin=0.0, window=None, gmax=30.0,
              export_grid=False, xor=False, cycles=None):
    """Minimise grid cost minus export income for one day.
    L, sol, rate: arrays of 48 (kWh per slot, pence per kWh); xrate is a scalar or an array of 48 (pence per kWh exported).
    The battery may charge from the grid only in 'window' slots.
    Default (export_grid=False, xor=False, cycles=None): a linear programme in which export in a half hour is limited to that half hour's
    solar, so the battery never exports energy bought from the grid. This is the version used for every number in the tariff-switch analysis.
    Options (each solves a small mixed-integer programme instead, one binary per half hour, about 0.1-1 s per day):
      xor=True          a half hour is either an import half hour or an export half hour, never both (what a meter registers when the
                        flow is one way within the half hour). Solar-only export as in the default.
      export_grid=True  also lets the battery export (up to Pd) energy that was bought from the grid, so cheap energy can be sold at a
                        high export price. Implies xor. Solar not needed in the house or battery can be curtailed.
      cycles=c          caps the energy drawn out of the battery in the day at c x B (one full cycle a day: cycles=1).
    Returns a dict with cost (pounds), grid import, export, charge, discharge and battery state."""
    n = NS
    if export_grid or xor or cycles is not None:
        return _solve_day_milp(L, sol, rate, xrate, B, P, Pd, eta_c, eta_d, smin, window, gmax, export_grid, cycles)
    ig, ic, id_, ie, is_ = 0, n, 2 * n, 3 * n, 4 * n
    nv = 4 * n + n + 1
    A = lil_matrix((2 * n + 1, nv)); b = np.zeros(2 * n + 1)
    for t in range(n):
        A[t, ig + t] = 1; A[t, id_ + t] = 1; A[t, ic + t] = -1; A[t, ie + t] = -1
        b[t] = L[t] - sol[t]
        A[n + t, is_ + t + 1] = 1; A[n + t, is_ + t] = -1; A[n + t, ic + t] = -eta_c; A[n + t, id_ + t] = 1.0 / eta_d
    A[2 * n, is_ + n] = 1; A[2 * n, is_] = -1
    cost = np.zeros(nv); cost[ig:ig + n] = rate; cost[ie:ie + n] = -xrate
    bounds = []
    win = np.ones(n, bool) if window is None else window
    for t in range(n):
        gub = gmax if win[t] else max(0.0, L[t] - sol[t])
        bounds.append((0, gub))
    bounds += [(0, P * 0.5)] * n + [(0, Pd * 0.5)] * n + [(0, max(0.0, sol[t])) for t in range(n)] + [(smin, B)] * (n + 1)
    r = linprog(cost, A_eq=csr_matrix(A), b_eq=b, bounds=bounds, method="highs")
    if r.status != 0:
        return None
    x = r.x
    g, c, d, e = x[ig:ig + n], x[ic:ic + n], x[id_:id_ + n], x[ie:ie + n]
    return dict(cost=float(r.fun) / 100, imp=float(g.sum()), exp=float(e.sum()), chg=float(c.sum()), dis=float(d.sum()),
                g=g, c=c, d=d, e=e, soc=x[is_:is_ + n + 1])


def _solve_day_milp(L, sol, rate, xrate, B, P, Pd, eta_c, eta_d, smin, window, gmax, export_grid, cycles):
    """Mixed-integer version of solve_day. Variables per slot: g import, c charge, d discharge, e export, w curtailed solar, z (1 = export half hour)."""
    from scipy.sparse import coo_matrix
    n = NS
    ig, ic, id_, ie, iw, iz, is_ = 0, n, 2 * n, 3 * n, 4 * n, 5 * n, 6 * n
    nv = 6 * n + n + 1
    win = np.ones(n, bool) if window is None else window
    net = np.asarray(L) - np.asarray(sol)
    gub = np.where(win, np.minimum(gmax, np.maximum(0.0, net) + P * 0.5), np.maximum(0.0, net))     # tight big-M for the import side
    eub = np.maximum(sol, 0.0) + (Pd * 0.5 if export_grid else 0.0)                                   # and for the export side
    xr = np.broadcast_to(np.asarray(xrate, float), (n,))
    Ae = []; be = []
    for t in range(n):
        Ae.append(({ig + t: 1, id_ + t: 1, iw + t: -1, ic + t: -1, ie + t: -1}, net[t]))
        Ae.append(({is_ + t + 1: 1, is_ + t: -1, ic + t: -eta_c, id_ + t: 1.0 / eta_d}, 0.0))
    Ae.append(({is_ + n: 1, is_: -1}, 0.0))
    Au = []; bu = []
    for t in range(n):
        Au.append(({ig + t: 1, iz + t: gub[t]}, gub[t]))        # g <= gub (1 - z)
        Au.append(({ie + t: 1, iz + t: -eub[t]}, 0.0))          # e <= eub z
    if cycles is not None:
        Au.append(({id_ + t: 1.0 / eta_d for t in range(n)}, cycles * B))
    def mat(rows):
        r_, c_, v_ = [], [], []
        for i, (dct, _) in enumerate(rows):
            for j, v in dct.items(): r_.append(i); c_.append(j); v_.append(v)
        return coo_matrix((v_, (r_, c_)), shape=(len(rows), nv)).tocsr()
    cons = [LinearConstraint(mat(Ae), [b for _, b in Ae], [b for _, b in Ae]), LinearConstraint(mat(Au), -np.inf, [b for _, b in Au])]
    c = np.zeros(nv); c[ig:ig + n] = rate; c[ie:ie + n] = -xr
    lb = np.zeros(nv); ub = np.zeros(nv)
    ub[ig:ig + n] = gub; ub[ic:ic + n] = P * 0.5; ub[id_:id_ + n] = Pd * 0.5; ub[ie:ie + n] = eub
    ub[iw:iw + n] = np.maximum(sol, 0.0); ub[iz:iz + n] = 1; lb[is_:] = smin; ub[is_:] = B
    integ = np.zeros(nv); integ[iz:iz + n] = 1
    r = milp(c, constraints=cons, integrality=integ, bounds=Bounds(lb, ub), options=dict(mip_rel_gap=1e-9))
    if r.x is None:
        return None
    x = r.x
    g, cc, d, e = x[ig:ig + n], x[ic:ic + n], x[id_:id_ + n], x[ie:ie + n]
    return dict(cost=float(r.fun) / 100, imp=float(g.sum()), exp=float(e.sum()), chg=float(cc.sum()), dis=float(d.sum()),
                g=g, c=cc, d=d, e=e, soc=x[is_:is_ + n + 1], curtailed=float(x[iw:iw + n].sum()))
