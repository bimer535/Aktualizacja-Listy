/** MK eKino for Vega OS 2.0. GPL-3.0-only. */
import React, {useCallback, useEffect, useRef, useState} from 'react';
import {BackHandler, Pressable, StyleSheet, Text, View} from 'react-native';
import {WebView} from '@amazon-devices/webview';
import {useHideSplashScreenCallback, usePreventHideSplashScreen} from '@amazon-devices/react-native-kepler';

import {publicUrl, resolveSource, AUTO_PLAY, videoScript} from './playback';

const USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36';
const SITE = 'https://ekino.ws';
const HOME = 'file:///pkg/assets/index.html';
const PATHS = /^\/(?:$|movie\/|serie\/|serial\/|watch\/|search\/)/;
type Message = {type: string; requestId?: number; url?: string; referer?: string};

function safeUrl(input: unknown): string | null {
  if (typeof input !== 'string' || !input || input.length > 2048) return null;
  // RN's URL implementation does not implement browser URL properties fully.
  if (!input.startsWith(SITE + '/') || /[\\\s\u0000-\u001f]/.test(input)) return null;
  const pathname = input.slice(SITE.length).split(/[?#]/, 1)[0];
  return PATHS.test(pathname) ? input : null;
}

export const App = () => {
  const homeRef = useRef<React.ElementRef<typeof WebView>>(null);
  const activeRequests = useRef(new Map<number, AbortController>());
  const [browserUrl, setBrowserUrl] = useState<string | null>(null);
  const [browserError, setBrowserError] = useState('');
  const [resolving, setResolving] = useState(false);
  const [playback, setPlayback] = useState<{kind:string;url:string;referer:string} | null>(null);
  const resolveGeneration = useRef(0);
  const sourceRequest = useRef<AbortController | null>(null);
  const playerRef = useRef<React.ElementRef<typeof WebView>>(null);
  const [backFocused, setBackFocused] = useState(false);
  usePreventHideSplashScreen();
  const hideSplash = useHideSplashScreenCallback();

  const closePlayer = useCallback(() => {
    ++resolveGeneration.current;
    sourceRequest.current?.abort();
    setResolving(false); setPlayback(null);
    setBrowserUrl(null);
    setBrowserError('');
    homeRef.current?.injectJavaScript('window.mkPlayerClosed?.(); true;');
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

  function sendToUi(payload: object) {
    homeRef.current?.injectJavaScript('window.mkReceive(' + JSON.stringify(JSON.stringify(payload)) + '); true;');
  }
  async function onHomeMessage(event: {nativeEvent: {data: string; url?: string}}) {
    if (event.nativeEvent.url && event.nativeEvent.url !== HOME) return;
    let msg: Message;
    try { msg = JSON.parse(event.nativeEvent.data); } catch { return; }
    if (!msg || typeof msg.type !== 'string') return;
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
        if (generation === resolveGeneration.current) setPlayback(result);
      } catch (error) {
        if (generation === resolveGeneration.current) setBrowserError(error instanceof Error && error.name !== 'AbortError' ? error.message : 'Upłynął czas otwierania źródła. Wróć i wybierz inne.');
      } finally {
        clearTimeout(timer);
        if (generation === resolveGeneration.current) {setResolving(false); sourceRequest.current = null;}
      }
      return;
    }
    if (msg.type === 'open') {
      if (url) { ++resolveGeneration.current; sourceRequest.current?.abort(); setResolving(false); setPlayback(null); setBrowserError(''); setBrowserUrl(url); }
      return;
    }
    if (msg.type !== 'fetch') return;
    const requestId = Number(msg.requestId);
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
      sendToUi({requestId, url: response.url || url, html});
    } catch (error) {
      sendToUi({requestId, error: error instanceof Error ? error.message : 'Błąd połączenia'});
    } finally {
      clearTimeout(timer); activeRequests.current.delete(requestId);
    }
  }

  return (
    <View style={styles.outer}>
      <View style={browserUrl ? styles.hidden : styles.content}>
        <WebView
          ref={homeRef}
          style={styles.web}
          hasTVPreferredFocus={!browserUrl}
          source={{uri: HOME}}
          allowSystemKeyEvents={false}
          domStorageEnabled
          javaScriptEnabled
          onMessage={onHomeMessage}
          onLoad={() => hideSplash()}
          onError={() => hideSplash()}
        />
      </View>
      {!!browserUrl && <View style={styles.playerLayer}>
        <View style={styles.toolbar}>
          <Pressable focusable onPress={closePlayer} onFocus={() => setBackFocused(true)} onBlur={() => setBackFocused(false)} style={[styles.back, backFocused && styles.focus]}>
            <Text style={styles.backText}>← Wróć do MK eKino</Text>
          </Pressable>
          <Text style={styles.notice}>Wstecz na pilocie: powrót do katalogu</Text>
        </View>
        {resolving && <Text style={styles.notice}>Otwieranie źródła filmu…</Text>}
        {!!browserError && <Text style={styles.error}>{browserError}</Text>}
        {!resolving && !browserError && <WebView
          ref={playerRef}
          style={styles.web}
          hasTVPreferredFocus
          userAgent={USER_AGENT}
          source={{uri: playback?.kind === 'direct' ? playback.referer : playback?.url || browserUrl, headers: {Referer: playback?.referer || SITE + '/'}}}
          onLoad={() => playerRef.current?.injectJavaScript(playback?.kind === 'direct' ? videoScript(playback.url) : AUTO_PLAY)}
          allowSystemKeyEvents={false}
          allowsDefaultMediaControl
          domStorageEnabled
          javaScriptEnabled
          mediaPlaybackRequiresUserAction={false}
          onError={() => setBrowserError('Nie udało się otworzyć odtwarzacza. Wróć i wybierz inne źródło.')}
          onHttpError={({nativeEvent}) => {
            if (nativeEvent.isMainFrame) setBrowserError('Źródło zwróciło HTTP ' + nativeEvent.statusCode);
          }}
        />}
      </View>}
    </View>
  );
};

const styles = StyleSheet.create({
  outer: {flex: 1, backgroundColor: '#09111b'}, content: {flex: 1},
  web: {flex: 1, backgroundColor: '#000000'},
  hidden: {height: 0, width: 0, overflow: 'hidden'},
  playerLayer: {position: 'absolute', top: 0, bottom: 0, left: 0, right: 0, backgroundColor: '#000000'},
  toolbar: {minHeight: 72, flexDirection: 'row', alignItems: 'center', gap: 20, paddingHorizontal: 34, backgroundColor: '#111e2a'},
  back: {paddingHorizontal: 20, paddingVertical: 10, borderWidth: 2, borderColor: '#2d5962', borderRadius: 12},
  focus: {borderColor: '#46f0d3', backgroundColor: '#153c44'},
  backText: {fontSize: 21, color: 'white', fontWeight: '700'},
  notice: {fontSize: 16, color: '#9aadb5'}, error: {fontSize: 18, color: '#ff8989', padding: 12},
});
