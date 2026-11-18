"""Independent mobility fare forecasting, not Uber/Ola/Rapido brokerage.
Paid fare estimates and bookings REQUIRE explicit provider approval.
"""
from __future__ import annotations
import json,os,sqlite3,uuid,math
from datetime import datetime,timedelta,timezone
from pathlib import Path
from typing import Literal
import httpx
from fastapi import FastAPI,HTTPException,Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field
ROOT=Path(__file__).resolve().parent.parent
DB=Path(os.getenv('RIDE_DB',str(ROOT/'data'/'ride_local.sqlite3')))
MODEL=ROOT/'data'/'fare_model.joblib'
METRICS=ROOT/'data'/'fare_model_report.json'
DB.parent.mkdir(parents=True,exist_ok=True)

def connection():
 c=sqlite3.connect(str(DB));c.row_factory=sqlite3.Row
 c.execute('CREATE TABLE IF NOT EXISTS plans(id TEXT PRIMARY KEY, created_at TEXT NOT NULL, pickup_at TEXT NOT NULL, activation_at TEXT NOT NULL, pickup_lat REAL, pickup_lon REAL, dropoff_lat REAL, dropoff_lon REAL, distance_km REAL, vehicle TEXT, provider TEXT, model_low REAL, model_high REAL, status TEXT, accepted INTEGER DEFAULT NULL)')
 c.commit();return c

app=FastAPI(title='Wayfare — route / weather / independently trained fare outlook',version='1.0')
app.mount('/assets',StaticFiles(directory=ROOT/'web'/'assets'),name='assets')

class RouteRequest(BaseModel):
 pickup_lat:float=Field(ge=-90,le=90)
 pickup_lon:float=Field(ge=-180,le=180)
 dropoff_lat:float=Field(ge=-90,le=90)
 dropoff_lon:float=Field(ge=-180,le=180)

class PlanRequest(RouteRequest):
 pickup_at:datetime
 vehicle:Literal['bike','auto','car']
 provider:Literal['independent','uber','ola','rapido']='independent'
 distance_km:float=Field(gt=0,le=1200)
 distance_source:Literal['routed_osrm','user_supplied']

class AcceptRequest(BaseModel):
 satisfied:bool

def utc_now():return datetime.now(timezone.utc)
def aware(dt:datetime):return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
def validate_time(dt:datetime):
 lead=(aware(dt)-utc_now()).total_seconds()
 if lead<=0 or lead>7*86400:raise HTTPException(422,'Future pickup time must be within next seven days')

@app.get('/api/health')
def health():return {'status':'ok','fare_ml_ready':MODEL.exists() and METRICS.exists(),'provider_quotes':'not_connected_to_any_platform','provider_bookings':'not_connected','guaranteed_prices':False,'weather':'Open-Meteo on request','route':'OSRM public demo for development only','traffic':'TomTom API optional and restricted to real-time observation'}

async def get_route(data:RouteRequest):
 coords=f'{data.pickup_lon},{data.pickup_lat};{data.dropoff_lon},{data.dropoff_lat}'
 async with httpx.AsyncClient(timeout=14) as c:
  response=await c.get(f'https://router.project-osrm.org/route/v1/driving/{coords}',params={'overview':'false','steps':'false'})
  response.raise_for_status();return response.json()

@app.post('/api/routes/drive')
async def route(data:RouteRequest):
 if abs(data.pickup_lat-data.dropoff_lat)+abs(data.pickup_lon-data.dropoff_lon)<1e-8:raise HTTPException(422,'Pickup and destination must differ')
 try:d=await get_route(data)
 except (httpx.HTTPError,ValueError) as exc:raise HTTPException(503,'OSRM route unavailable; no road distance was fabricated.') from exc
 routes=d.get('routes') or []
 if not routes:raise HTTPException(404,'No usable driving route found')
 result=routes[0]
 return {'distance_km':round(result['distance']/1000,2),'duration_minutes':round(result['duration']/60,1),'route_source':'OSRM public demo; development/testing only, no live traffic','traffic_included':False,'provider_fare':None}

async def get_weather(lat,lon,days):
 async with httpx.AsyncClient(timeout=12) as c:
  r=await c.get('https://api.open-meteo.com/v1/forecast',params={'latitude':lat,'longitude':lon,'hourly':'temperature_2m,precipitation,relative_humidity_2m','forecast_days':max(1,min(7,days)),'timezone':'GMT'})
  r.raise_for_status();return r.json()

@app.get('/api/weather')
async def weather(latitude:float=Query(ge=-90,le=90),longitude:float=Query(ge=-180,le=180),days:int=Query(7,ge=1,le=7)):
 try:d=await get_weather(latitude,longitude,days)
 except (httpx.HTTPError,ValueError) as exc:raise HTTPException(503,'Weather provider unavailable; no fake forecast.') from exc
 hourly=d.get('hourly') or {}
 rows=[]
 for i,t in enumerate(hourly.get('time',[])):
  rows.append({'time':t+'Z' if not t.endswith('Z') else t,'temp_c':(hourly.get('temperature_2m') or [None]*len(hourly['time']))[i],'rain_mm':(hourly.get('precipitation') or [None]*len(hourly['time']))[i]})
 return {'source':'Open-Meteo live hourly forecast','items':rows,'days':days,'provider_fare':None,'forecast_limit':'7-day planner only'}

@app.get('/api/providers')
def providers():
 return {'providers':[{'name':'Uber','fare_quote_status':'approval_required','booking_status':'approval_required','docs':'https://developer.uber.com/docs/riders/references/api/v1.2/estimates-price-get'},
 {'name':'Ola','fare_quote_status':'partner_only','booking_status':'partner_only','docs':'https://developers.olacabs.com/docs/ride-estimate'},
 {'name':'Rapido','fare_quote_status':'no_verified_public_api','booking_status':'no_verified_public_api','docs':None}],
 'notice':'No third-party real-time fares, provider-based price locks or bookings are available through this release.'}

def features(plan:PlanRequest,rain_mm,temp_c,traffic_ratio=1.0):
 local=aware(plan.pickup_at).astimezone(timezone(timedelta(hours=5,minutes=30)))
 return {'vehicle':plan.vehicle,'provider':plan.provider,'distance_km':plan.distance_km,'pickup_hour':local.hour,'day_of_week':local.weekday(),'rain_mm':rain_mm,'temp_c':temp_c,'traffic_ratio':traffic_ratio}

def model_predict(features_data):
 if not MODEL.exists() or not METRICS.exists():return None
 import pandas as pd,joblib
 try:
  model=joblib.load(MODEL);meta=json.loads(METRICS.read_text());val=float(model.predict(pd.DataFrame([features_data]))[0]);mae=float(meta['holdout_metrics']['MAE_INR']);return {'central_inr':round(max(0,val),2),'range_inr':[round(max(0,val-1.5*mae),2),round(max(0,val+1.5*mae),2)],'kind':'statistical_interval_heuristic_not_provider_guarantee','holdout_metrics':meta['holdout_metrics'],'limitations':'±1.5 MAE is illustrative, not a calibrated confidence interval.'}
 except (KeyError,ValueError,TypeError,OSError):return None

@app.get('/api/fare-model')
def model_status():
 if not MODEL.exists() or not METRICS.exists():return {'ready':False,'message':'No licensed or user-supplied historical fare labels. Fare figures will remain unavailable.'}
 try:return {'ready':True,'report':json.loads(METRICS.read_text())}
 except ValueError:raise HTTPException(503,'Invalid model report')

@app.post('/api/fare/model-estimate')
async def fare_model_estimate(req:PlanRequest):
    validate_time(req.pickup_at)
    if not MODEL.exists() or not METRICS.exists():raise HTTPException(503,'No trained historical-fare model. This release refuses to fabricate a seven-day price.')
    pickup=aware(req.pickup_at)
    days=max(1,min(7,math.ceil((pickup-utc_now()).total_seconds()/86400)+1))
    try:weather_response=await get_weather(req.pickup_lat,req.pickup_lon,days)
    except (httpx.HTTPError,ValueError) as exc:raise HTTPException(503,'Cannot get actual provider weather for planned pickup') from exc
    hours=(weather_response.get('hourly') or {})
    times=hours.get('time') or []
    if not times:raise HTTPException(503,'Weather response is missing forecast timestamps')
    def parse_hour(t):return datetime.fromisoformat(t+'+00:00' if t[-1]!='Z' and '+' not in t else t.replace('Z','+00:00'))
    closest=min(range(len(times)),key=lambda i:abs((parse_hour(times[i])-pickup).total_seconds()))
    if abs((parse_hour(times[closest])-pickup).total_seconds())>4000:raise HTTPException(503,'No near-pickup hourly forecast was found')
    precip=(hours.get('precipitation') or [None]*len(times))[closest]
    temp=(hours.get('temperature_2m') or [None]*len(times))[closest]
    if precip is None or temp is None:raise HTTPException(503,'Missing hourly weather inputs')
    inputs=features(req,precip,temp,1.0)
    prediction=model_predict(inputs)
    if prediction is None:raise HTTPException(503,'Fare model failed to evaluate supplied feature vector')
    return {'predicted':prediction,'weather_source':'Open-Meteo live forecast','matched_hour':times[closest],
            'traffic_source':'NEUTRAL_ASSUMPTION_NOT_MEASURED','traffic_ratio_assumed':1.0,
            'fare_provider_quote':None,'price_locked':False,'can_book':False,
            'warning':'This is an independent ML estimate, not the real price from Ola/Uber/Rapido. Day-ahead traffic uncertainty is not solved.'}

@app.post('/api/plans',status_code=201)
def plan(req:PlanRequest):
 validate_time(req.pickup_at)
 # Future weather is not inserted as fabricated ML input. The model cannot run until
 # both trained labels and a real matched weather observation are available.
 id_=str(uuid.uuid4());pickup=aware(req.pickup_at);activation=pickup-timedelta(minutes=10)
 with connection() as c:
  c.execute('INSERT INTO plans(id,created_at,pickup_at,activation_at,pickup_lat,pickup_lon,dropoff_lat,dropoff_lon,distance_km,vehicle,provider,model_low,model_high,status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(id_,utc_now().isoformat(),pickup.isoformat(),activation.isoformat(),req.pickup_lat,req.pickup_lon,req.dropoff_lat,req.dropoff_lon,req.distance_km,req.vehicle,req.provider,None,None,'PLANNED_NOT_BOOKED'))
  c.commit()
 return {'id':id_,'vehicle':req.vehicle,'provider':req.provider,'pickup_at':pickup.isoformat(),'activation_at':activation.isoformat(),'distance_km':req.distance_km,'distance_source':req.distance_source,'fare_estimate':None,'fare_reason':'No price is guaranteed; a separate trained model with real weather may estimate cost when historical data is available.','price_locked':False,'booked':False,'status':'PLANNED_NOT_BOOKED'}

@app.get('/api/plans/{plan_id}')
def get_plan(plan_id:str):
 with connection() as c:row=c.execute('SELECT * FROM plans WHERE id=?',(plan_id,)).fetchone()
 if not row:raise HTTPException(404,'Plan not found')
 data=dict(row)
 active=utc_now()>=datetime.fromisoformat(data['activation_at'])
 return {'plan':data,'window_active':active,'booking_active':False,'price_locked':False,'booking_status':'not_connected','note':'Window activation enables a reminder/quote refresh UI only; no ride can be reserved without authorized provider booking APIs.'}

@app.post('/api/plans/{plan_id}/feedback')
def feedback(plan_id:str,payload:AcceptRequest):
 with connection() as c:
  current=c.execute('SELECT id FROM plans WHERE id=?',(plan_id,)).fetchone()
  if not current:raise HTTPException(404,'Unknown plan')
  c.execute('UPDATE plans SET accepted=? WHERE id=?',(int(payload.satisfied),plan_id));c.commit()
 return {'recorded':True,'no_booking_occurred':True}

@app.get('/api/traffic/current')
async def traffic_current(latitude:float=Query(ge=-90,le=90),longitude:float=Query(ge=-180,le=180)):
 token=os.getenv('TOMTOM_API_KEY')
 if not token:raise HTTPException(503,'Live TomTom traffic requires licensed API credentials; future traffic cannot be inferred from current speed')
 try:
  async with httpx.AsyncClient(timeout=12) as c:
   r=await c.get('https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json',params={'key':token,'point':f'{latitude},{longitude}'})
   r.raise_for_status();data=r.json()['flowSegmentData']
 except (httpx.HTTPError,ValueError,KeyError) as exc:raise HTTPException(503,'Traffic provider unavailable') from exc
 return {'current_speed_kmph':data.get('currentSpeed'),'free_flow_speed_kmph':data.get('freeFlowSpeed'),'source':'TomTom present-time traffic','future_prediction':False,'guaranteed_future_fare':False}

@app.get('/')
def home():return FileResponse(ROOT/'web'/'index.html')
