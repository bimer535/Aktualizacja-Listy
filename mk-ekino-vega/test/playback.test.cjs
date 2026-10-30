const test = require('node:test');
const assert = require('node:assert/strict');
const {JSDOM} = require('jsdom');
const {resolveSource, publicUrl, MEDIA_REPORTING, videoScript} = require('../src/playback');
const watch = 'https://ekino.ws/watch/f/player/key';

test('follows the normal redirect link and iframe to the actual player, preserving Referer', async () => {
  const calls = [];
  const result = await resolveSource(watch, async (url, referer) => {
    calls.push({url, referer});
    return {url, html: calls.length === 1 ? '<a target="_blank" href="https://ekino.link/r/123">Przekierowanie</a>' : calls.length === 2 ? '<iframe src="https://host.example/embed/film"></iframe>' : '<script src="/normal-player.js"></script>'};
  }, 'https://ekino.ws/movie/show/test/1');
  assert.equal(calls.length, 3);
  assert.equal(calls[1].referer, watch);
  assert.deepEqual(result, {kind:'embed',url:'https://host.example/embed/film',referer:'https://ekino.link/r/123'});
});
test('discovers a direct source with its query token intact and does not fetch the video', async () => {
  const calls=[];
  const result=await resolveSource(watch, async url => {
    calls.push(url);
    return {url,html:calls.length===1?'<iframe src="https://host.example/e/1"></iframe>':'<video><source src="https://cdn.example/film.mp4?token=1&amp;exp=2"></video>'};
  });
  assert.equal(result.kind,'direct');
  assert.equal(result.url,'https://cdn.example/film.mp4?token=1&exp=2');
  assert.equal(result.referer,'https://host.example/e/1');
  assert.equal(calls.length,2);
});
test('rejects source loops, local endpoints, unexpected entry points and verification pages', async () => {
  for (const value of ['https://127.0.0.1/a','http://host.example/a','https://host.local/a','https://user:pass@host.example/a','https://host.example:443/a','https://host.example/\\a']) assert.equal(publicUrl(value),null);
  await assert.rejects(resolveSource('https://evil.example/a',async()=>{}),/Nieprawidłowy/);
  await assert.rejects(resolveSource(watch,async url=>({url,html:'<iframe src="'+watch+'"></iframe>'})),/zapętliło/);
  await assert.rejects(resolveSource(watch,async url=>({url,html:'<iframe src="https://127.0.0.1/private"></iframe>'})),/Nie znaleziono/);
  await assert.rejects(resolveSource(watch,async url=>({url,html:'cf-chl-cloudflare'})),/weryfikacji/);
});
test('stream player creates a video element safely and retains controls after repeated load', () => {
  const dom=new JSDOM('<body><p>Redirecting</p></body>',{runScripts:'outside-only'});
  try {
    dom.window.HTMLMediaElement.prototype.play=()=>Promise.resolve();
    const url='https://cdn.example/film.m3u8?token=test';
    dom.window.eval(videoScript(url)); dom.window.eval(videoScript(url));
    const video=dom.window.document.querySelector('video');
    assert.equal(dom.window.document.querySelectorAll('video').length,1);
    assert.equal(video.src,url);assert.equal(video.controls,true);
    assert.equal(dom.window.document.body.textContent,'');
  } finally {dom.window.close();}
});
test('embed observation leaves host playback, focus, controls and DOM unchanged', async () => {
  const dom=new JSDOM('<button id="confirm">Play</button><video></video>',{runScripts:'outside-only'});
  let played=0;
  try {
    dom.window.HTMLMediaElement.prototype.play=()=>{played++;return Promise.resolve();};
    const button=dom.window.document.querySelector('button'),video=dom.window.document.querySelector('video');
    button.focus(); const before=dom.window.document.body.innerHTML;
    dom.window.eval(MEDIA_REPORTING);await new Promise(r=>setImmediate(r));
    video.dispatchEvent(new dom.window.Event('playing'));
    assert.equal(played,0);assert.equal(video.controls,false);
    assert.equal(dom.window.document.activeElement,button);
    assert.equal(dom.window.document.body.innerHTML,before);
  } finally {dom.window.close();}
});
test('provider HTTP denial opens its normal embed session; wrapper denial remains an error', async()=>{
  const result=await resolveSource(watch, async url=>{
    if(url===watch)return {url,html:'<iframe src="https://host.example/e/1"></iframe>'};
    throw Error('Źródło zwróciło HTTP 403');
  });
  assert.equal(result.kind,'embed');assert.equal(result.url,'https://host.example/e/1');
  await assert.rejects(resolveSource(watch,async()=>{throw Error('Źródło zwróciło HTTP 403');}),/HTTP 403/);
});
test('passive media diagnostics include numeric state without stream tokens',async()=>{
  const dom=new JSDOM('<video></video>',{runScripts:'outside-only'});
  const messages=[];
  try {
    dom.window.ReactNativeWebView={postMessage:s=>messages.push(JSON.parse(s))};
    dom.window.eval(MEDIA_REPORTING);await new Promise(r=>setImmediate(r));
    const video=dom.window.document.querySelector('video');
    Object.defineProperty(video,'error',{value:{code:3,message:'https://private.example/token'}});
    video.dispatchEvent(new dom.window.Event('error'));
    assert.equal(messages.at(-1).code,3);
    assert.equal(JSON.stringify(messages).includes('private'),false);
    assert.ok(messages.some(m=>m.event==='document-ready'));
  } finally {dom.window.close();}
});
