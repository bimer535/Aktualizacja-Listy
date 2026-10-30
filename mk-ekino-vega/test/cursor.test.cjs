const test=require('node:test');
const assert=require('node:assert/strict');
const {movePointer,touchPoint}=require('../src/cursor');
test('cursor geometry scales to viewport pixels and stays inside the visible page',()=>{
  let point={x:0.5,y:0.5};const bounds={width:1280,height:720};
  point=movePointer(point,'left',bounds);point=movePointer(point,'up',bounds);
  assert.deepEqual(touchPoint(point,{width:1920,height:1080,offsetTop:300,offsetLeft:400}),{clientX:936,clientY:516});
  for(let i=0;i<200;i++)point=movePointer(movePointer(point,'left',bounds),'up',bounds);
  assert.deepEqual(point,{x:0,y:0});assert.deepEqual(touchPoint(point,{width:1920,height:1080}),{clientX:1,clientY:1});
  for(let i=0;i<200;i++)point=movePointer(movePointer(point,'right',bounds),'down',bounds);
  assert.deepEqual(touchPoint(point,{width:1920,height:1080}),{clientX:1919,clientY:1079});
  for(const viewport of [null,{width:0,height:0},{width:NaN,height:1080},{width:20000,height:1080}])assert.throws(()=>touchPoint(point,viewport),/viewport-unavailable/);
});
