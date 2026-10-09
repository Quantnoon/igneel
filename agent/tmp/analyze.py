import pandas as pd
import numpy as np
p='/workspace/market/XAUUSD_1W_37b74bb7.csv'
df=pd.read_csv(p)
req=['time','open_M15','high_M15','low_M15','close_M15']
assert all(c in df.columns for c in req)
df['time']=pd.to_datetime(df['time'],errors='coerce',utc=True)
df=df.sort_values('time').dropna(subset=req).copy()
for c in req[1:]: df[c]=pd.to_numeric(df[c],errors='coerce')
df=df[np.isfinite(df[req[1:]]).all(axis=1)]
assert len(df)>=64
assert ((df.low_M15<=df.open_M15)&(df.low_M15<=df.close_M15)&(df.high_M15>=df.open_M15)&(df.high_M15>=df.close_M15)).all()
# use latest completed candle as latest valid row
prev=df.close_M15.shift(1)
tr=pd.concat([df.high_M15-df.low_M15,(df.high_M15-prev).abs(),(df.low_M15-prev).abs()],axis=1).max(axis=1)
atr=tr.ewm(alpha=1/14,adjust=False,min_periods=14).mean()
df['atr']=atr
v=df.dropna(subset=['atr'])
latest=v.iloc[-1]; prior=v.iloc[-51:-1]
A=float(latest.atr); med=float(prior.atr.median()); close=float(latest.close_M15)
entry=4293.06; current=4290.18
print('completed',latest.time.isoformat())
print('ATR',A,'ATR_pct',A/close*100,'median50',med,'ratio',A/med)
print('adverse_ATR',(entry-current)/A,'favorable_ATR',(current-entry)/A)
print('candidate_buy_trail',current-1.5*A,'breakeven',entry)
