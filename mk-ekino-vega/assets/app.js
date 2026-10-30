/* MK eKino. Catalogue routes and selectors adapted from mk-ekino-android 0.1.2. GPL-3.0-only. */
'use strict';
const SITE = 'https://ekino.ws';
const KEY = 'mk_ekino_vega_v1';
const $ = selector => document.querySelector(selector);
const clean = text => (text || '').replace(/\s+/g, ' ').trim();
let currentTab = 'home', page = 1, cards = [], selected = null;
let sequence = 0, requestNumber = 0, query = '', nextPage = null;
let pageUrls = [], detailsStack = [], lastFocus = null;
const filters = {cat: '', version: '', year: ''};
const filterLabels = {cat: 'Kategoria', version: 'Wersja', year: 'Rok'};
let filterOptions = {cat: [], version: [], year: []};
let filterFetch = null, filterOpener = null, filterGeneration = 0;
const pending = new Map();
const saved = {favorites: {}, watched: {}};
try {
  const data = JSON.parse(localStorage.getItem(KEY) || '{}');
  for (const kind of ['favorites', 'watched']) {
    for (const item of Object.values(data[kind] || {})) {
      if (item && catalogueUrl(item.url) && typeof item.title === 'string') saved[kind][item.url] = item;
    }
  }
} catch (_) { /* A corrupt local record must not prevent startup. */ }

function absolute(input, base = SITE) {
  if (typeof input !== 'string' || !input.trim()) return null;
  try {
    const url = new URL(input, base);
    return url.protocol === 'https:' && !url.username && !url.password && !url.port ? url.href : null;
  } catch (_) { return null; }
}
function catalogueUrl(input, base = SITE) {
  const url = absolute(input, base);
  if (!url) return null;
  const parsed = new URL(url);
  return parsed.origin === SITE && /^\/(?:$|movie\/|serie\/|serial\/|watch\/|search\/)/.test(parsed.pathname) ? url : null;
}
function persist() { try { localStorage.setItem(KEY, JSON.stringify(saved)); } catch (_) {} }
function status(message) { $('#status').textContent = message; }
function send(message) {
  window.ReactNativeWebView?.postMessage(JSON.stringify(message));
}
function get(url) {
  return new Promise((resolve, reject) => {
    const requestId = ++requestNumber;
    const timer = setTimeout(() => { pending.delete(requestId); reject(Error('Upłynął czas oczekiwania')); }, 22000);
    pending.set(requestId, {resolve, reject, timer});
    send({type: 'fetch', requestId, url});
  });
}
window.mkReceive = raw => {
  let response;
  try { response = JSON.parse(raw); } catch (_) { return; }
  const job = pending.get(response.requestId);
  if (!job) return;
  clearTimeout(job.timer);
  pending.delete(response.requestId);
  response.error ? job.reject(Error(response.error)) : job.resolve(response);
};
const parseHTML = html => new DOMParser().parseFromString(html, 'text/html');
function parseCards(html, base = SITE) {
  const doc = parseHTML(html), items = new Map();
  // The same .movies-list-item/.title selectors used by the Android catalogue.
  for (const block of doc.querySelectorAll('.movies-list-item')) {
    const anchor = block.querySelector('.title a[href]');
    const url = anchor && catalogueUrl(anchor.getAttribute('href'), base);
    const title = clean(anchor?.textContent);
    if (!url || !title || items.has(url)) continue;
    const img = block.querySelector('img');
    const year = clean(block.querySelector('.cates')?.textContent).match(/^\d{4}/)?.[0];
    const language = block.querySelector('i[title]')?.getAttribute('title');
    const rating = clean(block.querySelector('.sum-vote div')?.textContent);
    items.set(url, {url, title, poster: absolute(img?.getAttribute('data-src') || img?.getAttribute('src'), base),
      meta: [year, language, /^\d+(?:[.,]\d+)?$/.test(rating) ? rating + '/10' : ''].filter(Boolean).join(' · ')});
  }
  for (const anchor of doc.querySelectorAll('a[href]')) {
    const url = catalogueUrl(anchor.getAttribute('href'), base);
    if (!url || !/\/(?:movie|serie|serial)\/(?:show|info)\//.test(new URL(url).pathname) || items.has(url)) continue;
    const img = anchor.querySelector('img');
    const title = clean(anchor.textContent) || clean(anchor.getAttribute('title')) || clean(img?.alt);
    if (!title || /^zobacz$/i.test(title)) continue;
    items.set(url, {url, title: title.slice(0, 150), poster: absolute(img?.getAttribute('src'), base)});
  }
  return [...items.values()];
}
function movieUrl() {
  let url = SITE + '/movie/cat/strona[1]+sort[add]+method[desc]+';
  for (const [key, route] of [['cat','kategoria'],['version','wersja'],['year','rok']]) {
    if (filters[key] && /^[A-Za-z0-9,]{1,50}$/.test(filters[key])) url += route + '[' + filters[key] + ']+';
  }
  return url;
}
function readFilters(html) {
  const doc = parseHTML(html);
  const parsed = {cat: [], version: [], year: []};
  for (const a of doc.querySelectorAll('.movieCategories a[href]')) {
    const id = (a.getAttribute('href') || '').match(/kategoria\[(\d+)\]/)?.[1];
    if (id) parsed.cat.push({id, name: clean(a.textContent)});
  }
  for (const [key, selector] of [['version','.quality li[data-id]'],['year','.filtyear [data-id]']]) {
    for (const li of doc.querySelectorAll(selector)) {
      const id = li.getAttribute('data-id'), name = clean(li.textContent) || id;
      if (/^[A-Za-z0-9,]{1,50}$/.test(id) && (key !== 'year' || /^\d{4}$/.test(id))) parsed[key].push({id, name});
    }
  }
  for (const key of Object.keys(parsed)) if (parsed[key].length) filterOptions[key] = [...new Map(parsed[key].map(x => [x.id,x])).values()];
}
function updateFilters() {
  for (const key of Object.keys(filters)) {
    const option = filterOptions[key].find(x => x.id === filters[key]);
    $('#filter-' + key).textContent = filterLabels[key] + ': ' + (option?.name || filters[key] || 'Wszystkie');
  }
}
function closeFilters() {
  const dialog = $('#filter-dialog');
  if (dialog.classList.contains('hidden')) return false;
  ++filterGeneration; $('#library').inert = false; dialog.classList.add('hidden'); filterOpener?.focus(); return true;
}
async function chooseFilter(key) {
  const generation = ++filterGeneration;
  $('#library').inert = true;
  filterOpener = $('#filter-' + key);
  const dialog = $('#filter-dialog'); dialog.classList.remove('hidden');
  $('#filter-title').textContent = filterLabels[key];
  $('#filter-options').replaceChildren();
  $('#filter-back').focus();
  try {
    if (!filterOptions[key].length) {
      $('#filter-title').textContent = 'Pobieranie filtrów…';
      if (!filterFetch) filterFetch = get(SITE + '/movie/cat/+').finally(() => {filterFetch = null;});
      const response = await filterFetch; readFilters(response.html);
    }
    if (generation !== filterGeneration || dialog.classList.contains('hidden')) return;
    $('#filter-title').textContent = filterLabels[key];
    if (!filterOptions[key].length) throw Error('Serwis nie udostępnił listy filtrów');
    const options = [{id:'',name:'Wszystkie'}, ...filterOptions[key]];
    for (const option of options) {
      const button = add($('#filter-options'), 'button', 'pill' + (filters[key] === option.id ? ' chosen' : ''), option.name);
      button.onclick = () => { filters[key] = option.id; updateFilters(); closeFilters(); changeTab('movies'); };
    }
    $('#filter-options .chosen')?.focus();
  } catch (error) { $('#filter-title').textContent = 'Nie można pobrać filtrów: ' + error.message; }
}
function parseNext(html, base) {
  const link = [...parseHTML(html).querySelectorAll('a[href]')].find(a => /Następna strona/i.test(a.title));
  return link ? catalogueUrl(link.getAttribute('href'), base) : null;
}
function parseDetail(html, base, item) {
  const doc = parseHTML(html), sources = [], episodes = [], seen = new Set();
  for (const anchor of doc.querySelectorAll('a[href]')) {
    const url = catalogueUrl(anchor.getAttribute('href'), base);
    if (!url || seen.has(url)) continue;
    if (url.includes('/serie/watch/')) {
      seen.add(url);
      const numbers = decodeURIComponent(url).match(/season\[(\d+)\].*episode\[(\d+)\]/);
      const label = numbers ? 'S' + numbers[1].padStart(2, '0') + 'E' + numbers[2].padStart(2, '0') + ' · ' : '';
      episodes.push({url, name: label + (clean(anchor.textContent) || 'Odcinek')});
    } else if (url.includes('/watch/')) {
      seen.add(url); sources.push({url, name: clean(anchor.textContent) || 'Odtwarzacz'});
    }
  }
  for (const match of html.matchAll(/ShowPlayer\(['"]([^'"]+)['"],\s*['"]([^'"]+)['"]\)/g)) {
    const url = SITE + '/watch/f/' + encodeURIComponent(match[1]) + '/' + encodeURIComponent(match[2]);
    if (!seen.has(url)) { seen.add(url); sources.push({url, name: match[1]}); }
  }
  const labels = new Map();
  for (const a of doc.querySelectorAll('ul.players a[href^="#"]')) {
    const label = [...a.querySelectorAll('[title]')].map(x => x.getAttribute('title')).filter(Boolean).join(' · ');
    labels.set(a.getAttribute('href').slice(1), label);
  }
  for (const source of sources) {
    const m = source.url.match(/\/watch\/f\/([^/]+)\/([^/?#]+)/);
    if (m) {const label = labels.get(decodeURIComponent(m[2]) + '-' + decodeURIComponent(m[1])); if (label) source.name += ' · ' + label;}
  }
  const order = ['player', 'voe', 'mix'];
  sources.sort((a, b) => (order.indexOf(a.name) < 0 ? 9 : order.indexOf(a.name)) - (order.indexOf(b.name) < 0 ? 9 : order.indexOf(b.name)));
  return {
    title: clean(doc.querySelector('h1')?.textContent) || item.title,
    description: clean(doc.querySelector('.descriptionMovie, [itemprop="description"], .description')?.textContent) || clean(doc.querySelector('meta[name="description"]')?.content),
    poster: absolute(doc.querySelector('meta[property="og:image"]')?.content, base) || item.poster,
    sources, episodes,
  };
}
function add(parent, tag, className, text) {
  const element = document.createElement(tag);
  element.className = className || '';
  if (text !== undefined) element.textContent = text;
  parent.appendChild(element);
  return element;
}
function captureState() {
  return {tab:currentTab,page,pageUrls:[...pageUrls],query,filters:{...filters},selected,detailsStack:[...detailsStack]};
}
function openPage(url, play = false) { const safe = catalogueUrl(url); if (safe) send({type: play ? 'play' : 'open', url: safe, referer: selected?.url || SITE + '/', state:captureState()}); }
function createCard(item) {
  const button = document.createElement('button');
  button.className = 'card'; button.dataset.url = item.url; button.setAttribute('aria-label', item.title);
  if (item.poster) {
    const img = add(button, 'img', 'poster'); img.src = item.poster; img.alt = ''; img.loading = 'lazy';
    img.onerror = () => { img.remove(); add(button, 'div', 'poster fallback', '▶'); };
  } else add(button, 'div', 'poster fallback', '▶');
  add(button, 'span', 'cardname', item.title);
  add(button, 'span', 'meta', saved.watched[item.url] ? '✓ Obejrzane' : saved.favorites[item.url] ? '★ Ulubione' : item.meta || 'Zobacz szczegóły');
  button.onclick = () => { lastFocus = item.url; detailsStack = []; showDetail(item); };
  return button;
}
function render() {
  const filter = currentTab === 'search' ? '' : clean($('#search').value).toLocaleLowerCase('pl');
  const items = cards.filter(item => item.title.toLocaleLowerCase('pl').includes(filter));
  $('#grid').replaceChildren(...items.map(createCard));
  if (!items.length) add($('#grid'), 'p', 'empty', filter ? 'Nie znaleziono tytułu na tej stronie.' : 'Brak pozycji do wyświetlenia.');
  $('#page-count').textContent = 'Strona ' + page;
  $('#paging').classList.toggle('hidden', !nextPage && page === 1);
  $('#prev').disabled = page <= 1;
  $('#next').disabled = !nextPage;
}
async function load(url) {
  const ticket = ++sequence;
  selected = null; detailsStack = [];
  $('#filters').classList.toggle('hidden', !['home','movies'].includes(currentTab));
  updateFilters();
  $('#details').classList.remove('visible'); $('#library').classList.remove('hidden');
  nextPage = null; cards = []; render();
  $('#search').placeholder = currentTab === 'search' ? 'Tytuł filmu lub serialu…' : 'Filtruj stronę lub wyszukaj w katalogu…';
  if (currentTab === 'favorites' || currentTab === 'watched') {
    cards = Object.values(saved[currentTab]); status('Zapisane na tym urządzeniu · ' + cards.length); render(); return;
  }
  if (currentTab === 'search' && !query) {
    status('Wpisz tytuł i wybierz „Szukaj w katalogu”.'); $('#search').focus(); return;
  }
  if (!url) url = currentTab === 'movies' ? movieUrl() :
    currentTab === 'shows' ? SITE + '/serie/' : currentTab === 'search' ? SITE + '/search/qf/?q=' + encodeURIComponent(query) : SITE + '/';
  pageUrls[page - 1] = url;
  status('Pobieranie katalogu…');
  try {
    const result = await get(url);
    if (ticket !== sequence) return;
    if (/cf-chl-|Attention Required! \| Cloudflare/.test(result.html)) throw Error('Serwis wymaga weryfikacji w przeglądarce');
    readFilters(result.html); updateFilters();
    cards = parseCards(result.html, url); nextPage = parseNext(result.html, url);
    status(cards.length ? cards.length + ' pozycji · strona ' + page : 'Brak wyników. Możesz otworzyć stronę eKino.');
  } catch (error) {
    if (ticket !== sequence) return;
    status('Nie można pobrać katalogu: ' + error.message + '.');
  }
  render(); if ($('#filter-dialog').classList.contains('hidden')) $('#grid button')?.focus();
}
async function showDetail(item, push = false) {
  if (push && selected) detailsStack.push(selected);
  selected = item;
  const ticket = ++sequence;
  $('#library').classList.add('hidden'); $('#details').classList.add('visible');
  const output = $('#detail-view'); output.replaceChildren();
  add(output, 'p', 'status', 'Pobieranie informacji…'); updateButtons(); $('#close').focus();
  try {
    const result = await get(item.url);
    if (ticket !== sequence) return;
    const info = parseDetail(result.html, item.url, item);
    output.replaceChildren();
    const head = add(output, 'div', 'detailHead');
    if (info.poster) { const img = add(head, 'img', 'detailPoster'); img.src = info.poster; img.alt = ''; }
    const body = add(head, 'div', 'detailBody');
    add(body, 'h1', '', info.title); add(body, 'p', 'description', info.description || 'Opis nie jest dostępny.');
    if (info.episodes.length) {
      add(output, 'h2', '', 'Odcinki serialu');
      const list = add(output, 'div', 'sources');
      for (const episode of info.episodes) {
        const button = add(list, 'button', 'pill', '▶ ' + episode.name);
        button.onclick = () => showDetail({url: episode.url, title: item.title + ' – ' + episode.name, poster: item.poster}, true);
      }
    }
    add(output, 'h2', '', 'Dostępne źródła');
    if (!info.sources.length) add(output, 'p', 'empty', 'Brak wykrytych źródeł. Spróbuj otworzyć stronę materiału.');
    const sources = add(output, 'div', 'sources');
    for (const source of info.sources) {
      const button = add(sources, 'button', 'pill', '▶ ' + source.name);
      button.onclick = () => { lastFocus = button; openPage(source.url, true); };
    }
    const button = add(sources, 'button', 'pill', 'Otwórz stronę materiału'); button.onclick = () => openPage(item.url);
  } catch (error) {
    if (ticket !== sequence) return;
    output.replaceChildren(); add(output, 'p', 'empty', 'Nie można pobrać informacji: ' + error.message);
    const button = add(output, 'button', 'pill', 'Otwórz stronę materiału'); button.onclick = () => openPage(item.url);
  }
}
function updateButtons() {
  if (!selected) return;
  $('#favorite').textContent = saved.favorites[selected.url] ? '★ Usuń z ulubionych' : '☆ Dodaj do ulubionych';
  $('#mark').textContent = saved.watched[selected.url] ? '↶ Oznacz jako nieobejrzany' : '✓ Obejrzałem';
}
function closeDetail() {
  if (!selected) return false;
  if (detailsStack.length) { showDetail(detailsStack.pop()); return true; }
  ++sequence;
  const previous = selected.url; selected = null;
  $('#details').classList.remove('visible'); $('#library').classList.remove('hidden');
  if (currentTab === 'favorites' || currentTab === 'watched') cards = Object.values(saved[currentTab]);
  render();
  [...document.querySelectorAll('.card')].find(button => button.dataset.url === previous)?.focus();
  return true;
}
function changeTab(tab) {
  currentTab = tab; page = 1; pageUrls = []; query = ''; $('#search').value = '';
  document.querySelectorAll('[data-tab]').forEach(button => button.classList.toggle('active', button.dataset.tab === tab));
  $('#page-title').textContent = {home: 'Odkrywaj filmy', movies: 'Filmy', shows: 'Seriale', favorites: 'Ulubione', watched: 'Obejrzane', search: 'Wyszukiwarka'}[tab];
  load();
}
function searchCatalogue() {
  const term = clean($('#search').value);
  if (!term) { $('#search').focus(); return; }
  currentTab = 'search'; query = term; page = 1; pageUrls = [];
  document.querySelectorAll('[data-tab]').forEach(button => button.classList.toggle('active', button.dataset.tab === 'search'));
  $('#page-title').textContent = 'Wyniki: ' + term; load();
}
window.mkBack = () => {
  if (closeFilters()) return;
  if (closeDetail()) return;
  if (currentTab !== 'home') changeTab('home');
  else send({type: 'exit'});
};
window.mkRestore = async state => {
  if (!state || typeof state !== 'object') return;
  const tabs = ['home','movies','shows','favorites','watched','search'];
  currentTab = tabs.includes(state.tab) ? state.tab : 'home';
  page = Number.isInteger(state.page) && state.page > 0 && state.page < 100000 ? state.page : 1;
  pageUrls = Array.isArray(state.pageUrls) ? state.pageUrls.slice(0,10000).map(url => catalogueUrl(url)) : [];
  query = typeof state.query === 'string' ? state.query.slice(0,300) : '';
  for (const key of Object.keys(filters)) filters[key] = /^[A-Za-z0-9,]{1,50}$/.test(state.filters?.[key]) ? state.filters[key] : '';
  document.querySelectorAll('[data-tab]').forEach(button => button.classList.toggle('active',button.dataset.tab === currentTab));
  $('#page-title').textContent = {home:'Odkrywaj filmy',movies:'Filmy',shows:'Seriale',favorites:'Ulubione',watched:'Obejrzane',search:'Wyniki: ' + query}[currentTab];
  $('#search').value = currentTab === 'search' ? query : '';
  const safeItem = item => item && catalogueUrl(item.url) && typeof item.title === 'string' ? {url:catalogueUrl(item.url), title:item.title.slice(0,300), poster:absolute(item.poster)} : null;
  const item = safeItem(state.selected);
  const stack = Array.isArray(state.detailsStack) ? state.detailsStack.map(safeItem).filter(Boolean).slice(0,30) : [];
  await load(pageUrls[page - 1]);
  if (item) {await showDetail(item); detailsStack = stack;}
};
window.mkPlayerClosed = () => {
  if (lastFocus && typeof lastFocus !== 'string' && lastFocus.isConnected) lastFocus.focus();
  else $('#close').focus();
};
for (const button of document.querySelectorAll('[data-tab]')) button.onclick = () => changeTab(button.dataset.tab);
for (const key of Object.keys(filters)) $('#filter-' + key).onclick = () => chooseFilter(key);
$('#filter-back').onclick = closeFilters;
$('#filter-clear').onclick = () => {for (const key of Object.keys(filters)) filters[key] = ''; updateFilters(); changeTab('movies');};
$('#refresh').onclick = () => load(pageUrls[page - 1]);
$('#do-search').onclick = searchCatalogue;
$('#search').oninput = () => { if (currentTab !== 'search') render(); };
$('#search').onkeydown = event => { if (event.key === 'Enter') { event.preventDefault(); searchCatalogue(); } };
$('#open-site').onclick = () => openPage(SITE + '/');
$('#next').onclick = () => { if (nextPage) { ++page; load(nextPage); } };
$('#prev').onclick = () => { if (page > 1) { --page; load(pageUrls[page - 1]); } };
$('#close').onclick = closeDetail;
for (const [selector, kind] of [['#favorite', 'favorites'], ['#mark', 'watched']]) {
  $(selector).onclick = () => {
    if (!selected) return;
    if (saved[kind][selected.url]) delete saved[kind][selected.url]; else saved[kind][selected.url] = selected;
    persist(); updateButtons();
  };
}
// System Back is routed by the native wrapper. This also supports desktop tests.
document.addEventListener('keydown', event => { if (event.key === 'Escape') { event.preventDefault(); window.mkBack(); } });
// Start only after the native wrapper acknowledges this initialized document.
// This avoids racing a default load with restoration after returning from film.
let started = false;
window.mkStart = state => {
  if (started) return;
  started = true;
  document.querySelector('.nav.active')?.focus();
  if (state && typeof state === 'object') window.mkRestore(state);
  else load();
};
window.mkReady = () => send({type:'ui-ready'});
if (window.ReactNativeWebView) window.mkReady();
else window.mkStart(null);
