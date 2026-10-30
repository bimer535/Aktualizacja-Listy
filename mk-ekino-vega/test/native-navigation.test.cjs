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
  const timers=new Map(),injected=[],logs=[],calls=[];
  const WebView=React.forwardRef((props,ref)=>{
    React.useEffect(()=>{mounts++;},[]);
    React.useImperativeHandle(ref,()=>({injectJavaScript:s=>injected.push(s),stopLoading:()=>{stopped++;}}));
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
      if(name==='@amazon-devices/react-native-kepler')return {useTVEventHandler:fn=>{tv=fn;},useHideSplashScreenCallback:()=>hideSplash,usePreventHideSplashScreen:()=>{}};
      if(name==='./playback')return {...require('../src/playback'),resolveSource:async(url,fetchPage)=>{await fetchPage(url,url);return {kind:'embed',url:HOST,referer:url};}};
      throw Error(name);
    }};
  vm.runInNewContext(code,sandbox);
  let tree;
  await renderer.act(async()=>{tree=renderer.create(React.createElement(sandbox.exports.App));});
  const web=()=>tree.root.findByType('WebView');
  const send=(message,url=HOME)=>renderer.act(async()=>{await web().props.onMessage({nativeEvent:{url,data:JSON.stringify(message)}});});
  return {tree,web,send,injected,logs,calls,timers,
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
    await h.tv({eventType:'menu',eventKeyAction:0});
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
