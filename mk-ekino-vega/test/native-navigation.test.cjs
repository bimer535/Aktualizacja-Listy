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

test('catalogue, resolving, playback, errors and Back share one continuously mounted full-size WebView', async () => {
  let mounts=0, back, release;
  const injected=[], logs=[], calls=[];
  const WebView=React.forwardRef((props,ref)=>{
    React.useEffect(()=>{mounts++;},[]);
    React.useImperativeHandle(ref,()=>({injectJavaScript:s=>injected.push(s)}));
    return React.createElement('WebView',props);
  });
  const source=fs.readFileSync(path.join(__dirname,'../src/App.tsx'),'utf8');
  const code=ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,esModuleInterop:true}}).outputText;
  const sandbox={exports:{},setTimeout,clearTimeout,AbortController,
    console:{info:(...args)=>logs.push(args.join(' '))},
    fetch:async(url)=>{calls.push(url);await new Promise(r=>{release=r;});return {ok:true,status:200,url, text:async()=>'<iframe src="https://host.example/e/video"></iframe>'};},
    require:name=>{
      if(name==='react')return React;
      if(name==='react-native')return {View:'View',Text:'Text',Pressable:'Pressable',StyleSheet:{create:x=>x},BackHandler:{addEventListener:(event,fn)=>{back=fn;return {remove(){}};},exitApp(){}}};
      if(name==='@amazon-devices/webview')return {WebView};
      if(name==='@amazon-devices/react-native-kepler')return {useHideSplashScreenCallback:()=>()=>{},usePreventHideSplashScreen:()=>{}};
      if(name==='./playback')return {...require('../src/playback'),resolveSource:async(url,fetchPage,referer)=>{await fetchPage(url,referer);return {kind:'embed',url:'https://host.example/e/video',referer:url};}};
      throw Error(name);
    }};
  vm.runInNewContext(code,sandbox);
  let tree;
  try {
    await renderer.act(async()=>{tree=renderer.create(React.createElement(sandbox.exports.App));});
    const web=()=>tree.root.findByType('WebView');
    assert.equal(web().props.source.uri,HOME);
    const state={tab:'movies',filters:{year:'2026'},selected:{url:'https://ekino.ws/movie/show/test/1',title:'Film'}};
    let task;
    await renderer.act(async()=>{task=web().props.onMessage({nativeEvent:{url:HOME,data:JSON.stringify({type:'play',url:'https://ekino.ws/watch/f/player/key',state})}});});
    assert.equal(tree.root.findAllByType('WebView').length,1);
    assert.equal(web().props.source.uri,HOME);
    await renderer.act(async()=>{release();await task;});
    assert.equal(web().props.source.uri,'https://host.example/e/video');
    assert.equal(mounts,1);assert.equal(web().props.style.flex,1);
    await renderer.act(async()=>{await web().props.onMessage({nativeEvent:{url:'https://host.example/e/video',data:JSON.stringify({type:'fetch',url:'https://ekino.ws/',requestId:100})}});});
    assert.equal(calls.length,1,'remote player must not access catalogue bridge');
    await renderer.act(async()=>{await web().props.onMessage({nativeEvent:{url:'https://host.example/e/video',data:JSON.stringify({type:'mk-media',event:'error',code:4,readyState:0,networkState:3,url:'https://secret.example/token'})}});});
    assert.ok(JSON.stringify(tree.toJSON()).includes('MEDIA_ERR_4'));
    assert.ok(logs.some(l=>l.includes('[MKPLAY] error code=4')));
    assert.ok(logs.every(l=>!l.includes('secret.example')));
    await renderer.act(async()=>{back();});
    assert.equal(web().props.source.uri,HOME);assert.equal(mounts,1);
    await renderer.act(async()=>{web().props.onLoad({nativeEvent:{url:HOME}});});
    assert.ok(injected.some(s=>s.includes('mkRestore')&&s.includes('2026')));
  } finally {if(tree)await renderer.act(async()=>tree.unmount());}
});
