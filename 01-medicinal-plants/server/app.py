"""VERDANT ATLAS / standalone medicinal plant marketplace foundation.

All listings, prices, and stock are seeded examples until verified sellers sign up.
No medicinal efficacy or real commerce is implied. GBIF is queried live on demand.
The app uses SQLite by default and PostgreSQL when DATABASE_URL is explicitly provided.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote as url_quote
from typing import Annotated
from .search import category, relevance, suggestions

import httpx
from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, create_engine, func, or_, select, update
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / 'data'
DATA_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_DB = 'sqlite:///' + str(DATA_DIR / 'verdant_atlas.sqlite3')
DATABASE_URL = os.getenv('DATABASE_URL', DEFAULT_DB)
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://','postgresql+psycopg://',1)
if DATABASE_URL.startswith('postgresql://'):
    DATABASE_URL = DATABASE_URL.replace('postgresql://','postgresql+psycopg://',1)
engine = create_engine(DATABASE_URL, connect_args={'check_same_thread':False} if DATABASE_URL.startswith('sqlite:') else {}, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class Plant(Base):
    __tablename__='plants'
    id: Mapped[int] = mapped_column(primary_key=True)
    common_name: Mapped[str] = mapped_column(String(120),index=True)
    scientific_name: Mapped[str] = mapped_column(String(180),unique=True)
    vernacular: Mapped[str] = mapped_column(String(250),default='')
    family: Mapped[str] = mapped_column(String(120))
    origin: Mapped[str] = mapped_column(Text)
    habitat: Mapped[str] = mapped_column(Text)
    forest_context: Mapped[str] = mapped_column(Text)
    heritage: Mapped[str] = mapped_column(Text)
    traditional_uses: Mapped[str] = mapped_column(Text)
    precautions: Mapped[str] = mapped_column(Text)
    evidence_note: Mapped[str] = mapped_column(Text)
    growth: Mapped[str] = mapped_column(Text)
    sources: Mapped[list] = mapped_column(JSON,default=list)
    color: Mapped[str] = mapped_column(String(24))
    art: Mapped[str] = mapped_column(String(40))
    listings: Mapped[list['Listing']] = relationship(back_populates='plant')

class Listing(Base):
    __tablename__='listings'
    id: Mapped[int] = mapped_column(primary_key=True)
    plant_id: Mapped[int] = mapped_column(ForeignKey('plants.id'),index=True)
    seller_name: Mapped[str] = mapped_column(String(120))
    city: Mapped[str] = mapped_column(String(100))
    region: Mapped[str] = mapped_column(String(100),index=True)
    unit: Mapped[str] = mapped_column(String(80),default='1 rooted nursery plant')
    price_inr: Mapped[int] = mapped_column(Integer)
    delivery_fee_inr: Mapped[int] = mapped_column(Integer,default=0)
    stock: Mapped[int] = mapped_column(Integer)
    freshness_checked_on: Mapped[str] = mapped_column(String(20),default='Not independently verified')
    is_live_verified: Mapped[bool] = mapped_column(Boolean,default=False)
    plant: Mapped[Plant] = relationship(back_populates='listings')

class User(Base):
    __tablename__='users'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(254),unique=True,index=True)
    salt: Mapped[str] = mapped_column(String(64))
    password_hash: Mapped[str] = mapped_column(String(128))

class SessionRecord(Base):
    __tablename__='user_sessions'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    token_hash: Mapped[str] = mapped_column(String(64),unique=True,index=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class Order(Base):
    __tablename__='orders'
    id: Mapped[str] = mapped_column(String(36),primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    region: Mapped[str] = mapped_column(String(100))
    address: Mapped[str] = mapped_column(String(300))
    subtotal_inr: Mapped[int] = mapped_column(Integer)
    delivery_inr: Mapped[int] = mapped_column(Integer)
    total_inr: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(70),default='DEMO_ONLY_NOT_PAID')
    lines: Mapped[list['OrderLine']] = relationship(back_populates='order')

class OrderLine(Base):
    __tablename__='order_lines'
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey('orders.id'))
    listing_id: Mapped[int] = mapped_column(ForeignKey('listings.id'))
    plant_name: Mapped[str] = mapped_column(String(120))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price_inr: Mapped[int] = mapped_column(Integer)
    delivery_fee_inr: Mapped[int] = mapped_column(Integer)
    order: Mapped[Order] = relationship(back_populates='lines')

class WishlistEntry(Base):
    __tablename__='wishlist_entries'
    __table_args__=(UniqueConstraint('user_id','plant_id',name='uq_wishlist_user_plant'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'),index=True)
    plant_id: Mapped[int] = mapped_column(ForeignKey('plants.id'),index=True)

# Editorial records are intentionally short and documented as educational summaries.
# This is not a medical database; medicinal claims require qualified expert review.
SOURCES = {
    'gbif':{'title':'GBIF species backbone','url':'https://www.gbif.org/','kind':'taxonomy'},
    'powo':{'title':'Kew Plants of the World Online','url':'https://powo.science.kew.org/','kind':'botany'},
    'nmpb':{'title':'National Medicinal Plants Board','url':'https://nmpb.nic.in/','kind':'cultivation'},
    'imppat':{'title':'IMPPAT phytochemical research database','url':'https://cb.imsc.res.in/imppat/','kind':'research'}
}
SEED_PLANTS = [
    ('Tulsi','Ocimum tenuiflorum','తులసి · तुलसी','Lamiaceae','South and Southeast Asia; widely cultivated across India.','Sunlit gardens, courtyards and tropical lowland areas; prefers free-draining soil.','Commonly cultivated near homes; garden occurrence should not be treated as evidence of wild forest origin.','Tulsi has a long role in South Asian cultural and traditional botanical literature.','Leaves feature in traditional household preparations. This record does not establish effectiveness for any disease.','Do not substitute preparations for prescribed treatment; product safety and interactions vary.','Ethnobotanical description; no product-specific clinical efficacy claim.','Warm climate · morning light · moderate water','#D7E3B4','tulsi'),
    ('Neem','Azadirachta indica','వేప · नीम','Meliaceae','Native to the Indian subcontinent and cultivated in many tropical regions.','Warm tropical and subtropical dry areas; tolerates seasonally dry conditions.','Common in dry deciduous landscapes and planted settlements; local occurrence depends on region.','Neem appears across centuries of agricultural, household and traditional literature.','Leaves, seeds and other parts have distinct historical applications; they are not interchangeable.','Neem oils and extracts may be harmful if swallowed, especially for children; do not self-medicate.','Safety and clinical evidence vary by preparation; avoid implying proven cures.','Full sun · well-drained soil · drought tolerant','#D7DFB3','neem'),
    ('Aloe vera','Aloe vera','కలబంద · घृतकुमारी','Asphodelaceae','Widely cultivated; its historical native range is discussed in botanical literature.','Warm, dry conditions; porous soil; sensitive to waterlogging.','Mostly grown in containers, gardens, and cultivated arid landscapes.','Aloe appears in several historical traditions of plant-based skin care.','The leaf gel has historically been applied to skin; safety depends on processing and formulation.','Oral aloe latex products can be unsafe; discuss use with a qualified professional.','Traditional use differs from approval of any particular preparation.','Bright indirect light · infrequent water','#E8D9B5','aloe'),
    ('Ashwagandha','Withania somnifera','అశ్వగంధ · अश्वगंधा','Solanaceae','Recorded across dry regions of Africa, Asia and Mediterranean areas.','Dry, well-drained soils in warm semi-arid settings.','Can occur in open, disturbed dry habitats; distribution needs local taxonomic verification.','Frequently discussed in the Indian Ayurveda literary tradition.','Roots appear in traditional formulations; health outcomes depend on specific interventions and evidence.','Can interact with medications and may be unsuitable during pregnancy or certain conditions.','Clinical evidence is variable; this catalog offers no treatment recommendations.','Dry soil · full sun · light irrigation','#E2D2B8','ashwagandha'),
    ('Brahmi','Bacopa monnieri','బ్రాహ్మి · ब्राह्मी','Plantaginaceae','Occurs in wet tropical and subtropical habitats in many regions.','Wetlands, marsh margins and other moist lowland sites.','Found in damp settings, not exclusively inside forests; wild harvesting may harm habitats.','Has a history in South Asian traditional botanical texts.','Historically discussed in traditional formulations; not proof of cognitive or medical benefit.','Identification matters: the vernacular name Brahmi can refer to different species.','No plant or preparation is represented as a clinically proven medicine.','Moist soil · partial sun · regular water','#C9DBCB','brahmi'),
    ('Amla','Phyllanthus emblica','ఉసిరి · आँवला','Phyllanthaceae','Tropical and subtropical Asia; planted across India.','Seasonally dry forests and cultivated orchards, with significant regional variation.','Associated with diverse deciduous habitats and plantation cultivation.','Fruit use is recorded in food, cultural and traditional botanical histories.','Fruits are eaten and used in traditional preparations; nutrition is different from therapeutic efficacy.','Check preparation ingredients and individual dietary tolerances.','Food use is documented; medical benefits are not asserted by this listing.','Full sun · warm climate · seasonal irrigation','#E3DDAF','amla'),
    ('Lemongrass','Cymbopogon citratus','నిమ్మగడ్డి · लेमन ग्रास','Poaceae','Cultivated extensively in tropical and subtropical regions.','Warm, bright, moist but drained field and container soils.','Primarily grown in cultivated herb gardens and farms.','Known in culinary and aromatic traditions in several regions.','Leaves are used as a culinary herb and aromatic infusion.','Essential oil is concentrated and requires appropriate handling; do not ingest undiluted oils.','Culinary uses should not be confused with medical efficacy.','Full sun · regular water · harvestable leaves','#D7DFA6','grass'),
    ('Mint','Mentha spicata','పుదీనా · पुदीना','Lamiaceae','Cultivated widely, with complex Mentha taxonomy and regional distributions.','Gardens, irrigated beds and other temperate to warm moist sites.','Commonly cultivated; naturalized populations may occur locally.','Mint has a long history in cooking and aromatic plant use.','Leaves are popular in food and beverages; botanical identity matters.','Essential oils and highly concentrated preparations are not equivalent to culinary leaf use.','Primarily culinary heritage; no treatment claims are made.','Partial sun · moist soil · spreading roots','#D0D9CA','mint'),
]
REGIONS = ['Andhra Pradesh','Tamil Nadu','Telangana','Karnataka','Kerala','Maharashtra']
CITIES = ['Ongole','Chennai','Hyderabad','Bengaluru','Kochi','Pune']


def seed():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(func.count(Plant.id))): return
        for i, p in enumerate(SEED_PLANTS):
            plant=Plant(common_name=p[0],scientific_name=p[1],vernacular=p[2],family=p[3],origin=p[4],habitat=p[5],forest_context=p[6],heritage=p[7],traditional_uses=p[8],precautions=p[9],evidence_note=p[10],growth=p[11],color=p[12],art=p[13],sources=[SOURCES[x] for x in ('gbif','powo','nmpb')])
            db.add(plant)
            db.flush()
            for j in range(3):
                region=REGIONS[(i+j*2)%len(REGIONS)]
                idx=REGIONS.index(region)
                price=49+(i*13)%66 + j*19 + idx*4
                db.add(Listing(plant_id=plant.id,seller_name=f'Demo nursery {i+1:02d}',city=CITIES[idx],region=region,price_inr=price,delivery_fee_inr=20+idx*3,stock=5+(i+j)%15,unit='1 rooted plant / nursery pot',is_live_verified=False))
        db.commit()
seed()

app=FastAPI(title='Verdant Atlas — Medicinal Plants Store',version='2.1.0',description='Botanical reference and local DEMO marketplace; no live payments or sellers')
app.mount('/assets',StaticFiles(directory=ROOT/'web'/'assets'),name='assets')

def session():
    with SessionLocal() as db:
        yield db

Db = Annotated[Session, Depends(session)]

def hash_password(password:str,salt:str)->str:
    return hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),240_000).hex()

def token_hash(raw:str)->str:
    return hashlib.sha256(raw.encode()).hexdigest()

def user_dict(user:User): return {'id':user.id,'name':user.name,'email':user.email}

def resolve_user(request:Request,db:Session,csrf_required:bool=False):
    raw=request.cookies.get('verdant_session')
    if not raw: raise HTTPException(401,'Sign in to continue')
    rec=db.scalar(select(SessionRecord).where(SessionRecord.token_hash==token_hash(raw)))
    now=datetime.now(timezone.utc)
    if not rec or rec.expires_at.replace(tzinfo=timezone.utc)<now: raise HTTPException(401,'Session expired; sign in again')
    if csrf_required and not secrets.compare_digest(request.headers.get('x-csrf-token',''),rec.csrf_token):
        raise HTTPException(403,'Missing or invalid CSRF token')
    user=db.get(User,rec.user_id)
    if not user: raise HTTPException(401,'Account unavailable')
    return user,rec

class Signup(BaseModel):
    name:str=Field(min_length=2,max_length=100)
    email:EmailStr
    password:str=Field(min_length=10,max_length=200)
class Login(BaseModel):
    email:EmailStr
    password:str

def create_login(response:Response,db:Session,user:User):
    raw=secrets.token_urlsafe(40)
    csrf=secrets.token_urlsafe(24)
    db.add(SessionRecord(user_id=user.id,token_hash=token_hash(raw),csrf_token=csrf,expires_at=datetime.now(timezone.utc)+timedelta(days=7)))
    db.commit()
    response.set_cookie('verdant_session',raw,httponly=True,samesite='lax',secure=os.getenv('COOKIE_SECURE','0')=='1',max_age=604800,path='/')
    return {'user':user_dict(user),'csrf':csrf}

@app.post('/api/auth/register',status_code=201)
def register(data:Signup,response:Response,db:Db):
    email=str(data.email).lower()
    if db.scalar(select(User).where(User.email==email)): raise HTTPException(409,'This email has an account')
    salt=secrets.token_hex(16)
    user=User(name=data.name.strip(),email=email,salt=salt,password_hash=hash_password(data.password,salt))
    db.add(user);db.commit();db.refresh(user)
    return create_login(response,db,user)

@app.post('/api/auth/login')
def login(data:Login,response:Response,db:Db):
    user=db.scalar(select(User).where(User.email==str(data.email).lower()))
    check=hash_password(data.password,user.salt if user else '00'*16)
    if not user or not secrets.compare_digest(check,user.password_hash): raise HTTPException(401,'Invalid credentials')
    return create_login(response,db,user)

@app.get('/api/auth/me')
def me(request:Request,db:Db):
    user,rec=resolve_user(request,db)
    return {'user':user_dict(user),'csrf':rec.csrf_token}

@app.post('/api/auth/logout')
def logout(request:Request,response:Response,db:Db):
    _,rec=resolve_user(request,db,csrf_required=True)
    db.delete(rec);db.commit();response.delete_cookie('verdant_session',path='/')
    return {'ok':True}


# Species-identified *real photographs* on Wikimedia Commons. Source pages include
# image-specific copyright/author information. No image-generation assets are used.
# These are external URLs: the browser needs an internet connection to render them.
PHOTO_LIBRARY = {
    'tulsi': ('Ocimum tenuiflorum plant.jpg', 'Krisnendu Paul', 'CC BY-SA 4.0', 'https://powo.science.kew.org/taxon/453130-1'),
    'neem': ('Azadirachta indica, Neem.jpg', 'Varinder Naturaphile', 'CC BY-SA 4.0', 'https://powo.science.kew.org/taxon/1213180-2'),
    'aloe': ('Aloe Vera growing plant.jpg', 'Agambire Sylvanus', 'CC0 1.0', 'https://powo.science.kew.org/taxon/530017-1'),
    'ashwagandha': ('An image of Withania somnifera.JPG', 'Thamizhpparithi Maari', 'CC BY-SA 3.0', 'https://powo.science.kew.org/taxon/821709-1'),
    'brahmi': ('Bacopa monnieri.jpg', 'Vinayaraj', 'CC BY-SA 3.0', 'https://powo.science.kew.org/taxon/1072674-2'),
    'amla': ('Phyllanthus emblica (Indian Gooseberry).jpg', 'Haneeshkm', 'CC BY-SA 4.0', 'https://powo.science.kew.org/taxon/353838-1'),
    'grass': ('Cymbopogon citratus.jpg', 'Nativeplants garden', 'CC BY-SA 4.0', 'https://powo.science.kew.org/taxon/396896-1'),
    'mint': ('Mentha spicata.jpg', 'Schumi4ever', 'CC BY-SA 4.0', 'https://powo.science.kew.org/taxon/451162-1'),
}
PHOTO_LICENSES = {
    'CC BY-SA 4.0': 'https://creativecommons.org/licenses/by-sa/4.0/',
    'CC BY-SA 3.0': 'https://creativecommons.org/licenses/by-sa/3.0/',
    'CC0 1.0': 'https://creativecommons.org/publicdomain/zero/1.0/',
}
FACT_SHEETS = {
    'tulsi': {
        'overview': 'An aromatic, branching basil with opposite leaves and small flower spikes. This is holy basil (Ocimum tenuiflorum), not the commonly sold sweet basil (Ocimum basilicum).',
        'where_grown': 'Native across parts of tropical and subtropical Asia; widely cultivated in home gardens, courtyards and temple grounds. Its occurrence in a garden does not prove a wild forest origin.',
        'heritage': 'Tulsi has a long documented cultural importance in South Asia, particularly in Hindu traditions, and appears in traditional herbal literature. Dates for the first human use cannot be established from this listing.',
        'real_use': 'The aromatic leaves are used in household infusions and traditional preparations. These uses describe culture and consumption, not clinically established prevention or treatment.',
    },
    'neem': {
        'overview': 'A tropical tree with compound leaves, white fragrant flowers and oval fruits; scientific name Azadirachta indica. A garden sapling should be distinguished from processed neem oil or leaf extracts.',
        'where_grown': 'Kew records a native range around Assam to Indochina. The species is now widely planted across tropical and subtropical regions and often grows in dry, warm landscapes.',
        'heritage': 'Neem has a long place in South Asian farming, household practices and traditional botanical writing. Documented historical applications include plant protection and materials from different tree parts.',
        'real_use': 'Neem-derived compounds, including azadirachtin, have been studied for insect-related applications. This does not make concentrated neem products safe to swallow; neem oil can be toxic.',
    },
    'aloe': {
        'overview': 'A succulent with thick, fleshy leaves, serrated leaf margins and water-storage tissue. The clear inner gel and yellow latex are chemically different materials.',
        'where_grown': 'Aloe vera is cultivated across warm climates. It performs best in bright light and very well-drained substrates; persistent wet soil can damage the roots.',
        'heritage': 'Aloe appears in historical material about cosmetic and topical plant preparations, but there is no single verified date for its first use.',
        'real_use': 'Leaf gel is used in commercial skin-care formulations. Oral aloe latex has important safety risks and should not be marketed as an everyday remedy.',
    },
    'ashwagandha': {
        'overview': 'Withania somnifera is a small Solanaceae shrub producing small flowers and orange-red berries within papery calyces. Common names should not replace scientific identification.',
        'where_grown': 'Found in various dry and semi-arid regions of Africa and Eurasia. Suitable cultivation generally requires warm conditions and well-drained soil.',
        'heritage': 'The plant has a long history in Ayurveda and related traditions. Root use is mentioned in historical preparations; exact first-use dates are not supported here.',
        'real_use': 'Some clinical studies examine standardized ashwagandha preparations, but results vary. It is not appropriate during pregnancy and may interact with medications.',
    },
    'brahmi': {
        'overview': 'Bacopa monnieri is a low-growing, creeping, fleshy-leaved wetland herb with small pale flowers. The common name “Brahmi” is also used for other species in some places.',
        'where_grown': 'Occurs in tropical and subtropical wet environments, including marsh edges and moist ground. It is not exclusively a woodland plant.',
        'heritage': 'Bacopa has a documented place in South Asian traditional literature. Correct identification is particularly important because the same vernacular name can identify different plants.',
        'real_use': 'It appears in traditional preparations and modern studies of plant extracts; this nursery listing makes no claim of proven cognitive or therapeutic outcomes.',
    },
    'amla': {
        'overview': 'Phyllanthus emblica is a deciduous tree producing round, typically greenish-yellow, sour fruits commonly known as Indian gooseberries.',
        'where_grown': 'Native to parts of tropical and subtropical Asia and grown in Indian orchards and home landscapes. Its habitats include seasonally dry wooded areas as well as cultivation.',
        'heritage': 'Amla fruit has a substantial history in South Asian foods and traditional preparations. The exact beginning of use is not recoverable from modern taxonomy records.',
        'real_use': 'The fruit is eaten fresh or preserved and is used as a food ingredient. Nutritional value does not establish treatment efficacy for particular diseases.',
    },
    'grass': {
        'overview': 'Cymbopogon citratus is a densely tufted grass with long, narrow, lemon-scented leaves. It differs from unrelated plants also called lemon grass.',
        'where_grown': 'Extensively cultivated in tropical climates in sunny, warm, well-drained soils. Usually found in cultivated plots rather than presented as a native forest tree.',
        'heritage': 'Lemongrass has a history of culinary and aromatic use in many Asian food cultures; a single origin date would be misleading.',
        'real_use': 'The leaves are used to flavor food and aromatic infusions. Concentrated essential oils require separate safety assessment and are not equivalent to edible leaves.',
    },
    'mint': {
        'overview': 'Mentha spicata, spearmint, is a fragrant perennial mint with opposite leaves and spreading underground stems; many culinary mints belong to other species or hybrids.',
        'where_grown': 'Cultivated widely in garden beds and irrigated fields. It grows vigorously where the soil remains moist, and its roots can spread beyond planting containers.',
        'heritage': 'Spearmint has long culinary and aromatic traditions across many regions. Local vernacular names may refer to multiple Mentha species.',
        'real_use': 'Fresh leaves are used in cooking, drinks and food garnish. Highly concentrated essential oils are not interchangeable with normal food portions.',
    },
}

def photo_record(art: str):
    filename, author, license_name, scientific_url = PHOTO_LIBRARY[art]
    slug = url_quote(filename, safe='')
    local_photo = ROOT / 'web' / 'assets' / 'photographs' / f'{art}.jpg'
    return {
        'image_url': f'/assets/photographs/{art}.jpg' if local_photo.exists() else f'https://commons.wikimedia.org/wiki/Special:FilePath/{slug}?width=960',
        'photo_page': f'https://commons.wikimedia.org/wiki/File:{slug}',
        'photographer': author,
        'license': license_name,
        'license_url': PHOTO_LICENSES[license_name],
        'scientific_source': scientific_url,
        'photo_kind': 'real_species_photograph',
        'image_verified_downloaded': local_photo.exists(),
    }

def serialized_plant(plant:Plant,listings:list[Listing]|None=None):
    result={c:getattr(plant,c) for c in ('id','common_name','scientific_name','vernacular','family','origin','habitat','forest_context','heritage','traditional_uses','precautions','evidence_note','growth','sources','color','art')}
    result['photo'] = photo_record(plant.art)
    result['fact_sheet'] = FACT_SHEETS.get(plant.art, {})
    result['sources'] = list(result.get('sources') or []) + [{'title':'Kew · species record', 'url':result['photo']['scientific_source'], 'kind':'taxonomy'}]
    if listings is not None:
        result['listings']=[serialized_listing(l) for l in listings]
    return result

def serialized_listing(l:Listing):
    return {k:getattr(l,k) for k in ('id','plant_id','seller_name','city','region','unit','price_inr','delivery_fee_inr','stock','freshness_checked_on','is_live_verified')}

@app.get('/api/health')
def health():
    return {'status':'ok','storage':'postgresql' if engine.dialect.name=='postgresql' else 'sqlite_local','catalog':'seeded_demo','checkout':'demo_only','payments':'not_connected','seller_verification':'not_connected','botanical_api':'GBIF_on_demand','photo_source':'Wikimedia Commons linked original photographs','public_deployment':'not_configured'}

@app.get('/api/regions')
def regions():
    return {'regions':REGIONS,'note':'Region selection filters seed listings; shipping availability is illustrative.'}

def catalog_products(db:Session):
    plant_rows=db.scalars(select(Plant).order_by(Plant.id)).all()
    listing_rows=db.scalars(select(Listing)).all()
    by_plant={}
    for row in listing_rows:by_plant.setdefault(row.plant_id,[]).append(row)
    records=[]
    # Verified sellers are tracked separately from unverified seed/demo listings.
    # Lazy import avoids circular imports while the application's metadata loads.
    from .commerce import LiveOffer, Merchant
    active_merchant_offers=db.execute(select(LiveOffer,Merchant).join(Merchant,LiveOffer.merchant_id==Merchant.id).where(LiveOffer.status=='APPROVED',Merchant.status=='VERIFIED',LiveOffer.stock>LiveOffer.reserved)).all()
    verified_by_plant={}
    for live_offer,merchant in active_merchant_offers:
        verified_by_plant.setdefault(live_offer.plant_id,[]).append((live_offer,merchant))
    for plant in plant_rows:
        lst=by_plant.get(plant.id,[])
        record=serialized_plant(plant)
        record.update({
            'category':category(plant.common_name),
            'verified_offer_count':len(verified_by_plant.get(plant.id,[])),
            'verified_min_price_inr':min((offer.price_inr for offer,merchant in verified_by_plant.get(plant.id,[])),default=None),
            'listing_count':len(lst),
            'min_price_inr':min((l.price_inr for l in lst if l.stock>0),default=None),
            'available_stock':sum(max(0,l.stock) for l in lst),
            'regions':sorted({l.region for l in lst}),
            'best_listing_id':min((l for l in lst if l.stock>0),key=lambda l:l.price_inr).id if any(l.stock>0 for l in lst) else None,
        })
        records.append((record,lst))
    return records

@app.get('/api/catalog')
@app.get('/api/plants')
def plants(db:Db,q:str=Query('',max_length=90),region:str='',category_filter:str=Query('',alias='category'),
           sort:str='relevance',min_price:int|None=Query(None,ge=0),max_price:int|None=Query(None,ge=0),
           in_stock:bool=False,limit:int=Query(24,ge=1,le=100),offset:int=Query(0,ge=0)):
    if max_price is not None and min_price is not None and max_price<min_price:
        raise HTTPException(422,'Maximum price must not be less than minimum price')
    results=[]
    for record,listings in catalog_products(db):
        eligible=[l for l in listings if (not region or l.region==region) and (not in_stock or l.stock>0)]
        if (region or in_stock) and not eligible:continue
        if category_filter and record['category']!=category_filter:continue
        record['min_price_inr']=min((l.price_inr for l in eligible if l.stock>0),default=None)
        record['available_stock']=sum(max(0,l.stock) for l in eligible)
        record['best_listing_id']=min((l for l in eligible if l.stock>0),key=lambda l:l.price_inr).id if any(l.stock>0 for l in eligible) else None
        record['listing_count']=len(eligible)
        record['regions']=sorted({l.region for l in eligible})
        if min_price is not None and (record['min_price_inr'] is None or record['min_price_inr']<min_price):continue
        if max_price is not None and (record['min_price_inr'] is None or record['min_price_inr']>max_price):continue
        score=relevance(record,q)
        if q and score<=0:continue
        record['relevance_score']=score
        results.append(record)
    if sort in ('price_asc','price_desc'):
        results.sort(key=lambda x:(x['min_price_inr'] is None, x['min_price_inr'] if sort=='price_asc' else -(x['min_price_inr'] or 0),x['id']))
    elif sort=='name':results.sort(key=lambda x:(x['common_name'].casefold(),x['id']))
    elif sort=='stock':results.sort(key=lambda x:(-x['available_stock'],x['id']))
    elif sort in ('popular','relevance'):
        results.sort(key=lambda x:(-x['relevance_score'],x['id']))
    else:raise HTTPException(422,'Unsupported sort')
    categories={}
    for x in results: categories[x['category']]=categories.get(x['category'],0)+1
    return {'items':results[offset:offset+limit],'total':len(results),'categories':categories,
            'page':offset//limit+1,'limit':limit,'query':q,
            'catalog_status':'DEMO_PRICES_AND_STOCK_NOT_LIVE'}

@app.get('/api/catalog/facets')
def facets(db:Db):
    records=catalog_products(db)
    categories={}
    for p,_ in records:categories[p['category']]=categories.get(p['category'],0)+1
    return {'categories':categories,'regions':REGIONS,'price_unit':'INR',
            'status':'UNVERIFIED_SEED_LISTINGS'}

@app.get('/api/search/suggest')
def suggest(db:Db,q:str=Query(min_length=1,max_length=90)):
    return {'suggestions':suggestions([p for p,_ in catalog_products(db)],q),'query':q}

@app.get('/api/plants/{plant_id}')
def plant_detail(plant_id:int,db:Db,region:str=''):
    plant=db.get(Plant,plant_id)
    if not plant: raise HTTPException(404,'Plant not found')
    li=db.scalars(select(Listing).where(Listing.plant_id==plant_id,*([Listing.region==region] if region else [])).order_by(Listing.price_inr)).all()
    return {'plant':{**serialized_plant(plant,li),'category':category(plant.common_name)},'listing_status':'SEED_DATA_NOT_LIVE_NURSERY_STOCK'}

@app.get('/api/plants/{plant_id}/taxonomy')
async def plant_taxonomy(plant_id:int,db:Db):
    plant=db.get(Plant,plant_id)
    if not plant:raise HTTPException(404,'Plant not found')
    try:
        async with httpx.AsyncClient(timeout=12,headers={'User-Agent':'VerdantAtlas/1.0 (educational botanical explorer)'}) as client:
            response=await client.get('https://api.gbif.org/v1/species/match',params={'name':plant.scientific_name,'strict':'true'})
            response.raise_for_status()
            payload=response.json()
    except (httpx.HTTPError,ValueError):
        raise HTTPException(503,'Live taxonomy unavailable; cached catalog record remains accessible')
    fields=('usageKey','scientificName','canonicalName','rank','status','confidence','matchType','kingdom','phylum','class','order','family','genus','species')
    return {'source':'GBIF species match live lookup','retrieved_at':datetime.now(timezone.utc).isoformat(),'data':{k:payload.get(k) for k in fields if k in payload},'reference':'https://techdocs.gbif.org/en/openapi/v1/species','note':'Taxonomic matching does not verify medical uses or nursery origin.'}

class LineInput(BaseModel):
    listing_id:int=Field(gt=0)
    quantity:int=Field(ge=1,le=20)
class CheckoutInput(BaseModel):
    region:str=Field(min_length=2,max_length=100)
    address:str=Field(min_length=8,max_length=300)
    lines:list[LineInput]=Field(min_length=1,max_length=20)

class QuoteRequest(BaseModel):
    region:str=Field(min_length=2,max_length=100)
    lines:list[LineInput]=Field(min_length=1,max_length=20)

@app.post('/api/checkout/quote')
def quote(data:QuoteRequest,db:Db):
    combined={}
    for line in data.lines:combined[line.listing_id]=combined.get(line.listing_id,0)+line.quantity
    if any(v>20 for v in combined.values()):raise HTTPException(422,'Maximum 20 per listing')
    subtotal=delivery=0;rows=[]
    for listing_id,qty in combined.items():
        listing=db.get(Listing,listing_id)
        if not listing or listing.region!=data.region:raise HTTPException(422,'Listing does not serve requested region')
        if listing.stock<qty:raise HTTPException(409,'Insufficient sample inventory')
        subtotal+=listing.price_inr*qty;delivery+=listing.delivery_fee_inr
        rows.append({'listing_id':listing.id,'quantity':qty,'unit_price_inr':listing.price_inr,'delivery_fee_inr':listing.delivery_fee_inr})
    return {'subtotal_inr':subtotal,'delivery_inr':delivery,'total_inr':subtotal+delivery,
            'lines':rows,'status':'DEMO_QUOTE_NOT_A_REAL_OFFER','note':'Quote recalculated on the server; no reservation or payment.'}

@app.get('/api/wishlist')
def get_wishlist(request:Request,db:Db):
    user,_=resolve_user(request,db)
    ids=db.scalars(select(WishlistEntry.plant_id).where(WishlistEntry.user_id==user.id)).all()
    return {'plant_ids':ids}

@app.post('/api/wishlist/{plant_id}')
def add_wishlist(plant_id:int,request:Request,db:Db):
    user,_=resolve_user(request,db,csrf_required=True)
    if not db.get(Plant,plant_id):raise HTTPException(404,'Plant not found')
    existing=db.scalar(select(WishlistEntry).where(WishlistEntry.user_id==user.id,WishlistEntry.plant_id==plant_id))
    if not existing:db.add(WishlistEntry(user_id=user.id,plant_id=plant_id));db.commit()
    return {'saved':True,'plant_id':plant_id}

@app.delete('/api/wishlist/{plant_id}')
def remove_wishlist(plant_id:int,request:Request,db:Db):
    user,_=resolve_user(request,db,csrf_required=True)
    entry=db.scalar(select(WishlistEntry).where(WishlistEntry.user_id==user.id,WishlistEntry.plant_id==plant_id))
    if entry:db.delete(entry);db.commit()
    return {'saved':False,'plant_id':plant_id}

@app.post('/api/orders/demo',status_code=201)
def create_demo_order(data:CheckoutInput,request:Request,db:Db):
    user,_=resolve_user(request,db,csrf_required=True)
    qty_by_listing={}
    for line in data.lines: qty_by_listing[line.listing_id]=qty_by_listing.get(line.listing_id,0)+line.quantity
    if any(q>20 for q in qty_by_listing.values()):raise HTTPException(422,'At most 20 units per listing')
    try:
        # Each UPDATE is guarded by stock >= quantity; transaction rolls back on any conflict.
        with db.begin_nested():
            lines=[];subtotal=0;delivery=0
            for listing_id,quantity in qty_by_listing.items():
                listing=db.get(Listing,listing_id)
                if not listing or listing.region!=data.region:raise HTTPException(422,'Listing does not ship to the selected demo region')
                changed=db.execute(update(Listing).where(Listing.id==listing_id,Listing.stock>=quantity).values(stock=Listing.stock-quantity))
                if changed.rowcount!=1:raise HTTPException(409,'Insufficient demo inventory; refresh the listing')
                name=db.get(Plant,listing.plant_id).common_name
                lines.append({'listing_id':listing_id,'plant_name':name,'quantity':quantity,'unit_price_inr':listing.price_inr,'delivery_fee_inr':listing.delivery_fee_inr})
                subtotal+=quantity*listing.price_inr
                delivery+=listing.delivery_fee_inr
            total=subtotal+delivery
            order=Order(id=str(uuid.uuid4()),user_id=user.id,region=data.region,address=data.address,subtotal_inr=subtotal,delivery_inr=delivery,total_inr=total,status='DEMO_ONLY_NOT_PAID_OR_SHIPPED')
            db.add(order);db.flush()
            for line in lines:db.add(OrderLine(order_id=order.id,**line))
        db.commit()
        return {'order_id':order.id,'status':order.status,'subtotal_inr':subtotal,'delivery_inr':delivery,'total_inr':total,'lines':lines,'notice':'This is a local demonstration record. No seller was contacted, no money charged and no shipment booked.'}
    except HTTPException:
        db.rollback();raise

@app.get('/api/orders')
def orders(request:Request,db:Db):
    user,_=resolve_user(request,db)
    records=db.scalars(select(Order).where(Order.user_id==user.id).order_by(Order.created_at.desc()).limit(25)).all()
    return {'orders':[{'id':o.id,'created_at':o.created_at.isoformat(),'status':o.status,'total_inr':o.total_inr,'region':o.region,'lines':[{'plant_name':l.plant_name,'quantity':l.quantity,'unit_price_inr':l.unit_price_inr} for l in o.lines]} for o in records]}

@app.get('/api/sources')
def sources():
    return {'sources':list(SOURCES.values()),'note':'Citations identify useful reference databases; narrative summaries are editorial starter content requiring specialist review before commercial publishing.'}

@app.get('/products/{plant_id}')
def product_route(plant_id:int):
    return FileResponse(ROOT/'web'/'index.html')

@app.get('/')
def home():return FileResponse(ROOT/'web'/'index.html')

@app.get('/favicon.ico')
def favicon():return Response(status_code=204)

# The merchant-commerce extension is deliberately loaded after the base models.
# It never makes a network request on import and cannot activate production payments.
from . import commerce as _merchant_commerce
app.include_router(_merchant_commerce.router)

@app.get('/owner')
def owner_review_screen(): return FileResponse(ROOT/'web'/'owner.html')
