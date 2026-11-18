'use strict';
// Verdant Atlas — dark, photograph-led botanical store. All plant images
// resolve to credited photographs of the identified species on Commons.
// No production seller, payment, or shipment is represented as connected.
const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, x => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));
const money = value => '₹' + Number(value || 0).toLocaleString('en-IN');
const state = {activeOffer:null, verifiedOffers:[], products:[], regions:[], plant:null, cart:loadCart(), user:null, csrf:null, saved:new Set(), mode:'login', category:'', lookupSeq:0, suggestionsSeq:0, searchDebounce:0};
let toastTimer;
function loadCart(){try{const raw=JSON.parse(localStorage.getItem('verdant_cart') || '[]');return Array.isArray(raw)?raw.filter(x=>Number.isInteger(x.id)&&x.id>0&&Number.isInteger(x.quantity)&&x.quantity>=1&&x.quantity<=20):[]}catch{return []}}
function saveCart(){try{localStorage.setItem('verdant_cart',JSON.stringify(state.cart))}catch{}updateCartCount()}
function updateCartCount(){$('#cart-count').textContent=String(state.cart.reduce((sum,x)=>sum+x.quantity,0))}
function toast(message){const target=$('#toast');target.textContent=message;target.classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>target.classList.remove('show'),3400)}
function feedback(selector,message,error=false){const e=$(selector);e.textContent=message;e.className='feedback '+(error?'error':'success')}
async function api(path,options={}){
 const headers={'Accept':'application/json'};
 if(options.body!==undefined){headers['Content-Type']='application/json';if(state.csrf)headers['X-CSRF-Token']=state.csrf}
 let response;
 try{response=await fetch(path,{method:options.method||'GET',headers,body:options.body===undefined?undefined:JSON.stringify(options.body),credentials:'same-origin'})}
 catch{throw new Error('The store API is unreachable. Start the local FastAPI server and retry.')}
 const data=await response.json().catch(()=>({}));
 if(!response.ok){const detail=data.detail;throw new Error(typeof detail==='string'?detail:`Request failed (${response.status}).`)}
 return data;
}
function openDrawer(id){closeSuggestions();$('#overlay').hidden=false;$$('.drawer').forEach(drawer=>drawer.hidden=true);$(id).hidden=false;document.body.style.overflow='hidden';$(id).querySelector('[data-close]')?.focus()}
function closeDrawers(){$('#overlay').hidden=true;$$('.drawer').forEach(drawer=>drawer.hidden=true);document.body.style.overflow=''}
function closeSuggestions(){$('#search-suggestions').hidden=true;$('#search-input').setAttribute('aria-expanded','false')}
function chip(label){return `<span>${escapeHTML(label)}</span>`}
function updateActiveFilters(){const labels=[];const query=$('#search-input').value.trim();if(query)labels.push('Search: '+query);if(state.category)labels.push(state.category);if($('#region-filter').value)labels.push($('#region-filter').value);if($('#price-min').value)labels.push('From '+money($('#price-min').value));if($('#price-max').value)labels.push('Under '+money($('#price-max').value));if($('#stock-only').checked)labels.push('In stock');$('#active-filters').innerHTML=labels.map(chip).join('')}
function selectCategory(category){state.category=category;$$('[data-category]').forEach(button=>{const selected=button.dataset.category===category;button.classList.toggle('selected',selected);button.classList.toggle('active',selected);button.setAttribute('aria-pressed',String(selected))});loadProducts()}
function renderCategories(data){const parent=$('#category-list');parent.innerHTML=`<button data-category="" type="button" class="${!state.category?'selected':''}">All plants <span>${data.total}</span></button>`+Object.entries(data.categories).sort((a,b)=>a[0].localeCompare(b[0])).map(([category,count])=>`<button type="button" data-category="${escapeHTML(category)}" class="${state.category===category?'selected':''}">${escapeHTML(category)} <span>${count}</span></button>`).join('')}
function botanicalPhoto(plant, className='photo-real', lazy=true){
 const photo=plant.photo;
 if(!photo)return '<div class="photo-unavailable">Species photo not available</div>';
 return `<img class="${className}" ${lazy?'loading="lazy"':''} decoding="async" src="${escapeHTML(photo.image_url)}" alt="Real photographic specimen of ${escapeHTML(plant.common_name)} (${escapeHTML(plant.scientific_name)}); source: Wikimedia Commons" referrerpolicy="no-referrer"><span class="photo-unavailable" hidden>Photograph needs an internet connection. <a href="${escapeHTML(photo.photo_page)}" target="_blank" rel="noopener noreferrer">View original ↗</a></span>`;
}
function photographCredit(plant){const photo=plant.photo;if(!photo)return '';
 return `<span class="photo-byline">PHOTO · <a href="${escapeHTML(photo.photo_page)}" target="_blank" rel="noopener noreferrer">${escapeHTML(photo.photographer)}</a> / <a href="${escapeHTML(photo.license_url)}" target="_blank" rel="noopener noreferrer">${escapeHTML(photo.license)}</a></span>`;
}
function productCard(product){
 const price=product.min_price_inr===null?'Unavailable':money(product.min_price_inr);
 const saved=state.saved.has(product.id);
 return `<article class="product-card" data-plant="${product.id}" style="--index:${Math.min(8,product.id)}">
 <div class="product-image"><span class="specimen-tag">SPECIES ${String(product.id).padStart(2,'0')} / REAL PHOTO</span>${botanicalPhoto(product)}<button type="button" class="preview-button" data-view="${product.id}" aria-label="View ${escapeHTML(product.common_name)} details"></button><button type="button" class="save-button ${saved?'saved':''}" data-wish="${product.id}" aria-label="${saved?'Remove':'Save'} ${escapeHTML(product.common_name)}">${saved?'♥':'♡'}</button></div>
 <div class="product-information"><p class="category-caption"><span class="category-dot">●</span> ${escapeHTML(product.category)}</p><h3 class="product-name"><button type="button" data-view="${product.id}">${escapeHTML(product.common_name)}</button></h3><p class="latin-name">${escapeHTML(product.scientific_name)}</p><p class="seller-info">${product.verified_offer_count?`${product.verified_offer_count} independently reviewed nursery offer(s) · `:''}${product.listing_count} sample regional listings</p><div class="price-row"><strong class="price-main">${product.verified_min_price_inr!==null?money(product.verified_min_price_inr):price}</strong><span class="price-caption">${product.verified_min_price_inr!==null?'SELLER PRICE · REVIEWED':'FROM · DEMO'}</span></div>${photographCredit(product)}</div>
 <div class="product-buy"><button type="button" data-view="${product.id}">View species</button><button class="add-button" type="button" data-quick="${product.id}" ${product.best_listing_id===null?'disabled':''}>Add to basket <span>↗</span></button></div>
 </article>`;
}
async function loadProducts(){
 const seq=++state.lookupSeq;
 const params=new URLSearchParams({q:$('#search-input').value.trim(),region:$('#region-filter').value,sort:$('#sort-filter').value,limit:'100'});
 if(state.category)params.set('category',state.category);
 if($('#price-min').value)params.set('min_price',$('#price-min').value);
 if($('#price-max').value)params.set('max_price',$('#price-max').value);
 if($('#stock-only').checked)params.set('in_stock','true');
 $('#plant-grid').innerHTML='<div class="empty-state">Loading the store collection…</div>';$('#catalog-error').hidden=true;updateActiveFilters();
 try{
  const data=await api('/api/catalog?'+params);
  if(seq!==state.lookupSeq)return;
  state.products=data.items;
  $('#result-count').textContent=`${data.total} plant${data.total!==1?'s':''} found`;
  $('#plant-grid').innerHTML=data.items.length?data.items.map(productCard).join(''):'<div class="empty-state"><h3>No plants matched.</h3><p>Try clearing filters, searching another species or choosing a different region.</p><button type="button" class="outline-button" id="empty-reset">Clear filters</button></div>';
 }catch(error){if(seq!==state.lookupSeq)return;$('#result-count').textContent='Unable to load products';$('#plant-grid').innerHTML='';$('#catalog-error').hidden=false;$('#catalog-error').textContent=error.message}
}
async function refreshFacets(){try{const result=await api('/api/catalog/facets');renderCategories({...result,total:Object.values(result.categories).reduce((a,b)=>a+b,0)})}catch(error){toast(error.message)}}
async function suggestSearch(){
 const query=$('#search-input').value.trim(),list=$('#search-suggestions'),seq=++state.suggestionsSeq;
 if(query.length<2){closeSuggestions();return}
 try{const d=await api('/api/search/suggest?q='+encodeURIComponent(query));if(seq!==state.suggestionsSeq)return;
 list.innerHTML=d.suggestions.map(s=>`<button type="button" role="option" data-suggestion="${escapeHTML(s.name)}"><strong>${escapeHTML(s.name)}</strong><small>${escapeHTML(s.scientific_name)}</small></button>`).join('');list.hidden=!d.suggestions.length;$('#search-input').setAttribute('aria-expanded',String(!list.hidden));}
 catch{closeSuggestions()}
}
function detailSections(plant){return `
<section class="fact-sheet"><div class="fact-head"><span>THE SPECIES FILE</span><span>RESEARCH RECORD / ${String(plant.id).padStart(2,'0')}</span></div><p class="fact-summary">${escapeHTML(plant.fact_sheet?.overview||'Botanical record under review.')}</p><dl><div><dt>DOCUMENTED DISTRIBUTION</dt><dd>${escapeHTML(plant.fact_sheet?.where_grown||plant.origin)}</dd></div><div><dt>HISTORICAL CONTEXT</dt><dd>${escapeHTML(plant.fact_sheet?.heritage||plant.heritage)}</dd></div><div><dt>KNOWN USE / EVIDENCE LIMIT</dt><dd>${escapeHTML(plant.fact_sheet?.real_use||plant.traditional_uses)}</dd></div></dl><p class="fact-caution">Educational botanical description — not medical advice or evidence of efficacy.</p></section>
<section class="detail-section"><span class="label">BOTANICAL IDENTITY</span><h3>${escapeHTML(plant.family)}</h3><p>${escapeHTML(plant.vernacular)}</p></section>
<section class="detail-section"><span class="label">HABITAT & REGIONAL DISTRIBUTION</span><h3>Where this plant grows</h3><p>${escapeHTML(plant.origin)}</p><p>${escapeHTML(plant.habitat)}</p><p>${escapeHTML(plant.forest_context)}</p></section>
<section class="detail-section"><span class="label">CULTIVATION</span><h3>Care and growing conditions</h3><p>${escapeHTML(plant.growth)}</p></section>
<section class="detail-section"><span class="label">CULTURE & HISTORY</span><h3>Historical uses</h3><p>${escapeHTML(plant.heritage)}</p><p>${escapeHTML(plant.traditional_uses)}</p></section>
<section class="detail-section"><span class="label">SAFETY / EVIDENCE</span><h3>Understand the research</h3><p>${escapeHTML(plant.evidence_note)}</p><p>${escapeHTML(plant.precautions)}</p><p><strong>Historical use is not evidence that this plant treats a disease.</strong></p></section>
<section class="detail-section"><span class="label">SOURCE VERIFICATION</span><h3>Botanical references</h3><button type="button" class="outline-button wide" id="gbif-btn">Check GBIF species name ↗</button><p id="gbif-result" class="muted"></p>${plant.sources.map(source=>`<p><a href="${escapeHTML(source.url)}" target="_blank" rel="noopener noreferrer" style="text-decoration:underline">${escapeHTML(source.title)} ↗</a></p>`).join('')}</section>`}
async function viewPlant(id){
 try{const region=$('#region-filter').value;const result=await api(`/api/plants/${id}?region=${encodeURIComponent(region)}`);const p=result.plant;state.plant=p;
 $('#detail-content').innerHTML=`<div class="drawer-header"><span>PRODUCT DETAILS / SPECIES ${String(p.id).padStart(2,'0')}</span><button class="close-btn" data-close aria-label="Close product">✕</button></div><div class="drawer-art">${botanicalPhoto(p,'photo-real drawer-real',false)}<div class="drawer-photo-attribution">${photographCredit(p)} <span>SPECIES REFERENCE, NOT THE LISTED PRODUCT</span></div></div><div class="drawer-body"><div class="detail-meta">${escapeHTML(p.category)} / ${escapeHTML(p.family)}</div><h2 id="detail-title">${escapeHTML(p.common_name)}<span class="orange-dot">.</span></h2><p class="muted"><i>${escapeHTML(p.scientific_name)}</i></p><div class="detail-price"><strong>${p.listings.length?money(Math.min(...p.listings.map(l=>l.price_inr))):'Unavailable'}</strong><span>From sample regional nursery inventory</span></div><section class="detail-section"><span class="label">CHOOSE A NURSERY</span><h3>Compare sample sellers & prices</h3><p>These are illustrative listings, not certified sellers or genuine shipping offers.</p>${p.listings.length?p.listings.map(l=>`<div class="listing"><div class="listing-row"><div><h4>${escapeHTML(l.seller_name)}</h4><p>${escapeHTML(l.city)}, ${escapeHTML(l.region)}</p><p>${escapeHTML(l.unit)} · ${l.stock} sample units</p><p>Freshness / seller identity not independently verified</p></div><div><strong>${money(l.price_inr)}</strong><p>+ ${money(l.delivery_fee_inr)} sample shipping</p></div></div><button type="button" data-add="${l.id}" ${!l.stock?'disabled':''}>+ Add to sample basket</button></div>`).join(''):'<p>No listings match this selected region. Choose another region above.</p>'}</section>${detailSections(p)}</div>`;
 openDrawer('#plant-drawer');
    displayVerifiedOffers(p.id);
 }catch(error){toast(error.message)}
}
async function displayVerifiedOffers(plantId){
 const details=$('#detail-content .drawer-body');
 if(!details)return;
 const place=document.createElement('section');place.className='detail-section real-seller-section';
 place.innerHTML='<span class="label">INDEPENDENT VERIFIED SELLERS</span><h3>Approved nursery offers</h3><p>Prices are merchant-managed and subject to reconfirmation. Demo nursery prices elsewhere on this page are not purchasable.</p><p class="muted">Checking verified offers…</p>';
 const sample=details.querySelector('.detail-section');
 if(sample)details.insertBefore(place,sample);
 try{
  const region=$('#region-filter').value;
  const data=await api('/api/commerce/offers?plant_id='+plantId+'&region='+encodeURIComponent(region));
  if(!data.items.length){place.querySelector('p:last-child').textContent='No independently reviewed nursery offers yet. You can browse the botanical facts or request a seller to register.';return;}
  place.querySelector('p:last-child').remove();
  data.items.forEach(offer=>{
   const box=document.createElement('article');box.className='listing verified-listing';
   box.innerHTML=`<div class="listing-row"><div><h4>${escapeHTML(offer.seller_name)} <span class="verified-mark">OWNER REVIEWED</span></h4><p>${escapeHTML(offer.city)}, ${escapeHTML(offer.region)}</p><p>${escapeHTML(offer.unit)} · ${offer.stock} seller-managed units</p><p>Last seller confirmation: ${escapeHTML(offer.seller_confirmed_at||'Not recorded')}</p></div><div><strong>${money(offer.price_inr)}</strong><p>Shipping unconfirmed</p></div></div><button type="button" data-verified-offer="${offer.id}">Review checkout status ↗</button>`;
   place.append(box);
  });
 }catch(error){place.querySelector('p:last-child').textContent=error.message;}
}
async function openSeller(){
 openDrawer('#seller-drawer');
 const guest=$('#seller-guest'),application=$('#seller-application'),portal=$('#seller-portal');
 guest.hidden=!!state.user;application.hidden=true;portal.hidden=true;
 if(!state.user)return;
 try{
  const data=await api('/api/commerce/seller/me');
  if(!data.merchant){application.hidden=false;return;}
  portal.hidden=false;
  const merchant=data.merchant;
  $('#seller-status').innerHTML=`<h3>${escapeHTML(merchant.business_name)}</h3><p>Verification: <strong>${escapeHTML(merchant.status)}</strong></p><p>${escapeHTML(merchant.city)} · ${escapeHTML(merchant.region)} · ${escapeHTML(merchant.pickup_pincode)}</p><p>${escapeHTML(merchant.review_note||'No approval decision yet.')}</p>`;
  $('#seller-offers').innerHTML=data.offers.length?data.offers.map(offer=>`<article class="listing"><h4>${escapeHTML(offer.plant_name)} · ${money(offer.price_inr)}</h4><p>${escapeHTML(offer.unit)} · stock ${offer.stock}</p><p>Review state: ${escapeHTML(offer.status)}. Updates require a new review.</p></article>`).join(''):'<p class="muted">No submitted offers yet.</p>';
 }catch(error){feedback('#seller-feedback',error.message,true)}
}
async function sellerApply(event){event.preventDefault();
 const f=new FormData(event.currentTarget);const data=Object.fromEntries(f.entries());
 try{await api('/api/commerce/seller/apply',{method:'POST',body:data});feedback('#seller-feedback','Seller application submitted for review. Nothing is public yet.');event.currentTarget.reset();await openSeller();}
 catch(error){feedback('#seller-feedback',error.message,true)}
}
async function sellerSubmitOffer(event){event.preventDefault();
 const data=Object.fromEntries(new FormData(event.currentTarget).entries());
 data.plant_id=Number(data.plant_id);data.price_inr=Number(data.price_inr);data.stock=Number(data.stock);data.handling_days=Number(data.handling_days);
 try{await api('/api/commerce/seller/offers',{method:'POST',body:data});feedback('#seller-feedback','Offer saved for independent review; not publicly available yet.');event.currentTarget.reset();await openSeller();}
 catch(error){feedback('#seller-feedback',error.message,true)}
}
async function openVerifiedOffer(offerId){
 if(!state.user){toast('Sign in first to view test checkout options.');openAuth();return;}
 try{
  const result=await api('/api/commerce/offers');const offer=result.items.find(item=>item.id===offerId);
  if(!offer)throw new Error('Offer no longer available');
  state.activeOffer=offer;
  $('#verified-offer-details').innerHTML=`<div class="seller-info-card"><h3>${escapeHTML(offer.plant_name)}</h3><p>${escapeHTML(offer.seller_name)} · ${escapeHTML(offer.region)}</p><p>${escapeHTML(offer.unit)}</p><strong>${money(offer.price_inr)} per unit</strong><p>Price set by seller. Shipping unknown.</p></div>`;
  $('#verified-pay-btn').disabled=true;$('#verified-feedback').textContent='';
  openDrawer('#verified-drawer');
 }catch(error){toast(error.message)}
}
async function verifiedQuote(){
 const offer=state.activeOffer;if(!offer)return;
 const quantity=Number($('#verified-qty').value);
 const body={lines:[{offer_id:offer.id,quantity}],region:offer.region,postal_code:$('#verified-pincode').value,address:$('#verified-address').value.trim()};
 try{
  const d=await api('/api/commerce/checkout/quote',{method:'POST',body});
  feedback('#verified-feedback',`Estimated sandbox subtotal ${money(d.subtotal_inr)}. Delivery is NOT quoted. No live purchase is available.`,false);
  const status=await api('/api/commerce/status');$('#verified-pay-btn').disabled=!status.sandbox_payment_ready;
 }catch(error){$('#verified-pay-btn').disabled=true;feedback('#verified-feedback',error.message,true)}
}
let sandboxCheckoutPromise;
function ensureTestCheckoutSDK(){
 if(window.Razorpay)return Promise.resolve();
 if(!sandboxCheckoutPromise)sandboxCheckoutPromise=new Promise((resolve,reject)=>{
   const script=document.createElement('script');script.src='https://checkout.razorpay.com/v1/checkout.js';
   script.async=true;script.onload=resolve;script.onerror=()=>reject(new Error('Razorpay TEST checkout library could not be loaded'));
   document.head.append(script);
 });
 return sandboxCheckoutPromise;
}
async function verifiedCheckout(event){
 event.preventDefault();if(!state.activeOffer)return;
 const offer=state.activeOffer;
 const body={lines:[{offer_id:offer.id,quantity:Number($('#verified-qty').value)}],region:offer.region,postal_code:$('#verified-pincode').value,address:$('#verified-address').value.trim()};
 try{
  const d=await api('/api/commerce/checkout/create-test-order',{method:'POST',body});
  feedback('#verified-feedback',`Opening Razorpay TEST checkout for ${d.gateway_order_id}. No live funds will be charged.`,false);
  $('#verified-pay-btn').disabled=true;
  await ensureTestCheckoutSDK();
  const modal=new window.Razorpay({
    key:d.key_id,order_id:d.gateway_order_id,amount:d.amount_paise,currency:'INR',
    name:'Verdant Atlas — TEST',description:'Sandbox-only transaction · no live purchase',
    theme:{color:'#5d8063'},
    handler:async function(payment){
      try{
        const answer=await api('/api/commerce/checkout/verify-test-payment',{method:'POST',body:{local_order_id:d.local_order_id,razorpay_order_id:payment.razorpay_order_id,razorpay_payment_id:payment.razorpay_payment_id,razorpay_signature:payment.razorpay_signature}});
        feedback('#verified-feedback',`Test payment ${answer.status} confirmed via provider. NO real shipment has been booked.`);
      }catch(error){feedback('#verified-feedback','Payment needs manual verification: '+error.message,true)}
    },modal:{ondismiss:()=>toast('Test checkout closed without a confirmed transaction.')}
  });
  modal.open();
 }catch(error){feedback('#verified-feedback',error.message,true)}
}

function addListing(listing,plantName){
 if(!listing||!listing.stock)return toast('This nursery listing has no sample stock.');
 if(state.cart.length && state.cart[0].region!==listing.region){if(!confirm('Your basket contains a different delivery region. Clear it and choose this region instead?'))return;state.cart=[]}
 let item=state.cart.find(x=>x.id===listing.id);
 if(item){if(item.quantity>=Math.min(listing.stock,20))return toast('Maximum sample quantity reached.');item.quantity+=1}
 else state.cart.push({id:listing.id,quantity:1,region:listing.region,plant:plantName,seller:listing.seller_name,price:listing.price_inr,shipping:listing.delivery_fee_inr,stock:listing.stock});
 saveCart();toast(`${plantName} added to your basket.`);
}
async function quickAdd(plantId){
 try{const result=await api('/api/plants/'+plantId+'?region='+encodeURIComponent($('#region-filter').value));const p=result.plant;const candidates=p.listings.filter(x=>x.stock>0).sort((a,b)=>a.price_inr-b.price_inr);if(!candidates.length)throw new Error('No sample inventory is available for this plant.');addListing(candidates[0],p.common_name)}catch(error){toast(error.message)}
}
async function addFromDetail(listingId){if(!state.plant)return;const listing=state.plant.listings.find(x=>x.id===listingId);addListing(listing,state.plant.common_name)}
async function renderCart(){
 const list=$('#cart-items');const regionSelector=$('#checkout-region');const items=state.cart;
 regionSelector.value=items[0]?.region||$('#region-filter').value||state.regions[0]||'';
 if(!items.length){list.innerHTML='<p class="muted">Your basket is empty. Browse the plant collection and add an item.</p>';$('#cart-total').innerHTML='';$('#checkout-btn').disabled=true;return}
 $('#checkout-btn').disabled=false;
 list.innerHTML=items.map(item=>`<div class="cart-line"><div><strong>${escapeHTML(item.plant)}</strong><p>${escapeHTML(item.seller)} · ${escapeHTML(item.region)}</p><p>${money(item.price)} / sample plant</p><div class="cart-quantity"><button type="button" data-qty="${item.id}" data-delta="-1" aria-label="Decrease ${escapeHTML(item.plant)} quantity">−</button><strong>${item.quantity}</strong><button type="button" data-qty="${item.id}" data-delta="1" aria-label="Increase ${escapeHTML(item.plant)} quantity">+</button></div></div><div><strong>${money(item.price*item.quantity)}</strong><br/><button type="button" data-remove="${item.id}">Remove</button></div></div>`).join('');
 $('#cart-total').innerHTML='<p class="muted">Recalculating item prices and delivery at the server…</p>';
 if(items.some(x=>x.region!==regionSelector.value)){$('#cart-total').textContent='Choose the matching delivery region or empty the basket.';return}
 const fingerprint=JSON.stringify(items.map(x=>[x.id,x.quantity]));
 try{const result=await api('/api/checkout/quote',{method:'POST',body:{region:regionSelector.value,lines:items.map(x=>({listing_id:x.id,quantity:x.quantity}))}});
 if(fingerprint!==JSON.stringify(state.cart.map(x=>[x.id,x.quantity])))return;
 $('#cart-total').innerHTML=`<div class="cart-grand"><div><span class="quote-note">SERVER-VERIFIED SAMPLE TOTAL</span><br/><strong>${money(result.total_inr)}</strong></div><span class="quote-note">Items ${money(result.subtotal_inr)}<br/>Delivery ${money(result.delivery_inr)}</span></div><p class="quote-note">Quote only · No reservation or payment</p>`;
 }catch(error){$('#cart-total').innerHTML=`<p class="feedback error">${escapeHTML(error.message)}</p>`;$('#checkout-btn').disabled=true}
}
async function checkout(){
 if(!state.cart.length)return;
 if(!state.user){toast('Sign in to place a sample order.');openAuth();return}
 const region=$('#checkout-region').value,address=$('#checkout-address').value.trim();
 if(state.cart.some(item=>item.region!==region))return feedback('#cart-feedback','Choose the same delivery region as the items.',true);
 try{const data=await api('/api/orders/demo',{method:'POST',body:{region,address,lines:state.cart.map(item=>({listing_id:item.id,quantity:item.quantity}))}});
 state.cart=[];saveCart();await renderCart();feedback('#cart-feedback',`Sample order ${data.order_id.slice(0,8)} recorded. Total ${money(data.total_inr)}. No purchase, payment or delivery occurred.`);await loadProducts();
 }catch(error){feedback('#cart-feedback',error.message,true)}
}
function renderAuth(){const signedIn=!!state.user;$('#auth-current').hidden=!signedIn;$('#auth-forms').hidden=signedIn;$('#account-btn').lastElementChild.textContent=signedIn?state.user.name.split(' ')[0]:'Sign in';if(signedIn)$('#auth-greeting').textContent=`Signed in as ${state.user.name} (${state.user.email}). Review your sample orders here.`}
function openAuth(){renderAuth();openDrawer('#auth-drawer')}
async function restoreAuth(){try{const d=await api('/api/auth/me');state.user=d.user;state.csrf=d.csrf;await refreshSaved()}catch{state.user=null;state.csrf=null;state.saved.clear()}renderAuth()}
async function authSubmit(event){event.preventDefault();const body={email:$('#auth-email').value.trim(),password:$('#auth-password').value};if(state.mode==='register')body.name=$('#auth-name').value.trim();try{const d=await api('/api/auth/'+(state.mode==='register'?'register':'login'),{method:'POST',body});state.user=d.user;state.csrf=d.csrf;renderAuth();await refreshSaved();await loadProducts();feedback('#auth-feedback','Account ready. You can save plants and place a sample order.');toast('Signed in successfully.')}catch(error){feedback('#auth-feedback',error.message,true)}}
async function logout(){try{await api('/api/auth/logout',{method:'POST',body:{}});state.user=null;state.csrf=null;state.saved.clear();$('#orders-list').innerHTML='';renderAuth();await loadProducts();toast('Signed out.')}catch(error){toast(error.message)}}
async function showOrders(){try{const d=await api('/api/orders');$('#orders-list').innerHTML=d.orders.length?d.orders.map(order=>`<article class="order-card"><strong>Sample order ${escapeHTML(order.id.slice(0,8))} · ${money(order.total_inr)}</strong><p>${escapeHTML(order.region)} · ${escapeHTML(order.status)}</p>${order.lines.map(line=>`<p>${escapeHTML(line.plant_name)} × ${line.quantity}</p>`).join('')}</article>`).join(''):'<p class="muted">No sample orders yet.</p>'}catch(error){toast(error.message)}}
async function refreshSaved(){if(!state.user)return;const d=await api('/api/wishlist');state.saved=new Set(d.plant_ids)}
async function toggleWish(id){if(!state.user){toast('Sign in to save plants.');openAuth();return}try{const selected=state.saved.has(id);await api('/api/wishlist/'+id,{method:selected?'DELETE':'POST',body:{}});selected?state.saved.delete(id):state.saved.add(id);$$(`[data-wish="${id}"]`).forEach(button=>{button.textContent=selected?'♡':'♥';button.classList.toggle('saved',!selected);button.setAttribute('aria-label',(selected?'Save':'Remove')+' plant')});toast(selected?'Removed from saved plants.':'Plant saved to your account.');if(!$('#wishlist-drawer').hidden)renderWishlist()}catch(error){toast(error.message)}}
async function renderWishlist(){const container=$('#saved-items');if(!state.user){container.innerHTML='<p class="muted">Sign in to access your saved plant list.</p>';return}
 try{await refreshSaved();const catalog=await api('/api/catalog?limit=100');const saved=catalog.items.filter(x=>state.saved.has(x.id));container.innerHTML=saved.length?saved.map(p=>`<div class="saved-card">${botanicalPhoto(p,'saved-photo')}<div><strong>${escapeHTML(p.common_name)}</strong><p class="muted">${escapeHTML(p.scientific_name)} · From ${money(p.min_price_inr)}</p><button type="button" data-view="${p.id}">View listings</button> · <button type="button" data-wish="${p.id}">Remove</button></div></div>`).join(''):'<p class="muted">No saved plants yet. Tap the heart on any product card.</p>'}
 catch(error){container.textContent=error.message}}
async function taxonomy(){if(!state.plant)return;$('#gbif-result').textContent='Checking live GBIF taxonomy…';try{const d=await api('/api/plants/'+state.plant.id+'/taxonomy');$('#gbif-result').textContent=`${d.data.scientificName||'No match'} · ${d.data.rank||'Unknown rank'} · GBIF confidence ${d.data.confidence??'not reported'}. Not a medical claim.`}catch(error){$('#gbif-result').textContent=error.message}}
function resetFilters(){state.category='';$('#search-input').value='';$('#region-filter').value='';$('#price-min').value='';$('#price-max').value='';$('#stock-only').checked=false;$('#sort-filter').value='relevance';$$('[data-category]').forEach(button=>{button.classList.toggle('selected',!button.dataset.category);button.classList.toggle('active',!button.dataset.category)});closeSuggestions();loadProducts()}
function bind(){
 document.addEventListener('error', event=>{
  const img=event.target;
  if(!(img instanceof HTMLImageElement))return;
  if(img.classList.contains('photo-real')||img.classList.contains('saved-photo')||img.classList.contains('hero-photo')){
   img.hidden=true;
   const notice=img.nextElementSibling;
   if(notice?.classList.contains('photo-unavailable'))notice.hidden=false;
   else if(img.classList.contains('hero-photo')){
    const prompt=document.createElement('div');prompt.className='hero-offline';prompt.textContent='Live botanical photograph requires internet access';img.after(prompt);
   }
  }
 },true);
 document.addEventListener('keydown',event=>{
  if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='k'){
   event.preventDefault();$('#search-input').focus();$('#search-input').select();
  }
 });

 $('#cart-btn').addEventListener('click',()=>{renderCart();openDrawer('#cart-drawer')});$('#account-btn').addEventListener('click',openAuth);
 $('#seller-btn').addEventListener('click',openSeller);$('#seller-login-btn').addEventListener('click',openAuth);
 $('#seller-application').addEventListener('submit',sellerApply);$('#seller-offer-form').addEventListener('submit',sellerSubmitOffer);
 $('#verified-quote-btn').addEventListener('click',verifiedQuote);$('#verified-checkout-form').addEventListener('submit',verifiedCheckout);
 $('#wishlist-btn').addEventListener('click',()=>{openDrawer('#wishlist-drawer');renderWishlist()});
 $('#overlay').addEventListener('click',closeDrawers);
 document.addEventListener('keydown',event=>{if(event.key==='Escape'){closeDrawers();closeSuggestions()}});
 document.addEventListener('click',async event=>{
  if(event.target.closest('[data-close]'))return closeDrawers();
  const category=event.target.closest('[data-category]');if(category)return selectCategory(category.dataset.category);
  const suggestion=event.target.closest('[data-suggestion]');if(suggestion){$('#search-input').value=suggestion.dataset.suggestion;closeSuggestions();loadProducts();return}
  const view=event.target.closest('[data-view]');if(view)return viewPlant(Number(view.dataset.view));
  const quick=event.target.closest('[data-quick]');if(quick)return quickAdd(Number(quick.dataset.quick));
  const verified=event.target.closest('[data-verified-offer]');if(verified)return openVerifiedOffer(Number(verified.dataset.verifiedOffer));
  const add=event.target.closest('[data-add]');if(add)return addFromDetail(Number(add.dataset.add));
  const wish=event.target.closest('[data-wish]');if(wish)return toggleWish(Number(wish.dataset.wish));
  const remove=event.target.closest('[data-remove]');if(remove){state.cart=state.cart.filter(x=>x.id!==Number(remove.dataset.remove));saveCart();renderCart();return}
  const quantity=event.target.closest('[data-qty]');if(quantity){const item=state.cart.find(x=>x.id===Number(quantity.dataset.qty));if(!item)return;item.quantity=Math.max(0,Math.min(20,item.stock,item.quantity+Number(quantity.dataset.delta)));state.cart=state.cart.filter(x=>x.quantity>0);saveCart();renderCart();return}
  if(event.target.id==='gbif-btn')return taxonomy();
  if(event.target.id==='empty-reset')return resetFilters();
  if(!event.target.closest('.search-zone'))closeSuggestions();
 });
 $('#search-input').addEventListener('input',()=>{clearTimeout(state.searchDebounce);state.searchDebounce=setTimeout(()=>{loadProducts();suggestSearch()},180)});
 $('#search-input').addEventListener('keydown',event=>{if(event.key==='Enter'&&!$('#search-suggestions').hidden){event.preventDefault();const first=$('#search-suggestions [data-suggestion]');if(first){$('#search-input').value=first.dataset.suggestion;closeSuggestions();loadProducts()}}});
 $('#region-filter').addEventListener('change',loadProducts);$('#sort-filter').addEventListener('change',loadProducts);
 $('#apply-price').addEventListener('click',loadProducts);$('#stock-only').addEventListener('change',loadProducts);
 $('#reset-filters').addEventListener('click',resetFilters);
 $('#checkout-region').addEventListener('change',renderCart);$('#checkout-btn').addEventListener('click',checkout);
 $('#auth-form').addEventListener('submit',authSubmit);$('#orders-btn').addEventListener('click',showOrders);$('#logout-btn').addEventListener('click',logout);
 $$('[data-mode]').forEach(button=>button.addEventListener('click',()=>{state.mode=button.dataset.mode;$$('[data-mode]').forEach(b=>b.classList.toggle('active',b.dataset.mode===state.mode));$('#name-field').hidden=state.mode!=='register';$('#auth-name').required=state.mode==='register';$('#auth-submit-label').textContent=state.mode==='register'?'Create sample account':'Sign in';$('#auth-password').autocomplete=state.mode==='register'?'new-password':'current-password';$('#auth-feedback').textContent=''}));
}
async function init(){bind();updateCartCount();try{const d=await api('/api/regions');state.regions=d.regions;[ $('#region-filter'),$('#checkout-region'),$('#seller-region') ].forEach(select=>d.regions.forEach(region=>{const option=document.createElement('option');option.textContent=region;option.value=region;select.appendChild(option)}))}catch(error){toast(error.message)}await restoreAuth();await Promise.all([loadProducts(),refreshFacets()]);try{const catalog=await api('/api/catalog?limit=100');$('#seller-plant').innerHTML=catalog.items.map(p=>`<option value="${p.id}">${escapeHTML(p.common_name)} — ${escapeHTML(p.scientific_name)}</option>`).join('')}catch{}}
init();
