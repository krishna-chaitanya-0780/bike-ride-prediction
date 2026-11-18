"""Train on REAL historical harvest data. No synthetic model shipped.
Usage: python scripts/train_yield.py --csv /path/to/verified_crop_data.csv --source 'Government crop yield dataset ...'
Columns: crop,region,season,year,average_temp_c,rainfall_mm,soil_moisture,ndvi,area_hectares,yield_tonnes_per_hectare
"""
from __future__ import annotations
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error,mean_squared_error,r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

ROOT=Path(__file__).resolve().parent.parent
CAT=['crop','region','season']
NUM=['year','average_temp_c','rainfall_mm','soil_moisture','ndvi','area_hectares']
TARGET='yield_tonnes_per_hectare'

def train(csv,source):
 if not source.strip() or source.lower().startswith(('demo','synthetic')):raise ValueError('Provide genuine source provenance; synthetic claims are refused')
 df=pd.read_csv(csv)
 for col in CAT+NUM+[TARGET]:
  if col not in df.columns:raise ValueError(f'Required dataset field missing: {col}')
 df=df.dropna(subset=CAT+NUM+[TARGET])
 if len(df)<80 or df.year.nunique()<4:raise ValueError('Need >=80 labeled observations spanning >=4 years. No metric from tiny demo data.')
 if (df[TARGET]<=0).any():raise ValueError('All label yields must be positive tonnes/hectare')
 years=sorted(df.year.unique());test_years=years[-1:];train_df=df[~df.year.isin(test_years)];test_df=df[df.year.isin(test_years)]
 if len(test_df)<10 or len(train_df)<50:raise ValueError('Need a temporally separated holdout with at least 10 rows')
 proc=ColumnTransformer([('categorical',OneHotEncoder(handle_unknown='ignore'),CAT),('numeric','passthrough',NUM)])
 pipe=Pipeline([('preprocess',proc),('rf',RandomForestRegressor(n_estimators=220,min_samples_leaf=3,random_state=42,n_jobs=-1))]);pipe.fit(train_df[CAT+NUM],train_df[TARGET]);pred=pipe.predict(test_df[CAT+NUM])
 mae=float(mean_absolute_error(test_df[TARGET],pred));rmse=float(np.sqrt(mean_squared_error(test_df[TARGET],pred)));r2=float(r2_score(test_df[TARGET],pred))
 meta={'model':'RandomForestRegressor','trained_at':datetime.now(timezone.utc).isoformat(),'dataset_source':source,'train_rows':len(train_df),'holdout_rows':len(test_df),'holdout_years':list(map(int,test_years)),'holdout_metrics':{'MAE_tonnes_per_ha':round(mae,3),'RMSE_tonnes_per_ha':round(rmse,3),'R2':round(r2,3)},'caution':'A time holdout is not geographic transfer validation; real farm yield accuracy unproven.'}
 output=ROOT/'data';output.mkdir(exist_ok=True);joblib.dump(pipe,output/'trained_yield.joblib');(output/'model_metadata.json').write_text(json.dumps(meta,indent=2));print(json.dumps(meta,indent=2))

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--csv',required=True);parser.add_argument('--source',required=True);args=parser.parse_args();train(args.csv,args.source)
