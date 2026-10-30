/** MK eKino for Vega OS 2.0. GPL-3.0-only. */
import React, {useCallback, useEffect, useRef, useState} from 'react';
import {AppState, BackHandler, Pressable, StyleSheet, Text, View} from 'react-native';
import {WebView} from '@amazon-devices/webview';
import {useHideSplashScreenCallback, usePreventHideSplashScreen, useTVEventHandler, TVFocusGuideView} from '@amazon-devices/react-native-kepler';

import {publicUrl, resolveSource, videoScript, MEDIA_REPORTING, MANUAL_PLAY_PAUSE} from './playback';
import {movePointer, touchPoint} from './cursor';

const USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36';
const SITE = 'https://ekino.ws';
const HOME = 'file:///pkg/assets/index.html';
const PATHS = /^\/(?:$|movie\/|serie\/|serial\/|watch\/|search\/)/;
type Message = {type: string; requestId?: number; url?: string; referer?: string; state?: unknown; event?: string; code?: number; readyState?: number; networkState?: number; paused?: boolean; timeMs?: number; bufferedMs?: number};

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
  const playerOpen = useRef(false);
  const lastBack = useRef(0);
  const [slowPlayer, setSlowPlayer] = useState(false);
  const [mediaAvailable, setMediaAvailable] = useState(false);
  const [playFocused, setPlayFocused] = useState(false);
  const [cataloguePhase, setCataloguePhase] = useState<'loading'|'ready'|'error'>('loading');
  const cataloguePhaseRef = useRef(cataloguePhase);
  const [rendererMounted, setRendererMounted] = useState(true);
  const restartTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [cursorMode, setCursorMode] = useState(false);
  const cursorEnabled = useRef(false);
  const [pointer, setPointer] = useState({x:0.5,y:0.5});
  const pointerRef = useRef(pointer);
  const [bounds, setBounds] = useState({width:1280,height:720});
  const boundsRef = useRef(bounds);
  const [cursorError, setCursorError] = useState('');
  const pendingTouch = useRef<{target:React.ElementRef<typeof WebView>;point:{clientX:number;clientY:number};timer:ReturnType<typeof setTimeout> | null} | null>(null);
  usePreventHideSplashScreen();
  const hideSplash = useHideSplashScreenCallback();
  const markCatalogue = useCallback((phase:'loading'|'ready'|'error') => {
    cataloguePhaseRef.current = phase; setCataloguePhase(phase);
  }, []);
  const finishTouch = useCallback(() => {
    const touch = pendingTouch.current;
    if (!touch) return;
    pendingTouch.current = null;
    if (touch.timer) clearTimeout(touch.timer);
    try {touch.target.dispatchTouchEvent({type:'touchend',touches:[touch.point]});} catch (_) {}
  }, []);
  const enableCursor = useCallback((enabled:boolean) => {
    finishTouch(); cursorEnabled.current = enabled; setCursorMode(enabled); setCursorError('');
  }, [finishTouch]);
  const clickPointer = useCallback(() => {
    if (!playerOpen.current || !playerDocument.current || !cursorEnabled.current || pendingTouch.current) return;
    const target = homeRef.current;
    if (!target) return;
    try {
      const point = touchPoint(pointerRef.current,target.getVisualViewportInfo());
      target.dispatchTouchEvent({type:'touchstart',touches:[point]});
      pendingTouch.current = {target,point,timer:null};
      pendingTouch.current.timer = setTimeout(finishTouch,80);
      console.info('[MKPLAY] cursor-click'); setCursorError('');
    } catch (_) {
      finishTouch(); console.info('[MKPLAY] cursor-click-failed');
      setCursorError('Nie udało się wysłać kliknięcia. Wstecz: katalog.');
    }
  }, [finishTouch]);

  const restartCatalogue = useCallback(() => {
    console.info('[MKPLAY] catalogue-restart');
    ++catalogueGeneration.current;
    for (const controller of activeRequests.current.values()) controller.abort();
    activeRequests.current.clear();
    restorePending.current = !!catalogueState.current;
    markCatalogue('loading'); setRendererMounted(false); setPageSource({uri:HOME});
    if (restartTimer.current) clearTimeout(restartTimer.current);
    // Return and recovery release the old renderer before creating a new one.
    restartTimer.current = setTimeout(() => {setRendererMounted(true); restartTimer.current = null;}, 300);
  }, [markCatalogue]);
  const closePlayer = useCallback(() => {
    enableCursor(false);
    playerOpen.current = false;
    ++resolveGeneration.current; ++catalogueGeneration.current;
    sourceRequest.current?.abort();
    setResolving(false); setPlayback(null);
    setBrowserUrl(null);
    setBrowserError('');
    setMediaStatus(''); setMediaStarted(false); setSlowPlayer(false); setMediaAvailable(false);
    if (playerDocument.current) {
      playerDocument.current = false;
      console.info('[MKPLAY] catalogue-requested'); restartCatalogue();
    } else homeRef.current?.injectJavaScript('window.mkPlayerClosed?.(); true;');
  }, [restartCatalogue, enableCursor]);
  const requestPlayback = useCallback(() => {
    if (!playerOpen.current || !playerDocument.current || cursorEnabled.current) return;
    console.info('[MKPLAY] native-playpause');
    homeRef.current?.injectJavaScript(MANUAL_PLAY_PAUSE);
  }, []);
  const handleBack = useCallback(() => {
      // Kepler may deliver the same press through both native subscriptions.
      const now = Date.now();
      if (now - lastBack.current < 250) return true;
      lastBack.current = now;
      if (playerOpen.current) {console.info('[MKPLAY] native-back'); closePlayer();}
      else if (cataloguePhaseRef.current !== 'ready') BackHandler.exitApp();
      else homeRef.current?.injectJavaScript('window.mkBack?.(); true;');
      return true;
  }, [closePlayer]);
  useTVEventHandler(event => {
    if (event.eventKeyAction === 1) return;
    if (playerOpen.current && playerDocument.current && event.eventType === 'menu') {
      enableCursor(!cursorEnabled.current); return;
    }
    if (playerOpen.current && cursorEnabled.current && ['up','down','left','right'].includes(event.eventType)) {
      const next = movePointer(pointerRef.current,event.eventType,boundsRef.current);
      pointerRef.current = next; setPointer(next); return;
    }
    if (playerOpen.current && event.eventType === 'playpause') {requestPlayback(); return;}
    if (event.eventType === 'back') handleBack();
  });
  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', handleBack);
    return () => sub.remove();
  }, [handleBack]);
  useEffect(() => {
    if (browserError) enableCursor(false);
  }, [browserError,enableCursor]);
  useEffect(() => {
    if (browserUrl || cataloguePhase !== 'loading' || !rendererMounted) return;
    const timer = setTimeout(() => {
      console.info('[MKPLAY] catalogue-ready-timeout'); hideSplash(); markCatalogue('error');
    }, 10000);
    return () => clearTimeout(timer);
  }, [browserUrl, cataloguePhase, rendererMounted, hideSplash, markCatalogue]);
  useEffect(() => {
    const sub = AppState.addEventListener('change', state => {
      if (state === 'active' && !playerOpen.current && cataloguePhaseRef.current !== 'ready') restartCatalogue();
    });
    return () => sub.remove();
  }, [restartCatalogue]);
  useEffect(() => {
    if (!browserUrl || mediaStarted) return;
    const timer = setTimeout(() => {
      console.info('[MKPLAY] startup-unconfirmed'); setSlowPlayer(true);
    }, 45000);
    return () => clearTimeout(timer);
  }, [browserUrl, mediaStarted]);
  useEffect(() => () => {
    finishTouch();
    if (restartTimer.current) clearTimeout(restartTimer.current);
    sourceRequest.current?.abort();
    for (const controller of activeRequests.current.values()) controller.abort();
    activeRequests.current.clear();
  }, [finishTouch]);

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
      const label = ['document-ready','manual-play','manual-pause','manual-state','manual-not-ready','play','playing','pause','canplay','ended','waiting','stalled','error','play-rejected','no-video','loadstart','loadedmetadata'].includes(msg.event || '') ? msg.event : 'unknown';
      const code = Number.isInteger(msg.code) ? Math.min(Math.max(msg.code!,0),9) : 0;
      const bounded = (n:unknown, max:number) => typeof n === 'number' && Number.isFinite(n) ? Math.min(max,Math.max(0,Math.round(n))) : 0;
      console.info('[MKPLAY]', label, 'code=' + code, 'ready=' + bounded(msg.readyState,4), 'network=' + bounded(msg.networkState,3), 'paused=' + (typeof msg.paused === 'boolean' ? Number(msg.paused) : -1), 'timeMs=' + bounded(msg.timeMs,86400000), 'bufferedMs=' + bounded(msg.bufferedMs,600000));
      if (label === 'loadedmetadata' || label === 'canplay' || label === 'playing') setMediaAvailable(true);
      if (label === 'playing') {setMediaStarted(true); setSlowPlayer(false); setMediaStatus('Odtwarzanie');}
      else if (label === 'error') {
        setMediaStarted(false);
        const reasons:Record<number,string> = {1:'Przerwane odtwarzanie',2:'Błąd pobierania filmu',3:'Błąd dekodowania filmu',4:'Nieobsługiwany strumień lub brak źródła'};
        setMediaStatus((reasons[code] || 'Błąd odtwarzacza') + ' · MEDIA_ERR_' + code);
      } else if (label === 'play-rejected') {
        setMediaStarted(false);
        const reasons:Record<number,string> = {1:'WebView zablokował rozpoczęcie odtwarzania',2:'Nieobsługiwane źródło wideo',3:'Uruchomienie filmu zostało przerwane'};
        setMediaStatus((reasons[code] || 'Nie udało się rozpocząć odtwarzania') + ' · PLAY_REJECTED_' + code);
      }
      else if (label === 'loadedmetadata' && msg.paused === true) setMediaStatus('Odczytano dane filmu. Naciśnij Play/Pauza na pilocie lub przycisk u góry.');
      else if (label === 'manual-not-ready') setMediaStatus('Player nie udostępnił jeszcze filmu. Potwierdź Play na stronie źródła.');
      else if (label === 'pause') {setMediaStarted(false); setMediaStatus('Pauza · Play/Pauza na pilocie: wznów');}
      else if (label === 'no-video') setMediaStatus('Brak zdarzeń wideo w głównym widoku źródła.');
      else if (!mediaStarted) setMediaStatus('Oczekiwanie na film…');
      return;
    }
    if (msg.type === 'ui-ready' && !playerOpen.current && (!event.nativeEvent.url || event.nativeEvent.url === HOME)) {
      console.info('[MKPLAY] catalogue-ready');
      markCatalogue('ready'); hideSplash();
      const state = restorePending.current ? catalogueState.current : null;
      restorePending.current = false;
      homeRef.current?.injectJavaScript('window.mkStart?.(' + JSON.stringify(state) + '); true;');
      return;
    }
    if (restorePending.current || (event.nativeEvent.url && event.nativeEvent.url !== HOME)) return;
    if (msg.type === 'play' || msg.type === 'open') {
      ++catalogueGeneration.current;
      for (const controller of activeRequests.current.values()) controller.abort();
      activeRequests.current.clear();
      if (msg.state && JSON.stringify(msg.state).length <= 120000) catalogueState.current = msg.state;
      setMediaStatus(''); setMediaStarted(false); setSlowPlayer(false); setMediaAvailable(false);
    }
    if (msg.type === 'exit') { BackHandler.exitApp(); return; }
    const url = safeUrl(msg.url);
    if (msg.type === 'play' && url && url.startsWith(SITE + '/watch/')) {
      const generation = ++resolveGeneration.current;
      sourceRequest.current?.abort();
      const controller = new AbortController(); sourceRequest.current = controller;
      playerOpen.current = true;
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
          pointerRef.current = {x:0.5,y:0.5}; setPointer(pointerRef.current);
          enableCursor(result.kind === 'embed');
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
      if (url) { playerOpen.current = true; ++resolveGeneration.current; sourceRequest.current?.abort(); setResolving(false); setPlayback(null); setBrowserError(''); setBrowserUrl(url); playerDocument.current = true; enableCursor(true); setPageSource({uri:url,headers:{Referer:SITE + '/'}}); }
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
      console.info('[MKPLAY] catalogue-document-loaded');
      homeRef.current?.injectJavaScript('window.mkReady?.(); true;');
      return;
    }
    if (playerDocument.current && loaded !== HOME) {
      // Embedded providers own their controls, focus and playback lifecycle.
      // Observe them without replacing controls or forcing video.play().
      homeRef.current?.injectJavaScript(playback?.kind === 'direct' ? videoScript(playback.url) : MEDIA_REPORTING);
      console.info('[MKPLAY] document-loaded');
    }
  }
  return (
    <View style={styles.outer} onLayout={({nativeEvent:{layout}}) => {
      if (layout.width > 0 && layout.height > 0) {const size = {width:layout.width,height:layout.height}; boundsRef.current = size; setBounds(size);}
    }}>
      {rendererMounted && <WebView
        // Keep the surface on entry. Return releases it before mounting the
        // catalogue after a gap; never recreate Chromium in the same commit.
        ref={homeRef}
        style={styles.web}
        focusable={!cursorMode}
        hasTVPreferredFocus={!cursorMode}
        userAgent={USER_AGENT}
        source={pageSource}
        allowSystemKeyEvents={false}
        allowsDefaultMediaControl={false}
        domStorageEnabled
        thirdPartyCookiesEnabled
        javaScriptEnabled
        mediaPlaybackRequiresUserAction={false}
        injectedJavaScriptBeforeContentLoaded={browserUrl ? MEDIA_REPORTING : undefined}
        onMessage={onHomeMessage}
        onLoad={onWebLoad}
        onError={() => {
          hideSplash();
          if (playerDocument.current) {console.info('[MKPLAY] document-error'); setBrowserError('Nie udało się otworzyć strony odtwarzacza.');}
          else {console.info('[MKPLAY] catalogue-document-error'); markCatalogue('error');}
        }}
        onHttpError={({nativeEvent}) => {
          if (playerDocument.current && nativeEvent.isMainFrame) {
            console.info('[MKPLAY] http-error status=' + nativeEvent.statusCode);
            setBrowserError('Źródło zwróciło HTTP ' + nativeEvent.statusCode);
          }
        }}
      />}
      {!browserUrl && cataloguePhase !== 'ready' && <View style={styles.recovery}>
        <Text style={styles.backText}>MK eKino</Text>
        <Text style={styles.error}>{cataloguePhase === 'loading' ? 'Ładowanie katalogu…' : 'Katalog nie odpowiedział. Ponów wczytywanie lub zamknij aplikację.'}</Text>
        {cataloguePhase === 'error' && <Pressable focusable hasTVPreferredFocus onPress={restartCatalogue} style={styles.back}>
          <Text style={styles.backText}>Ponów wczytywanie katalogu</Text>
        </Pressable>}
        <Pressable focusable hasTVPreferredFocus={cataloguePhase === 'loading'} onPress={() => BackHandler.exitApp()} style={styles.back}>
          <Text style={styles.backText}>Zamknij aplikację</Text>
        </Pressable>
      </View>}
      {!!browserUrl && !cursorMode && <View style={styles.toolbar}>
        <Pressable focusable hasTVPreferredFocus={slowPlayer || !!browserError} onPress={closePlayer} onFocus={() => setBackFocused(true)} onBlur={() => setBackFocused(false)} style={[styles.back, backFocused && styles.focus]}>
          <Text style={styles.backText}>← Wróć do MK eKino</Text>
        </Pressable>
        {mediaAvailable && <Pressable focusable onPress={requestPlayback} onFocus={() => setPlayFocused(true)} onBlur={() => setPlayFocused(false)} style={[styles.back,playFocused && styles.focus]}>
          <Text style={styles.backText}>▶ Play / Pauza</Text>
        </Pressable>}
        {!resolving && <Pressable focusable onPress={() => enableCursor(true)} style={styles.back}><Text style={styles.backText}>Kursor</Text></Pressable>}
        <Text style={styles.notice}>{resolving ? 'Otwieranie źródła…' : 'Wstecz: katalog · Menu: kursor'}</Text>
      </View>}
      {!!browserUrl && (resolving || !!browserError) && <View style={styles.message}>
        <Text style={styles.error}>{browserError || 'Otwieranie źródła filmu…'}</Text>
      </View>}
      {!!browserUrl && !cursorMode && !resolving && !browserError && !mediaStarted && (!!mediaStatus || slowPlayer) && <View pointerEvents="none" style={styles.mediaStatus}>
        <Text style={styles.error}>{slowPlayer ? 'Brak potwierdzenia odtwarzania po 45 s. Wstecz lub Menu: wróć do źródeł. ' + mediaStatus : mediaStatus}</Text>
      </View>}
      {!!browserUrl && cursorMode && !resolving && !browserError && <TVFocusGuideView autoFocus trapFocusUp trapFocusDown trapFocusLeft trapFocusRight style={styles.cursorLayer}>
        <Pressable focusable hasTVPreferredFocus accessibilityLabel="Kursor: strzałki przesuwają, OK klika, Menu przełącza tryb" onPress={clickPointer} style={styles.cursorCapture}>
          <View pointerEvents="none" style={[styles.cursor,{left:pointer.x*bounds.width-12,top:pointer.y*bounds.height-12}]}>
            <View style={styles.cursorDot}/>
          </View>
          <View pointerEvents="none" style={styles.cursorHint}><Text style={styles.cursorHintText}>{cursorError || 'Kursor · Strzałki: ruch · OK: klik · Menu: zmień tryb · Wstecz: katalog'}</Text></View>
        </Pressable>
      </TVFocusGuideView>}
    </View>
  );
};

const styles = StyleSheet.create({
  outer: {flex: 1, backgroundColor: '#000000'},
  web: {flex: 1, backgroundColor: '#000000'},
  cursorLayer: {position:'absolute',top:0,bottom:0,left:0,right:0},
  cursorCapture: {flex:1},
  cursor: {position:'absolute',width:24,height:24,borderRadius:12,borderWidth:3,borderColor:'#31e4cc',backgroundColor:'#10233288',justifyContent:'center',alignItems:'center'},
  cursorDot: {width:4,height:4,borderRadius:2,backgroundColor:'#ffffff'},
  cursorHint: {position:'absolute',bottom:14,left:24,right:24,backgroundColor:'#102332',padding:10,borderRadius:8},
  cursorHintText: {fontSize:18,color:'#ffffff',textAlign:'center'},
  recovery: {position:'absolute',top:0,bottom:0,left:0,right:0,backgroundColor:'#111e2a',justifyContent:'center',alignItems:'center',gap:20},
  message: {position:'absolute',top:84,bottom:0,left:0,right:0,backgroundColor:'#000000',justifyContent:'center',alignItems:'center'},
  mediaStatus: {position:'absolute',bottom:75,left:20,right:20,backgroundColor:'#111e2a'},
  toolbar: {position:'absolute',top:0,left:0,right:0,minHeight: 72, flexDirection: 'row', alignItems: 'center', gap: 20, paddingHorizontal: 34, backgroundColor: '#111e2a'},
  back: {paddingHorizontal: 20, paddingVertical: 10, borderWidth: 2, borderColor: '#2d5962', borderRadius: 12},
  focus: {borderColor: '#46f0d3', backgroundColor: '#153c44'},
  backText: {fontSize: 21, color: 'white', fontWeight: '700'},
  notice: {fontSize: 16, color: '#9aadb5'}, error: {fontSize: 18, color: '#ff8989', padding: 12},
});
