"""Draw charts/methods/knockout_summary_percent.png from data/knockout_percent.csv (percentages only).
Run from the repository root:   python switch_model/plot_knockout.py"""
import os, sys
import pandas as pd, numpy as np
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
K = pd.read_csv(os.path.join(ROOT, 'data', 'knockout_percent.csv'))
K = K[K.group != 'reference'].reset_index(drop=True)
BG, INK, MUT, BL, OR = '#fcfcfb', '#1f2328', '#555b63', '#2a78d6', '#eb6834'
short = {'NAIVE: reprice the metered half-hourly import (comparison-site method)': 'reprice the metered half-hourly import (comparison-site method)',
         'import-or-export per half hour (solar-only export, as the default otherwise)': 'import-or-export per half hour (check; no grid export)',
         'battery may export energy bought from the grid (12 p flat export)': 'battery may sell grid-bought energy, 12 p',
         'battery may export grid-bought energy, export 15 p': 'battery may sell grid-bought energy, 15 p',
         'battery may export grid-bought energy, efficiency 90%': 'battery may sell grid-bought energy, 90% efficiency',
         'battery may charge from the grid in any slot (no window rule)': 'battery may grid-charge in any slot'}
K['lab'] = ['[%s]  %s' % (g.split()[0], short.get(v, v)) for g, v in zip(K.group, K.variant)]
n = len(K); y = np.arange(n)[::-1]
fig, ax = plt.subplots(1, 2, figsize=(12.5, 0.245 * n + 2.6), facecolor=BG, sharey=True, gridspec_kw=dict(width_ratios=[1.5, 1], wspace=0.03))
fig.suptitle("Knockout tests: what moves the answer. Each row changes one thing against the reference run. Letters are the groups in the methods document.",
             x=0.01, ha='left', fontsize=11, color=INK, y=0.998)
a, b = ax
for q in ax: q.set_facecolor(BG); q.grid(axis='x', color='#dcdcda', lw=1); q.set_axisbelow(True)
a.hlines(y, 0, K.d_saving_pct, color=BL, lw=2.4); a.scatter(K.d_saving_pct, y, s=46, color=BL, edgecolor=BG, zorder=3)
b.hlines(y, 0, K.regret_pct, color=OR, lw=2.4); b.scatter(K.regret_pct, y, s=46, color=OR, edgecolor=BG, zorder=3)
a.axvline(0, color='#b8b8b4', lw=1.4)
a.set_xlim(-35, 21); b.set_xlim(-0.2, 14.5)
a.set_title("Change in the year's Cosy-minus-Go gap, points of annual cost\n(reference gap = %.1f%% of annual cost on the tariffs used)" % 21.3, loc='left', fontsize=10, color=INK)
b.set_title("Regret of the variant's switch dates,\n% of annual cost (on the reference savings)", loc='left', fontsize=10, color=INK)
a.set_yticks(y); a.set_yticklabels(K.lab, fontsize=9, color=MUT)
grp = K.group.str.split().str[0].values
for i in range(1, n):
    if grp[i] != grp[i - 1]:
        for q in ax: q.axhline(y[i] + 0.5, color='#dcdcda', lw=1.2)
for q in ax:
    [q.spines[k].set_visible(False) for k in ('top', 'right', 'left')]; q.tick_params(axis='y', length=0); q.tick_params(axis='x', colors=INK, labelsize=10)
a.set_ylim(-0.8, n - 0.2)
fig.subplots_adjust(left=0.36, right=0.985, top=0.925, bottom=0.04)
fig.savefig(os.path.join(ROOT, 'charts', 'methods', 'knockout_summary_percent.png'), dpi=150, facecolor=BG)
