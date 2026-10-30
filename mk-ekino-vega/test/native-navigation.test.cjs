const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const React = require('react');
const renderer = require('react-test-renderer');
global.IS_REACT_ACT_ENVIRONMENT = true;
const HOME = 'file:///pkg/assets/index.html';
const HOST = 'https://host.example/e/video';
const source=fs.readFileSync(path.join(__dirname,'../src/App.tsx'),'utf8');
const code=ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,esModuleInterop:true}}).outputText;
const state={tab:'movies',filters:{year:'2026'},selected:{url:'https://ekino.ws/movie/show/test/1',title:'Film'}};
async function harness() {
  let mounts=0, back, tv, foreground, release, stopped=0, exits=0, clock=10000, nextTimer=0;
  let viewport={width:1920,height:1080,offsetTop:100,offsetLeft:50};const touches=[];
  const timers=new Map(),injected=[],logs=[],calls=[];
  const WebView=React.forwardRef((props,ref)=>{
    React.useEffect(()=>{mounts++;},[]);
    React.useImperativeHandle(ref,()=>({injectJavaScript:s=>injected.push(s),stopLoading:()=>{stopped++;},getVisualViewportInfo:()=>viewport,dispatchTouchEvent:e=>touches.push(e)}));
    return React.createElement('WebView',props);
  });
  const hideSplash=()=>{};
  const sandbox={exports:{},setTimeout:(fn,ms)=>{const id=++nextTimer;timers.set(id,{fn,ms});return id;},clearTimeout:id=>timers.delete(id),AbortController,Date:{now:()=>clock},
    console:{info:(...args)=>logs.push(args.join(' '))},
    fetch:async(url)=>{calls.push(url);await new Promise(r=>{release=r;});return {ok:true,status:200,url,text:async()=>'<iframe src="'+HOST+'"></iframe>'};},
    require:name=>{
      if(name==='react')return React;
      if(name==='react-native')return {View:'View',Text:'Text',Pressable:'Pressable',StyleSheet:{create:x=>x},AppState:{addEventListener:(event,fn)=>{foreground=fn;return {remove(){}};}},BackHandler:{addEventListener:(event,fn)=>{back=fn;return {remove(){}};},exitApp:()=>exits++}};
      if(name==='@amazon-devices/webview')return {WebView};
      if(name==='@amazon-devices/react-native-kepler')return {TVFocusGuideView:'TVFocusGuideView',useTVEventHandler:fn=>{tv=fn;},useHideSplashScreenCallback:()=>hideSplash,usePreventHideSplashScreen:()=>{}};
      if(name==='./cursor')return require('../src/cursor');
      if(name==='./playback')return {...require('../src/playback'),resolveSource:async(url,fetchPage)=>{await fetchPage(url,url);return {kind:'embed',url:HOST,referer:url};}};
      throw Error(name);
    }};
  vm.runInNewContext(code,sandbox);
  let tree;
  await renderer.act(async()=>{tree=renderer.create(React.createElement(sandbox.exports.App));});
  const web=()=>tree.root.findByType('WebView');
  const send=(message,url=HOME)=>renderer.act(async()=>{await web().props.onMessage({nativeEvent:{url,data:JSON.stringify(message)}});});
  return {tree,web,send,injected,logs,calls,timers,touches,setViewport:v=>{viewport=v;},
    mounts:()=>mounts,stopped:()=>stopped,exits:()=>exits,
    back:()=>renderer.act(async()=>{back();}),
    tv:event=>renderer.act(async()=>{tv(event);}),
    foreground:()=>renderer.act(async()=>{foreground('active');}),
    advance:()=>{clock+=1000;},
    tick:ms=>renderer.act(async()=>{const entry=[...timers.entries()].find(([id,t])=>t.ms===ms);assert.ok(entry,'expected timer '+ms);timers.delete(entry[0]);entry[1].fn();}),
    begin:async()=>{let task;await renderer.act(async()=>{task=web().props.onMessage({nativeEvent:{url:HOME,data:JSON.stringify({type:'play',url:'https://ekino.ws/watch/f/player/key',state})}});});return {finish:()=>renderer.act(async()=>{release();await task;})};},
    cleanup:()=>renderer.act(async()=>tree.unmount())};
}
test('player return releases the old renderer before recreating the catalogue and restoring its state',async()=>{
  const h=await harness();
  try {
    await h.send({type:'ui-ready'});
    const task=await h.begin();await task.finish();
    assert.equal(h.web().props.source.uri,HOST);assert.equal(h.mounts(),1);
    assert.equal(h.web().props.allowSystemKeyEvents,false);
    assert.equal(h.web().props.thirdPartyCookiesEnabled,true);
    assert.equal(h.web().props.allowsDefaultMediaControl,false,'native Play has one controller, without a second default media toggle');
    assert.equal(h.web().props.mediaPlaybackRequiresUserAction,false,'host may start video after asynchronous manual confirmation');
    await renderer.act(async()=>h.web().props.onLoad({nativeEvent:{url:HOST}}));
    assert.ok(h.injected.every(s=>!s.includes('v.controls=true')&&!s.includes('v.play()')));
    await h.tv({eventType:'menu',eventKeyAction:0});
    await h.send({type:'mk-media',event:'loadedmetadata',readyState:1,paused:true},HOST);
    const playButton=h.tree.root.findAllByType('Pressable').find(p=>p.findByType('Text').props.children.includes('Play / Pauza'));
    assert.ok(playButton);
    const beforePlay=h.injected.length;
    await h.tv({eventType:'playpause',eventKeyAction:1});assert.equal(h.injected.length,beforePlay);
    await h.tv({eventType:'playpause',eventKeyAction:0});
    assert.ok(h.injected.at(-1).includes("window.mkReport('manual-play'"));
    await h.tick(45000);
    assert.ok(JSON.stringify(h.tree.toJSON()).includes('Brak potwierdzenia odtwarzania po 45 s'));
    await h.send({type:'fetch',url:'https://ekino.ws/',requestId:100},HOST);
    assert.equal(h.calls.length,1,'host cannot access catalogue bridge');
    await h.send({type:'mk-media',event:'error',code:4,url:'https://secret.example/token'},HOST);
    assert.ok(JSON.stringify(h.tree.toJSON()).includes('MEDIA_ERR_4'));
    assert.ok(h.logs.every(l=>!l.includes('secret.example')));
    await h.back();
    assert.equal(h.tree.root.findAllByType('WebView').length,0);
    await h.tick(300);
    assert.equal(h.web().props.source.uri,HOME);assert.equal(h.mounts(),2);
    assert.equal(h.stopped(),0,'stopLoading must not race the catalogue navigation');
    assert.ok(JSON.stringify(h.tree.toJSON()).includes('Ładowanie katalogu…'));
    await h.back();assert.equal(h.exits(),0,'duplicate native event ignored');
    const previous=h.injected.length;
    await renderer.act(async()=>h.web().props.onLoad({nativeEvent:{url:HOME}}));
    assert.ok(h.injected.slice(previous).every(s=>!s.includes('2026')),'onLoad is not evidence of JS readiness');
    await h.send({type:'ui-ready'});
    assert.ok(h.injected.some(s=>s.includes('mkStart')&&s.includes('2026')));
    assert.equal(JSON.stringify(h.tree.toJSON()).includes('Ładowanie katalogu…'),false);
    h.advance();const cancelled=await h.begin();await h.back();await cancelled.finish();
    assert.equal(h.web().props.source.uri,HOME);assert.equal(h.mounts(),2);
  } finally {await h.cleanup();}
});
test('missing catalogue readiness exposes native retry/exit and recreates renderer only after a gap',async()=>{
  const h=await harness();
  try {
    await renderer.act(async()=>h.web().props.onLoad({nativeEvent:{url:HOME}}));
    await h.tick(10000);
    assert.ok(JSON.stringify(h.tree.toJSON()).includes('Katalog nie odpowiedział'));
    const retry=h.tree.root.findAllByType('Pressable').find(p=>p.findByType('Text').props.children.includes('Ponów'));
    await renderer.act(async()=>retry.props.onPress());
    assert.equal(h.tree.root.findAllByType('WebView').length,0,'old renderer is released first');
    assert.ok(JSON.stringify(h.tree.toJSON()).includes('Zamknij aplikację'));
    await h.tick(300);assert.equal(h.mounts(),2);
    await h.send({type:'ui-ready'});
    assert.equal(JSON.stringify(h.tree.toJSON()).includes('Katalog nie odpowiedział'),false);
    assert.equal(h.timers.size,0);
  } finally {await h.cleanup();}
});
test('reentering an unready application retries catalogue, and Back can exit without web JavaScript',async()=>{
  const h=await harness();
  try {
    await h.tick(10000);await h.foreground();
    assert.equal(h.tree.root.findAllByType('WebView').length,0);
    await h.tick(300);assert.equal(h.mounts(),2);
    await h.back();assert.equal(h.exits(),1);
    assert.ok(h.injected.every(s=>!s.includes('mkBack')));
  } finally {await h.cleanup();}
});

test('manual cursor captures focus, moves with arrows and sends one native touch pair per OK',async()=>{
  const h=await harness();
  try {
    await h.send({type:'ui-ready'});const task=await h.begin();await task.finish();
    assert.equal(h.web().props.focusable,false);
    const guide=h.tree.root.findByType('TVFocusGuideView');
    assert.equal(guide.props.trapFocusLeft,true);assert.equal(guide.props.trapFocusRight,true);
    assert.equal(h.touches.length,0,'no click on page load');
    const cursorButton=()=>h.tree.root.findAllByType('Pressable').find(p=>p.props.accessibilityLabel?.startsWith('Kursor:'));
    assert.equal(cursorButton().props.hasTVPreferredFocus,true);
    await h.tv({eventType:'right',eventKeyAction:0});
    await h.tv({eventType:'right',eventKeyAction:1});
    await h.tv({eventType:'down',eventKeyAction:0});
    assert.equal(h.touches.length,0,'movement and release must never click');
    await renderer.act(async()=>cursorButton().props.onPress());
    assert.equal(h.touches.length,1);assert.equal(h.touches[0].type,'touchstart');
    assert.equal(h.touches[0].touches[0].clientX,984);assert.equal(h.touches[0].touches[0].clientY,564);
    await renderer.act(async()=>cursorButton().props.onPress());assert.equal(h.touches.length,1,'ignore duplicate activation during a touch');
    await h.tick(80);assert.equal(h.touches.length,2);assert.equal(h.touches[1].type,'touchend');
    assert.deepEqual(h.touches[0].touches,h.touches[1].touches);
    await h.tv({eventType:'menu',eventKeyAction:0});assert.equal(h.web().props.focusable,true);
    assert.equal(h.tree.root.findAllByType('TVFocusGuideView').length,0);
    assert.equal(h.mounts(),1,'toggling cursor must not recreate the renderer');
    await h.tv({eventType:'menu',eventKeyAction:0});assert.equal(h.web().props.focusable,false);
    await renderer.act(async()=>cursorButton().props.onPress());
    await h.back();assert.equal(h.touches.at(-1).type,'touchend','Back releases pending touch before unmount');
    assert.equal([...h.timers.values()].some(t=>t.ms===80),false);
  } finally {await h.cleanup();}
});
test('cursor fails visibly without a valid viewport and never guesses a click position',async()=>{
  const h=await harness();
  try {
    await h.send({type:'ui-ready'});const task=await h.begin();await task.finish();
    h.setViewport({width:0,height:0});
    const button=h.tree.root.findAllByType('Pressable').find(p=>p.props.accessibilityLabel?.startsWith('Kursor:'));
    await renderer.act(async()=>button.props.onPress());
    assert.equal(h.touches.length,0);
    assert.ok(JSON.stringify(h.tree.toJSON()).includes('Nie udało się wysłać kliknięcia'));
  } finally {await h.cleanup();}
});

test('provider errors preserve the WebView and cursor, redact details and clear after media recovers',async()=>{
  const h=await harness();
  try {
    await h.send({type:'ui-ready'});const task=await h.begin();await task.finish();
    await renderer.act(async()=>h.web().props.onError({nativeEvent:{code:-3,description:'net::ERR_ABORTED https://secret.example/token',url:HOST}}));
    assert.equal(JSON.stringify(h.tree.toJSON()).includes('Błąd strony źródła'),false);
    await renderer.act(async()=>h.web().props.onError({nativeEvent:{code:-2,description:'net::ERR_FAILED https://secret.example/token',url:HOST}}));
    assert.equal(h.tree.root.findAllByType('TVFocusGuideView').length,1);
    assert.equal(h.web().props.source.uri,HOST);assert.equal(h.mounts(),1);
    assert.ok(JSON.stringify(h.tree.toJSON()).includes('Błąd strony źródła'));
    assert.equal(JSON.stringify(h.tree.toJSON()).includes('Nie udało się otworzyć strony odtwarzacza'),false);
    assert.ok(h.logs.some(l=>l.includes('document-error code=-2 reason=ERR_FAILED')));
    assert.ok(h.logs.every(l=>!l.includes('secret.example')));
    await h.send({type:'mk-media',event:'canplay',readyState:4,paused:true},HOST);
    assert.equal(JSON.stringify(h.tree.toJSON()).includes('Błąd strony źródła'),false);
    const cursor=h.tree.root.findAllByType('Pressable').find(p=>p.props.accessibilityLabel?.startsWith('Kursor:'));
    await renderer.act(async()=>cursor.props.onPress());assert.equal(h.touches.length,1);
    await h.tick(80);assert.equal(h.touches.length,2);
  } finally {await h.cleanup();}
});
test('HTTP errors remain nonblocking and preserve manual input',async()=>{
  const h=await harness();
  try {
    await h.send({type:'ui-ready'});const task=await h.begin();await task.finish();
    await renderer.act(async()=>h.web().props.onHttpError({nativeEvent:{statusCode:403,isMainFrame:false,url:HOST}}));
    assert.equal(JSON.stringify(h.tree.toJSON()).includes('Błąd strony źródła'),false);
    await renderer.act(async()=>h.web().props.onHttpError({nativeEvent:{statusCode:503,isMainFrame:true,url:HOST}}));
    assert.ok(JSON.stringify(h.tree.toJSON()).includes('HTTP 503'));
    assert.equal(h.tree.root.findAllByType('TVFocusGuideView').length,1);
    assert.equal(h.web().props.source.uri,HOST);
  } finally {await h.cleanup();}
});
