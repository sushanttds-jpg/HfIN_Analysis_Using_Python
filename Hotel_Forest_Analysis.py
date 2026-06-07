import pandas as pd
import numpy as np
import matplotlib.pyplot as ply
from matplotlib.gridspec import GridSpec

df = pd.read_csv('Stock Trading of Hotel Forest Inn Limited.csv',
                 parse_dates=['BUSINESS DATE'])
df.columns = ['Date','Close','High','Low','Volume','TradedValue','Trades']
df = df.sort_values('Date').reset_index(drop=True)

df['MA7']         = df['Close'].rolling(7).mean()
df['MA14']        = df['Close'].rolling(14).mean()
df['VolMA7']      = df['Volume'].rolling(7).mean()
df['DailyReturn'] = df['Close'].pct_change() * 100
df['CumReturn']   = (df['Close'] / df['Close'].iloc[0] - 1) * 100
returns = df['DailyReturn'].dropna()

events = {
    '2026-03-27': ('Balen Shah\nSworn In', 'green'),
    '2026-04-22': ('Price Peak',            'red'),
}


fig = ply.figure(figsize=(18, 12))
fig.patch.set_facecolor('white')
fig.suptitle("Hotel Forest Inn Ltd (HFIN) — NEPSE Market Analysis\n"
             "Political Transition Event Study | Mar–Jun 2026",
             fontsize=16, fontweight='bold', y=0.98)

gs  = GridSpec(3, 2, figure=fig, hspace=0.4, wspace=0.28)
ax1 = fig.add_subplot(gs[0, :])   # price — needs full width
ax2 = fig.add_subplot(gs[1, 0])
ax3 = fig.add_subplot(gs[1, 1])
ax4 = fig.add_subplot(gs[2, 0])
ax5 = fig.add_subplot(gs[2, 1])

def draw_events(ax):
    """drop political event lines on any time-series chart"""
    for date_str, (label, color) in events.items():
        d = pd.Timestamp(date_str)
        ax.axvline(d, color=color, linewidth=1.5,
                   linestyle='--', alpha=0.7)
        ax.text(d, ax.get_ylim()[1] * 0.95, label,
                fontsize=7.5, color=color,
                rotation=90, va='top', ha='right',
                fontweight='bold')


ax1.plot(df['Date'], df['Close'],
         color='steelblue', linewidth=2, label='Close Price')
ax1.plot(df['Date'], df['MA7'],
         color='red', linewidth=1.5,
         linestyle='--', label='7-Day MA')
ax1.plot(df['Date'], df['MA14'],
         color='darkorange', linewidth=1.5,
         linestyle=':', label='14-Day MA')


peak_idx   = df['Close'].idxmax()
peak_date  = df.loc[peak_idx, 'Date']
peak_price = df.loc[peak_idx, 'Close']
ax1.scatter(peak_date, peak_price, color='red', s=80, zorder=5)
ax1.annotate(f'Peak: NPR {peak_price:.0f}',
             xy=(peak_date, peak_price),
             xytext=(15, 20), textcoords='offset points',
             fontsize=9, color='red', fontweight='bold',
             bbox=dict(facecolor='white', edgecolor='red',
                       alpha=0.8))

ax1.set_title("Closing Price — 11× Pump Followed by Correction",
              fontweight='bold', fontsize=11)
ax1.set_ylabel("Price (NPR)")
ax1.grid(alpha=0.3)
ax1.legend(fontsize=9)
ax1.tick_params(axis='x', rotation=45)
draw_events(ax1)


vol_colors = [
    'steelblue' if d < pd.Timestamp('2026-03-27')
    else 'seagreen' if d <= pd.Timestamp('2026-04-22')
    else 'salmon'
    for d in df['Date']
]
ax2.bar(df['Date'], df['Volume'],
        color=vol_colors, alpha=0.85, width=1)
ax2.plot(df['Date'], df['VolMA7'],
         color='darkorange', linewidth=2, label='7-Day Vol MA')

# annotate the distribution day — this is the key flaw signal
max_vol_idx  = df['Volume'].idxmax()
ax2.annotate(f"{df.loc[max_vol_idx,'Volume']:,.0f} shares\n(distribution?)",
             xy=(df.loc[max_vol_idx,'Date'], df.loc[max_vol_idx,'Volume']),
             xytext=(-50, -40), textcoords='offset points',
             fontsize=7.5, color='red',
             arrowprops=dict(arrowstyle='->', color='red'))

ax2.set_title("Trading Volume by Phase", fontweight='bold')
ax2.set_ylabel("Shares Traded")
ax2.grid(axis='y', alpha=0.3)
ax2.legend(fontsize=8)
ax2.tick_params(axis='x', rotation=45)


ax3.hist(returns, bins=25, color='steelblue',
         edgecolor='black', linewidth=0.4, alpha=0.8)
ax3.axvline(returns.mean(), color='red', linewidth=2,
            linestyle='--',
            label=f'Mean = {returns.mean():.2f}%')
ax3.axvline(0, color='black', linewidth=1,
            linestyle='-', alpha=0.4)

ax3.set_title("Daily Returns Distribution\n"
              f"Volatility = {returns.std():.2f}% / day",
              fontweight='bold')
ax3.set_xlabel("Daily Return (%)")
ax3.set_ylabel("Frequency")
ax3.grid(alpha=0.25)
ax3.legend(fontsize=8)

ax4.fill_between(df['Date'], df['CumReturn'],
                 where=df['CumReturn'] >= 0,
                 color='seagreen', alpha=0.25)
ax4.plot(df['Date'], df['CumReturn'],
         color='seagreen', linewidth=2.5)
ax4.axhline(0, color='black', linestyle='--', linewidth=1)

peak_cum = df['CumReturn'].max()
ax4.annotate(f'+{peak_cum:.0f}%\nfrom start',
             xy=(df.loc[df['CumReturn'].idxmax(), 'Date'], peak_cum),
             xytext=(-60, -30), textcoords='offset points',
             fontsize=8.5, color='seagreen', fontweight='bold',
             arrowprops=dict(arrowstyle='->', color='seagreen'))

ax4.set_title("Cumulative Return from First Trading Day",
              fontweight='bold')
ax4.set_ylabel("Return (%)")
ax4.grid(alpha=0.3)
ax4.tick_params(axis='x', rotation=45)
draw_events(ax4)

ax5.axis('off')

price_now   = df['Close'].iloc[-1]
price_start = df['Close'].iloc[0]

rows = [
    ['Period', f"{df['Date'].iloc[0].strftime('%d %b')} — "
               f"{df['Date'].iloc[-1].strftime('%d %b %Y')}"],
    ['Starting Price',  f"NPR {price_start:.2f}"],
    ['Current Price',   f"NPR {price_now:.2f}"],
    ['Peak Price',      f"NPR {peak_price:.2f}"],
    ['Total Max Return',f"+{df['CumReturn'].max():.1f}%"],
    ['Correction',      f"{((price_now/peak_price)-1)*100:.1f}% from peak"],
    ['Avg Daily Return',f"{returns.mean():.2f}%"],
    ['Daily Volatility',f"{returns.std():.2f}%"],
    ['Peak Volume',     f"{df['Volume'].max():,.0f} shares"],
    ['Avg Volume',      f"{df['Volume'].mean():,.0f} shares"],
    ['Trading Days',    f"{len(df)}"],
]

table = ax5.table(cellText=rows,
                  colLabels=['Metric', 'Value'],
                  cellLoc='left', loc='center',
                  bbox=[0, 0, 1, 1])
table.auto_set_font_size(False)
table.set_fontsize(9.5)

for (row, col), cell in table.get_celld().items():
    cell.set_edgecolor('white')
    if row == 0:
        cell.set_facecolor('blue')
        cell.set_text_props(color='white', fontweight='bold')
    elif row % 2 == 0:
        cell.set_facecolor('white')
    else:
        cell.set_facecolor('white')

ax5.set_title("Summary Statistics", fontweight='bold')

ply.tight_layout(rect=[0, 0, 1, 0.96])
ply.savefig('hfin_event_study.png', dpi=150, bbox_inches='tight')
ply.show()
print("Saved ")