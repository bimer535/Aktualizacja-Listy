/* Public embed discovery, adapted from MK eKino E2 worker.py. GPL-3.0-only. */
'use strict';
function publicUrl(value) {
  if (typeof value !== 'string' || value.length > 8192 || /[\\\s<>"\u0000-\u001f]/.test(value)) return null;
  const m = /^https:\/\/([a-z0-9.-]+)(\/[^]*)?$/i.exec(value);
  if (!m || !m[1].includes('.') || /^[\d.]+$/.test(m[1]) || /\.(?:local|internal|localhost)$/.test(m[1])) return null;
  return value;
}
function link(value, base) {
  value = value.replace(/&amp;/g, '&').replace(/&#0?39;/g, "'").replace(/\\\//g, '/');
  const origin = /^https:\/\/[^/]+/.exec(base)?.[0];
  if (value.startsWith('//')) value = 'https:' + value;
  else if (value.startsWith('/')) value = origin + value;
  else if (!value.startsWith('https://')) value = base.split(/[?#]/)[0].replace(/[^/]*$/, '') + value;
  return publicUrl(value);
}
/** @param {string} initial @param {(url:string, referer:string)=>Promise<{html:string,url:string}>} fetchPage @param {string} [referer] */
async function resolveSource(initial, fetchPage, referer = 'https://ekino.ws/') {
  let url = publicUrl(initial);
  if (!url || !url.startsWith('https://ekino.ws/watch/')) throw Error('Nieprawidłowy adres źródła');
  const visited = new Set();
  for (let hop = 0; hop < 6; hop++) {
    if (visited.has(url)) throw Error('Źródło zapętliło przekierowania');
    visited.add(url);
    if (/\.(?:m3u8|mp4|webm)(?:[?#]|$)/i.test(url)) return {kind:'direct', url, referer};
    let result;
    try {result = await fetchPage(url, referer);}
    catch (error) {
      // Some hosts require their own normal browser session. Let their embed
      // handle that session; do not treat the watch redirect as a video page.
      const wrapper = /^https:\/\/(?:ekino\.ws|(?:[a-z0-9-]+\.)?ekino\.link)\//i.test(url);
      if (!wrapper && /^Źródło zwróciło HTTP (?:403|429|503)$/.test(error.message || '')) return {kind:'embed',url,referer};
      throw error;
    }
    const final = publicUrl(result.url || url);
    if (!final) throw Error('Źródło zwróciło nieobsługiwany adres');
    const html = result.html;
    if (/cf-chl-|Attention Required! \| Cloudflare/i.test(html)) throw Error('Źródło wymaga weryfikacji. Wybierz inne źródło.');
    const media = /<source\b[^>]*\bsrc=["']([^"']+)["']/i.exec(html) ||
      /\b(?:file|hls|src)\s*[:=]\s*["']([^"']+\.(?:m3u8|mp4|webm)(?:\?[^"']*)?)["']/i.exec(html);
    const direct = media && link(media[1], final);
    if (direct) return {kind:'direct', url:direct, referer:final};
    const wrapper = /^https:\/\/(?:ekino\.ws|(?:[a-z0-9-]+\.)?ekino\.link)\//i.test(final);
    const playerFrame = /<iframe\b[^>]*\bsrc=["']([^"']+)["']/i.exec(html);
    if (!wrapper && /^https:\/\/(?:mfw09\.org|streamlyplayero\.online)\//.test(final) && playerFrame) {
      const target = link(playerFrame[1], final);
      if (target) {referer = final; url = target; continue;}
    }
    if (!wrapper) return {kind:'embed', url:final, referer};
    // E2 follows the public target link before an iframe on redirect pages.
    const anchor = [...html.matchAll(/<a\b[^>]*>/gi)].find(m => /\btarget\s*=/i.test(m[0]));
    const target = anchor && /\bhref=["']([^"']+)["']/i.exec(anchor[0]);
    const frame = /<iframe\b[^>]*\bsrc=["']([^"']+)["']/i.exec(html);
    const next = target || frame;
    const nextUrl = next && link(next[1], final);
    if (!nextUrl) throw Error('Nie znaleziono odtwarzacza tego źródła. Wybierz inne źródło.');
    referer = final; url = nextUrl;
  }
  throw Error('Zbyt wiele przekierowań źródła');
}
// Report bounded event codes only; never send stream URLs, cookies or page text.
const MEDIA_REPORTING = `(function(){if(window.mkMediaReporting)return;window.mkMediaReporting=true;
window.mkReport=function(event,v,code){try{window.ReactNativeWebView&&window.ReactNativeWebView.postMessage(JSON.stringify({type:'mk-media',event:event,code:Number(code||v&&v.error&&v.error.code||0),readyState:Number(v&&v.readyState||0),networkState:Number(v&&v.networkState||0)}));}catch(_){}};
function observe(){if(!document)return;document.querySelectorAll('video').forEach(function(v){if(v.dataset.mkReported)return;v.dataset.mkReported='1';
['playing','waiting','stalled','error','loadstart','loadedmetadata'].forEach(function(event){v.addEventListener(event,function(){window.mkReport(event,v);});});});}
const observer=new MutationObserver(observe);observer.observe(document.documentElement,{subtree:true,childList:true});
window.addEventListener('pagehide',function(){observer.disconnect();},{once:true});observe();
setTimeout(function(){if(document&&!document.querySelector('video'))window.mkReport('no-video',null);},15000);
})();true;`;
// Use the host's normal player. No CAPTCHA, DRM or access checks are bypassed.
const AUTO_PLAY = MEDIA_REPORTING + `(function(){if(window.mkPlaybackReady)return;window.mkPlaybackReady=true;
function activate(){if(!document)return;document.querySelectorAll('video').forEach(function(v){
v.controls=true;v.autoplay=true;v.style.background='black';v.setAttribute('playsinline','');
if(!v.dataset.mkReady){v.dataset.mkReady='1';v.tabIndex=0;v.addEventListener('playing',function(){v.focus();
v.style.position='fixed';v.style.inset='0';v.style.width='100vw';v.style.height='100vh';v.style.zIndex='2147483647';
document.body.style.background='black';});v.play().catch(function(){window.mkReport('play-rejected',v);});}});}
const observer=new MutationObserver(activate);observer.observe(document.documentElement,{subtree:true,childList:true});window.addEventListener('pagehide',function(){observer.disconnect();},{once:true});activate();})();true;`;
function videoScript(url) {
  const literal = JSON.stringify(url).replace(/</g, '\\u003c');
  return MEDIA_REPORTING + `(function(){if(window.mkDirectInitialized)return;window.mkDirectInitialized=true;
const v=document.createElement('video'),error=document.createElement('p');
document.body.replaceChildren(v,error);document.body.style.cssText='margin:0;background:black;color:white';
v.controls=true;v.autoplay=true;v.setAttribute('playsinline','');v.style.cssText='position:fixed;inset:0;width:100vw;height:100vh;background:black;z-index:2147483646';
error.style.cssText='position:fixed;bottom:70px;left:30px;z-index:2147483647;color:white';
v.src=${literal};v.onerror=function(){error.textContent='Nie udało się odtworzyć strumienia. MEDIA_ERR_'+Number(v.error&&v.error.code||0);window.mkReport('error',v);};v.play().catch(function(){window.mkReport('play-rejected',v);});})();true;`;
}
module.exports = {publicUrl, resolveSource, AUTO_PLAY, videoScript, MEDIA_REPORTING};
