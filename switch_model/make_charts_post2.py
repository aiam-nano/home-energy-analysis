"""Charts for post 2 (percentages only). Run from the repository root after analysis.py: python switch_model/make_charts_post2.py"""
import os, sys, textwrap
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt, matplotlib.dates as mdates
import model as M, tariffs as T
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.facecolor':'#fcfcfb','figure.facecolor':'#fcfcfb','savefig.facecolor':'#fcfcfb',
 'axes.edgecolor':'#cfcdc7','axes.labelcolor':'#52514e','xtick.color':'#52514e','ytick.color':'#52514e','text.color':'#0b0b0b','axes.spines.top':False,'axes.spines.right':False,
 'grid.color':'#ecebe7','grid.linewidth':0.8,'axes.grid':True,'axes.axisbelow':True,'legend.frameon':False})
INK='#0b0b0b'; MUTE='#52514e'; COSY='#6250d6'; IOG='#eb6834'; AQUA='#1baf7a'; RED='#e34948'; GREY='#9a9892'
SRC='Salford, Greater Manchester · 21 Oct 2025 – 20 Oct 2026 · Costs simulated at the Octopus rates in force on each day · Percentages only'
OUTDIR=os.path.join(M.ROOT,'charts','post2'); os.makedirs(OUTDIR,exist_ok=True)
def head(fig,title,sub):
    fig.text(0.055,0.965,title,fontsize=17,fontweight='bold',ha='left',va='top')
    fig.text(0.055,0.915,textwrap.fill(sub,92),fontsize=11,color=MUTE,ha='left',va='top',linespacing=1.3)
def foot(fig,src=None): fig.text(0.055,0.018,src or SRC,fontsize=8,color=MUTE,ha='left',va='bottom')
def save(fig,name): fig.savefig(os.path.join(OUTDIR,name+'.png'),dpi=200); plt.close(fig)

D=M.load_inputs(); P=M.fit_chain(D)
C=pd.read_pickle(os.path.join(M.ROOT,'switch_model','cache','truth_costs_hist.pkl')); F=pd.read_pickle(os.path.join(M.ROOT,'switch_model','cache','chain_costs_hist.pkl'))
S=pd.read_csv(os.path.join(M.ROOT,'data','switch_strategies_percent.csv'))
SE=pd.read_csv(os.path.join(M.ROOT,'data','switch_sensitivity_percent.csv'))
FF=pd.read_csv(os.path.join(M.ROOT,'data','switch_fixed_vs_flexible_percent.csv'))
idx=C.index; ACT=('2025-10-23','2026-04-05'); HB=('2025-11-22','2026-02-10')
m=(idx>=pd.Timestamp(ACT[0]))&(idx<pd.Timestamp(ACT[1])); base=C.cosy[m].sum()+C.iog[~m].sum(); avg_day=base/365
def roll(s): return s.rolling(7,center=True,min_periods=7).mean()

# 10 strategies
fig,ax=plt.subplots(figsize=(9,5)); fig.subplots_adjust(left=0.43,right=0.95,top=0.8,bottom=0.18)
labs=['Cosy all year','Intelligent Go all year','Your dates\n(23 Oct, 5 Apr)','Best dates in\nhindsight\n(22 Nov, 10 Feb)','Best dates from the\nweather model\n(18 Nov, 8 Feb)']
vals=S.difference_pct.values; cols=[COSY,IOG,'#7a8a99',AQUA,AQUA]
y=np.arange(len(vals))[::-1]
ax.barh(y,vals,color=cols,height=0.62)
for yi,v in zip(y,vals): ax.text(v+(0.5 if v>=0 else -0.5),yi,('%+.1f%%'%v) if abs(v)>0.05 else 'baseline',va='center',ha='left' if v>=0 else 'right',fontsize=11,fontweight='bold')
ax.set_yticks(y); ax.set_yticklabels(labs); ax.axvline(0,color=INK,lw=1); ax.set_xlim(-13,24); ax.set_xlabel('Annual cost compared with the dates actually used (%)'); ax.grid(axis='y',visible=False)
head(fig,'Staying on Go beat my switching; the best dates beat both','Simulated annual cost of each strategy, as a percentage above or below the switch dates actually used, at the rates in force on each day. The best dates in hindsight would have saved 7.8%.')
foot(fig); save(fig,'10_strategies')

# 11 seesaw
fig,ax=plt.subplots(figsize=(9,5.4)); fig.subplots_adjust(left=0.09,right=0.97,top=0.82,bottom=0.11)
sav=roll(C.cosy-C.iog)/avg_day*100
ax.fill_between(sav.index,0,sav.where(sav>0),color=IOG,alpha=0.55,lw=0); ax.fill_between(sav.index,0,sav.where(sav<0),color=COSY,alpha=0.55,lw=0); ax.plot(sav.index,sav,color=INK,lw=1.6)
ax.axhline(0,color=INK,lw=0.8); ax.set_ylim(-45,90)
for d,lab,ls,col in [(ACT[0],'You: 23 Oct',':',MUTE),(ACT[1],'You: 5 Apr',':',MUTE),(HB[0],'Best: 22 Nov','-',AQUA),(HB[1],'Best: 10 Feb','-',AQUA)]:
    ax.axvline(pd.Timestamp(d),color=col,lw=1.6,ls=ls)
ax.text(pd.Timestamp(ACT[0])+pd.Timedelta(days=2),ax.get_ylim()[1]*0.95,'23 Oct',ha='left',fontsize=9,color=MUTE)
ax.text(pd.Timestamp(HB[0])+pd.Timedelta(days=2),ax.get_ylim()[1]*0.95,'22 Nov',ha='left',fontsize=9,color=AQUA)
ax.text(pd.Timestamp(HB[1])-pd.Timedelta(days=2),ax.get_ylim()[1]*0.95,'10 Feb',ha='right',fontsize=9,color=AQUA)
ax.text(pd.Timestamp(ACT[1])+pd.Timedelta(days=2),ax.get_ylim()[0]*0.9,'5 Apr',ha='left',fontsize=9,color=MUTE)
ax.text(pd.Timestamp('2025-11-26'),-41,'Cosy cheaper',ha='left',fontsize=11,color=COSY,fontweight='bold')
ax.text(pd.Timestamp('2026-08-20'),82,'Intelligent Go cheaper',ha='center',fontsize=11,color=IOG,fontweight='bold')
ax.xaxis.set_major_locator(mdates.MonthLocator()); ax.xaxis.set_major_formatter(mdates.DateFormatter('%b')); ax.set_xlim(idx.min(),idx.max())
ax.set_ylabel("Cosy minus Intelligent Go, as % of an average day's bill")
head(fig,'The tariffs trade places twice a year','Daily cost difference between Cosy and Intelligent Go (7-day average, as a percentage of an average day\'s bill). Dotted lines: dates used. Solid green: best dates in hindsight.')
foot(fig); save(fig,'11_cosy_vs_iog_seesaw')

# 12 sensitivity
fig,ax=plt.subplots(figsize=(9,5)); fig.subplots_adjust(left=0.1,right=0.96,top=0.82,bottom=0.17)
ax.plot(SE.shift_days,SE.cost_above_best_pct,color=AQUA,lw=2.5,marker='o'); ax.axvline(0,color=INK,lw=0.8)
ax.set_xlabel('Both switch dates moved by this many days (negative = earlier)'); ax.set_ylabel('Annual cost above the best dates (%)'); ax.set_ylim(0,7)
for k,xt in ((-14,-12),(14,13)): v=float(SE.loc[SE.shift_days==k,'cost_above_best_pct'].iloc[0]); ax.annotate('%d days: %.1f%% dearer'%(k,v) if k<0 else '+%d days: %.1f%% dearer'%(k,v),xy=(k,v),xytext=(xt,3.2),ha='center',fontsize=9.5,color=MUTE,arrowprops=dict(arrowstyle='-',color=MUTE,lw=0.8))
ax.set_xticks(range(-42,43,14))
head(fig,'A week off costs under 1%; a month off, 3 to 4%','How much dearer the year gets if both switch dates are moved together away from the hindsight-best dates (22 Nov and 10 Feb).')
foot(fig); save(fig,'12_switch_date_sensitivity')

# 13, 16-18 battery plan on one day on each tariff
def plan_chart(day, fname, title, sub):
    day=pd.Timestamp(day); car=D.car.fillna(D.car.median())[day]
    fig,axes=plt.subplots(2,2,figsize=(10,6.6),sharex=True,gridspec_kw={'height_ratios':[1,1.5],'hspace':0.1,'wspace':0.22}); fig.subplots_adjust(left=0.08,right=0.93,top=0.82,bottom=0.12)
    t=np.arange(48)/2
    for j,(key,colr,name) in enumerate([('cosy',COSY,'Cosy'),('iog',IOG,'Intelligent Go')]):
        cost,res=M.day_cost(day,D.loc[day,'home'],D.loc[day,'sol'],car,key,return_plan=True); r=T.rates_on(key,day)[0]
        a,b=axes[0,j],axes[1,j]
        a.step(np.append(t,24),np.append(r,r[-1]),where='post',color=colr,lw=2); a.set_title('%s: %d%% of an average day\'s bill'%(name,round(cost/avg_day*100)),fontsize=12,fontweight='bold',color=colr,loc='left'); a.set_ylabel('Price (p/kWh)' if j==0 else ''); a.set_ylim(0,50)
        b.bar(t+0.25,res['g'],width=0.45,color='#7a8a99',label='Grid import (kWh per half hour)'); b.set_ylabel('kWh per half hour' if j==0 else ''); b.set_ylim(0,3.7)
        b2=b.twinx(); b2.plot(t[0:1].tolist()+list(t+0.5),res['soc'],color=AQUA,lw=2.4,label='Battery charge (kWh)'); b2.set_ylim(0,13.5); b2.grid(False); b2.spines['right'].set_visible(j==1); b2.spines['top'].set_visible(False)
        b2.set_ylabel('Battery charge (kWh)' if j==1 else '',color=AQUA)
        b.set_xlim(0,24); b.set_xticks(range(0,25,4)); b.set_xlabel('Hour of day')
    axes[1,0].legend(loc='upper center',fontsize=8.5,handles=[plt.Rectangle((0,0),1,1,color='#7a8a99'),plt.Line2D([0],[0],color=AQUA,lw=2.4)],labels=['Grid import','Battery charge'])
    head(fig,title,sub)
    foot(fig); save(fig,fname)
plan_chart('2026-01-15','13_battery_plan_winter_day','How the battery plans a cold January day','15 January 2026 on each tariff. The planner fills the battery in cheap slots, covers the expensive hours from it, and the cheap windows are where the two tariffs differ most.')
plan_chart('2025-11-20','16_battery_plan_autumn_balanced','A balanced day in the autumn: 20 November','A cold day with no car charging, two days before the best autumn switch date. The two tariffs cost almost the same.')
plan_chart('2026-02-08','17_battery_plan_spring_balanced','A balanced day in late winter: 8 February','A milder day with no car charging, two days before the best spring switch date. Cosy is a few per cent cheaper.')
plan_chart('2026-02-05','18_battery_plan_balanced_with_car','A balanced day with the car charging: 5 February','Five days before the best spring switch date, with about 12 kWh going into the car at each tariff\'s cheapest rate.')

# 14 weather chain
fig,ax=plt.subplots(figsize=(9,5.2)); fig.subplots_adjust(left=0.09,right=0.97,top=0.82,bottom=0.11)
tr=roll(C.cosy-C.iog)/avg_day*100; mo=roll(F.cosy-F.iog)/avg_day*100
ax.plot(tr.index,tr,color=INK,lw=2,label='Using the actual home load and solar'); ax.plot(mo.index,mo,color=AQUA,lw=2,ls='--',label='Predicted from temperature and sunshine only')
ax.axhline(0,color=INK,lw=0.8); ax.legend(loc='lower right',fontsize=9.5); ax.xaxis.set_major_locator(mdates.MonthLocator()); ax.xaxis.set_major_formatter(mdates.DateFormatter('%b')); ax.set_xlim(idx.min(),idx.max())
ax.set_ylabel("Cosy minus Intelligent Go, as % of an average day's bill")
_wc=pd.concat([tr,mo],axis=1).dropna().corr().iloc[0,1]
head(fig,'Weather alone predicts which tariff wins (r = %.2f)'%_wc,'7-day average cost difference between the tariffs, from the actual daily load and solar (black) and predicted from temperature and sunshine alone (green dashed).')
foot(fig); save(fig,'14_weather_chain_accuracy')

# 15 fixed vs flexible
fig,ax=plt.subplots(figsize=(9,5.4)); fig.subplots_adjust(left=0.09,right=0.97,top=0.82,bottom=0.13)
for ex,col in (('exit 1 Mar',COSY),('exit 5 Apr',IOG)):
    g=FF[FF.exit==ex]; ax.plot(g.flexible_rise_pct,g.fixed_dearer_pct_with_fee,color=col,lw=2.5,label=ex.replace('exit','Leave').replace('Mar','March').replace('Apr','April')+', with £50 exit fee'); ax.plot(g.flexible_rise_pct,g.fixed_dearer_pct_no_fee,color=col,lw=1.6,ls=':',label=ex.replace('exit','Leave').replace('Mar','March').replace('Apr','April')+', if there were no fee')
ax.axhline(0,color=INK,lw=1); ax.fill_between([0,35],-6,0,color=AQUA,alpha=0.1,lw=0); ax.text(1,-4.6,'Fixed would be cheaper',color=AQUA,fontsize=10,fontweight='bold')
ax.axvline(15,color=MUTE,lw=1.2,ls='--'); ax.text(14.6,14.6,'Cornwall Insight forecast:\nabout +15-16%',fontsize=9,color=MUTE,va='top',ha='right')
ax.axvline(25,color=MUTE,lw=1.2,ls='--'); ax.text(24.6,14.6,'Higher supplier forecasts\n(+20-26% on the bill)',fontsize=9,color=MUTE,va='top',ha='right')
ax.set_xlim(0,35); ax.set_ylim(-6,15); ax.set_xlabel('Rise in flexible Cosy rates on 21 January (%)'); ax.set_ylabel('Fixed Cosy dearer than flexible (%)'); ax.legend(loc='upper right',fontsize=8.5,bbox_to_anchor=(1.0,0.78))
head(fig,'Why staying flexible beats fixing, even with a January rise','Cost of Octopus fixed Cosy against flexible Cosy from 28 October until leaving in spring, for different January rises in flexible rates. Winter 2025-26 stands in for the coming one.')
foot(fig,'Salford, Greater Manchester · Last winter\'s data at Octopus rates of 27 Oct 2026 · Percentages only'); save(fig,'15_fixed_vs_flexible_cosy')
print('charts written to',OUTDIR)
