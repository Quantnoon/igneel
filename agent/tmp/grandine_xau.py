import pandas as pd
import numpy as np
p='/workspace/market/XAUUSD_1W_73c50d33.csv'
df=pd.read_csv(p)
req=['time','open_M15','high_M15','low_M15','close_M15']
assert all(c in df.columns for c in req) and len(df)>0
for c in req[1:]: df[c]=pd.to_numeric(df[c],errors='coerce')
df['time']=pd.to_datetime(df['time'],errors='coerce',utc=True)
df=df.dropna(subset=req).sort_values('time')
assert len(df)>=64
assert np.isfinite(df[req[1:]].to_numpy()).all()
assert ((df.low_M15<=df.open_M15)&(df.low_M15<=df.close_M15)&(df.high_M15>=df.open_M15)&(df.high_M15>=df.close_M15)).all()
prev=df.close_M15.shift(1)
tr=pd.concat([df.high_M15-df.low_M15,(df.high_M15-prev).abs(),(df.low_M15-prev).abs()],axis=1).max(axis=1)
atr=tr.ewm(alpha=1/14,adjust=False,min_periods=14).mean()
df['atr']=atr
v=df.dropna(subset=['atr'])
last=v.iloc[-1]; prior=v['atr'].iloc[-51:-1]
A=float(last.atr); med=float(prior.median()); cur=4292.78; entry=4293.06
fav=max(0,cur-entry)/A; adv=max(0,entry-cur)/A
candidate=max(entry,cur-1.5*A)
print('completed',last.time.isoformat())
print('ATR14',A)
print('ATR_pct',A/last.close_M15*100)
print('prior50_median',med)
print('ratio',A/med)
print('favorable_ATR',fav,'adverse_ATR',adv)
print('candidate_stop',round(candidate,2))
print('rows_valid',len(v))
PY
python3 /tmp/grandine_xau.py