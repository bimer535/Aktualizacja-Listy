const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require('jsdom');
const root = path.join(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'assets/index.html'), 'utf8');
const script = fs.readFileSync(path.join(root, 'assets/app.js'), 'utf8');
const list = '<div class="movies-list-item"><a href="/movie/show/film/1"><img src="/poster.jpg" alt="Wrong title"/></a><div class="title"><a href="/movie/show/film/1">Polski tytuł</a><a class="blue" href="/movie/show/film/1">Long original title</a></div><p class="cates">2026 | Dramat</p><i title="Lektor"></i><div class="sum-vote"><div>8.5</div></div></div><a title="Następna strona" href="/movie/cat/strona[2]+">2</a>';
const detail = '<h1>Polski tytuł</h1><div class="descriptionMovie">Opis filmu</div><script>ShowPlayer("voe","abc");ShowPlayer("player","def")</script>';
const settle = () => new Promise(resolve => setImmediate(resolve));
function setup(responder, autoStart = true) {
  const dom = new JSDOM(html, {url: 'https://mk.local/', runScripts: 'outside-only'});
  const messages = [];
  dom.window.ReactNativeWebView = {postMessage(raw) {
    const message = JSON.parse(raw); messages.push(message);
    if (message.type === 'ui-ready') {if (autoStart) queueMicrotask(() => dom.window.mkStart(null)); return;}
    if (message.type !== 'fetch') return;
    const response = responder ? responder(message) : message.url.includes('/movie/show/') ? detail : list;
    if (response !== null) queueMicrotask(() => dom.window.mkReceive(JSON.stringify({requestId: message.requestId, url: message.url, html: response})));
  }};
  dom.window.eval(script);
  return {dom, w: dom.window, d: dom.window.document, messages};
}

test('uses the Polish catalogue title and poster, removes duplicate links, follows server pagination', async () => {
  const {dom, d, messages} = setup();
  try {
    await settle();
    assert.equal(d.querySelectorAll('.card').length, 1);
    assert.equal(d.querySelector('.cardname').textContent, 'Polski tytuł');
    assert.equal(d.querySelector('img.poster').src, 'https://ekino.ws/poster.jpg');
    assert.match(d.querySelector('.meta').textContent, /2026 · Lektor · 8.5\/10/);
    d.querySelector('#next').click(); await settle();
    assert.match(messages.at(-1).url, /strona\[2\]/);
    d.querySelector('#prev').click(); await settle();
    assert.equal(messages.at(-1).url, 'https://ekino.ws/');
  } finally {dom.window.close();}
});

test('search submits a catalogue query instead of clearing/filtering only the current page', async () => {
  const {dom, d, messages} = setup();
  try {
    await settle(); d.querySelector('[data-tab="search"]').click();
    d.querySelector('#search').value = 'Zażółć & kot'; d.querySelector('#do-search').click();
    await settle();
    assert.equal(messages.at(-1).url, 'https://ekino.ws/search/qf/?q=' + encodeURIComponent('Zażółć & kot'));
    assert.equal(d.querySelectorAll('.card').length, 1);
  } finally {dom.window.close();}
});

test('source selection, favourites, watched marks and Back/exit messages', async () => {
  const {dom, d, w, messages} = setup();
  try {
    await settle(); d.querySelector('.card').click(); await settle();
    const source = [...d.querySelectorAll('.sources button')].find(b => b.textContent === '▶ player');
    assert.ok(source); source.click();
    assert.equal(messages.at(-1).url, 'https://ekino.ws/watch/f/player/def');
    d.querySelector('#favorite').click(); d.querySelector('#mark').click();
    const state = JSON.parse(w.localStorage.getItem('mk_ekino_vega_v1'));
    assert.equal(Object.keys(state.favorites).length, 1);
    assert.equal(Object.keys(state.watched).length, 1);
    w.mkBack(); assert.equal(d.querySelector('#library').classList.contains('hidden'), false);
    d.querySelector('[data-tab="favorites"]').click(); await settle();
    assert.equal(d.querySelectorAll('.card').length, 1);
    w.mkBack(); await settle(); w.mkBack(); assert.equal(messages.at(-1).type, 'exit');
  } finally {dom.window.close();}
});

test('episode Back returns to series before returning to catalogue', async () => {
  const series = '<a href="/serie/show/test/">Serial</a>';
  const episodes = '<h1>Serial</h1><a href="/serie/watch/test+season[1]+episode[2]+">Odcinek 2</a>';
  const {dom, d, w} = setup(m => m.url.includes('/serie/show/') ? episodes : m.url.includes('/serie/watch/') ? detail : series);
  try {
    await settle(); d.querySelector('.card').click(); await settle();
    const episode = [...d.querySelectorAll('.sources button')].find(b => b.textContent.includes('S01E02'));
    assert.ok(episode); episode.click(); await settle();
    w.mkBack(); await settle(); assert.match(d.querySelector('#detail-view h1').textContent, /Serial/);
    w.mkBack(); assert.equal(d.querySelector('#library').classList.contains('hidden'), false);
  } finally {dom.window.close();}
});

test('late catalogue responses cannot overwrite another tab and remote HTML stays inert', async () => {
  const {dom, d, w, messages} = setup(() => null);
  try {
    await settle(); const old = messages.find(m => m.type === 'fetch'); d.querySelector('[data-tab="favorites"]').click();
    w.mkReceive(JSON.stringify({requestId:old.requestId,html:list})); await settle();
    assert.equal(d.querySelectorAll('.card').length, 0);
  } finally {dom.window.close();}
  const hostile = setup(() => '<a href="https://ekino.ws.evil.example/movie/show/a">Bad</a><a href="javascript:alert(1)">Bad</a><a href="/movie/show/safe/1">&lt;img onerror=alert(1)&gt;</a><script>window.pwned=1</script>');
  try {
    await settle();
    assert.equal(hostile.d.querySelectorAll('.card').length, 1);
    assert.equal(hostile.d.querySelector('.cardname').textContent, '<img onerror=alert(1)>');
    assert.equal(hostile.d.querySelectorAll('img').length, 0);
    assert.equal(hostile.w.pwned, undefined);
  } finally {hostile.dom.window.close();}
});

const filterPage = '<ul class="movieCategories"><li><a href="/movie/cat/kategoria[4]+">Komedia</a></li></ul><ul class="quality"><li data-id="1">Lektor</li><li data-id="2">Napisy</li></ul><ul class="filtyear"><li data-id="2026">2026</li><li data-id="2025">2025</li></ul>';
test('category, language and year filters combine in server requests, reset pagination and can be cleared', async () => {
  const {dom,d,messages}=setup(()=>filterPage+list);
  try {
    await settle();
    for(const [key,name] of [['cat','Komedia'],['version','Lektor'],['year','2026']]) {
      d.querySelector('#filter-'+key).click();await settle();
      [...d.querySelectorAll('#filter-options button')].find(b=>b.textContent===name).click();await settle();
    }
    assert.equal(messages.at(-1).url,'https://ekino.ws/movie/cat/strona[1]+sort[add]+method[desc]+kategoria[4]+wersja[1]+rok[2026]+');
    assert.equal(d.querySelector('#filter-year').textContent,'Rok: 2026');
    d.querySelector('#filter-clear').click();await settle();
    assert.equal(messages.at(-1).url,'https://ekino.ws/movie/cat/strona[1]+sort[add]+method[desc]+');
  } finally {dom.window.close();}
});
test('filter dialog loads filters when absent from home, and Back closes only the dialog',async()=>{
  const {dom,d,w,messages}=setup(m=>m.url.endsWith('/movie/cat/+')?filterPage:list);
  try {
    await settle();d.querySelector('#filter-version').click();await settle();
    assert.equal(messages.at(-1).url,'https://ekino.ws/movie/cat/+');
    assert.ok([...d.querySelectorAll('#filter-options button')].some(b=>b.textContent==='Lektor'));
    w.mkBack();assert.equal(d.querySelector('#filter-dialog').classList.contains('hidden'),true);
    assert.notEqual(messages.at(-1).type,'exit');
  } finally {dom.window.close();}
});

test('return from a navigated player restores category, year, title detail and the series back stack',async()=>{
  const {dom,d,w}=setup(()=>filterPage+list);
  try {
    await settle();
    await w.mkRestore({tab:'movies',page:1,pageUrls:['https://ekino.ws/movie/cat/strona[1]+rok[2026]+'],filters:{year:'2026',cat:'4'},selected:{url:'https://ekino.ws/movie/show/test/1',title:'Film'},detailsStack:[{url:'https://ekino.ws/serie/show/test/',title:'Serial'}]});
    assert.equal(d.querySelector('#filter-year').textContent,'Rok: 2026');
    assert.equal(d.querySelector('#details').classList.contains('visible'),true);
    w.mkBack();await settle();assert.match(d.querySelector('#detail-view h1').textContent,/Serial/);
  } finally {dom.window.close();}
});

test('native readiness handshake starts exactly one catalogue request, using restored filters', async () => {
  const {dom,w,messages,d}=setup(undefined,false);
  try {
    assert.equal(messages.length,1);assert.equal(messages[0].type,'ui-ready');
    assert.equal(messages.filter(m=>m.type==='fetch').length,0);
    w.mkStart({tab:'movies',filters:{year:'2026',version:'1'}});
    w.mkStart(null);w.mkReady();await settle();
    const requests=messages.filter(m=>m.type==='fetch');
    assert.equal(requests.length,1);
    assert.ok(requests[0].url.includes('rok[2026]'));assert.ok(requests[0].url.includes('wersja[1]'));
    assert.equal(d.querySelectorAll('.card').length,1);
  } finally {dom.window.close();}
});
