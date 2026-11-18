import sys,os,tempfile,uuid
from pathlib import Path
os.environ['RIDE_DB']=os.path.join(tempfile.gettempdir(),'ride-test-'+uuid.uuid4().hex+'.sqlite3')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from datetime import datetime,timedelta,timezone
from fastapi.testclient import TestClient
from server.app import app
client=TestClient(app)

BASE={'pickup_lat':15.5,'pickup_lon':80.05,'dropoff_lat':15.6,'dropoff_lon':80.13}
def plan_input():return {**BASE,'pickup_at':(datetime.now(timezone.utc)+timedelta(days=3)).isoformat(),'vehicle':'bike','provider':'rapido','distance_km':15,'distance_source':'user_supplied'}

def test_health_providers_are_not_faked():
 health=client.get('/api/health').json()
 assert health['provider_quotes']=='not_connected_to_any_platform'
 providers=client.get('/api/providers').json()['providers']
 assert len(providers)==3 and all(p['booking_status']!='connected' for p in providers)

def test_plans_and_activation_without_booking():
 result=client.post('/api/plans',json=plan_input())
 assert result.status_code==201,result.text
 d=result.json(); assert d['fare_estimate'] is None and not d['price_locked'] and not d['booked']
 saved=client.get('/api/plans/'+d['id']).json()
 assert saved['window_active'] is False and saved['booking_active'] is False
 assert client.post('/api/plans/'+d['id']+'/feedback',json={'satisfied':True}).status_code==200

def test_dates_rejected_and_no_ml_fare():
 p=plan_input();p['pickup_at']=(datetime.now(timezone.utc)+timedelta(days=8)).isoformat()
 assert client.post('/api/plans',json=p).status_code==422
 assert client.post('/api/fare/model-estimate',json=plan_input()).status_code==503

def test_route_contract_mock(monkeypatch):
 from server import app as mod
 async def fake_route(req):return {'code':'Ok','routes':[{'distance':23050,'duration':2800}]}
 monkeypatch.setattr(mod,'get_route',fake_route)
 r=client.post('/api/routes/drive',json=BASE)
 assert r.status_code==200 and r.json()['distance_km']==23.05 and not r.json()['traffic_included']

def test_weather_contract_mock(monkeypatch):
 from server import app as mod
 async def fake_weather(lat,lon,days):return {'hourly':{'time':['2026-11-18T09:00'],'temperature_2m':[28],'precipitation':[1],'relative_humidity_2m':[78]}}
 monkeypatch.setattr(mod,'get_weather',fake_weather)
 r=client.get('/api/weather?latitude=15.5&longitude=80&days=7')
 assert r.status_code==200 and r.json()['items'][0]['rain_mm']==1

def test_traffic_guard_and_ui():
 assert client.get('/api/traffic/current?latitude=15.5&longitude=80').status_code==503
 assert client.get('/').status_code==200 and client.get('/assets/app.js').status_code==200
