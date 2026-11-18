import os,sys,tempfile,uuid
os.environ['CROP_DB']=os.path.join(tempfile.gettempdir(),'crop-ci-'+uuid.uuid4().hex+'.sqlite3')
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from server.app import app,weather_risks,get_weather,get_stac
client=TestClient(app)

def test_status_and_frontend():
 assert client.get('/').status_code==200
 assert client.get('/api/health').json()['yield_prediction'].startswith('disabled')

def test_no_fake_yield():
 response=client.post('/api/yield/predict',json={'crop':'rice','region':'Andhra Pradesh','season':'kharif','year':2026,'average_temp_c':28,'rainfall_mm':100,'soil_moisture':0.2,'ndvi':0.6,'area_hectares':1})
 assert response.status_code==503

def test_ndvi_and_cloud_rejection():
 good=client.post('/api/ndvi/pixel',json={'red_b04':.1,'nir_b08':.5,'scl_class':4,'source_scene_id':'S2_STAC_TEST_SCENE'})
 assert good.status_code==200 and abs(good.json()['ndvi']-2/3)<0.001
 assert client.post('/api/ndvi/pixel',json={'red_b04':.1,'nir_b08':.5,'scl_class':9,'source_scene_id':'S2_STAC_TEST_SCENE'}).status_code==422

def test_weather_real_provider_contract_mocked(monkeypatch):
 from server import app as mod
 async def fake(lat,lon,days):
  return {'daily':{'time':['2026-11-18','2026-11-19'],'temperature_2m_max':[30,35],'temperature_2m_min':[20,22],'precipitation_sum':[0,1],'et0_fao_evapotranspiration':[4,4]},'hourly':{'soil_moisture_0_to_7cm':[.22,.24]}}
 monkeypatch.setattr(mod,'get_weather',fake)
 r=client.post('/api/outlook',json={'crop':'rice','latitude':15.5,'longitude':80,'days':25})
 assert r.status_code==200,r.text
 assert r.json()['days_without_daily_forecast']==23
 assert r.json()['yield_tonnes_per_hectare'] is None
 assert r.json()['summary']['total_rain_mm']==1

def test_satellite_stac_metadata_no_fabricated_ndvi(monkeypatch):
 from server import app as mod
 async def fake(params):
  assert params['collections']==['sentinel-2-c1-l2a']
  return {'features':[{'id':'S2_REAL_METADATA_TEST','properties':{'datetime':'2026-11-14T06:00:00Z','eo:cloud_cover':12},'assets':{'thumbnail':{'href':'https://example.org/real-thumbnail.png'},'red':{'href':'red'},'nir':{'href':'nir'},'scl':{'href':'scl'}},'links':[{'href':'https://example.org/stac'}]}]}
 monkeypatch.setattr(mod,'get_stac',fake)
 r=client.post('/api/satellite/scenes',json={'latitude':15.5,'longitude':80,'days_back':40})
 assert r.status_code==200 and r.json()['count']==1
 assert 'ndvi' not in r.json()['scenes'][0]
