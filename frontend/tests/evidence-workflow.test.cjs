const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const {buildSync} = require('esbuild');
const React = require('react');
const {renderToStaticMarkup} = require('react-dom/server');
require.extensions['.css']=()=>{};
const root = path.resolve(__dirname,'..');
const output = buildSync({stdin:{contents: `export * from './src/research'; export * from './src/research-records'; export * from './src/case-navigation'; export * from './src/automation'; export * from './src/claim-checks'; export * from './src/paypal-account'; export * from './src/delivery-location'; export * from './src/experience'; export * from './src/assessment-view'; export * from './src/account-settings'; export * from './src/evidence-reading'; export * from './src/autonomous-resolution';`,resolveDir:root,loader:'tsx'},bundle:true,write:false,format:'cjs',platform:'node',packages:'external',loader:{'.css':'empty'}});
const compiled = new Module(path.join(root,'tests','compiled.cjs'),module);
compiled.filename=path.join(root,'tests','compiled.cjs');compiled.paths=Module._nodeModulePaths(root);
compiled._compile(output.outputFiles[0].text,compiled.filename);
const ui=compiled.exports;
const render=(Component,props)=>renderToStaticMarkup(React.createElement(Component,props));
const hash='a'.repeat(64),textHash='b'.repeat(64);

test('duplicate overview facts and graph nodes collapse without losing citation links',()=>{
 const claims=[{id:'C1',source_id:'E1',text:'Buyer reports non-receipt.',semantic_support:'entailed'},
  {id:'C2',source_id:'E2',text:'Buyer reports non-receipt.',semantic_support:'entailed'},
  {id:'C3',source_id:'E1',text:'Buyer names a different destination.',semantic_support:'entailed'}];
 const before=JSON.stringify(claims),g=ui.graphClaims(claims);
 assert.equal(g.claims.length,2);assert.equal(g.aliases.get('C2'),'C1');assert.equal(g.claims[0].additional_citations[0].source_id,'E2');
 assert.equal(JSON.stringify(claims),before);
 const current={evidence:[],requests:[],analysis:{claims:claims.map(c=>({...c,source_check:'exact_quote_found'})),requests:[],unknowns:[],finding:'conflicting',overview_summary:'The delivery accounts conflict.',assessment_quality_version:2}};
 const html=render(ui.CaseOverview,{current,onEvidence:()=>{},onRequest:()=>{},onSource:()=>{}});
 assert.equal((html.match(/Buyer reports non-receipt\./g)||[]).length,1);
 assert.doesNotMatch(html,/PICTURE SO FAR|STORY SO FAR/);assert.match(html,/Buyer names a different destination/);
});

test('old repeated paragraphs are kept out of the overview and graph without editing saved records',()=>{
 const long='An entire uploaded statement repeated as a claim. '.repeat(8),claims=[{id:'C1',source_id:'E1',text:long},{id:'C2',source_id:'E2',text:long}];
 const before=JSON.stringify(claims);assert.equal(ui.visibleClaims(claims).length,0);assert.equal(ui.graphClaims(claims).claims.length,0);assert.equal(JSON.stringify(claims),before);
});

test('closed reworded evidence requests are history rather than the next task',()=>{
 const w={id:'W1',title:'Original checkout address',question:'Please supply the raw checkout shipping address.',recipient:'payment_provider',priority:'first'};
 const current={evidence:[],requests:[{id:'R1',title:'Original order shipping address',question:'Please provide the original order shipping address.',recipient:'payment_provider',status:'received'}],analysis:{claims:[],requests:[w],unknowns:[],finding:'insufficient',overview_summary:'The original address remains unverified.',assessment_quality_version:2}};
 assert.equal(ui.nextRequest(current),undefined);
 const html=render(ui.CaseOverview,{current,onEvidence:()=>{},onRequest:()=>{},onSource:()=>{}});
 assert.match(html,/No new request prepared/);assert.doesNotMatch(html,/Prepared for|Share request|Please supply/);
 assert.match(render(ui.EvidenceRequestAction,{current,witness:w,onShare:()=>{}}),/Response received/);
});

test('a new independent carrier source is not hidden by a received seller confirmation',()=>{
 const w={id:'W1',title:'Proof of delivery',question:'Please provide proof of delivery.',recipient:'carrier',priority:'first'};
 const current={requests:[{...w,id:'R1',recipient:'seller',status:'received'}],analysis:{requests:[w]}};
 assert.equal(ui.nextRequest(current).id,'W1');
});
test('exhausted provider retries name the service problem without blaming evidence',()=>{
 const html=render(ui.AutomaticInvestigation,{current:{id:'case',automation:{state:'failed',stage:'needs_attention',progress:{last_failure:{code:'model_unavailable',http_status:503,summary:'Gemini is temporarily unavailable.'}}}},api:async()=>{},changed:async()=>{}});
 assert.match(html,/AI service unavailable/);assert.match(html,/Reassessment has stopped/);assert.match(html,/HTTP 503/);
 assert.doesNotMatch(html,/add the missing information|Trying again automatically|spin/);
});
test('stale assessments describe stopped queued paused and active states honestly',()=>{
 for(const [state,expected] of [['failed','update could not finish'],['queued','update is queued'],['paused','Investigation is paused'],['running','VERDICT investigates the update']]){
  const html=render(ui.AssessmentFreshness,{current:{analysis_stale:true,automation:{state}}});assert.ok(html.includes(expected));
  if(state!=='running')assert.doesNotMatch(html,/while VERDICT investigates/);
 }
 assert.equal(render(ui.AssessmentFreshness,{current:{analysis_stale:false,automation:{state:'failed'}}}),'');
});
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
 for(const label of ['Investigation','Witnesses · 2','Timeline','Findings'])assert.ok(html.includes(label));
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
 assert.match(html,/Automatically discovered source/);assert.match(html,/Not independently verified/);assert.match(html,/Origin unverified/);
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
 assert.match(html,/HTTP 403/);assert.match(html,/HTTP 403/);assert.match(html,/Technical activity record/);
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
 assert.match(html,/test funds/);assert.match(html,/statements still need assessment/);
 assert.match(html,/order unavailable:403/);assert.match(html,/Previously preserved sources are retained/);
 assert.doesNotMatch(html,/Refund payment|Submit evidence|Accept claim/);
});
const locationProps={current:{id:'case',location_authorization:{mode:'off'}},api:async()=>({}),changed:async()=>{},onSource:()=>{}};
test('delivery verification defaults to local privacy and no third-party map',()=>{
 const html=render(ui.DeliveryLocation,locationProps);
 assert.equal(html,''); // No irrelevant map settings before any address evidence exists.
});
test('delivery comparison distinguishes explicit PIN, inferred PIN and approximate area points',()=>{
 const current={id:'case',location_authorization:{mode:'area_only'},delivery_location:{status:'LOCATION MISMATCH',checked_at:'2026-11-08T00:00:00Z',extraction:'Source parser',comparisons:[{intended_id:'L0',reported_delivery_id:'L1',status:'LOCATION MISMATCH',distance_m:3000,distance_label:'Map estimates, not a parcel route.',supporting_facts:[],conflicting_facts:['Explicit PIN codes differ: 400076 versus 400078.'],limitations:['No proof of non-delivery.']}],mentions:[{id:'L1',source_id:'E1',role:'reported_delivery',address:'Carrier destination 400078',quote:'Reported destination PIN 400078',explicit_postcode:'400078',source_authenticity:'Reported; unverified authenticity.',source_sha256:hash,quote_sha256:textHash,geocode:{status:'resolved',provider:'Photon / OpenStreetMap',precision:'postcode_area',lat:19.149,lon:72.936,inferred_postcode:'400078',uncertainty_basis:'Policy tolerance, not provider accuracy.',response_sha256:hash}}],limitations:['A mismatch is not proof of non-delivery.'],record_sha256:hash}};
 const html=render(ui.DeliveryLocationDiagnostics,{...locationProps,current});
 for(const text of ['LOCATION MISMATCH','3.0 km','Approximate area location','Map-provider PIN (inferred)','not a PIN supplied by the carrier','Inspect source E1','Policy tolerance'])assert.ok(html.includes(text),text);
});
test('malicious address and provider text are escaped and unavailable coordinates are never plotted',()=>{
 const current={id:'case',delivery_location:{status:'UNVERIFIED',checked_at:'2026-11-08T00:00:00Z',comparisons:[],mentions:[{id:'L1',source_id:'E1',role:'intended',address:'<script>bad()</script>',quote:'<img src=x onerror=bad()>',geocode:{status:'provider_unavailable',detail:'Provider unavailable; no location invented.'}}],limitations:[],record_sha256:hash}};
 const html=render(ui.DeliveryLocationDiagnostics,{...locationProps,current});assert.ok(html.includes('&lt;script&gt;'));assert.doesNotMatch(html,/<script>|<img|delivery-map/);assert.match(html,/Provider unavailable/);
});
test('overview leads with findings and an automatically prepared evidence request, without model or hash jargon',()=>{
 const current={evidence:[{id:'E1'}],analysis:{finding:'conflicting',summary:'The buyer reports no delivery; the carrier lists another postcode.',claims:[{id:'C1',text:'The carrier names a different PIN.',source_id:'E1',quote:'400078',semantic_support:'entailed',source_check:'exact_quote_found'}],requests:[{id:'W1',title:'Delivery receipt',recipient:'carrier',priority:'first',rationale:'It can establish the reported destination.'}],unknowns:['Who received the parcel?']}};
 const html=render(ui.CaseOverview,{current,onEvidence:()=>{},onRequest:()=>{},onSource:()=>{}});
 for(const t of ['What does the evidence suggest?','Why this matters','Share request','Delivery company','reported information, not independent proof'])assert.ok(html.includes(t),t);
 assert.doesNotMatch(html,/Gemini|SHA-256|PostgreSQL|Reassess case|Investigate case/);
});
test('timeline shows changed assessment with technical hashes only inside disclosure',()=>{
 const html=render(ui.CaseTimeline,{events:[{hash:'a'.repeat(64),at:'2026-11-08T00:00:00Z',kind:'investigation_updated',data:{finding:'supports_buyer',analysis:{change:{previous_finding:'insufficient',current_finding:'supports_buyer'}}}}],onSource:()=>{}});
 assert.match(html,/Before: More evidence needed/);assert.match(html,/After: Evidence supports the buyer/);assert.match(html,/<details class="technical-record"><summary>Technical record/);
});
test('temporary failure message promises recovery only for an actual scheduled retry',()=>{
 const html=render(ui.AutomaticInvestigation,{current:{id:'case',automation:{state:'queued',stage:'retry_wait',enabled:true,retry_at:'2026-11-08T12:00:00Z',progress:{}}},api:async()=>{},changed:async()=>{}});
 assert.match(html,/Trying again automatically/);assert.match(html,/Next eligible attempt/);
 const failed=render(ui.AutomaticInvestigation,{current:{id:'case',automation:{state:'failed',stage:'needs_attention',enabled:true,progress:{}}},api:async()=>{},changed:async()=>{}});
 assert.doesNotMatch(failed,/Trying again automatically/);
});
test('currency field is a keyboard-selectable searchable combobox with a form value',()=>{
 const html=render(ui.CurrencyField,{});assert.match(html,/role="combobox"/);assert.match(html,/name="currency" value="USD"/);assert.match(html,/US Dollar/);
});
test('campus fallback shows its actual map identity and never claims the exact gate',()=>{
 const current={id:'case',location_authorization:{mode:'address'},delivery_location:{status:'POSSIBLE MATCH',comparisons:[],mentions:[{id:'L1',source_id:'E1',role:'intended',address:'IIT Bombay Main Gate, Powai, Mumbai, Maharashtra',quote:'Intended destination: IIT Bombay Main Gate, Powai, Mumbai, Maharashtra',geocode:{status:'resolved',precision:'site',accuracy_label:'Approximate campus location; exact gate or entrance not confirmed.',label:'Indian Institute of Technology Bombay, Mumbai, Maharashtra, India',attempts:[{query:'Indian Institute of Technology Bombay, Mumbai, Maharashtra',status:'resolved',response_sha256:hash}]}}]}};
 const html=render(ui.DeliveryLocationDiagnostics,{...locationProps,current});assert.match(html,/Approximate campus location; exact gate or entrance not confirmed/);assert.match(html,/Map result: Indian Institute of Technology Bombay/);assert.match(html,/IIT Bombay Main Gate, Powai, Mumbai, Maharashtra/);
 assert.match(html,/Lookup 1:/);assert.doesNotMatch(html,/Map-estimated entrance location/);
});

const quietCase={id:'case',location_authorization:{mode:'address'},delivery_location:{version:3,status:'LOCATION MISMATCH',comparisons:[{status:'LOCATION MISMATCH',supporting_facts:[],conflicting_facts:[],limitations:[],explanation:'The order names IIT Bombay Main Gate; the delivery record names Bhandup Railway Station, a different destination. This compares the records; it does not establish physical delivery.',source_ids:['E1','E2'],distance_m:2740}],mentions:[{id:'L1',role:'intended',source_id:'E1',geocode:{status:'resolved',lat:19.1326186,lon:72.9149702,precision:'site',provider:'Photon'}},{id:'L2',role:'reported_delivery',source_id:'E2',geocode:{status:'resolved',lat:19.1442357,lon:72.9379711,precision:'site'}}]}};
test('normal location view contains only the map and distance after a resolved pair',()=>{
 const current=JSON.parse(JSON.stringify(quietCase));
 Object.assign(current.delivery_location.comparisons[0],{intended_id:'L1',reported_delivery_id:'L2',sufficiently_precise:false});
 const html=render(ui.DeliveryLocation,{...locationProps,current});
 assert.match(html,/class="delivery-map"/);assert.match(html,/≈ 2.7 km/);
 assert.doesNotMatch(html,/<h[1-6]|<p|<button|<details|Advanced review|View intended|View delivery|different destination|doesn&#x27;t match|Photon|GPS|Green:|geocod|Allow automatic/);
});

test('unresolved, stale, invalid or unpaired locations never invent a map distance',()=>{
 for(const change of [c=>c.delivery_location.version=2,c=>c.delivery_location.comparisons[0].distance_m=null,
   c=>c.delivery_location.comparisons[0].distance_m=-1,c=>c.delivery_location.mentions[1].geocode.status='ambiguous',
   c=>c.delivery_location.mentions[1].geocode.lat=91,c=>c.delivery_location.mentions[1].geocode.lon='72.9',
   c=>c.delivery_location.comparisons[0].reported_delivery_id='missing',c=>c.analysis_stale=true,
   c=>c.automation={state:'running'},c=>c.automation={state:'queued'}]){
  const current=JSON.parse(JSON.stringify(quietCase));Object.assign(current.delivery_location.comparisons[0],{intended_id:'L1',reported_delivery_id:'L2'});
  change(current);assert.equal(render(ui.DeliveryLocation,{...locationProps,current}),'');
 }
});

for(const [distance,expected] of [[0,'<200 m'],[199,'<200 m'],[199.9,'<200 m'],[200,'200 m'],[201,'201 m'],[450,'450 m'],[2740,'2.7 km']]){
 test(`distance badge formats ${distance} metres as ${expected}`,()=>{
  assert.equal(ui.distanceLabel(distance),expected);
 });
}
test('distance display respects configured tolerance and keeps coarse estimates qualified without paragraphs',()=>{
 assert.equal(ui.distanceLabel(230,250),'<250 m');assert.equal(ui.distanceLabel(250,250),'250 m');
 assert.equal(ui.distanceLabel(2740,200,true),'≈ 2.7 km');assert.equal(ui.distanceLabel(199,NaN),'<200 m');
 for(const value of [NaN,Infinity,-1,null,'200'])assert.equal(ui.distanceLabel(value),null);
});
test('account revocation prevents even preserved map results from requesting tiles',()=>{
 const current=JSON.parse(JSON.stringify(quietCase));Object.assign(current.delivery_location.comparisons[0],{intended_id:'L1',reported_delivery_id:'L2'});
 current.effective_map_preference={mode:'off',has_account_choice:true};
 assert.equal(render(ui.DeliveryLocation,{...locationProps,current}),'');
});
test('advanced diagnostics do not mount a hidden map until opened',()=>{
 const html=render(ui.LocationTechnicalRecord,{...locationProps,current:quietCase});
 assert.match(html,/Technical location record/);assert.doesNotMatch(html,/delivery-map|Photon|Approximate separation/);
});

test('ordinary investigations never prompt for per-case geocoding consent',()=>{
 const current={...quietCase,location_authorization:{mode:'off'}};
 const ordinary=render(ui.DeliveryLocation,{...locationProps,current});
 assert.doesNotMatch(ordinary,/Allow automatic|Photon|OpenStreetMap|select|checkbox|Map settings/);
 const diagnostics=render(ui.DeliveryLocationDiagnostics,{...locationProps,current});
 assert.match(diagnostics,/account Settings/);assert.match(diagnostics,/Local comparison continues/);
 assert.doesNotMatch(diagnostics,/<select|type="checkbox"|delivery-map/);
});

test('prepared requests offer sharing directly without a reviewer form or a claim of contact',()=>{
 const witness={id:'W1',recipient:'seller',question:'Supply the original order.'};
 const html=render(ui.EvidenceRequestAction,{current:{requests:[],analysis:{acquisition_plan:[{suggestion_id:'W1',state:'prepared'}]}},witness,onShare:()=>{}});
 assert.match(html,/Share request/);assert.match(html,/Prepared automatically/);assert.match(html,/VERDICT sends no message/);
 assert.doesNotMatch(html,/Human review|reviewed invitation|<form|<input|<textarea/);
});
for(const [status,message] of [['open','Waiting for the requested response'],['received','Response received'],['unavailable','Source reported unavailable'],['withdrawn','Request closed']]){
 test(`prepared requests preserve ${status} outcomes and do not offer duplicate invitations`,()=>{
  const witness={id:'W1',recipient:'seller',question:'Supply the original order.'};
  const current={requests:[{...witness,status}],analysis:{acquisition_plan:[{suggestion_id:'W1',state:'prepared'}]}};
  const html=render(ui.EvidenceRequestAction,{current,witness,onShare:()=>{}});
  assert.ok(html.includes(message));assert.doesNotMatch(html,/<button|Share request/);
 });
}

test('ordinary overview suppresses technical location narrative while retaining source access',()=>{
 const current={...quietCase,evidence:[{id:'E1'}],analysis:{finding:'conflicting',summary:'Photon found destinations 2.7 km apart at 19.1326186, 72.9149702.',claims:[{id:'C1',text:'The GPS estimates are 2.7 km apart.',source_id:'E1',quote:'IIT Bombay',semantic_support:'entailed',source_check:'exact_quote_found'}],requests:[{id:'W1',title:'GPS coordinates',recipient:'carrier',priority:'first',rationale:'Verify proximity threshold.'}],unknowns:['Exact GPS accuracy?']}};
 const html=render(ui.CaseOverview,{current,onEvidence:()=>{},onRequest:()=>{},onSource:()=>{}});assert.doesNotMatch(html.replace(/<svg[\s\S]*?<\/svg>/g,''),/Photon|19\.132|72\.914|2\.7|GPS|proximity threshold/);assert.match(html,/source-backed findings/);assert.match(html,/Inspect the supporting address evidence/);assert.match(html,/Delivery destination evidence/);
 assert.match(render(ui.DeliveryLocationDiagnostics,{...locationProps,current}),/Full investigation assessment/);
});


test('machine reading exposes uncertainty and original integrity without claiming authenticity',()=>{
 const html=render(ui.ExtractionDetails,{source:{extraction:{status:'uncertain',original_sha256:hash,text_sha256:textHash,warning:'Machine transcription may contain errors.',pages:[{page:1,method:'tesseract',status:'uncertain',vision:{writing:'handwritten',uncertainty:['Faded total is unclear']}}]}}});
 assert.match(html,/inspect the original/);assert.match(html,/Faded total is unclear/);assert.match(html,/authenticity unverified/);assert.match(html,RegExp(hash));
});
test('unreadable originals are retained with no invented content',()=>{
 const html=render(ui.ExtractionDetails,{source:{extraction:{status:'unreadable',original_sha256:hash,warning:'Original file preserved.'}}});
 assert.match(html,/Couldn’t reliably read/);assert.match(html,/Original file preserved/);assert.doesNotMatch(html,/Refunded|Resolved/);
});
test('sandbox financial opt-in is explicit limited and never shown as a completed refund',()=>{
 const html=render(ui.SandboxAutonomy,{api:async()=>({enabled:false})});
 assert.match(html,/sandbox merchant/);assert.match(html,/24 hours/);assert.match(html,/required/);assert.match(html,/Enable sandbox autonomy/);assert.doesNotMatch(html,/Resolved —/);
});
