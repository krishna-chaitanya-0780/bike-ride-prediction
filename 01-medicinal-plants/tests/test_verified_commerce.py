"""Security and offline contract tests for seller + TEST-only commerce flows.
No live payment, email, parcel or network activity is performed."""
import hashlib,hmac,os,json,uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from server.app import app, SessionLocal
from server.commerce import Merchant,LiveOffer,CommerceOrder,Shipment


def new_seller():
    client=TestClient(app)
    email=f'seller-{uuid.uuid4().hex}@example.org'
    response=client.post('/api/auth/register',json={'name':'Demo Nursery Manager','email':email,'password':'unique-example-password-1234'})
    assert response.status_code==201,response.text
    csrf=response.json()['csrf']
    data={'business_name':'Coastal Herbs Nursery','contact_email':email,'city':'Ongole','region':'Andhra Pradesh','pickup_pincode':'523001'}
    assert client.post('/api/commerce/seller/apply',json=data,headers={'X-CSRF-Token':csrf}).status_code==201
    return client,csrf


def seller_offer(client,csrf):
    response=client.post('/api/commerce/seller/offers',json={'plant_id':1,'unit':'1 potted rooted Tulsi plant','price_inr':135,'stock':7,'handling_days':3,'proof_reference':'Inventory receipt #test-2026-01'},headers={'X-CSRF-Token':csrf})
    assert response.status_code==201,response.text
    return response.json()['offer']


def approve(client,csrf,monkeypatch):
    seller=seller_offer(client,csrf)
    merchant=client.get('/api/commerce/seller/me').json()['merchant']
    monkeypatch.setenv('VERDANT_OWNER_TOKEN','0123456789abcdef0123456789abcdefOWNER')
    admin={'X-Owner-Token':os.environ['VERDANT_OWNER_TOKEN']}
    assert client.post(f"/api/commerce/owner/merchants/{merchant['id']}/review",json={'approved':True,'evidence_note':'Identity checked offline for local integration test only'},headers=admin).status_code==200
    assert client.post(f"/api/commerce/owner/offers/{seller['id']}/review",json={'approved':True,'evidence_note':'Test inventory evidence reviewed for sandbox only'},headers=admin).status_code==200
    return seller['id'], merchant['id']


def test_seller_review_and_visibility(monkeypatch):
    client,csrf=new_seller()
    result=seller_offer(client,csrf)
    offerid=result['id'];sellerid=client.get('/api/commerce/seller/me').json()['merchant']['id']
    assert client.get('/api/commerce/offers').json()['total']==0
    assert client.get('/api/commerce/owner/review').status_code==403
    assert client.post(f'/api/commerce/owner/offers/{offerid}/review',json={'approved':True,'evidence_note':'not verified seller review'},headers={'X-Owner-Token':'x'}).status_code==403
    monkeypatch.setenv('VERDANT_OWNER_TOKEN','ABCDEFGHIJKLMNOPabcdefghijklmnop_123456789')
    hdr={'X-Owner-Token':os.environ['VERDANT_OWNER_TOKEN']}
    assert client.post(f'/api/commerce/owner/offers/{offerid}/review',json={'approved':True,'evidence_note':'evidence note accepted for product'},headers=hdr).status_code==409
    assert client.post(f'/api/commerce/owner/merchants/{sellerid}/review',json={'approved':True,'evidence_note':'Business paperwork verified offline in test'},headers=hdr).status_code==200
    assert client.post(f'/api/commerce/owner/offers/{offerid}/review',json={'approved':True,'evidence_note':'Product photographs and stock checked'},headers=hdr).status_code==200
    listing=client.get('/api/commerce/offers').json()
    assert listing['total']==1 and any(x['id']==offerid for x in listing['items'])
    assert listing['items'][0]['stock']==7
    updated=client.put(f'/api/commerce/seller/offers/{offerid}',json={'plant_id':1,'unit':'Updated 6 inch nursery pot','price_inr':128,'stock':4,'handling_days':2,'proof_reference':'Inventory updated per crop receipt'},headers={'X-CSRF-Token':csrf})
    assert updated.status_code==200
    assert client.get('/api/commerce/offers').json()['total']==0  # update revokes verification


def test_checkout_fails_closed_without_test_keys(monkeypatch):
    client,csrf=new_seller()
    id_,_=approve(client,csrf,monkeypatch)
    payload={'region':'Andhra Pradesh','postal_code':'523001','address':'12 Garden Lane, Ongole, Andhra Pradesh','lines':[{'offer_id':id_,'quantity':2}]}
    quote=client.post('/api/commerce/checkout/quote',json=payload)
    assert quote.status_code==200,quote.text
    assert quote.json()['subtotal_inr']==270 and quote.json()['shipping_kind'].startswith('UNVERIFIED')
    for name in ['ENABLE_TEST_CHECKOUT','RAZORPAY_KEY_ID','RAZORPAY_KEY_SECRET']:
        monkeypatch.delenv(name,raising=False)
    assert client.post('/api/commerce/checkout/create-test-order',json=payload,headers={'X-CSRF-Token':csrf}).status_code==503
    assert client.post('/api/commerce/checkout/create-test-order',json=payload).status_code==403
    assert client.get('/api/commerce/delivery/quote?pickup_pincode=523001&delivery_pincode=600001').status_code==503
    assert client.post('/api/commerce/orders/notreal/ship').status_code==503


def test_sandbox_payment_gateway_verified_and_idempotent(monkeypatch):
    client,csrf=new_seller()
    offer_id,_=approve(client,csrf,monkeypatch)
    monkeypatch.setenv('ENABLE_TEST_CHECKOUT','1')
    monkeypatch.setenv('RAZORPAY_KEY_ID','rzp_test_thisisfake')
    secret='sandbox-secret-for-unit-test'
    monkeypatch.setenv('RAZORPAY_KEY_SECRET',secret)
    monkeypatch.setenv('RAZORPAY_TEST_WEBHOOK_SECRET','webhook-test-only-secret')
    from server import commerce
    real_client=commerce.httpx.Client
    class Response:
        def __init__(self,data):self.data=data
        def raise_for_status(self):pass
        def json(self):return self.data
    last={'order_id':None,'amount':None}
    class StubGateway:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def post(self,url,auth=None,json=None):
            assert url.endswith('/v1/orders') and auth[0].startswith('rzp_test_')
            last['order_id']='order_FAKE1234567';last['amount']=json['amount'];
            return Response({'id':last['order_id'],'amount':json['amount'],'currency':'INR'})
        def get(self,url,auth=None):
            return Response({'id':'pay_FAKE121','order_id':last['order_id'],'amount':last['amount'],'currency':'INR','status':'captured'})
    monkeypatch.setattr(commerce.httpx,'Client',StubGateway)
    payload={'region':'Andhra Pradesh','postal_code':'523001','address':'17 Mango Gardens, Ongole, Andhra Pradesh','lines':[{'offer_id':offer_id,'quantity':2}]}
    created=client.post('/api/commerce/checkout/create-test-order',json=payload,headers={'X-CSRF-Token':csrf})
    assert created.status_code==201,created.text
    info=created.json();assert info['mode']=='TEST_ONLY_NOT_LIVE'
    with SessionLocal() as db:
        o=db.get(LiveOffer,offer_id);assert o.stock==7 and o.reserved==2
    incorrect={'local_order_id':info['local_order_id'],'razorpay_order_id':info['gateway_order_id'],'razorpay_payment_id':'pay_FAKE121','razorpay_signature':'false'}
    assert client.post('/api/commerce/checkout/verify-test-payment',json=incorrect,headers={'X-CSRF-Token':csrf}).status_code==403
    signed=hmac.new(secret.encode(),(info['gateway_order_id']+'|pay_FAKE121').encode(),hashlib.sha256).hexdigest()
    incorrect['razorpay_signature']=signed
    success=client.post('/api/commerce/checkout/verify-test-payment',json=incorrect,headers={'X-CSRF-Token':csrf})
    assert success.status_code==200,success.text
    assert success.json()['status']=='PAID_TEST_VERIFIED'
    again=client.post('/api/commerce/checkout/verify-test-payment',json=incorrect,headers={'X-CSRF-Token':csrf})
    assert again.status_code==200 and again.json()['idempotent']
    with SessionLocal() as db:
        o=db.get(LiveOffer,offer_id);assert o.stock==5 and o.reserved==0
        shipping=db.scalar(select(Shipment).where(Shipment.order_id==info['local_order_id']))
        assert shipping and shipping.status=='NOT_BOOKED'
    event={'event':'payment.captured','payload':{'payment':{'entity':{'id':'pay_FAKE121','order_id':info['gateway_order_id']}}}}
    raw=json.dumps(event).encode()
    sig=hmac.new(b'webhook-test-only-secret',raw,hashlib.sha256).hexdigest()
    wh=client.post('/api/commerce/webhooks/razorpay-test',content=raw,headers={'X-Razorpay-Signature':sig,'X-Razorpay-Event-Id':'evt_same','Content-Type':'application/json'})
    assert wh.status_code==200 and wh.json()['processed']
    wh2=client.post('/api/commerce/webhooks/razorpay-test',content=raw,headers={'X-Razorpay-Signature':sig,'X-Razorpay-Event-Id':'evt_same','Content-Type':'application/json'})
    assert wh2.status_code==200 and wh2.json()['duplicate']
    bad=client.post('/api/commerce/webhooks/razorpay-test',content=raw,headers={'X-Razorpay-Signature':'bad','Content-Type':'application/json'})
    assert bad.status_code==403
    monkeypatch.setattr(commerce.httpx,'Client',real_client)


def test_historical_reference_prices_are_not_checkout_offers():
    client=TestClient(app)
    r=client.get('/api/commerce/price-references')
    assert r.status_code==200
    assert all(row['historical'] and row['may_not_be_current'] for row in r.json()['prices'])
    assert all(row['source_url'].startswith('https://') for row in r.json()['prices'])
