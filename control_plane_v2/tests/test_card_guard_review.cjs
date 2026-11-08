const fs=require('node:fs'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const source=JSON.parse(fs.readFileSync('runtime/worker-context-candidate/card-guard-review.json','utf8'));
function evaluate(code){let now=1000,handler;const document={addEventListener:(type,fn)=>handler=fn,documentElement:{setAttribute(){}}};vm.runInNewContext(code,{document,Date:{now:()=>now}},{timeout:1000});
 const card=(inGame=false)=>({id:'',className:'card',getAttribute:()=>null,closest:selector=>selector==='.card'?null:inGame?{}:null});
 const first=card(),second=card();const click=(el,t)=>{now=t;let blocked=false;handler({target:{closest:()=>el},preventDefault(){blocked=true},stopImmediatePropagation(){}});return blocked};
 return {first,second,card,click};}
const original=evaluate(source.original);original.click(original.first,1000);
const defect=original.click(original.second,1100);
test('original shared-class collision is independently reproduced',()=>assert.equal(defect,true));
test('candidate accepts two distinct cards with same class',()=>{const c=evaluate(source.candidate);assert.equal(c.click(c.first,1000),false);assert.equal(c.click(c.second,1100),false)});
test('candidate still blocks duplicate click on same card',()=>{const c=evaluate(source.candidate);c.click(c.first,1000);assert.equal(c.click(c.first,1100),true)});
test('candidate re-enables same card after interval',()=>{const c=evaluate(source.candidate);c.click(c.first,1000);assert.equal(c.click(c.first,1400),false)});
test('candidate leaves in-game targets unaffected',()=>{const c=evaluate(source.candidate);const inGame=c.card(true);assert.equal(c.click(inGame,1000),false);assert.equal(c.click(inGame,1100),false)});
