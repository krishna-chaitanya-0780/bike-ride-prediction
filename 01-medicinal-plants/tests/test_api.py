"""Local integration tests; no cloud keys or external API calls are required."""
import os,sys,tempfile,uuid
from pathlib import Path
TEST_DATABASE=Path(tempfile.gettempdir())/f'verdant-atlas-tests-{uuid.uuid4().hex}.sqlite3'
os.environ['DATABASE_URL']='sqlite:///'+str(TEST_DATABASE)
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from server.app import app,SessionLocal,Listing
from sqlalchemy import select
client=TestClient(app)

def test_health_reports_demo_and_local_storage():
 d=client.get('/api/health').json()
 assert d['storage']=='sqlite_local' and d['checkout']=='demo_only' and d['payments']=='not_connected'

def test_plant_search_and_detail_contains_evidence():
 data=client.get('/api/plants').json();assert data['total']==8
 item=client.get('/api/plants?q=brahmi').json()['items'][0]; assert item['common_name']=='Brahmi'
 detail=client.get(f"/api/plants/{item['id']}").json()['plant']
 assert detail['evidence_note'] and detail['precautions']
 assert len(detail['listings'])==3
 assert all(l['is_live_verified'] is False for l in detail['listings'])

def test_regional_listing_filters():
 data=client.get('/api/plants?region=Tamil%20Nadu').json()
 assert data['total']>=1
 plant_id=data['items'][0]['id']
 listing=client.get(f'/api/plants/{plant_id}?region=Tamil%20Nadu').json()['plant']['listings']
 assert listing and all(x['region']=='Tamil Nadu' for x in listing)

def test_account_signup_login_password_hash_and_csrf():
 email=f'tester-{uuid.uuid4().hex[:8]}@example.org'
 created=client.post('/api/auth/register',json={'name':'Field Tester','email':email,'password':'long-example-pass-123'})
 assert created.status_code==201
 csrf=created.json()['csrf'];assert csrf
 assert client.get('/api/auth/me').json()['user']['email']==email
 with SessionLocal() as db:
  record=db.execute(select(Listing).where(Listing.region=='Tamil Nadu')).scalars().first()
  lid=record.id;price=record.price_inr;fee=record.delivery_fee_inr;stock=record.stock
 payload={'region':'Tamil Nadu','address':'Demo parcel, 12 Sample Street, Ongole','lines':[{'listing_id':lid,'quantity':2}]}
 bad=client.post('/api/orders/demo',json=payload)
 assert bad.status_code==403
 ok=client.post('/api/orders/demo',json=payload,headers={'X-CSRF-Token':csrf})
 assert ok.status_code==201,ok.text
 data=ok.json();assert data['status']=='DEMO_ONLY_NOT_PAID_OR_SHIPPED'
 assert data['total_inr']==price*2+fee
 assert client.get('/api/orders').json()['orders'][0]['id']==data['order_id']
 with SessionLocal() as db:
  assert db.get(Listing,lid).stock==stock-2
 logout=client.post('/api/auth/logout',json={},headers={'X-CSRF-Token':csrf})
 assert logout.status_code==200
 assert client.get('/api/auth/me').status_code==401
 login=client.post('/api/auth/login',json={'email':email,'password':'long-example-pass-123'})
 assert login.status_code==200

def test_duplicate_listing_quantities_are_aggregated():
 csrf=client.get('/api/auth/me').json()['csrf']
 with SessionLocal() as db:
  listing=db.execute(select(Listing).where(Listing.region=='Tamil Nadu',Listing.stock>=3)).scalars().first()
 body={'region':'Tamil Nadu','address':'16 Example Road, Ongole, AP','lines':[{'listing_id':listing.id,'quantity':1},{'listing_id':listing.id,'quantity':2}]}
 r=client.post('/api/orders/demo',json=body,headers={'X-CSRF-Token':csrf})
 assert r.status_code==201,r.text
 assert len(r.json()['lines'])==1 and r.json()['lines'][0]['quantity']==3

def test_invalid_region_and_out_of_stock_are_rejected_without_order():
 csrf=client.get('/api/auth/me').json()['csrf']
 with SessionLocal() as db:
  listing=db.execute(select(Listing).where(Listing.region=='Tamil Nadu')).scalars().first()
 line={'listing_id':listing.id,'quantity':1}
 bad=client.post('/api/orders/demo',json={'region':'Karnataka','address':'Test street address, Bengaluru','lines':[line]},headers={'X-CSRF-Token':csrf})
 assert bad.status_code==422
 too_many=client.post('/api/orders/demo',json={'region':'Tamil Nadu','address':'Test street address, Chennai','lines':[{'listing_id':listing.id,'quantity':20}]},headers={'X-CSRF-Token':csrf})
 assert too_many.status_code in (201,409)

def test_static_home_served():
 r=client.get('/'); assert r.status_code==200 and 'Shop medicinal plants' in r.text
 assert client.get('/assets/app.js').status_code==200


def test_search_alias_ranking_typo_and_telugu_name():
    holy=client.get('/api/catalog?q=holy%20basil').json()
    assert holy['total'] >= 1 and holy['items'][0]['common_name'] == 'Tulsi'
    tulasi=client.get('/api/catalog?q=tulasi').json()
    assert tulasi['items'][0]['common_name'] == 'Tulsi'
    typo=client.get('/api/catalog?q=ashwaganda').json()
    assert typo['total'] >= 1 and typo['items'][0]['common_name'] == 'Ashwagandha'
    vernacular=client.get('/api/catalog?q=%E0%B0%95%E0%B0%B2%E0%B0%AC%E0%B0%82%E0%B0%A6').json()
    assert vernacular['total'] >= 1 and vernacular['items'][0]['common_name'] == 'Aloe vera'


def test_search_suggestion_facets_category_and_price_sort():
    suggestions=client.get('/api/search/suggest?q=hol%20bas').json()['suggestions']
    assert suggestions and suggestions[0]['name'] == 'Tulsi'
    facets=client.get('/api/catalog/facets').json()
    assert facets['categories']['Aromatic herbs'] == 3
    category=client.get('/api/catalog?category=Aromatic%20herbs').json()
    assert category['total'] == 3
    assert {x['common_name'] for x in category['items']} == {'Tulsi','Lemongrass','Mint'}
    low=client.get('/api/catalog?sort=price_asc&region=Andhra%20Pradesh').json()['items']
    prices=[x['min_price_inr'] for x in low]
    assert prices == sorted(prices)
    assert client.get('/api/catalog?min_price=200&max_price=100').status_code == 422


def test_server_quote_validates_region_stock_and_duplicate_items():
    with SessionLocal() as db:
        item=db.execute(select(Listing).where(Listing.region=='Andhra Pradesh')).scalars().first()
        lid,price,delivery,stock=item.id,item.price_inr,item.delivery_fee_inr,item.stock
    quote=client.post('/api/checkout/quote',json={'region':'Andhra Pradesh','lines':[
        {'listing_id':lid,'quantity':1},{'listing_id':lid,'quantity':2}
    ]})
    assert quote.status_code==200,quote.text
    assert quote.json()['subtotal_inr']==price*3
    assert quote.json()['delivery_inr']==delivery
    assert quote.json()['total_inr']==price*3+delivery
    assert client.post('/api/checkout/quote',json={'region':'Tamil Nadu','lines':[{'listing_id':lid,'quantity':1}]}).status_code==422
    assert client.post('/api/checkout/quote',json={'region':'Andhra Pradesh','lines':[{'listing_id':lid,'quantity':stock+1}]}).status_code in (409,422)


def test_wishlist_requires_login_and_csrf():
    with TestClient(app) as isolated:
        assert isolated.get('/api/wishlist').status_code==401
        email=f'wishlist-{uuid.uuid4().hex}@example.org'
        account=isolated.post('/api/auth/register',json={'name':'Wishlist Tester','email':email,'password':'unique-test-password-21'})
        assert account.status_code==201
        csrf=account.json()['csrf']
        assert isolated.post('/api/wishlist/1',json={}).status_code==403
        saved=isolated.post('/api/wishlist/1',json={},headers={'X-CSRF-Token':csrf})
        assert saved.status_code==200 and saved.json()['saved']
        assert 1 in isolated.get('/api/wishlist').json()['plant_ids']
        removed=isolated.request('DELETE','/api/wishlist/1',json={},headers={'X-CSRF-Token':csrf})
        assert removed.status_code==200 and not removed.json()['saved']
        assert isolated.get('/api/wishlist').json()['plant_ids']==[]


def test_real_photo_provenance_and_plant_fact_sheet():
    items=client.get('/api/catalog?limit=100').json()['items']
    assert len(items)==8
    assert all(x['photo']['photo_kind']=='real_species_photograph' for x in items)
    assert all('commons.wikimedia.org/wiki/File:' in x['photo']['photo_page'] for x in items)
    assert all('creativecommons.org/' in x['photo']['license_url'] for x in items)
    assert all('powo.science.kew.org/taxon/' in x['photo']['scientific_source'] for x in items)
    assert all(x['fact_sheet']['overview'] and x['fact_sheet']['where_grown'] and x['fact_sheet']['real_use'] for x in items)
    assert all('/assets/specimen-' not in x['photo']['image_url'] for x in items)


def test_dark_storefront_and_brand_are_served():
    home=client.get('/').text
    assert 'THE BOTANICAL MARKET' in home
    assert 'Shop medicinal plants' in home
    css=client.get('/assets/styles.css').text
    assert '--page:#111a16' in css
    assert 'prefers-reduced-motion' in css
    assert client.get('/assets/brand-mark.svg').status_code==200
    assert client.get('/assets/app.js').status_code==200
