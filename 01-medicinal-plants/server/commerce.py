"""Opt-in verified merchant workflows and sandbox-only payment/delivery connectors.

All commerce operations fail closed unless a human reviewer verifies a merchant,
that merchant owns an approved published offer, and a TEST payment gateway is set.
Never interpret demonstration seed inventory as stock that can be purchased.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, select, update
from sqlalchemy.orm import Mapped, Session, mapped_column

from .app import Base, Plant, User, engine, resolve_user, session

router=APIRouter(prefix='/api/commerce',tags=['Verified Merchant Commerce'])
Db=Annotated[Session, Depends(session)]

class Merchant(Base):
    __tablename__='merchants'
    id: Mapped[int]=mapped_column(primary_key=True)
    user_id: Mapped[int]=mapped_column(ForeignKey('users.id'),unique=True,index=True)
    business_name: Mapped[str]=mapped_column(String(120))
    contact_email: Mapped[str]=mapped_column(String(254))
    city: Mapped[str]=mapped_column(String(90))
    region: Mapped[str]=mapped_column(String(90))
    pickup_pincode: Mapped[str]=mapped_column(String(6))
    status: Mapped[str]=mapped_column(String(30),default='PENDING_REVIEW')
    review_note: Mapped[str]=mapped_column(Text,default='')
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    reviewed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class LiveOffer(Base):
    __tablename__='merchant_offers'
    id: Mapped[int]=mapped_column(primary_key=True)
    merchant_id: Mapped[int]=mapped_column(ForeignKey('merchants.id'),index=True)
    plant_id: Mapped[int]=mapped_column(ForeignKey('plants.id'),index=True)
    unit: Mapped[str]=mapped_column(String(90))
    price_inr: Mapped[int]=mapped_column(Integer)
    stock: Mapped[int]=mapped_column(Integer)
    reserved: Mapped[int]=mapped_column(Integer,default=0)
    handling_days: Mapped[int]=mapped_column(Integer,default=2)
    proof_reference: Mapped[str]=mapped_column(String(500),default='')
    review_note: Mapped[str]=mapped_column(Text,default='')
    status: Mapped[str]=mapped_column(String(30),default='PENDING_REVIEW')
    last_seller_confirmed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    approved_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class CommerceOrder(Base):
    __tablename__='merchant_orders'
    id: Mapped[str]=mapped_column(String(36),primary_key=True)
    user_id: Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    merchant_id: Mapped[int]=mapped_column(ForeignKey('merchants.id'))
    region: Mapped[str]=mapped_column(String(90))
    postal_code: Mapped[str]=mapped_column(String(6))
    address: Mapped[str]=mapped_column(String(320))
    subtotal_inr: Mapped[int]=mapped_column(Integer)
    shipping_inr: Mapped[int]=mapped_column(Integer)
    total_inr: Mapped[int]=mapped_column(Integer)
    lines: Mapped[list]=mapped_column(JSON)
    status: Mapped[str]=mapped_column(String(50),default='AWAITING_TEST_PAYMENT')
    gateway_order_id: Mapped[str|None]=mapped_column(String(100),unique=True,nullable=True)
    gateway_payment_id: Mapped[str|None]=mapped_column(String(100),nullable=True)
    reserved_until: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class Shipment(Base):
    __tablename__='merchant_shipments'
    id: Mapped[int]=mapped_column(primary_key=True)
    order_id: Mapped[str]=mapped_column(ForeignKey('merchant_orders.id'),unique=True)
    provider: Mapped[str]=mapped_column(String(60),default='not_connected')
    provider_shipment_id: Mapped[str|None]=mapped_column(String(100),nullable=True)
    awb: Mapped[str|None]=mapped_column(String(100),nullable=True)
    status: Mapped[str]=mapped_column(String(50),default='NOT_BOOKED')
    last_event_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class WebhookEvent(Base):
    __tablename__='payment_webhook_events'
    id: Mapped[int]=mapped_column(primary_key=True)
    event_id: Mapped[str]=mapped_column(String(130),unique=True)
    event_name: Mapped[str]=mapped_column(String(90))
    received_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

Base.metadata.create_all(engine)

class ApplySeller(BaseModel):
    business_name:str=Field(min_length=3,max_length=120)
    contact_email:EmailStr
    city:str=Field(min_length=2,max_length=90)
    region:str=Field(min_length=2,max_length=90)
    pickup_pincode:str=Field(pattern=r'^\d{6}$')

class OfferInput(BaseModel):
    plant_id:int=Field(gt=0)
    unit:str=Field(min_length=4,max_length=90)
    price_inr:int=Field(ge=1,le=250000)
    stock:int=Field(ge=0,le=500000)
    handling_days:int=Field(ge=0,le=30)
    proof_reference:str=Field(min_length=8,max_length=500)

class ReviewInput(BaseModel):
    approved:bool
    evidence_note:str=Field(min_length=12,max_length=800)

class OrderLineInput(BaseModel):
    offer_id:int=Field(gt=0)
    quantity:int=Field(ge=1,le=20)

class PaymentOrderInput(BaseModel):
    lines:list[OrderLineInput]=Field(min_length=1,max_length=20)
    region:str=Field(min_length=2,max_length=90)
    postal_code:str=Field(pattern=r'^\d{6}$')
    address:str=Field(min_length=12,max_length=320)

class ConfirmPaymentInput(BaseModel):
    local_order_id:str
    razorpay_order_id:str
    razorpay_payment_id:str
    razorpay_signature:str

def user_and_csrf(request:Request,db:Session):
    return resolve_user(request,db,csrf_required=True)[0]

def owner_access(token:str|None):
    actual=os.getenv('VERDANT_OWNER_TOKEN','')
    if len(actual)<28 or not token or not secrets.compare_digest(actual,token):
        raise HTTPException(403,'Owner review requires a private configured owner token')


def merchant_dict(m:Merchant):
    return {k:getattr(m,k) for k in ('id','business_name','city','region','pickup_pincode','status','review_note')}

def offer_dict(o:LiveOffer,m:Merchant|None=None,p:Plant|None=None):
    return {'id':o.id,'plant_id':o.plant_id,'plant_name':p.common_name if p else None,
            'merchant_id':o.merchant_id,'seller_name':m.business_name if m else None,
            'region':m.region if m else None,'city':m.city if m else None,
            'unit':o.unit,'price_inr':o.price_inr,'stock':max(0,o.stock-o.reserved),
            'handling_days':o.handling_days,'status':o.status,
            'verified_seller':bool(m and m.status=='VERIFIED'),
            'seller_confirmed_at':o.last_seller_confirmed_at.isoformat() if o.last_seller_confirmed_at else None,
            'reviewed_at':o.approved_at.isoformat() if o.approved_at else None,
            'source_kind':'seller_managed_verified_review_not_live_market_price'}

@router.get('/status')
def commerce_status():
    key=os.getenv('RAZORPAY_KEY_ID','')
    return {'merchant_onboarding':'available_pending_manual_verification',
            'sandbox_payment_ready':bool(os.getenv('ENABLE_TEST_CHECKOUT')=='1' and key.startswith('rzp_test_') and os.getenv('RAZORPAY_KEY_SECRET')),
            'live_payments':False,'courier_quotes_ready':os.getenv('ENABLE_SHIPROCKET_QUOTES')=='1' and bool(os.getenv('SHIPROCKET_API_TOKEN')),
            'booked_shipping':False,'provider':'Razorpay test keys only','seller_seed_data':'not_verified'}

@router.post('/seller/apply',status_code=201)
def apply_seller(data:ApplySeller,request:Request,db:Db):
    user=user_and_csrf(request,db)
    if db.scalar(select(Merchant).where(Merchant.user_id==user.id)):raise HTTPException(409,'Seller application already exists')
    m=Merchant(user_id=user.id,**data.model_dump(),status='PENDING_REVIEW')
    db.add(m);db.commit();db.refresh(m)
    return {'merchant':merchant_dict(m),'message':'Application pending independent owner review; no listings are live.'}

@router.get('/seller/me')
def seller_me(request:Request,db:Db):
    user,_=resolve_user(request,db)
    m=db.scalar(select(Merchant).where(Merchant.user_id==user.id))
    return {'merchant':merchant_dict(m) if m else None,'offers':[offer_dict(o,m,db.get(Plant,o.plant_id)) for o in db.scalars(select(LiveOffer).where(LiveOffer.merchant_id==m.id))] if m else []}

@router.post('/seller/offers',status_code=201)
def submit_offer(data:OfferInput,request:Request,db:Db):
    user=user_and_csrf(request,db)
    m=db.scalar(select(Merchant).where(Merchant.user_id==user.id))
    if not m: raise HTTPException(403,'Apply as a seller first')
    if not db.get(Plant,data.plant_id):raise HTTPException(404,'Unknown botanically identified species')
    o=LiveOffer(merchant_id=m.id,**data.model_dump(),status='PENDING_REVIEW',last_seller_confirmed_at=datetime.now(timezone.utc))
    db.add(o);db.commit();db.refresh(o)
    return {'offer':offer_dict(o,m,db.get(Plant,o.plant_id)),'message':'Not publicly purchasable until independent review.'}

@router.put('/seller/offers/{offer_id}')
def update_offer(offer_id:int,data:OfferInput,request:Request,db:Db):
    user=user_and_csrf(request,db)
    m=db.scalar(select(Merchant).where(Merchant.user_id==user.id))
    o=db.get(LiveOffer,offer_id)
    if not m or not o or o.merchant_id!=m.id:raise HTTPException(404,'Offer unavailable')
    if o.reserved:raise HTTPException(409,'Offer has outstanding reservations; contact support')
    if not db.get(Plant,data.plant_id):raise HTTPException(404,'Plant not found')
    for key,value in data.model_dump().items():setattr(o,key,value)
    o.status='PENDING_REVIEW'  # any modification revokes approval until reviewed again
    o.approved_at=None
    o.review_note=''
    o.last_seller_confirmed_at=datetime.now(timezone.utc)
    db.commit()
    return {'offer':offer_dict(o,m,db.get(Plant,o.plant_id)),'message':'Change requires renewed approval.'}

@router.get('/owner/review')
def owner_queue(db:Db,x_owner_token:Annotated[str|None,Header()]=None):
    owner_access(x_owner_token)
    merchants=db.scalars(select(Merchant)).all()
    offers=db.scalars(select(LiveOffer)).all()
    return {'merchants':[merchant_dict(m) for m in merchants],
            'offers':[offer_dict(o,db.get(Merchant,o.merchant_id),db.get(Plant,o.plant_id)) for o in offers]}

@router.post('/owner/merchants/{merchant_id}/review')
def review_merchant(merchant_id:int,data:ReviewInput,db:Db,x_owner_token:Annotated[str|None,Header()]=None):
    owner_access(x_owner_token)
    m=db.get(Merchant,merchant_id)
    if not m:raise HTTPException(404,'Merchant not found')
    m.status='VERIFIED' if data.approved else 'REJECTED'
    m.review_note=data.evidence_note
    m.reviewed_at=datetime.now(timezone.utc)
    if not data.approved:
        for o in db.scalars(select(LiveOffer).where(LiveOffer.merchant_id==merchant_id)):o.status='SUSPENDED'
    db.commit()
    return {'merchant':merchant_dict(m)}

@router.post('/owner/offers/{offer_id}/review')
def review_offer(offer_id:int,data:ReviewInput,db:Db,x_owner_token:Annotated[str|None,Header()]=None):
    owner_access(x_owner_token)
    o=db.get(LiveOffer,offer_id)
    if not o: raise HTTPException(404,'Offer not found')
    m=db.get(Merchant,o.merchant_id)
    if data.approved and (not m or m.status!='VERIFIED'):raise HTTPException(409,'Verify merchant first')
    o.status='APPROVED' if data.approved else 'REJECTED'
    o.review_note=data.evidence_note
    o.approved_at=datetime.now(timezone.utc) if data.approved else None
    db.commit()
    return {'offer':offer_dict(o,m,db.get(Plant,o.plant_id)),'review_note_recorded':bool(data.evidence_note)}

@router.get('/offers')
def approved_offers(db:Db,plant_id:int|None=None,region:str='',sort:str='price_asc',limit:int=Query(100,ge=1,le=100)):
    stmt=select(LiveOffer).where(LiveOffer.status=='APPROVED',LiveOffer.stock>LiveOffer.reserved)
    if plant_id:stmt=stmt.where(LiveOffer.plant_id==plant_id)
    rows=db.scalars(stmt).all()
    arr=[]
    for offer in rows:
        merchant=db.get(Merchant,offer.merchant_id)
        if not merchant or merchant.status!='VERIFIED' or (region and merchant.region!=region):continue
        arr.append(offer_dict(offer,merchant,db.get(Plant,offer.plant_id)))
    arr.sort(key=lambda x:x['price_inr'] if sort=='price_asc' else -x['price_inr'] if sort=='price_desc' else x['plant_name'].lower())
    return {'items':arr[:limit],'total':len(arr),'price_label':'Seller-maintained offers requiring independent review; prices must be reconfirmed before payment.'}

# Known institutional reference prices are informational, never transaction offers.
@router.get('/price-references')
def price_references():
    return {'prices':[
       {'name':'Tulsi species','reference_price_inr':5,'unit':'plant','source':'DMAPR historical nursery propagation price list','source_url':'https://www.dmapr.org.in/HeadPage/Pricelist.html','historical':True,'may_not_be_current':True},
       {'name':'Ashwagandha','reference_price_inr':15,'unit':'plant','source':'DMAPR historical nursery propagation price list','source_url':'https://www.dmapr.org.in/HeadPage/Pricelist.html','historical':True,'may_not_be_current':True},
       {'name':'Giloy','reference_price_inr':15,'unit':'plant','source':'DMAPR historical nursery propagation price list (grouped species)','source_url':'https://www.dmapr.org.in/HeadPage/Pricelist.html','historical':True,'may_not_be_current':True}
    ],'notice':'Institutional historical references, not current vendor quotations or offers. Shipping, tax and quantity may differ.'}

def test_gateway_config():
    key=os.getenv('RAZORPAY_KEY_ID','');secret=os.getenv('RAZORPAY_KEY_SECRET','')
    if os.getenv('ENABLE_TEST_CHECKOUT')!='1' or not key.startswith('rzp_test_') or not secret:
        raise HTTPException(503,'Test payment gateway is not configured; real payments are disabled')
    return key,secret

def quotes(data:PaymentOrderInput,db:Session,require_service:bool):
    # all lines must belong to ONE approved merchant in ONE target region
    quantities={}
    for item in data.lines:quantities[item.offer_id]=quantities.get(item.offer_id,0)+item.quantity
    if sum(quantities.values())>40:raise HTTPException(422,'Maximum 40 plants in one purchase')
    merchant=None;lines=[];subtotal=0
    for oid,quantity in quantities.items():
        offer=db.get(LiveOffer,oid)
        if not offer or offer.status!='APPROVED':raise HTTPException(409,'Unapproved or unavailable live offer')
        m=db.get(Merchant,offer.merchant_id)
        if not m or m.status!='VERIFIED' or m.region!=data.region:raise HTTPException(422,'Choose a verified seller delivering to your region')
        if merchant and merchant.id!=m.id:raise HTTPException(422,'One seller per order; split multi-seller baskets')
        if offer.stock-offer.reserved<quantity:raise HTTPException(409,'Insufficient confirmed available inventory')
        merchant=m
        plant=db.get(Plant,offer.plant_id)
        subtotal+=offer.price_inr*quantity
        lines.append({'offer_id':oid,'quantity':quantity,'plant_id':offer.plant_id,'plant_name':plant.common_name,'unit_price_inr':offer.price_inr})
    # Never quote a shipment amount as real without a courier serviceability result.
    # For sandbox use only, zero shipping is explicitly a test assumption.
    shipping=0
    return merchant,lines,subtotal,shipping

@router.post('/checkout/quote')
def merchant_quote(data:PaymentOrderInput,db:Db):
    merchant,lines,subtotal,shipping=quotes(data,db,False)
    return {'merchant':merchant_dict(merchant),'lines':lines,'subtotal_inr':subtotal,'shipping_inr':shipping,'total_inr':subtotal+shipping,
            'shipping_kind':'UNVERIFIED_SANDBOX_ASSUMPTION_NOT_FREIGHT_QUOTE',
            'can_pay_test':os.getenv('ENABLE_TEST_CHECKOUT')=='1',
            'can_pay_live':False,'notice':'This cannot be used as a live customer quotation until shipping charges and serviceability are confirmed.'}

@router.post('/checkout/create-test-order',status_code=201)
def create_test_order(data:PaymentOrderInput,request:Request,db:Db):
    user=user_and_csrf(request,db)
    key,secret=test_gateway_config()
    merchant,lines,subtotal,shipping=quotes(data,db,True)
    order_id=str(uuid.uuid4())
    # charge exactly server-derived total, never trust client amount
    total=subtotal+shipping
    if total<=0:raise HTTPException(422,'No payable amount')
    # Gateway may be unavailable; no local inventory changes if it fails.
    try:
        with httpx.Client(timeout=12) as client:
            resp=client.post('https://api.razorpay.com/v1/orders',auth=(key,secret),json={'amount':total*100,'currency':'INR','receipt':order_id,'notes':{'mode':'sandbox_only','local_order_id':order_id}})
            resp.raise_for_status()
            provider=resp.json()
    except (httpx.HTTPError,ValueError) as exc:
        raise HTTPException(503,'Razorpay TEST order service unavailable') from exc
    if not isinstance(provider,dict) or not str(provider.get('id','')).startswith('order_') or provider.get('amount')!=total*100 or provider.get('currency')!='INR':
        raise HTTPException(502,'Invalid sandbox payment-order response')
    # reserve atomically and require all stock updates to succeed; rollback on failure
    try:
        for line in lines:
            statement=update(LiveOffer).where(LiveOffer.id==line['offer_id'],LiveOffer.status=='APPROVED',LiveOffer.stock-LiveOffer.reserved>=line['quantity']).values(reserved=LiveOffer.reserved+line['quantity'])
            if db.execute(statement).rowcount!=1:raise HTTPException(409,'Stock changed during checkout; retry with a fresh quote')
        order=CommerceOrder(id=order_id,user_id=user.id,merchant_id=merchant.id,region=data.region,postal_code=data.postal_code,address=data.address,subtotal_inr=subtotal,shipping_inr=shipping,total_inr=total,lines=lines,status='AWAITING_TEST_PAYMENT',gateway_order_id=provider['id'],reserved_until=datetime.now(timezone.utc)+timedelta(minutes=15))
        db.add(order);db.commit()
    except Exception:
        db.rollback();raise
    return {'local_order_id':order_id,'gateway_order_id':provider['id'],'key_id':key,'amount_paise':total*100,'currency':'INR','mode':'TEST_ONLY_NOT_LIVE','checkout_status':'AWAITING_TEST_PAYMENT','expires_in_minutes':15}

def verify_rzp_payment_gateway(order:CommerceOrder,payment_id:str,key:str,secret:str):
    try:
        with httpx.Client(timeout=12) as client:
            resp=client.get(f'https://api.razorpay.com/v1/payments/{payment_id}',auth=(key,secret))
            resp.raise_for_status();data=resp.json()
    except (httpx.HTTPError,ValueError) as exc:raise HTTPException(503,'Cannot independently verify payment status') from exc
    if data.get('order_id')!=order.gateway_order_id or data.get('amount')!=order.total_inr*100 or data.get('currency')!='INR' or data.get('status')!='captured' or data.get('id')!=payment_id:
        raise HTTPException(409,'Payment has not been independently confirmed captured for this exact order')
    return True

def confirm_paid_order(db:Session,order:CommerceOrder,payment_id:str,key:str,secret:str):
    if order.status=='PAID_TEST_VERIFIED':
        if order.gateway_payment_id!=payment_id:raise HTTPException(409,'Order already recorded under another payment')
        return {'status':order.status,'idempotent':True}
    if order.status!='AWAITING_TEST_PAYMENT':raise HTTPException(409,'Order cannot be paid from current state')
    if order.reserved_until.replace(tzinfo=timezone.utc)<datetime.now(timezone.utc):raise HTTPException(409,'Reservation expired; payment must be manually reconciled')
    verify_rzp_payment_gateway(order,payment_id,key,secret)
    for line in order.lines:
        # Reservation is consumed exactly once, with both counters updated atomically.
        query=update(LiveOffer).where(LiveOffer.id==line['offer_id'],LiveOffer.reserved>=line['quantity'],LiveOffer.stock>=line['quantity']).values(stock=LiveOffer.stock-line['quantity'],reserved=LiveOffer.reserved-line['quantity'])
        if db.execute(query).rowcount!=1:raise HTTPException(409,'Stock state conflict; requires manual reconciliation')
    order.gateway_payment_id=payment_id;order.status='PAID_TEST_VERIFIED'
    db.add(Shipment(order_id=order.id,provider='not_connected',status='NOT_BOOKED'))
    db.commit()
    return {'status':order.status,'idempotent':False,'shipment':'NOT_BOOKED'}

@router.post('/checkout/verify-test-payment')
def confirm_test_payment(data:ConfirmPaymentInput,request:Request,db:Db):
    user=user_and_csrf(request,db)
    key,secret=test_gateway_config()
    order=db.get(CommerceOrder,data.local_order_id)
    if not order or order.user_id!=user.id or order.gateway_order_id!=data.razorpay_order_id:raise HTTPException(404,'Your test order was not found')
    payload=f'{order.gateway_order_id}|{data.razorpay_payment_id}'.encode()
    actual=hmac.new(secret.encode(),payload,hashlib.sha256).hexdigest()
    if not secrets.compare_digest(actual,data.razorpay_signature):raise HTTPException(403,'Payment signature invalid')
    return confirm_paid_order(db,order,data.razorpay_payment_id,key,secret)

@router.post('/webhooks/razorpay-test')
async def razorpay_test_webhook(request:Request,db:Db,x_razorpay_signature:Annotated[str|None,Header()]=None,x_razorpay_event_id:Annotated[str|None,Header()]=None):
    key,secret=test_gateway_config()
    webhook_secret=os.getenv('RAZORPAY_TEST_WEBHOOK_SECRET','')
    if not webhook_secret:raise HTTPException(503,'Webhook secret is not configured')
    raw=await request.body()
    if len(raw)>100_000:raise HTTPException(413,'Webhook payload too large')
    expected=hmac.new(webhook_secret.encode(),raw,hashlib.sha256).hexdigest()
    if not x_razorpay_signature or not secrets.compare_digest(expected,x_razorpay_signature):raise HTTPException(403,'Webhook authentication failed')
    try:payload=json.loads(raw)
    except ValueError:raise HTTPException(400,'Invalid JSON')
    event_id=x_razorpay_event_id or hashlib.sha256(raw).hexdigest()
    existing=db.scalar(select(WebhookEvent).where(WebhookEvent.event_id==event_id))
    if existing:return {'received':True,'duplicate':True}
    event=str(payload.get('event',''))
    if event!='payment.captured':
        db.add(WebhookEvent(event_id=event_id,event_name=event));db.commit()
        return {'received':True,'processed':False}
    payment=payload.get('payload',{}).get('payment',{}).get('entity',{})
    pay_id=payment.get('id');gateway_order_id=payment.get('order_id')
    order=db.scalar(select(CommerceOrder).where(CommerceOrder.gateway_order_id==gateway_order_id))
    if not order or not pay_id:raise HTTPException(404,'Order or payment not recognized')
    status=confirm_paid_order(db,order,pay_id,key,secret)
    db.add(WebhookEvent(event_id=event_id,event_name=event));db.commit()
    return {'received':True,'processed':True,'status':status}

@router.get('/orders')
def merchant_orders(request:Request,db:Db):
    user,_=resolve_user(request,db)
    items=db.scalars(select(CommerceOrder).where(CommerceOrder.user_id==user.id).order_by(CommerceOrder.created_at.desc())).all()
    return {'orders':[{'id':o.id,'status':o.status,'total_inr':o.total_inr,'shipping_inr':o.shipping_inr,'lines':o.lines,'created_at':o.created_at.isoformat()} for o in items]}

@router.get('/delivery/quote')
def shiprocket_quote(pickup_pincode:str=Query(pattern=r'^\d{6}$'),delivery_pincode:str=Query(pattern=r'^\d{6}$'),weight_kg:float=Query(0.5,gt=0,le=30)):
    # Not activated without an explicit operator opt-in and licensed API credentials.
    token=os.getenv('SHIPROCKET_API_TOKEN','')
    if os.getenv('ENABLE_SHIPROCKET_QUOTES')!='1' or not token:
        raise HTTPException(503,'Courier integration is disabled; delivery price and availability are not confirmed')
    try:
        with httpx.Client(timeout=12) as client:
            resp=client.get('https://apiv2.shiprocket.in/v1/external/courier/serviceability/',headers={'Authorization':f'Bearer {token}'},params={'pickup_postcode':pickup_pincode,'delivery_postcode':delivery_pincode,'weight':weight_kg,'cod':0})
            resp.raise_for_status();result=resp.json()
    except (httpx.HTTPError,ValueError) as exc:
        raise HTTPException(503,'Courier provider unavailable') from exc
    options=result.get('data',{}).get('available_courier_companies',[]) if isinstance(result,dict) else []
    if not isinstance(options,list):options=[]
    return {'provider':'Shiprocket','available':bool(options),'shipping_options':[{'courier_name':r.get('courier_name'),'rate_inr':r.get('rate'),'estimated_days':r.get('estimated_delivery_days')} for r in options[:8]],'notice':'Indicative provider quotations only. Shipment booking is not enabled.'}

@router.post('/orders/{order_id}/ship')
def shipment_disabled(order_id:str):
    raise HTTPException(503,'Dispatch requires a verified seller, a real paid order and an explicitly authorized shipping account; production dispatch is disabled')
