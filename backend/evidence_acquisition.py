"""Prepare useful evidence requests with the analysis, without contacting anyone."""
from store import digest,now
import re

def request_purpose(request):
    text=(request.get('title','')+' '+request.get('question','')).casefold()
    if re.search(r'address|destination',text) and re.search(r'original|checkout|time of (?:purchase|order)|captured',text):return 'original_checkout_address'
    if re.search(r'proof of delivery|delivery confirmation|delivery receipt|delivery or service fulfillment',text):return 'delivery_proof'
    return None

def same_request(a,b):
    if a.get('recipient')!=b.get('recipient'):return False
    if a.get('question','').strip().casefold()==b.get('question','').strip().casefold():return True
    def ids(r):return {v.casefold() for v in re.findall(r'\b(?:order|transaction|capture)\s+([a-zA-Z0-9-]{6,})',r.get('question','')) if re.search(r'\d',v)}
    ai,bi=ids(a),ids(b)
    if ai and bi and not ai.intersection(bi):return False
    purpose=request_purpose(a)
    return bool(purpose and purpose==request_purpose(b))

def prior_request(suggestion,case):
    # A specific defect in a received reply may justify a genuinely different
    # follow-up. It cannot override an unavailable/withdrawn response.
    linked=next((r for r in case.get('requests',[]) if r['id']==suggestion.get('follow_up_to')),None)
    if linked and linked.get('status')=='received' and len(suggestion.get('unresolved_defect','').strip())>=20 and not response_unavailable(linked,case) and suggestion.get('question','').strip()!=linked.get('question','').strip():
        return None
    matches=[r for r in case.get('requests',[]) if same_request(suggestion,r)]
    return matches[-1] if matches else None

def supplied_record(suggestion,case):
    if suggestion.get('follow_up_to') and suggestion.get('unresolved_defect'):return None
    purpose=request_purpose(suggestion)
    pattern={'original_checkout_address':r'original.*(?:checkout|shipping|order).*address|original checkout address',
        'delivery_proof':r'proof of delivery|delivery confirmation|delivery receipt'}.get(purpose)
    if not pattern:return None
    return next((e for e in reversed(case.get('evidence',[])) if e.get('party')==suggestion.get('recipient') and re.search(pattern,e.get('title',''),re.I)),None)

def response_unavailable(request,case):
    source=next((e for e in case.get('evidence',[]) if e['id']==request.get('evidence_id')),None)
    if not source:return False
    return bool(re.search(r"\b(?:unavailable|not available|(?:do not|don't) have access|cannot (?:access|retrieve|provide))\b",source.get('title','')+' '+source.get('text',''),re.I))


def prepare_requests(result,case):
    plan=[]
    for suggestion in result.get('requests',[]):
        existing=prior_request(suggestion,case)
        state={'open':'link_ready','received':'response_received','unavailable':'reported_unavailable','withdrawn':'withdrawn'}.get((existing or {}).get('status'),'prepared')
        if existing and response_unavailable(existing,case):state='reported_unavailable'
        supplied=supplied_record(suggestion,case) if not existing else None
        if supplied:state='evidence_received'
        plan.append({'id':'A-'+digest({'question':suggestion['question'],'recipient':suggestion['recipient']})[:16],
            'suggestion_id':suggestion['id'],'state':state,'prepared_at':now(),
            'title':suggestion['title'],'question':suggestion['question'],'recipient':suggestion['recipient'],
            'rationale':suggestion['rationale'],'priority':suggestion['priority'],
            'request_id':existing['id'] if existing else None,
            'source_id':supplied['id'] if supplied else (existing or {}).get('evidence_id'),
            'contact_authorization':'A private response link can be created by the authorized owner. No external contact or disclosure is performed by preparation.',
            'message_sent_by_verdict':False,'input_digest':result.get('input_digest')})
    # A completed/unavailable request is history, never the next instruction.
    actionable=next((p for p in plan if p['state']=='prepared'),None)
    if actionable:result['recommendation']=actionable['question']
    elif any(p['state']=='link_ready' for p in plan):result['recommendation']='Waiting for the existing requested response.'
    else:result['recommendation']='No new evidence request is prepared. Existing responses and limitations are retained.'
    return plan

def reconcile_requests(result,case):
    """Keep addressed suggestions in diagnostics, not the active request list."""
    result['proposed_requests']=list(result.get('requests',[]))
    plan=prepare_requests(result,case);active=[]
    for suggestion,row in zip(result['proposed_requests'],plan):
        if row['state'] not in ('prepared','link_ready'):continue
        duplicate=next((r for r in active if same_request(suggestion,r)),None)
        if duplicate:
            row.update(state='duplicate_prepared',duplicate_of=duplicate['id'])
        else:active.append(suggestion)
    result['requests']=active
    result['acquisition_plan']=plan
    return result
