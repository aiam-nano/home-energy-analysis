import pandas as pd, numpy as np, matplotlib, textwrap
matplotlib.use('Agg')
import matplotlib.pyplot as plt, matplotlib.dates as mdates
from scipy import stats
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.facecolor':'#fcfcfb','figure.facecolor':'#fcfcfb','savefig.facecolor':'#fcfcfb',
 'axes.edgecolor':'#cfcdc7','axes.labelcolor':'#52514e','xtick.color':'#52514e','ytick.color':'#52514e','text.color':'#0b0b0b','axes.spines.top':False,'axes.spines.right':False,
 'grid.color':'#ecebe7','grid.linewidth':0.8,'axes.grid':True,'axes.axisbelow':True,'legend.frameon':False})
INK='#0b0b0b'; MUTE='#52514e'
BLUE='#2a78d6'; ORANGE='#eb6834'; AQUA='#1baf7a'; YEL='#eda100'; MAG='#e87ba4'; VIOL='#6250d6'; RED='#e34948'
C=dict(solar=YEL, imp=BLUE, exp=AQUA, home=VIOL, temp=RED, pw=MAG, car=ORANGE)
SRC='Salford, Greater Manchester · 21 Oct 2025 – 20 Oct 2026 · Tesla Powerwall gateway and Octopus meter data · Weather: Open-Meteo (CC BY 4.0)'
import os
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE)
def load():
    """Read the public daily CSV and add the helper columns the charts use."""
    c=pd.read_csv(os.path.join(ROOT,'data','daily_energy_weather.csv'))
    d=c.rename(columns={'solar_generated_kwh':'gen','solar_to_house_kwh':'to_home','solar_to_powerwall_kwh':'to_battery','solar_exported_kwh':'to_grid',
        'grid_import_kwh':'imported','grid_export_kwh':'exported','home_consumption_kwh':'home_total','car_and_other_kwh':'car_other',
        'temp_max_c':'tmax','temp_min_c':'tmin','sunshine_hours':'sun_h','away_from_home':'away'})
    d['dt']=pd.to_datetime(d.date); d['tmean']=(d.tmax+d.tmin)/2
    # billing months run 21st-20th and are named for the month they end in
    def billing_month(t):
        y,m=t.year,t.month+(1 if t.day>=21 else 0)
        return '%d-%02d'%(y+(m>12),(m-1)%12+1)
    d['period']=d.dt.map(billing_month); d['month']=d.dt.dt.strftime('%Y-%m')
    return d
d=load()
x0,x1=d.dt.min()-pd.Timedelta(days=1), d.dt.max()+pd.Timedelta(days=1)
AW=(pd.Timestamp('2026-07-22'),pd.Timestamp('2026-08-17'))
def roll(s,n=7): return s.rolling(n,center=True,min_periods=n).mean()
def head(fig,title,sub):
    fig.text(0.055,0.965,title,fontsize=17,fontweight='bold',ha='left',va='top')
    fig.text(0.055,0.915,textwrap.fill(sub,92),fontsize=11,color=MUTE,ha='left',va='top',linespacing=1.3)
def foot(fig,extra=''):
    fig.text(0.055,0.018,SRC+extra,fontsize=8,color=MUTE,ha='left',va='bottom')
def months(ax):
    ax.xaxis.set_major_locator(mdates.MonthLocator()); ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))
    ax.set_xlim(x0,x1)
def away(ax,label=True,y=0.97):
    ax.axvspan(*AW,color='#9a9892',alpha=0.16,lw=0)
    if label: ax.text(AW[0]+(AW[1]-AW[0])/2,y,'away',transform=ax.get_xaxis_transform(),ha='center',va='top',fontsize=9,color=MUTE)
def save(fig,name): fig.savefig(os.path.join(ROOT,'charts','post1',name+'.png'),dpi=200); plt.close(fig)
P=d.groupby('period').agg(gen=('gen','sum'),imp=('imported','sum'),exp=('exported','sum'),home=('home_total','sum'),to_home=('to_home','sum'),to_b=('to_battery','sum'),to_g=('to_grid','sum'),co=('car_other','sum'),days=('date','count')).reset_index()
P['lab']=pd.to_datetime(P.period+'-01').dt.strftime('%b')

# 1 daily solar and sunshine
fig,(a1,a2)=plt.subplots(2,1,figsize=(9,6.2),sharex=True,gridspec_kw={'height_ratios':[3,1.5],'hspace':0.12})
fig.subplots_adjust(left=0.08,right=0.97,top=0.82,bottom=0.1)
a1.bar(d.dt,d.gen,width=0.9,color=YEL,alpha=0.75,lw=0); a1.plot(d.dt,roll(d.gen),color=INK,lw=2)
a1.set_ylabel('Solar generated (kWh per day)'); away(a1)
a1.annotate('Best day: 66.8 kWh\n24 May',xy=(pd.Timestamp('2026-05-24'),66.8),xytext=(pd.Timestamp('2026-03-20'),60),fontsize=9,color=MUTE,arrowprops=dict(arrowstyle='-',color=MUTE,lw=0.8),va='center')
a1.text(pd.Timestamp('2025-12-20'),22,'Dec–Jan: over half the\ndays under 5 kWh',fontsize=9,color=MUTE,ha='center')
a2.bar(d.dt,d.sun_h,width=0.9,color='#f3c75a',lw=0); a2.plot(d.dt,roll(d.sun_h),color=INK,lw=2)
a2.set_ylabel('Sunshine (hours)'); away(a2,False); months(a2)
head(fig,'A year of solar: 9,109 kWh, tracking the sunshine','Daily solar generation (top) and daily sunshine hours (bottom). Black lines are 7-day centred averages.')
foot(fig); save(fig,'01_daily_solar_sunshine')

# 2 monthly stacked
fig,ax=plt.subplots(figsize=(9,5.6)); fig.subplots_adjust(left=0.09,right=0.97,top=0.82,bottom=0.13)
xs=np.arange(len(P)); b=np.zeros(len(P))
for k,col,lab in [('to_home',VIOL,'Used in the house'),('to_b',MAG,'Charged the Powerwall'),('to_g',AQUA,'Exported')]:
    ax.bar(xs,P[k],bottom=b,color=col,width=0.7,label=lab,edgecolor='#fcfcfb',linewidth=1.5); b+=P[k].values
ax.set_xticks(xs); ax.set_xticklabels(P.lab); ax.set_ylabel('Solar generated (kWh)'); ax.legend(loc='upper left',ncol=3,fontsize=10)
for i,v in enumerate(b): ax.text(i,v+20,f'{v:,.0f}',ha='center',fontsize=9,color=MUTE)
ax.set_ylim(0,max(b)*1.12)
head(fig,'Where the solar went, month by month','Billing months (21st–20th), named for the month they end in. Only 41% of the year\'s generation stayed on site.')
foot(fig); save(fig,'02_monthly_solar_split')

# 3 import/export monthly diverging
fig,ax=plt.subplots(figsize=(9,5.6)); fig.subplots_adjust(left=0.09,right=0.97,top=0.82,bottom=0.13)
ax.bar(xs,P.imp,color=BLUE,width=0.7,label='Imported from grid',edgecolor='#fcfcfb',linewidth=1.5); ax.bar(xs,-P.exp,color=AQUA,width=0.7,label='Exported to grid',edgecolor='#fcfcfb',linewidth=1.5)
net=P.imp-P.exp; ax.plot(xs,net,color=INK,lw=2,marker='o',ms=6,mec='#fcfcfb',mew=1.5,label='Net (import minus export)')
ax.axhline(0,color='#9a9892',lw=1); ax.set_xticks(xs); ax.set_xticklabels(P.lab); ax.set_ylabel('kWh per month (export downwards)')
ax.legend(loc='upper right',ncol=1,fontsize=10,reverse=True)
ax.set_ylim(-1500,2050)
head(fig,'Five months a net exporter, seven a net importer','Grid import 10,457 kWh, export 6,176 kWh over the year. Import includes Powerwall grid charging; export includes Powerwall discharge.')
foot(fig); save(fig,'03_monthly_import_export')

# 4 scatter solar vs sun by season
fig,ax=plt.subplots(figsize=(9,6)); fig.subplots_adjust(left=0.09,right=0.97,top=0.82,bottom=0.13)
mo=d.dt.dt.month
grp=[('Nov – Feb',mo.isin([11,12,1,2]),BLUE),('Mar, Oct',mo.isin([3,10]),ORANGE),('Apr – Sep',mo.between(4,9),AQUA)]
for lab,m,col in grp:
    s=d[m]; l=stats.linregress(s.sun_h,s.gen)
    ax.scatter(s.sun_h,s.gen,s=26,color=col,alpha=0.75,edgecolor='#fcfcfb',linewidth=0.6,label=f'{lab}: {l.slope:.1f} kWh per sunshine hour (r = {l.rvalue:.2f})')
    xx=np.array([s.sun_h.min(),s.sun_h.max()]); ax.plot(xx,l.intercept+l.slope*xx,color=col,lw=2)
ax.set_xlabel('Sunshine hours in the day'); ax.set_ylabel('Solar generated (kWh)'); ax.legend(loc='upper left',fontsize=10)
head(fig,'Sunshine explains the solar, at a seasonal exchange rate','Each dot is a day. Overall r = 0.89. A sunshine hour is worth about 1.3 kWh in winter and 3 kWh in summer.')
foot(fig); save(fig,'04_solar_vs_sunshine')

# 5 home vs temp
x=d[d.away==0]; T0=12.5; hdd=np.maximum(0,T0-x.tmean); l=stats.linregress(hdd,x.home_total)
fig,ax=plt.subplots(figsize=(9,6)); fig.subplots_adjust(left=0.09,right=0.97,top=0.82,bottom=0.13)
ax.scatter(x.tmean,x.home_total,s=26,color=VIOL,alpha=0.7,edgecolor='#fcfcfb',linewidth=0.6,label='Home consumption, one dot per day')
a=d[d.away==1]; ax.scatter(a.tmean,a.home_total,s=26,color=ORANGE,alpha=0.9,edgecolor='#fcfcfb',linewidth=0.6,label='Away from home (22 Jul – 17 Aug)')
tt=np.linspace(d.tmean.min(),d.tmean.max(),100); ax.plot(tt,l.intercept+l.slope*np.maximum(0,T0-tt),color=INK,lw=2,label=f'Fit: {l.slope:.1f} kWh per degree below {T0:.1f} °C (R² = {l.rvalue**2:.2f})')
ax.set_xlabel('Daily mean outdoor temperature (°C)'); ax.set_ylabel('Home consumption through the gateway (kWh per day)'); ax.legend(loc='upper right',fontsize=10)
head(fig,'Every degree colder adds about 4.3 kWh a day','Whole-house consumption (heat pump included) against outdoor temperature. Away days excluded from the fit.')
foot(fig); save(fig,'05_home_vs_temperature')

# 6 daily home + temperature
fig,(a1,a2)=plt.subplots(2,1,figsize=(9,6.2),sharex=True,gridspec_kw={'height_ratios':[3,1.5],'hspace':0.12})
fig.subplots_adjust(left=0.08,right=0.97,top=0.82,bottom=0.1)
a1.bar(d.dt,d.home_total,width=0.9,color=VIOL,alpha=0.7,lw=0); a1.plot(d.dt,roll(d.home_total),color=INK,lw=2); a1.set_ylabel('Home consumption (kWh per day)'); away(a1)
a1.annotate('Peak: 103 kWh\n5 Jan, −2.1 °C mean',xy=(pd.Timestamp('2026-01-05'),103.2),xytext=(pd.Timestamp('2026-03-01'),96),fontsize=9,color=MUTE,arrowprops=dict(arrowstyle='-',color=MUTE,lw=0.8),va='center')
a2.fill_between(d.dt,d.tmin,d.tmax,color=RED,alpha=0.25,lw=0); a2.plot(d.dt,roll(d.tmean),color=INK,lw=2); a2.set_ylabel('Temperature (°C)'); away(a2,False); months(a2)
head(fig,'Home consumption: a mirror image of the temperature','Top: daily consumption through the Powerwall gateway, 7-day average in black. Bottom: daily min–max temperature band.')
foot(fig); save(fig,'06_daily_home_temperature')

# 7 away zoom
z=d[(d.date>='2026-07-08')&(d.date<='2026-09-08')]
fig,ax=plt.subplots(figsize=(9,5.8)); fig.subplots_adjust(left=0.09,right=0.86,top=0.82,bottom=0.13)
for col,k,lab,cc in [('exported','exp','Grid export',AQUA),('gen','solar','Solar generated',YEL),('imported','imp','Grid import',BLUE),('home_total','home','Home consumption',VIOL)]:
    ax.plot(z.dt,z[col],color=cc,lw=2.2); ax.text(z.dt.iloc[-1]+pd.Timedelta(days=1),{'exported':z[col].iloc[-1]-1,'gen':z[col].iloc[-1]+3,'imported':z[col].iloc[-1]-3,'home_total':z[col].iloc[-1]+2}[col],lab,color=INK,fontsize=9.5,va='center')
ax.axvspan(*AW,color='#9a9892',alpha=0.16,lw=0)
ax.text(AW[0]+(AW[1]-AW[0])/2,0.96,'Away: 22 Jul – 17 Aug\nhouse idling at 9.6 kWh a day',transform=ax.get_xaxis_transform(),ha='center',va='top',fontsize=9.5,color=INK)
ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0,interval=2)); ax.xaxis.set_major_formatter(mdates.DateFormatter('%-d %b')); ax.set_xlim(z.dt.min(),z.dt.max()+pd.Timedelta(days=11))
ax.set_ylabel('kWh per day')
head(fig,'August: a house on standby, exporting all its solar','While away the house drew a flat 9.6 ± 0.3 kWh a day, so nearly all the solar went to the grid.')
foot(fig); save(fig,'07_away_period')

# 8 car & other
fig,ax=plt.subplots(figsize=(9,5.4)); fig.subplots_adjust(left=0.09,right=0.97,top=0.82,bottom=0.13)
ev=pd.read_csv(os.path.join(ROOT,'data','car_reported_monthly_kwh.csv')).rename(columns={'car_reported_kwh':'ev','billing_month':'period'})
P=P.merge(ev,on='period'); w=0.38
ax.bar(xs-w/2,P.ev,width=w,color=ORANGE,label='Reported by the car',edgecolor='#fcfcfb',linewidth=1.5); ax.bar(xs+w/2,P.co,width=w,color=BLUE,label='Seen by the meter, outside the gateway',edgecolor='#fcfcfb',linewidth=1.5)
ax.set_xticks(xs); ax.set_xticklabels(P.lab); ax.set_ylabel('kWh per billing month'); ax.set_ylim(0,300); ax.legend(loc='upper center',ncol=2,fontsize=10)
head(fig,'The car, counted two ways, agrees (r = 0.98)','Car-reported charging against the meter import not seen by the Powerwall gateway. The meter figure is 11% higher: 2,163 vs 1,945 kWh.')
foot(fig); save(fig,'08_car_two_ways')

# 9 daily import/export
fig,ax=plt.subplots(figsize=(9,5.6)); fig.subplots_adjust(left=0.09,right=0.97,top=0.82,bottom=0.1)
ax.bar(d.dt,d.imported,width=0.9,color=BLUE,alpha=0.75,lw=0); ax.bar(d.dt,-d.exported,width=0.9,color=AQUA,alpha=0.75,lw=0)
ax.plot(d.dt,roll(d.imported),color=INK,lw=1.8); ax.plot(d.dt,-roll(d.exported),color=INK,lw=1.8)
ax.axhline(0,color='#9a9892',lw=1); away(ax,True,0.97); months(ax); ax.set_ylabel('kWh per day (export downwards)'); ax.set_ylim(-72,100)
ax.text(pd.Timestamp('2026-01-12'),92,'Import',color=BLUE,fontsize=11,fontweight='bold'); ax.text(pd.Timestamp('2025-12-10'),-30,'Export',color=AQUA,fontsize=11,fontweight='bold')
head(fig,'Winter you import, summer you export','Daily grid import (up) and export (down); black lines are 7-day averages.')
foot(fig); save(fig,'09_daily_import_export')
print('done')
