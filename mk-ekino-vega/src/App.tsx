/** MK eKino for Vega OS 2.0. GPL-3.0-only. */
import React, {useCallback, useEffect, useRef, useState} from 'react';
import {BackHandler, Pressable, StyleSheet, Text, View} from 'react-native';
import {WebView} from '@amazon-devices/webview';
import {useHideSplashScreenCallback, usePreventHideSplashScreen} from '@amazon-devices/react-native-kepler';

const SITE = 'https://ekino.ws';
const HOME = 'file:///pkg/assets/index.html';
const PATHS = /^\/(?:$|movie\/|serie\/|serial\/|watch\/|search\/)/;
type Message = {type: string; requestId?: number; url?: string};

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
  const [backFocused, setBackFocused] = useState(false);
  usePreventHideSplashScreen();
  const hideSplash = useHideSplashScreenCallback();

  const closePlayer = useCallback(() => {
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
    if (msg.type === 'open') {
      if (url) { setBrowserError(''); setBrowserUrl(url); }
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
        {!!browserError && <Text style={styles.error}>{browserError}</Text>}
        <WebView
          style={styles.web}
          hasTVPreferredFocus
          source={{uri: browserUrl, headers: {Referer: SITE + '/'}}}
          allowSystemKeyEvents={false}
          allowsDefaultMediaControl
          domStorageEnabled
          javaScriptEnabled
          mediaPlaybackRequiresUserAction={false}
          onError={() => setBrowserError('Nie udało się otworzyć odtwarzacza. Wróć i wybierz inne źródło.')}
          onHttpError={({nativeEvent}) => {
            if (nativeEvent.isMainFrame) setBrowserError('Źródło zwróciło HTTP ' + nativeEvent.statusCode);
          }}
        />
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
