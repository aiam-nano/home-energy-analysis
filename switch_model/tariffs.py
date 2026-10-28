"""Octopus tariffs used in the switching analysis (region G, North West England).

Rates are pence per kWh including VAT and standing charges are pence per day.

Two sets of rates are used:
  * rates_on(tariff, date): the rates actually in force on each day (data/tariff_rates_history.csv, from Octopus's published
    rate history for region G). The main switching analysis uses these, because the Cosy and Go rates changed several times
    during the year and a switch date can only be judged against the prices of that moment.
  * TARIFFS / COSY_FIXED: rates as published on Octopus's public product API on 27 October 2026 (VAT on domestic energy is 0%
    from 1 October 2026, so inc-VAT equals ex-VAT). Used only for the forward-looking fixed-versus-flexible example.
Intelligent Go in the history is the variable product (INTELLI-VAR-24-10-29) before 5 April 2026 and the 12-month fixed
product (INTELLI-FIX-12M-26-03-23, the one actually taken) from 5 April 2026.

Half-hour slot numbers are local clock time: slot 0 is 00:00-00:30, slot 47 is 23:30-00:00.
"""
import os
import numpy as np, pandas as pd

EXPORT_RATE = 12.0     # Outgoing Octopus variable export, p/kWh
BATTERY_KWH = 12.0     # usable battery capacity assumed in the planner
FLAT_LOAD = 0.8        # share of the day's load treated as flat (rest follows the typical profile)
POWER_KW = 5.0         # battery charge and discharge power
EFFICIENCY = 0.95      # one-way battery efficiency

def cosy_rates(cheap=14.0651, std=28.6808, peak=43.0212):
    """Cosy: cheap 04:00-07:00, 13:00-16:00 and 22:00-24:00; peak 16:00-19:00; standard otherwise."""
    r = np.full(48, std); r[8:14] = cheap; r[26:32] = cheap; r[44:48] = cheap; r[32:38] = peak
    return r

def iog_rates(night=7.619, day=32.1441):
    """Intelligent Go: cheap 23:30-05:30, one day rate otherwise."""
    r = np.full(48, day); r[0:11] = night; r[47] = night
    return r

TARIFFS = {
    'cosy':   dict(rate=cosy_rates(), sc=44.8523, label='Cosy Octopus (flexible)'),
    'iog':    dict(rate=iog_rates(), sc=42.7943, label='Intelligent Go (12M fixed)'),
    'iogvar': dict(rate=iog_rates(6.60, 35.8518), sc=44.8523, label='Intelligent Go (variable)'),
}

# Fixed Cosy (product COSY-FIX-12M-26-10-14): rates 10.1% above flexible Cosy, standing charge 6.1% above, 12 months, 50 pound exit fee
COSY_FIXED = dict(cheap=15.4901, std=31.574, peak=47.361, sc=47.5686, exit_fee_pounds=50.0)


_HIST = None
def history():
    """Rate regimes by tariff and date range (public rates, p/kWh inc VAT and p/day)."""
    global _HIST
    if _HIST is None:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'tariff_rates_history.csv')
        h = pd.read_csv(p, parse_dates=['from_date', 'to_date']); _HIST = h
    return _HIST

def rates_on(tariff, date):
    """48 half-hourly rates (p/kWh) and the standing charge (p/day) in force on a date. tariff is 'cosy' or 'iog' (Go)."""
    h = history(); t = 'go' if tariff in ('iog', 'go') else tariff
    d = pd.Timestamp(date).normalize()
    x = h[(h.tariff == t) & (h.from_date <= d) & (h.to_date >= d)]
    if len(x) != 1: raise KeyError('no rates for %s on %s' % (tariff, d.date()))
    x = x.iloc[0]
    if t == 'cosy':
        return cosy_rates(x.low_p_per_kwh, x.mid_p_per_kwh, x.peak_p_per_kwh), float(x.standing_p_per_day)
    return iog_rates(x.low_p_per_kwh, x.mid_p_per_kwh), float(x.standing_p_per_day)
