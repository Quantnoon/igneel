import pandas as pd, numpy as np
p='/workspace/market/Volatility_10_Index_1W_8d20df43.csv'
df=pd.read_csv(p); df['time']=pd.to_datetime(df['time']); df=df.sort_values('time')
for tf in ['M15','M5']:
 c=[f'{x}_{tf}' for x in ['open','high','low','close']]
 x=df[['time']+c].dropna().copy(); x[c]=x[c].apply(pd.to_numeric)
 ok=np.isfinite(x[c]).all().all() and ((x[f'low_{tf}']<=x[[f'open_{tf}',f'close_{tf}']]).all(axis=1)&(x[[f'open_{tf}',f'close_{tf}']]<=x[f'high_{tf}']).all(axis=1)).all()
 close=x[f'close_{tf}'];
 def ema(n): return close.ewm(span=n,adjust=False).mean()
 def rsi(n=14):
  d=close.diff(); up=d.clip(lower=0); dn=-d.clip(upper=0); return 100-100/(1+up.ewm(alpha=1/n,adjust=False).mean()/dn.ewm(alpha=1/n,adjust=False).mean())
 atr=(pd.concat([x[f'high_{tf}']-x[f'low_{tf}'],(x[f'high_{tf}']-close.shift()).abs(),(x[f'low_{tf}']-close.shift()).abs()],axis=1).max(axis=1).ewm(span=14,adjust=False).mean())
 print(tf,len(x),ok, x['time'].iloc[-1],close.iloc[-1], 'ema21',ema(21).iloc[-1], 'ema50',ema(50).iloc[-1], 'ema200',ema(200).iloc[-1], 'rsi',rsi().iloc[-1], 'atr',atr.iloc[-1], 'last10',close.tail(10).tolist())
