"""Counterfactual daily cost of each tariff for this house, plus the weather-to-demand/solar chain."""
import os, numpy as np, pandas as pd
from scipy.optimize import least_squares
import sim, tariffs as T

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_inputs():
    """Daily inputs from the public CSV: home load, solar, car and other load outside the gateway, weather."""
    c = pd.read_csv(os.path.join(ROOT, 'data', 'daily_energy_weather.csv'), parse_dates=['date']).set_index('date')
    D = pd.DataFrame({'home': c.home_consumption_kwh, 'sol': c.solar_generated_kwh, 'car': c.car_and_other_kwh,
                      'tmax': c.temp_max_c, 'tmin': c.temp_min_c, 'sun_h': c.sunshine_hours})
    D['tmean'] = (D.tmax + D.tmin) / 2
    return D

def day_cost(date, home, solar, car, key, return_plan=False, hist=True):
    """Cost (pounds) of one day on one tariff: battery plan + car charged in the cheap window + standing charge.
    hist=True uses the rates in force on that date; hist=False uses the rates published on 27 October 2026."""
    if hist: r, sc = T.rates_on(key, date)
    else: t = T.TARIFFS[key]; r, sc = t['rate'], t['sc']
    off = pd.Timestamp(date).tz_localize('Europe/London').replace(hour=12).utcoffset().total_seconds() / 3600
    sh = sim.solar_shape(date, off)
    res = sim.solve_day(home * sim.load_shape(T.FLAT_LOAD), solar * sh, r, T.EXPORT_RATE, B=T.BATTERY_KWH, P=T.POWER_KW,
                        Pd=T.POWER_KW, eta_c=T.EFFICIENCY, eta_d=T.EFFICIENCY, window=(r <= r.min() + 0.01))
    cost = res['cost'] + car * r.min() / 100 + sc / 100
    return (cost, res) if return_plan else cost

def counterfactual(D, keys=('cosy', 'iog'), hist=True):
    """Cost of every day on every tariff, using the day's actual home load, solar and car use, at the rates in force that day
    (hist=True) or at the rates of 27 October 2026 (hist=False)."""
    car = D.car.fillna(D.car.median())
    rows = []
    for d in D.index:
        rows.append({'date': d, **{k: day_cost(d, D.loc[d, 'home'], D.loc[d, 'sol'], car[d], k, hist=hist) for k in keys}})
    return pd.DataFrame(rows).set_index('date')

# ---- weather chain: temperature and sunshine -> predicted home load and solar -> predicted cost
def daylen(doy, lat=53.53):
    dec = np.radians(23.44) * np.sin(2 * np.pi * (doy - 81) / 365); phi = np.radians(lat)
    x = np.clip(-np.tan(phi) * np.tan(dec), -1, 1)
    return 2 * np.degrees(np.arccos(x)) / 15

def S_model(p, doy, frac):
    A, Bc, c0, pw = p
    return (A + Bc * np.cos(2 * np.pi * (doy - 172) / 365)) * (c0 + (1 - c0) * frac ** pw)

def fit_chain(D):
    """Fit solar = clear-sky(day of year) x cloud factor(sunshine fraction) and home = a + b HDD + c HDD x sun + d range."""
    doy = D.index.dayofyear.values.astype(float)
    frac = np.clip(D.sun_h.values / daylen(doy), 0, 1)
    r = least_squares(lambda p: S_model(p, doy, frac) - D.sol.values, [40, 25, 0.15, 1.0], bounds=([5, 0, 0, 0.3], [100, 60, 0.6, 3]))
    pS = r.x
    best = None; y = D.home.values
    for T0 in np.arange(12, 19, 0.5):
        hdd = np.clip(T0 - D.tmean.values, 0, None)
        X = np.column_stack([np.ones(len(y)), hdd, hdd * frac, D.tmax.values - D.tmin.values])
        beta = np.linalg.lstsq(X, y, rcond=None)[0]; e = y - X @ beta
        if best is None or e.var() < best[0]: best = (e.var(), T0, beta, e)
    v, T0, beta, e = best
    resS = D.sol.values - S_model(pS, doy, frac)
    return dict(pS=pS, T0=T0, beta=beta, r2_home=1 - v / y.var(), r2_solar=1 - resS.var() / D.sol.var(), sd_home=e.std(), sd_solar=resS.std())

def predict_DS(P, date, tmax, tmin, sun_h):
    doy = pd.Timestamp(date).dayofyear
    dl = float(daylen(np.array([doy]))[0]); fr = min(1, max(0, sun_h / dl))
    tm = (tmax + tmin) / 2; hdd = max(0, P['T0'] - tm); b = P['beta']
    Dh = max(5.0, b[0] + b[1] * hdd + b[2] * hdd * fr + b[3] * (tmax - tmin))
    Sh = max(0.0, float(S_model(P['pS'], np.array([doy], float), np.array([fr]))[0]))
    return Dh, Sh

def predicted_costs(D, P, keys=('cosy', 'iog'), hist=True):
    car = D.car.mean()
    rows = []
    for d in D.index:
        Dh, Sh = predict_DS(P, d, D.loc[d, 'tmax'], D.loc[d, 'tmin'], D.loc[d, 'sun_h'])
        rows.append({'date': d, **{k: day_cost(d, Dh, Sh, car, k, hist=hist) for k in keys}})
    return pd.DataFrame(rows).set_index('date')
