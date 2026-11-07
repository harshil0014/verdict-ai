const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const {buildSync} = require('esbuild');
const React = require('react');
const {renderToStaticMarkup} = require('react-dom/server');
const root = path.resolve(__dirname,'..');
const output = buildSync({stdin:{contents: `export * from './src/research'; export * from './src/research-records'; export * from './src/case-navigation'; export * from './src/automation';`,resolveDir:root,loader:'tsx'},bundle:true,write:false,format:'cjs',platform:'node',packages:'external',loader:{'.css':'empty'}});
const compiled = new Module(path.join(root,'tests','compiled.cjs'),module);
compiled.filename=path.join(root,'tests','compiled.cjs');compiled.paths=Module._nodeModulePaths(root);
compiled._compile(output.outputFiles[0].text,compiled.filename);
const ui=compiled.exports;
const render=(Component,props)=>renderToStaticMarkup(React.createElement(Component,props));
const hash='a'.repeat(64),textHash='b'.repeat(64);
const records=[
 {id:'already',status:'approved',source_id:'E1',title:'Already in Evidence',url:'https://agency.gov/decision'},
 {id:'staged',status:'ready',title:'Earlier staged PDF',url:'https://agency.gov/staged.pdf',raw_sha256:hash,metadata:{text_sha256:textHash}},
 {id:'dismissed',status:'dismissed',title:'Previously dismissed record',url:'https://agency.gov/old'},
 {id:'failed',status:'unavailable',title:'Unavailable policy',url:'https://agency.gov/policy',failure_message:'HTTP 403. No document was invented.'},
 {id:'report',status:'research_report',title:'Saved search',url:'search:query',google:{provider:'Free discovery',status:'completed',documents:[{title:'Primary lead',url:'https://agency.gov/lead'}]}}
];

test('case navigation is one investigation with no standalone research destination',()=>{
 const html=render(ui.CaseNavigation,{tab:'evidence',evidenceCount:3,witnessCount:2,onSelect:()=>{}});
 assert.equal((html.match(/<button/g)||[]).length,5);
 assert.match(html,/aria-current="page">Evidence · 3/);
 for(const label of ['Investigation','Witnesses · 2','Timeline','Human review'])assert.ok(html.includes(label));
 assert.doesNotMatch(html,/Public research/);
});

test('retained discoveries remain inspectable without duplicating collected evidence or failures',()=>{
 const original=JSON.stringify(records);
 const html=render(ui.DiscoveryRecords,{records,evidenceIds:['E1'],onInspect:()=>{}});
 assert.match(html,/Earlier staged PDF/);assert.match(html,/Previously dismissed record/);
 assert.match(html,/https:\/\/agency.gov\/staged.pdf/);assert.ok(html.includes(hash));assert.ok(html.includes(textHash));
 assert.doesNotMatch(html,/Already in Evidence|Unavailable policy|Saved search/);
 assert.equal(JSON.stringify(records),original);
});

test('retrieval failures and provider leads remain accessible as investigation history',()=>{
 const html=render(ui.ActivityRecords,{records});
 assert.match(html,/HTTP 403/);assert.match(html,/Free discovery/);assert.match(html,/Primary lead/);
 assert.match(html,/https:\/\/agency.gov\/lead/);assert.doesNotMatch(html,/Earlier staged PDF/);
 assert.match(html,/leads, not original source passages/);
});

test('evidence provenance shows requested and final URLs, both hashes and honest review status',()=>{
 const html=render(ui.PublicSourceFacts,{source:{sha256:hash,provenance:{requested_url:'https://agency.gov/original',final_url:'https://agency.gov/resolved',text_sha256:textHash,acquisition_mode:'embedded_reference',review_status:'unreviewed'}}});
 assert.match(html,/Automatically discovered source/);assert.match(html,/Not human reviewed/);assert.match(html,/Origin unverified/);
 assert.ok(html.includes(hash)&&html.includes(textHash));assert.match(html,/original/);assert.match(html,/resolved/);
 assert.match(html,/Unknown — not inferred/);assert.match(html,/does not establish historical policy/);
});

test('hostile source text stays escaped and credential or executable links are not exposed',()=>{
 const html=render(ui.DiscoveryRecords,{records:[{id:'hostile',status:'ready',title:'<script>alert(1)</script>',url:'javascript:alert(1)',relevance:'<img src=x onerror=alert(1)>'}],evidenceIds:[],onInspect:()=>{}});
 assert.doesNotMatch(html,/<script|<img|href="javascript:/);assert.match(html,/&lt;script&gt;/);
 for(const u of ['javascript:alert(1)','file:///private','https://user:password@example.com/'])assert.equal(ui.safeSourceUrl(u),undefined);
 assert.equal(ui.safeSourceUrl('https://agency.gov/record'),'https://agency.gov/record');
});

test('optional acquisition opens one URL form and offers search without a separate case tab',()=>{
 const api=()=>{throw Error('Rendering optional UI must not send an API mutation');};
 const html=render(ui.FindEvidence,{caseId:'case',api,suggestions:[],completed:async()=>{}});
 assert.match(html,/Find more evidence/);assert.match(html,/Enter a URL/);assert.match(html,/Search the web/);
 assert.equal((html.match(/<form/g)||[]).length,1);assert.match(html,/Add &amp; investigate/);
 assert.doesNotMatch(html,/Approve this exact snapshot|Public research/);
});

test('recovered sources retain the refusal and qualify the identity match',()=>{
 const url='https://www.canlii.org/decision',recovered='https://decisions.civilresolutionbc.ca/decision';
 const html=render(ui.AutomaticInvestigation,{current:{id:'qa',automation:{state:'completed',stage:'complete',enabled:true,progress:{
  references:{[url]:{status:'unavailable',detail:'HTTP 403',recovery:{status:'recovered',citation:'2024 BCCRT 149',url:recovered}}},
  recoveries:{[url]:{citation:'2024 BCCRT 149',status:'recovered',identity_check:{status:'matched'}}}
 }}},api:()=>{throw Error('Display must not mutate');},changed:async()=>{}});
 assert.match(html,/HTTP 403/);assert.match(html,/original refusal is retained/);
 assert.match(html,/2024 BCCRT 149/);assert.match(html,/https:\/\/decisions.civilresolutionbc.ca\/decision/);
 assert.match(html,/does not verify legal truth or identical bytes/);
});
