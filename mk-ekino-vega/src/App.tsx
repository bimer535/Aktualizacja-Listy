/** MK eKino for Vega OS 2.0. GPL-3.0-only. */
import React, {useCallback, useEffect, useRef, useState} from 'react';
import {BackHandler, Pressable, StyleSheet, Text, View} from 'react-native';
import {WebView} from '@amazon-devices/webview';
import {useHideSplashScreenCallback, usePreventHideSplashScreen} from '@amazon-devices/react-native-kepler';

import {publicUrl, resolveSource, AUTO_PLAY, videoScript, MEDIA_REPORTING} from './playback';

const USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36';
const SITE = 'https://ekino.ws';
const HOME = 'file:///pkg/assets/index.html';
const PATHS = /^\/(?:$|movie\/|serie\/|serial\/|watch\/|search\/)/;
type Message = {type: string; requestId?: number; url?: string; referer?: string; state?: unknown; event?: string; code?: number; readyState?: number; networkState?: number};

function safeUrl(input: unknown): string | null {
  if (typeof input !== 'string' || !input || input.length > 2048) return null;
  // RN's URL implementation does not implement browser URL properties fully.
  if (!input.startsWith(SITE + '/') || /[\\\s\u0000-\u001f]/.test(input)) return null;
  const pathname = input.slice(SITE.length).split(/[?#]/, 1)[0];
  return PATHS.test(pathname) ? input : null;
}

export const App = () => {
  const homeRef = useRef<React.ElementRef<typeof WebView>>(null);
  const catalogueGeneration = useRef(0);
  const activeRequests = useRef(new Map<number, AbortController>());
  const [browserUrl, setBrowserUrl] = useState<string | null>(null);
  const [browserError, setBrowserError] = useState('');
  const [resolving, setResolving] = useState(false);
  const [playback, setPlayback] = useState<{kind:string;url:string;referer:string} | null>(null);
  const resolveGeneration = useRef(0);
  const sourceRequest = useRef<AbortController | null>(null);
  const [pageSource, setPageSource] = useState<{uri:string;headers?:Record<string,string>}>({uri:HOME});
  const catalogueState = useRef<unknown>(null);
  const restorePending = useRef(false);
  const playerDocument = useRef(false);
  const [mediaStatus, setMediaStatus] = useState('');
  const [mediaStarted, setMediaStarted] = useState(false);
  const [backFocused, setBackFocused] = useState(false);
  usePreventHideSplashScreen();
  const hideSplash = useHideSplashScreenCallback();

  const closePlayer = useCallback(() => {
    ++resolveGeneration.current; ++catalogueGeneration.current;
    sourceRequest.current?.abort();
    setResolving(false); setPlayback(null);
    setBrowserUrl(null);
    setBrowserError('');
    setMediaStatus(''); setMediaStarted(false);
    if (playerDocument.current) {
      restorePending.current = true; playerDocument.current = false; setPageSource({uri:HOME});
    } else homeRef.current?.injectJavaScript('window.mkPlayerClosed?.(); true;');
  }, []);
  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      if (browserUrl) closePlayer();
      else homeRef.current?.injectJavaScript('window.mkBack?.(); true;');
      return true;
    });
    return () => sub.remove();
  }, [browserUrl, closePlayer]);
  useEffect(() => () => {
    sourceRequest.current?.abort();
    for (const controller of activeRequests.current.values()) controller.abort();
    activeRequests.current.clear();
  }, []);

  function sendToUi(payload: object, generation = catalogueGeneration.current) {
    if (generation !== catalogueGeneration.current || playerDocument.current || restorePending.current) return;
    homeRef.current?.injectJavaScript('window.mkReceive(' + JSON.stringify(JSON.stringify(payload)) + '); true;');
  }
  async function onHomeMessage(event: {nativeEvent: {data: string; url?: string}}) {
    let msg: Message;
    try { msg = JSON.parse(event.nativeEvent.data); } catch { return; }
    if (!msg || typeof msg.type !== 'string') return;
    if (playerDocument.current) {
      if (msg.type !== 'mk-media') return;
      const label = ['playing','waiting','stalled','error','play-rejected','no-video','loadstart','loadedmetadata'].includes(msg.event || '') ? msg.event : 'unknown';
      const code = Number.isInteger(msg.code) ? Math.min(Math.max(msg.code!,0),9) : 0;
      console.info('[MKPLAY]', label, 'code=' + code, 'ready=' + Number(msg.readyState || 0), 'network=' + Number(msg.networkState || 0));
      if (label === 'playing') {setMediaStarted(true); setMediaStatus('Odtwarzanie');}
      else if (label === 'error') {
        setMediaStarted(false);
        const reasons:Record<number,string> = {1:'Przerwane odtwarzanie',2:'Błąd pobierania filmu',3:'Błąd dekodowania filmu',4:'Nieobsługiwany strumień lub brak źródła'};
        setMediaStatus((reasons[code] || 'Błąd odtwarzacza') + ' · MEDIA_ERR_' + code);
      } else if (label === 'play-rejected') {setMediaStarted(false); setMediaStatus('Player odrzucił uruchomienie. Naciśnij Play; jeśli nadal brak obrazu, wróć i wybierz inne źródło.');}
      else if (label === 'no-video') setMediaStatus('Brak zdarzeń wideo w głównym widoku źródła.');
      else if (!mediaStarted) setMediaStatus('Oczekiwanie na film…');
      return;
    }
    if (restorePending.current || (event.nativeEvent.url && event.nativeEvent.url !== HOME)) return;
    if (msg.type === 'play' || msg.type === 'open') {
      ++catalogueGeneration.current;
      for (const controller of activeRequests.current.values()) controller.abort();
      activeRequests.current.clear();
      if (msg.state && JSON.stringify(msg.state).length <= 120000) catalogueState.current = msg.state;
      setMediaStatus(''); setMediaStarted(false);
    }
    if (msg.type === 'exit') { BackHandler.exitApp(); return; }
    const url = safeUrl(msg.url);
    if (msg.type === 'play' && url && url.startsWith(SITE + '/watch/')) {
      const generation = ++resolveGeneration.current;
      sourceRequest.current?.abort();
      const controller = new AbortController(); sourceRequest.current = controller;
      setPlayback(null); setBrowserError(''); setBrowserUrl(url); setResolving(true);
      const timer = setTimeout(() => controller.abort(), 35000);
      try {
        const result = await resolveSource(url, async (page: string, referer: string) => {
          const response = await fetch(page, {signal:controller.signal, headers:{Accept:'text/html', Referer:referer, 'User-Agent':USER_AGENT}});
          if (!response.ok) throw Error('Źródło zwróciło HTTP ' + response.status);
          if (response.url && !publicUrl(response.url)) throw Error('Źródło zwróciło nieobsługiwany adres');
          const html = await response.text();
          if (html.length > 2500000) throw Error('Zbyt duża odpowiedź źródła');
          return {html, url:response.url || page};
        }, safeUrl(msg.referer) || SITE + '/');
        if (generation === resolveGeneration.current) {
          setPlayback(result); playerDocument.current = true;
          setPageSource({uri:result.kind === 'direct' ? result.referer : result.url,headers:{Referer:result.referer}});
          console.info('[MKPLAY] resolved mode=' + result.kind);
        }
      } catch (error) {
        if (generation === resolveGeneration.current) {console.info('[MKPLAY] resolve-failed'); setBrowserError(error instanceof Error && error.name !== 'AbortError' ? error.message : 'Upłynął czas otwierania źródła. Wróć i wybierz inne.');}
      } finally {
        clearTimeout(timer);
        if (generation === resolveGeneration.current) {setResolving(false); sourceRequest.current = null;}
      }
      return;
    }
    if (msg.type === 'open') {
      if (url) { ++resolveGeneration.current; sourceRequest.current?.abort(); setResolving(false); setPlayback(null); setBrowserError(''); setBrowserUrl(url); playerDocument.current = true; setPageSource({uri:url,headers:{Referer:SITE + '/'}}); }
      return;
    }
    if (msg.type !== 'fetch') return;
    const requestId = Number(msg.requestId);
    const catalogueTicket = catalogueGeneration.current;
    if (!Number.isSafeInteger(requestId) || requestId < 1 || activeRequests.current.has(requestId)) return;
    if (!url || activeRequests.current.size >= 6) {
      sendToUi({requestId, error: 'Nieprawidłowe zapytanie do katalogu'}); return;
    }
    const controller = new AbortController();
    activeRequests.current.set(requestId, controller);
    const timer = setTimeout(() => controller.abort(), 18000);
    try {
      const response = await fetch(url, {
        signal: controller.signal,
        headers: {Accept: 'text/html', 'Accept-Language': 'pl-PL,pl;q=0.9', Referer: SITE + '/'},
      });
      if (!response.ok) throw Error('Serwer zwrócił HTTP ' + response.status);
      if (response.url && !safeUrl(response.url)) throw Error('Serwis przekierował poza obsługiwany katalog');
      const html = await response.text();
      if (html.length > 2500000) throw Error('Zbyt duża odpowiedź katalogu');
      sendToUi({requestId, url: response.url || url, html}, catalogueTicket);
    } catch (error) {
      sendToUi({requestId, error: error instanceof Error ? error.message : 'Błąd połączenia'}, catalogueTicket);
    } finally {
      clearTimeout(timer); if (activeRequests.current.get(requestId) === controller) activeRequests.current.delete(requestId);
    }
  }

  function onWebLoad(event: {nativeEvent:{url?:string}}) {
    hideSplash();
    const loaded = event.nativeEvent.url || pageSource.uri;
    if (pageSource.uri === HOME && loaded === HOME && !playerDocument.current) {
      if (restorePending.current) {
        restorePending.current = false;
        homeRef.current?.injectJavaScript('window.mkRestore?.(' + JSON.stringify(catalogueState.current) + '); true;');
      }
      return;
    }
    if (playerDocument.current && loaded !== HOME) {
      homeRef.current?.injectJavaScript(playback?.kind === 'direct' ? videoScript(playback.url) : AUTO_PLAY);
      console.info('[MKPLAY] document-loaded');
    }
  }
  return (
    <View style={styles.outer}>
      <WebView
        ref={homeRef}
        style={styles.web}
        hasTVPreferredFocus
        userAgent={USER_AGENT}
        source={pageSource}
        allowSystemKeyEvents={false}
        allowsDefaultMediaControl
        domStorageEnabled
        javaScriptEnabled
        mediaPlaybackRequiresUserAction={false}
        injectedJavaScriptBeforeContentLoaded={browserUrl ? MEDIA_REPORTING : undefined}
        onMessage={onHomeMessage}
        onLoad={onWebLoad}
        onError={() => {
          hideSplash();
          if (playerDocument.current) {console.info('[MKPLAY] document-error'); setBrowserError('Nie udało się otworzyć strony odtwarzacza.');}
        }}
        onHttpError={({nativeEvent}) => {
          if (playerDocument.current && nativeEvent.isMainFrame) {
            console.info('[MKPLAY] http-error status=' + nativeEvent.statusCode);
            setBrowserError('Źródło zwróciło HTTP ' + nativeEvent.statusCode);
          }
        }}
      />
      {!!browserUrl && <View style={styles.toolbar}>
        <Pressable focusable onPress={closePlayer} onFocus={() => setBackFocused(true)} onBlur={() => setBackFocused(false)} style={[styles.back, backFocused && styles.focus]}>
          <Text style={styles.backText}>← Wróć do MK eKino</Text>
        </Pressable>
        <Text style={styles.notice}>{resolving ? 'Otwieranie źródła…' : 'Wstecz: katalog'}</Text>
      </View>}
      {!!browserUrl && (resolving || !!browserError) && <View style={styles.message}>
        <Text style={styles.error}>{browserError || 'Otwieranie źródła filmu…'}</Text>
      </View>}
      {!!browserUrl && !resolving && !browserError && !mediaStarted && !!mediaStatus && <View pointerEvents="none" style={styles.mediaStatus}>
        <Text style={styles.error}>{mediaStatus}</Text>
      </View>}
    </View>
  );
};

const styles = StyleSheet.create({
  outer: {flex: 1, backgroundColor: '#000000'},
  web: {flex: 1, backgroundColor: '#000000'},
  message: {position:'absolute',top:84,bottom:0,left:0,right:0,backgroundColor:'#000000',justifyContent:'center',alignItems:'center'},
  mediaStatus: {position:'absolute',bottom:75,left:20,right:20,backgroundColor:'#111e2a'},
  toolbar: {position:'absolute',top:0,left:0,right:0,minHeight: 72, flexDirection: 'row', alignItems: 'center', gap: 20, paddingHorizontal: 34, backgroundColor: '#111e2a'},
  back: {paddingHorizontal: 20, paddingVertical: 10, borderWidth: 2, borderColor: '#2d5962', borderRadius: 12},
  focus: {borderColor: '#46f0d3', backgroundColor: '#153c44'},
  backText: {fontSize: 21, color: 'white', fontWeight: '700'},
  notice: {fontSize: 16, color: '#9aadb5'}, error: {fontSize: 18, color: '#ff8989', padding: 12},
});
