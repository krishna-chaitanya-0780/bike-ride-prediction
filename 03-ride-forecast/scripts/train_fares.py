"""Train only on legitimately obtained historical fare observations with actual settled prices.
Required columns: provider,vehicle,distance_km,pickup_hour,day_of_week,rain_mm,temp_c,traffic_ratio,pickup_timestamp,actual_fare_inr.
"""
import argparse,json
from pathlib import Path
from datetime import datetime,timezone
import numpy as np,pandas as pd,joblib
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error,mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
ROOT=Path(__file__).resolve().parent.parent
COLS=['provider','vehicle','distance_km','pickup_hour','day_of_week','rain_mm','temp_c','traffic_ratio']

def train(path,provenance):
 if not provenance or 'synthetic' in provenance.lower():raise ValueError('Provide actual lawful data provenance, not synthetic claims')
 data=pd.read_csv(path)
 for col in COLS+['pickup_timestamp','actual_fare_inr']:
  if col not in data.columns:raise ValueError('Missing '+col)
 data=data.dropna(subset=COLS+['pickup_timestamp','actual_fare_inr'])
 data['pickup_timestamp']=pd.to_datetime(data.pickup_timestamp,utc=True)
 if len(data)<150 or data.pickup_timestamp.dt.date.nunique()<21:raise ValueError('Need >=150 real price observations spanning >=21 distinct dates')
 data=data.sort_values('pickup_timestamp');cut=int(len(data)*.8);tr,te=data.iloc[:cut],data.iloc[cut:]
 if tr.pickup_timestamp.max()>=te.pickup_timestamp.min():raise ValueError('Time leakage between train and holdout')
 proc=ColumnTransformer([('category',OneHotEncoder(handle_unknown='ignore'),['provider','vehicle']),('number','passthrough',[c for c in COLS if c not in ['provider','vehicle']])]);model=Pipeline([('prep',proc),('rf',RandomForestRegressor(n_estimators=200,min_samples_leaf=3,random_state=17,n_jobs=-1))]);model.fit(tr[COLS],tr.actual_fare_inr);pred=model.predict(te[COLS]);mae=float(mean_absolute_error(te.actual_fare_inr,pred));rmse=float(np.sqrt(mean_squared_error(te.actual_fare_inr,pred)))
 report={'trained_at':datetime.now(timezone.utc).isoformat(),'data_source':provenance,'train_count':len(tr),'holdout_count':len(te),'holdout_metrics':{'MAE_INR':round(mae,2),'RMSE_INR':round(rmse,2)},'caveat':'No guarantee for future seven-day prices, trips, providers or route conditions.'}
 folder=ROOT/'data';folder.mkdir(exist_ok=True);joblib.dump(model,folder/'fare_model.joblib');(folder/'fare_model_report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--csv',required=True);p.add_argument('--source',required=True);x=p.parse_args();train(x.csv,x.source)
