"""Aether Crop Intelligence — measured weather + STAC scene discovery + opt-in trained yield model.
No satellite pixel statistic or yield label is fabricated. External data can be unavailable.
"""
from __future__ import annotations
import json,math,os,sqlite3,uuid
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
from statistics import mean
from typing import Literal
import httpx
from fastapi import FastAPI,HTTPException,Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field

ROOT=Path(__file__).resolve().parent.parent
DATA=ROOT/'data';DATA.mkdir(exist_ok=True)
DB=Path(os.getenv('CROP_DB',str(DATA/'crop_local.sqlite3')))
MODEL=DATA/'trained_yield.joblib'
META=DATA/'model_metadata.json'
DB.parent.mkdir(exist_ok=True,parents=True)

def connect():
 c=sqlite3.connect(str(DB));c.row_factory=sqlite3.Row
 c.execute('CREATE TABLE IF NOT EXISTS analyses (id TEXT PRIMARY KEY, created_at TEXT, kind TEXT, coordinates TEXT, result_json TEXT)')
 c.commit();return c

app=FastAPI(title='Crop Intelligence · Weather, STAC and Yield ML',version='1.0')
app.mount('/assets',StaticFiles(directory=ROOT/'web'/'assets'),name='assets')

class FieldRequest(BaseModel):
 crop:Literal['rice','wheat','maize','cotton','groundnut']
 latitude:float=Field(ge=-90,le=90)
 longitude:float=Field(ge=-180,le=180)
 days:int=Field(7,ge=1,le=25)

class SceneRequest(BaseModel):
 latitude:float=Field(ge=-90,le=90)
 longitude:float=Field(ge=-180,le=180)
 radius_km:float=Field(3,ge=0.1,le=10)
 days_back:int=Field(40,ge=1,le=365)
 max_cloud_percent:float=Field(40,ge=0,le=100)

class PixelReflectance(BaseModel):
 red_b04:float=Field(ge=0,le=1)
 nir_b08:float=Field(ge=0,le=1)
 scl_class:int=Field(4,ge=0,le=11)
 source_scene_id:str=Field(min_length=4,max_length=120)

class YieldFeatures(BaseModel):
 crop:Literal['rice','wheat','maize','cotton','groundnut']
 region:str=Field(min_length=2,max_length=80)
 season:str=Field(min_length=2,max_length=30)
 year:int=Field(ge=1990,le=2100)
 average_temp_c:float=Field(ge=-10,le=55)
 rainfall_mm:float=Field(ge=0,le=5000)
 soil_moisture:float=Field(ge=0,le=1)
 ndvi:float=Field(ge=-1,le=1)
 area_hectares:float=Field(gt=0,le=1_000_000)

SOURCE_URLS={
 'weather':'https://open-meteo.com/en/docs',
 'satellite':'https://earth-search.aws.element84.com/v1',
 'sentinel_docs':'https://documentation.dataspace.copernicus.eu/Data/Sentinel2.html',
 'ground_truth':'https://data.desagri.gov.in/website/crops-report-district-level-web',
}

@app.get('/api/health')
def health():return {'status':'ok','database':'SQLite local','weather':'Open-Meteo live on request','satellite':'Element84 Earth Search STAC live on request','satellite_pixel_processing':'reflectance inputs supported; COG raster sampling requires separate processing','yield_prediction':'trained model available' if MODEL.exists() and META.exists() else 'disabled until trained on actual harvest records','sources':SOURCE_URLS}

async def get_weather(latitude,longitude,days):
 params={'latitude':latitude,'longitude':longitude,'forecast_days':min(days,16),'daily':'temperature_2m_max,temperature_2m_min,precipitation_sum,et0_fao_evapotranspiration','hourly':'soil_moisture_0_to_7cm,relative_humidity_2m','timezone':'auto'}
 async with httpx.AsyncClient(timeout=16) as client:
  result=await client.get('https://api.open-meteo.com/v1/forecast',params=params)
  result.raise_for_status();return result.json()

def weather_risks(crop, daily, soil):
 max_temp=[v for v in daily.get('temperature_2m_max',[]) if isinstance(v,(int,float))]
 rain=[v for v in daily.get('precipitation_sum',[]) if isinstance(v,(int,float))]
 e0=[v for v in daily.get('et0_fao_evapotranspiration',[]) if isinstance(v,(int,float))]
 if not max_temp:raise ValueError('No daily temperature values in weather response')
 notes=[]
 if max(max_temp)>38: notes.append({'level':'watch','type':'heat','message':'Forecast includes very hot days. Check crop-stage and cultivar-specific thresholds.'})
 if sum(rain)<3 and len(rain)>=3:notes.append({'level':'watch','type':'rainfall','message':'Little rain predicted. Irrigation decisions require real field measurements.'})
 if sum(rain)>100:notes.append({'level':'watch','type':'waterlogging','message':'Significant forecast rain. Monitor drainage and field conditions.'})
 moist=[v for v in soil if isinstance(v,(int,float))]
 if moist and mean(moist)<0.15:notes.append({'level':'watch','type':'soil','message':'Modeled near-surface soil moisture is low. Validate using a local sensor.'})
 if not notes: notes=[{'level':'info','type':'general','message':'No simple threshold was triggered. This does not establish that crops are healthy.'}]
 return {'mean_max_temp_c':round(mean(max_temp),1),'min_temp_c':min(v for v in daily.get('temperature_2m_min',[]) if isinstance(v,(int,float))), 'total_rain_mm':round(sum(rain),1),'total_et0_mm':round(sum(e0),1),'modeled_mean_topsoil_moisture':round(mean(moist),3) if moist else None,'flags':notes}

@app.post('/api/outlook')
async def outlook(request:FieldRequest):
 try:response=await get_weather(request.latitude,request.longitude,request.days)
 except (httpx.HTTPError,ValueError) as exc:raise HTTPException(503,'Weather API unavailable. No forecast was invented.') from exc
 daily=response.get('daily') or {}
 try:summary=weather_risks(request.crop,daily,(response.get('hourly') or {}).get('soil_moisture_0_to_7cm',[]))
 except (ValueError,ZeroDivisionError) as exc:raise HTTPException(502,'Weather API response was incomplete') from exc
 days_actual=min(request.days,len(daily.get('time',[])))
 result={'crop':request.crop,'latitude':request.latitude,'longitude':request.longitude,'requested_days':request.days,'forecast_days_used':days_actual,'days_without_daily_forecast':max(0,request.days-days_actual),'source':'Open-Meteo live request','source_url':SOURCE_URLS['weather'],'summary':summary,'days':[{'date':day,'max_c':daily.get('temperature_2m_max',[None]*days_actual)[i],'min_c':daily.get('temperature_2m_min',[None]*days_actual)[i],'rain_mm':daily.get('precipitation_sum',[None]*days_actual)[i]} for i,day in enumerate(daily.get('time',[])[:request.days])],'yield_tonnes_per_hectare':None,'crop_health_verified':False,'note':'Weather-derived watch flags are not validated crop yield predictions. Days 17–25 are not daily forecasts when beyond provider horizon.'}
 id_=str(uuid.uuid4())
 with connect() as c:c.execute('INSERT INTO analyses VALUES (?,?,?,?,?)',(id_,datetime.now(timezone.utc).isoformat(),'weather',f'{request.latitude},{request.longitude}',json.dumps(result)));c.commit()
 result['analysis_id']=id_
 return result

async def get_stac(payload:dict):
 async with httpx.AsyncClient(timeout=20) as client:
  result=await client.post('https://earth-search.aws.element84.com/v1/search',json=payload)
  result.raise_for_status();return result.json()

@app.post('/api/satellite/scenes')
async def scenes(req:SceneRequest):
 # Small geographic bbox in degrees; correct at all latitudes not near poles.
 if abs(req.latitude)>85:raise HTTPException(422,'Polar bounding boxes not supported by this simplified locator')
 delta_lat=req.radius_km/111.32
 delta_lon=req.radius_km/(111.32*max(0.09,math.cos(math.radians(req.latitude))))
 bbox=[round(req.longitude-delta_lon,6),round(req.latitude-delta_lat,6),round(req.longitude+delta_lon,6),round(req.latitude+delta_lat,6)]
 start=(datetime.now(timezone.utc)-timedelta(days=req.days_back)).isoformat().replace('+00:00','Z')
 payload={'collections':['sentinel-2-c1-l2a'],'bbox':bbox,'datetime':f'{start}/..','limit':20,'query':{'eo:cloud_cover':{'lte':req.max_cloud_percent}}}
 try:response=await get_stac(payload)
 except (httpx.HTTPError,ValueError) as exc:raise HTTPException(503,'Sentinel-2 STAC catalog unavailable; no imagery was invented') from exc
 result=[]
 for feature in response.get('features',[]):
  assets=feature.get('assets') or {}; properties=feature.get('properties') or {}
  thumbnail=next((assets[k].get('href') for k in ('thumbnail','rendered_preview','visual') if k in assets and assets[k].get('href')),None)
  result.append({'id':feature.get('id'),'timestamp':properties.get('datetime'),'cloud_cover_percent':properties.get('eo:cloud_cover'),'thumbnail_url':thumbnail,'stac_item_url':feature.get('links',[{}])[0].get('href'),'red_b04_available':bool(assets.get('red')),'nir_b08_available':bool(assets.get('nir')),'scl_available':bool(assets.get('scl'))})
 return {'scenes':result,'count':len(result),'bbox':bbox,'collection':'sentinel-2-c1-l2a','catalog':'Element84 Earth Search STAC','note':'These are actual satellite catalog scene METADATA and scene previews. NDVI is not calculated from a preview image. Access to spectral raster pixels requires additional processing.'}

@app.post('/api/ndvi/pixel')
def ndvi(req:PixelReflectance):
 if req.scl_class in [0,1,3,8,9,10,11]:raise HTTPException(422,'Cloud, shadow, snow or invalid scene classification. Pixel excluded.')
 denom=req.red_b04+req.nir_b08
 if denom<=1e-9:raise HTTPException(422,'No valid reflectance signal')
 n=(req.nir_b08-req.red_b04)/denom
 return {'ndvi':round(n,5),'source_scene_id':req.source_scene_id,'red_b04':req.red_b04,'nir_b08':req.nir_b08,'scl_class':req.scl_class,'description':'NDVI computed from supplied Sentinel-2 B04/B08 reflectance pixel values; this is not a regional crop yield or verified vegetation-health estimate.'}

@app.get('/api/yield/model')
def model_status():
 if not META.exists() or not MODEL.exists():return {'ready':False,'message':'No trained harvest-ground-truth model exists. Upload actual labelled yield history and train it offline.','observed_yield':None}
 try:return {'ready':True,'metadata':json.loads(META.read_text())}
 except (ValueError,IOError):raise HTTPException(503,'Model metadata could not be read')

@app.post('/api/yield/predict')
def yield_prediction(req:YieldFeatures):
 if not META.exists() or not MODEL.exists():raise HTTPException(503,'Cannot generate yield estimate: no trained, validated harvest model is installed.')
 import joblib,pandas as pd
 try:
  meta=json.loads(META.read_text());model=joblib.load(MODEL)
  row=pd.DataFrame([req.model_dump()]);prediction=float(model.predict(row)[0]);
 except (OSError,ValueError,KeyError,TypeError) as exc:raise HTTPException(503,'Model artifact incompatible with supplied features') from exc
 return {'predicted_tonnes_per_hectare':max(0,round(prediction,3)),'type':'statistical_model_estimate_not_guaranteed','metrics':meta.get('holdout_metrics'),'trained_data_provenance':meta.get('dataset_source'),'warning':'Do not infer zero error. An accurate estimate needs field-stage metadata, spatial/temporal validation and local ground truth.'}

@app.get('/')
def page():return FileResponse(ROOT/'web'/'index.html')
