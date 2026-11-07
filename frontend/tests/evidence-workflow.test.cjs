const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const {buildSync} = require('esbuild');
const React = require('react');
const {renderToStaticMarkup} = require('react-dom/server');
require.extensions['.css']=()=>{};
const root = path.resolve(__dirname,'..');
const output = buildSync({stdin:{contents: `export * from './src/research'; export * from './src/research-records'; export * from './src/case-navigation'; export * from './src/automation'; export * from './src/claim-checks'; export * from './src/paypal-account'; export * from './src/delivery-location';`,resolveDir:root,loader:'tsx'},bundle:true,write:false,format:'cjs',platform:'node',packages:'external',loader:{'.css':'empty'}});
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

test('claim inspector exposes which field/value failed without rejecting a valid quote',()=>{
 const claim={field:'refund_status',value:'ordered_to_pay',source_check:'exact_quote_found',structured_check:'value_not_found_in_quote',semantic_support:'entailed'};
 const before=JSON.stringify(claim),html=render(ui.ClaimChecks,{claim});
 assert.match(html,/refund status/);assert.match(html,/<code>ordered_to_pay<\/code>/);
 assert.match(html,/Literal value check/);assert.match(html,/exact quote found/);assert.match(html,/entailed/);
 assert.match(html,/does not invalidate the source quote/);assert.match(html,/not every number/);
 assert.equal(JSON.stringify(claim),before);
});

test('literal monetary matches and legacy missing fields are displayed honestly',()=>{
 const html=render(ui.ClaimChecks,{claim:{field:'amount',value:'812.02',structured_check:'value_in_quote'}});
 assert.match(html,/<code>812.02<\/code>/);assert.match(html,/Extracted value text found in quote/);
 assert.doesNotMatch(html,/does not invalidate/);
 const legacy=render(ui.ClaimChecks,{claim:{structured_check:'value_not_found_in_quote'}});
 assert.match(legacy,/Not recorded in this revision/);assert.match(legacy,/does not record the field or value/);
 assert.doesNotMatch(legacy,/refund status|ordered_to_pay|812.02/);
});

test('model-extracted field/value strings stay escaped in the inspector',()=>{
 const html=render(ui.ClaimChecks,{claim:{field:'<script>alert(1)</script>',value:'<img src=x onerror=alert(1)>'}});
 assert.doesNotMatch(html,/<script|<img/);assert.match(html,/&lt;script&gt;/);assert.match(html,/&lt;img/);
});

test('PayPal import is a distinct case entry without fabricated consent or manual payment fields',()=>{
 const html=render(ui.PayPalCaseEntry,{onImport:()=>{}});
 assert.match(html,/Import from PayPal/);assert.match(html,/filled automatically/);assert.doesNotMatch(html,/<input|OAuth consent/);
 const notice=render(ui.PayPalConnectionNotice,{connection:{connected:false}});
 assert.match(notice,/No authorized connection/);assert.match(notice,/Typing a transaction ID or email does not grant access/);
 assert.doesNotMatch(notice,/Connect any merchant|Sign in with PayPal/);
});

test('provider receipt separates amounts, account identifiers, missing fields and reported statements',()=>{
 const html=render(ui.PayPalReceipt,{caseData:{id:'case',payment_record_acquisition:{issues:['order_unavailable:403']},paypal_account:{merchant_id:'M1',dispute:{dispute_id:'PP-D-test',disputed_amount:{currency_code:'USD',value:'1.00'},reason:'ITEM_NOT_RECEIVED'},payments:[{capture_id:'CAP1',payment_amount:{currency_code:'USD',value:'5.00'},buyer_id:null,order_id:null}]}},api:()=>{throw Error('Rendering must not mutate');},onUpdated:async()=>{}});
 assert.match(html,/USD 1.00/);assert.match(html,/USD 5.00/);assert.match(html,/Not available from PayPal/);
 assert.match(html,/SANDBOX · TEST FUNDS/);assert.match(html,/not a finding that it is true/);
 assert.match(html,/order unavailable:403/);assert.match(html,/Previously preserved sources are retained/);
 assert.doesNotMatch(html,/Refund payment|Submit evidence|Accept claim/);
});
const locationProps={current:{id:'case',location_authorization:{mode:'off'}},api:async()=>({}),changed:async()=>{},onSource:()=>{}};
test('delivery verification defaults to local privacy and no third-party map',()=>{
 const html=render(ui.DeliveryLocation,locationProps);
 assert.match(html,/Smart Delivery Location Verification/);assert.match(html,/Local comparison only/);
 assert.match(html,/Local comparison sends no address/);assert.doesNotMatch(html,/delivery-map|Verify GPS/);
 assert.match(html,/authorization applies to future evidence/);
});
test('delivery comparison distinguishes explicit PIN, inferred PIN and approximate area points',()=>{
 const current={id:'case',location_authorization:{mode:'area_only'},delivery_location:{status:'LOCATION MISMATCH',checked_at:'2026-11-08T00:00:00Z',extraction:'Source parser',comparisons:[{status:'LOCATION MISMATCH',distance_m:3000,distance_label:'Map estimates, not a parcel route.',supporting_facts:[],conflicting_facts:['Explicit PIN codes differ: 400076 versus 400078.'],limitations:['No proof of non-delivery.']}],mentions:[{id:'L1',source_id:'E1',role:'reported_delivery',address:'Carrier destination 400078',quote:'Reported destination PIN 400078',explicit_postcode:'400078',source_authenticity:'Reported; unverified authenticity.',source_sha256:hash,quote_sha256:textHash,geocode:{status:'resolved',provider:'Photon / OpenStreetMap',precision:'postcode_area',lat:19.149,lon:72.936,inferred_postcode:'400078',uncertainty_basis:'Policy tolerance, not provider accuracy.',response_sha256:hash}}],limitations:['A mismatch is not proof of non-delivery.'],record_sha256:hash}};
 const html=render(ui.DeliveryLocation,{...locationProps,current});
 for(const text of ['LOCATION MISMATCH','3.0 km','Approximate area location','Map-provider PIN (inferred)','not a PIN supplied by the carrier','Interactive source-linked','Inspect source E1','Policy tolerance'])assert.ok(html.includes(text),text);
});
test('malicious address and provider text are escaped and unavailable coordinates are never plotted',()=>{
 const current={id:'case',delivery_location:{status:'UNVERIFIED',checked_at:'2026-11-08T00:00:00Z',comparisons:[],mentions:[{id:'L1',source_id:'E1',role:'intended',address:'<script>bad()</script>',quote:'<img src=x onerror=bad()>',geocode:{status:'provider_unavailable',detail:'Provider unavailable; no location invented.'}}],limitations:[],record_sha256:hash}};
 const html=render(ui.DeliveryLocation,{...locationProps,current});assert.ok(html.includes('&lt;script&gt;'));assert.doesNotMatch(html,/<script>|<img|delivery-map/);assert.match(html,/Provider unavailable/);
});
