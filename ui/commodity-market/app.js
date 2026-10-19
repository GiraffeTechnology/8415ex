'use strict';
(() => {
 const catalog = [
  ['gold','GOLD','kg','gold.svg'],['silver','SILVER','kg','silver.svg'],
  ['copper','CU','t','copper.png'],['iron-ore','IRON','t','ore.png'],
  ['crude-oil','OIL','bbl','crude-oil.svg'],['coal','COAL','t','coal.svg'],
  ['soy','SOY','t','soy.png'],['corn','CORN','t','corn.svg']
 ];
 const locales = window.EX_LOCALES;
 const params = new URLSearchParams(location.search);
 let locale = Object.hasOwn(locales, params.get('lang')) ? params.get('lang') : 'en';
 let selected = null, modalIndex = null, lastFocus = null;
 const query = document.querySelector('#search');
 query.value = (params.get('q') || '').slice(0,64);
 const dialog = document.querySelector('#details');
 const node = (tag, text, className) => { const el = document.createElement(tag); if (text !== undefined) el.textContent = text; if(className) el.className = className; return el; };
 const photo = (item, name, className='product-photo') => { const image = node('img'); image.src = 'assets/' + item[3]; image.alt = name; image.className = className; image.width=400; image.height=148; return image; };
 const updateURL = () => { const url=new URL(location.href); url.searchParams.set('lang',locale); if(query.value) url.searchParams.set('q',query.value); else url.searchParams.delete('q'); history.replaceState(null,'',url); };
 function detail(i) {
  const t=locales[locale];modalIndex=i;
  document.querySelector('#detail-title').textContent=t.names[i];
  document.querySelector('#detail-spec').textContent=t.specs[i]+' · '+t.spec;
  const img=document.querySelector('#detail-image');img.src='assets/'+catalog[i][3];img.alt=t.names[i];
 }
 function render() {
  const t=locales[locale];document.documentElement.lang=locale;document.title='8415EX · '+t.market;
  document.querySelector('#language').value=locale;
  document.querySelectorAll('[data-i18n]').forEach(el=>{el.textContent=t[el.dataset.i18n];});
  document.querySelector('.hero h2').style.whiteSpace='pre-line';
  document.querySelector('.hero-photo').alt=t.names[6]+' · '+t.illustration;
  const quotes=document.querySelector('#quotes'), products=document.querySelector('#products'), categories=document.querySelector('#mobile-categories');
  quotes.replaceChildren();products.replaceChildren();categories.replaceChildren();
  let count=0;const q=query.value.trim().toLocaleLowerCase(locale);
  catalog.forEach((item,i)=>{
   const button=node('button',t.names[i]);button.type='button';button.dataset.commodity=item[0];button.setAttribute('aria-pressed',String(selected===i));
   button.addEventListener('click',()=>{selected=i;query.value='';render();document.querySelector('#commodities').scrollIntoView({block:'start'});});categories.append(button);
   const quote=node('article',undefined,'quote-card');quote.dataset.code=item[0];
   const head=node('div',undefined,'quote-head');head.append(node('h3',t.names[i]),node('span',item[1]+' / CNY','code'));
   const price=node('div',undefined,'price');price.append(node('strong','—'),node('small','CNY / '+item[2]));
   quote.append(head,price,node('p',t.unavailable,'muted'),node('p',t.source,'source'));quotes.append(quote);
   if((selected!==null&&selected!==i)||(q&&!((t.names[i]+' '+t.specs[i]+' '+item[0]+' '+item[1]).toLocaleLowerCase(locale).includes(q))))return;
   count++;const card=node('article',undefined,'product');card.id='commodity-'+item[0];card.dataset.commodity=item[0];card.dataset.mobileSelected=String(selected===i||(selected===null&&(q!==''||i===6)));
   const title=node('div',undefined,'product-head');title.append(node('h3',t.names[i]),node('span',item[1],'code'));
   const amount=node('div',undefined,'price');amount.append(node('strong','—'),node('small','USDT / '+item[2]),node('span','DEMO','badge'));
   const qty=node('p',undefined,'unit-line muted');qty.append(node('span',t.quantity),node('span','— '+item[2]+' · 1 NFT'));
   const open=node('button',t.details+' →','button');open.type='button';open.setAttribute('aria-haspopup','dialog');open.addEventListener('click',()=>{lastFocus=open;detail(i);dialog.showModal();});
   card.append(photo(item,t.names[i]+' · '+t.illustration),title,node('p',t.specs[i]+' · '+t.spec,'muted spec'),amount,qty,node('p',t.unavailable,'muted'),open);products.append(card);
  });
  document.querySelector('#empty').hidden=count!==0;
  if(modalIndex!==null)detail(modalIndex);
 }
 document.querySelector('#language').addEventListener('change',event=>{locale=Object.hasOwn(locales,event.target.value)?event.target.value:'en';render();updateURL();});
 document.querySelector('#search-form').addEventListener('submit',event=>{event.preventDefault();selected=null;render();updateURL();});
 document.querySelector('#all').addEventListener('click',()=>{selected=null;query.value='';render();updateURL();});
 document.querySelector('#close-detail').addEventListener('click',()=>dialog.close());
 dialog.addEventListener('close',()=>{modalIndex=null;if(lastFocus?.isConnected)lastFocus.focus();});
 render();
})();
