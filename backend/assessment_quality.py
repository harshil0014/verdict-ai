"""Source-bound presentation and conservative extraction checks, without inference."""
import re

VERSION=2

def key(text):
    return ' '.join(re.findall(r'\w+',str(text).casefold()))

def claim_defect(claim):
    text=claim.get('text','').strip()
    if len(text)>240 or len(text.split())>48:
        return 'Claim is a paragraph rather than one concise fact'
    value=claim.get('value','').strip()
    if claim.get('field')=='amount' and value.casefold() not in ('','unknown','unavailable','not supplied','not provided') and not re.fullmatch(r'(?:[A-Z]{3}\s*)?[$€£₹]?\s*[\d,]+(?:\.\d+)?(?:\s*[A-Z]{3})?',value):
        return 'The amount field contains a non-monetary value'
    return None

def deduplicate(result,merge_sources=True):
    """Merge repeated facts; keep every distinct source citation and graph edge."""
    kept=[];seen={};aliases={};duplicates=[]
    for c in result['claims']:
        identity=(key(c.get('text','')),key(c.get('subject','')),c.get('field'),key(c.get('value','')),c.get('stance'),c.get('epistemic_status'),c.get('semantic_support'))
        if not merge_sources:identity+=(c['source_id'],key(c['quote']))
        if identity not in seen:
            seen[identity]=c;kept.append(c);continue
        prior=seen[identity];aliases[c['id']]=prior['id'];duplicates.append({'claim':c['id'],'merged_into':prior['id']})
        if c['source_id']!=prior['source_id'] or c['quote']!=prior['quote']:
            citation={k:v for k,v in c.items() if k not in ('id','text','subject','field','value','stance','additional_citations')}
            if citation not in prior.setdefault('additional_citations',[]):prior['additional_citations'].append(citation)
    result['claims']=kept;result.setdefault('duplicate_claims',[]).extend(duplicates)
    for h in result['hypotheses']:
        for field in ('supports','challenges'):
            h[field]=list(dict.fromkeys(aliases.get(x,x) for x in h[field]))
    return result

def attributed_text(claim,source):
    text=claim.get('concise_text') or claim['text']
    if source.get('provenance'):
        label={'document_finding':'Decision finding','document_order':'Decision order','current_policy':'Current policy'}.get(claim.get('epistemic_status'),'Public document reports')
    elif source.get('origin_verified') and source.get('origin')=='paypal_sandbox_api':label='PayPal API record'
    else:label={'buyer':'Buyer’s submitted account','seller':'Seller’s submitted record','carrier':'Submitted delivery-company record','payment_provider':'Uploaded payment record'}.get(source.get('party'),'Submitted document')
    return label+': '+text

def highlights(claims,limit=3):
    eligible=[c for c in claims if c.get('semantic_support')=='entailed' and not claim_defect(c)]
    selected=[];texts=set();sources=set();fields=set()
    while eligible and len(selected)<limit:
        eligible.sort(key=lambda c:(c['source_id'] not in sources,c.get('field') not in fields),reverse=True)
        c=eligible.pop(0);identity=key(c.get('concise_text') or c['text'])
        if identity in texts:continue
        selected.append(c);texts.add(identity);sources.add(c['source_id']);fields.add(c.get('field'))
    return selected

def finalize(result,case):
    sources={e['id']:e for e in case['evidence']}
    for c in result['claims']:
        c['display_text']=attributed_text(c,sources.get(c['source_id'],{}))
    result['proposed_narrative']={'summary':result['summary'],'recommendation':result['recommendation']}
    selected=highlights(result['claims'])
    result['highlight_claim_ids']=[c['id'] for c in selected]
    # Free-form narrative was not semantically checked. Publish only facts that
    # passed the source/support checks, explicitly attributed to their origin.
    result['summary']=' '.join(c['display_text'].rstrip('. ')+'.' for c in selected) if selected else 'No sufficiently supported facts could be extracted. The original evidence is preserved.'
    delivery=case.get('reason')=='ITEM_NOT_RECEIVED' or bool(case.get('delivery_location'))
    if delivery and result['finding']=='supports_seller' and not any(e.get('party')=='carrier' and e.get('origin_verified') for e in sources.values()):
        result['finding']='insufficient'
    if delivery and case.get('delivery_location',{}).get('status')=='LOCATION MISMATCH':
        overview='The submitted delivery addresses differ. The available records do not establish where the parcel was received.'
    elif delivery and result['finding']=='conflicting':
        overview='The delivery accounts conflict. The submitted records do not independently establish receipt.'
    else:overview={'insufficient':'The available evidence leaves important points unresolved.','conflicting':'The sources describe conflicting accounts. Important points remain unresolved.','supports_buyer':'The supported source passages favor the buyer’s account.','supports_seller':'The supported source passages favor the seller’s account.'}[result['finding']]
    result['overview_summary']=overview
    result['recommendation']='No new evidence request is prepared. Existing responses and limitations are retained.'
    result['assessment_quality_version']=VERSION
    return result
