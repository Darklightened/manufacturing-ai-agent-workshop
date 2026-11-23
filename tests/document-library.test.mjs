import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync} from 'node:fs';
import {appendDocument,emptyLibrary,EXAMPLES,LIMITS,prepareDocument,removeDocument,safeFilename,safeLocalUrl,scopeFor,summaryText,validateLibrary} from '../packages/document-library/store.mjs';
import {DocumentLibrary} from '../packages/document-library/ui.mjs';
const base={filename:'검수조서.html',content:'<html><body>실습 예제</body></html>',mime:'text/html',scenarioId:'measurement_input_demo',title:'표준형 검수조서',summary:'충족 3 / 불일치 0'};
const make=(n=1,patch={})=>prepareDocument({...base,...patch},{id:`doc-${n}`,now:new Date('2026-11-23T12:00:00.000Z')});

test('Document record preserves exact downloaded Blob, type, bytes, identity and timestamp',async()=>{
 const binary=new Blob([new Uint8Array([0,1,2,255])],{type:'application/octet-stream'}),entry=make(1,{content:binary,filename:'검수.docx'});
 assert.equal(entry.blob,binary);assert.equal(entry.blob.type,'application/octet-stream');assert.deepEqual([...new Uint8Array(await entry.blob.arrayBuffer())],[0,1,2,255]);
 assert.equal(entry.kind,'docx');assert.equal(entry.scope,'lab2');assert.equal(entry.createdAt,'2026-11-23T12:00:00.000Z');assert.equal(entry.size,4);
 assert.equal(validateLibrary(structuredClone(appendDocument(emptyLibrary(),entry))).entries[0].size,4);
});
test('String and typed binary sources remain unmodified and are bound to file extension',async()=>{
 const html=make();assert.equal(await html.blob.text(),base.content);
 const bytes=new Uint8Array([1,2,3]),entry=make(2,{filename:'inspection.sqlite',content:bytes});assert.deepEqual([...new Uint8Array(await entry.blob.arrayBuffer())],[1,2,3]);assert.equal(entry.kind,'sqlite');
 assert.throws(()=>make(3,{content:{value:1}}),/내용 형식/);
});
test('Unsafe filenames, unsupported extensions and malformed scopes are rejected',()=>{
 for(const filename of ['../x.html','a/b.json','a\\b.html','%2e%2e%2fx.json','http:x.html','a<script>.html','a\n.json','.hidden.html','x.exe','x.zip','x.pdf',' x.html','x%.html','a'.repeat(181)+'.html'])assert.throws(()=>safeFilename(filename),filename);
 for(const scenarioId of ['../foo','<script>','x y','',null])assert.throws(()=>make(1,{scenarioId}));
 assert.equal(safeFilename('작업_보고서-01.HTML'),'작업_보고서-01.HTML');assert.equal(scopeFor('electronics_demo'),'lab1');assert.equal(scopeFor('mechanical_demo'),'lab3');assert.equal(scopeFor('custom_case'),'other');
});
test('Sample links are existing local public examples and never remote/traversing URLs',()=>{
 for(const url of ['https://evil/x.html','//evil/x.html','docs/../x.html','docs/%2e%2e/x.html','javascript:alert(1)','file:///x.html','docs/x.html?next=evil','/docs/x.html','docs/x%00.html'])assert.throws(()=>safeLocalUrl(url),url);
 assert.equal(EXAMPLES.length,8);for(const entry of EXAMPLES){safeLocalUrl(entry.url);assert.ok(existsSync(new URL('../'+entry.url,import.meta.url)),entry.url);}
 assert.ok(EXAMPLES.some(e=>e.kind==='docx')&&EXAMPLES.some(e=>e.kind==='pdf'));
});
test('Same filename creates separate records and cannot overwrite an existing entry id',()=>{
 const first=make(1),second=make(2),state=appendDocument(appendDocument(emptyLibrary(),first),second);
 assert.equal(state.entries.length,2);assert.equal(state.entries[0].filename,state.entries[1].filename);assert.notEqual(state.entries[0].id,state.entries[1].id);assert.throws(()=>appendDocument(state,first),/덮어쓸/);
 const next=removeDocument(state,'doc-2');assert.equal(next.entries.length,1);assert.equal(state.entries.length,2);assert.throws(()=>removeDocument(next,'missing'),/찾지/);
});
test('Individual size, aggregate size and entry caps reject rather than deleting old data',()=>{
 const large=new Blob([new Uint8Array(LIMITS.fileBytes)]);assert.throws(()=>make(1,{content:new Blob([large,'x'])}),/25 MB/);
 let state=emptyLibrary();for(let i=0;i<4;i++)state=appendDocument(state,make(i,{content:large}));assert.throws(()=>appendDocument(state,make(5,{content:'x'})),/100 MB/);assert.equal(state.entries.length,4);
 let many=emptyLibrary();for(let i=0;i<100;i++)many=appendDocument(many,make(i,{content:''}));assert.throws(()=>appendDocument(many,make(101,{content:''})),/100개/);assert.equal(many.entries.length,100);
});
test('Corrupt persisted state is rejected without silently returning an empty replacement',()=>{
 const state=appendDocument(emptyLibrary(),make());for(const change of [s=>s.schemaVersion=2,s=>s.entries[0].size=123,s=>s.entries[0].scope='lab1',s=>s.entries[0].kind='json',s=>s.entries[0].createdAt='nonsense',s=>s.entries[0].blob={},s=>s.entries.push(s.entries[0])]){
  const bad=structuredClone(state);change(bad);assert.throws(()=>validateLibrary(bad));
 }
 assert.deepEqual(validateLibrary(null),emptyLibrary());
});
test('Summary values are bounded plain text and do not evaluate markup',()=>{
 assert.equal(summaryText('<img onerror=alert(1)>'),'<img onerror=alert(1)>');assert.equal(summaryText({pass:true,met:3}),'{'+'"pass":true,"met":3}');assert.equal(summaryText('x'.repeat(600)).length,500);
 const cyclic={};cyclic.self=cyclic;assert.equal(summaryText(cyclic),'요약 정보 없음');assert.equal(make(1,{title:'<script>alert(1)</script>'}).title,'<script>alert(1)</script>');
});
test('Concurrent captures serialize independent writes and never use current-session storage',async()=>{
 let state=null;const writes=[],toasts=[];const lib=new DocumentLibrary({main:null,read:async()=>state,write:async value=>{await Promise.resolve();state=structuredClone(value);writes.push(state);},toast:x=>toasts.push(x)});
 const result=await Promise.all([lib.capture(base),lib.capture(base),lib.capture({...base,filename:'records.json',content:'{}'})]);assert.ok(result.every(r=>r.ok));assert.equal(new Set(result.map(r=>r.id)).size,3);assert.equal(state.entries.length,3);assert.equal(writes.length,3);assert.deepEqual(toasts,[]);assert.deepEqual(Object.keys(state),['schemaVersion','entries']);
});
test('Capture storage failure is surfaced and does not throw or pretend it was saved',async()=>{
 const messages=[];let writes=0;const lib=new DocumentLibrary({main:null,read:async()=>null,write:async()=>{writes++;throw new Error('quota');},toast:x=>messages.push(x)});
 const result=await lib.capture(base);assert.equal(result.ok,false);assert.match(result.error,/quota/);assert.equal(messages.length,1);assert.equal(writes,1);
 const corrupt=new DocumentLibrary({main:null,read:async()=>({schemaVersion:99}),write:async()=>{throw new Error('must not write');},toast:x=>messages.push(x)});assert.equal((await corrupt.capture(base)).ok,false);
});
